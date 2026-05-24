from typing import Optional

from fastapi import APIRouter, HTTPException, Query

from app.services.metric_catalog import SINGLE_CYCLE_DEFAULT_METRICS, catalog

router = APIRouter(prefix="/metric-catalog", tags=["Metric Catalog"])


@router.get("")
async def get_metric_catalog(application_id: int = Query(..., gt=0)):
    """
    Return the discovered metric catalog for an application.

    The list is per-tenant — it reflects what the app's VictoriaMetrics
    actually exposes, decorated with metadata for the comparison flow.
    """
    try:
        entries = await catalog.get_for_app(application_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except RuntimeError as e:
        raise HTTPException(status_code=503, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Catalog discovery failed: {e}")

    categories = sorted({m["category"] for m in entries})
    curated_count = sum(1 for m in entries if m["source"] == "curated")

    return {
        "application_id": application_id,
        "total": len(entries),
        "curated_count": curated_count,
        "inferred_count": len(entries) - curated_count,
        "categories": categories,
        "metrics": entries,
    }


@router.delete("/cache", status_code=204)
def invalidate_catalog_cache(application_id: Optional[int] = Query(None, gt=0)):
    """Drop the cached catalog. Pass `application_id` to scope, or omit to clear all."""
    catalog.invalidate(application_id)
