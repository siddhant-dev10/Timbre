import base64
import json
import logging
import uuid
from typing import Dict, Any, List
from fastapi import APIRouter, Depends, HTTPException, status, Response
from sqlalchemy.orm import Session
from app.database.session import get_db
from app.models.citizen import Citizen
from app.models.service_scheme import ServiceScheme
from app.schemas.voice import SynthesizeRequest, VoiceChatRequest, VoiceChatResponse
from app.schemas.service_scheme import ServiceSchemeResponse
from app.services.llm_service import llm_service
from app.services.rules_engine import evaluate_all_services
from app.services.elevenlabs_service import elevenlabs_service
from app.config import settings

logger = logging.getLogger("timbre.voice_api")

router = APIRouter(prefix="/voice", tags=["Voice & TTS"])

# In-memory transient buffer for recently synthesized audio clips (LRU / FIFO capped)
_audio_cache: Dict[str, bytes] = {}
_MAX_CACHE_ITEMS = 50


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


@router.get("/status")
async def get_voice_status():
    """Returns safe diagnostic status of the ElevenLabs voice integration."""
    return elevenlabs_service.check_health()


@router.post("/synthesize")
async def synthesize_speech(request: SynthesizeRequest):
    """
    Direct Text-to-Speech synthesis using ElevenLabs and the custom Timbre voice.
    Returns binary MP3 audio stream (audio/mpeg).
    """
    if not elevenlabs_service.is_configured():
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="ElevenLabs TTS is not configured. Set ELEVENLABS_API_KEY and ELEVENLABS_VOICE_ID in backend .env."
        )

    try:
        audio_bytes = await elevenlabs_service.synthesize_speech(
            text=request.text,
            voice_id=request.voice_id,
            model_id=request.model_id
        )
        return Response(
            content=audio_bytes,
            media_type="audio/mpeg",
            headers={"Content-Disposition": 'inline; filename="timbre_speech.mp3"'}
        )
    except PermissionError as e:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except (TimeoutError, ConnectionError) as e:
        raise HTTPException(status_code=status.HTTP_504_GATEWAY_TIMEOUT, detail=str(e))
    except Exception as e:
        logger.error("Synthesis error: %s", str(e))
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(e))


@router.get("/audio/{audio_id}")
async def get_cached_audio(audio_id: str):
    """Retrieves and streams a previously synthesized MP3 audio clip by ID."""
    if audio_id not in _audio_cache:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Audio clip not found or expired.")
    
    return Response(
        content=_audio_cache[audio_id],
        media_type="audio/mpeg",
        headers={"Content-Disposition": f'inline; filename="{audio_id}.mp3"'}
    )


@router.post("/chat", response_model=VoiceChatResponse)
async def chat_with_voice(request: VoiceChatRequest, db: Session = Depends(get_db)):
    """
    Full Conversational Voice Pipeline:
    Flutter Client -> ASUS FastAPI -> Local Qwen (reasoning) -> ElevenLabs (Timbre Voice) -> Audio + Transcript to Flutter.
    """
    citizen = db.query(Citizen).filter(Citizen.id == request.citizen_id).first()
    if not citizen:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Citizen '{request.citizen_id}' not found."
        )

    conversation_id = request.conversation_id or str(uuid.uuid4())
    ref_date = settings.parsed_reference_date

    # 1. Statutory domain grounding
    query_service_ids = _extract_keywords(request.message)
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

    # 2. Local Qwen 3.5 9B Conversational Brain
    language = request.language_preference or citizen.preferred_language or "Hinglish"
    system_prompt = llm_service.build_grounded_system_prompt(schemes_dicts, language=language)
    user_prompt = (
        f"Citizen Profile: Name={citizen.name}, Age={citizen.age}, State={citizen.state}, "
        f"Occupation={citizen.occupation}, Income Category={citizen.simulated_income_bracket}.\n"
        f"Citizen Query: '{request.message}'"
    )

    llm_result = await llm_service.generate_response(
        prompt=user_prompt,
        system_prompt=system_prompt,
        conversation_id=conversation_id
    )

    if llm_result.get("success"):
        answer = llm_result.get("response", "")
        model_used = llm_result.get("model_used", settings.OLLAMA_MODEL)
    else:
        primary_svc = grounded_responses[0] if grounded_responses else None
        if primary_svc:
            answer = (
                f"Namaste {citizen.name} ji! Aapki jankari ke anusar, aap '{primary_svc.name}' ke liye "
                f"aavedan kar sakte hain. Iska official portal {primary_svc.official_application_url} hai. "
                "Yeh preliminary guidance hai."
            )
        else:
            answer = (
                f"Namaste {citizen.name} ji! Aapka anurodh prapt hua hai. "
                "Timbre portal par sabhi statutory government schemes ki official jankari uplabdh hai."
            )
        model_used = "catalogue-grounded-fallback"

    # 3. ElevenLabs Speech Synthesis (Timbre Custom Voice)
    audio_base64 = None
    audio_url = None

    if elevenlabs_service.is_configured():
        try:
            audio_bytes = await elevenlabs_service.synthesize_speech(
                text=answer,
                voice_id=request.voice_id
            )
            audio_base64 = base64.b64encode(audio_bytes).decode("ascii")
            
            # Cache audio for streaming
            audio_id = f"aud-{uuid.uuid4().hex[:12]}"
            if len(_audio_cache) >= _MAX_CACHE_ITEMS:
                _audio_cache.pop(next(iter(_audio_cache)))
            _audio_cache[audio_id] = audio_bytes
            audio_url = f"/api/v1/voice/audio/{audio_id}"
        except Exception as exc:
            logger.warning("Voice synthesis bypassed due to error: %s", str(exc))

    return VoiceChatResponse(
        conversation_id=conversation_id,
        citizen_id=citizen.id,
        answer=answer,
        language=language,
        audio_base64=audio_base64,
        audio_format="audio/mpeg",
        audio_url=audio_url,
        grounded_services=grounded_responses,
        confidence_note=(
            "Preliminary AI guidance based on verified official catalogue entries. "
            "Consult official portals for statutory application processing."
        ),
        llm_model=model_used,
        tts_provider="ElevenLabs",
        voice_name="Timbre"
    )
