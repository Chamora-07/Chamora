"""
MetricsAnalyzer
Detects threshold violations and correlates them into failure categories.
All thresholds are pulled from Settings so they can be tuned per deployment.
"""

from __future__ import annotations
from typing import Dict, List, Tuple
from dataclasses import dataclass

from ..core.config import settings
from ..models.schemas import EvidenceMetrics, CorrelationMap


@dataclass
class AnomalyReport:
    anomalies: List[str]
    severity_scores: Dict[str, float]
    correlations: CorrelationMap


class MetricsAnalyzer:
    """Stateless helper — all methods are static."""

    # Threshold aliases pointing to global settings
    @staticmethod
    def _t() -> dict:
        return {
            "latency_p95":              settings.THRESHOLD_LATENCY_P95,
            "error_rate":               settings.THRESHOLD_ERROR_RATE,
            "cpu_usage_rate":           settings.THRESHOLD_CPU_USAGE,
            "memory_usage":             settings.THRESHOLD_MEMORY_BYTES,
            "memory_pressure":          settings.THRESHOLD_MEMORY_PRESSURE,
            "memory_growth_rate":       settings.THRESHOLD_MEMORY_GROWTH,
            "disk_io_rate":             settings.THRESHOLD_DISK_IO,
            "cpu_container_vs_node_ratio": settings.THRESHOLD_CPU_NODE_RATIO,
            "failure_streak":           settings.THRESHOLD_FAILURE_STREAK,
        }

    @staticmethod
    def identify_anomalies(m: EvidenceMetrics) -> Tuple[List[str], Dict[str, float]]:
        t = MetricsAnalyzer._t()
        anomalies: List[str] = []
        scores: Dict[str, float] = {}

        def flag(condition: bool, name: str, raw: float, threshold: float):
            if condition:
                anomalies.append(name)
                scores[name] = round(raw / threshold, 3) if threshold else 1.0

        flag(m.latency_p95 > t["latency_p95"],
             "high_latency", m.latency_p95, t["latency_p95"])

        flag(m.error_rate > t["error_rate"],
             "high_error_rate", m.error_rate, t["error_rate"])

        flag(m.cpu_usage_rate > t["cpu_usage_rate"],
             "high_cpu_usage", m.cpu_usage_rate, t["cpu_usage_rate"])

        flag(m.memory_usage > t["memory_usage"],
             "high_memory_usage", m.memory_usage, t["memory_usage"])

        flag(m.memory_pressure > t["memory_pressure"],
             "memory_pressure_high", m.memory_pressure, t["memory_pressure"])

        flag(abs(m.memory_growth_rate) > t["memory_growth_rate"],
             "memory_leak_indicator", abs(m.memory_growth_rate), t["memory_growth_rate"])

        flag(m.disk_io_rate > t["disk_io_rate"],
             "high_disk_io", m.disk_io_rate, t["disk_io_rate"])

        flag(m.cpu_container_vs_node_ratio > t["cpu_container_vs_node_ratio"],
             "cpu_contention", m.cpu_container_vs_node_ratio, t["cpu_container_vs_node_ratio"])

        flag(m.failure_streak > t["failure_streak"],
             "repeated_failures", m.failure_streak, t["failure_streak"])

        if m.has_restart or m.restart_flag > 0:
            anomalies.append("container_restart")
            scores["container_restart"] = 1.0

        return anomalies, scores

    @staticmethod
    def correlate(m: EvidenceMetrics, anomalies: List[str]) -> CorrelationMap:
        a = set(anomalies)
        return CorrelationMap(
            memory_issue=bool(
                a & {"high_memory_usage", "memory_pressure_high", "memory_leak_indicator"}
            ),
            cpu_issue=bool(a & {"high_cpu_usage", "cpu_contention"}),
            io_issue="high_disk_io" in a,
            infrastructure_issue=bool(a & {"container_restart", "repeated_failures"}),
            application_issue=bool(a & {"high_latency", "high_error_rate"}),
        )

    @staticmethod
    def analyze(m: EvidenceMetrics) -> AnomalyReport:
        anomalies, scores = MetricsAnalyzer.identify_anomalies(m)
        correlations = MetricsAnalyzer.correlate(m, anomalies)
        return AnomalyReport(
            anomalies=anomalies,
            severity_scores=scores,
            correlations=correlations,
        )
