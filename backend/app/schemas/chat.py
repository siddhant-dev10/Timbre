from typing import List, Optional
from pydantic import BaseModel, Field
from app.schemas.service_scheme import ServiceSchemeResponse


class ChatMessage(BaseModel):
    role: str  # user, assistant, system
    content: str


class ChatRequest(BaseModel):
    citizen_id: str
    message: str = Field(..., min_length=1, max_length=4000)
    conversation_id: Optional[str] = None
    language_preference: Optional[str] = "Hinglish"  # Hindi, Hinglish, English
    synthesize_voice: Optional[bool] = False


class ChatResponse(BaseModel):
    conversation_id: str
    citizen_id: str
    answer: str
    language: str
    grounded_services: List[ServiceSchemeResponse] = Field(default_factory=list)
    confidence_note: str = (
        "Preliminary guidance based on Timbre's stored service catalogue. "
        "Check the official portal for current rules and application processing."
    )
    llm_model: str
    audio_base64: Optional[str] = None
    tts_error: Optional[str] = None
