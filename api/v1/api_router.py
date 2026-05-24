from fastapi import APIRouter
from services.auth.router import router as auth_router
from services.app_registration.router import router as app_registration_router
from services.test_script_registration.router import router as test_script_registration_router
from services.anomaly_config_registration.router import router as anomaly_config_router
from services.test_cycles.router import router as test_cycles_router
from services.document_registration.router import router as document_router
from services.load_testing_services.router import router as load_testing_router

v1_router = APIRouter()


v1_router.include_router(auth_router, prefix="/auth", tags=["Authentication"])
v1_router.include_router(app_registration_router, prefix="/application", tags=["Application"])
v1_router.include_router(test_script_registration_router, prefix="/test-scripts", tags=["Test Scripts"])
v1_router.include_router(anomaly_config_router,prefix="/anomaly-configs", tags=["Anomaly Detection Configs"])
v1_router.include_router(test_cycles_router, prefix="/test-cycles", tags=["Test Cycles"])
v1_router.include_router(document_router,prefix="/documents",tags=["Documents"])
v1_router.include_router(load_testing_router, prefix="/k6", tags=["k6 Testing"])
