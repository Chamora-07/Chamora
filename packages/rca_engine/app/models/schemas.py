"""
Pydantic models — request payloads and response schemas.
"""

from __future__ import annotations
from pydantic import BaseModel, Field, field_validator
from typing import Any, Dict, List, Optional
from datetime import datetime
import json


# ---------------------------------------------------------------------------
# Inbound
# ---------------------------------------------------------------------------

class EvidenceMetrics(BaseModel):
    """Parsed metric snapshot that the ML model attaches to each alert."""
    error_rate: float = 0.0
    has_restart: bool = False
    latency_p95: float = 0.0
    latency_std: float = 0.0
    disk_io_rate: float = 0.0
    memory_usage: float = 0.0
    restart_flag: float = 0.0
    cpu_usage_rate: float = 0.0
    failure_streak: int = 0
    net_throughput: float = 0.0
    memory_pressure: float = 0.0
    memory_growth_rate: float = 0.0
    cpu_container_vs_node_ratio: float = 0.0


class MLRecord(BaseModel):
    """Single ML model output record (one anomaly window)."""
    id: str
    application_id: int
    config_id: int
    window_timestamp: str
    anomaly_score: Optional[float] = None
    severity: str = "WARNING"
    root_cause: Optional[str] = None
    # evidence can arrive as a JSON string or already-parsed dict
    evidence: Any

    @field_validator("evidence", mode="before")
    @classmethod
    def parse_evidence(cls, v: Any) -> dict:
        if isinstance(v, str):
            return json.loads(v)
        return v

    def get_evidence_metrics(self) -> EvidenceMetrics:
        raw = self.evidence if isinstance(self.evidence, dict) else {}
        valid = {f: raw[f] for f in EvidenceMetrics.model_fields if f in raw}
        return EvidenceMetrics(**valid)


class AnalyzeRequest(BaseModel):
    """POST /analyze — single record."""
    record: MLRecord


class BatchAnalyzeRequest(BaseModel):
    """POST /analyze/batch — multiple records."""
    records: List[MLRecord] = Field(..., min_length=1, max_length=500)


# ---------------------------------------------------------------------------
# Outbound
# ---------------------------------------------------------------------------

class MetricsSummary(BaseModel):
    cpu_usage_pct: float
    memory_usage_gb: float
    memory_pressure_pct: float
    memory_growth_mbps: float
    latency_p95_ms: float
    error_rate_pct: float
    disk_io_pct: float
    net_throughput_mbps: float
    failure_streak: int


class CorrelationMap(BaseModel):
    memory_issue: bool
    cpu_issue: bool
    io_issue: bool
    infrastructure_issue: bool
    application_issue: bool


class RCAResult(BaseModel):
    """Full root cause analysis result for one record."""
    id: str
    application_id: int
    config_id: int
    window_timestamp: str

    # Pass-through from ML model
    ml_severity: str
    ml_root_cause: str

    # LLM / synthetic analysis
    root_cause: str
    confidence: float
    affected_component: str
    evidence: str
    reasoning: str
    recommended_actions: List[str] = []

    # Supporting data
    anomalies_detected: List[str]
    correlations: CorrelationMap
    metrics_summary: MetricsSummary

    # Provenance
    analysis_source: str     # "llm" | "synthetic"
    created_at: datetime


class BatchRCAResult(BaseModel):
    total: int
    results: List[RCAResult]
    summary: Dict[str, Any]
