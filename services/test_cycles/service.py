import os
from datetime import datetime, timezone
from typing import List, Optional

from dotenv import load_dotenv
from fastapi import HTTPException, UploadFile
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from supabase import Client, create_client

from db.models import Application, TestRun, TestScript

from .schemas import CycleStatus, TestCycleResponse, TestCycleStart

load_dotenv()

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
SUPABASE_RESULTS_BUCKET = os.getenv(
    "SUPABASE_STORAGE_TEST_RESULTS_BUCKET", "test_results"
)

_supabase: Optional[Client] = None


def _get_supabase() -> Client:
    global _supabase
    if _supabase is None:
        if not SUPABASE_URL or not SUPABASE_KEY:
            raise HTTPException(500, "Supabase is not configured.")
        _supabase = create_client(SUPABASE_URL, SUPABASE_KEY)
    return _supabase


async def _get_script_or_404(
    db: AsyncSession, script_id: int, user_id: int
) -> TestScript:
    stmt = (
        select(TestScript)
        .join(Application, TestScript.application_id == Application.id)
        .where(TestScript.id == script_id)
        .where(Application.user_id == user_id)
    )
    result = await db.execute(stmt)
    script = result.scalar_one_or_none()
    if not script:
        raise HTTPException(
            status_code=404,
            detail="Test script not found or does not belong to your account.",
        )
    return script


async def _get_cycle_or_404(
    db: AsyncSession, cycle_id: int, user_id: int
) -> TestRun:
    stmt = (
        select(TestRun)
        .join(TestScript, TestRun.test_script_id == TestScript.id)
        .join(Application, TestScript.application_id == Application.id)
        .where(TestRun.id == cycle_id)
        .where(Application.user_id == user_id)
        .options(selectinload(TestRun.test_script))
    )
    result = await db.execute(stmt)
    cycle = result.scalar_one_or_none()
    if not cycle:
        raise HTTPException(
            status_code=404,
            detail="Test cycle not found or does not belong to your account.",
        )
    return cycle


def _as_utc(dt: Optional[datetime]) -> Optional[datetime]:
    """
    Coerce a datetime to UTC. Tolerates legacy rows where end_time was
    stored as a naive timestamp (the model previously declared end_time
    without timezone=True). Naive values are assumed to already be UTC.
    """
    if dt is None:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt


def _to_response(
    cycle: TestRun, script: Optional[TestScript] = None
) -> TestCycleResponse:
    script = script or cycle.test_script
    start = _as_utc(cycle.start_time)
    end = _as_utc(cycle.end_time)
    duration = (end - start).total_seconds() if (start and end) else None
    return TestCycleResponse(
        id=cycle.id,
        test_script_id=cycle.test_script_id,
        script_name=script.script_name if script else None,
        application_id=script.application_id if script else None,
        status=cycle.status,
        start_time=start,
        end_time=end,
        duration_seconds=duration,
        result_file_path=cycle.result_file_path,
    )


async def start_cycle(
    db: AsyncSession, data: TestCycleStart, user_id: int
) -> TestCycleResponse:
    script = await _get_script_or_404(db, data.test_script_id, user_id)

    cycle = TestRun(
        test_script_id=script.id,
        status=CycleStatus.RUNNING.value,
    )
    db.add(cycle)
    await db.commit()
    await db.refresh(cycle)

    return _to_response(cycle, script)


async def end_cycle(
    db: AsyncSession,
    cycle_id: int,
    status: CycleStatus,
    result_file: Optional[UploadFile],
    user_id: int,
) -> TestCycleResponse:
    if status == CycleStatus.RUNNING:
        raise HTTPException(
            status_code=400,
            detail="Cannot end a cycle with status 'running'.",
        )

    cycle = await _get_cycle_or_404(db, cycle_id, user_id)

    if cycle.end_time is not None:
        raise HTTPException(
            status_code=409,
            detail="Test cycle has already ended.",
        )

    if result_file is not None:
        cycle.result_file_path = await _upload_result(result_file, cycle)

    cycle.status = status.value
    cycle.end_time = datetime.now(timezone.utc)

    await db.commit()
    await db.refresh(cycle)

    return _to_response(cycle)


async def _upload_result(file: UploadFile, cycle: TestRun) -> str:
    script = cycle.test_script
    if script is None:
        raise HTTPException(500, "Cycle is missing its parent test script.")

    safe_name = (file.filename or "result").split("/")[-1].split("\\")[-1]
    bucket_path = f"apps/{script.application_id}/cycles/{cycle.id}/{safe_name}"
    file_bytes = await file.read()

    try:
        _get_supabase().storage.from_(SUPABASE_RESULTS_BUCKET).upload(
            path=bucket_path,
            file=file_bytes,
            file_options={
                "content-type": file.content_type or "application/octet-stream"
            },
        )
    except Exception as e:
        raise HTTPException(500, f"Result upload failed: {str(e)}")

    return bucket_path


async def list_cycles_for_application(
    db: AsyncSession, application_id: int, user_id: int
) -> List[TestCycleResponse]:
    ownership_check = await db.execute(
        select(Application)
        .where(Application.id == application_id)
        .where(Application.user_id == user_id)
    )
    if not ownership_check.scalar_one_or_none():
        raise HTTPException(
            status_code=404,
            detail="Application not found or does not belong to your account.",
        )

    stmt = (
        select(TestRun)
        .join(TestScript, TestRun.test_script_id == TestScript.id)
        .where(TestScript.application_id == application_id)
        .options(selectinload(TestRun.test_script))
        .order_by(TestRun.start_time.desc())
    )
    result = await db.execute(stmt)
    cycles = result.scalars().all()
    return [_to_response(c) for c in cycles]


async def get_cycle(
    db: AsyncSession, cycle_id: int, user_id: int
) -> TestCycleResponse:
    cycle = await _get_cycle_or_404(db, cycle_id, user_id)
    return _to_response(cycle)
