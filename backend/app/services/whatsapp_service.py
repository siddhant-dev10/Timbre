"""WhatsApp Business Service Coordinator for Timbre.

Coordinates:
- Webhook subscription challenges and cryptographic signature verification.
- Inbound payload parsing and deduplication (wamid).
- Isolated multi-turn conversation session tracking in SQLite.
- Forwarding user messages to the WhatsAppCivicAgent.
- Outbound reply delivery via WhatsAppCloudProvider or MockWhatsAppProvider.
- Phone number privacy masking in logs and persistence.
- Zero-external-dependency local simulation and audit.
"""
import json
import logging
import re
import time
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple
from sqlalchemy.orm import Session

from app.config import settings
from app.models.whatsapp import WhatsAppConversation, WhatsAppMessage
from app.services.messaging_provider import (
    BaseMessagingProvider,
    MessagingProviderError,
    MockWhatsAppProvider,
    OpenWAProvider,
    WhatsAppCloudProvider,
)
from app.services.whatsapp_agent import whatsapp_agent

logger = logging.getLogger("timbre.whatsapp.service")


def _mask_phone(phone: Optional[str]) -> str:
    """Masks a phone number or wa_id for privacy compliance (e.g. 919876543210 -> ***3210)."""
    if not phone:
        return "***0000"
    digits = re.sub(r"\D", "", phone)
    return "***" + digits[-4:] if len(digits) >= 4 else "***"


class WhatsAppService:
    """High-level service coordinating WhatsApp webhook events, database persistence, and AI responses."""

    def __init__(self):
        self.cloud_provider = WhatsAppCloudProvider()
        self.openwa_provider = OpenWAProvider()
        self.mock_provider = MockWhatsAppProvider()
        # In-memory replay cache: wamid -> timestamp
        self._processed_wamids: Dict[str, float] = {}
        self._MAX_WAMID_CACHE = 1000

    def reload_config(self, reload_env: bool = False) -> None:
        import os
        if reload_env and "PYTEST_CURRENT_TEST" not in os.environ:
            settings.reload_from_env()
        self.cloud_provider.reload_config()
        self.openwa_provider.reload_config()

    def get_provider(self, force_mock: bool = False) -> BaseMessagingProvider:
        """Returns the active provider. Uses OpenWA or WhatsAppCloudProvider if configured and not in simulation."""
        if force_mock:
            return self.mock_provider
        if self.openwa_provider.is_configured():
            return self.openwa_provider
        if self.cloud_provider.is_configured():
            return self.cloud_provider
        return self.mock_provider

    def verify_webhook_challenge(self, mode: Optional[str], token: Optional[str], challenge: Optional[str]) -> Optional[str]:
        """Validates the GET /webhook challenge for Meta Webhook subscription."""
        if not mode or not token:
            return None
        provider = self.cloud_provider if self.cloud_provider.is_configured() else self.mock_provider
        if provider.verify_webhook_token(mode, token):
            return challenge
        return None

    def verify_signature(self, raw_body: bytes, signature_header: Optional[str]) -> bool:
        """Validates the X-Hub-Signature-256 header using the active provider."""
        return self.get_provider().verify_payload_signature(raw_body, signature_header)

    async def handle_incoming_webhook(
        self,
        db: Session,
        payload: Dict[str, Any],
        raw_body: bytes,
        signature_header: Optional[str] = None,
        event_header: Optional[str] = None,
        force_mock: bool = False,
    ) -> Dict[str, Any]:
        """
        Parses incoming WhatsApp webhook events from either OpenWA gateway or Meta Cloud API,
        performs signature validation and deduplication, processes citizen messages,
        generates grounded AI answers, and delivers replies.
        """
        is_openwa = (
            "event" in payload
            or event_header is not None
            or "sessionId" in payload
            or (signature_header and "sha256=" in signature_header and "entry" not in payload)
            or ("data" in payload and isinstance(payload.get("data"), dict) and "entry" not in payload)
        )

        if is_openwa:
            return await self._handle_openwa_webhook(
                db=db,
                payload=payload,
                raw_body=raw_body,
                signature_header=signature_header,
                force_mock=force_mock,
            )

        return await self._handle_meta_webhook(
            db=db,
            payload=payload,
            raw_body=raw_body,
            signature_header=signature_header,
            force_mock=force_mock,
        )

    async def _handle_openwa_webhook(
        self,
        db: Session,
        payload: Dict[str, Any],
        raw_body: bytes,
        signature_header: Optional[str] = None,
        force_mock: bool = False,
    ) -> Dict[str, Any]:
        """Handles incoming events dispatched by the OpenWA WhatsApp gateway."""
        provider = self.mock_provider if force_mock else self.openwa_provider

        # 1. Cryptographic Signature Check (if secret is configured)
        if not provider.verify_payload_signature(raw_body, signature_header):
            logger.warning("Rejected OpenWA webhook submission: Invalid HMAC-SHA256 signature")
            raise MessagingProviderError("Invalid payload signature.", status_code=401, provider=provider.provider_name)

        event = payload.get("event") or ""
        session_id = payload.get("sessionId") or ""

        # 2. Handle 'test' probe events from OpenWA dashboard
        if event == "test":
            logger.info("Acknowledged OpenWA test webhook event for session %s", session_id)
            return {"status": "test_acknowledged", "sessionId": session_id}

        # 3. Filter non-message events
        if event != "message.received":
            logger.debug("Ignored non-message OpenWA event: %s", event)
            return {"status": "ignored_non_message_event", "event": event}

        # 4. Extract data payload
        data = payload.get("data")
        if not data or not isinstance(data, dict):
            logger.debug("Ignored OpenWA message with empty data payload")
            return {"status": "ignored_empty_data"}

        # 5. Filter outgoing messages (echoes of assistant replies or operator sends)
        if data.get("fromMe") is True or data.get("direction") == "outgoing":
            logger.debug("Ignored outgoing OpenWA message (fromMe=True)")
            return {"status": "ignored_outgoing_message"}

        # 6. Filter status broadcasts
        chat_id = str(data.get("chatId") or data.get("from") or "").strip()
        from_id = str(data.get("from") or "").strip()
        msg_type = str(data.get("type") or "chat")
        if (
            data.get("isStatusBroadcast") is True
            or chat_id == "status@broadcast"
            or from_id == "status@broadcast"
            or msg_type == "status"
        ):
            logger.debug("Ignored WhatsApp status broadcast")
            return {"status": "ignored_status_broadcast"}

        # 7. Filter group messages (civic assistance is private 1-on-1)
        if data.get("isGroup") is True or chat_id.endswith("@g.us") or from_id.endswith("@g.us"):
            logger.info("Ignored group WhatsApp message from %s (groups unsupported in 1-on-1 assistant)", _mask_phone(chat_id))
            return {"status": "ignored_group_message"}

        # 8. Filter non-usable text
        body = data.get("body") or data.get("text") or ""
        if not isinstance(body, str) or not body.strip():
            logger.info("Ignored OpenWA message without usable text (type: %s)", msg_type)
            return {"status": "ignored_no_usable_text"}

        user_text = body.strip()

        # 9. Deduplication check
        msg_id = data.get("id") or payload.get("idempotencyKey") or payload.get("deliveryId")
        if msg_id:
            if msg_id in self._processed_wamids:
                logger.info("Ignoring duplicate OpenWA delivery for msg_id %s", msg_id[:16])
                return {"status": "duplicate_ignored", "wamid": msg_id}

            existing_msg = db.query(WhatsAppMessage).filter(WhatsAppMessage.wamid == msg_id).first()
            if existing_msg:
                logger.info("Duplicate msg_id %s found in database; ignoring.", msg_id[:16])
                return {"status": "duplicate_ignored", "wamid": msg_id}

            if len(self._processed_wamids) >= self._MAX_WAMID_CACHE:
                self._processed_wamids.pop(next(iter(self._processed_wamids)))
            self._processed_wamids[msg_id] = time.time()

        # 10. Extract sender information
        sender_name = data.get("pushName") or data.get("senderName") or data.get("notifyName")

        if session_id and hasattr(provider, "set_active_session_id"):
            provider.set_active_session_id(session_id)

        # 11. Run citizen conversational turn
        turn_result = await self._process_citizen_turn(
            db=db,
            sender_wa_id=chat_id,
            user_text=user_text,
            wamid=msg_id,
            sender_name=sender_name,
            provider=provider,
        )

        return {
            "status": "processed",
            "provider": provider.provider_name,
            "turn": turn_result,
        }

    async def _handle_meta_webhook(
        self,
        db: Session,
        payload: Dict[str, Any],
        raw_body: bytes,
        signature_header: Optional[str] = None,
        force_mock: bool = False,
    ) -> Dict[str, Any]:
        """Handles incoming webhook submissions from Meta WhatsApp Cloud API."""
        # 1. Cryptographic Signature Validation
        provider = self.mock_provider if force_mock else (
            self.cloud_provider if self.cloud_provider.is_configured() else self.mock_provider
        )
        if not provider.verify_payload_signature(raw_body, signature_header):
            logger.warning("Rejected WhatsApp webhook submission: Invalid HMAC-SHA256 signature")
            raise MessagingProviderError("Invalid payload signature.", status_code=401, provider=provider.provider_name)

        # 2. Extract entries and changes
        entries = payload.get("entry", [])
        if not entries or not isinstance(entries, list):
            return {"status": "ignored_empty_entry"}

        processed_count = 0
        results = []

        for entry in entries:
            changes = entry.get("changes", [])
            for change in changes:
                value = change.get("value", {})
                if not value or not isinstance(value, dict):
                    continue

                # Ignore status receipts (sent, delivered, read) gracefully
                if "statuses" in value and "messages" not in value:
                    logger.debug("Acknowledged WhatsApp delivery status receipt")
                    return {"status": "status_acknowledged"}

                messages = value.get("messages", [])
                contacts = value.get("contacts", [])
                contact_map = {}
                for c in contacts:
                    if isinstance(c, dict) and "wa_id" in c:
                        contact_map[c["wa_id"]] = c.get("profile", {}).get("name")

                for msg in messages:
                    if not isinstance(msg, dict):
                        continue
                    wamid = msg.get("id")
                    sender_wa_id = msg.get("from")
                    if not sender_wa_id:
                        continue

                    sender_name = contact_map.get(sender_wa_id)

                    # 3. Deduplication check
                    if wamid:
                        if wamid in self._processed_wamids:
                            logger.info("Ignoring duplicate WhatsApp delivery for wamid %s", wamid[:12])
                            return {"status": "duplicate_ignored", "wamid": wamid}
                        # Also check database uniqueness
                        existing_msg = db.query(WhatsAppMessage).filter(WhatsAppMessage.wamid == wamid).first()
                        if existing_msg:
                            logger.info("Duplicate wamid %s found in database; ignoring.", wamid[:12])
                            return {"status": "duplicate_ignored", "wamid": wamid}

                        # Add to in-memory cache
                        if len(self._processed_wamids) >= self._MAX_WAMID_CACHE:
                            self._processed_wamids.pop(next(iter(self._processed_wamids)))
                        self._processed_wamids[wamid] = time.time()

                    # 4. Extract message text
                    msg_type = msg.get("type", "text")
                    if msg_type == "text":
                        user_text = msg.get("text", {}).get("body", "").strip()
                    else:
                        user_text = "[Non-text message received. Please send text inquiries.]"

                    turn_result = await self._process_citizen_turn(
                        db=db,
                        sender_wa_id=sender_wa_id,
                        user_text=user_text,
                        wamid=wamid,
                        sender_name=sender_name,
                        provider=provider,
                    )
                    results.append(turn_result)
                    processed_count += 1

        return {
            "status": "processed",
            "messages_handled": processed_count,
            "turns": results,
        }

    async def _process_citizen_turn(
        self,
        db: Session,
        sender_wa_id: str,
        user_text: str,
        wamid: Optional[str],
        sender_name: Optional[str],
        provider: BaseMessagingProvider,
        simulate_failure: bool = False,
    ) -> Dict[str, Any]:
        """
        Executes an isolated multi-turn citizen dialogue step:
        - Loads or creates WhatsAppConversation
        - Stores inbound WhatsAppMessage
        - Generates conversational response via WhatsAppCivicAgent
        - Dispatches reply via provider
        - Stores outbound WhatsAppMessage
        """
        # Clean wa_id digits for conversation storage, but preserve original sender_wa_id for reply
        clean_wa_id = re.sub(r"\D", "", sender_wa_id) or sender_wa_id
        masked_phone = _mask_phone(clean_wa_id)
        logger.info("Processing WhatsApp turn for sender %s (wamid: %s)", masked_phone, (wamid or "")[:8])

        # 1. Retrieve or create isolated conversation record
        conv = db.query(WhatsAppConversation).filter(WhatsAppConversation.wa_id == clean_wa_id).first()
        if not conv:
            conv = WhatsAppConversation(
                id=str(uuid.uuid4()),
                wa_id=clean_wa_id,
                phone_number_masked=masked_phone,
                contact_name=sender_name,
                language_preference="Hinglish",
                status="ACTIVE",
            )
            db.add(conv)
            db.flush()
        else:
            if sender_name and not conv.contact_name:
                conv.contact_name = sender_name

        # 2. Record incoming message
        inbound_msg = WhatsAppMessage(
            id=str(uuid.uuid4()),
            conversation_id=conv.id,
            wa_id=clean_wa_id,
            wamid=wamid,
            direction="inbound",
            message_type="text",
            content=user_text,
            delivery_status="received",
            meta_json=json.dumps({"sender_name": sender_name, "raw_sender_id": sender_wa_id}),
        )
        db.add(inbound_msg)
        db.flush()

        # 3. Load recent conversation history for isolated multi-turn context
        past_messages = (
            db.query(WhatsAppMessage)
            .filter(WhatsAppMessage.conversation_id == conv.id)
            .order_by(WhatsAppMessage.created_at.asc())
            .all()
        )
        history_for_llm: List[Dict[str, str]] = []
        for pm in past_messages[:-1]:  # Exclude current inbound
            role = "user" if pm.direction == "inbound" else "assistant"
            history_for_llm.append({"role": role, "text": pm.content})

        # 4. Generate AI response via WhatsAppCivicAgent
        agent_result = await whatsapp_agent.generate_reply(
            db=db,
            user_message=user_text,
            conversation_history=history_for_llm[-8:],
            sender_name=sender_name or conv.contact_name,
            conversation_id=conv.id,
        )
        ai_reply = agent_result["reply"]
        lang = agent_result["language"]
        conv.language_preference = lang

        # 5. Deliver outbound reply via active messaging provider
        outbound_delivery_status = "sent"
        outbound_wamid = None
        delivery_error = None

        if isinstance(provider, MockWhatsAppProvider) and simulate_failure:
            provider.simulate_failure = True

        try:
            send_res = await provider.send_text_message(recipient_id=sender_wa_id, text=ai_reply)
            outbound_wamid = send_res.get("message_id")
            outbound_delivery_status = send_res.get("status", "sent")
        except MessagingProviderError as exc:
            logger.warning("Failed to deliver WhatsApp message to %s: %s", masked_phone, exc)
            outbound_delivery_status = "failed"
            delivery_error = str(exc)
        finally:
            if isinstance(provider, MockWhatsAppProvider):
                provider.simulate_failure = False

        # 6. Record outbound message in database
        outbound_msg = WhatsAppMessage(
            id=str(uuid.uuid4()),
            conversation_id=conv.id,
            wa_id=clean_wa_id,
            wamid=outbound_wamid,
            direction="outbound",
            message_type="text",
            content=ai_reply,
            delivery_status=outbound_delivery_status,
            meta_json=json.dumps({
                "language": lang,
                "grounded_sources": agent_result.get("grounded_sources", []),
                "error": delivery_error,
                "provider": provider.provider_name,
            }),
        )
        db.add(outbound_msg)

        conv.last_message_at = datetime.now(timezone.utc)
        db.commit()
        db.refresh(conv)

        return {
            "conversation_id": conv.id,
            "wa_id": clean_wa_id,
            "sender_phone_masked": masked_phone,
            "user_message": user_text,
            "ai_reply": ai_reply,
            "language": lang,
            "grounded_sources": agent_result.get("grounded_sources", []),
            "delivery_status": outbound_delivery_status,
            "provider": provider.provider_name,
            "error": delivery_error,
        }

    async def simulate_turn(
        self,
        db: Session,
        sender_phone: str,
        message: str,
        sender_name: Optional[str] = None,
        reset_conversation: bool = False,
        simulate_failure: bool = False,
    ) -> Dict[str, Any]:
        """
        Runs a complete demonstration turn in simulation mode.
        Does not send real messages to anyone, guaranteeing complete isolation and safety.
        """
        clean_sender = re.sub(r"\D", "", sender_phone)
        if not clean_sender:
            clean_sender = "919876543210"

        if reset_conversation:
            # Clean past simulation history for this sender
            existing_conv = db.query(WhatsAppConversation).filter(WhatsAppConversation.wa_id == clean_sender).first()
            if existing_conv:
                db.query(WhatsAppMessage).filter(WhatsAppMessage.conversation_id == existing_conv.id).delete()
                db.delete(existing_conv)
                db.commit()

        mock_wamid = f"wamid.sim.{uuid.uuid4().hex[:12]}"
        provider = self.get_provider(force_mock=True)

        return await self._process_citizen_turn(
            db=db,
            sender_wa_id=clean_sender,
            user_text=message.strip(),
            wamid=mock_wamid,
            sender_name=sender_name or "Demo Citizen",
            provider=provider,
            simulate_failure=simulate_failure,
        )

    def check_readiness(self) -> Dict[str, Any]:
        """Performs a lightweight, zero-cost readiness audit for the WhatsApp integration."""
        self.reload_config(reload_env=True)
        openwa_ready = self.openwa_provider.is_configured()
        cloud_ready = self.cloud_provider.is_configured()

        provider_mode = "simulation_fallback"
        if openwa_ready:
            provider_mode = "openwa"
        elif cloud_ready:
            provider_mode = "whatsapp_cloud"

        return {
            "status": "ready" if (openwa_ready or cloud_ready) else "credentials_pending",
            "provider_mode": provider_mode,
            "openwa_configured": openwa_ready,
            "openwa_base_url": settings.OPENWA_BASE_URL,
            "openwa_session_id_set": bool(settings.OPENWA_SESSION_ID.strip()),
            "openwa_api_key_set": bool(self.openwa_provider.api_key),
            "openwa_webhook_secret_set": bool(settings.OPENWA_WEBHOOK_SECRET.strip()),
            "whatsapp_cloud_configured": cloud_ready,
            "phone_number_id_set": bool(settings.WHATSAPP_PHONE_NUMBER_ID.strip()),
            "access_token_set": bool(settings.WHATSAPP_ACCESS_TOKEN.strip()),
            "verify_token_set": bool(settings.WHATSAPP_VERIFY_TOKEN.strip()),
            "app_secret_set": bool(settings.WHATSAPP_APP_SECRET.strip()),
            "webhook_endpoint": "/api/webhooks/whatsapp",
            "simulation_endpoint": "/api/whatsapp/simulate",
            "safety_invariants": {
                "ENABLE_REAL_CALLS": settings.ENABLE_REAL_CALLS,
                "BOLNA_TEST_AGENT_VERIFIED": settings.BOLNA_TEST_AGENT_VERIFIED,
                "outbound_phone_dialing_prevented": True,
            },
            "setup_instructions": (
                "OpenWA gateway is active."
                if openwa_ready
                else "WhatsApp Cloud API is ready."
                if cloud_ready
                else "WhatsApp credentials not configured. Timbre is running with MockWhatsAppProvider for safe local simulation."
            ),
        }


whatsapp_service = WhatsAppService()
