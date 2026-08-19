"""
Comparison history.

Read access to the `comparison_results` table written after every /compare
run. Two consumers:

  * the frontend — reloading a saved report so ComparisonResultsPage survives
    a refresh or a shared link
  * the recommendation module — reading past comparisons to answer questions
    like "has response time regressed across the last five cycles?"

Listings omit the heavy `report`/`display` payloads; fetch one by id to get
them.
"""

import logging
from typing import Optional

from fastapi import APIRouter, HTTPException, Query

from app.services import report_store

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/comparison-results", tags=["Comparison History"])


@router.get("")
def list_results(
    application_id: Optional[int] = Query(None, gt=0),
    user_id: Optional[int] = Query(None, gt=0),
    cycle_id: Optional[int] = Query(
        None, gt=0, description="Only comparisons that included this cycle"
    ),
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
):
    """
    List saved comparisons, newest first.

    At least one of `application_id` or `user_id` is required — an unscoped
    listing would leak other tenants' history.
    """
    if application_id is None and user_id is None:
        raise HTTPException(
            status_code=422,
            detail="Provide application_id or user_id to scope the listing.",
        )

    try:
        results = report_store.list_comparison_results(
            application_id=application_id,
            user_id=user_id,
            cycle_id=cycle_id,
            limit=limit,
            offset=offset,
        )
    except Exception as e:
        logger.exception("Failed to list comparison results")
        raise HTTPException(status_code=503, detail=f"History unavailable: {e}")

    return {
        "application_id": application_id,
        "user_id": user_id,
        "count": len(results),
        "limit": limit,
        "offset": offset,
        "results": results,
    }


@router.get("/{result_id}")
def get_result(result_id: int):
    """Load one saved comparison in full — including `report` and `display`."""
    try:
        result = report_store.get_comparison_result(result_id)
    except Exception as e:
        logger.exception("Failed to load comparison result %s", result_id)
        raise HTTPException(status_code=503, detail=f"History unavailable: {e}")

    if result is None:
        raise HTTPException(
            status_code=404, detail=f"Comparison result {result_id} not found"
        )
    return result


@router.delete("/{result_id}", status_code=204)
def delete_result(result_id: int):
    """Remove a saved comparison from the history."""
    try:
        deleted = report_store.delete_comparison_result(result_id)
    except Exception as e:
        logger.exception("Failed to delete comparison result %s", result_id)
        raise HTTPException(status_code=503, detail=f"History unavailable: {e}")

    if not deleted:
        raise HTTPException(
            status_code=404, detail=f"Comparison result {result_id} not found"
        )
