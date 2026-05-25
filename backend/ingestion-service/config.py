"""
Configuration management for ingestion service.
Loads settings from environment variables with validation.
"""
from pathlib import Path
from pydantic_settings import BaseSettings
from pydantic import field_validator


SERVICE_DIR = Path(__file__).resolve().parent
REPO_ROOT = SERVICE_DIR.parents[1]


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    # Database configuration
    database_path: str = "./ingestion.db"

    # Server configuration
    host: str = "0.0.0.0"
    port: int = 8001

    # Rate limiting
    rate_limit_per_minute: int = 1000

    # Event ingestion
    redis_url: str = "redis://localhost:6379/0"
    inference_log_stream: str = "inference.logs"
    inference_consumer_group: str = "ingestion-service"
    inference_consumer_name: str = "ingestion-1"
    stream_block_ms: int = 5000

    # CORS (not needed for internal service, but kept for flexibility)
    allowed_origins: str = ""

    @field_validator('database_path')
    @classmethod
    def validate_database_path(cls, v: str) -> str:
        """Ensure database path is set."""
        if not v:
            raise ValueError("DATABASE_PATH must be set")
        return v

    @property
    def allowed_origins_list(self) -> list[str]:
        """Parse comma-separated origins into list."""
        if not self.allowed_origins:
            return []
        return [origin.strip() for origin in self.allowed_origins.split(",")]

    class Config:
        env_file = (str(REPO_ROOT / ".env"), str(SERVICE_DIR / ".env"))
        case_sensitive = False
        extra = "ignore"


# Global settings instance
settings = Settings()
