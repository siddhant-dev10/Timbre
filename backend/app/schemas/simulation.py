from datetime import datetime, date
from typing import List, Optional
from pydantic import BaseModel, Field, ConfigDict
from app.schemas.service_scheme import ServiceSchemeResponse, EligibilityResult


class SimulationRequest(BaseModel):
    citizen_id: str
    trigger_event: str = "MILESTONE_AGE_18"
    target_dob: Optional[date] = None


class SimulationResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    citizen_id: str
    citizen_name: str
    trigger_event: str
    previous_age: int
    calculated_age: int
    previous_dob: str
    simulated_dob: str
    eligible_services: List[ServiceSchemeResponse]
    detailed_results: List[EligibilityResult]
    preliminary_notes: str
    llm_explanation: str
    created_at: str
    disclaimer: str = (
        "This simulation generates synthetic life events for testing. "
        "No actual citizen records or official registrations are modified."
    )
