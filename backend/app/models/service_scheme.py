from datetime import datetime, date, timezone
from sqlalchemy import Column, String, Integer, Float, Date, DateTime, Text
from app.database.base import Base


def utc_now():
    return datetime.now(timezone.utc)


class ServiceScheme(Base):
    __tablename__ = "services"

    id = Column(String(64), primary_key=True, index=True)
    service_code = Column(String(64), unique=True, index=True, nullable=False)
    name = Column(String(128), nullable=False)
    category = Column(String(64), nullable=False)
    administering_body = Column(String(128), nullable=False)
    intended_beneficiaries = Column(Text, nullable=False)
    basic_eligibility_criteria = Column(Text, nullable=False)
    commonly_required_documents = Column(Text, nullable=False, default="[]")
    application_channel = Column(String(32), nullable=False, default="ONLINE")
    statutory_fee_inr = Column(Float, nullable=False, default=0.0)
    official_application_url = Column(String(256), nullable=False)
    official_source_url = Column(String(256), nullable=False)
    description_english = Column(Text, nullable=False)
    description_hinglish = Column(Text, nullable=False)
    min_age = Column(Integer, nullable=False, default=18)
    max_age = Column(Integer, nullable=True)
    last_verification_date = Column(Date, nullable=False, default=date(2026, 10, 28))
    verification_status = Column(String(32), nullable=False, default="NEEDS_REVIEW")
    created_at = Column(DateTime, default=utc_now)
