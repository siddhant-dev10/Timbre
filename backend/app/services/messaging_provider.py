"""Messaging Provider Abstraction for Timbre WhatsApp Integration.

Decouples Timbre's civic assistance AI brain from the transport provider.
Provides:
1. BaseMessagingProvider: Standard messaging interface.
2. WhatsAppCloudProvider: Official WhatsApp Business Platform Cloud API (Meta Graph API).
3. MockWhatsAppProvider: In-memory simulation and testing provider for local development.
"""
from abc import ABC, abstractmethod
import hashlib
import hmac
import logging
from pathlib import Path
import re
import secrets
import time
import uuid
from typing import Any, Dict, List, Optional

import httpx

from app.config import settings

logger = logging.getLogger("timbre.messaging")


class MessagingProviderError(RuntimeError):
    """Raised when an external messaging provider rejects a request or times out."""

    def __init__(self, message: str, status_code: int = 502, provider: str = "whatsapp"):
        super().__init__(message)
        self.status_code = status_code
        self.provider = provider


class BaseMessagingProvider(ABC):
    """Abstract interface for messaging providers (WhatsApp, Simulator, etc.)."""

    @abstractmethod
    async def send_text_message(self, recipient_id: str, text: str) -> Dict[str, Any]:
        """Sends an outbound text message to the specified recipient."""
        pass

    @abstractmethod
    def verify_webhook_token(self, mode: str, token: str) -> bool:
        """Verifies the webhook subscription challenge token."""
        pass

    @abstractmethod
    def verify_payload_signature(self, raw_body: bytes, signature_header: Optional[str]) -> bool:
        """Validates cryptographic signature of incoming webhook payloads."""
        pass

    @abstractmethod
    def is_configured(self) -> bool:
        """Returns True if the provider has necessary credentials."""
        pass

    @property
    @abstractmethod
    def provider_name(self) -> str:
        """Returns provider name identifier."""
        pass


class WhatsAppCloudProvider(BaseMessagingProvider):
    """Official WhatsApp Business Cloud API integration via Meta Graph API."""

    def __init__(self):
        self.reload_config()

    def reload_config(self) -> None:
        self.base_url = settings.WHATSAPP_API_BASE_URL.rstrip("/")
        self.access_token = settings.WHATSAPP_ACCESS_TOKEN.strip()
        self.phone_number_id = settings.WHATSAPP_PHONE_NUMBER_ID.strip()
        self.verify_token = settings.WHATSAPP_VERIFY_TOKEN.strip()
        self.app_secret = settings.WHATSAPP_APP_SECRET.strip()
        self.timeout = settings.WHATSAPP_TIMEOUT_SECONDS

    @property
    def provider_name(self) -> str:
        return "whatsapp_cloud"

    def is_configured(self) -> bool:
        return bool(self.access_token and self.phone_number_id)

    def verify_webhook_token(self, mode: str, token: str) -> bool:
        """
        Validates WhatsApp Webhook verification handshake:
        mode must be 'subscribe' and token must match WHATSAPP_VERIFY_TOKEN.
        """
        if mode != "subscribe":
            return False
        expected_token = self.verify_token or "timbre_verify_token"
        return secrets.compare_digest(token.strip(), expected_token)

    def verify_payload_signature(self, raw_body: bytes, signature_header: Optional[str]) -> bool:
        """
        Validates the X-Hub-Signature-256 header using HMAC-SHA256 with WHATSAPP_APP_SECRET.
        Format: sha256=<hex_digest>
        """
        if not self.app_secret:
            # If app secret is not configured in local environment, allow pass-through with warning
            logger.debug("WHATSAPP_APP_SECRET not configured; skipping payload signature check.")
            return True

        if not signature_header or not signature_header.startswith("sha256="):
            logger.warning("Missing or malformed X-Hub-Signature-256 header")
            return False

        received_hash = signature_header[7:].strip()
        expected_hash = hmac.new(
            key=self.app_secret.encode("utf-8"),
            msg=raw_body,
            digestmod=hashlib.sha256,
        ).hexdigest()

        return secrets.compare_digest(received_hash, expected_hash)

    async def send_text_message(self, recipient_id: str, text: str) -> Dict[str, Any]:
        """
        Sends an outbound text message via POST https://graph.facebook.com/v21.0/{phone_number_id}/messages
        """
        if not self.is_configured():
            raise MessagingProviderError(
                "WhatsApp Cloud API credentials (WHATSAPP_ACCESS_TOKEN and WHATSAPP_PHONE_NUMBER_ID) are not configured.",
                status_code=503,
                provider=self.provider_name,
            )

        clean_recipient = recipient_id.lstrip("+").strip()
        url = f"{self.base_url}/{self.phone_number_id}/messages"
        headers = {
            "Authorization": f"Bearer {self.access_token}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        }
        payload = {
            "messaging_product": "whatsapp",
            "recipient_type": "individual",
            "to": clean_recipient,
            "type": "text",
            "text": {
                "preview_url": False,
                "body": text,
            },
        }

        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(url, headers=headers, json=payload)
        except httpx.TimeoutException as exc:
            logger.warning("WhatsApp API timeout when sending to ***%s", clean_recipient[-4:])
            raise MessagingProviderError(
                "WhatsApp API request timed out. Please retry.",
                status_code=504,
                provider=self.provider_name,
            ) from exc
        except httpx.RequestError as exc:
            logger.warning("WhatsApp network request failed: %s", type(exc).__name__)
            raise MessagingProviderError(
                "Could not reach WhatsApp Cloud API. Check network connectivity.",
                status_code=502,
                provider=self.provider_name,
            ) from exc

        if response.status_code not in (200, 201):
            logger.warning("WhatsApp API rejected message (HTTP %s)", response.status_code)
            error_msg = self._safe_error_message(response.status_code)
            raise MessagingProviderError(
                error_msg,
                status_code=response.status_code if response.status_code in (400, 401, 403, 429) else 502,
                provider=self.provider_name,
            )

        try:
            data = response.json()
            messages = data.get("messages", [])
            wamid = messages[0].get("id") if messages and isinstance(messages[0], dict) else None
            return {
                "success": True,
                "message_id": wamid,
                "recipient_id": clean_recipient,
                "status": "sent",
                "provider": self.provider_name,
            }
        except Exception:
            return {
                "success": True,
                "message_id": f"wamid.fallback.{uuid.uuid4().hex[:12]}",
                "recipient_id": clean_recipient,
                "status": "sent",
                "provider": self.provider_name,
            }

    @staticmethod
    def _safe_error_message(status_code: int) -> str:
        if status_code in (401, 403):
            return "WhatsApp Cloud API authentication failed. Verify WHATSAPP_ACCESS_TOKEN and account permissions."
        if status_code == 429:
            return "WhatsApp messaging rate limit reached. Please wait before retrying."
        if status_code == 400:
            return "WhatsApp API rejected message format or recipient number."
        return f"WhatsApp Cloud API returned an error (HTTP {status_code})."


class MockWhatsAppProvider(BaseMessagingProvider):
    """
    In-memory simulation provider for local development, automated testing, and demonstration.
    Does not require any live WhatsApp account or network access.
    """

    def __init__(self):
        self.sent_messages: List[Dict[str, Any]] = []
        self.simulate_failure: bool = False
        self.failure_status_code: int = 503

    @property
    def provider_name(self) -> str:
        return "mock"

    def is_configured(self) -> bool:
        return True

    def verify_webhook_token(self, mode: str, token: str) -> bool:
        if mode != "subscribe":
            return False
        expected = settings.WHATSAPP_VERIFY_TOKEN or "timbre_verify_token"
        return secrets.compare_digest(token.strip(), expected)

    def verify_payload_signature(self, raw_body: bytes, signature_header: Optional[str]) -> bool:
        if settings.WHATSAPP_APP_SECRET and signature_header:
            if not signature_header.startswith("sha256="):
                return False
            received_hash = signature_header[7:].strip()
            expected_hash = hmac.new(
                key=settings.WHATSAPP_APP_SECRET.encode("utf-8"),
                msg=raw_body,
                digestmod=hashlib.sha256,
            ).hexdigest()
            return secrets.compare_digest(received_hash, expected_hash)
        return True

    async def send_text_message(self, recipient_id: str, text: str) -> Dict[str, Any]:
        if self.simulate_failure:
            raise MessagingProviderError(
                f"Simulated WhatsApp API failure (HTTP {self.failure_status_code})",
                status_code=self.failure_status_code,
                provider=self.provider_name,
            )

        clean_recipient = recipient_id.lstrip("+").strip()
        msg_id = f"mock-wamid-{uuid.uuid4().hex[:12]}"
        entry = {
            "message_id": msg_id,
            "recipient_id": clean_recipient,
            "text": text,
            "timestamp": time.time(),
            "status": "simulated",
            "provider": self.provider_name,
        }
        self.sent_messages.append(entry)
        return {
            "success": True,
            "message_id": msg_id,
            "recipient_id": clean_recipient,
            "status": "simulated",
            "provider": self.provider_name,
        }

    def clear_history(self) -> None:
        self.sent_messages.clear()

    def get_sent_messages(self, recipient_id: Optional[str] = None) -> List[Dict[str, Any]]:
        if recipient_id:
            clean = recipient_id.lstrip("+").strip()
            return [m for m in self.sent_messages if m["recipient_id"] == clean]
        return list(self.sent_messages)


class OpenWAProvider(BaseMessagingProvider):
    """Local OpenWA Gateway integration via OpenWA REST API."""

    def __init__(self):
        self.reload_config()

    def reload_config(self) -> None:
        self.base_url = settings.OPENWA_BASE_URL.rstrip("/")
        self.api_key = settings.OPENWA_API_KEY.strip()
        self.session_id = settings.OPENWA_SESSION_ID.strip()
        self.webhook_secret = settings.OPENWA_WEBHOOK_SECRET.strip()
        self.timeout = settings.OPENWA_TIMEOUT_SECONDS
        self._resolved_session_uuid: Optional[str] = None

        # Safe local fallback: load API key from OpenWA data directory if unconfigured in .env
        if not self.api_key:
            for fallback_path in [
                Path("/Users/sidh._./OpenWA/data/.api-key"),
                Path.home() / "OpenWA/data/.api-key",
            ]:
                if fallback_path.is_file():
                    try:
                        self.api_key = fallback_path.read_text().strip()
                        break
                    except Exception:
                        pass

    @property
    def provider_name(self) -> str:
        return "openwa"

    def is_configured(self) -> bool:
        """Returns True if the OpenWA gateway has a base URL and an identified session or API key."""
        return bool(self.base_url and (self.api_key or self.session_id))

    def set_active_session_id(self, session_id: str) -> None:
        """Dynamically caches the active session UUID (e.g. from incoming webhook payload)."""
        if session_id:
            self._resolved_session_uuid = session_id.strip()

    def verify_webhook_token(self, mode: str, token: str) -> bool:
        """OpenWA does not use Meta's GET challenge handshake."""
        return False

    def verify_payload_signature(self, raw_body: bytes, signature_header: Optional[str]) -> bool:
        """
        Validates X-OpenWA-Signature header using HMAC-SHA256 with OPENWA_WEBHOOK_SECRET.
        Format: sha256=<hex_digest>
        """
        if not self.webhook_secret:
            logger.debug("OPENWA_WEBHOOK_SECRET not configured; skipping payload signature check.")
            return True

        if not signature_header or not signature_header.startswith("sha256="):
            logger.warning("Missing or malformed X-OpenWA-Signature header")
            return False

        received_hash = signature_header[7:].strip()
        expected_hash = hmac.new(
            key=self.webhook_secret.encode("utf-8"),
            msg=raw_body,
            digestmod=hashlib.sha256,
        ).hexdigest()

        return secrets.compare_digest(received_hash, expected_hash)

    def _normalize_chat_id(self, recipient_id: str) -> str:
        """Normalizes a recipient identifier into OpenWA's expected chatId format (e.g. phone@c.us)."""
        cleaned = recipient_id.strip()
        if "@" in cleaned:
            if cleaned.endswith("@s.whatsapp.net"):
                return cleaned.replace("@s.whatsapp.net", "@c.us")
            return cleaned
        digits = re.sub(r"\D", "", cleaned)
        return f"{digits}@c.us"

    async def resolve_session_id(self, client: Optional[httpx.AsyncClient] = None) -> str:
        """
        Resolves the UUID for the target session.
        If session_id is already a UUID or was cached from an incoming webhook, returns it directly.
        Otherwise, queries GET /api/sessions to map session name (e.g. 'timbre') to UUID.
        """
        if self._resolved_session_uuid:
            return self._resolved_session_uuid

        raw_id = self.session_id or "timbre"
        try:
            uuid.UUID(raw_id)
            self._resolved_session_uuid = raw_id
            return raw_id
        except ValueError:
            pass

        # Query OpenWA sessions list to resolve by name
        headers: Dict[str, str] = {}
        if self.api_key:
            headers["X-API-Key"] = self.api_key

        url = f"{self.base_url}/api/sessions"
        close_client = False
        active_client = client
        if active_client is None:
            active_client = httpx.AsyncClient(timeout=self.timeout)
            close_client = True

        try:
            resp = await active_client.get(url, headers=headers)
            if resp.status_code == 200:
                sessions = resp.json()
                if isinstance(sessions, list):
                    for s in sessions:
                        if s.get("name") == raw_id:
                            self._resolved_session_uuid = s.get("id")
                            return self._resolved_session_uuid
                    if sessions and "id" in sessions[0]:
                        self._resolved_session_uuid = sessions[0]["id"]
                        return self._resolved_session_uuid
        except Exception as exc:
            logger.warning("Could not query OpenWA sessions list: %s", exc)
        finally:
            if close_client and active_client:
                await active_client.aclose()

        return raw_id

    async def send_text_message(self, recipient_id: str, text: str) -> Dict[str, Any]:
        """
        Sends an outbound message via POST /api/sessions/{sessionId}/messages/send-text
        """
        chat_id = self._normalize_chat_id(recipient_id)

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            session_uuid = await self.resolve_session_id(client)
            url = f"{self.base_url}/api/sessions/{session_uuid}/messages/send-text"
            idempotency_key = f"timbre-send-{uuid.uuid4()}"
            headers: Dict[str, str] = {
                "Content-Type": "application/json",
                "Idempotency-Key": idempotency_key,
            }
            if self.api_key:
                headers["X-API-Key"] = self.api_key

            payload = {
                "chatId": chat_id,
                "text": text,
            }

            try:
                response = await client.post(url, headers=headers, json=payload)
            except httpx.TimeoutException as exc:
                logger.warning("OpenWA API timeout when sending to %s", self._mask_phone(chat_id))
                raise MessagingProviderError(
                    "OpenWA gateway request timed out. Please retry.",
                    status_code=504,
                    provider=self.provider_name,
                ) from exc
            except httpx.RequestError as exc:
                logger.warning("OpenWA network request failed: %s", type(exc).__name__)
                raise MessagingProviderError(
                    f"Could not reach OpenWA gateway at {self.base_url}.",
                    status_code=502,
                    provider=self.provider_name,
                ) from exc

        if response.status_code not in (200, 201):
            logger.warning("OpenWA API rejected send-text (HTTP %s): %s", response.status_code, response.text[:200])
            error_msg = self._safe_error_message(response.status_code)
            raise MessagingProviderError(
                error_msg,
                status_code=response.status_code if response.status_code in (400, 401, 403, 404, 409, 429) else 502,
                provider=self.provider_name,
            )

        try:
            data = response.json() if response.content else {}
            msg_id = data.get("id") or data.get("messageId") or f"openwa.{uuid.uuid4().hex[:12]}"
            return {
                "success": True,
                "message_id": msg_id,
                "recipient_id": chat_id,
                "status": "sent",
                "provider": self.provider_name,
            }
        except Exception:
            return {
                "success": True,
                "message_id": f"openwa.{uuid.uuid4().hex[:12]}",
                "recipient_id": chat_id,
                "status": "sent",
                "provider": self.provider_name,
            }

    @staticmethod
    def _mask_phone(phone: Optional[str]) -> str:
        if not phone:
            return "***0000"
        digits = re.sub(r"\D", "", phone)
        return "***" + digits[-4:] if len(digits) >= 4 else "***"

    @staticmethod
    def _safe_error_message(status_code: int) -> str:
        if status_code == 409:
            return "OpenWA session is not connected. The WhatsApp client is not ready. Please link your WhatsApp in the OpenWA dashboard."
        if status_code in (401, 403):
            return "OpenWA authentication failed. Verify OPENWA_API_KEY in backend/.env."
        if status_code == 404:
            return "OpenWA session not found or route unavailable."
        if status_code == 400:
            return "OpenWA rejected the message or recipient format."
        if status_code == 429:
            return "OpenWA messaging rate limit reached."
        return f"OpenWA gateway returned an error (HTTP {status_code})."
