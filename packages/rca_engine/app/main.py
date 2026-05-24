"""
AI Performance Intelligent Engine - Root Cause Analysis API
FastAPI backend that exposes the LLM analysis engine as REST endpoints.
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager

from .api import analysis, health
from .core.config import settings


@asynccontextmanager
async def lifespan(app: FastAPI):
    print(f"Starting RCA Engine — LLM provider: {'Gemini' if settings.GEMINI_API_KEY else 'Synthetic fallback'}")
    yield
    print("Shutting down RCA Engine")


app = FastAPI(
    title="AI Performance RCA Engine",
    description="Root Cause Analysis API for ML model anomaly output",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health.router, prefix="/api/v1", tags=["health"])
app.include_router(analysis.router, prefix="/api/v1", tags=["analysis"])
