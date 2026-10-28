from typing import List, Optional
from pydantic import BaseModel, Field
from app.schemas.service_scheme import ServiceSchemeResponse


class SynthesizeRequest(BaseModel):
    text: str = Field(..., description="Text content to convert to speech.")
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
    grounded_services: List[ServiceSchemeResponse] = Field(default_factory=list)
    confidence_note: str = (
        "Preliminary AI guidance based on verified official catalogue entries. "
        "Consult official portals for statutory application processing."
    )
    llm_model: str
    tts_provider: str = "ElevenLabs"
    voice_name: str = "Timbre"
