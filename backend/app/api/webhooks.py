"""Bolna Telephony Webhook Ingress for Timbre.

Processes asynchronous call events (queued, ringing, completed, failed, duration)
with strict constant-time authentication, replay/duplicate prevention, and privacy preservation.
"""
import json
import logging
import re
import secrets
import time
import uuid
from datetime import date, datetime, timezone
from typing import Dict, Optional, Tuple
from fastapi import APIRouter, Depends, Header, HTTPException, Query, Request, status
from sqlalchemy.orm import Session

from app.config import settings
from app.database.session import get_db
from app.models.citizen import Citizen
from app.models.call_job import CallJobRecord
from app.schemas.call_job import BolnaWebhookPayload

logger = logging.getLogger("timbre.webhook")
router = APIRouter(prefix="/webhooks", tags=["Webhooks"])

# In-memory replay cache: execution_id -> (terminal_status, processed_at)
_processed_events: Dict[str, Tuple[str, float]] = {}
_MAX_REPLAY_CACHE = 500


def _mask_phone(phone: Optional[str]) -> str:
    """Masks caller phone number to protect citizen privacy."""
    if not phone:
        return "***0000"
    digits = re.sub(r"\D", "", phone)
    return "***" + digits[-4:] if len(digits) >= 4 else "***"


def _get_or_create_inbound_citizen(db: Session) -> Citizen:
    """Retrieves or creates a synthetic inbound caller profile fulfilling foreign key constraints."""
    inbound_citizen = db.query(Citizen).filter(Citizen.id == "CIT-INBOUND").first()
    if not inbound_citizen:
        inbound_citizen = Citizen(
            id="CIT-INBOUND",
            first_name="Inbound",
            last_name="Caller",
            name="Inbound Telephony Caller",
            date_of_birth=date(1990, 1, 1),
            age=35,
            gender="OTHER",
            state="India",
            district="National",
            city_or_village="Inbound",
            rural_or_urban="URBAN",
            preferred_language="Hindi",
            education="General",
            occupation="Citizen Inquirer",
            employment_status="Self-employed",
            synthetic_family_income=0,
            simulated_income_bracket="GENERAL",
            family_size=1,
            marital_status="Single",
            children=0,
            is_student=False,
            is_farmer=False,
            is_senior_citizen=False,
            simulated_life_event="Inbound Phone Inquiry",
            potentially_relevant_services="[]",
            eligibility_notes="Inbound telephony caller inquiring about civic assistance",
            required_documents="[]",
            demo_only=True,
            phone_number="INBOUND",
            email="inbound@timbre.internal",
            pincode="110001",
            record_source="synthetic",
        )
        db.add(inbound_citizen)
        db.flush()
    return inbound_citizen


@router.post("/bolna")
async def handle_bolna_webhook(
    payload: BolnaWebhookPayload,
    db: Session = Depends(get_db),
    webhook_secret: Optional[str] = Header(default=None, alias="X-Timbre-Webhook-Secret"),
    authorization: Optional[str] = Header(default=None),
    token: Optional[str] = Query(default=None),
):
    """
    Handles authenticated call status and completion callbacks from Bolna telephony.
    Authenticates via X-Timbre-Webhook-Secret header, Authorization: Bearer token, or ?token query param.
    Protects against duplicate delivery, replays, and unauthenticated probing.
    """
    if not settings.BOLNA_WEBHOOK_SECRET:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Bolna webhook secret is not configured in backend/.env.",
        )

    # 1. Multi-transport authentication check (Header, Bearer, Query param)
    candidate_secret: Optional[str] = None
    if webhook_secret:
        candidate_secret = webhook_secret.strip()
    elif authorization and authorization.startswith("Bearer "):
        candidate_secret = authorization.replace("Bearer ", "").strip()
    elif token:
        candidate_secret = token.strip()

    if not candidate_secret or not secrets.compare_digest(candidate_secret, settings.BOLNA_WEBHOOK_SECRET):
        logger.warning("Rejected unauthenticated webhook submission for execution: %s", payload.id[:8])
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Webhook authentication failed.",
        )

    # 2. Map external Bolna status to Timbre internal lifecycle state
    status_map = {
        "scheduled": "QUEUED",
        "queued": "QUEUED",
        "initiated": "IN_PROGRESS",
        "ringing": "IN_PROGRESS",
        "in-progress": "IN_PROGRESS",
        "call-disconnected": "COMPLETED",
        "completed": "COMPLETED",
        "busy": "FAILED",
        "no-answer": "FAILED",
        "canceled": "FAILED",
        "failed": "FAILED",
    }
    internal_status = status_map.get(payload.status.lower(), payload.status.upper())

    # 3. Duplicate and replay prevention
    cache_key = f"{payload.id}:{internal_status}"
    if cache_key in _processed_events:
        logger.info("Ignoring duplicate webhook delivery for %s (status: %s)", payload.id[:8], internal_status)
        return {
            "status": "duplicate_ignored",
            "execution_id": payload.id,
            "job_status": internal_status,
        }

    # Record event in replay prevention cache
    if len(_processed_events) >= _MAX_REPLAY_CACHE:
        _processed_events.pop(next(iter(_processed_events)))
    _processed_events[cache_key] = (internal_status, time.time())

    logger.info("Processing verified Bolna webhook for execution %s -> %s", payload.id[:8], internal_status)

    # 4. Locate call job record by bolna_execution_id or citizen user_data
    job = db.query(CallJobRecord).filter(
        CallJobRecord.bolna_execution_id == payload.id
    ).first()

    if not job and payload.user_data:
        cid = payload.user_data.get("citizen_id")
        if cid:
            job = db.query(CallJobRecord).filter(
                CallJobRecord.citizen_id == cid
            ).order_by(CallJobRecord.scheduled_at.desc()).first()

    # 5. Check if this is an inbound call event
    is_inbound = False
    caller_raw_number = None

    if payload.telephony_data:
        t_data = payload.telephony_data
        t_type = str(t_data.get("call_type", "")).lower()
        if t_type == "inbound" or ("from_number" in t_data and t_type != "outbound"):
            is_inbound = True
        caller_raw_number = t_data.get("from_number") or t_data.get("from")

    if not is_inbound:
        if (payload.call_type and payload.call_type.lower() == "inbound") or \
           (payload.direction and payload.direction.lower() == "inbound"):
            is_inbound = True
        elif payload.user_data and str(payload.user_data.get("call_type", "")).lower() == "inbound":
            is_inbound = True

    if not caller_raw_number:
        caller_raw_number = payload.user_number or payload.from_phone_number
    if not caller_raw_number and payload.user_data:
        caller_raw_number = payload.user_data.get("phone_number") or payload.user_data.get("caller_phone")

    # If unmatched and it is an inbound call, create an inbound CallJobRecord
    if not job and is_inbound:
        matched_citizen = None
        if caller_raw_number:
            raw_str = caller_raw_number.strip()
            clean_digits = re.sub(r"\D", "", raw_str)
            candidates = db.query(Citizen).filter(Citizen.archived_at.is_(None)).all()
            for c in candidates:
                c_phone = (c.phone_number or "").strip()
                if c_phone and c_phone == raw_str:
                    matched_citizen = c
                    break
                c_clean = re.sub(r"\D", "", c_phone)
                if clean_digits and c_clean:
                    if clean_digits == c_clean:
                        matched_citizen = c
                        break
                    if len(clean_digits) >= 10 and c_clean.endswith(clean_digits[-10:]):
                        matched_citizen = c
                        break
                    if len(c_clean) >= 10 and clean_digits.endswith(c_clean[-10:]):
                        matched_citizen = c
                        break
        if not matched_citizen:
            matched_citizen = _get_or_create_inbound_citizen(db)

        masked_phone = _mask_phone(caller_raw_number)
        job = CallJobRecord(
            id=str(uuid.uuid4()),
            citizen_id=matched_citizen.id,
            citizen_name=matched_citizen.name,
            trigger_event="INBOUND_CALL",
            direction="inbound",
            job_status=internal_status,
            idempotency_key=f"inbound:{payload.id}",
            attempt_count=1,
            scheduled_at=datetime.now(timezone.utc),
            duration_seconds=payload.call_duration or (payload.telephony_data.get("duration") if payload.telephony_data else 0) or 0,
            is_real_call=True,
            recipient_phone=masked_phone,
            bolna_execution_id=payload.id,
            transcript_events=json.dumps([{
                "id": str(uuid.uuid4()),
                "speaker": "AI_AGENT",
                "transcript_segment": "[Inbound call session initialized - conversation privacy preserved]",
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "latency_ms": 0,
            }]),
            created_at=datetime.now(timezone.utc),
        )
        db.add(job)
        db.commit()
        db.refresh(job)
        logger.info("Recorded new inbound call job %s for execution %s (caller: %s)", job.id, payload.id[:8], masked_phone)
        return {"status": "processed_inbound", "job_id": job.id, "job_status": internal_status}

    if job:
        job.job_status = internal_status
        if payload.call_duration is not None:
            job.duration_seconds = payload.call_duration
        elif payload.telephony_data and payload.telephony_data.get("duration") is not None:
            job.duration_seconds = payload.telephony_data.get("duration")

        # Append transcript segment safely without storing plain recipient PII
        if payload.transcript:
            events = []
            try:
                events = json.loads(job.transcript_events or "[]")
            except Exception:
                pass
            events.append({
                "id": str(uuid.uuid4()),
                "speaker": "AI_AGENT",
                "transcript_segment": "[Provider transcript omitted from local log for privacy.]",
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "latency_ms": 0,
            })
            job.transcript_events = json.dumps(events)

        db.commit()
        return {"status": "processed", "job_id": job.id, "job_status": internal_status}

    return {"status": "received_unmatched", "execution_id": payload.id, "job_status": internal_status}
