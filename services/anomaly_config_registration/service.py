from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from fastapi import HTTPException

from db.models import AnomalyDetectionConfig, Endpoint, Application
from .schemas import AnomalyConfigCreate, AnomalyConfigUpdate


async def get_endpoint_or_404(db: AsyncSession, endpoint_id: int, user_id: int) -> Endpoint:
    """
    Validates that the endpoint exists and belongs to the requesting user.
    Prevents users from creating configs on other users' endpoints.
    """
    stmt = (
        select(Endpoint)
        .join(Application, Endpoint.application_id == Application.id)
        .where(Endpoint.id == endpoint_id)
        .where(Application.user_id == user_id)
    )
    result = await db.execute(stmt)
    endpoint = result.scalar_one_or_none()

    if not endpoint:
        raise HTTPException(
            status_code=404,
            detail="Endpoint not found or does not belong to your account."
        )
    return endpoint


async def create_config(
    db: AsyncSession,
    data: AnomalyConfigCreate,
    user_id: int
) -> AnomalyDetectionConfig:

    # Validate ownership
    await get_endpoint_or_404(db, data.endpoint_id, user_id)

    # Check if a config already exists for this endpoint (unique constraint)
    existing = await db.execute(
        select(AnomalyDetectionConfig).where(
            AnomalyDetectionConfig.endpoint_id == data.endpoint_id
        )
    )
    if existing.scalar_one_or_none():
        raise HTTPException(
            status_code=409,
            detail="A config already exists for this endpoint. Use PATCH to update it."
        )

    config = AnomalyDetectionConfig(**data.model_dump())
    db.add(config)
    await db.commit()
    await db.refresh(config)
    return config


async def get_config_by_endpoint(
    db: AsyncSession,
    endpoint_id: int,
    user_id: int
) -> AnomalyDetectionConfig:

    await get_endpoint_or_404(db, endpoint_id, user_id)

    result = await db.execute(
        select(AnomalyDetectionConfig).where(
            AnomalyDetectionConfig.endpoint_id == endpoint_id
        )
    )
    config = result.scalar_one_or_none()
    if not config:
        raise HTTPException(status_code=404, detail="No config found for this endpoint.")
    return config


async def get_all_configs_for_user(
    db: AsyncSession,
    user_id: int
) -> list[AnomalyDetectionConfig]:
    """Returns all configs across all endpoints belonging to this user."""
    stmt = (
        select(AnomalyDetectionConfig)
        .join(Endpoint, AnomalyDetectionConfig.endpoint_id == Endpoint.id)
        .join(Application, Endpoint.application_id == Application.id)
        .where(Application.user_id == user_id)
    )
    result = await db.execute(stmt)
    return result.scalars().all()


async def update_config(
    db: AsyncSession,
    endpoint_id: int,
    data: AnomalyConfigUpdate,
    user_id: int
) -> AnomalyDetectionConfig:

    config = await get_config_by_endpoint(db, endpoint_id, user_id)

    # Only update fields that were actually provided
    update_data = data.model_dump(exclude_none=True)
    for field, value in update_data.items():
        setattr(config, field, value)

    await db.commit()
    await db.refresh(config)
    return config


async def delete_config(
    db: AsyncSession,
    endpoint_id: int,
    user_id: int
) -> None:

    config = await get_config_by_endpoint(db, endpoint_id, user_id)
    await db.delete(config)
    await db.commit()