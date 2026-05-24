"""
Helper route for the single-cycle threshold-input UI.

Returns the canonical default metric set used when exactly one cycle is
selected for comparison. When `application_id` is provided, each metric
is enriched with its catalog metadata for that tenant (so the UI can
pre-fill unit, direction, sensible placeholder ranges, etc.).
"""

from typing import Optional

from fastapi import APIRouter, HTTPException, Query

from app.services.metric_catalog import SINGLE_CYCLE_DEFAULT_METRICS, catalog

router = APIRouter(tags=["Single Cycle"])


@router.get("/single-cycle-defaults")
async def get_single_cycle_defaults(
    application_id: Optional[int] = Query(None, gt=0),
):
    if application_id is None:
        return {
            "metric_keys": list(SINGLE_CYCLE_DEFAULT_METRICS),
            "metrics": None,
        }

    try:
        entries = await catalog.get_for_app(application_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except RuntimeError as e:
        raise HTTPException(status_code=503, detail=str(e))

    by_key = {m["key"]: m for m in entries}
    enriched = []
    for key in SINGLE_CYCLE_DEFAULT_METRICS:
        meta = by_key.get(key)
        if meta is not None:
            enriched.append({**meta, "available": True})
        else:
            enriched.append({
                "key": key,
                "label": key,
                "available": False,
                "category": None,
                "unit": None,
                "aggregation": None,
                "higher_is_worse": None,
                "endpoint_scoped": None,
                "label_filter": None,
                "multi_series_aggregator": None,
                "source": None,
            })

    available_count = sum(1 for m in enriched if m["available"])
    return {
        "application_id": application_id,
        "metric_keys": list(SINGLE_CYCLE_DEFAULT_METRICS),
        "available_count": available_count,
        "missing_from_vm": [m["key"] for m in enriched if not m["available"]],
        "metrics": enriched,
    }
