from datetime import date
from pathlib import Path
from typing import List
from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=(str(Path(__file__).resolve().parent.parent / ".env"), ".env"),
        env_file_encoding="utf-8",
        extra="ignore"
    )

    def reload_from_env(self) -> None:
        """Reloads settings from the .env file in-place so active processes reflect changes."""
        new_settings = Settings()
        for field_name in type(self).model_fields:
            setattr(self, field_name, getattr(new_settings, field_name))

    # Server
    HOST: str = "127.0.0.1"
    PORT: int = 8000
    DEBUG: bool = False
    ALLOWED_ORIGINS: str = "http://localhost:3000,http://localhost:8080,http://127.0.0.1:3000,http://127.0.0.1:8080"

    # Database
    DATABASE_URL: str = "sqlite:///./data/timbre.db"

    # Reference Date for Demographics & Simulations (YYYY-MM-DD)
    REFERENCE_DATE: str = "2026-10-28"

    # NVIDIA-hosted OpenAI-compatible API. Credentials stay on this local backend.
    NVIDIA_API_KEY: str = ""
    NVIDIA_BASE_URL: str = "https://integrate.api.nvidia.com/v1"
    NVIDIA_MODEL: str = "nvidia/nemotron-3.5-super-vl-120b-a12b"
    NVIDIA_TIMEOUT_SECONDS: float = 90.0
    NVIDIA_MAX_TOKENS: int = 400
    NVIDIA_TEMPERATURE: float = 1.0
    NVIDIA_TOP_P: float = 0.95
    NVIDIA_REASONING_EFFORT: str = "none"

    # Bolna.ai Integration
    BOLNA_BASE_URL: str = "https://api.bolna.ai"
    BOLNA_API_KEY: str = ""
    BOLNA_AGENT_ID: str = ""
    BOLNA_TIMEOUT_SECONDS: float = 30.0
    # Configure the same value as a custom webhook header in Bolna.
    BOLNA_WEBHOOK_SECRET: str = ""
    # Set only after verifying the agent's AI-disclosure greeting, approved
    # synthetic test script, Hindi/Hinglish configuration, and no-retry policy.
    BOLNA_TEST_AGENT_VERIFIED: bool = False

    # Dedicated Bearer Token for OpenAI-compatible Custom LLM endpoint
    # When set, inbound calls from Bolna/external clients to /v1/chat/completions
    # must present this token via Authorization: Bearer <key>.
    TIMBRE_LLM_API_KEY: str = ""

    # WhatsApp Business Cloud API Integration
    WHATSAPP_API_BASE_URL: str = "https://graph.facebook.com/v21.0"
    WHATSAPP_ACCESS_TOKEN: str = ""
    WHATSAPP_PHONE_NUMBER_ID: str = ""
    WHATSAPP_VERIFY_TOKEN: str = ""
    WHATSAPP_APP_SECRET: str = ""
    WHATSAPP_TIMEOUT_SECONDS: float = 15.0

    # OpenWA Local WhatsApp Gateway Integration
    OPENWA_BASE_URL: str = "http://localhost:2785"
    OPENWA_API_KEY: str = ""
    OPENWA_SESSION_ID: str = "timbre"
    OPENWA_WEBHOOK_SECRET: str = ""
    OPENWA_TIMEOUT_SECONDS: float = 15.0

    # ElevenLabs Text-to-Speech Integration
    ELEVENLABS_BASE_URL: str = "https://api.elevenlabs.io"
    ELEVENLABS_API_KEY: str = ""
    ELEVENLABS_VOICE_ID: str = ""
    ELEVENLABS_TTS_MODEL_ID: str = "eleven_multilingual_v2"
    ELEVENLABS_TIMEOUT_SECONDS: float = 30.0

    # Speech Recognition (Whisper STT) Integration
    WHISPER_MODEL_SIZE: str = "base"
    WHISPER_DEVICE: str = "cpu"
    WHISPER_COMPUTE_TYPE: str = "int8"
    WHISPER_LANGUAGE: str = "hi"
    WHISPER_CONFIDENCE_THRESHOLD: float = 0.40
    WHISPER_TIMEOUT_SECONDS: float = 30.0
    DEFAULT_CONVERSATION_LANGUAGE: str = "Hindi"

    # Knowledge Base & Vector Embedding Configuration
    EMBEDDING_PROVIDER: str = "fastembed"  # "fastembed" (multilingual ONNX) or "deterministic_hash" (SHA-256)
    EMBEDDING_MODEL_NAME: str = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
    EMBEDDING_VERSION: str = "2.0.0"
    EMBEDDING_DIM: int = 384

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
