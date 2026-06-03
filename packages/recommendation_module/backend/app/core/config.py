import os
from dotenv import load_dotenv

load_dotenv()


class Settings:
    APP_NAME = os.getenv("APP_NAME", "Chamora Recommendation API")
    APP_ENV = os.getenv("APP_ENV", "development")
    API_PORT = int(os.getenv("API_PORT", "8000"))

    DATABASE_URL = os.getenv("DATABASE_URL", "")
    SUPABASE_URL = os.getenv("SUPABASE_URL", "")
    SUPABASE_KEY = os.getenv("SUPABASE_KEY", "")
    SUPABASE_PUBLISHABLE_KEY = os.getenv("SUPABASE_PUBLISHABLE_KEY", "")
    SUPABASE_STORAGE_BUCKET = os.getenv("SUPABASE_STORAGE_BUCKET", "application-documents")

    GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")
    GROQ_MODEL = os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile")

    VICTORIA_METRICS_URL = os.getenv("VICTORIA_METRICS_URL", "http://localhost:8428")
    DOCKER_TIMEOUT = int(os.getenv("DOCKER_TIMEOUT", "5"))

    GITHUB_API_BASE = os.getenv("GITHUB_API_BASE", "https://api.github.com")
    GITHUB_TOKEN = os.getenv("GITHUB_TOKEN", "")


settings = Settings()