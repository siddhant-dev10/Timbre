import uuid
from datetime import datetime, timezone
from sqlalchemy import Column, String, Integer, Boolean, DateTime, Text, ForeignKey
from app.database.base import Base


def utc_now():
    return datetime.now(timezone.utc)


class CallJobRecord(Base):
    __tablename__ = "call_jobs"

    id = Column(String(64), primary_key=True, default=lambda: str(uuid.uuid4()))
    citizen_id = Column(String(32), ForeignKey("citizens.id"), nullable=False, index=True)
    citizen_name = Column(String(128), nullable=False)
    trigger_event = Column(String(64), nullable=False, default="MANUAL_TRIGGER")
    direction = Column(String(16), nullable=False, default="outbound", server_default="outbound", index=True)
    job_status = Column(String(32), nullable=False, default="QUEUED")
    idempotency_key = Column(String(128), unique=True, index=True, nullable=False)
    attempt_count = Column(Integer, nullable=False, default=0)
    scheduled_at = Column(DateTime, default=utc_now)
    duration_seconds = Column(Integer, nullable=False, default=0)
    is_real_call = Column(Boolean, nullable=False, default=False)
    recipient_phone = Column(String(32), nullable=False)
    bolna_execution_id = Column(String(64), nullable=True)
    transcript_events = Column(Text, nullable=False, default="[]")
    created_at = Column(DateTime, default=utc_now)
    updated_at = Column(DateTime, default=utc_now, onupdate=utc_now)
