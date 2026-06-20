from pydantic import BaseModel
from typing import Optional, Dict, Any
from datetime import datetime
import uuid


class AnomalyFlagResponse(BaseModel):
    id: uuid.UUID
    application_id: int
    config_id: int
    window_timestamp: datetime
    score: float
    severity: str  # 'WARNING' or 'CRITICAL'
    root_cause: Optional[str]
    evidence: Dict[str, Any]
    created_at: datetime

    class Config:
        from_attributes = True


class AnomalyFlagListResponse(BaseModel):
    """Paginated + sorted anomaly flag list for an application."""
    total: int
    items: list[AnomalyFlagResponse]


class AnomalyFlagSortParams(BaseModel):
    """
    Query parameters for sorting / filtering the anomaly flag list.
    sort_by   : 'severity' | 'window_timestamp' | 'score' | 'created_at'
    order     : 'asc' | 'desc'
    severity  : optional filter – 'WARNING' | 'CRITICAL'
    config_id : optional filter – restrict to a single config
    """
    sort_by: str = "window_timestamp"
    order: str = "desc"
    severity: Optional[str] = None
    config_id: Optional[int] = None