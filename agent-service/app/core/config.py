from pydantic_settings import BaseSettings, SettingsConfigDict
from functools import lru_cache
from typing import List, Optional
import json


class Settings(BaseSettings):
    """Application settings loaded from environment variables"""

    # Redis
    REDIS_URL: str

    # TimescaleDB
    DATABASE_URL: str

    # Anthropic
    ANTHROPIC_API_KEY: str

    # CORS - Stored as string, parsed via get_cors_origins() method
    CORS_ORIGINS: Optional[str] = None

    def get_cors_origins(self) -> List[str]:
        """Parse CORS_ORIGINS from comma-separated string or JSON array"""
        if not self.CORS_ORIGINS:
            return []
        v = self.CORS_ORIGINS.strip()
        if not v:
            return []
        # Try JSON array first
        if v.startswith("["):
            try:
                return json.loads(v)
            except json.JSONDecodeError:
                pass
        # Fall back to comma-separated
        return [origin.strip() for origin in v.split(",") if origin.strip()]

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


# Singleton instance for direct imports
settings = get_settings()
