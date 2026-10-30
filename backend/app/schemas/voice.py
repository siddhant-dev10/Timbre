from typing import List, Optional
from pydantic import BaseModel, Field
from app.schemas.service_scheme import ServiceSchemeResponse


class SynthesizeRequest(BaseModel):
    text: str = Field(..., min_length=1, max_length=4000, description="Text content to convert to speech.")
    voice_id: Optional[str] = Field(None, description="Optional ElevenLabs voice ID override.")
    model_id: Optional[str] = Field(None, description="Optional ElevenLabs model ID override.")


class VoiceChatRequest(BaseModel):
    citizen_id: str = Field(..., description="Citizen ID (e.g. CIT-0001).")
    message: str = Field(..., description="Citizen query message.")
    conversation_id: Optional[str] = Field(None, description="Optional multi-turn conversation session ID.")
    language_preference: Optional[str] = Field("Hinglish", description="Target language (Hindi, Hinglish, English).")
    voice_id: Optional[str] = Field(None, description="Optional custom ElevenLabs Voice ID override.")


class VoiceChatResponse(BaseModel):
    conversation_id: str
    citizen_id: str
    answer: str
    language: str
    audio_base64: Optional[str] = Field(None, description="Base64-encoded MP3 audio stream for direct playback.")
    audio_format: str = "audio/mpeg"
    audio_url: Optional[str] = Field(None, description="Direct URL endpoint to stream audio.")
    tts_error: Optional[str] = Field(None, description="Safe explanation when optional speech synthesis is unavailable.")
    grounded_services: List[ServiceSchemeResponse] = Field(default_factory=list)
    confidence_note: str = (
        "Preliminary guidance based on Timbre's stored service catalogue. "
        "Check the official portal for current rules and application processing."
    )
    llm_model: str
    tts_provider: str = "ElevenLabs"
    voice_name: str = "Timbre"


class TranscribeResponse(BaseModel):
    success: bool
    text: str
    language: str
    language_probability: float
    confidence: float
    duration_seconds: float
    latency_ms: float
    is_unclear: bool
    stop_requested: bool
    clarification_needed: bool
    clarification_prompt: Optional[str] = None


class TurnRequest(BaseModel):
    citizen_id: str = Field(..., description="Citizen ID (e.g. CIT-0001).")
    session_id: Optional[str] = Field(None, description="Optional active session ID.")
    audio_base64: Optional[str] = Field(None, description="Base64 encoded audio bytes (WAV, MP3, WebM).")
    text: Optional[str] = Field(None, description="Direct text input if audio was pre-transcribed.")
    language: Optional[str] = Field("Hindi", description="Language preference (Hindi, Hinglish, English).")
    synthesize_voice: bool = Field(True, description="Whether to synthesize spoken audio with ElevenLabs.")


class TurnResponse(BaseModel):
    session_id: str
    turn_id: str
    turn_index: int
    user_transcript: str
    ai_response: str
    language: str
    latencies_ms: dict
    is_unclear: bool
    stop_requested: bool
    audio_url: Optional[str] = None
    audio_base64: Optional[str] = None
    tts_error: Optional[str] = None
    session_status: str


class SessionHistoryResponse(BaseModel):
    session_id: str
    citizen_id: str
    citizen_name: str
    language: str
    status: str
    created_at: str
    turn_count: int
    turns: list

