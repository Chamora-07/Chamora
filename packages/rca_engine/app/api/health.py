from fastapi import APIRouter
from ..core.config import settings

router = APIRouter()


@router.get("/health", summary="Health check")
async def health():
    return {
        "status": "ok",
        "llm_provider": "gemini" if settings.GEMINI_API_KEY else "none",
        "use_llm": settings.USE_LLM,
        "guardrails_enabled": settings.GUARDRAILS_ENABLED,
    }
