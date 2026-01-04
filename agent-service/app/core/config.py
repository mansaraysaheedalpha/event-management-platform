from pydantic_settings import BaseSettings, SettingsConfigDict
from functools import lru_cache


class Settings(BaseSettings):
    """Application settings loaded from environment variables"""

    # Redis
    REDIS_URL: str = "redis://localhost:6379"

    # TimescaleDB
    DATABASE_URL: str = "postgresql://postgres:password@localhost:5437/agent_db"

    # Anthropic
    ANTHROPIC_API_KEY: str = ""

    # LangSmith (optional - for agent observability)
    LANGCHAIN_API_KEY: str = ""
    LANGCHAIN_TRACING_V2: bool = False
    LANGCHAIN_PROJECT: str = "engagement-conductor"

    # Agent Settings
    ENGAGEMENT_THRESHOLD: float = 0.6
    ANOMALY_WARNING_THRESHOLD: float = 0.6
    ANOMALY_CRITICAL_THRESHOLD: float = 0.8

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


@lru_cache()
def get_settings() -> Settings:
    """Get cached settings instance"""
    return Settings()
