from sqlalchemy.ext.asyncio import AsyncSession
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


async def check_monitoring_status(db: AsyncSession, app_id: int, user_id: int) -> dict:
    """
    Checks the Victoria Metrics monitoring endpoint of the application.
    """
    query = select(Application).where(Application.id == app_id, Application.user_id == user_id)
    result = await db.execute(query)
    app = result.scalar_one_or_none()
    
    if not app or not app.victoria_metrics_url:
        return {"status": "pending", "message": "Monitoring Pending"}
        
    try:
        url = app.victoria_metrics_url
        if not url.startswith('http://') and not url.startswith('https://'):
            url = f"http://{url}"
            
        async with httpx.AsyncClient(timeout=3.0) as client:
            response = await client.get(url, params={"query": "1"})
            if response.status_code == 200:
                return {"status": "connected", "message": "Monitoring Connected"}
    except Exception:
        pass
        
    return {"status": "failed", "message": "Monitoring Failed"}

