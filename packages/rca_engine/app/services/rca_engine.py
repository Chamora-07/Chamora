"""
RCAEngine
Orchestrates the full analysis pipeline for a single ML record.
"""

from __future__ import annotations
import asyncio
import logging
from datetime import datetime, timezone
from typing import Any, Dict, List

from ..core.config import settings
from ..models.schemas import (
    MLRecord, RCAResult, MetricsSummary, CorrelationMap,
    BatchRCAResult,
)
from .metrics_analyzer import MetricsAnalyzer
from .synthetic_analyzer import SyntheticAnalyzer
from .gemini_analyzer import GeminiAnalyzer
from .ollama_analyzer import OllamaAnalyzer
from .groq_analyzer import GroqAnalyzer

logger = logging.getLogger(__name__)


class RCAEngine:

    def __init__(self):
        self.metrics_analyzer = MetricsAnalyzer()
        self.gemini = GeminiAnalyzer()
        self.ollama = OllamaAnalyzer()
        self.groq = GroqAnalyzer()

    async def analyze(self, record: MLRecord) -> RCAResult:
        """Full pipeline for a single record."""
        normalized_root_cause = record.root_cause or "GENERAL_DEGRADATION"
        m = record.get_evidence_metrics()

        # Step 1 — anomaly detection + correlation
        report = self.metrics_analyzer.analyze(m)

        # Step 2 — LLM or synthetic analysis
        analysis = None
        if settings.USE_LLM:
            if settings.LLM_PROVIDER == "groq" and self.groq.available:
                analysis = await self.groq.analyze(
                    m=m,
                    anomalies=report.anomalies,
                    corr=report.correlations,
                    ml_severity=record.severity,
                    ml_root_cause=normalized_root_cause,
                )
            elif settings.LLM_PROVIDER == "ollama" and self.ollama.available:
                analysis = await self.ollama.analyze(
                    m=m,
                    anomalies=report.anomalies,
                    corr=report.correlations,
                    ml_severity=record.severity,
                    ml_root_cause=normalized_root_cause,
                )
            elif settings.LLM_PROVIDER == "gemini" and self.gemini.available:
                analysis = await self.gemini.analyze(
                    m=m,
                    anomalies=report.anomalies,
                    corr=report.correlations,
                    ml_severity=record.severity,
                    ml_root_cause=normalized_root_cause,
                )

        if not analysis:
            analysis = SyntheticAnalyzer.analyze(m, report.anomalies, report.correlations)

        # Step 3 — build response
        return RCAResult(
            id=record.id,
            application_id=record.application_id,
            config_id=record.config_id,
            window_timestamp=record.window_timestamp,
            ml_severity=record.severity,
            ml_root_cause=normalized_root_cause,
            root_cause=analysis.root_cause,
            confidence=round(analysis.confidence, 4),
            affected_component=analysis.affected_component,
            evidence=analysis.evidence,
            reasoning=analysis.reasoning,
            recommended_actions=analysis.recommended_actions,
            anomalies_detected=report.anomalies,
            correlations=report.correlations,
            metrics_summary=self._build_metrics_summary(m),
            analysis_source=analysis.source,
            created_at=datetime.now(timezone.utc),
        )

    async def analyze_batch(
        self, records: List[MLRecord], rpm_delay: float | None = None
    ) -> BatchRCAResult:
        """Process a list of records sequentially (respects Gemini rate limits)."""
        delay = rpm_delay if rpm_delay is not None else (
            settings.GEMINI_RPM_DELAY
            if (settings.USE_LLM and settings.LLM_PROVIDER == "gemini" and self.gemini.available)
            else 0.0
        )

        results: List[RCAResult] = []
        for i, record in enumerate(records):
            if i > 0 and delay > 0:
                await asyncio.sleep(delay)
            try:
                result = await self.analyze(record)
                results.append(result)
            except Exception as exc:
                logger.exception("Failed to analyze record %s: %s", record.id, exc)

        return BatchRCAResult(
            total=len(results),
            results=results,
            summary=self._summarise(results),
        )

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _build_metrics_summary(m) -> MetricsSummary:
        return MetricsSummary(
            cpu_usage_pct=round(m.cpu_usage_rate * 100, 2),
            memory_usage_gb=round(m.memory_usage / 1e9, 3),
            memory_pressure_pct=round(m.memory_pressure * 100, 2),
            memory_growth_mbps=round(m.memory_growth_rate / 1e6, 2),
            latency_p95_ms=round(m.latency_p95 * 1000, 2),
            error_rate_pct=round(m.error_rate * 100, 4),
            disk_io_pct=round(m.disk_io_rate * 100, 2),
            net_throughput_mbps=round(m.net_throughput, 2),
            failure_streak=m.failure_streak,
        )

    @staticmethod
    def _summarise(results: List[RCAResult]) -> Dict[str, Any]:
        if not results:
            return {}

        from collections import Counter
        import statistics

        confidences = [r.confidence for r in results]
        return {
            "total": len(results),
            "root_cause_distribution": dict(Counter(r.root_cause for r in results)),
            "component_distribution": dict(Counter(r.affected_component for r in results)),
            "analysis_source_distribution": dict(Counter(r.analysis_source for r in results)),
            "confidence": {
                "mean": round(statistics.mean(confidences), 3),
                "min":  round(min(confidences), 3),
                "max":  round(max(confidences), 3),
                "stdev": round(statistics.stdev(confidences), 3) if len(confidences) > 1 else 0.0,
            },
        }
