from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from fastapi import HTTPException

from db.models import AnomalyDetectionConfig, Endpoint, Application, Anomaly, MLModelMetric
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

    if config.ml_inference_need is None:
        config.ml_inference_need = False

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
    configs = result.scalars().all()

    for config in configs:
        if config.ml_inference_need is None:
            config.ml_inference_need = False

    return configs


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


async def get_application_config_summaries(
    db: AsyncSession,
    application_id: int,
    user_id: int
) -> list[dict]:
    app_stmt = (
        select(Application.id)
        .where(Application.id == application_id)
        .where(Application.user_id == user_id)
    )
    app_result = await db.execute(app_stmt)
    if app_result.scalar_one_or_none() is None:
        raise HTTPException(status_code=404, detail="Application not found.")

    summary_stmt = (
        select(
            AnomalyDetectionConfig.id.label("config_id"),
            AnomalyDetectionConfig.endpoint_id,
            Endpoint.target_name.label("endpoint_name"),
            Endpoint.container_name,
            AnomalyDetectionConfig.latency_threshold,
            AnomalyDetectionConfig.error_rate_threshold,
            AnomalyDetectionConfig.failure_streak_limit,
            AnomalyDetectionConfig.cpu_usage_threshold,
            AnomalyDetectionConfig.memory_pressure_threshold,
            AnomalyDetectionConfig.disk_io_threshold,
            AnomalyDetectionConfig.cpu_node_ratio_threshold,
            AnomalyDetectionConfig.is_active,
            AnomalyDetectionConfig.ml_inference_need,
            AnomalyDetectionConfig.created_at,
            func.count(Anomaly.id).label("anomaly_count"),
        )
        .join(Endpoint, AnomalyDetectionConfig.endpoint_id == Endpoint.id)
        .join(Application, Endpoint.application_id == Application.id)
        .outerjoin(Anomaly, Anomaly.config_id == AnomalyDetectionConfig.id)
        .where(Application.id == application_id)
        .where(Application.user_id == user_id)
        .group_by(
            AnomalyDetectionConfig.id,
            AnomalyDetectionConfig.endpoint_id,
            Endpoint.target_name,
            Endpoint.container_name,
            AnomalyDetectionConfig.latency_threshold,
            AnomalyDetectionConfig.error_rate_threshold,
            AnomalyDetectionConfig.failure_streak_limit,
            AnomalyDetectionConfig.cpu_usage_threshold,
            AnomalyDetectionConfig.memory_pressure_threshold,
            AnomalyDetectionConfig.disk_io_threshold,
            AnomalyDetectionConfig.cpu_node_ratio_threshold,
                AnomalyDetectionConfig.is_active,
                AnomalyDetectionConfig.ml_inference_need,
            AnomalyDetectionConfig.created_at,
        )
        .order_by(AnomalyDetectionConfig.created_at.desc())
    )

    result = await db.execute(summary_stmt)
    summaries = []
    for row in result:
        summary = dict(row._mapping)
        summary["ml_inference_need"] = bool(summary.get("ml_inference_need"))
        summaries.append(summary)
    return summaries


async def toggle_ml_inference_need(
    db: AsyncSession,
    config_id: int,
    user_id: int
) -> AnomalyDetectionConfig:
    """
    Toggle the `ml_inference_need` flag for a given config id.
    Ensures the requesting user owns the application/endpoint associated with the config.
    """
    # Validate ownership by joining through endpoint -> application
    stmt = (
        select(AnomalyDetectionConfig)
        .join(Endpoint, AnomalyDetectionConfig.endpoint_id == Endpoint.id)
        .join(Application, Endpoint.application_id == Application.id)
        .where(AnomalyDetectionConfig.id == config_id)
        .where(Application.user_id == user_id)
    )

    result = await db.execute(stmt)
    config = result.scalar_one_or_none()
    if not config:
        raise HTTPException(status_code=404, detail="Config not found or not owned by your account.")

    if config.ml_inference_need is None:
        config.ml_inference_need = False

    # Toggle and persist
    config.ml_inference_need = not bool(config.ml_inference_need)
    await db.commit()
    await db.refresh(config)
    return config


async def get_model_metrics_for_config(
    db: AsyncSession,
    config_id: int,
    user_id: int
) -> list[MLModelMetric]:
    stmt = (
        select(MLModelMetric)
        .join(AnomalyDetectionConfig, MLModelMetric.config_id == AnomalyDetectionConfig.id)
        .join(Endpoint, AnomalyDetectionConfig.endpoint_id == Endpoint.id)
        .join(Application, Endpoint.application_id == Application.id)
        .where(MLModelMetric.config_id == config_id)
        .where(Application.user_id == user_id)
        .order_by(MLModelMetric.created_at.desc())
    )
    result = await db.execute(stmt)
    return result.scalars().all()