import logging
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
import os
from dotenv import load_dotenv

load_dotenv()

# Import the retriever component
# Note: Ensure 'packages/metrics-retriever' is in your PYTHONPATH or installed via uv
from metrics_retriever.router import router as retriever_router
from metrics_retriever.router import manager as retriever_manager

from api.v1.api_router import v1_router
from db.init_db import ensure_ml_inference_need_column


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)

logger = logging.getLogger("CHAMORA")

@asynccontextmanager
async def lifespan(app: FastAPI):
    # --- STARTUP PHASE ---
    logger.info("Initializing Chamora...")
    await ensure_ml_inference_need_column()
    # Start the Metrics Retriever component
    await retriever_manager.start()
    logger.info("Retriever Manager is active and monitoring.")
    
    # (Future) await rule_engine_manager.start()
    
    yield
    
    # --- SHUTDOWN PHASE ---
    await retriever_manager.stop()
    logger.info("Shutting down Chamora Metrics Platform...")
    # (Future) await rule_engine_manager.stop()

app = FastAPI(
    title="Chamora",
    version="1.0.0",
    lifespan=lifespan
)

frontend_origins_env = os.getenv("FRONTEND_ORIGINS", "").strip()
frontend_origins = (
    [origin.strip() for origin in frontend_origins_env.split(",") if origin.strip()]
    if frontend_origins_env
    else [
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:5174",
        "http://127.0.0.1:5174",
        "http://localhost:4173",
        "http://127.0.0.1:4173",
        "http://localhost:3000",
        "http://127.0.0.1:3000",
    ]
)

frontend_origin_regex = os.getenv(
    "FRONTEND_ORIGIN_REGEX",
    r"https?://(localhost|127\.0\.0\.1)(:\d+)?$",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=frontend_origins,
    allow_origin_regex=frontend_origin_regex,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Plug in the component routers
app.include_router(v1_router, prefix="/api/v1")
app.include_router(retriever_router)

@app.get("/")
async def root():
    """
    Enhanced root endpoint to provide visibility into 
    how many applications are currently being monitored.
    """
    active_jobs_count = len(retriever_manager.active_jobs)
    return {
        "status": "Chamora Platform is running",
        "version": "1.0.0",
        "engine_status": "Ready" if retriever_manager.is_running else "Stopped",
        "monitoring_stats": {
            "active_endpoints_count": active_jobs_count,
            "connected_to": os.getenv("KAFKA_TOPIC", "raw_metrics")
        }
    }

if __name__ == "__main__":
    import uvicorn
    # Use 0.0.0.0 so it's accessible from outside the container
    uvicorn.run(app, host="0.0.0.0", port=8000)