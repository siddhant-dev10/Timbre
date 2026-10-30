import uuid
from datetime import datetime, date, timezone
from sqlalchemy import Column, String, Integer, Date, DateTime, Text, ForeignKey
from app.database.base import Base


def utc_now():
    return datetime.now(timezone.utc)


class SimulationRecord(Base):
    __tablename__ = "simulations"

    id = Column(String(64), primary_key=True, default=lambda: str(uuid.uuid4()))
    citizen_id = Column(String(32), ForeignKey("citizens.id"), nullable=False, index=True)
    trigger_event = Column(String(64), nullable=False)
    previous_age = Column(Integer, nullable=False)
    calculated_age = Column(Integer, nullable=False)
    previous_dob = Column(Date, nullable=False)
    simulated_dob = Column(Date, nullable=False)
    eligible_services = Column(Text, nullable=False, default="[]")
    preliminary_notes = Column(Text, nullable=False, default="")
    llm_explanation = Column(Text, nullable=False, default="")
    created_at = Column(DateTime, default=utc_now)
