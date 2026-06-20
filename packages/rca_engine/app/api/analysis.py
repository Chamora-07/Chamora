"""
Analysis routes
POST /api/v1/analyze          — single record
POST /api/v1/analyze/batch    — up to 500 records
"""

from fastapi import APIRouter, HTTPException
import logging

from ..models.schemas import (
    AnalyzeRequest, BatchAnalyzeRequest,
    RCAResult, BatchRCAResult,
)
from ..services.rca_engine import RCAEngine

router = APIRouter()
logger = logging.getLogger(__name__)

# One shared engine instance (stateless internally)
_engine = RCAEngine()


@router.post(
    "/analyze",
    response_model=RCAResult,
    summary="Analyze a single ML anomaly record",
    description=(
        "Accepts one ML model output record and returns a full root cause analysis "
        "including anomaly detection, metric correlation, LLM/synthetic diagnosis, "
        "and recommended remediation actions."
    ),
)
async def analyze_single(body: AnalyzeRequest) -> RCAResult:
    try:
        return await _engine.analyze(body.record)
    except Exception as exc:
        logger.exception("analyze_single failed")
        raise HTTPException(status_code=500, detail=str(exc))


@router.post(
    "/analyze/batch",
    response_model=BatchRCAResult,
    summary="Analyze a batch of ML anomaly records",
    description=(
        "Accepts up to 500 ML model output records. Returns individual RCA results "
        "plus an aggregate summary (root cause distribution, confidence statistics, etc.)."
    ),
)
async def analyze_batch(body: BatchAnalyzeRequest) -> BatchRCAResult:
    try:
        return await _engine.analyze_batch(body.records)
    except Exception as exc:
        logger.exception("analyze_batch failed")
        raise HTTPException(status_code=500, detail=str(exc))
