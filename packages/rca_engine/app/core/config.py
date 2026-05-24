"""
Central configuration — reads from environment variables / .env file.
"""

from pydantic_settings import BaseSettings
from pydantic_settings import SettingsConfigDict
from typing import List


class Settings(BaseSettings):
    # Gemini LLM
    GEMINI_API_KEY: str = ""
    GEMINI_MODEL: str = "gemini-2.5-flash-lite"
    GEMINI_TIMEOUT: int = 30
    GEMINI_RPM_DELAY: float = 6.0          # seconds between calls on free tier (10 RPM)

    # Analysis behaviour
    USE_LLM: bool = True                   # False = synthetic rule-based only
    LLM_CONFIDENCE_FLOOR: float = 0.0      # reject LLM results below this
    GUARDRAILS_ENABLED: bool = True        # SRE guardrails that validate LLM output

    # Metric thresholds (tune per SLA)
    THRESHOLD_LATENCY_P95: float = 0.05        # 50 ms
    THRESHOLD_ERROR_RATE: float = 0.01         # 1 %
    THRESHOLD_CPU_USAGE: float = 0.85          # 85 %
    THRESHOLD_MEMORY_BYTES: float = 900_000_000  # 900 MB
    THRESHOLD_MEMORY_PRESSURE: float = 0.80
    THRESHOLD_MEMORY_GROWTH: float = 50_000_000   # 50 MB/s
    THRESHOLD_DISK_IO: float = 0.80
    THRESHOLD_CPU_NODE_RATIO: float = 0.90
    THRESHOLD_FAILURE_STREAK: int = 5

    # API
    CORS_ORIGINS: List[str] = ["*"]

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


settings = Settings()
