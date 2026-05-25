"""
Configuration management for chatbot service.
Loads settings from environment variables with secure validation.
"""
import secrets
from pathlib import Path
from pydantic_settings import BaseSettings
from pydantic import field_validator
from dotenv import load_dotenv


SERVICE_DIR = Path(__file__).resolve().parent
REPO_ROOT = SERVICE_DIR.parents[1]

# Load repo-level defaults first, then allow a service-local .env to override.
load_dotenv(REPO_ROOT / ".env")
load_dotenv(SERVICE_DIR / ".env", override=True)


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    # LLM provider configuration
    # Use "mock" for local demos, "openai" for GPT, or "groq" for Groq.
    llm_provider: str = "mock"
    llm_fallback_providers: str = ""
    openai_api_key: str = ""
    openai_base_url: str = ""
    groq_api_key: str = ""

    # Ingestion service configuration
    ingestion_api_url: str = "http://localhost:8001/api/ingest"
    redis_url: str = "redis://localhost:6379/0"
    inference_log_stream: str = "inference.logs"

    # Database configuration
    database_path: str = "./chatbot.db"

    # Security
    secret_key: str = secrets.token_urlsafe(32)  # Default random key, should override in production
    csrf_cookie_secure: bool = False

    # CORS configuration
    allowed_origins: str = "http://localhost:5173"

    # Server configuration
    host: str = "0.0.0.0"
    port: int = 8000

    # LLM configuration
    default_model: str = "llama-3.1-70b-versatile"
    context_window_size: int = 10  # Number of messages to keep in context
    max_tokens: int = 1024  # Max tokens in response

    # Ingestion retry configuration
    ingestion_timeout_seconds: int = 5
    ingestion_max_retries: int = 3

    @field_validator('llm_provider')
    @classmethod
    def validate_llm_provider(cls, v: str) -> str:
        """Ensure provider is supported."""
        supported = {"mock", "openai", "groq"}
        normalized = v.lower().strip()
        if normalized not in supported:
            raise ValueError(f"LLM_PROVIDER must be one of: {', '.join(sorted(supported))}")
        return normalized

    @field_validator('groq_api_key')
    @classmethod
    def validate_groq_api_key(cls, v: str) -> str:
        """Allow empty key for mock mode; Groq calls fail clearly if not configured."""
        return v

    @field_validator('openai_api_key')
    @classmethod
    def validate_openai_api_key(cls, v: str) -> str:
        """Allow empty key for mock mode; OpenAI calls fail clearly if not configured."""
        return v

    @field_validator('secret_key')
    @classmethod
    def validate_secret_key(cls, v: str) -> str:
        """Ensure secret key is strong enough."""
        if len(v) < 32:
            raise ValueError("SECRET_KEY must be at least 32 characters")
        return v

    @property
    def allowed_origins_list(self) -> list[str]:
        """Parse comma-separated origins into list."""
        return [origin.strip() for origin in self.allowed_origins.split(",")]

    @property
    def provider_order(self) -> list[str]:
        """Primary provider followed by optional comma-separated fallbacks."""
        providers = [self.llm_provider]
        providers.extend(
            provider.strip().lower()
            for provider in self.llm_fallback_providers.split(",")
            if provider.strip()
        )
        return list(dict.fromkeys(providers))

    class Config:
        env_file = (str(REPO_ROOT / ".env"), str(SERVICE_DIR / ".env"))
        case_sensitive = False
        extra = "ignore"


# Global settings instance
settings = Settings()
