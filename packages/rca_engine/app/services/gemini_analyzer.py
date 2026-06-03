"""
GeminiAnalyzer
Calls Gemini 2.5 Flash-Lite to produce structured RCA output.
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


class GeminiAnalyzer:

    def __init__(self):
        self.api_key = settings.GEMINI_API_KEY
        self.available = bool(self.api_key)
        if not self.available:
            logger.warning("GEMINI_API_KEY not set — using synthetic fallback for all requests.")

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
        """Return LLM-based analysis, falling back to synthetic on any failure."""
        synthetic = SyntheticAnalyzer.analyze(m, anomalies, corr)

        if not self.available:
            return synthetic

        try:
            raw = await self._call_gemini(m, anomalies, corr, ml_severity, ml_root_cause, synthetic)
            result = self._parse(raw, m, anomalies, corr, synthetic)
            if settings.GUARDRAILS_ENABLED:
                result = self._guardrails(result, m, anomalies, corr, synthetic)
            result.source = "llm"
            return result
        except Exception as exc:
            logger.exception("Gemini analysis failed: %s — using synthetic fallback", exc)
            return synthetic

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    async def _call_gemini(
        self,
        m: EvidenceMetrics,
        anomalies: List[str],
        corr: CorrelationMap,
        ml_severity: str,
        ml_root_cause: str,
        synthetic: AnalysisOutput,
    ) -> str:
        prompt = self._build_prompt(m, anomalies, corr, ml_severity, ml_root_cause, synthetic)
        url = (
            f"https://generativelanguage.googleapis.com/v1beta/models/"
            f"{settings.GEMINI_MODEL}:generateContent?key={self.api_key}"
        )
        payload = {
            "contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {"responseMimeType": "application/json"},
        }
        async with httpx.AsyncClient(timeout=settings.GEMINI_TIMEOUT) as client:
            resp = await client.post(url, json=payload)
            resp.raise_for_status()

        data = resp.json()
        return data["candidates"][0]["content"]["parts"][0]["text"]

    def _build_prompt(
        self,
        m: EvidenceMetrics,
        anomalies: List[str],
        corr: CorrelationMap,
        ml_severity: str,
        ml_root_cause: str,
        synthetic: AnalysisOutput,
    ) -> str:
        return f"""You are a senior SRE. Analyze this performance anomaly and return ONLY a raw JSON object.

## ML model alert
- severity: {ml_severity}
- ml_root_cause: {ml_root_cause}

## Detected anomalies
{', '.join(anomalies) if anomalies else 'none'}

## Rule-based pre-analysis (use as strong prior)
- root_cause: {synthetic.root_cause}
- confidence: {synthetic.confidence}
- affected_component: {synthetic.affected_component}

## Container metrics
- CPU usage: {m.cpu_usage_rate:.4f} ({m.cpu_usage_rate:.1%})
- CPU container/node ratio: {m.cpu_container_vs_node_ratio:.4f}
- Memory usage: {m.memory_usage / 1e9:.3f} GB
- Memory pressure: {m.memory_pressure:.4f} ({m.memory_pressure:.1%})
- Memory growth rate: {m.memory_growth_rate / 1e6:.2f} MB/s
- Latency P95: {m.latency_p95 * 1000:.2f} ms
- Error rate: {m.error_rate:.4f} ({m.error_rate:.2%})
- Disk I/O rate: {m.disk_io_rate:.4f}
- Net throughput: {m.net_throughput:.1f} Mbps
- Failure streak: {m.failure_streak}
- Container restarted: {m.has_restart}

## Required JSON keys (all mandatory)
1. "root_cause"          — one of: {', '.join(sorted(VALID_ROOT_CAUSES))}
2. "confidence"          — float 0.0–1.0
3. "affected_component"  — one of: {', '.join(sorted(VALID_COMPONENTS))}
4. "evidence"            — 1–2 sentences citing specific metric values
5. "reasoning"           — 2–3 sentences explaining SRE diagnosis
6. "recommended_actions" — JSON array of 2–3 short actionable strings

Output ONLY valid raw JSON. No markdown fences, no prose outside the JSON."""

    def _parse(
        self,
        raw: str,
        m: EvidenceMetrics,
        anomalies: List[str],
        corr: CorrelationMap,
        synthetic: AnalysisOutput,
    ) -> AnalysisOutput:
        """Extract JSON from LLM response and map to AnalysisOutput."""
        s, e = raw.find("{"), raw.rfind("}") + 1
        if s < 0 or e <= s:
            raise ValueError("No JSON object found in LLM response")

        parsed: Dict[str, Any] = json.loads(raw[s:e])

        root_cause = parsed.get("root_cause", "UNKNOWN")
        if root_cause not in VALID_ROOT_CAUSES:
            root_cause = synthetic.root_cause

        component = parsed.get("affected_component", "APPLICATION")
        if component not in VALID_COMPONENTS:
            component = synthetic.affected_component

        try:
            confidence = float(parsed["confidence"])
            confidence = max(0.0, min(1.0, confidence))
        except (KeyError, TypeError, ValueError):
            confidence = synthetic.confidence

        evidence = parsed.get("evidence") or synthetic.evidence
        reasoning = parsed.get("reasoning") or synthetic.reasoning
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
                "Guardrail: LLM claimed %s but metric correlations disagree — "
                "overriding with synthetic result (%s).",
                result.root_cause,
                synthetic.root_cause,
            )
            synthetic.source = "synthetic_guardrail"
            return synthetic

        return result
