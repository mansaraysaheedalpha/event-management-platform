# app/core/config.py
"""
Configuration management for the Event Management Service.
This file handles all environment variables and application settings.
"""

from pydantic_settings import BaseSettings
from typing import Optional


class Settings(BaseSettings):
    """
    Application settings loaded from environment variables.

    Pydantic automatically:
    1. Loads values from .env file
    2. Validates data types
    3. Provides default values
    4. Raises errors for missing required values
    """

    # Application Info
    app_name: str = "GlobalConnect Event Management Service"
    version: str = "1.1.0"
    environment: str = "development"

    # Database Configuration
    database_url: str

    # Security Settings
    secret_key: str
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 30

    # Internal API Key for service-to-service communication
    internal_api_key: str

    # File Upload Settings
    max_file_size_mb: int = 10
    upload_folder: str = "uploads"

    # API Configuration
    api_v1_prefix: str = "/api/events/v1"

    class Config:
        # Tell Pydantic to load from .env file
        env_file = ".env"
        # Convert environment variable names (DATABASE_URL -> database_url)
        case_sensitive = False


# Create a global settings instance
# This will be imported throughout the application
settings = Settings()
