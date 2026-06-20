from fastapi import APIRouter

from packages.rca_engine.app.api.analysis import router as rca_analysis_router
from packages.rca_engine.app.api.health import router as rca_health_router

router = APIRouter()

router.include_router(rca_health_router, tags=["Root Cause Analysis"])
router.include_router(rca_analysis_router, tags=["Root Cause Analysis"])