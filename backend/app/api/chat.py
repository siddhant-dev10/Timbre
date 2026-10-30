import base64
import json
import re
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
from app.services.elevenlabs_service import elevenlabs_service
from app.services.rules_engine import evaluate_all_services
from app.services.profile_context import minimal_profile_context
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
        if any(re.search(r"(?<!\w)" + re.escape(tr) + r"(?!\w)", text_lower) for tr in triggers):
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
    
    broad_service_intent = any(word in request.message.lower() for word in (
        "scheme", "service", "yojana", "benefit", "eligible", "eligibility", "document", "apply", "application"
    ))
    # For broad benefit questions use deterministic profile rules. Unrelated or
    # unsupported questions receive no unrelated scheme context.
    if not query_service_ids and broad_service_intent:
        citizen_snapshot = {
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
            "official_source_url": s.official_source_url,
            "verification_status": s.verification_status,
            "last_verification_date": s.last_verification_date.isoformat(),
            "commonly_required_documents": docs
        })

    # 2. Query Local LLM with domain grounding
    language = request.language_preference or citizen.preferred_language or "Hinglish"
    system_prompt = llm_service.build_grounded_system_prompt(schemes_dicts, language=language)
    system_prompt += "\n\n" + minimal_profile_context(citizen, ref_date)
    system_prompt += (
        "\nTreat every profile value as synthetic demo data. Never claim official eligibility, "
        "current deadlines, fees, or exhaustive document requirements. Only repeat catalogue facts "
        "as preliminary and only when their verification status is VERIFIED; otherwise explicitly "
        "say the information needs checking on the official source. If no relevant catalogue facts "
        "are provided, say you cannot verify the answer and do not invent details."
    )
    user_prompt = request.message

    llm_result = await llm_service.generate_response(
        prompt=user_prompt,
        system_prompt=system_prompt,
        # Isolate in-memory history by synthetic profile so a reused client
        # conversation ID cannot mix two different demo records.
        conversation_id=f"{citizen.id}:{conversation_id}"
    )

    if llm_result.get("success"):
        answer = llm_result.get("response", "")
        model_used = llm_result.get("model_used", settings.NVIDIA_MODEL)
    else:
        code = llm_result.get("status_code", 503)
        raise HTTPException(
            status_code=429 if code == 429 else 503,
            detail=llm_result.get("error", "AI provider is unavailable. Please retry."),
        )

    # Optional speech synthesis with ElevenLabs
    audio_base64 = None
    tts_error = None
    if getattr(request, "synthesize_voice", False):
        if not elevenlabs_service.is_configured():
            tts_error = "ElevenLabs speech is not configured."
        else:
            try:
                audio_bytes = await elevenlabs_service.synthesize_speech(text=answer)
                audio_base64 = base64.b64encode(audio_bytes).decode("ascii")
            except PermissionError:
                tts_error = "ElevenLabs authentication failed. Check its configured key."
            except TimeoutError:
                tts_error = "ElevenLabs request timed out."
            except Exception as exc:
                tts_error = (
                    "ElevenLabs quota or rate limit reached."
                    if "service limit reached" in str(exc).lower()
                    else "ElevenLabs speech synthesis failed."
                )

    return ChatResponse(
        conversation_id=conversation_id,
        citizen_id=citizen.id,
        answer=answer,
        language=language,
        grounded_services=grounded_responses,
        confidence_note=(
            "Preliminary guidance based on Timbre's stored service catalogue. "
            "Check the official portal for current rules and application processing."
        ),
        llm_model=model_used,
        audio_base64=audio_base64,
        tts_error=tts_error,
    )
