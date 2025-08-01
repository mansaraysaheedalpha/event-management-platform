from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # This will automatically load the DATABASE_URL from the .env file

    DATABASE_URL: str
    JWT_SECRET: str
    INTERNAL_API_KEY: str
    REDIS_URL: str = "redis://localhost:6379"
    app_name: str = "GlobalConnect Event Management Service"
    version: str = "1.1.0"
    api_v1_prefix: str = "/api/events/v1"
    # ADD THESE for AWS S3
    AWS_ACCESS_KEY_ID: str = "YOUR_AWS_ACCESS_KEY"
    AWS_SECRET_ACCESS_KEY: str = "YOUR_AWS_SECRET_KEY"
    AWS_S3_BUCKET_NAME: str = "your-s3-bucket-name"
    AWS_S3_REGION: str = "your-aws-region"
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")


settings = Settings()
