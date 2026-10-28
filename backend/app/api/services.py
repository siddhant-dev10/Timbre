import json
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session
from app.database.session import get_db
from app.models.service_scheme import ServiceScheme
from app.schemas.service_scheme import ServiceSchemeResponse

router = APIRouter(prefix="/services", tags=["Government Services Catalogue"])


def _to_service_response(s: ServiceScheme) -> ServiceSchemeResponse:
    docs = []
    try:
        docs = json.loads(s.commonly_required_documents)
    except Exception:
        pass

    return ServiceSchemeResponse(
        id=s.id,
        service_code=s.service_code,
        name=s.name,
        service_name=s.name,
        category=s.category,
        administering_body=s.administering_body,
        intended_beneficiaries=s.intended_beneficiaries,
        basic_eligibility_criteria=s.basic_eligibility_criteria,
        commonly_required_documents=docs,
        required_docs=docs,
        application_channel=s.application_channel,
        application_mode=s.application_channel,
        statutory_fee_inr=s.statutory_fee_inr,
        official_application_url=s.official_application_url,
        official_portal_url=s.official_application_url,
        official_source_url=s.official_source_url,
        description_english=s.description_english,
        description_hinglish=s.description_hinglish,
        min_age=s.min_age,
        max_age=s.max_age,
        last_verification_date=s.last_verification_date.isoformat(),
        verification_status=s.verification_status
    )


@router.get("", response_model=List[ServiceSchemeResponse])
def list_services(
    category: Optional[str] = Query(None, description="Filter by service category"),
    db: Session = Depends(get_db)
):
    query = db.query(ServiceScheme)
    if category:
        query = query.filter(ServiceScheme.category.ilike(f"%{category}%"))
    services = query.order_by(ServiceScheme.id).all()
    return [_to_service_response(s) for s in services]


@router.get("/{service_id}", response_model=ServiceSchemeResponse)
def get_service_by_id(service_id: str, db: Session = Depends(get_db)):
    svc = db.query(ServiceScheme).filter(
        (ServiceScheme.id == service_id) | (ServiceScheme.service_code == service_id)
    ).first()
    if not svc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Service '{service_id}' not found in official catalogue."
        )
    return _to_service_response(svc)
