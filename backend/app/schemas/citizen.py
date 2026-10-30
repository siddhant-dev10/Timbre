from datetime import date, datetime
import re
from typing import List, Optional, Any
from pydantic import BaseModel, Field, ConfigDict, field_validator


class CitizenBase(BaseModel):
    first_name: str = Field(min_length=1, max_length=64)
    last_name: str = Field(min_length=1, max_length=64)
    name: Optional[str] = None
    date_of_birth: date
    age: int = 0
    gender: str = "OTHER"
    state: str = Field(min_length=1, max_length=64)
    district: str = Field(min_length=1, max_length=64)
    city_or_village: str = Field(min_length=1, max_length=64)
    rural_or_urban: str = "RURAL"
    preferred_language: str = "Hindi"
    education: str = "Not provided"
    occupation: str = "Not provided"
    employment_status: str = "Not provided"
    synthetic_family_income: int = 120000
    simulated_income_bracket: str = "LOW"
    family_size: int = 4
    marital_status: str = "Single"
    children: int = 0
    is_student: bool = False
    is_farmer: bool = False
    is_senior_citizen: bool = False
    simulated_life_event: str = "Approaching age 18"
    potentially_relevant_services: List[str] = Field(default_factory=list)
    eligibility_notes: str = ""
    required_documents: List[str] = Field(default_factory=list)
    demo_only: bool = True
    phone_number: str = "DEMO-PHONE-0000"
    email: str = "demo@example.com"
    pincode: str = "110001"
    record_source: str = "synthetic"

    @field_validator("record_source")
    @classmethod
    def valid_record_source(cls, value: str) -> str:
        value = value.strip().lower()
        if value not in {"synthetic", "real"}:
            raise ValueError("record_source must be 'synthetic' or 'real'")
        return value

    @field_validator("date_of_birth")
    @classmethod
    def birth_date_not_in_future(cls, value: date) -> date:
        if value > date.today():
            raise ValueError("date_of_birth cannot be in the future")
        return value

    @field_validator("phone_number")
    @classmethod
    def validate_phone_number(cls, value: str) -> str:
        value = value.strip()
        if value.upper().startswith("DEMO-PHONE-"):
            return value
        digits = re.sub(r"\D", "", value)
        if len(digits) < 7 or len(digits) > 15 or not re.fullmatch(r"[+0-9().\-\s]+", value):
            raise ValueError("phone_number must be a valid international-style number or synthetic demo marker")
        return value

    @field_validator("email")
    @classmethod
    def validate_email(cls, value: str) -> str:
        value = value.strip()
        if value and not re.fullmatch(r"[^\s@]+@[^\s@]+\.[^\s@]+", value):
            raise ValueError("email must be a valid email address")
        return value


class CitizenCreate(CitizenBase):
    id: str


class CitizenUpdate(BaseModel):
    first_name: Optional[str] = Field(default=None, min_length=1, max_length=64)
    last_name: Optional[str] = Field(default=None, min_length=1, max_length=64)
    date_of_birth: Optional[date] = None
    gender: Optional[str] = None
    state: Optional[str] = None
    district: Optional[str] = None
    city_or_village: Optional[str] = None
    rural_or_urban: Optional[str] = None
    preferred_language: Optional[str] = None
    education: Optional[str] = None
    occupation: Optional[str] = None
    employment_status: Optional[str] = None
    synthetic_family_income: Optional[int] = Field(default=None, ge=0)
    family_size: Optional[int] = Field(default=None, ge=1)
    marital_status: Optional[str] = None
    children: Optional[int] = Field(default=None, ge=0)
    phone_number: Optional[str] = None
    email: Optional[str] = None
    pincode: Optional[str] = None
    simulated_life_event: Optional[str] = None
    simulated_income_bracket: Optional[str] = None
    is_student: Optional[bool] = None
    is_farmer: Optional[bool] = None
    is_senior_citizen: Optional[bool] = None
    record_source: Optional[str] = None

    @field_validator("record_source")
    @classmethod
    def valid_optional_record_source(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return value
        value = value.strip().lower()
        if value not in {"synthetic", "real"}:
            raise ValueError("record_source must be 'synthetic' or 'real'")
        return value

    @field_validator("date_of_birth")
    @classmethod
    def valid_optional_birth_date(cls, value: Optional[date]) -> Optional[date]:
        if value is not None and value > date.today():
            raise ValueError("date_of_birth cannot be in the future")
        return value

    @field_validator("phone_number")
    @classmethod
    def valid_optional_phone_number(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return value
        value = value.strip()
        if value.upper().startswith("DEMO-PHONE-"):
            return value
        digits = re.sub(r"\D", "", value)
        if len(digits) < 7 or len(digits) > 15 or not re.fullmatch(r"[+0-9().\-\s]+", value):
            raise ValueError("phone_number must be a valid international-style number or synthetic demo marker")
        return value


class CitizenResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    first_name: str
    last_name: str
    name: str
    date_of_birth: str
    age: int
    gender: str
    state: str
    district: str
    city_or_village: str
    rural_or_urban: str
    preferred_language: str
    education: str
    occupation: str
    employment_status: str
    synthetic_family_income: int
    simulated_income_bracket: str
    family_size: int
    marital_status: str
    children: int
    is_student: bool
    is_farmer: bool
    is_senior_citizen: bool
    simulated_life_event: str
    potentially_relevant_services: List[str] = Field(default_factory=list)
    eligibility_notes: str
    required_documents: List[str] = Field(default_factory=list)
    demo_only: bool
    is_fictional: bool = True
    phone_number: str
    email: str
    pincode: str
    record_source: str = "synthetic"
    archived_at: Optional[datetime] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


class CitizenDobPatchResponse(BaseModel):
    citizen_id: str
    previous_age: int
    calculated_age: int
    event_detected: Optional[str] = None
    citizen: CitizenResponse


class CitizenListResponse(BaseModel):
    total: int
    limit: int
    offset: int
    citizens: List[CitizenResponse]
