"""
SyntheticAnalyzer
Pure rule-based analysis used when Gemini is unavailable or as a guardrail
baseline to validate/correct LLM output.
"""

from __future__ import annotations
from dataclasses import dataclass
from typing import List

from ..models.schemas import EvidenceMetrics, CorrelationMap


@dataclass
class AnalysisOutput:
    root_cause: str
    confidence: float
    affected_component: str
    evidence: str
    reasoning: str
    recommended_actions: List[str]
    source: str = "synthetic"


class SyntheticAnalyzer:

    @staticmethod
    def analyze(
        m: EvidenceMetrics,
        anomalies: List[str],
        corr: CorrelationMap,
    ) -> AnalysisOutput:

        if corr.memory_issue:
            return SyntheticAnalyzer._memory(m, anomalies)

        if corr.cpu_issue:
            return SyntheticAnalyzer._cpu(m)

        if corr.io_issue:
            return SyntheticAnalyzer._io(m)

        if corr.infrastructure_issue:
            return SyntheticAnalyzer._infra(m)

        if corr.application_issue:
            return SyntheticAnalyzer._app(m)

        return SyntheticAnalyzer._unknown(anomalies)

    # ------------------------------------------------------------------
    # Private helpers per failure category
    # ------------------------------------------------------------------

    @staticmethod
    def _memory(m: EvidenceMetrics, anomalies: List[str]) -> AnalysisOutput:
        growth_mbps = abs(m.memory_growth_rate) / 1e6
        usage_gb = m.memory_usage / 1e9

        if abs(m.memory_growth_rate) > 100_000_000:   # > 100 MB/s growth
            return AnalysisOutput(
                root_cause="MEMORY_LEAK",
                confidence=0.85,
                affected_component="APPLICATION",
                evidence=(
                    f"Memory growing at {growth_mbps:.1f} MB/s — usage {usage_gb:.2f} GB, "
                    f"pressure {m.memory_pressure:.1%}."
                ),
                reasoning=(
                    "Sustained high-velocity memory growth that GC cannot reclaim suggests an "
                    "active heap leak. Likely unbounded cache, retained listeners, or circular refs."
                ),
                recommended_actions=[
                    "Capture heap dump and inspect retained objects",
                    "Review recent code changes for unbounded collections or missing finalizers",
                    "Set memory limit + alert on >80% usage to trigger proactive restart",
                ],
            )

        return AnalysisOutput(
            root_cause="GC_PRESSURE",
            confidence=0.75,
            affected_component="APPLICATION",
            evidence=(
                f"Memory pressure {m.memory_pressure:.1%}, usage {usage_gb:.2f} GB — "
                "GC cannot keep up with allocation rate."
            ),
            reasoning=(
                "High memory pressure without rapid growth points to GC thrashing: "
                "short-lived objects accumulate faster than GC cycles clear them."
            ),
            recommended_actions=[
                "Tune GC settings (heap size, generation ratios)",
                "Profile allocation hotspots with async-profiler or similar",
                "Consider object pooling for high-frequency allocations",
            ],
        )

    @staticmethod
    def _cpu(m: EvidenceMetrics) -> AnalysisOutput:
        ratio = m.cpu_container_vs_node_ratio

        if ratio > 0.8:
            return AnalysisOutput(
                root_cause="RESOURCE_CONTENTION",
                confidence=0.80,
                affected_component="SCHEDULER",
                evidence=(
                    f"Container consuming {ratio:.1%} of node CPU — "
                    f"container usage {m.cpu_usage_rate:.1%}."
                ),
                reasoning=(
                    "Container is monopolising node CPU, starving co-located pods. "
                    "Likely missing CPU limits or a noisy-neighbour situation."
                ),
                recommended_actions=[
                    "Enforce container CPU limits in pod spec",
                    "Move workload to a dedicated node pool",
                    "Review HPA / VPA settings to redistribute load",
                ],
            )

        return AnalysisOutput(
            root_cause="CPU_SATURATION",
            confidence=0.75,
            affected_component="APPLICATION",
            evidence=(
                f"CPU at {m.cpu_usage_rate:.1%}, latency P95 {m.latency_p95 * 1000:.1f} ms."
            ),
            reasoning=(
                "CPU at or above saturation threshold causing request queuing "
                "and elevated tail latency."
            ),
            recommended_actions=[
                "Scale out horizontally or increase CPU quota",
                "Profile CPU hotspots and optimise hot code paths",
                "Enable rate limiting to shed excess load",
            ],
        )

    @staticmethod
    def _io(m: EvidenceMetrics) -> AnalysisOutput:
        return AnalysisOutput(
            root_cause="IO_BOTTLENECK",
            confidence=0.70,
            affected_component="STORAGE",
            evidence=(
                f"Disk I/O rate {m.disk_io_rate:.1%}, latency P95 {m.latency_p95 * 1000:.1f} ms."
            ),
            reasoning=(
                "Storage throughput saturated. Requests are blocked on slow I/O, "
                "inflating tail latency."
            ),
            recommended_actions=[
                "Switch to faster storage class (SSD / NVMe)",
                "Add read caching layer (Redis/Memcached) to reduce disk reads",
                "Investigate large sequential writes — batch or async if possible",
            ],
        )

    @staticmethod
    def _infra(m: EvidenceMetrics) -> AnalysisOutput:
        return AnalysisOutput(
            root_cause="CONFIGURATION_ISSUE",
            confidence=0.65,
            affected_component="SCHEDULER",
            evidence=(
                f"Restart flag {m.restart_flag:.0%}, failure streak {m.failure_streak} — "
                "low resource usage rules out OOM."
            ),
            reasoning=(
                "Repeated restarts without resource pressure suggests misconfigured "
                "liveness/readiness probes, bad health-check thresholds, or image pull issues."
            ),
            recommended_actions=[
                "Review liveness probe thresholds and initial delay settings",
                "Check pod events for OOMKilled vs CrashLoopBackOff distinction",
                "Validate ConfigMap / Secret mounts that may block startup",
            ],
        )

    @staticmethod
    def _app(m: EvidenceMetrics) -> AnalysisOutput:
        return AnalysisOutput(
            root_cause="APPLICATION_BUG",
            confidence=0.60,
            affected_component="APPLICATION",
            evidence=(
                f"Error rate {m.error_rate:.2%}, latency P95 {m.latency_p95 * 1000:.1f} ms — "
                "no infrastructure anomalies."
            ),
            reasoning=(
                "Elevated errors and latency without infrastructure pressure points to an "
                "application-layer defect — unhandled exceptions, bad query, or deadlock."
            ),
            recommended_actions=[
                "Pull application error logs and trace the top error class",
                "Check recent deploys for regression — consider rollback",
                "Enable distributed tracing to identify slow code paths",
            ],
        )

    @staticmethod
    def _unknown(anomalies: List[str]) -> AnalysisOutput:
        return AnalysisOutput(
            root_cause="UNKNOWN",
            confidence=0.50,
            affected_component="APPLICATION",
            evidence=f"Detected anomalies: {', '.join(anomalies) or 'none'}.",
            reasoning=(
                "No dominant failure pattern identified from current metric correlations. "
                "Manual investigation is recommended."
            ),
            recommended_actions=[
                "Review full metric history for the affected window",
                "Correlate with deployment or config change events",
                "Escalate to on-call SRE for manual investigation",
            ],
        )
