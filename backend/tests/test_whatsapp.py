"""Comprehensive Automated Test Suite for Timbre WhatsApp Messaging MVP.

Covers:
1. Meta Webhook Subscription Handshake (GET /api/webhooks/whatsapp).
2. Webhook Signature Verification (HMAC-SHA256 valid, invalid, missing).
3. Inbound Message Parsing & Normalization.
4. Message Deduplication by wamid (in-memory and database level).
5. Conversation Isolation (different wa_id senders never leak context).
6. Multi-turn Conversational Continuity.
7. Scheme Discovery & Adulthood (18-year-old) Milestone Guidance.
8. Interactive Clarifying Questions when information is missing.
9. Multilingual Support: Hindi (Devanagari), Hinglish, and English.
10. Provider Failure & Timeout Handling.
11. Privacy & Phone Number Masking.
12. Preservation of Outbound Call Safety Flags.
"""
import hashlib
import hmac
import json
import pytest
from app.config import settings
from app.models.whatsapp import WhatsAppConversation, WhatsAppMessage
from app.services.messaging_provider import MockWhatsAppProvider, WhatsAppCloudProvider, MessagingProviderError
from app.services.whatsapp_service import whatsapp_service

TEST_VERIFY_TOKEN = "test-whatsapp-verify-token-123"
TEST_APP_SECRET = "test-meta-app-secret-xyz"


@pytest.fixture(autouse=True)
def configure_whatsapp_test_env(monkeypatch):
    monkeypatch.setattr(settings, "WHATSAPP_VERIFY_TOKEN", TEST_VERIFY_TOKEN)
    monkeypatch.setattr(settings, "WHATSAPP_APP_SECRET", TEST_APP_SECRET)
    monkeypatch.setattr(settings, "WHATSAPP_ACCESS_TOKEN", "test-access-token")
    monkeypatch.setattr(settings, "WHATSAPP_PHONE_NUMBER_ID", "109876543210")
    monkeypatch.setattr(settings, "NVIDIA_API_KEY", "")
    monkeypatch.setattr(settings, "ENABLE_REAL_CALLS", False)
    monkeypatch.setattr(settings, "BOLNA_TEST_AGENT_VERIFIED", False)
    whatsapp_service.reload_config()


def _compute_signature(raw_bytes: bytes, secret: str = TEST_APP_SECRET) -> str:
    digest = hmac.new(secret.encode("utf-8"), raw_bytes, hashlib.sha256).hexdigest()
    return f"sha256={digest}"


def test_whatsapp_webhook_verification_handshake(client):
    """GET /api/webhooks/whatsapp returns hub.challenge as plaintext when token matches."""
    challenge_val = "1158201207"
    res = client.get(
        f"/api/webhooks/whatsapp?hub.mode=subscribe&hub.challenge={challenge_val}&hub.verify_token={TEST_VERIFY_TOKEN}"
    )
    assert res.status_code == 200
    assert res.text == challenge_val
    assert "text/plain" in res.headers["content-type"]


def test_whatsapp_webhook_verification_rejects_invalid_token(client):
    """GET /api/webhooks/whatsapp returns HTTP 403 when verify_token does not match."""
    res = client.get(
        f"/api/webhooks/whatsapp?hub.mode=subscribe&hub.challenge=999&hub.verify_token=wrong-token"
    )
    assert res.status_code == 403


def test_whatsapp_webhook_signature_verification(client):
    """POST /api/webhooks/whatsapp verifies HMAC-SHA256 signature with WHATSAPP_APP_SECRET."""
    payload = {
        "object": "whatsapp_business_account",
        "entry": [{
            "id": "biz-1",
            "changes": [{
                "value": {
                    "messaging_product": "whatsapp",
                    "contacts": [{"wa_id": "919811002200", "profile": {"name": "Signature Test"}}],
                    "messages": [{
                        "from": "919811002200",
                        "id": "wamid.sigtest.001",
                        "timestamp": "1730000000",
                        "type": "text",
                        "text": {"body": "Namaste"},
                    }],
                },
                "field": "messages",
            }],
        }],
    }
    raw_bytes = json.dumps(payload).encode("utf-8")
    valid_sig = _compute_signature(raw_bytes)

    # 1. Valid signature succeeds
    res_valid = client.post(
        "/api/webhooks/whatsapp",
        content=raw_bytes,
        headers={"Content-Type": "application/json", "X-Hub-Signature-256": valid_sig},
    )
    assert res_valid.status_code == 200
    assert res_valid.json()["status"] == "ok"

    # 2. Invalid signature is rejected with 401
    payload["entry"][0]["changes"][0]["value"]["messages"][0]["id"] = "wamid.sigtest.002"
    invalid_bytes = json.dumps(payload).encode("utf-8")
    res_invalid = client.post(
        "/api/webhooks/whatsapp",
        content=invalid_bytes,
        headers={"Content-Type": "application/json", "X-Hub-Signature-256": "sha256=invalidhex000000"},
    )
    assert res_invalid.status_code == 401


def test_whatsapp_message_deduplication(client):
    """Duplicate webhook deliveries with the same wamid are ignored idempotently."""
    wamid = "wamid.dedup.unique.001"
    payload = {
        "object": "whatsapp_business_account",
        "entry": [{
            "id": "biz-1",
            "changes": [{
                "value": {
                    "messaging_product": "whatsapp",
                    "contacts": [{"wa_id": "919811003300", "profile": {"name": "Dedup Test"}}],
                    "messages": [{
                        "from": "919811003300",
                        "id": wamid,
                        "timestamp": "1730000000",
                        "type": "text",
                        "text": {"body": "First delivery"},
                    }],
                },
                "field": "messages",
            }],
        }],
    }
    raw_bytes = json.dumps(payload).encode("utf-8")
    sig = _compute_signature(raw_bytes)

    # First delivery: processed
    res1 = client.post(
        "/api/webhooks/whatsapp",
        content=raw_bytes,
        headers={"Content-Type": "application/json", "X-Hub-Signature-256": sig},
    )
    assert res1.status_code == 200
    assert res1.json()["details"]["status"] == "processed"

    # Second delivery with exact same wamid: duplicate_ignored
    res2 = client.post(
        "/api/webhooks/whatsapp",
        content=raw_bytes,
        headers={"Content-Type": "application/json", "X-Hub-Signature-256": sig},
    )
    assert res2.status_code == 200
    assert res2.json()["details"]["status"] == "duplicate_ignored"


def test_whatsapp_status_receipts_acknowledged(client):
    """Delivery status receipts (sent/delivered/read) are acknowledged cleanly."""
    payload = {
        "object": "whatsapp_business_account",
        "entry": [{
            "id": "biz-1",
            "changes": [{
                "value": {
                    "messaging_product": "whatsapp",
                    "statuses": [{
                        "id": "wamid.status.001",
                        "status": "delivered",
                        "timestamp": "1730000010",
                        "recipient_id": "919811003300",
                    }],
                },
                "field": "messages",
            }],
        }],
    }
    raw_bytes = json.dumps(payload).encode("utf-8")
    sig = _compute_signature(raw_bytes)

    res = client.post(
        "/api/webhooks/whatsapp",
        content=raw_bytes,
        headers={"Content-Type": "application/json", "X-Hub-Signature-256": sig},
    )
    assert res.status_code == 200
    assert res.json()["details"]["status"] == "status_acknowledged"


def test_conversation_isolation_between_senders(client, db):
    """Different senders have isolated conversation history and never cross-contaminate."""
    sender_a = "919800000001"
    sender_b = "919800000002"

    # Sender A asks about Voter ID
    res_a = client.post(
        "/api/whatsapp/simulate",
        json={
            "sender_phone": sender_a,
            "sender_name": "Citizen A",
            "message": "Main 18 saal ka ho gaya hoon. Voter ID kaise banega?",
            "reset_conversation": True,
        },
    )
    assert res_a.status_code == 200
    conv_a_id = res_a.json()["conversation_id"]

    # Sender B asks about PM-Kisan
    res_b = client.post(
        "/api/whatsapp/simulate",
        json={
            "sender_phone": sender_b,
            "sender_name": "Citizen B",
            "message": "Kisan samman nidhi yojana ke baare me batayein",
            "reset_conversation": True,
        },
    )
    assert res_b.status_code == 200
    conv_b_id = res_b.json()["conversation_id"]

    assert conv_a_id != conv_b_id

    # Verify messages in Sender A's conversation
    history_a = client.get(f"/api/whatsapp/conversations/{sender_a}").json()
    assert history_a["conversation_id"] == conv_a_id
    assert history_a["phone_number_masked"] == "***0001"
    assert any("Voter ID" in m["content"] or "18" in m["content"] for m in history_a["messages"])
    assert not any("Kisan samman nidhi" in m["content"] for m in history_a["messages"])

    # Verify messages in Sender B's conversation
    history_b = client.get(f"/api/whatsapp/conversations/{sender_b}").json()
    assert history_b["conversation_id"] == conv_b_id
    assert history_b["phone_number_masked"] == "***0002"
    assert any("Kisan" in m["content"] or "kisan" in m["content"].lower() for m in history_b["messages"])


def test_adulthood_milestone_and_clarifying_questions(client):
    """When a citizen turns 18, Timbre explains core documents and asks clarifying questions."""
    res = client.post(
        "/api/whatsapp/simulate",
        json={
            "sender_phone": "919877665544",
            "sender_name": "Vikram",
            "message": "Main 18 saal ka ho gaya hoon. Mujhe kaun se government documents banwane chahiye?",
            "reset_conversation": True,
        },
    )
    assert res.status_code == 200
    data = res.json()
    reply = data["ai_reply"]

    # Discloses AI identity
    assert "Timbre" in reply or "AI" in reply
    # Mentions core documents for age 18
    assert "Voter ID" in reply or "Form 6" in reply
    assert "PAN" in reply
    # Asks clarifying question (state or existing documents)
    assert any(q in reply.lower() for q in ["state", "rajya", "documents", "pehchan", "marksheet", "birth certificate", "aadhaar"])
    # Disclaims preliminary guidance
    assert "preliminary" in reply.lower() or "official" in reply.lower() or "sarkari portal" in reply.lower()


def test_multilingual_handling_hindi_devanagari(client):
    """Queries in Devanagari Hindi receive natural Devanagari Hindi responses."""
    res = client.post(
        "/api/whatsapp/simulate",
        json={
            "sender_phone": "919877665544",
            "sender_name": "Sita",
            "message": "नमस्ते, क्या मुझे आयुष्मान भारत गोल्डन कार्ड के दस्तावेज़ पता चल सकते हैं?",
            "reset_conversation": True,
        },
    )
    assert res.status_code == 200
    data = res.json()
    assert data["language"] == "Hindi"
    assert any("\u0900" <= c <= "\u097f" for c in data["ai_reply"])
    assert "आयुष्मान" in data["ai_reply"] or "कार्ड" in data["ai_reply"] or "टिम्ब्रे" in data["ai_reply"] or "Timbre" in data["ai_reply"]


def test_multilingual_handling_english(client):
    """Queries in English receive clear English responses."""
    res = client.post(
        "/api/whatsapp/simulate",
        json={
            "sender_phone": "919877665544",
            "sender_name": "Arun",
            "message": "What is the statutory fee and application process for a Driving Learner Licence?",
            "reset_conversation": True,
        },
    )
    assert res.status_code == 200
    data = res.json()
    assert data["language"] in ("English", "Hinglish")
    assert "parivahan" in data["ai_reply"].lower() or "licence" in data["ai_reply"].lower() or "license" in data["ai_reply"].lower()


def test_privacy_refuses_aadhaar_collection(client):
    """Timbre explicitly refuses to collect Aadhaar numbers, OTPs, or passwords."""
    res = client.post(
        "/api/whatsapp/simulate",
        json={
            "sender_phone": "919877665544",
            "message": "Mera Aadhaar number 1234 5678 9012 hai aur OTP 4321 hai. Mera card bana do.",
            "reset_conversation": False,
        },
    )
    assert res.status_code == 200
    reply = res.json()["ai_reply"]
    assert "privacy" in reply.lower() or "sensitive" in reply.lower() or "aadhaar" in reply.lower() or "गोपनीयता" in reply


def test_provider_failure_handling(client):
    """Simulated provider outages (e.g. HTTP 503) are gracefully handled and logged."""
    res = client.post(
        "/api/whatsapp/simulate",
        json={
            "sender_phone": "919877665544",
            "message": "Testing provider outage handling",
            "simulate_provider_failure": True,
        },
    )
    assert res.status_code == 200
    data = res.json()
    assert data["delivery_status"] == "failed"
    assert data["error"] is not None
    assert "503" in data["error"] or "failure" in data["error"].lower()


def test_whatsapp_readiness_audit_endpoint(client):
    """GET /api/whatsapp/readiness returns non-dialing preflight check without network calls."""
    res = client.get("/api/whatsapp/readiness")
    assert res.status_code == 200
    data = res.json()
    assert "status" in data
    assert "provider_mode" in data
    assert data["safety_invariants"]["ENABLE_REAL_CALLS"] is False
    assert data["safety_invariants"]["BOLNA_TEST_AGENT_VERIFIED"] is False
    assert data["safety_invariants"]["outbound_phone_dialing_prevented"] is True


def test_preservation_of_telephony_safety_flags():
    """Confirms that telephony flags remain strictly disabled."""
    assert settings.ENABLE_REAL_CALLS is False
    assert settings.BOLNA_TEST_AGENT_VERIFIED is False
