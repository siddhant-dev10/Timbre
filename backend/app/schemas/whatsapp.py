"""Pydantic Schemas for Timbre WhatsApp Messaging and Simulation."""
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class WhatsAppSimulationRequest(BaseModel):
    """Request schema for local interactive WhatsApp conversation simulation."""
    sender_phone: str = Field(default="919876543210", description="Simulated citizen phone number or wa_id")
    message: str = Field(..., min_length=1, description="Citizen text inquiry")
    sender_name: Optional[str] = Field(default="Demo Citizen", description="Optional contact profile name")
    reset_conversation: bool = Field(default=False, description="Clear prior dialogue history to start afresh")
    simulate_provider_failure: bool = Field(default=False, description="Simulate an outbound provider delivery failure")


class WhatsAppSimulationResponse(BaseModel):
    """Response schema for WhatsApp conversation turn."""
    conversation_id: str
    wa_id: str
    sender_phone_masked: str
    user_message: str
    ai_reply: str
    language: str
    grounded_sources: List[str] = Field(default_factory=list)
    delivery_status: str
    provider: str
    error: Optional[str] = None


class WhatsAppMessageItem(BaseModel):
    id: str
    direction: str
    content: str
    delivery_status: str
    created_at: str


class WhatsAppConversationDetail(BaseModel):
    conversation_id: str
    wa_id: str
    phone_number_masked: str
    contact_name: Optional[str] = None
    language_preference: str
    status: str
    last_message_at: Optional[str] = None
    messages: List[WhatsAppMessageItem] = Field(default_factory=list)
