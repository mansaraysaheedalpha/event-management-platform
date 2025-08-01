from pydantic_settings import BaseSettings

class Settings(BaseSettings):
   KAFKA_BOOTSTRAP_SERVERS: str = "kafka:9092"
   REDIS_URL: str = "redis://redis:6379"

settings = Settings()