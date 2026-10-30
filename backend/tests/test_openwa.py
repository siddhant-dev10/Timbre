"""Comprehensive Automated Test Suite for OpenWA WhatsApp Gateway Integration with Timbre.

Tests:
1. OpenWA Webhook Signature Verification (HMAC-SHA256 valid, invalid, missing).
2. OpenWA Dashboard Test Probe Acknowledgement (event: 'test').
3. Inbound Citizen Message Processing and Outbound OpenWA Send.
4. Outgoing Message Echo Filtering (fromMe: true, direction: 'outgoing').
5. Status Broadcast Filtering (isStatusBroadcast: true, status@broadcast).
6. Group Message Filtering (isGroup: true, @g.us).
7. Non-Text and Empty Message Filtering.
8. Message Deduplication by ID (in-memory and database level).
9. Provider Failure Handling (e.g. OpenWA HTTP 409 'qr_ready' / not connected).
10. Dynamic Session Name-to-UUID Resolution.
11. Readiness Audit Reporting for OpenWA.
12. Telephony Safety Invariant Preservation.
"""
import hashlib
import hmac
import json
from unittest.mock import AsyncMock, MagicMock, patch
import pytest

from app.config import settings
from app.models.whatsapp import WhatsAppConversation, WhatsAppMessage
from app.services.messaging_provider import MessagingProviderError, OpenWAProvider
from app.services.whatsapp_service import whatsapp_service

TEST_OPENWA_SECRET = "test-openwa-webhook-secret-999"
TEST_OPENWA_KEY = "test-openwa-api-key-abc"
TEST_SESSION_UUID = "ed741830-3751-45ae-81b1-41d6ad72d9dc"


@pytest.fixture(autouse=True)
def configure_openwa_test_env(monkeypatch):
    """Configures clean test environment with mocked OpenWA settings."""
    monkeypatch.setattr(settings, "OPENWA_BASE_URL", "http://localhost:2785")
    monkeypatch.setattr(settings, "OPENWA_API_KEY", TEST_OPENWA_KEY)
    monkeypatch.setattr(settings, "OPENWA_SESSION_ID", "timbre")
    monkeypatch.setattr(settings, "OPENWA_WEBHOOK_SECRET", TEST_OPENWA_SECRET)
    monkeypatch.setattr(settings, "NVIDIA_API_KEY", "")
    monkeypatch.setattr(settings, "ENABLE_REAL_CALLS", False)
    monkeypatch.setattr(settings, "BOLNA_TEST_AGENT_VERIFIED", False)
    whatsapp_service.reload_config()


def _compute_openwa_sig(raw_bytes: bytes, secret: str = TEST_OPENWA_SECRET) -> str:
    digest = hmac.new(secret.encode("utf-8"), raw_bytes, hashlib.sha256).hexdigest()
    return f"sha256={digest}"


def test_openwa_test_event_acknowledged(client):
    """OpenWA dashboard test probe (event: 'test') is acknowledged with HTTP 200."""
    payload = {
        "event": "test",
        "timestamp": "2026-10-31T01:00:00.000Z",
        "sessionId": TEST_SESSION_UUID,
        "idempotencyKey": "test_delivery_123",
        "deliveryId": "del_123",
        "data": {
            "message": "This is a test webhook from OpenWA",
            "webhookId": "wh_test_01",
            "url": "https://test.ngrok.dev/api/webhooks/whatsapp",
        },
    }
    raw_bytes = json.dumps(payload).encode("utf-8")
    sig = _compute_openwa_sig(raw_bytes)

    res = client.post(
        "/api/webhooks/whatsapp",
        content=raw_bytes,
        headers={"Content-Type": "application/json", "X-OpenWA-Signature": sig},
    )
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "ok"
    assert data["details"]["status"] == "test_acknowledged"
    assert data["details"]["sessionId"] == TEST_SESSION_UUID


def test_openwa_signature_verification_valid_and_invalid(client):
    """POST /api/webhooks/whatsapp verifies HMAC-SHA256 signature when secret is configured."""
    payload = {
        "event": "test",
        "timestamp": "2026-10-31T01:00:00.000Z",
        "sessionId": TEST_SESSION_UUID,
        "data": {"message": "Test"},
    }
    raw_bytes = json.dumps(payload).encode("utf-8")
    valid_sig = _compute_openwa_sig(raw_bytes)

    # 1. Valid signature succeeds
    res_valid = client.post(
        "/api/webhooks/whatsapp",
        content=raw_bytes,
        headers={"Content-Type": "application/json", "X-OpenWA-Signature": valid_sig},
    )
    assert res_valid.status_code == 200
    assert res_valid.json()["details"]["status"] == "test_acknowledged"

    # 2. Invalid signature is rejected with 401
    res_invalid = client.post(
        "/api/webhooks/whatsapp",
        content=raw_bytes,
        headers={"Content-Type": "application/json", "X-OpenWA-Signature": "sha256=invalid00000000"},
    )
    assert res_invalid.status_code == 401

    # 3. Missing signature when secret is required is rejected with 401
    res_missing = client.post(
        "/api/webhooks/whatsapp",
        content=raw_bytes,
        headers={"Content-Type": "application/json"},
    )
    assert res_missing.status_code == 401


@pytest.mark.asyncio
async def test_openwa_inbound_message_processed_and_replied(client, db):
    """Valid citizen message via OpenWA generates AI reply and delivers to sender chatId."""
    chat_id = "919876543210@c.us"
    msg_id = "false_919876543210@c.us_3EB0OPENWA1"

    payload = {
        "event": "message.received",
        "timestamp": "2026-10-31T01:00:00.000Z",
        "sessionId": TEST_SESSION_UUID,
        "idempotencyKey": "key_123",
        "deliveryId": "del_123",
        "data": {
            "id": msg_id,
            "from": chat_id,
            "to": "919060189531@c.us",
            "chatId": chat_id,
            "body": "Namaste! Main 18 saal ka ho gaya hoon, mujhe kaun se documents banwane chahiye?",
            "type": "chat",
            "timestamp": 1730000000,
            "fromMe": False,
            "isGroup": False,
            "isStatusBroadcast": False,
            "pushName": "Rohan",
        },
    }
    raw_bytes = json.dumps(payload).encode("utf-8")
    sig = _compute_openwa_sig(raw_bytes)

    # Mock outbound OpenWA send-text HTTP request
    mock_send = AsyncMock(return_value={
        "success": True,
        "message_id": "true_919876543210@c.us_3EB0REPLY1",
        "recipient_id": chat_id,
        "status": "sent",
        "provider": "openwa",
    })

    with patch.object(OpenWAProvider, "send_text_message", mock_send):
        res = client.post(
            "/api/webhooks/whatsapp",
            content=raw_bytes,
            headers={"Content-Type": "application/json", "X-OpenWA-Signature": sig},
        )

    assert res.status_code == 200
    res_data = res.json()
    assert res_data["status"] == "ok"
    assert res_data["details"]["status"] == "processed"
    assert res_data["details"]["provider"] == "openwa"

    # Verify OpenWA send was called with correct chat and AI reply
    mock_send.assert_called_once()
    call_args = mock_send.call_args[1]
    assert call_args["recipient_id"] == chat_id
    assert "Voter ID" in call_args["text"] or "PAN" in call_args["text"]

    # Verify SQLite database records
    conv = db.query(WhatsAppConversation).filter(WhatsAppConversation.wa_id == "919876543210").first()
    assert conv is not None
    assert conv.contact_name == "Rohan"
    assert conv.phone_number_masked == "***3210"

    messages = db.query(WhatsAppMessage).filter(WhatsAppMessage.conversation_id == conv.id).all()
    assert len(messages) >= 2
    inbound = [m for m in messages if m.direction == "inbound"][0]
    outbound = [m for m in messages if m.direction == "outbound"][0]
    assert inbound.wamid == msg_id
    assert outbound.delivery_status == "sent"


def test_openwa_outgoing_message_filtered(client):
    """Outgoing message echoes (fromMe: true or direction: 'outgoing') are ignored."""
    payload = {
        "event": "message.received",
        "sessionId": TEST_SESSION_UUID,
        "data": {
            "id": "true_919876543210@c.us_3EB0ECHO",
            "chatId": "919876543210@c.us",
            "from": "919060189531@c.us",
            "body": "Outgoing bot message echo",
            "fromMe": True,
        },
    }
    raw_bytes = json.dumps(payload).encode("utf-8")
    sig = _compute_openwa_sig(raw_bytes)

    res = client.post(
        "/api/webhooks/whatsapp",
        content=raw_bytes,
        headers={"Content-Type": "application/json", "X-OpenWA-Signature": sig},
    )
    assert res.status_code == 200
    assert res.json()["details"]["status"] == "ignored_outgoing_message"


def test_openwa_status_broadcast_filtered(client):
    """Status/story broadcasts are ignored safely."""
    payload = {
        "event": "message.received",
        "sessionId": TEST_SESSION_UUID,
        "data": {
            "id": "status_broadcast_001",
            "chatId": "status@broadcast",
            "from": "status@broadcast",
            "body": "User posted a WhatsApp status",
            "isStatusBroadcast": True,
            "fromMe": False,
        },
    }
    raw_bytes = json.dumps(payload).encode("utf-8")
    sig = _compute_openwa_sig(raw_bytes)

    res = client.post(
        "/api/webhooks/whatsapp",
        content=raw_bytes,
        headers={"Content-Type": "application/json", "X-OpenWA-Signature": sig},
    )
    assert res.status_code == 200
    assert res.json()["details"]["status"] == "ignored_status_broadcast"


def test_openwa_group_message_filtered(client):
    """Group messages (@g.us or isGroup: true) are ignored to keep civic assistance 1-on-1."""
    payload = {
        "event": "message.received",
        "sessionId": TEST_SESSION_UUID,
        "data": {
            "id": "group_msg_001",
            "chatId": "120363000000000000@g.us",
            "from": "120363000000000000@g.us",
            "body": "Hello group members",
            "isGroup": True,
            "fromMe": False,
        },
    }
    raw_bytes = json.dumps(payload).encode("utf-8")
    sig = _compute_openwa_sig(raw_bytes)

    res = client.post(
        "/api/webhooks/whatsapp",
        content=raw_bytes,
        headers={"Content-Type": "application/json", "X-OpenWA-Signature": sig},
    )
    assert res.status_code == 200
    assert res.json()["details"]["status"] == "ignored_group_message"


def test_openwa_empty_and_non_text_filtered(client):
    """Messages without usable text (e.g. image without caption or empty string) are ignored."""
    payload = {
        "event": "message.received",
        "sessionId": TEST_SESSION_UUID,
        "data": {
            "id": "media_empty_001",
            "chatId": "919876543210@c.us",
            "from": "919876543210@c.us",
            "body": "   ",
            "type": "image",
            "fromMe": False,
            "isGroup": False,
        },
    }
    raw_bytes = json.dumps(payload).encode("utf-8")
    sig = _compute_openwa_sig(raw_bytes)

    res = client.post(
        "/api/webhooks/whatsapp",
        content=raw_bytes,
        headers={"Content-Type": "application/json", "X-OpenWA-Signature": sig},
    )
    assert res.status_code == 200
    assert res.json()["details"]["status"] == "ignored_no_usable_text"


def test_openwa_message_deduplication(client):
    """Duplicate message IDs are processed once and subsequent deliveries are ignored."""
    msg_id = "false_919876543210@c.us_3EB0DEDUP"
    payload = {
        "event": "message.received",
        "sessionId": TEST_SESSION_UUID,
        "data": {
            "id": msg_id,
            "chatId": "919876543210@c.us",
            "from": "919876543210@c.us",
            "body": "Hello Timbre deduplication test",
            "type": "chat",
            "fromMe": False,
            "isGroup": False,
        },
    }
    raw_bytes = json.dumps(payload).encode("utf-8")
    sig = _compute_openwa_sig(raw_bytes)

    mock_send = AsyncMock(return_value={"success": True, "message_id": "reply_1", "status": "sent"})
    with patch.object(OpenWAProvider, "send_text_message", mock_send):
        # 1. First delivery processed
        res1 = client.post(
            "/api/webhooks/whatsapp",
            content=raw_bytes,
            headers={"Content-Type": "application/json", "X-OpenWA-Signature": sig},
        )
        assert res1.status_code == 200
        assert res1.json()["details"]["status"] == "processed"

        # 2. Duplicate delivery ignored
        res2 = client.post(
            "/api/webhooks/whatsapp",
            content=raw_bytes,
            headers={"Content-Type": "application/json", "X-OpenWA-Signature": sig},
        )
        assert res2.status_code == 200
        assert res2.json()["details"]["status"] == "duplicate_ignored"
        assert res2.json()["details"]["wamid"] == msg_id


def test_openwa_send_failure_handled_safely(client, db):
    """When OpenWA returns HTTP 409 (qr_ready / not connected), failure is recorded safely without crashing."""
    msg_id = "false_919876543210@c.us_3EB0FAIL"
    payload = {
        "event": "message.received",
        "sessionId": TEST_SESSION_UUID,
        "data": {
            "id": msg_id,
            "chatId": "919876543210@c.us",
            "from": "919876543210@c.us",
            "body": "What is PAN card fee?",
            "type": "chat",
            "fromMe": False,
            "isGroup": False,
        },
    }
    raw_bytes = json.dumps(payload).encode("utf-8")
    sig = _compute_openwa_sig(raw_bytes)

    # Mock OpenWA send failure (HTTP 409 Conflict: session not connected)
    mock_send_fail = AsyncMock(
        side_effect=MessagingProviderError(
            "OpenWA session is not connected. The WhatsApp client is not ready.",
            status_code=409,
            provider="openwa",
        )
    )

    with patch.object(OpenWAProvider, "send_text_message", mock_send_fail):
        res = client.post(
            "/api/webhooks/whatsapp",
            content=raw_bytes,
            headers={"Content-Type": "application/json", "X-OpenWA-Signature": sig},
        )

    assert res.status_code == 200
    res_data = res.json()
    assert res_data["status"] == "ok"
    turn = res_data["details"]["turn"]
    assert turn["delivery_status"] == "failed"
    assert "OpenWA session is not connected" in turn["error"]

    # Inbound and AI generated response are preserved in database
    outbound = (
        db.query(WhatsAppMessage)
        .filter(WhatsAppMessage.direction == "outbound")
        .order_by(WhatsAppMessage.created_at.desc())
        .first()
    )
    assert outbound is not None
    assert outbound.delivery_status == "failed"
    meta = json.loads(outbound.meta_json)
    assert "OpenWA session is not connected" in meta["error"]


@pytest.mark.asyncio
async def test_openwa_session_name_to_uuid_resolution():
    """OpenWAProvider dynamically resolves session name 'timbre' to UUID via GET /api/sessions."""
    provider = OpenWAProvider()
    provider.session_id = "timbre"
    provider._resolved_session_uuid = None

    mock_resp = MagicMock(status_code=200)
    mock_resp.json.return_value = [
        {"id": "uuid-other-1", "name": "other"},
        {"id": TEST_SESSION_UUID, "name": "timbre"},
    ]
    mock_client = AsyncMock()
    mock_client.get = AsyncMock(return_value=mock_resp)

    resolved = await provider.resolve_session_id(mock_client)
    assert resolved == TEST_SESSION_UUID
    assert provider._resolved_session_uuid == TEST_SESSION_UUID


def test_openwa_readiness_audit(client):
    """GET /api/whatsapp/readiness reports openwa_configured: true and provider_mode: openwa."""
    res = client.get("/api/whatsapp/readiness")
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "ready"
    assert data["provider_mode"] == "openwa"
    assert data["openwa_configured"] is True
    assert data["openwa_session_id_set"] is True
    assert data["safety_invariants"]["ENABLE_REAL_CALLS"] is False
    assert data["safety_invariants"]["outbound_phone_dialing_prevented"] is True


def test_openwa_preserves_telephony_safety_flags():
    """Confirms telephony dialing flags remain strictly false under OpenWA."""
    assert settings.ENABLE_REAL_CALLS is False
    assert settings.BOLNA_TEST_AGENT_VERIFIED is False


def test_openwa_non_message_events_ignored(client):
    """Non-message OpenWA lifecycle events (e.g. session.status, presence.update) are ignored."""
    payload = {
        "event": "session.status",
        "sessionId": TEST_SESSION_UUID,
        "data": {"status": "connected"},
    }
    raw_bytes = json.dumps(payload).encode("utf-8")
    sig = _compute_openwa_sig(raw_bytes)

    res = client.post(
        "/api/webhooks/whatsapp",
        content=raw_bytes,
        headers={"Content-Type": "application/json", "X-OpenWA-Signature": sig},
    )
    assert res.status_code == 200
    assert res.json()["details"]["status"] == "ignored_non_message_event"
    assert res.json()["details"]["event"] == "session.status"


def test_openwa_chat_id_normalization():
    """OpenWAProvider correctly normalizes various phone number formats into @c.us JID."""
    provider = OpenWAProvider()
    assert provider._normalize_chat_id("919876543210@c.us") == "919876543210@c.us"
    assert provider._normalize_chat_id("919876543210@s.whatsapp.net") == "919876543210@c.us"
    assert provider._normalize_chat_id("+91 98765 43210") == "919876543210@c.us"
    assert provider._normalize_chat_id("919876543210") == "919876543210@c.us"

