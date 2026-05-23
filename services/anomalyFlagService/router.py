import uuid
from typing import Optional

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from db.connection import get_db
from db.models import User
from services.auth.dependencies import get_current_user

from .schemas import AnomalyFlagResponse, AnomalyFlagListResponse
from . import service

router = APIRouter()


# ---------------------------------------------------------------------------
# Read endpoints
# ---------------------------------------------------------------------------

@router.get(
    "/application/{application_id}",
    response_model=AnomalyFlagListResponse,
    summary="List anomaly flags for an application",
)
async def list_anomaly_flags(
    application_id: int,
    sort_by: str = Query(
        default="window_timestamp",
        description="Sort field: severity | window_timestamp | score | created_at",
    ),
    order: str = Query(
        default="desc",
        description="Sort direction: asc | desc",
    ),
    severity: Optional[str] = Query(
        default=None,
        description="Filter by severity: WARNING | CRITICAL",
    ),
    config_id: Optional[int] = Query(
        default=None,
        description="Filter by a specific anomaly config ID",
    ),
    date_from: Optional[str] = Query(
        default=None,
        description="Filter anomalies from this ISO date/time (window timestamp)",
    ),
    date_to: Optional[str] = Query(
        default=None,
        description="Filter anomalies up to this ISO date/time (window timestamp)",
    ),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return await service.get_anomaly_flags(
        db,
        application_id=application_id,
        user_id=current_user.id,
        sort_by=sort_by,
        order=order,
        severity=severity,
        config_id=config_id,
        date_from=date_from,
        date_to=date_to,
    )


@router.get(
    "/application/{application_id}/counts",
    summary="Get anomaly flag counts broken down by severity",
)
async def get_flag_counts(
    application_id: int,
    date_from: Optional[str] = Query(
        default=None,
        description="Filter anomaly counts from this ISO date/time (window timestamp)",
    ),
    date_to: Optional[str] = Query(
        default=None,
        description="Filter anomaly counts up to this ISO date/time (window timestamp)",
    ),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Returns a lightweight summary useful for badge / header indicators:
    { "total": 12, "CRITICAL": 4, "WARNING": 8 }
    """
    return await service.get_anomaly_flag_counts(
        db,
        application_id=application_id,
        user_id=current_user.id,
        date_from=date_from,
        date_to=date_to,
    )


@router.get(
    "/{anomaly_id}",
    response_model=AnomalyFlagResponse,
    summary="Get a single anomaly flag by ID",
)
async def get_anomaly_flag(
    anomaly_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return await service.get_anomaly_flag_by_id(db, anomaly_id, current_user.id)


# ---------------------------------------------------------------------------
# Acknowledge (delete) endpoints
# ---------------------------------------------------------------------------

@router.delete(
    "/{anomaly_id}/acknowledge",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Acknowledge (dismiss) a single anomaly flag",
)
async def acknowledge_flag(
    anomaly_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Marks an anomaly as acknowledged by permanently deleting it from the table.
    """
    await service.acknowledge_anomaly_flag(db, anomaly_id, current_user.id)


@router.delete(
    "/application/{application_id}/acknowledge-all",
    summary="Bulk-acknowledge anomaly flags for an application",
)
async def acknowledge_all_flags(
    application_id: int,
    severity: Optional[str] = Query(
        default=None,
        description="Only acknowledge flags of this severity: WARNING | CRITICAL",
    ),
    config_id: Optional[int] = Query(
        default=None,
        description="Only acknowledge flags belonging to this config ID",
    ),
    date_from: Optional[str] = Query(
        default=None,
        description="Only acknowledge flags on or after this ISO date/time",
    ),
    date_to: Optional[str] = Query(
        default=None,
        description="Only acknowledge flags on or before this ISO date/time",
    ),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Bulk-acknowledges all matching anomaly flags.
    Returns the number of deleted records.
    """
    deleted = await service.acknowledge_all_flags_for_application(
        db,
        application_id=application_id,
        user_id=current_user.id,
        severity=severity,
        config_id=config_id,
        date_from=date_from,
        date_to=date_to,
    )
    return {"acknowledged": deleted}