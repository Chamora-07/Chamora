from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime
from uuid import UUID

class AnomalyConfigCreate(BaseModel):
    endpoint_id: int = Field(..., gt=0, description="Valid Endpoint ID")
    latency_threshold: float = Field(1.5, ge=0.0, description="Latency threshold must be non-negative")
    error_rate_threshold: float = Field(0.05, ge=0.0, le=1.0, description="Error rate threshold must be between 0.0 and 1.0")
    failure_streak_limit: int = Field(3, ge=1, description="Failure streak limit must be at least 1")
    cpu_usage_threshold: float = Field(0.8, ge=0.0, le=1.0, description="CPU usage threshold must be between 0.0 and 1.0")
    memory_pressure_threshold: float = Field(0.9, ge=0.0, le=1.0, description="Memory pressure threshold must be between 0.0 and 1.0")
    disk_io_threshold: float = Field(0.7, ge=0.0, le=1.0, description="Disk IO threshold must be between 0.0 and 1.0")
    cpu_node_ratio_threshold: float = Field(0.5, ge=0.0, le=1.0, description="CPU node ratio threshold must be between 0.0 and 1.0")
    is_active: bool = True

class AnomalyConfigUpdate(BaseModel):
    latency_threshold: Optional[float] = Field(None, ge=0.0, description="Latency threshold must be non-negative")
    error_rate_threshold: Optional[float] = Field(None, ge=0.0, le=1.0, description="Error rate threshold must be between 0.0 and 1.0")
    failure_streak_limit: Optional[int] = Field(None, ge=1, description="Failure streak limit must be at least 1")
    cpu_usage_threshold: Optional[float] = Field(None, ge=0.0, le=1.0, description="CPU usage threshold must be between 0.0 and 1.0")
    memory_pressure_threshold: Optional[float] = Field(None, ge=0.0, le=1.0, description="Memory pressure threshold must be between 0.0 and 1.0")
    disk_io_threshold: Optional[float] = Field(None, ge=0.0, le=1.0, description="Disk IO threshold must be between 0.0 and 1.0")
    cpu_node_ratio_threshold: Optional[float] = Field(None, ge=0.0, le=1.0, description="CPU node ratio threshold must be between 0.0 and 1.0")
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
        