from fastapi import APIRouter
from ..core.config import settings

router = APIRouter()


@router.get("/health", summary="Health check")
async def health():
    provider = "none"
    if settings.USE_LLM:
        if settings.LLM_PROVIDER == "groq" and settings.GROQ_API_KEY:
            provider = "groq"
        elif settings.LLM_PROVIDER == "ollama":
            provider = "ollama"
        elif settings.LLM_PROVIDER == "gemini" and settings.GEMINI_API_KEY:
            provider = "gemini"

    return {
        "status": "ok",
        "llm_provider": provider,
        "use_llm": settings.USE_LLM,
        "guardrails_enabled": settings.GUARDRAILS_ENABLED,
    }
