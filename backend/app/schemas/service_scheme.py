from datetime import date
from typing import List, Optional
from pydantic import BaseModel, Field, ConfigDict


class ServiceSchemeResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    service_code: str
    name: str
    service_name: Optional[str] = None
    category: str
    administering_body: str
    intended_beneficiaries: str
    basic_eligibility_criteria: str
    commonly_required_documents: List[str] = Field(default_factory=list)
    required_docs: Optional[List[str]] = None
    application_channel: str
    application_mode: Optional[str] = None
    statutory_fee_inr: float = 0.0
    official_application_url: str
    official_portal_url: Optional[str] = None
    official_source_url: str
    description_english: str
    description_hinglish: str
    min_age: int = 18
    max_age: Optional[int] = None
    last_verification_date: str
    verification_status: str


class EligibilityResult(BaseModel):
    id: str
    citizen_id: str
    service: ServiceSchemeResponse
    is_eligible: bool
    status: str  # POTENTIALLY_ELIGIBLE, NEEDS_MORE_INFO, INELIGIBLE
    evaluated_at: str
    qualification_reason: str
    missing_documents: List[str] = Field(default_factory=list)
    disclaimer: str = (
        "Preliminary guidance only. Statutory eligibility is determined "
        "solely by official Indian authorities upon original document verification."
    )


class CitizenEvaluationResponse(BaseModel):
    citizen_id: str
    calculated_age: int
    eligible_services: List[ServiceSchemeResponse]
    detailed_results: List[EligibilityResult]
    call_job_scheduled: bool = False
