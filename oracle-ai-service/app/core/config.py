# app/core/config.py
from typing import Optional
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import PostgresDsn, field_validator


class Settings(BaseSettings):
    """
    Application settings with validation.
    All sensitive values must come from environment variables.
    """

    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore"
    )

    # Core Services
    KAFKA_BOOTSTRAP_SERVERS: str = "kafka:9092"
    KAFKA_API_KEY: Optional[str] = None
    KAFKA_API_SECRET: Optional[str] = None
    KAFKA_SECURITY_PROTOCOL: str = "PLAINTEXT"
    KAFKA_SASL_MECHANISM: str = "PLAIN"
    REDIS_URL: str = "redis://redis:6379"

    # Database
    ORACLE_DB_USER: str
    ORACLE_DB_PASSWORD: str
    ORACLE_DB_HOST: str
    ORACLE_DB_PORT: int
    ORACLE_DB_NAME: str

    # Models
    SENTIMENT_MODEL_NAME: str = "distilbert-base-uncased-finetuned-sst-2-english"

    # GitHub App Credentials (Optional - only needed for CI/CD workflows)
    GITHUB_APP_ID: Optional[str] = None
    GITHUB_INSTALLATION_ID: Optional[str] = None
    GITHUB_PRIVATE_KEY: Optional[str] = None
    GITHUB_WORKFLOW_DISPATCH_URL: Optional[str] = None

    # Monitoring (Optional - only needed if using Datadog)
    DATADOG_API_KEY: Optional[str] = None
    DATADOG_APP_KEY: Optional[str] = None

    # ===========================================
    # Profile Enrichment Settings (Sprint 2)
    # ===========================================

    # Tavily API for web search (REQUIRED for enrichment)
    TAVILY_API_KEY: str = ""

    # Anthropic API for LLM extraction (REQUIRED for enrichment)
    ANTHROPIC_API_KEY: str = ""

    # GitHub Public API Token (optional, increases rate limit from 60 to 5000/hr)
    GITHUB_PUBLIC_API_TOKEN: Optional[str] = None

    # ===========================================
    # Rate Limiting Settings (Sprint 8)
    # ===========================================

    # Tavily: Default 100 requests/hour (adjust based on plan)
    TAVILY_RATE_LIMIT: int = 100
    TAVILY_RATE_PERIOD_SECONDS: int = 3600

    # GitHub Public API: 60/hr unauthenticated, 5000/hr authenticated
    GITHUB_RATE_LIMIT: int = 50
    GITHUB_RATE_PERIOD_SECONDS: int = 3600

    # LLM calls: Adjust based on Anthropic plan
    LLM_RATE_LIMIT: int = 500
    LLM_RATE_PERIOD_SECONDS: int = 3600

    # Per-user enrichment rate limit (prevent abuse)
    USER_ENRICHMENT_RATE_LIMIT: int = 5
    USER_ENRICHMENT_RATE_PERIOD_SECONDS: int = 3600

    # ===========================================
    # Celery / Background Task Settings
    # ===========================================

    CELERY_BROKER_URL: str = "redis://redis:6379/1"
    CELERY_RESULT_BACKEND: str = "redis://redis:6379/2"

    # Max enrichments per hour (global throttle)
    ENRICHMENT_MAX_PER_HOUR: int = 100

    # ===========================================
    # Circuit Breaker Settings
    # ===========================================

    # Failure threshold before circuit opens
    CIRCUIT_BREAKER_FAIL_MAX: int = 5

    # Time before circuit attempts to close (seconds)
    CIRCUIT_BREAKER_TIMEOUT: int = 60

    # ===========================================
    # Caching Settings
    # ===========================================

    # Tavily search results cache TTL (24 hours)
    TAVILY_CACHE_TTL_SECONDS: int = 86400

    # GitHub profile cache TTL (7 days)
    GITHUB_CACHE_TTL_SECONDS: int = 604800

    # Analytics computation cache TTL (1 hour)
    ANALYTICS_CACHE_TTL_SECONDS: int = 3600

    # ===========================================
    # Security Settings
    # ===========================================

    # Max string length for user inputs (prevent memory attacks)
    MAX_INPUT_STRING_LENGTH: int = 1000

    # Max interests/skills array length
    MAX_ARRAY_INPUT_LENGTH: int = 50

    # Enrichment data retention (days) - delete after this period
    ENRICHMENT_DATA_RETENTION_DAYS: int = 365

    @field_validator("TAVILY_API_KEY")
    @classmethod
    def validate_tavily_key(cls, v: str) -> str:
        """Warn if Tavily key is missing (enrichment will fail)."""
        if not v:
            import logging

            logging.warning(
                "TAVILY_API_KEY not set - profile enrichment will be disabled"
            )
        return v

    @field_validator("ANTHROPIC_API_KEY")
    @classmethod
    def validate_anthropic_key(cls, v: str) -> str:
        """Warn if Anthropic key is missing (enrichment will fail)."""
        if not v:
            import logging

            logging.warning(
                "ANTHROPIC_API_KEY not set - profile enrichment will be disabled"
            )
        return v

    @property
    def database_url(self) -> str:
        return str(
            PostgresDsn.build(
                scheme="postgresql",
                username=self.ORACLE_DB_USER,
                password=self.ORACLE_DB_PASSWORD,
                host=self.ORACLE_DB_HOST,
                port=self.ORACLE_DB_PORT,
                path=self.ORACLE_DB_NAME,
            )
        )

    @property
    def enrichment_enabled(self) -> bool:
        """Check if enrichment dependencies are configured."""
        return bool(self.TAVILY_API_KEY and self.ANTHROPIC_API_KEY)


# Global settings singleton
settings = Settings()
