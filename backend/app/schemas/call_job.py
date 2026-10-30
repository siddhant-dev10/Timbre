from datetime import datetime
from typing import List, Optional, Any, Dict, Literal
import re
from pydantic import BaseModel, Field, ConfigDict, field_validator, model_validator


def _normalize_e164(value: str) -> str:
    compact = re.sub(r"[\s().-]", "", value)
    if not re.fullmatch(r"\+?\d+", compact):
        raise ValueError("Enter a phone number using digits and an optional leading +.")
    if compact.startswith("0") and len(compact) == 11:
        compact = compact[1:]
    if len(compact) == 10:
        compact = "+91" + compact
    elif compact.startswith("91") and len(compact) == 12:
        compact = "+" + compact
    if not re.fullmatch(r"\+[1-9]\d{7,14}", compact):
        raise ValueError("Enter a valid international phone number (E.164); Indian 10-digit numbers are accepted.")
    return compact


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

    @field_validator("consented_phone_number")
    @classmethod
    def normalize_consented_number(cls, value: Optional[str]) -> Optional[str]:
        return _normalize_e164(value) if value else value

    @model_validator(mode="after")
    def validate_real_call_gate(self):
        if self.is_real_call and not self.consented_phone_number:
            raise ValueError("A consented recipient phone number is required for a real call request.")
        if self.is_real_call and not self.consent_confirmed:
            raise ValueError("Recipient consent must be confirmed for a real call request.")
        return self


class DryRunCallRequest(BaseModel):
    """Local-only rehearsal. Recipient is validated, masked, and never dialed."""
    citizen_id: str
    trigger_event: str = "CONTROLLED_DEMO"
    test_recipient_number: str = Field(..., min_length=10, max_length=24)
    recipient_has_consented: bool

    @field_validator("test_recipient_number")
    @classmethod
    def normalize_number(cls, value: str) -> str:
        return _normalize_e164(value)

    @field_validator("recipient_has_consented")
    @classmethod
    def require_recipient_consent(cls, value: bool) -> bool:
        if not value:
            raise ValueError("Confirm that the recipient agreed to this demonstration.")
        return value


class ApprovedTestCallRequest(BaseModel):
    """One manually reviewed call to a consenting test recipient."""
    citizen_id: str
    test_recipient_number: str = Field(..., min_length=10, max_length=24)
    language: Literal["hi", "en"] = "hi"
    recipient_has_consented: bool
    script_reviewed: bool
    ai_disclosure_confirmed: bool
    caller_id_reviewed: bool
    confirm_single_call: bool
    confirmation_phrase: str

    @field_validator("test_recipient_number")
    @classmethod
    def normalize_number(cls, value: str) -> str:
        return _normalize_e164(value)

    @model_validator(mode="after")
    def require_explicit_review(self):
        required = {
            "recipient_has_consented": self.recipient_has_consented,
            "script_reviewed": self.script_reviewed,
            "ai_disclosure_confirmed": self.ai_disclosure_confirmed,
            "caller_id_reviewed": self.caller_id_reviewed,
            "confirm_single_call": self.confirm_single_call,
        }
        if not all(required.values()):
            raise ValueError("Recipient consent, script review, AI disclosure, caller-ID review, and one-call confirmation are required.")
        if self.confirmation_phrase.strip() != "CALL ONCE":
            raise ValueError("Type CALL ONCE to confirm this individual call.")
        return self


class CallJobResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    citizen_id: str
    citizen_name: str
    trigger_event: str
    direction: str = "outbound"
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
    model_config = ConfigDict(extra="ignore")

    id: str
    agent_id: Optional[str] = None
    status: str
    user_data: Optional[Dict[str, Any]] = None
    transcript: Optional[str] = None
    call_duration: Optional[int] = None
    created_at: Optional[str] = None
    call_type: Optional[str] = None
    direction: Optional[str] = None
    telephony_data: Optional[Dict[str, Any]] = None
    user_number: Optional[str] = None
    from_phone_number: Optional[str] = None
    to_phone_number: Optional[str] = None
