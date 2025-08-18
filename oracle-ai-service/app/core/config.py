#app/core/config.py
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    # Allow loading from a .env file
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    # The default is the Docker service name, but it can be overridden
    KAFKA_BOOTSTRAP_SERVERS: str = "kafka:9092"
    REDIS_URL: str = "redis:6379"
    

settings = Settings()
