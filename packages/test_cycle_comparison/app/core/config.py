import os

from dotenv import load_dotenv

load_dotenv()


class Settings:
    APP_NAME = os.getenv("APP_NAME", "Chamora Test Cycle Comparison")
    APP_ENV = os.getenv("APP_ENV", "development")
    API_PORT = int(os.getenv("API_PORT", "8000"))

    SUPABASE_URL = os.getenv("SUPABASE_URL", "")
    SUPABASE_KEY = os.getenv("SUPABASE_KEY", "")

    # Catalog cache TTL (seconds) — per-app discovered metric list
    CATALOG_CACHE_TTL = int(os.getenv("CATALOG_CACHE_TTL", "600"))

    # Per-query timeout when talking to VictoriaMetrics
    VM_HTTP_TIMEOUT = float(os.getenv("VM_HTTP_TIMEOUT", "10.0"))

    # LLM (Groq) — used for narrative summary on top of the math report
    GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")
    GROQ_MODEL = os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile")
    GROQ_TIMEOUT = float(os.getenv("GROQ_TIMEOUT", "20.0"))
    GROQ_MAX_TOKENS = int(os.getenv("GROQ_MAX_TOKENS", "700"))


settings = Settings()
