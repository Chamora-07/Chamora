"""
router.py  (recommendations)

Mount under: /api/v1/reports
Exposes:     POST /api/v1/reports/{application_id}/recommendations

The frontend ReportPage POSTs the compact `findings` payload it computed from the
detected anomalies; we return grounded, specific recommendations.
"""

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from typing import Any, Optional

from ..services.recommendation_service import generate_recommendations
# from ..auth import get_current_user   # wire to your existing auth dependency

router = APIRouter(prefix="/reports", tags=["reports"])


# ---- Request / response models -------------------------------------------------

class Totals(BaseModel):
    detections: int = 0
    critical: int = 0
    warning: int = 0


class Signals(BaseModel):
    peak_memory_pressure: Optional[float] = None
    baseline_memory_pressure: Optional[float] = None
    max_error_rate: Optional[float] = None
    timeouts: Optional[int] = None
    restarts: Optional[int] = None
    restarts_new_vs_baseline: Optional[bool] = None
    latency_p95_regression_pct: Optional[float] = None


class Findings(BaseModel):
    app_id: Optional[Any] = None
    totals: Optional[Totals] = None
    signals: Optional[Signals] = None
    top_incidents: Optional[list[dict]] = None


class Recommendation(BaseModel):
    title: str
    priority: str
    observation: str = ""
    likely_cause: str = ""
    actions: list[str] = []
    addresses: str = ""


class RecommendationsResponse(BaseModel):
    recommendations: list[Recommendation]
    source: str  # "llm" | "fallback"


# ---- Endpoint ------------------------------------------------------------------

@router.post("/{application_id}/recommendations", response_model=RecommendationsResponse)
def recommendations(
    application_id: int,
    findings: Findings,
    # current_user = Depends(get_current_user),   # uncomment to require auth
):
    try:
        result = generate_recommendations(
            app_id=application_id,
            findings=findings.model_dump(exclude_none=True),
        )
        return result
    except Exception as e:
        # Never 500 the report over recommendations; surface a clean message.
        raise HTTPException(status_code=502, detail=f"Recommendation generation failed: {e}")