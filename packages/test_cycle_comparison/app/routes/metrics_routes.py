"""
Public route for fetching one cycle's metrics.

This is the Phase-3 verification surface. Phase 6's compare endpoint
will call `fetch_cycle_metrics` directly for each cycle and combine
the results.
"""

from typing import List, Optional

from fastapi import APIRouter, HTTPException, Query

from app.services.cycle_metrics_fetcher import FetchError, fetch_cycle_metrics

router = APIRouter(prefix="/cycles", tags=["Cycle Metrics"])


def _parse_csv_ints(value: str, field: str) -> List[int]:
    try:
        items = [int(x.strip()) for x in value.split(",") if x.strip()]
    except ValueError:
        raise HTTPException(
            status_code=422,
            detail=f"{field} must be a comma-separated list of integers",
        )
    if not items:
        raise HTTPException(
            status_code=422, detail=f"{field} must contain at least one value"
        )
    return items


def _parse_csv_strings(value: str, field: str) -> List[str]:
    items = [x.strip() for x in value.split(",") if x.strip()]
    if not items:
        raise HTTPException(
            status_code=422, detail=f"{field} must contain at least one value"
        )
    return items


def _parse_overrides(value: Optional[str]) -> dict:
    if not value:
        return {}
    overrides = {}
    for pair in value.split(","):
        pair = pair.strip()
        if not pair:
            continue
        if ":" not in pair:
            raise HTTPException(
                status_code=422,
                detail=f"aggregation_overrides entry '{pair}' must be 'metric:agg'",
            )
        key, agg = pair.split(":", 1)
        overrides[key.strip()] = agg.strip()
    return overrides


@router.get("/{cycle_id}/metrics")
async def get_cycle_metrics(
    cycle_id: int,
    metric_keys: str = Query(
        ...,
        description="Comma-separated metric keys from /metric-catalog",
    ),
    endpoint_ids: str = Query(
        ...,
        description="Comma-separated endpoint ids for label scoping",
    ),
    aggregation_overrides: Optional[str] = Query(
        None,
        description="Comma-separated `metric:agg` pairs (e.g. probe_success:min)",
    ),
    group_by_endpoint: bool = Query(
        False,
        description="If true, emit one value per (metric, endpoint) instead "
                    "of one aggregated value per metric.",
    ),
):
    keys = _parse_csv_strings(metric_keys, "metric_keys")
    ep_ids = _parse_csv_ints(endpoint_ids, "endpoint_ids")
    overrides = _parse_overrides(aggregation_overrides)

    try:
        return await fetch_cycle_metrics(
            cycle_id=cycle_id,
            metric_keys=keys,
            endpoint_ids=ep_ids,
            aggregation_overrides=overrides,
            group_by_endpoint=group_by_endpoint,
        )
    except FetchError as e:
        raise HTTPException(status_code=e.status_code, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Metric fetch failed: {e}")
