"""
Application settings using Pydantic.
Loads configuration from environment variables and .env file.
"""

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application configuration settings."""

    # PostgreSQL
    postgres_user: str = "collabscribe_user"
    postgres_password: str = "changeme_strong_password"
    postgres_db: str = "collabscribe"
    postgres_host: str = "localhost"
    postgres_port: int = 5432

    # Connection pool
    db_pool_min_size: int = 2
    db_pool_max_size: int = 10

    # Application
    app_host: str = "0.0.0.0"
    app_port: int = 8000
    app_env: str = "development"

    class Config:
        """Pydantic config."""

        env_file = ".env"
        case_sensitive = False


# Global settings instance
settings = Settings()
