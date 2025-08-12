#app/core/config.py
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # This tells Pydantic to load variables from the .env file
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    # The environment mode: 'local' or 'prod'
    ENV: str = "prod"

    # --- Production URLs (for inside Docker) ---
    DATABASE_URL_PROD: str
    REDIS_URL_PROD: str
    KAFKA_BOOTSTRAP_SERVERS_PROD: str

    # --- Local Development URLs (for running locally) ---
    DATABASE_URL_LOCAL: str
    REDIS_URL_LOCAL: str
    KAFKA_BOOTSTRAP_SERVERS_LOCAL: str

    # Other secrets
    JWT_SECRET: str
    INTERNAL_API_KEY: str
    AWS_ACCESS_KEY_ID: str
    AWS_SECRET_ACCESS_KEY: str
    AWS_S3_BUCKET_NAME: str
    AWS_S3_REGION: str

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


# Create a single instance of the settings
settings = Settings()
