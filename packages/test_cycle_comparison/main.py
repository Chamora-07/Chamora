import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import settings
from app.routes.catalog_routes import router as catalog_router
from app.routes.metrics_routes import router as metrics_router
from app.routes.compare_routes import router as compare_router
from app.routes.single_cycle_routes import router as single_cycle_router

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)

app = FastAPI(title=settings.APP_NAME)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(catalog_router)
app.include_router(metrics_router)
app.include_router(compare_router)
app.include_router(single_cycle_router)


@app.get("/health")
def health():
    return {
        "status": "ok",
        "app_name": settings.APP_NAME,
        "environment": settings.APP_ENV,
    }
