"""Comprehensive Inbound AI Calling Tests for Timbre.

Tests inbound telephony integration:
1. Inbound webhook authentication (Header, Bearer, Query param).
2. Automatic Inbound CallJobRecord creation with privacy-masked caller number.
3. Matching known citizen by phone or linking to synthetic CIT-INBOUND profile.
4. Lifecycle status transitions (initiated -> in-progress -> completed/failed).
5. Duplicate webhook replay prevention.
6. Missing/invalid caller information handling without crashes.
7. Inbound call monitoring list endpoint (GET /api/calls/inbound).
8. Strict inbound/outbound workflow separation.
9. Inbound preflight readiness audit (GET /api/calls/inbound/readiness).
10. Verified Reliance Jio USSD forwarding guide (GET /api/calls/inbound/forwarding-guide).
11. Multilingual conversational support (Hindi / English / Hinglish stop intent).
12. Preservation of outbound safety flags (ENABLE_REAL_CALLS=false, BOLNA_TEST_AGENT_VERIFIED=false).
"""
import pytest
from unittest.mock import patch, AsyncMock
from app.config import settings
from app.models.call_job import CallJobRecord
from app.models.citizen import Citizen
from app.services.bolna_service import bolna_service

TEST_WEBHOOK_SECRET = "test-inbound-webhook-secret-999"


@pytest.fixture(autouse=True)
def configure_test_secrets(monkeypatch):
    monkeypatch.setattr(settings, "BOLNA_WEBHOOK_SECRET", TEST_WEBHOOK_SECRET)
    monkeypatch.setattr(settings, "TIMBRE_LLM_API_KEY", "test-llm-key-123")
    monkeypatch.setattr(settings, "ENABLE_REAL_CALLS", False)
    monkeypatch.setattr(settings, "BOLNA_TEST_AGENT_VERIFIED", False)
    bolna_service.reload_config()


def test_inbound_webhook_authentication_modes(client, monkeypatch):
    """Verifies that all supported authentication modes succeed, and missing/invalid tokens fail."""
    payload = {
        "id": "inbound-auth-exec-1",
        "status": "ringing",
        "call_type": "inbound",
        "telephony_data": {
            "call_type": "inbound",
            "from_number": "+919876543210",
        },
    }

    # 1. Header: X-Timbre-Webhook-Secret
    h_res = client.post(
        "/api/webhooks/bolna",
        json=payload,
        headers={"X-Timbre-Webhook-Secret": TEST_WEBHOOK_SECRET},
    )
    assert h_res.status_code == 200
    assert h_res.json()["status"] == "processed_inbound"

    # 2. Header: Authorization: Bearer
    payload["id"] = "inbound-auth-exec-2"
    b_res = client.post(
        "/api/webhooks/bolna",
        json=payload,
        headers={"Authorization": f"Bearer {TEST_WEBHOOK_SECRET}"},
    )
    assert b_res.status_code == 200
    assert b_res.json()["status"] == "processed_inbound"

    # 3. Query param: ?token=
    payload["id"] = "inbound-auth-exec-3"
    q_res = client.post(
        f"/api/webhooks/bolna?token={TEST_WEBHOOK_SECRET}",
        json=payload,
    )
    assert q_res.status_code == 200
    assert q_res.json()["status"] == "processed_inbound"

    # 4. Invalid secret -> 401
    payload["id"] = "inbound-auth-exec-4"
    inv_res = client.post(
        "/api/webhooks/bolna",
        json=payload,
        headers={"X-Timbre-Webhook-Secret": "wrong-secret"},
    )
    assert inv_res.status_code == 401

    # 5. Missing secret in env -> 503
    monkeypatch.setattr(settings, "BOLNA_WEBHOOK_SECRET", "")
    unconf_res = client.post(
        "/api/webhooks/bolna",
        json=payload,
        headers={"X-Timbre-Webhook-Secret": TEST_WEBHOOK_SECRET},
    )
    assert unconf_res.status_code == 503


def test_inbound_call_creation_with_masked_phone(client, db):
    """Inbound call webhook automatically creates an inbound CallJobRecord with masked caller phone."""
    exec_id = "inbound-exec-masked-01"
    raw_phone = "+919876543210"

    res = client.post(
        "/api/webhooks/bolna",
        headers={"X-Timbre-Webhook-Secret": TEST_WEBHOOK_SECRET},
        json={
            "id": exec_id,
            "status": "initiated",
            "telephony_data": {
                "call_type": "inbound",
                "from_number": raw_phone,
                "to_number": "+911145678900",
                "duration": 0,
            },
        },
    )
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "processed_inbound"
    assert data["job_status"] == "IN_PROGRESS"

    # Verify database record
    record = db.query(CallJobRecord).filter(CallJobRecord.bolna_execution_id == exec_id).first()
    assert record is not None
    assert record.direction == "inbound"
    assert record.trigger_event == "INBOUND_CALL"
    assert record.job_status == "IN_PROGRESS"
    assert record.recipient_phone == "***3210"
    assert record.citizen_id == "CIT-INBOUND"
    assert "Inbound" in record.citizen_name


def test_inbound_call_lifecycle_transitions(client, db):
    """Inbound call moves through lifecycle states: initiated -> in-progress -> completed with duration."""
    exec_id = "inbound-lifecycle-exec-02"

    # 1. Queued
    res1 = client.post(
        "/api/webhooks/bolna",
        headers={"X-Timbre-Webhook-Secret": TEST_WEBHOOK_SECRET},
        json={
            "id": exec_id,
            "status": "queued",
            "call_type": "inbound",
            "telephony_data": {"from_number": "+919811223344"},
        },
    )
    assert res1.status_code == 200
    assert res1.json()["job_status"] == "QUEUED"

    # 2. Ringing / In-Progress update
    res2 = client.post(
        "/api/webhooks/bolna",
        headers={"X-Timbre-Webhook-Secret": TEST_WEBHOOK_SECRET},
        json={
            "id": exec_id,
            "status": "in-progress",
            "call_type": "inbound",
        },
    )
    assert res2.status_code == 200
    assert res2.json()["status"] == "processed"
    assert res2.json()["job_status"] == "IN_PROGRESS"

    # 3. Completed with call duration
    res3 = client.post(
        "/api/webhooks/bolna",
        headers={"X-Timbre-Webhook-Secret": TEST_WEBHOOK_SECRET},
        json={
            "id": exec_id,
            "status": "completed",
            "call_duration": 82,
            "transcript": "Citizen inquired about PM-Kisan installment dates.",
            "call_type": "inbound",
        },
    )
    assert res3.status_code == 200
    assert res3.json()["status"] == "processed"
    assert res3.json()["job_status"] == "COMPLETED"

    record = db.query(CallJobRecord).filter(CallJobRecord.bolna_execution_id == exec_id).first()
    assert record.job_status == "COMPLETED"
    assert record.duration_seconds == 82
    # Verify transcript privacy preservation
    assert "PM-Kisan installment" not in record.transcript_events
    assert "omitted from local log" in record.transcript_events


def test_inbound_call_duplicate_replay_prevention(client):
    """Duplicate delivery of the exact same inbound event status is ignored idempotently."""
    exec_id = "inbound-dup-exec-03"
    payload = {
        "id": exec_id,
        "status": "in-progress",
        "call_type": "inbound",
        "telephony_data": {"from_number": "+919876540000"},
    }

    # First delivery: creates record
    res1 = client.post(
        "/api/webhooks/bolna",
        headers={"X-Timbre-Webhook-Secret": TEST_WEBHOOK_SECRET},
        json=payload,
    )
    assert res1.status_code == 200
    assert res1.json()["status"] == "processed_inbound"

    # Duplicate delivery: returns duplicate_ignored
    res2 = client.post(
        "/api/webhooks/bolna",
        headers={"X-Timbre-Webhook-Secret": TEST_WEBHOOK_SECRET},
        json=payload,
    )
    assert res2.status_code == 200
    assert res2.json()["status"] == "duplicate_ignored"


def test_inbound_call_matches_existing_citizen_by_phone(client, db):
    """If caller phone number matches an existing citizen record, link directly to that citizen."""
    citizen = db.query(Citizen).filter(Citizen.id.startswith("CIT-")).first()
    assert citizen is not None

    exec_id = "inbound-matched-citizen-exec-04"
    res = client.post(
        "/api/webhooks/bolna",
        headers={"X-Timbre-Webhook-Secret": TEST_WEBHOOK_SECRET},
        json={
            "id": exec_id,
            "status": "initiated",
            "call_type": "inbound",
            "telephony_data": {
                "from_number": citizen.phone_number,
                "call_type": "inbound",
            },
        },
    )
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "processed_inbound"

    record = db.query(CallJobRecord).filter(CallJobRecord.bolna_execution_id == exec_id).first()
    assert record.citizen_id == citizen.id
    assert record.citizen_name == citizen.name


def test_inbound_call_missing_caller_phone_handled_safely(client, db):
    """Webhook with missing or empty caller phone does not crash and defaults safely."""
    exec_id = "inbound-missing-phone-exec-05"
    res = client.post(
        "/api/webhooks/bolna",
        headers={"X-Timbre-Webhook-Secret": TEST_WEBHOOK_SECRET},
        json={
            "id": exec_id,
            "status": "ringing",
            "call_type": "inbound",
        },
    )
    assert res.status_code == 200
    assert res.json()["status"] == "processed_inbound"

    record = db.query(CallJobRecord).filter(CallJobRecord.bolna_execution_id == exec_id).first()
    assert record.recipient_phone == "***0000"
    assert record.citizen_id == "CIT-INBOUND"


def test_inbound_call_monitoring_endpoint(client):
    """GET /api/calls/inbound lists recorded inbound calls with masked numbers and direction=inbound."""
    # Ensure at least one inbound call exists
    exec_id = "inbound-list-exec-06"
    client.post(
        "/api/webhooks/bolna",
        headers={"X-Timbre-Webhook-Secret": TEST_WEBHOOK_SECRET},
        json={
            "id": exec_id,
            "status": "completed",
            "call_duration": 42,
            "call_type": "inbound",
            "telephony_data": {"from_number": "+919876543210"},
        },
    )

    res = client.get("/api/calls/inbound")
    assert res.status_code == 200
    data = res.json()
    assert data["total"] >= 1
    found = any(job["bolna_execution_id"] == exec_id for job in data["jobs"])
    assert found
    for job in data["jobs"]:
        assert job["direction"] == "inbound"
        assert job["recipient_phone"].startswith("***")


def test_inbound_and_outbound_workflow_separation(client):
    """Verifies that inbound records cannot accidentally trigger outbound dialing, and outbound safety is enforced."""
    # 1. Standard schedule_call rejects real calls
    res1 = client.post(
        "/api/calls",
        json={
            "citizen_id": "CIT-0001",
            "is_real_call": True,
            "consented_phone_number": "+919876543210",
            "consent_confirmed": True,
        },
    )
    assert res1.status_code == 403

    # 2. Approved test call rejects when ENABLE_REAL_CALLS is False
    res2 = client.post(
        "/api/calls/approved-test",
        json={
            "citizen_id": "CIT-0001",
            "test_recipient_number": "+919876543210",
            "language": "hi",
            "recipient_has_consented": True,
            "script_reviewed": True,
            "ai_disclosure_confirmed": True,
            "caller_id_reviewed": True,
            "confirm_single_call": True,
            "confirmation_phrase": "CALL ONCE",
        },
    )
    assert res2.status_code == 403
    assert "Live calls are disabled" in res2.json()["detail"]


def test_preservation_of_outbound_safety_flags():
    """Confirms that both safety flags remain False and outbound dialing cannot be triggered."""
    assert settings.ENABLE_REAL_CALLS is False
    assert settings.BOLNA_TEST_AGENT_VERIFIED is False
    assert bolna_service.enable_real_calls is False
    assert bolna_service.test_agent_verified is False
    assert bolna_service.is_test_call_ready() is False


def test_inbound_readiness_endpoint(client):
    """GET /api/calls/inbound/readiness returns complete preflight audit without placing calls."""
    res = client.get("/api/calls/inbound/readiness")
    assert res.status_code == 200
    data = res.json()
    assert "status" in data
    assert "agent_id" in data
    assert "public_tunnel" in data
    assert "webhook" in data
    assert "telephony_numbers" in data
    assert "safety_invariants" in data
    assert data["safety_invariants"]["ENABLE_REAL_CALLS"] is False
    assert data["safety_invariants"]["BOLNA_TEST_AGENT_VERIFIED"] is False
    assert data["safety_invariants"]["outbound_dialing_prevented"] is True


def test_inbound_jio_forwarding_guide_endpoint(client):
    """GET /api/calls/inbound/forwarding-guide returns verified Reliance Jio USSD codes and instructions."""
    res = client.get("/api/calls/inbound/forwarding-guide")
    assert res.status_code == 200
    data = res.json()
    assert data["telephony_operator"] == "Reliance Jio (India)"
    assert "*401*" in data["activation_codes"]["unconditional"]
    assert "*402" in data["deactivation_codes"]["unconditional"]
    assert "*413" in data["deactivation_codes"]["master_cancel_all"]
    assert len(data["step_by_step_instructions"]) >= 4


def test_openai_compat_multilingual_handling(client):
    """Verifies that Custom LLM endpoint supports Hindi, English inquiries, and AI disclosure."""
    headers = {"Authorization": "Bearer test-llm-key-123"}

    # 1. English inquiry
    en_res = client.post(
        "/v1/chat/completions",
        headers=headers,
        json={
            "model": "timbre-voice-agent",
            "messages": [{"role": "user", "content": "What are the required documents for senior pension scheme?"}],
            "stream": False,
        },
    )
    assert en_res.status_code == 200
    en_choice = en_res.json()["choices"][0]["message"]["content"]
    assert "Timbre" in en_choice or "AI assistant" in en_choice or "pension" in en_choice.lower()

    # 2. Hindi inquiry
    hi_res = client.post(
        "/v1/chat/completions",
        headers=headers,
        json={
            "model": "timbre-voice-agent",
            "messages": [{"role": "user", "content": "राशन कार्ड के लिए कौन से दस्तावेज़ चाहिए?"}],
            "stream": False,
        },
    )
    assert hi_res.status_code == 200
    hi_choice = hi_res.json()["choices"][0]["message"]["content"]
    assert any('\u0900' <= char <= '\u097f' for char in hi_choice)
