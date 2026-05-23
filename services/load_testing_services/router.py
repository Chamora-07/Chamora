from fastapi import APIRouter, Depends, UploadFile, File
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List
from db.connection import get_db
from services.auth.dependencies import get_current_user
from db.models import User
from . import service, schemas

router = APIRouter()


@router.get(
    "/applications/{app_id}/scripts",
    response_model=List[schemas.TestScriptResponse]
)
async def read_scripts(
    app_id: int,
    db: AsyncSession = Depends(get_db)
):
    scripts = await service.get_scripts_for_application(db, application_id=app_id)
    return scripts or []


@router.post(
    "/applications/{app_id}/scripts/upload",
    response_model=schemas.TestScriptResponse
)
async def upload_script(
    app_id: int,
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    return await service.upload_script(db, app_id=app_id, file=file, user_id=current_user.id)


@router.get(
    "/scripts/{script_id}/history",
    response_model=List[schemas.TestRunResponse]
)
async def read_test_history(
    script_id: int,
    db: AsyncSession = Depends(get_db)
):
    return await service.get_test_runs_for_script(db, script_id=script_id)


@router.post(
    "/scripts/{script_id}/run",
    response_model=schemas.TestRunResponse
)
async def trigger_test_run(
    script_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    return await service.trigger_test_run(
        db,
        script_id=script_id,
        user_id=current_user.id
    )


@router.get(
    "/scripts/{script_id}/result/download"
)
async def download_test_result(
    script_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    return await service.download_latest_result_for_script(
        db,
        script_id=script_id,
        user_id=current_user.id
    )