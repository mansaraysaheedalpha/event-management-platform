# app/core/config.py
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import PostgresDsn


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore"
    )

    # Core Services
    KAFKA_BOOTSTRAP_SERVERS: str = "kafka:9092"
    REDIS_URL: str = "redis:6379"

    # Database
    ORACLE_DB_USER: str
    ORACLE_DB_PASSWORD: str
    ORACLE_DB_HOST: str
    ORACLE_DB_PORT: int
    ORACLE_DB_NAME: str

    # Models
    SENTIMENT_MODEL_NAME: str

    # GitHub App Credentials
    GITHUB_APP_ID: str
    GITHUB_INSTALLATION_ID: str
    GITHUB_PRIVATE_KEY: str
    GITHUB_WORKFLOW_DISPATCH_URL: str

    # Monitoring
    DATADOG_API_KEY: str
    DATADOG_APP_KEY: str

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


# We are reverting to the simpler global settings object.
# The pytest.ini file will ensure this is loaded correctly during tests.
settings = Settings()
