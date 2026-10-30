"""SQLAlchemy Models for WhatsApp Business Cloud API Messaging in Timbre.

Maintains isolated conversation sessions, incoming and outgoing message audit logs,
deduplication keys (wamid), and privacy preservation (masked phone numbers).
"""
import uuid
from datetime import datetime, timezone
from sqlalchemy import Column, String, Integer, DateTime, Text, ForeignKey, Index
from app.database.base import Base


def utc_now():
    return datetime.now(timezone.utc)


class WhatsAppConversation(Base):
    """Represents an isolated multi-turn WhatsApp conversation session for a citizen sender."""
    __tablename__ = "whatsapp_conversations"

    id = Column(String(64), primary_key=True, default=lambda: str(uuid.uuid4()))
    wa_id = Column(String(32), unique=True, nullable=False, index=True)
    phone_number_masked = Column(String(32), nullable=False)
    contact_name = Column(String(128), nullable=True)
    language_preference = Column(String(32), nullable=False, default="Hinglish")
    status = Column(String(32), nullable=False, default="ACTIVE")
    last_message_at = Column(DateTime, default=utc_now)
    created_at = Column(DateTime, default=utc_now)
    updated_at = Column(DateTime, default=utc_now, onupdate=utc_now)


class WhatsAppMessage(Base):
    """Represents an individual incoming or outgoing WhatsApp message with delivery status."""
    __tablename__ = "whatsapp_messages"

    id = Column(String(64), primary_key=True, default=lambda: str(uuid.uuid4()))
    conversation_id = Column(String(64), ForeignKey("whatsapp_conversations.id"), nullable=False, index=True)
    wa_id = Column(String(32), nullable=False, index=True)
    wamid = Column(String(128), nullable=True, unique=True, index=True)
    direction = Column(String(16), nullable=False, default="inbound")  # inbound or outbound
    message_type = Column(String(32), nullable=False, default="text")
    content = Column(Text, nullable=False, default="")
    delivery_status = Column(String(32), nullable=False, default="received")  # received, sent, failed, simulated
    meta_json = Column(Text, nullable=False, default="{}")
    created_at = Column(DateTime, default=utc_now)
