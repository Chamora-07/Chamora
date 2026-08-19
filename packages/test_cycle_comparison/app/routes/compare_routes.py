from typing import Dict, List, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.services.comparison_service import run_comparison
from app.services.cycle_metrics_fetcher import FetchError

router = APIRouter(tags=["Compare"])


class ThresholdSpec(BaseModel):
    min: Optional[float] = None
    max: Optional[float] = None
    target: Optional[float] = None


class CompareRequest(BaseModel):
    cycle_ids: List[int] = Field(..., min_length=1, max_length=4)
    # metric_keys may be omitted when cycle_ids has exactly one entry —
    # the orchestrator will fall back to SINGLE_CYCLE_DEFAULT_METRICS.
    metric_keys: Optional[List[str]] = Field(default=None, max_length=50)
    endpoint_ids: List[int] = Field(..., min_length=1)
    baseline_cycle_id: Optional[int] = None
    group_by_endpoint: bool = False
    regression_threshold_pct: float = Field(default=10.0, ge=0.0, le=1000.0)
    aggregation_overrides: Optional[Dict[str, str]] = None
    # Per-metric thresholds. Only applied when cycle_ids has exactly one entry.
    thresholds: Optional[Dict[str, ThresholdSpec]] = None
    include_summary: bool = True
    summary_top_n: int = Field(default=12, ge=1, le=50)
    # Persist the finished report to `comparison_results`. Turn off for
    # throwaway/debug runs you don't want in the history.
    persist: bool = True


@router.post("/compare")
async def compare_cycles(req: CompareRequest):
    """
    Compare 1–4 test cycles for the same application.

    Returns per-metric values, baseline-relative diffs, cross-cycle stats
    (when N≥3), and a global significance ranking. In `group_by_endpoint`
    mode each endpoint-scoped metric is broken out per endpoint.

    The report is saved to `comparison_results` and its row id returned
    as `comparison_id` (unless `persist` is false).
    """
    try:
        thresholds_dict = (
            {k: v.model_dump() for k, v in req.thresholds.items()}
            if req.thresholds
            else None
        )
        return await run_comparison(
            cycle_ids=req.cycle_ids,
            metric_keys=req.metric_keys,
            endpoint_ids=req.endpoint_ids,
            baseline_cycle_id=req.baseline_cycle_id,
            group_by_endpoint=req.group_by_endpoint,
            regression_threshold_pct=req.regression_threshold_pct,
            aggregation_overrides=req.aggregation_overrides,
            thresholds=thresholds_dict,
            include_summary=req.include_summary,
            summary_top_n=req.summary_top_n,
            persist=req.persist,
        )
    except FetchError as e:
        raise HTTPException(status_code=e.status_code, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Comparison failed: {e}")
