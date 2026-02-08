# event-lifecycle-service/app/core/config.py

from typing import Optional
from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # ✅ THE FIX: We remove the `env_file` directive.
    # Pydantic will now automatically read from the environment variables
    # provided by Docker Compose from the root .env file.
    model_config = SettingsConfigDict(extra="ignore")

    # The environment mode: 'local' or 'prod'
    ENV: str = "prod"

    # --- Production URLs ---
    DATABASE_URL_PROD: Optional[str] = None
    REDIS_URL_PROD: Optional[str] = None
    KAFKA_BOOTSTRAP_SERVERS_PROD: Optional[str] = None

    # --- Local Development URLs (only needed in local mode) ---
    DATABASE_URL_LOCAL: Optional[str] = None
    REDIS_URL_LOCAL: Optional[str] = None
    KAFKA_BOOTSTRAP_SERVERS_LOCAL: Optional[str] = None

    # --- Kafka Authentication (for Confluent Cloud) ---
    KAFKA_API_KEY: Optional[str] = None
    KAFKA_API_SECRET: Optional[str] = None
    KAFKA_SECURITY_PROTOCOL: Optional[str] = "SASL_SSL"  # SASL_SSL for Confluent Cloud
    KAFKA_SASL_MECHANISM: Optional[str] = "PLAIN"  # PLAIN for Confluent Cloud

    # Other secrets
    JWT_SECRET: str
    INTERNAL_API_KEY: str
    AWS_ACCESS_KEY_ID: str
    AWS_SECRET_ACCESS_KEY: str
    AWS_S3_BUCKET_NAME: str
    AWS_S3_REGION: str
    AWS_S3_ENDPOINT_URL: Optional[str] = None
    # Set to False for S3 buckets with ACLs disabled (modern default)
    AWS_S3_USE_ACL: bool = False
    RESEND_API_KEY: Optional[str] = None
    RESEND_FROM_DOMAIN: Optional[str] = "onboarding@resend.dev"

    # AI Services
    ANTHROPIC_API_KEY: Optional[str] = None

    # App URL for tracking links
    NEXT_PUBLIC_APP_URL: Optional[str] = "http://localhost:3000"

    # Backend API URL for email tracking pixels and click redirects
    # This should be the publicly accessible URL of the event-lifecycle-service API
    API_BASE_URL: Optional[str] = "http://localhost:8000"

    # Stripe Payment Configuration
    STRIPE_SECRET_KEY: Optional[str] = None
    STRIPE_PUBLISHABLE_KEY: Optional[str] = None
    STRIPE_WEBHOOK_SECRET: Optional[str] = None

    # Security & Privacy
    IP_HASH_SALT: str  # For IP anonymization (GDPR compliance) - MUST be set in environment
    ALLOWED_ORIGINS: str = "http://localhost:3000"  # Comma-separated list of allowed CORS origins

    # Frontend URL for redirects (if comma-separated, only the first URL is used)
    FRONTEND_URL: str = "http://localhost:3000"

    @field_validator("FRONTEND_URL")
    @classmethod
    def clean_frontend_url(cls, v: str) -> str:
        """Take only the first URL if comma-separated, and strip trailing slashes."""
        return v.split(",")[0].strip().rstrip("/")

    # Internal service URLs for inter-service communication
    REAL_TIME_SERVICE_URL_INTERNAL: Optional[str] = "http://real-time-service:3002"
    USER_SERVICE_URL: Optional[str] = "http://user-and-org-service:3000"

    # --- Dynamic Properties ---
    # These properties will intelligently return the correct URL based on the ENV
    @property
    def DATABASE_URL(self) -> str:
        return (
            self.DATABASE_URL_LOCAL if self.ENV == "local" else self.DATABASE_URL_PROD
        )

    @property
    def REDIS_URL(self) -> str:
        return self.REDIS_URL_LOCAL if self.ENV == "local" else self.REDIS_URL_PROD

    @property
    def KAFKA_BOOTSTRAP_SERVERS(self) -> str:
        return (
            self.KAFKA_BOOTSTRAP_SERVERS_LOCAL
            if self.ENV == "local"
            else self.KAFKA_BOOTSTRAP_SERVERS_PROD
        )

    @property
    def SQLALCHEMY_DATABASE_URI(self) -> str:
        """Alias for DATABASE_URL for SQLAlchemy compatibility."""
        return self.DATABASE_URL


# Create a single instance of the settings
settings = Settings()
