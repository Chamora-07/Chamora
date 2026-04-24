from fastapi import APIRouter
from services.auth.router import router as auth_router
from services.app_registration.router import router as app_registration_router
from services.test_script_registration.router import router as test_script_registration_router


v1_router = APIRouter()


v1_router.include_router(auth_router, prefix="/auth", tags=["Authentication"])
v1_router.include_router(app_registration_router, prefix="/application", tags=["Application"])
v1_router.include_router(prefix="/test-scripts", tags=["Test Scripts"])

