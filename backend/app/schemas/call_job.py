from datetime import datetime
from typing import List, Optional, Any, Dict
from pydantic import BaseModel, Field, ConfigDict


class CallEventSchema(BaseModel):
    id: str
    speaker: str  # AI_AGENT, CITIZEN, SYSTEM
    transcript_segment: str
    timestamp: str
    latency_ms: int = 0


class CallRequest(BaseModel):
    citizen_id: str
    trigger_event: str = "MANUAL_TRIGGER"
    # Strict safety: For a real call, the user must explicitly set is_real_call=True
    # and provide a verified, consented real phone number.
    is_real_call: bool = False
    consented_phone_number: Optional[str] = None
    consent_confirmed: bool = False


class CallJobResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    citizen_id: str
    citizen_name: str
    trigger_event: str
    job_status: str  # QUEUED, IN_PROGRESS, COMPLETED, FAILED, RETRY_SCHEDULED
    idempotency_key: str
    attempt_count: int = 0
    scheduled_at: str
    duration_seconds: int = 0
    is_real_call: bool = False
    recipient_phone: str
    bolna_execution_id: Optional[str] = None
    transcript_events: List[CallEventSchema] = Field(default_factory=list)


class CallJobListResponse(BaseModel):
    total: int
    jobs: List[CallJobResponse]


class BolnaWebhookPayload(BaseModel):
    id: str
    agent_id: Optional[str] = None
    status: str
    user_data: Optional[Dict[str, Any]] = None
    transcript: Optional[str] = None
    call_duration: Optional[int] = None
    created_at: Optional[str] = None
