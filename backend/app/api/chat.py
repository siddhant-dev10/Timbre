import json
import uuid
from typing import List, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from app.database.session import get_db
from app.models.citizen import Citizen
from app.models.service_scheme import ServiceScheme
from app.schemas.chat import ChatRequest, ChatResponse
from app.schemas.service_scheme import ServiceSchemeResponse
from app.services.llm_service import llm_service
from app.services.rules_engine import evaluate_all_services
from app.config import settings

router = APIRouter(prefix="/chat", tags=["Conversational AI"])


def _extract_keywords(text: str) -> List[str]:
    text_lower = text.lower()
    matches = []
    keywords_map = {
        "SVC-VOTER-ID": ["voter", "vote", "matdata", "form 6", "epic", "chunav", "election"],
        "SVC-LEARNER-LICENCE": ["licence", "license", "driving", "gadi", "parivahan", "sarathi", "ll", "dl"],
        "SVC-PAN-CARD": ["pan", "pan card", "tax", "income tax", "bank account", "form 49a"],
        "SVC-PM-KISAN": ["kisan", "farmer", "agriculture", "kheti", "pm kisan", "samman nidhi", "6000"],
        "SVC-AYUSHMAN-BHARAT": ["ayushman", "health", "hospital", "beema", "insurance", "ilaj", "golden card", "pmjay"],
        "SVC-NSP-SCHOLARSHIP": ["scholarship", "padhai", "college", "fees", "chhatravritti", "nsp", "student"],
        "SVC-IGNOAPS-PENSION": ["pension", "old age", "vridhha", "bujurg", "senior", "nsap", "60"],
        "SVC-SUKANYA-SAMRIDDHI": ["sukanya", "beti", "daughter", "girl child", "ssa", "post office"],
        "SVC-E-SHRAM": ["shram", "eshram", "worker", "labour", "majdoor", "uan", "unorganised"],
        "SVC-UDID-DISABILITY": ["disability", "divyang", "handicap", "swavlamban", "udid"]
    }
    for svc_id, triggers in keywords_map.items():
        if any(tr in text_lower for tr in triggers):
            matches.append(svc_id)
    return matches


@router.post("", response_model=ChatResponse)
async def chat_with_assistant(request: ChatRequest, db: Session = Depends(get_db)):
    citizen = db.query(Citizen).filter(Citizen.id == request.citizen_id).first()
    if not citizen:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Citizen '{request.citizen_id}' not found."
        )

    conversation_id = request.conversation_id or str(uuid.uuid4())
    ref_date = settings.parsed_reference_date

    # 1. Retrieve Grounding Schemes based on citizen profile & query keywords
    query_service_ids = _extract_keywords(request.message)
    
    # If no specific query keywords, evaluate citizen against all services
    if not query_service_ids:
        citizen_snapshot = {
            "id": citizen.id,
            "date_of_birth": citizen.date_of_birth,
            "age": citizen.age,
            "gender": citizen.gender,
            "state": citizen.state,
            "district": citizen.district,
            "simulated_income_bracket": citizen.simulated_income_bracket,
            "is_student": citizen.is_student,
            "is_farmer": citizen.is_farmer,
            "is_senior_citizen": citizen.is_senior_citizen,
            "occupation": citizen.occupation,
            "simulated_life_event": citizen.simulated_life_event,
            "children": citizen.children
        }
        eval_results = evaluate_all_services(citizen_snapshot, ref_date)
        eligible = [res.service.id for res in eval_results if res.is_eligible]
        query_service_ids = eligible[:3]

    matched_schemes = db.query(ServiceScheme).filter(ServiceScheme.id.in_(query_service_ids)).all()
    if not matched_schemes:
        matched_schemes = db.query(ServiceScheme).limit(2).all()

    grounded_responses: List[ServiceSchemeResponse] = []
    schemes_dicts: List[Dict[str, Any]] = []

    for s in matched_schemes:
        docs = []
        try:
            docs = json.loads(s.commonly_required_documents)
        except Exception:
            pass
        s_resp = ServiceSchemeResponse(
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
        grounded_responses.append(s_resp)
        schemes_dicts.append({
            "id": s.id,
            "name": s.name,
            "administering_body": s.administering_body,
            "basic_eligibility_criteria": s.basic_eligibility_criteria,
            "statutory_fee_inr": s.statutory_fee_inr,
            "official_application_url": s.official_application_url,
            "commonly_required_documents": docs
        })

    # 2. Query Local LLM with domain grounding
    language = request.language_preference or citizen.preferred_language or "Hinglish"
    system_prompt = llm_service.build_grounded_system_prompt(schemes_dicts, language=language)
    user_prompt = (
        f"Citizen Profile: Name={citizen.name}, Age={citizen.age}, State={citizen.state}, "
        f"Occupation={citizen.occupation}, Income Category={citizen.simulated_income_bracket}.\n"
        f"Citizen Query: '{request.message}'"
    )

    llm_result = await llm_service.generate_response(
        prompt=user_prompt,
        system_prompt=system_prompt
    )

    if llm_result.get("success"):
        answer = llm_result.get("response", "")
        model_used = llm_result.get("model_used", settings.OLLAMA_MODEL)
    else:
        # High quality grounded domain fallback
        primary_svc = grounded_responses[0] if grounded_responses else None
        if primary_svc:
            answer = (
                f"Namaste {citizen.name} ji! Aapki jankari ke anusar, aap '{primary_svc.name}' ke liye "
                f"aavedan kar sakte hain. Iske liye aavedan portal {primary_svc.official_application_url} hai. "
                f"Zaroori documents: {', '.join(primary_svc.commonly_required_documents[:3])}. "
                "Yeh preliminary guidance hai, antim satyapan official portal par hoga."
            )
        else:
            answer = (
                f"Namaste {citizen.name} ji! Aapka anurodh prapt hua hai. "
                "Bharat Assist portal par sabhi statutory government schemes ki official jankari uplabdh hai."
            )
        model_used = "catalogue-grounded-fallback"

    return ChatResponse(
        conversation_id=conversation_id,
        citizen_id=citizen.id,
        answer=answer,
        language=language,
        grounded_services=grounded_responses,
        confidence_note=(
            "Preliminary AI guidance based on verified official catalogue entries. "
            "Consult official portals for statutory application processing."
        ),
        llm_model=model_used
    )
