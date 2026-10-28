import json
import logging
import uuid
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from app.database.session import get_db
from app.models.call_job import CallJobRecord
from app.schemas.call_job import BolnaWebhookPayload

logger = logging.getLogger("timbre.webhook")
router = APIRouter(prefix="/webhooks", tags=["Webhooks"])


@router.post("/bolna")
async def handle_bolna_webhook(payload: BolnaWebhookPayload, db: Session = Depends(get_db)):
    logger.info(f"Received Bolna webhook for execution {payload.id} with status {payload.status}")

    # Map Bolna status to internal status
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
        "canceled": "FAILED"
    }
    internal_status = status_map.get(payload.status.lower(), payload.status.upper())

    # Locate call job by execution ID or user_data
    job = db.query(CallJobRecord).filter(
        CallJobRecord.bolna_execution_id == payload.id
    ).first()

    if not job and payload.user_data:
        cid = payload.user_data.get("citizen_id")
        if cid:
            job = db.query(CallJobRecord).filter(
                CallJobRecord.citizen_id == cid
            ).order_by(CallJobRecord.scheduled_at.desc()).first()

    if job:
        job.job_status = internal_status
        if payload.call_duration is not None:
            job.duration_seconds = payload.call_duration
        
        # If transcript is delivered in webhook, append to transcript events
        if payload.transcript:
            events = []
            try:
                events = json.loads(job.transcript_events)
            except Exception:
                pass
            events.append({
                "id": str(uuid.uuid4()),
                "speaker": "AI_AGENT",
                "transcript_segment": payload.transcript,
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "latency_ms": 0
            })
            job.transcript_events = json.dumps(events)

        db.commit()
        return {"status": "processed", "job_id": job.id, "job_status": internal_status}

    return {"status": "received_unmatched", "execution_id": payload.id}
