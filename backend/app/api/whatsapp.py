"""FastAPI Router for WhatsApp Business Cloud API & Civic Conversation Simulator.

Handles:
- Meta Webhook Subscription Handshake (GET /webhooks/whatsapp)
- Incoming Meta Webhook Events (POST /webhooks/whatsapp)
- Local Demonstration & Simulation (POST /whatsapp/simulate)
- Preflight Readiness Audit (GET /whatsapp/readiness)
- Conversation History Inspection & Reset
"""
import json
import logging
from typing import Optional
from fastapi import APIRouter, Depends, Header, HTTPException, Query, Request, Response, status
from sqlalchemy.orm import Session

from app.database.session import get_db
from app.models.whatsapp import WhatsAppConversation, WhatsAppMessage
from app.schemas.whatsapp import (
    WhatsAppConversationDetail,
    WhatsAppMessageItem,
    WhatsAppSimulationRequest,
    WhatsAppSimulationResponse,
)
from app.services.messaging_provider import MessagingProviderError
from app.services.whatsapp_service import whatsapp_service

logger = logging.getLogger("timbre.whatsapp.api")
router = APIRouter(tags=["WhatsApp Messaging & Webhooks"])


@router.get("/webhooks/whatsapp")
@router.get("/whatsapp/webhook")
async def verify_whatsapp_webhook(
    hub_mode: Optional[str] = Query(None, alias="hub.mode"),
    hub_challenge: Optional[str] = Query(None, alias="hub.challenge"),
    hub_verify_token: Optional[str] = Query(None, alias="hub.verify_token"),
):
    """
    Handles Meta Webhook verification handshake:
    When Meta sends GET with hub.mode=subscribe and hub.verify_token,
    verifies the token against WHATSAPP_VERIFY_TOKEN and returns hub.challenge as plaintext.
    """
    challenge = whatsapp_service.verify_webhook_challenge(
        mode=hub_mode,
        token=hub_verify_token,
        challenge=hub_challenge,
    )
    if challenge:
        logger.info("WhatsApp webhook challenge verified successfully")
        return Response(content=challenge, media_type="text/plain", status_code=200)

    logger.warning("WhatsApp webhook verification failed: Token mismatch or invalid mode")
    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail="WhatsApp webhook verification token mismatch.",
    )


@router.post("/webhooks/whatsapp")
@router.post("/whatsapp/webhook")
async def receive_whatsapp_webhook(
    request: Request,
    db: Session = Depends(get_db),
    x_hub_signature: Optional[str] = Header(None, alias="X-Hub-Signature-256"),
    x_openwa_signature: Optional[str] = Header(None, alias="X-OpenWA-Signature"),
    x_openwa_event: Optional[str] = Header(None, alias="X-OpenWA-Event"),
):
    """
    Receives incoming WhatsApp events from OpenWA gateway or Meta Cloud API:
    Validates cryptographic signatures, parses user text messages, generates AI replies,
    and returns 200 OK promptly.
    """
    raw_body = await request.body()
    try:
        payload = json.loads(raw_body.decode("utf-8")) if raw_body else {}
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid JSON payload.")

    signature_header = (
        x_openwa_signature
        or x_hub_signature
        or request.headers.get("x-openwa-signature")
        or request.headers.get("x-hub-signature-256")
    )
    event_header = x_openwa_event or request.headers.get("x-openwa-event")

    try:
        result = await whatsapp_service.handle_incoming_webhook(
            db=db,
            payload=payload,
            raw_body=raw_body,
            signature_header=signature_header,
            event_header=event_header,
        )
        return {"status": "ok", "details": result}
    except MessagingProviderError as exc:
        raise HTTPException(status_code=exc.status_code, detail=str(exc)) from exc


@router.post("/whatsapp/simulate", response_model=WhatsAppSimulationResponse)
async def simulate_whatsapp_turn(
    request: WhatsAppSimulationRequest,
    db: Session = Depends(get_db),
):
    """
    Demonstration and local development route:
    Simulates a citizen sending a message to Timbre over WhatsApp.
    Executes the full conversational pipeline (RAG, rules engine, Nemotron, multi-turn context)
    without requiring live Meta credentials or sending external messages.
    """
    result = await whatsapp_service.simulate_turn(
        db=db,
        sender_phone=request.sender_phone,
        message=request.message,
        sender_name=request.sender_name,
        reset_conversation=request.reset_conversation,
        simulate_failure=request.simulate_provider_failure,
    )
    return WhatsAppSimulationResponse(**result)


@router.get("/whatsapp/readiness")
def get_whatsapp_readiness():
    """
    Performs a non-dialing, zero-cost readiness audit for the WhatsApp integration:
    Checks environment variables, webhook endpoints, and safety flags.
    """
    return whatsapp_service.check_readiness()


@router.get("/whatsapp/conversations/{wa_id}", response_model=WhatsAppConversationDetail)
def get_conversation_history(wa_id: str, db: Session = Depends(get_db)):
    """Retrieves conversation history and message logs for a given WhatsApp sender (wa_id)."""
    clean_wa_id = wa_id.lstrip("+").strip()
    conv = db.query(WhatsAppConversation).filter(WhatsAppConversation.wa_id == clean_wa_id).first()
    if not conv:
        raise HTTPException(status_code=404, detail="Conversation not found for this sender.")

    messages = (
        db.query(WhatsAppMessage)
        .filter(WhatsAppMessage.conversation_id == conv.id)
        .order_by(WhatsAppMessage.created_at.asc())
        .all()
    )

    return WhatsAppConversationDetail(
        conversation_id=conv.id,
        wa_id=conv.wa_id,
        phone_number_masked=conv.phone_number_masked,
        contact_name=conv.contact_name,
        language_preference=conv.language_preference,
        status=conv.status,
        last_message_at=conv.last_message_at.isoformat() if conv.last_message_at else None,
        messages=[
            WhatsAppMessageItem(
                id=m.id,
                direction=m.direction,
                content=m.content,
                delivery_status=m.delivery_status,
                created_at=m.created_at.isoformat(),
            )
            for m in messages
        ],
    )


@router.post("/whatsapp/conversations/{wa_id}/reset")
def reset_conversation(wa_id: str, db: Session = Depends(get_db)):
    """Clears conversation history for the specified sender to restart fresh testing."""
    clean_wa_id = wa_id.lstrip("+").strip()
    conv = db.query(WhatsAppConversation).filter(WhatsAppConversation.wa_id == clean_wa_id).first()
    if conv:
        db.query(WhatsAppMessage).filter(WhatsAppMessage.conversation_id == conv.id).delete()
        db.delete(conv)
        db.commit()
    return {"status": "reset_successful", "wa_id": clean_wa_id}
