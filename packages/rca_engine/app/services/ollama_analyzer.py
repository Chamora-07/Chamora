"""
OllamaAnalyzer
Calls a local Ollama server running the fine-tuned qwen-sre model to produce structured RCA output.
Applies SRE guardrails to validate/correct the LLM result before returning.
"""

from __future__ import annotations
import json
import logging
from typing import Any, Dict, List, Optional

import httpx

from ..core.config import settings
from ..models.schemas import EvidenceMetrics, CorrelationMap
from .synthetic_analyzer import AnalysisOutput, SyntheticAnalyzer

logger = logging.getLogger(__name__)

# Valid enum values the LLM must produce
VALID_ROOT_CAUSES = {
    "MEMORY_LEAK", "GC_PRESSURE", "CPU_SATURATION", "RESOURCE_CONTENTION",
    "IO_BOTTLENECK", "CONFIGURATION_ISSUE", "APPLICATION_BUG",
    "NETWORK_BOTTLENECK", "UNKNOWN",
}
VALID_COMPONENTS = {
    "APPLICATION", "SCHEDULER", "STORAGE", "DATABASE",
    "CACHE", "NETWORK", "API_SERVER", "MESSAGE_QUEUE",
}


class OllamaAnalyzer:

    def __init__(self):
        self.api_url = settings.OLLAMA_API_URL
        self.model_name = settings.OLLAMA_MODEL
        # We will assume it's available and let requests catch connection failures dynamically,
        # or we can do a quick check later.
        self.available = True

    async def check_availability(self) -> bool:
        """Check if Ollama service is reachable and has the model."""
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                resp = await client.get(f"{self.api_url}/api/tags")
                if resp.status_code == 200:
                    models = [m.get("name") for m in resp.json().get("models", [])]
                    # Check if our model (or its prefix) is in the list
                    has_model = any(self.model_name in m or m in self.model_name for m in models)
                    if not has_model:
                        logger.warning(
                            "Ollama is reachable, but model '%s' is not registered. Registered models: %s",
                            self.model_name, models
                        )
                    return True
                return False
        except Exception as exc:
            logger.warning("Ollama check failed: %s", exc)
            return False

    # ------------------------------------------------------------------
    # Public interface
    # ------------------------------------------------------------------

    async def analyze(
        self,
        m: EvidenceMetrics,
        anomalies: List[str],
        corr: CorrelationMap,
        ml_severity: str,
        ml_root_cause: str,
    ) -> AnalysisOutput:
        """Return Ollama-based analysis, falling back to synthetic on any failure."""
        synthetic = SyntheticAnalyzer.analyze(m, anomalies, corr)

        try:
            raw = await self._call_ollama(m, anomalies, corr, ml_severity, ml_root_cause)
            result = self._parse(raw, m, anomalies, corr, synthetic)
            if settings.GUARDRAILS_ENABLED:
                result = self._guardrails(result, m, anomalies, corr, synthetic)
            result.source = "llm"
            return result
        except Exception as exc:
            logger.exception("Ollama analysis failed: %s — using synthetic fallback", exc)
            return synthetic

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    async def _call_ollama(
        self,
        m: EvidenceMetrics,
        anomalies: List[str],
        corr: CorrelationMap,
        ml_severity: str,
        ml_root_cause: str,
    ) -> str:
        prompt = self._build_prompt(m, anomalies, corr, ml_severity, ml_root_cause)
        url = f"{self.api_url}/api/generate"
        payload = {
            "model": self.model_name,
            "prompt": prompt,
            "stream": False,
            "system": "You are an expert DevOps and performance analyst. Analyze performance metrics and provide root cause analysis in JSON format.",
            "options": {
                "temperature": 0.1,
                "top_p": 0.9,
            }
        }
        async with httpx.AsyncClient(timeout=120.0) as client:
            resp = await client.post(url, json=payload)
            resp.raise_for_status()

        data = resp.json()
        return data["response"]

    def _build_prompt(
        self,
        m: EvidenceMetrics,
        anomalies: List[str],
        corr: CorrelationMap,
        ml_severity: str,
        ml_root_cause: str,
    ) -> str:
        # Construct prompt matching the training prompt structure exactly for the fine-tuned model
        return f"""You are an expert DevOps and performance analyst. Analyze the following performance metrics and provide root cause analysis.

ML Model Output:
- Severity: {ml_severity}
- Initial Root Cause: {ml_root_cause}

Detected Anomalies: {', '.join(anomalies) if anomalies else 'none'}

System Metrics:
- CPU Usage Rate: {m.cpu_usage_rate:.4f}
- Memory Usage: {m.memory_usage / 1e9:.2f} GB
- Memory Pressure: {m.memory_pressure:.4f}
- Memory Growth Rate: {m.memory_growth_rate / 1e6:.2f} MB/s
- Latency P95: {m.latency_p95:.4f}s
- Error Rate: {m.error_rate:.4f}
- Disk I/O Rate: {m.disk_io_rate:.4f}
- Network Throughput: {m.net_throughput:.2f} Mbps
- CPU Container vs Node Ratio: {m.cpu_container_vs_node_ratio:.4f}
- Failure Streak: {m.failure_streak}
- Container Restarts: {m.has_restart}

Task: Provide a JSON response with:
1. "root_cause": specific root cause (one of: MEMORY_LEAK, CPU_SATURATION, NETWORK_BOTTLENECK, APPLICATION_BUG, RESOURCE_CONTENTION, GC_PRESSURE, IO_BOTTLENECK, CONFIGURATION_ISSUE, UNKNOWN)
2. "confidence": confidence score (0.0-1.0)
3. "evidence": brief explanation with key metrics supporting the conclusion
4. "affected_component": which component (API_SERVER, CACHE, DATABASE, MESSAGE_QUEUE, STORAGE, NETWORK, SCHEDULER, APPLICATION)
5. "reasoning": detailed analysis

Format as JSON only."""

    def _parse(
        self,
        raw: str,
        m: EvidenceMetrics,
        anomalies: List[str],
        corr: CorrelationMap,
        synthetic: AnalysisOutput,
    ) -> AnalysisOutput:
        """Extract JSON from Ollama response and map to AnalysisOutput."""
        # Find balanced JSON block
        text = raw.strip()
        json_str = ""
        brace_count = 0
        start_idx = -1
        
        for i, char in enumerate(text):
            if char == '{':
                if brace_count == 0:
                    start_idx = i
                brace_count += 1
            elif char == '}':
                brace_count -= 1
                if brace_count == 0 and start_idx != -1:
                    json_str = text[start_idx:i+1]
                    break
        
        if not json_str:
            s, e = text.find("{"), text.rfind("}") + 1
            if s >= 0 and e > s:
                json_str = text[s:e]

        if not json_str:
            raise ValueError("No JSON object found in Ollama response")

        parsed: Dict[str, Any] = json.loads(json_str)

        root_cause = str(parsed.get("root_cause", "")).strip().upper()
        if root_cause not in VALID_ROOT_CAUSES:
            root_cause = synthetic.root_cause

        component = str(parsed.get("affected_component", "")).strip().upper()
        if component not in VALID_COMPONENTS:
            component = synthetic.affected_component

        try:
            confidence = float(parsed["confidence"])
            confidence = max(0.0, min(1.0, confidence))
        except (KeyError, TypeError, ValueError):
            confidence = synthetic.confidence

        evidence = parsed.get("evidence") or synthetic.evidence
        reasoning = parsed.get("reasoning") or synthetic.reasoning
        
        # Support both array and string recommended actions
        actions = parsed.get("recommended_actions") or synthetic.recommended_actions
        if isinstance(actions, str):
            actions = [actions]

        return AnalysisOutput(
            root_cause=root_cause,
            confidence=confidence,
            affected_component=component,
            evidence=evidence,
            reasoning=reasoning,
            recommended_actions=list(actions),
            source="llm",
        )

    def _guardrails(
        self,
        result: AnalysisOutput,
        m: EvidenceMetrics,
        anomalies: List[str],
        corr: CorrelationMap,
        synthetic: AnalysisOutput,
    ) -> AnalysisOutput:
        """
        SRE guardrails: reject LLM claims that contradict metric evidence.
        Returns corrected AnalysisOutput (may swap to synthetic).
        """
        invalid = (
            (result.root_cause in {"MEMORY_LEAK", "GC_PRESSURE"} and not corr.memory_issue)
            or (result.root_cause in {"CPU_SATURATION", "RESOURCE_CONTENTION"} and not corr.cpu_issue)
            or (result.root_cause == "IO_BOTTLENECK" and not corr.io_issue)
            or (result.confidence < settings.LLM_CONFIDENCE_FLOOR)
        )

        if invalid:
            logger.warning(
                "Guardrail: Ollama/Qwen SRE claimed %s but metric correlations disagree — "
                "overriding with synthetic result (%s).",
                result.root_cause,
                synthetic.root_cause,
            )
            synthetic.source = "synthetic_guardrail"
            return synthetic

        return result
