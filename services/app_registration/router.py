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
    app = await service.get_application_by_id(db, app_id, current_user.id)
    if not app.victoria_metrics_url:
        return {"status": "pending", "message": "Monitoring Pending"}
    try:
        url = app.victoria_metrics_url
        if not url.startswith('http://') and not url.startswith('https://'):
            url = f"http://{url}"
        async with service.httpx.AsyncClient(timeout=3.0) as client:
            response = await client.get(url, params={"query": "1"})
            if response.status_code == 200:
                return {"status": "connected", "message": "Monitoring Connected"}
    except Exception:
        pass
    return {"status": "failed", "message": "Monitoring Failed"}

@router.get("/{app_id}", response_model=schemas.ApplicationResponse)
async def get_application(
    app_id: int,
    db: AsyncSession = Depends(get_db),
    current_user = Depends(get_current_user)
):
    """Get single application details by ID."""
    return await service.get_application_by_id(db, app_id, current_user.id)

@router.put("/{app_id}/victoria-metrics", response_model=schemas.ApplicationResponse)
async def update_victoria_metrics(
    app_id: int,
    data: schemas.VictoriaMetricsUpdate,
    db: AsyncSession = Depends(get_db),
    current_user = Depends(get_current_user)
):
    """Update Victoria Metrics endpoint URL for the application."""
    return await service.update_victoria_metrics_url(
        db, app_id, current_user.id, data.victoria_metrics_url
    )

@router.put("/{app_id}/grafana", response_model=schemas.ApplicationResponse)
async def update_grafana(
    app_id: int,
    data: schemas.GrafanaUpdate,
    db: AsyncSession = Depends(get_db),
    current_user = Depends(get_current_user)
):
    """Update Grafana endpoint URL for the application."""
    return await service.update_grafana_url(
        db, app_id, current_user.id, data.grafana_url
    )

@router.put("/{app_id}/github-repo", response_model=schemas.ApplicationResponse)
async def update_github_repo(
    app_id: int,
    data: schemas.GithubRepoUpdate,
    db: AsyncSession = Depends(get_db),
    current_user = Depends(get_current_user)
):
    """Update GitHub repository URL/name for the application."""
    return await service.update_github_repo(
        db, app_id, current_user.id, data.github_repo
    )

@router.put("/{app_id}/health-endpoint", response_model=schemas.ApplicationResponse)
async def update_health_endpoint(
    app_id: int,
    data: schemas.HealthEndpointUpdate,
    db: AsyncSession = Depends(get_db),
    current_user = Depends(get_current_user)
):
    """Update health check endpoint URL for the application."""
    return await service.update_health_endpoint(
        db, app_id, current_user.id, data.health_endpoint
    )


@router.post("/{app_id}/endpoints", response_model=schemas.EndpointResponse)
async def add_endpoint(
    app_id: int,
    endpoint_data: schemas.EndpointCreate,
    db: AsyncSession = Depends(get_db),
    current_user = Depends(get_current_user)
):
    """Add a new monitored target endpoint for the application."""
    return await service.add_application_endpoint(
        db, app_id, current_user.id, endpoint_data.target_name, endpoint_data.container_name
    )

@router.put("/{app_id}/endpoints/{endpoint_id}", response_model=schemas.EndpointResponse)
async def update_endpoint(
    app_id: int,
    endpoint_id: int,
    endpoint_data: schemas.EndpointUpdate,
    db: AsyncSession = Depends(get_db),
    current_user = Depends(get_current_user)
):
    """Update an existing target endpoint for the application."""
    return await service.update_application_endpoint(
        db, app_id, endpoint_id, current_user.id, endpoint_data.target_name, endpoint_data.container_name
    )

@router.delete("/{app_id}/endpoints/{endpoint_id}", status_code=204)
async def delete_endpoint(
    app_id: int,
    endpoint_id: int,
    db: AsyncSession = Depends(get_db),
    current_user = Depends(get_current_user)
):
    """Delete a target endpoint for the application."""
    await service.delete_application_endpoint(db, app_id, endpoint_id, current_user.id)
    return None

