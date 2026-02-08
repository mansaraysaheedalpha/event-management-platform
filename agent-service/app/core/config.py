from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict
from functools import lru_cache
from typing import List, Optional
import json


class Settings(BaseSettings):
    """Application settings loaded from environment variables"""

    # Redis
    REDIS_URL: str

    # TimescaleDB (optional - service can run without it using Redis for state)
    DATABASE_URL: Optional[str] = None

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

    # Engagement Conductor Agent Settings
    AGENT_AUTO_APPROVE_THRESHOLD: float = 0.75  # Confidence threshold for auto-approval
    AGENT_PENDING_APPROVAL_TTL_SECONDS: int = 1800  # 30 minutes TTL for pending approvals
    AGENT_MAX_PENDING_APPROVALS: int = 1000  # Max pending approvals before eviction
    AGENT_ENGAGEMENT_CALCULATION_INTERVAL: int = 5  # Seconds between engagement calculations
    AGENT_CLEANUP_INTERVAL_SECONDS: int = 300  # 5 minutes for cleanup tasks

    # LLM Settings
    LLM_TIMEOUT_SECONDS: int = 30  # Timeout for LLM calls

    # Rate Limiting
    MAX_REQUESTS_PER_MINUTE: int = 60
    MAX_LLM_COST_PER_HOUR: float = 20.0
    MAX_LLM_COST_PER_DAY: float = 100.0

    # Email Notifications (Resend)
    RESEND_API_KEY: Optional[str] = None
    RESEND_FROM_DOMAIN: str = "onboarding@resend.dev"

    # Frontend URL for notification links (if comma-separated, only the first URL is used)
    FRONTEND_URL: str = "http://localhost:3000"

    @field_validator("FRONTEND_URL")
    @classmethod
    def clean_frontend_url(cls, v: str) -> str:
        """Take only the first URL if comma-separated, and strip trailing slashes."""
        return v.split(",")[0].strip().rstrip("/")

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


@lru_cache()
def get_settings() -> Settings:
    """Get cached settings instance"""
    return Settings()


# Singleton instance for direct imports
settings = get_settings()
