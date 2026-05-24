from typing import List, Optional

from fastapi import APIRouter, Depends, File, Form, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from db.connection import get_db
from db.models import User
from services.auth.dependencies import get_current_user

from . import service
from .schemas import CycleStatus, TestCycleResponse, TestCycleStart

router = APIRouter()


@router.post("/start", response_model=TestCycleResponse, status_code=201)
async def start_cycle(
    data: TestCycleStart,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Open a new test cycle for a registered test script."""
    return await service.start_cycle(db, data, current_user.id)


@router.patch("/{cycle_id}/end", response_model=TestCycleResponse)
async def end_cycle(
    cycle_id: int,
    status: CycleStatus = Form(...),
    result_file: Optional[UploadFile] = File(None),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Close a running cycle. Optionally attach a result file (multipart)."""
    return await service.end_cycle(
        db, cycle_id, status, result_file, current_user.id
    )


@router.get("", response_model=List[TestCycleResponse])
async def list_cycles(
    application_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """List all cycles for an application, newest first."""
    return await service.list_cycles_for_application(
        db, application_id, current_user.id
    )


@router.get("/{cycle_id}", response_model=TestCycleResponse)
async def get_cycle(
    cycle_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Fetch a single cycle with computed duration."""
    return await service.get_cycle(db, cycle_id, current_user.id)
