from datetime import date
from typing import List
from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )

    # Server
    HOST: str = "0.0.0.0"
    PORT: int = 8000
    DEBUG: bool = False
    ALLOWED_ORIGINS: str = (
        "http://localhost:3000,http://localhost:8080,http://127.0.0.1:3000,"
        "http://127.0.0.1:8080,app://*,http://10.32.72.23:8000"
    )

    # Database
    DATABASE_URL: str = "sqlite:///./data/timbre.db"

    # Reference Date for Demographics & Simulations (YYYY-MM-DD)
    REFERENCE_DATE: str = "2026-10-28"

    # Local LLM (Ollama)
    OLLAMA_BASE_URL: str = "http://127.0.0.1:11434"
    OLLAMA_MODEL: str = "qwen3.5:9b"
    OLLAMA_TIMEOUT_SECONDS: float = 60.0
    OLLAMA_NUM_CTX: int = 4096

    # Bolna.ai Integration
    BOLNA_BASE_URL: str = "https://api.bolna.ai"
    BOLNA_API_KEY: str = ""
    BOLNA_AGENT_ID: str = ""
    BOLNA_TIMEOUT_SECONDS: float = 30.0

    # Call Safety Control Flag
    # Hard safety invariant: Real outbound calls are strictly disabled by default.
    ENABLE_REAL_CALLS: bool = False

    @property
    def cors_origins(self) -> List[str]:
        if not self.ALLOWED_ORIGINS:
            return ["*"]
        return [origin.strip() for origin in self.ALLOWED_ORIGINS.split(",") if origin.strip()]

    @property
    def parsed_reference_date(self) -> date:
        return date.fromisoformat(self.REFERENCE_DATE)


settings = Settings()
