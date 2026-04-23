from sqlalchemy.ext.asyncio import AsyncSession
from db.models import Application, Endpoint
from .schemas import ApplicationCreate, ApplicationResponse
from typing import List
from sqlalchemy import select , func
from sqlalchemy.orm import selectinload

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
        github_repo=app_data.github_repo
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



