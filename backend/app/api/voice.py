import base64
import json
import logging
import re
import uuid
from typing import Dict, Any, List, Optional
from fastapi import APIRouter, Depends, HTTPException, status, Response, UploadFile, File, Form
from sqlalchemy.orm import Session
from app.database.session import get_db
from app.models.citizen import Citizen
from app.models.service_scheme import ServiceScheme
from app.schemas.voice import (
    SynthesizeRequest,
    VoiceChatRequest,
    VoiceChatResponse,
    TranscribeResponse,
    TurnRequest,
    TurnResponse,
    SessionHistoryResponse,
)
from app.schemas.service_scheme import ServiceSchemeResponse
from app.services.llm_service import llm_service
from app.services.rules_engine import evaluate_all_services
from app.services.profile_context import minimal_profile_context
from app.services.elevenlabs_service import elevenlabs_service
from app.services.whisper_service import whisper_service, WhisperServiceError
from app.services.session_service import session_manager
from app.services.audio_playback_manager import playback_manager
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
        if any(re.search(r"(?<!\w)" + re.escape(tr) + r"(?!\w)", text_lower) for tr in triggers):
            matches.append(svc_id)
    return matches


@router.get("/status")
async def get_voice_status():
    """Returns safe diagnostic status of the ElevenLabs TTS and Whisper STT integrations."""
    return {
        "elevenlabs_tts": elevenlabs_service.check_health(),
        "whisper_stt": whisper_service.check_health(),
    }


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
    except PermissionError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="ElevenLabs authentication failed. Check the configured API key.")
    except ValueError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Configured ElevenLabs voice or model was not found.")
    except TimeoutError:
        raise HTTPException(status_code=status.HTTP_504_GATEWAY_TIMEOUT, detail="ElevenLabs request timed out.")
    except ConnectionError:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail="Could not connect to ElevenLabs.")
    except RuntimeError as exc:
        if "service limit reached" in str(exc).lower():
            raise HTTPException(status_code=429, detail="ElevenLabs quota or rate limit reached.")
        logger.error("Speech synthesis failed (%s)", type(exc).__name__)
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail="ElevenLabs speech synthesis failed.")
    except Exception as exc:
        logger.error("Speech synthesis failed (%s)", type(exc).__name__)
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail="ElevenLabs speech synthesis failed.")


@router.get("/audio/{audio_id}")
async def get_cached_audio(audio_id: str):
    """Retrieves and streams a previously synthesized MP3 audio clip by ID."""
    audio_bytes, pstatus = playback_manager.get_audio(audio_id)
    if pstatus == "CANCELLED":
        raise HTTPException(
            status_code=status.HTTP_410_GONE,
            detail="Audio playback was cancelled due to interruption or session termination."
        )
    if audio_bytes is None:
        if audio_id in _audio_cache:
            audio_bytes = _audio_cache[audio_id]
        else:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Audio clip not found or expired.")

    return Response(
        content=audio_bytes,
        media_type="audio/mpeg",
        headers={"Content-Disposition": f'inline; filename="{audio_id}.mp3"'}
    )


@router.post("/playback/{session_id}/cancel")
async def cancel_session_audio(session_id: str):
    """
    Halts active audio playback on the client and marks server-cached audio as cancelled.
    Prevents stale in-flight speech from playing after an interruption or hang-up.
    """
    cancelled_count = playback_manager.cancel_session_playback(session_id, reason="client_interrupt")
    session = session_manager.get_session(session_id)
    if session:
        session.status = "INTERRUPTED"
    return {
        "status": "CANCELLED",
        "session_id": session_id,
        "cancelled_clips": cancelled_count,
    }


@router.post("/chat", response_model=VoiceChatResponse)
async def chat_with_voice(request: VoiceChatRequest, db: Session = Depends(get_db)):
    """
    Text chat pipeline with optional ElevenLabs speech synthesis.
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
    broad_service_intent = any(word in request.message.lower() for word in (
        "scheme", "service", "yojana", "benefit", "eligible", "eligibility", "document", "apply", "application"
    ))
    if not query_service_ids and broad_service_intent:
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

    # 2. NVIDIA Nemotron conversational response
    language = request.language_preference or citizen.preferred_language or "Hinglish"
    system_prompt = llm_service.build_grounded_system_prompt(schemes_dicts, language=language)
    system_prompt += "\n\n" + minimal_profile_context(citizen, settings.parsed_reference_date)
    system_prompt += (
        "\nTreat every profile value as synthetic demo data. Never claim official eligibility, current deadlines, fees, "
        "or exhaustive document requirements. Use catalogue entries for factual claims only when status is VERIFIED. "
        "If information is pending or absent, say it cannot be verified and direct the user to an official source."
    )
    user_prompt = request.message

    llm_result = await llm_service.generate_response(
        prompt=user_prompt,
        system_prompt=system_prompt,
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

    # 3. ElevenLabs Speech Synthesis (Timbre Custom Voice)
    audio_base64 = None
    audio_url = None
    tts_error = None

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
            logger.warning("Voice synthesis bypassed due to %s", type(exc).__name__)
            tts_error = "ElevenLabs speech synthesis failed."
    else:
        tts_error = "ElevenLabs speech is not configured."

    return VoiceChatResponse(
        conversation_id=conversation_id,
        citizen_id=citizen.id,
        answer=answer,
        language=language,
        audio_base64=audio_base64,
        audio_format="audio/mpeg",
        audio_url=audio_url,
        tts_error=tts_error,
        grounded_services=grounded_responses,
        confidence_note=(
            "Preliminary guidance based on Timbre's stored service catalogue. "
            "Check the official portal for current rules and application processing."
        ),
        llm_model=model_used,
        tts_provider="ElevenLabs",
        voice_name="Timbre"
    )


@router.post("/transcribe", response_model=TranscribeResponse)
async def transcribe_audio_endpoint(
    file: Optional[UploadFile] = File(None),
    audio_base64: Optional[str] = Form(None),
    language: Optional[str] = Form("hi"),
):
    """
    Transcribes audio into Hindi/English text using Whisper.
    Accepts either an uploaded audio file (WAV, MP3, WebM) or a base64 encoded audio string.
    """
    audio_bytes: Optional[bytes] = None

    if file is not None:
        audio_bytes = await file.read()
    elif audio_base64:
        try:
            audio_bytes = base64.b64decode(audio_base64)
        except Exception as exc:
            raise HTTPException(status_code=400, detail="Invalid base64 audio payload.") from exc

    if not audio_bytes or len(audio_bytes) < 32:
        raise HTTPException(
            status_code=400,
            detail="No valid audio data provided. Upload an audio file or supply audio_base64.",
        )

    try:
        result = await whisper_service.transcribe_audio(audio_bytes, language=language)
        return TranscribeResponse(**result)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except WhisperServiceError as exc:
        raise HTTPException(status_code=502, detail=f"Speech recognition service error: {exc}") from exc
    except Exception as exc:
        logger.error("Transcription endpoint error: %s", exc)
        raise HTTPException(status_code=500, detail="Transcription could not be completed.") from exc


@router.post("/turn", response_model=TurnResponse)
async def process_call_turn(
    request: TurnRequest,
    db: Session = Depends(get_db),
):
    """
    Executes a complete telephone conversational turn:
    User Audio/Text -> Whisper STT -> NVIDIA Nemotron (Hindi) -> ElevenLabs TTS.
    Measures and logs latencies for every stage of the turn.
    """
    citizen = db.query(Citizen).filter(Citizen.id == request.citizen_id).first()
    if not citizen:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Citizen '{request.citizen_id}' not found.",
        )

    db_services = db.query(ServiceScheme).all()

    # Decode audio if provided
    audio_bytes: Optional[bytes] = None
    if request.audio_base64:
        try:
            audio_bytes = base64.b64decode(request.audio_base64)
        except Exception as exc:
            raise HTTPException(status_code=400, detail="Invalid base64 audio string.") from exc

    session = session_manager.get_or_create_session(
        session_id=request.session_id,
        citizen=citizen,
        language=request.language,
        is_simulation=True,
    )

    try:
        turn = await session_manager.execute_turn(
            session=session,
            citizen=citizen,
            db_services=db_services,
            user_audio_bytes=audio_bytes,
            user_text=request.text,
            synthesize_voice=request.synthesize_voice,
        )

        return TurnResponse(
            session_id=session.session_id,
            turn_id=turn.turn_id,
            turn_index=turn.turn_index,
            user_transcript=turn.user_transcript,
            ai_response=turn.ai_response,
            language=turn.language,
            latencies_ms=turn.latencies,
            is_unclear=turn.is_unclear,
            stop_requested=turn.stop_requested,
            audio_url=turn.audio_url,
            tts_error=turn.tts_error,
            session_status=session.status,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        logger.error("Call turn processing failed: %s", exc)
        raise HTTPException(status_code=500, detail="Turn processing encountered an error.") from exc


@router.get("/turn/{session_id}", response_model=SessionHistoryResponse)
def get_session_history(session_id: str):
    """Retrieves complete conversation context and latency telemetry for an active call session."""
    session = session_manager.get_session(session_id)
    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Call session '{session_id}' not found.",
        )
    return SessionHistoryResponse(**session.to_dict())


@router.post("/turn/{session_id}/terminate")
def terminate_session(session_id: str):
    """Gracefully ends a call session."""
    session = session_manager.get_session(session_id)
    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Call session '{session_id}' not found.",
        )
    session.status = "COMPLETED"
    return {"status": "COMPLETED", "session_id": session_id, "turns": len(session.turns)}

