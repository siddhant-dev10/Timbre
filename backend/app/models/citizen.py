from datetime import datetime, date, timezone
from sqlalchemy import Column, String, Integer, Boolean, Date, DateTime, Text
from app.database.base import Base


def utc_now():
    return datetime.now(timezone.utc)


class Citizen(Base):
    __tablename__ = "citizens"

    id = Column(String(32), primary_key=True, index=True)
    first_name = Column(String(64), nullable=False)
    last_name = Column(String(64), nullable=False)
    name = Column(String(128), nullable=False)
    date_of_birth = Column(Date, nullable=False)
    age = Column(Integer, nullable=False)
    gender = Column(String(16), nullable=False, default="OTHER")
    state = Column(String(64), nullable=False)
    district = Column(String(64), nullable=False)
    city_or_village = Column(String(64), nullable=False)
    rural_or_urban = Column(String(16), nullable=False, default="RURAL")
    preferred_language = Column(String(32), nullable=False, default="Hindi")
    education = Column(String(64), nullable=False)
    occupation = Column(String(64), nullable=False)
    employment_status = Column(String(32), nullable=False)
    synthetic_family_income = Column(Integer, nullable=False, default=120000)
    simulated_income_bracket = Column(String(32), nullable=False, default="LOW")
    family_size = Column(Integer, nullable=False, default=4)
    marital_status = Column(String(32), nullable=False, default="Single")
    children = Column(Integer, nullable=False, default=0)
    is_student = Column(Boolean, nullable=False, default=False)
    is_farmer = Column(Boolean, nullable=False, default=False)
    is_senior_citizen = Column(Boolean, nullable=False, default=False)
    simulated_life_event = Column(String(128), nullable=False, default="Approaching age 18")
    potentially_relevant_services = Column(Text, nullable=False, default="[]")
    eligibility_notes = Column(Text, nullable=False, default="")
    required_documents = Column(Text, nullable=False, default="[]")
    demo_only = Column(Boolean, nullable=False, default=True)
    phone_number = Column(String(32), nullable=False, default="DEMO-PHONE-0000")
    email = Column(String(64), nullable=False, default="demo@example.com")
    pincode = Column(String(16), nullable=False, default="110001")
    created_at = Column(DateTime, default=utc_now)
    updated_at = Column(DateTime, default=utc_now, onupdate=utc_now)
