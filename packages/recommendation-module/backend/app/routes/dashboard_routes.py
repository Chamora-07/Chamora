from fastapi import APIRouter, HTTPException
from app.schemas.dashboard import DashboardResponse
from app.services.dashboard_service import get_dashboard_data

router = APIRouter(prefix="/dashboard", tags=["Dashboard"])


@router.get("/{app_id}", response_model=DashboardResponse)
def dashboard(app_id: str):
    try:
        return get_dashboard_data(app_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Dashboard load failed: {str(e)}")


@router.get("/{app_id}/health")
def dashboard_health(app_id: str):
    try:
        data = get_dashboard_data(app_id)
        return {
            "status": "ok",
            "app_id": app_id,
            "checks": {
                "application": bool(data.get("application")),
                "metrics": bool(data.get("metrics")),
                "containers": bool(data.get("containers")),
                "tech_stack": bool(data.get("tech_stack")),
                "anomaly": bool(data.get("anomaly"))
            }
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Health check failed: {str(e)}")
    
@router.get("/{app_id}/context-check")
def context_check(app_id: str):
    try:
        from app.services.application_context_service import get_application_context
        return get_application_context(app_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Context check failed: {str(e)}")