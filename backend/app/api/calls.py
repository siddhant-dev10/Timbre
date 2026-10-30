import ipaddress
import json
import re
import uuid
from datetime import datetime, timezone
from typing import Optional, List
from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy.orm import Session
from app.database.session import get_db
from app.models.citizen import Citizen
from app.models.call_job import CallJobRecord
from app.schemas.call_job import (
    CallRequest,
    CallJobResponse,
    CallEventSchema,
    CallJobListResponse,
    DryRunCallRequest,
    ApprovedTestCallRequest,
)
from app.services.bolna_service import BolnaProviderError, bolna_service
from app.config import settings

router = APIRouter(prefix="/calls", tags=["Voice Calls & Audio Telemetry"])


def _mask_phone(phone: str) -> str:
    digits = re.sub(r"\D", "", phone)
    return "***" + digits[-4:] if len(digits) >= 4 else "***"


def _require_local_client(http_request: Request) -> None:
    peer = http_request.client.host if http_request.client else ""
    try:
        local = ipaddress.ip_address(peer).is_loopback
    except ValueError:
        local = peer == "testclient"
    if not local:
        raise HTTPException(status_code=403, detail="Call controls are available only from this Mac.")


@router.post("/dry-run", response_model=CallJobResponse, status_code=status.HTTP_201_CREATED)
def create_local_dry_run(
    request: DryRunCallRequest,
    http_request: Request,
    db: Session = Depends(get_db),
):
    """Create a consent-checked local rehearsal. This route never calls Bolna or a phone network."""
    _require_local_client(http_request)
    citizen = db.query(Citizen).filter(Citizen.id == request.citizen_id, Citizen.archived_at.is_(None)).first()
    if not citizen:
        raise HTTPException(status_code=404, detail="Synthetic demo profile not found.")
    if not citizen.demo_only or not citizen.id.startswith("CIT-"):
        raise HTTPException(status_code=403, detail="Dry-run rehearsals require a synthetic demo profile.")

    idempotency_key = f"dryrun-{citizen.id}-{request.trigger_event}"
    if db.query(CallJobRecord).filter(CallJobRecord.idempotency_key == idempotency_key).first():
        raise HTTPException(status_code=409, detail="This dry-run rehearsal was already recorded.")

    # The number is validated for the consented rehearsal, then masked. It is
    # never supplied to a telephony service and never persisted in full.
    masked_number = "***" + request.test_recipient_number[-4:]
    simulation = bolna_service._simulate_demo_call(
        citizen_id=citizen.id,
        citizen_name="demo participant",
        trigger_event=request.trigger_event,
        phone_number=masked_number,
    )
    record = CallJobRecord(
        id=str(uuid.uuid4()),
        citizen_id=citizen.id,
        citizen_name="Synthetic demo profile",
        trigger_event=request.trigger_event,
        direction="outbound",
        job_status="COMPLETED",
        idempotency_key=idempotency_key,
        attempt_count=1,
        scheduled_at=datetime.now(timezone.utc),
        duration_seconds=0,
        is_real_call=False,
        recipient_phone=masked_number,
        bolna_execution_id=None,
        transcript_events=json.dumps(simulation.get("transcript_events", [])),
        created_at=datetime.now(timezone.utc),
    )
    db.add(record)
    db.commit()
    db.refresh(record)
    return _to_call_job_response(record)


@router.post("/approved-test", response_model=CallJobResponse, status_code=status.HTTP_201_CREATED)
async def create_approved_test_call(
    request: ApprovedTestCallRequest,
    http_request: Request,
    db: Session = Depends(get_db),
):
    """Place one locally approved test call; synthetic context only, no retries."""
    _require_local_client(http_request)
    if not settings.ENABLE_REAL_CALLS:
        raise HTTPException(status_code=403, detail="Live calls are disabled in backend/.env.")
    if not settings.BOLNA_TEST_AGENT_VERIFIED:
        raise HTTPException(
            status_code=403,
            detail="Review and mark the Bolna test agent ready in backend/.env before enabling a test call.",
        )
    if not bolna_service.is_configured():
        raise HTTPException(status_code=503, detail="Bolna API credentials and agent ID are not configured in backend/.env.")

    citizen = db.query(Citizen).filter(Citizen.id == request.citizen_id, Citizen.archived_at.is_(None)).first()
    if not citizen or not citizen.demo_only or not citizen.id.startswith("CIT-"):
        raise HTTPException(status_code=404, detail="Synthetic test profile not found.")

    # Record the attempt before dispatch so a client timeout/retry cannot erase
    # evidence that a request may already have reached the telephony provider.
    job_record = CallJobRecord(
        id=str(uuid.uuid4()),
        citizen_id=citizen.id,
        citizen_name="Consenting test recipient",
        trigger_event="MANUAL_APPROVED_TEST",
        direction="outbound",
        job_status="SUBMITTING",
        idempotency_key=f"approved-test-{uuid.uuid4()}",
        attempt_count=1,
        scheduled_at=datetime.now(timezone.utc),
        duration_seconds=0,
        is_real_call=True,
        recipient_phone=_mask_phone(request.test_recipient_number),
        bolna_execution_id=None,
        transcript_events="[]",
        created_at=datetime.now(timezone.utc),
    )
    db.add(job_record)
    db.commit()

    try:
        result = await bolna_service.initiate_approved_test_call(
            phone_number=request.test_recipient_number,
            language=request.language,
        )
    except BolnaProviderError as exc:
        job_record.job_status = "UNKNOWN" if exc.ambiguous else "FAILED"
        db.commit()
        raise HTTPException(status_code=exc.http_status, detail=str(exc)) from exc
    except (PermissionError, RuntimeError) as exc:
        job_record.job_status = "FAILED"
        db.commit()
        raise HTTPException(status_code=403, detail=str(exc)) from exc

    job_record.job_status = result.get("status", "QUEUED")
    job_record.bolna_execution_id = result.get("execution_id")
    job_record.attempt_count = 1
    db.commit()
    db.refresh(job_record)
    return _to_call_job_response(job_record)


def _to_call_job_response(job: CallJobRecord) -> CallJobResponse:
    events = []
    try:
        raw_events = json.loads(job.transcript_events)
        for ev in raw_events:
            events.append(CallEventSchema(**ev))
    except Exception:
        pass

    return CallJobResponse(
        id=job.id,
        citizen_id=job.citizen_id,
        citizen_name=job.citizen_name,
        trigger_event=job.trigger_event,
        direction=job.direction or "outbound",
        job_status=job.job_status,
        idempotency_key=job.idempotency_key,
        attempt_count=job.attempt_count,
        scheduled_at=job.scheduled_at.isoformat(),
        duration_seconds=job.duration_seconds,
        is_real_call=job.is_real_call,
        recipient_phone=job.recipient_phone,
        bolna_execution_id=job.bolna_execution_id,
        transcript_events=events
    )


@router.post("", response_model=CallJobResponse, status_code=status.HTTP_201_CREATED)
async def schedule_call(request: CallRequest, db: Session = Depends(get_db)):
    if request.is_real_call:
        raise HTTPException(
            status_code=403,
            detail="Live dialing is available only through the individually reviewed test-call flow.",
        )
    citizen = db.query(Citizen).filter(Citizen.id == request.citizen_id, Citizen.archived_at.is_(None)).first()
    if not citizen:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Citizen '{request.citizen_id}' not found.",
        )

    # Enforce Idempotency Key
    idempotency_key = f"call-{citizen.id}-{request.trigger_event}"
    existing_job = db.query(CallJobRecord).filter(
        CallJobRecord.idempotency_key == idempotency_key
    ).first()

    if existing_job:
        # Return HTTP 409 Conflict if active job already exists as specified by frontend contract
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Duplicate call job already exists (Idempotency Enforced).",
        )

    recipient_number = citizen.phone_number

    try:
        call_result = await bolna_service.initiate_call(
            citizen_id=citizen.id,
            citizen_name=citizen.name,
            phone_number=recipient_number,
            trigger_event=request.trigger_event,
            is_real_call_requested=False,
            consent_confirmed=False,
            user_data={},
        )
    except (ValueError, PermissionError) as e:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e))
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Phone-call provider request failed.",
        )

    job_id = str(uuid.uuid4())
    job_record = CallJobRecord(
        id=job_id,
        citizen_id=citizen.id,
        citizen_name=citizen.name,
        trigger_event=request.trigger_event,
        direction="outbound",
        job_status=call_result.get("status", "QUEUED"),
        idempotency_key=idempotency_key,
        attempt_count=1,
        scheduled_at=datetime.now(timezone.utc),
        duration_seconds=call_result.get("duration_seconds", 0),
        is_real_call=call_result.get("is_real_call", False),
        recipient_phone=_mask_phone(recipient_number),
        bolna_execution_id=call_result.get("execution_id"),
        transcript_events=json.dumps(call_result.get("transcript_events", [])),
        created_at=datetime.now(timezone.utc),
    )
    db.add(job_record)
    db.commit()
    db.refresh(job_record)

    return _to_call_job_response(job_record)


@router.get("", response_model=CallJobListResponse)
def list_call_jobs(
    citizen_id: Optional[str] = Query(None),
    limit: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db)
):
    query = db.query(CallJobRecord)
    if citizen_id:
        query = query.filter(CallJobRecord.citizen_id == citizen_id)
    records = query.order_by(CallJobRecord.scheduled_at.desc()).limit(limit).all()

    return CallJobListResponse(
        total=len(records),
        jobs=[_to_call_job_response(j) for j in records]
    )


@router.get("/inbound", response_model=CallJobListResponse)
def list_inbound_calls(
    limit: int = Query(20, ge=1, le=100),
    http_request: Request = None,
    db: Session = Depends(get_db),
):
    """Lists logged inbound calls with masked caller numbers and metadata privacy."""
    if http_request:
        _require_local_client(http_request)
    records = (
        db.query(CallJobRecord)
        .filter((CallJobRecord.direction == "inbound") | (CallJobRecord.trigger_event == "INBOUND_CALL"))
        .order_by(CallJobRecord.scheduled_at.desc())
        .limit(limit)
        .all()
    )
    return CallJobListResponse(
        total=len(records),
        jobs=[_to_call_job_response(j) for j in records],
    )


@router.get("/inbound/readiness")
async def get_inbound_readiness(
    http_request: Request = None,
):
    """
    Non-dialing preflight check inspecting all components required for inbound calling:
    1. Local FastAPI backend & public ngrok tunnel status
    2. Bolna Agent configuration & custom LLM base URL
    3. Webhook readiness & authentication secret
    4. FastEmbed RAG knowledge base & Nemotron API readiness
    5. Jio call forwarding guide
    6. Safety locks: ENABLE_REAL_CALLS=false and BOLNA_TEST_AGENT_VERIFIED=false
    """
    if http_request:
        _require_local_client(http_request)
    return await bolna_service.check_inbound_readiness()


@router.get("/inbound/forwarding-guide")
def get_jio_forwarding_guide(
    http_request: Request = None,
):
    """Returns verified Jio call forwarding instructions, USSD codes, and verification steps."""
    if http_request:
        _require_local_client(http_request)
    return bolna_service.get_jio_call_forwarding_instructions()


@router.get("/{call_id}", response_model=CallJobResponse)
def get_call_job(call_id: str, db: Session = Depends(get_db)):
    job = db.query(CallJobRecord).filter(CallJobRecord.id == call_id).first()
    if not job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Call job '{call_id}' not found.",
        )
    return _to_call_job_response(job)


def _translate_provider_status(status_value: str) -> str:
    status_map = {
        "QUEUED": "QUEUED",
        "SCHEDULED": "SCHEDULED",
        "RESCHEDULED": "QUEUED",
        "INITIATED": "IN_PROGRESS",
        "RINGING": "IN_PROGRESS",
        "IN_PROGRESS": "IN_PROGRESS",
        "CALL_DISCONNECTED": "FINALIZING",
        "COMPLETED": "COMPLETED",
        "NO_ANSWER": "FAILED",
        "BUSY": "FAILED",
        "FAILED": "FAILED",
        "CANCELED": "CANCELED",
        "STOPPED": "STOPPED",
        "ERROR": "FAILED",
        "BALANCE_LOW": "FAILED",
    }
    return status_map.get(status_value.upper().replace("-", "_"), "UNKNOWN")


@router.post("/{call_id}/refresh-status", response_model=CallJobResponse)
async def refresh_call_status(
    call_id: str,
    http_request: Request,
    db: Session = Depends(get_db),
):
    _require_local_client(http_request)
    job = db.query(CallJobRecord).filter(CallJobRecord.id == call_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Call job not found.")
    if not job.is_real_call or not job.bolna_execution_id:
        return _to_call_job_response(job)
    try:
        provider_status = await bolna_service.get_call_status(job.bolna_execution_id)
    except BolnaProviderError as exc:
        raise HTTPException(status_code=exc.http_status, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    job.job_status = _translate_provider_status(provider_status["status"])
    job.duration_seconds = provider_status.get("duration_seconds", job.duration_seconds)
    db.commit()
    db.refresh(job)
    return _to_call_job_response(job)


@router.post("/{call_id}/stop", response_model=CallJobResponse)
async def stop_queued_call(
    call_id: str,
    http_request: Request,
    db: Session = Depends(get_db),
):
    _require_local_client(http_request)
    job = db.query(CallJobRecord).filter(CallJobRecord.id == call_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Call job not found.")
    if not job.is_real_call or not job.bolna_execution_id:
        raise HTTPException(status_code=409, detail="Only a pending provider call can be canceled.")
    if job.job_status not in {"QUEUED", "SCHEDULED"}:
        raise HTTPException(
            status_code=409,
            detail="Bolna can cancel a queued or scheduled call only. This call may already be active; end it from the recipient phone or provider dashboard.",
        )
    try:
        await bolna_service.stop_queued_call(job.bolna_execution_id)
    except BolnaProviderError as exc:
        raise HTTPException(status_code=exc.http_status, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    job.job_status = "STOPPED"
    db.commit()
    db.refresh(job)
    return _to_call_job_response(job)
