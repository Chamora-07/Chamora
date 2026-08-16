from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import HTTPException
from db.models import Application, Endpoint
from .schemas import ApplicationCreate, ApplicationResponse
from typing import List
from sqlalchemy import select , func
from sqlalchemy.orm import selectinload
import httpx

async def create_application(
    db: AsyncSession, 
    app_data: ApplicationCreate, 
    user_id: int
) -> ApplicationResponse:
    """
    Registers a new application and its associated monitoring endpoints.
    
    Args:
        db: The asynchronous database session.
        app_data: The validated request body containing app details and endpoints.
        user_id: The ID of the authenticated user (owner).
        
    Returns:
        ApplicationResponse: The newly created application including its ID.
    """

    new_app = Application(
        user_id=user_id,
        name=app_data.name,
        description=app_data.description,
        github_repo=app_data.github_repo,
        grafana_url=app_data.grafana_url,
        victoria_metrics_url=app_data.victoria_metrics_url,
        health_endpoint=app_data.health_endpoint
    )
    
    db.add(new_app)

    await db.flush()

    for ep in app_data.endpoints:
        new_endpoint = Endpoint(
            application_id=new_app.id,
            target_name=ep.target_name,
            container_name=ep.container_name
        )
        db.add(new_endpoint)

    await db.commit()
    query = (
        select(Application)
        .where(Application.id == new_app.id)
        .options(selectinload(Application.endpoints))
    )

    result = await db.execute(query)
    app_with_endpoints = result.scalar_one()

    return ApplicationResponse.model_validate(app_with_endpoints)

async def get_user_applications(db: AsyncSession, user_id: int) -> List[Application]:
    """
    Fetches all applications belonging to a specific user, 
    including their nested endpoints.
    """
    query = (
        select(Application)
        .where(Application.user_id == user_id)
        .options(selectinload(Application.endpoints))
    )
    result = await db.execute(query)
    return result.scalars().all()

async def get_user_application_count(db: AsyncSession, user_id: int) -> int:
    """
    Returns the total number of applications registered by a specific user.
    """
    query = (
        select(func.count(Application.id))
        .where(Application.user_id == user_id)
    )
    result = await db.execute(query)
    return result.scalar() or 0

async def check_application_health(db: AsyncSession, app_id: int, user_id: int) -> dict:
    """
    Checks the health endpoint of a given application.
    """
    query = select(Application).where(Application.id == app_id, Application.user_id == user_id)
    result = await db.execute(query)
    app = result.scalar_one_or_none()
    
    if not app or not app.health_endpoint:
        return {"status": "inactive"}
        
    try:
        url = app.health_endpoint
        if not url.startswith('http://') and not url.startswith('https://'):
            url = f"http://{url}"
            
        async with httpx.AsyncClient(timeout=3.0) as client:
            response = await client.get(url)
            if response.status_code in (200, 301, 302, 307, 308):
                return {"status": "active"}
    except Exception:
        pass
        
    return {"status": "inactive"}

async def get_application_endpoints(
    db: AsyncSession, application_id: int, user_id: int
) -> List[Endpoint]:
    """
    Returns endpoints for an application, after verifying ownership.
    Used by the test-cycle comparison UI to populate the endpoint picker.
    """
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

    result = await db.execute(
        select(Endpoint)
        .where(Endpoint.application_id == application_id)
        .order_by(Endpoint.id)
    )
    return result.scalars().all()



async def get_application_by_id(db: AsyncSession, app_id: int, user_id: int) -> Application:
    """
    Fetches a single application by ID belonging to a specific user,
    including its nested endpoints.
    """
    query = (
        select(Application)
        .where(Application.id == app_id, Application.user_id == user_id)
        .options(selectinload(Application.endpoints))
    )
    result = await db.execute(query)
    app = result.scalar_one_or_none()
    if not app:
        raise HTTPException(
            status_code=404,
            detail="Application not found or does not belong to your account."
        )
    return app

async def update_victoria_metrics_url(
    db: AsyncSession, app_id: int, user_id: int, victoria_metrics_url: str
) -> Application:
    """
    Updates the Victoria Metrics URL for an application.
    """
    app = await get_application_by_id(db, app_id, user_id)
    app.victoria_metrics_url = victoria_metrics_url.strip() if victoria_metrics_url else None
    await db.commit()
    await db.refresh(app)
    return app

async def update_grafana_url(
    db: AsyncSession, app_id: int, user_id: int, grafana_url: str
) -> Application:
    """
    Updates the Grafana URL for an application.
    """
    app = await get_application_by_id(db, app_id, user_id)
    app.grafana_url = grafana_url.strip() if grafana_url else None
    await db.commit()
    await db.refresh(app)
    return app

async def update_github_repo(
    db: AsyncSession, app_id: int, user_id: int, github_repo: str
) -> Application:
    """
    Updates the GitHub repository URL/name for an application.
    """
    app = await get_application_by_id(db, app_id, user_id)
    app.github_repo = github_repo.strip() if github_repo else None
    await db.commit()
    await db.refresh(app)
    return app

async def update_health_endpoint(
    db: AsyncSession, app_id: int, user_id: int, health_endpoint: str
) -> Application:
    """
    Updates the health check endpoint URL for an application.
    """
    app = await get_application_by_id(db, app_id, user_id)
    app.health_endpoint = health_endpoint.strip() if health_endpoint else None
    await db.commit()
    await db.refresh(app)
    return app

async def add_application_endpoint(
    db: AsyncSession, app_id: int, user_id: int, target_name: str, container_name: str
) -> Endpoint:
    """
    Adds a new monitored target endpoint for an application.
    """
    # Verify ownership
    await get_application_by_id(db, app_id, user_id)
    
    new_endpoint = Endpoint(
        application_id=app_id,
        target_name=target_name.strip(),
        container_name=container_name.strip()
    )
    db.add(new_endpoint)
    await db.commit()
    await db.refresh(new_endpoint)
    return new_endpoint

async def update_application_endpoint(
    db: AsyncSession, app_id: int, endpoint_id: int, user_id: int, target_name: str, container_name: str
) -> Endpoint:
    """
    Updates an existing target endpoint for an application.
    """
    # Verify app ownership
    await get_application_by_id(db, app_id, user_id)

    query = select(Endpoint).where(
        Endpoint.id == endpoint_id, Endpoint.application_id == app_id
    )
    result = await db.execute(query)
    endpoint = result.scalar_one_or_none()
    if not endpoint:
        raise HTTPException(
            status_code=404,
            detail="Endpoint not found for this application."
        )

    endpoint.target_name = target_name.strip()
    endpoint.container_name = container_name.strip()
    await db.commit()
    await db.refresh(endpoint)
    return endpoint

async def delete_application_endpoint(
    db: AsyncSession, app_id: int, endpoint_id: int, user_id: int
) -> None:
    """
    Deletes a target endpoint for an application.
    """
    # Verify app ownership
    await get_application_by_id(db, app_id, user_id)

    query = select(Endpoint).where(
        Endpoint.id == endpoint_id, Endpoint.application_id == app_id
    )
    result = await db.execute(query)
    endpoint = result.scalar_one_or_none()
    if not endpoint:
        raise HTTPException(
            status_code=404,
            detail="Endpoint not found for this application."
        )

    await db.delete(endpoint)
    await db.commit()


