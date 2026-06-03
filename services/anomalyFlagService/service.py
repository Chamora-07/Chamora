import uuid
from datetime import datetime
from typing import Optional

from fastapi import HTTPException
from sqlalchemy import asc, desc, delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from db.models import Anomaly, Application


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

_SORT_COLUMN_MAP = {
    "severity": Anomaly.severity,
    "window_timestamp": Anomaly.window_timestamp,
    "score": Anomaly.score,
    "created_at": Anomaly.created_at,
}

_SEVERITY_ORDER = {
    "asc": "CASE WHEN severity = 'WARNING' THEN 0 ELSE 1 END",
    "desc": "CASE WHEN severity = 'CRITICAL' THEN 0 ELSE 1 END",
}


async def _assert_application_ownership(
    db: AsyncSession,
    application_id: int,
    user_id: int,
) -> None:
    """Raise 404 if the application doesn't exist or doesn't belong to the user."""
    stmt = select(Application.id).where(Application.id == application_id).where(Application.user_id == user_id)
    result = await db.execute(stmt)
    if result.scalar_one_or_none() is None:
        raise HTTPException(status_code=404, detail="Application not found.")


async def _assert_anomaly_ownership(
    db: AsyncSession,
    anomaly_id: uuid.UUID,
    user_id: int,
) -> Anomaly:
    """Return the anomaly if it belongs to the user's application, otherwise raise 404."""
    stmt = (
        select(Anomaly)
        .join(Application, Anomaly.application_id == Application.id)
        .where(Anomaly.id == anomaly_id)
        .where(Application.user_id == user_id)
    )
    result = await db.execute(stmt)
    anomaly = result.scalar_one_or_none()
    if anomaly is None:
        raise HTTPException(status_code=404, detail="Anomaly not found or does not belong to your account.")
    return anomaly


def _parse_iso_datetime(value: Optional[str], field_name: str) -> Optional[datetime]:
    if not value:
        return None

    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=f"{field_name} must be a valid ISO date/time.") from exc


# ---------------------------------------------------------------------------
# Public service functions
# ---------------------------------------------------------------------------

async def get_anomaly_flags(
    db: AsyncSession,
    application_id: int,
    user_id: int,
    sort_by: str = "window_timestamp",
    order: str = "desc",
    severity: Optional[str] = None,
    config_id: Optional[int] = None,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
) -> dict:
    """Return all anomaly flags for an application with optional filtering and sorting."""
    await _assert_application_ownership(db, application_id, user_id)

    if sort_by not in _SORT_COLUMN_MAP:
        raise HTTPException(status_code=422, detail=f"Invalid sort_by value. Choose from: {list(_SORT_COLUMN_MAP.keys())}")
    if order not in ("asc", "desc"):
        raise HTTPException(status_code=422, detail="order must be 'asc' or 'desc'.")
    if severity and severity not in ("WARNING", "CRITICAL"):
        raise HTTPException(status_code=422, detail="severity filter must be 'WARNING' or 'CRITICAL'.")

    parsed_date_from = _parse_iso_datetime(date_from, "date_from")
    parsed_date_to = _parse_iso_datetime(date_to, "date_to")
    if parsed_date_from and parsed_date_to and parsed_date_from > parsed_date_to:
        raise HTTPException(status_code=422, detail="date_from must be earlier than or equal to date_to.")

    stmt = select(Anomaly).where(Anomaly.application_id == application_id)

    if severity:
        stmt = stmt.where(Anomaly.severity == severity)
    if config_id is not None:
        stmt = stmt.where(Anomaly.config_id == config_id)
    if parsed_date_from is not None:
        stmt = stmt.where(Anomaly.window_timestamp >= parsed_date_from)
    if parsed_date_to is not None:
        stmt = stmt.where(Anomaly.window_timestamp <= parsed_date_to)

    if sort_by == "severity":
        from sqlalchemy import text

        stmt = stmt.order_by(text(_SEVERITY_ORDER[order]))
    else:
        column = _SORT_COLUMN_MAP[sort_by]
        stmt = stmt.order_by(desc(column) if order == "desc" else asc(column))

    result = await db.execute(stmt)
    items = result.scalars().all()
    return {"total": len(items), "items": items}


async def get_anomaly_flag_by_id(
    db: AsyncSession,
    anomaly_id: uuid.UUID,
    user_id: int,
) -> Anomaly:
    """Fetch a single anomaly flag (ownership-checked)."""
    return await _assert_anomaly_ownership(db, anomaly_id, user_id)


async def acknowledge_anomaly_flag(
    db: AsyncSession,
    anomaly_id: uuid.UUID,
    user_id: int,
) -> None:
    """Acknowledge (delete) an anomaly flag."""
    anomaly = await _assert_anomaly_ownership(db, anomaly_id, user_id)
    await db.delete(anomaly)
    await db.commit()


async def acknowledge_all_flags_for_application(
    db: AsyncSession,
    application_id: int,
    user_id: int,
    severity: Optional[str] = None,
    config_id: Optional[int] = None,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
) -> int:
    """Bulk-acknowledge (delete) anomaly flags for an application."""
    await _assert_application_ownership(db, application_id, user_id)

    parsed_date_from = _parse_iso_datetime(date_from, "date_from")
    parsed_date_to = _parse_iso_datetime(date_to, "date_to")
    if parsed_date_from and parsed_date_to and parsed_date_from > parsed_date_to:
        raise HTTPException(status_code=422, detail="date_from must be earlier than or equal to date_to.")

    stmt = delete(Anomaly).where(Anomaly.application_id == application_id)
    if severity:
        stmt = stmt.where(Anomaly.severity == severity)
    if config_id is not None:
        stmt = stmt.where(Anomaly.config_id == config_id)
    if parsed_date_from is not None:
        stmt = stmt.where(Anomaly.window_timestamp >= parsed_date_from)
    if parsed_date_to is not None:
        stmt = stmt.where(Anomaly.window_timestamp <= parsed_date_to)

    result = await db.execute(stmt)
    await db.commit()
    return result.rowcount


async def get_anomaly_flag_counts(
    db: AsyncSession,
    application_id: int,
    user_id: int,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
) -> dict:
    """Return a summary count broken down by severity for quick badge display."""
    await _assert_application_ownership(db, application_id, user_id)

    parsed_date_from = _parse_iso_datetime(date_from, "date_from")
    parsed_date_to = _parse_iso_datetime(date_to, "date_to")
    if parsed_date_from and parsed_date_to and parsed_date_from > parsed_date_to:
        raise HTTPException(status_code=422, detail="date_from must be earlier than or equal to date_to.")

    stmt = select(Anomaly.severity, func.count(Anomaly.id).label("count")).where(Anomaly.application_id == application_id)
    if parsed_date_from is not None:
        stmt = stmt.where(Anomaly.window_timestamp >= parsed_date_from)
    if parsed_date_to is not None:
        stmt = stmt.where(Anomaly.window_timestamp <= parsed_date_to)
    stmt = stmt.group_by(Anomaly.severity)

    result = await db.execute(stmt)
    rows = result.all()

    counts: dict = {"total": 0, "CRITICAL": 0, "WARNING": 0}
    for row in rows:
        counts[row.severity] = row.count
        counts["total"] += row.count

    return counts