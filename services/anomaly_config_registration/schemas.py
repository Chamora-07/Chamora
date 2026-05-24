from pydantic import BaseModel
from typing import Optional
from datetime import datetime
from uuid import UUID

class AnomalyConfigCreate(BaseModel):
    endpoint_id: int
    latency_threshold: float = 1.5
    error_rate_threshold: float = 0.05
    failure_streak_limit: int = 3
    cpu_usage_threshold: float = 0.8
    memory_pressure_threshold: float = 0.9
    disk_io_threshold: float = 0.7
    cpu_node_ratio_threshold: float = 0.5
    is_active: bool = True

class AnomalyConfigUpdate(BaseModel):
    latency_threshold: Optional[float] = None
    error_rate_threshold: Optional[float] = None
    failure_streak_limit: Optional[int] = None
    cpu_usage_threshold: Optional[float] = None
    memory_pressure_threshold: Optional[float] = None
    disk_io_threshold: Optional[float] = None
    cpu_node_ratio_threshold: Optional[float] = None
    is_active: Optional[bool] = None

class AnomalyConfigResponse(BaseModel):
    id: int
    endpoint_id: int
    latency_threshold: float
    error_rate_threshold: float
    failure_streak_limit: int
    cpu_usage_threshold: float
    memory_pressure_threshold: float
    disk_io_threshold: float
    cpu_node_ratio_threshold: float
    is_active: bool
    ml_inference_need: bool
    created_at: datetime

    class Config:
        from_attributes = True


class AnomalyConfigSummaryResponse(BaseModel):
    config_id: int
    endpoint_id: int
    endpoint_name: str
    container_name: str
    latency_threshold: float
    error_rate_threshold: float
    failure_streak_limit: int
    cpu_usage_threshold: float
    memory_pressure_threshold: float
    disk_io_threshold: float
    cpu_node_ratio_threshold: float
    is_active: bool
    ml_inference_need: bool
    created_at: datetime
    anomaly_count: int


class MLModelMetricResponse(BaseModel):
    id: UUID
    config_id: int
    model_version: str
    recall_score: float
    precision_score: float
    accuracy_score: float
    f1_score: float
    evaluation_type: str
    is_promoted: bool
    created_at: datetime

    class Config:
        from_attributes = True
        