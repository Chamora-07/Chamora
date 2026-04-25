from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List

from db.connection import get_db
from services.auth.dependencies import get_current_user
from db.models import User
from packages.metrics_retriever.metrics_retriever.router import manager as retriever_manager

from .schemas import AnomalyConfigCreate, AnomalyConfigUpdate, AnomalyConfigResponse
from . import service

router = APIRouter()


@router.post("/", response_model=AnomalyConfigResponse, status_code=201)
async def create_config(
    data: AnomalyConfigCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    config = await service.create_config(db, data, current_user.id)
    await retriever_manager.refresh_jobs()   # ← scraping starts within 1s
    return config


@router.get("/", response_model=List[AnomalyConfigResponse])
async def get_all_configs(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    return await service.get_all_configs_for_user(db, current_user.id)


@router.get("/endpoint/{endpoint_id}", response_model=AnomalyConfigResponse)
async def get_config(
    endpoint_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    return await service.get_config_by_endpoint(db, endpoint_id, current_user.id)


@router.patch("/endpoint/{endpoint_id}", response_model=AnomalyConfigResponse)
async def update_config(
    endpoint_id: int,
    data: AnomalyConfigUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    config = await service.update_config(db, endpoint_id, data, current_user.id)
    await retriever_manager.refresh_jobs()   # ← handles is_active toggle too
    return config


@router.delete("/endpoint/{endpoint_id}", status_code=204)
async def delete_config(
    endpoint_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    await service.delete_config(db, endpoint_id, current_user.id)
    await retriever_manager.refresh_jobs()   # ← stops scraping immediately