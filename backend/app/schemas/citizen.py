from datetime import date, datetime
from typing import List, Optional, Any
from pydantic import BaseModel, Field, ConfigDict


class CitizenBase(BaseModel):
    first_name: str
    last_name: str
    name: Optional[str] = None
    date_of_birth: date
    age: int
    gender: str = "OTHER"
    state: str
    district: str
    city_or_village: str
    rural_or_urban: str = "RURAL"
    preferred_language: str = "Hindi"
    education: str
    occupation: str
    employment_status: str
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


class CitizenCreate(CitizenBase):
    id: str


class CitizenUpdate(BaseModel):
    date_of_birth: Optional[date] = None
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    simulated_life_event: Optional[str] = None
    simulated_income_bracket: Optional[str] = None
    is_student: Optional[bool] = None
    is_farmer: Optional[bool] = None
    is_senior_citizen: Optional[bool] = None


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
