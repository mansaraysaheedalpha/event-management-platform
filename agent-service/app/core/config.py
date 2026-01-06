from pydantic_settings import BaseSettings, SettingsConfigDict
from functools import lru_cache
from typing import List


class Settings(BaseSettings):
    """Application settings loaded from environment variables"""

    # Redis
    REDIS_URL: str

    # TimescaleDB
    DATABASE_URL: str

    # Anthropic
    ANTHROPIC_API_KEY: str

    # CORS - Allowed origins for production
    CORS_ORIGINS: List[str] = []

    # JWT Secret for validating tokens
    JWT_SECRET: str = ""

    # LangSmith (optional - for agent observability)
    LANGCHAIN_API_KEY: str = ""
    LANGCHAIN_TRACING_V2: bool = False
    LANGCHAIN_PROJECT: str = "engagement-conductor"

    # Agent Settings
    ENGAGEMENT_THRESHOLD: float = 0.6
    ANOMALY_WARNING_THRESHOLD: float = 0.6
    ANOMALY_CRITICAL_THRESHOLD: float = 0.8

    # Rate Limiting
    MAX_REQUESTS_PER_MINUTE: int = 60
    MAX_LLM_COST_PER_HOUR: float = 20.0
    MAX_LLM_COST_PER_DAY: float = 100.0

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


@lru_cache()
def get_settings() -> Settings:
    """Get cached settings instance"""
    return Settings()
