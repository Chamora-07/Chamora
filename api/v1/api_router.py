from fastapi import APIRouter
from services.auth.router import router as auth_router
from services.app_registration.router import router as app_registration_router
from services.test_script_registration.router import router as test_script_registration_router
from services.anomaly_config_registration.router import router as anomaly_config_router
from services.document_registration.router import router as document_router
from services.load_testing_services.router import router as load_testing_router
from services.anomalyFlagService.router import router as anomaly_flag_router
from api.v1.rca_router import router as rca_router
from packages.recommendation_module.backend.app.routes.chatbot_routes import router as chatbot_router
from packages.recommendation_module.backend.app.routes.dashboard_routes import router as dashboard_router
from packages.recommendation_module.backend.app.routes.recommendation_routes import router as recommendation_router

v1_router = APIRouter()


v1_router.include_router(auth_router, prefix="/auth", tags=["Authentication"])
v1_router.include_router(app_registration_router, prefix="/application", tags=["Application"])
v1_router.include_router(test_script_registration_router, prefix="/test-scripts", tags=["Test Scripts"])
v1_router.include_router(anomaly_config_router,prefix="/anomaly-configs", tags=["Anomaly Detection Configs"])
v1_router.include_router(document_router,prefix="/documents",tags=["Documents"])
v1_router.include_router(load_testing_router, prefix="/k6", tags=["k6 Testing"])
v1_router.include_router(anomaly_flag_router, prefix="/anomaly-flags", tags=["Anomaly Flags"])
v1_router.include_router(rca_router, prefix="")
v1_router.include_router(chatbot_router, tags=["Chatbot"])
v1_router.include_router(dashboard_router, prefix="/dashboard", tags=["Dashboard"])
v1_router.include_router(recommendation_router, tags=["Recommendations"])