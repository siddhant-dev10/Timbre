import json
import uuid
from datetime import datetime, timezone
from typing import Optional, List
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session
from app.database.session import get_db
from app.models.citizen import Citizen
from app.models.call_job import CallJobRecord
from app.schemas.call_job import (
    CallRequest,
    CallJobResponse,
    CallEventSchema,
    CallJobListResponse
)
from app.services.bolna_service import bolna_service
from app.config import settings

router = APIRouter(prefix="/calls", tags=["Voice Calls & Audio Telemetry"])


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
    citizen = db.query(Citizen).filter(Citizen.id == request.citizen_id).first()
    if not citizen:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Citizen '{request.citizen_id}' not found."
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
            detail="Duplicate call job already exists (Idempotency Enforced)."
        )

    recipient_number = (
        request.consented_phone_number
        if request.is_real_call
        else citizen.phone_number
    )

    try:
        call_result = await bolna_service.initiate_call(
            citizen_id=citizen.id,
            citizen_name=citizen.name,
            phone_number=recipient_number,
            trigger_event=request.trigger_event,
            is_real_call_requested=request.is_real_call,
            consent_confirmed=request.consent_confirmed,
            user_data={
                "citizen_id": citizen.id,
                "state": citizen.state,
                "preferred_language": citizen.preferred_language
            }
        )
    except (ValueError, PermissionError) as e:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))

    job_id = str(uuid.uuid4())
    job_record = CallJobRecord(
        id=job_id,
        citizen_id=citizen.id,
        citizen_name=citizen.name,
        trigger_event=request.trigger_event,
        job_status=call_result.get("status", "QUEUED"),
        idempotency_key=idempotency_key,
        attempt_count=1,
        scheduled_at=datetime.now(timezone.utc),
        duration_seconds=call_result.get("duration_seconds", 0),
        is_real_call=call_result.get("is_real_call", False),
        recipient_phone=recipient_number,
        bolna_execution_id=call_result.get("execution_id"),
        transcript_events=json.dumps(call_result.get("transcript_events", [])),
        created_at=datetime.now(timezone.utc)
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


@router.get("/{call_id}", response_model=CallJobResponse)
def get_call_job(call_id: str, db: Session = Depends(get_db)):
    job = db.query(CallJobRecord).filter(CallJobRecord.id == call_id).first()
    if not job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Call job '{call_id}' not found."
        )
    return _to_call_job_response(job)
