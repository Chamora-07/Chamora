from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from db.connection import get_db
from services.auth.dependencies import get_current_user
from . import service, schemas
from typing import List

router = APIRouter()

@router.post("/register", response_model=schemas.ApplicationResponse)
async def register_application(
    app_data: schemas.ApplicationCreate,
    db: AsyncSession = Depends(get_db),
    current_user = Depends(get_current_user)
):
    try:
        return await service.create_application(db, app_data, current_user.id)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.get("/me", response_model=List[schemas.ApplicationResponse])
async def get_applications(
    db: AsyncSession = Depends(get_db),
    current_user = Depends(get_current_user)
):
    """Get all registered applications for the authenticated user."""
    return await service.get_user_applications(db, current_user.id)

@router.get("/count")
async def get_application_count(
    db: AsyncSession = Depends(get_db),
    current_user = Depends(get_current_user)
):
    """Get the total count of applications for the logged-in user."""
    count = await service.get_user_application_count(db, current_user.id)
    return {"count": count}

@router.get("/{application_id}/endpoints", response_model=List[schemas.EndpointResponse])
async def get_application_endpoints(
    application_id: int,
    db: AsyncSession = Depends(get_db),
    current_user = Depends(get_current_user)
):
    """List endpoints for an application (used by the test-cycle comparison UI)."""
    return await service.get_application_endpoints(db, application_id, current_user.id)

@router.get("/{app_id}/health-check")
async def get_application_health(
    app_id: int,
    db: AsyncSession = Depends(get_db),
    current_user = Depends(get_current_user)
):
    """Ping the application's health endpoint and return its status."""
    return await service.check_application_health(db, app_id, current_user.id)


@router.get("/{app_id}/monitoring-status")
async def get_application_monitoring_status(
    app_id: int,
    db: AsyncSession = Depends(get_db),
    current_user = Depends(get_current_user)
):
    """Check the connection to the application's Victoria Metrics endpoint and return its status."""
    return await service.check_monitoring_status(db, app_id, current_user.id)
