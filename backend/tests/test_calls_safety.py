import pytest
from unittest.mock import patch, AsyncMock


def test_demo_call_dispatch(client):
    res = client.post(
        "/api/calls",
        json={
            "citizen_id": "CIT-0002",
            "trigger_event": "TEST_DEMO_TRIGGER",
            "is_real_call": False
        }
    )
    assert res.status_code == 201
    data = res.json()
    assert data["citizen_id"] == "CIT-0002"
    assert data["is_real_call"] is False
    assert data["job_status"] == "COMPLETED"
    assert len(data["transcript_events"]) > 0


def test_idempotent_duplicate_call_prevention(client):
    # First call
    res1 = client.post(
        "/api/calls",
        json={
            "citizen_id": "CIT-0003",
            "trigger_event": "MILESTONE_AGE_18",
            "is_real_call": False
        }
    )
    assert res1.status_code == 201

    # Second identical call must be blocked with 409 Conflict
    res2 = client.post(
        "/api/calls",
        json={
            "citizen_id": "CIT-0003",
            "trigger_event": "MILESTONE_AGE_18",
            "is_real_call": False
        }
    )
    assert res2.status_code == 409
    assert "idempotency enforced" in res2.json()["detail"].lower()


def test_safety_rejection_fictional_citizen_real_call(client):
    # Attempting to place a real call to a fictional citizen ID must be rejected
    res = client.post(
        "/api/calls",
        json={
            "citizen_id": "CIT-0001",
            "trigger_event": "REAL_TEST",
            "is_real_call": True,
            "consented_phone_number": "+919876543210",
            "consent_confirmed": True
        }
    )
    assert res.status_code == 403
    assert "individually reviewed test-call flow" in res.json()["detail"].lower()


def test_safety_rejection_real_calls_disabled_by_default(client):
    # Using a non-synthetic ID but real calls disabled on server
    res = client.post(
        "/api/calls",
        json={
            "citizen_id": "CIT-0004",
            "trigger_event": "REAL_CALL_FLAG_CHECK",
            "is_real_call": True,
            "consented_phone_number": "+919876543210",
            "consent_confirmed": True
        }
    )
    assert res.status_code == 403


def test_get_call_job_by_id(client):
    # First create a demo job
    create_res = client.post(
        "/api/calls",
        json={
            "citizen_id": "CIT-0005",
            "trigger_event": "GET_JOB_TEST",
            "is_real_call": False
        }
    )
    assert create_res.status_code == 201
    job_id = create_res.json()["id"]

    get_res = client.get(f"/api/calls/{job_id}")
    assert get_res.status_code == 200
    assert get_res.json()["id"] == job_id


def test_bolna_credential_redaction():
    from app.services.bolna_service import bolna_service
    health_info = bolna_service.check_health()
    # Ensure raw secret keys are not present in health dict
    assert "api_key" not in health_info
    assert "BOLNA_API_KEY" not in str(health_info)


def test_real_call_missing_credentials_handling():
    import pytest
    from app.services.bolna_service import BolnaIntegrationService
    svc = BolnaIntegrationService()
    svc.api_key = ""
    svc.agent_id = ""
    svc.enable_real_calls = True
    svc.test_agent_verified = True
    with pytest.raises(PermissionError, match="individually reviewed"):
        import asyncio
        asyncio.run(svc.initiate_call(
            citizen_id="REAL-123",
            citizen_name="Test Citizen",
            phone_number="+919876543210",
            trigger_event="REAL_EVENT",
            is_real_call_requested=True,
            consent_confirmed=True
        ))


def _approved_test_payload(**overrides):
    payload = {
        "citizen_id": "CIT-0009",
        "test_recipient_number": "+919000000099",
        "language": "hi",
        "recipient_has_consented": True,
        "script_reviewed": True,
        "ai_disclosure_confirmed": True,
        "caller_id_reviewed": True,
        "confirm_single_call": True,
        "confirmation_phrase": "CALL ONCE",
    }
    payload.update(overrides)
    return payload


def test_approved_live_test_is_locked_by_default(client):
    with patch("app.api.calls.settings.ENABLE_REAL_CALLS", False), patch(
        "app.api.calls.bolna_service.initiate_approved_test_call", new_callable=AsyncMock
    ) as dispatch:
        response = client.post("/api/calls/approved-test", json=_approved_test_payload())
    assert response.status_code == 403
    assert "disabled" in response.json()["detail"].lower()
    dispatch.assert_not_called()


def test_approved_test_requires_consent_script_disclosure_and_single_call(client):
    for field in (
        "recipient_has_consented",
        "script_reviewed",
        "ai_disclosure_confirmed",
        "caller_id_reviewed",
        "confirm_single_call",
    ):
        response = client.post(
            "/api/calls/approved-test",
            json=_approved_test_payload(**{field: False}),
        )
        assert response.status_code == 422
    wrong_phrase = client.post(
        "/api/calls/approved-test",
        json=_approved_test_payload(confirmation_phrase="CALL"),
    )
    assert wrong_phrase.status_code == 422


def test_approved_test_sends_only_synthetic_context_and_masks_number(client, monkeypatch):
    from app.config import settings
    from app.services.bolna_service import bolna_service

    monkeypatch.setattr(settings, "ENABLE_REAL_CALLS", True)
    monkeypatch.setattr(settings, "BOLNA_TEST_AGENT_VERIFIED", True)
    monkeypatch.setattr(bolna_service, "api_key", "test-token")
    monkeypatch.setattr(bolna_service, "agent_id", "test-agent")
    monkeypatch.setattr(bolna_service, "enable_real_calls", True)
    monkeypatch.setattr(bolna_service, "test_agent_verified", True)
    with patch.object(
        bolna_service,
        "initiate_approved_test_call",
        new_callable=AsyncMock,
        return_value={
            "success": True,
            "status": "QUEUED",
            "is_real_call": True,
            "execution_id": "execution-test-1",
        },
    ) as dispatch:
        response = client.post("/api/calls/approved-test", json=_approved_test_payload())

    assert response.status_code == 201
    data = response.json()
    assert data["is_real_call"] is True
    assert data["recipient_phone"] == "***0099"
    assert data["bolna_execution_id"] == "execution-test-1"
    assert data["transcript_events"] == []
    dispatch.assert_awaited_once_with(phone_number="+919000000099", language="hi")


def test_call_job_cancel_only_queued_and_status_refresh_are_safe(client, monkeypatch):
    from app.config import settings
    from app.services.bolna_service import bolna_service

    monkeypatch.setattr(settings, "ENABLE_REAL_CALLS", True)
    monkeypatch.setattr(settings, "BOLNA_TEST_AGENT_VERIFIED", True)
    monkeypatch.setattr(bolna_service, "api_key", "test-token")
    monkeypatch.setattr(bolna_service, "agent_id", "test-agent")
    monkeypatch.setattr(bolna_service, "enable_real_calls", True)
    monkeypatch.setattr(bolna_service, "test_agent_verified", True)
    with patch.object(
        bolna_service,
        "initiate_approved_test_call",
        new_callable=AsyncMock,
        return_value={"status": "QUEUED", "execution_id": "execution-test-2"},
    ):
        created = client.post("/api/calls/approved-test", json=_approved_test_payload())
    call_id = created.json()["id"]

    with patch.object(
        bolna_service,
        "get_call_status",
        new_callable=AsyncMock,
        return_value={"status": "in-progress", "duration_seconds": 15},
    ) as status_lookup:
        refreshed = client.post(f"/api/calls/{call_id}/refresh-status")
    assert refreshed.status_code == 200
    assert refreshed.json()["job_status"] == "IN_PROGRESS"
    assert refreshed.json()["duration_seconds"] == 15
    status_lookup.assert_awaited_once_with("execution-test-2")

    with patch.object(
        bolna_service,
        "stop_queued_call",
        new_callable=AsyncMock,
    ) as stop:
        rejected = client.post(f"/api/calls/{call_id}/stop")
    assert rejected.status_code == 409
    stop.assert_not_called()


def test_local_dry_run_requires_consent_normalizes_and_masks_recipient(client):
    from app.services.bolna_service import bolna_service
    from unittest.mock import patch

    with patch.object(bolna_service, "initiate_call", new_callable=AsyncMock) as real_call:
        response = client.post("/api/calls/dry-run", json={
            "citizen_id": "CIT-0007",
            "trigger_event": "CONTROLLED_REVIEW_2026_10",
            "test_recipient_number": "906 018 9531",
            "recipient_has_consented": True,
        })
    assert response.status_code == 201
    data = response.json()
    assert data["is_real_call"] is False
    assert data["recipient_phone"] == "***9531"
    assert data["duration_seconds"] == 0
    transcript = " ".join(event["transcript_segment"] for event in data["transcript_events"])
    assert "Timbre" in transcript and "AI" in transcript
    assert "koi phone call nahi" in transcript.lower()
    assert "eligible" not in transcript.lower()
    assert "9060189531" not in transcript
    real_call.assert_not_called()
    duplicate = client.post("/api/calls/dry-run", json={
        "citizen_id": "CIT-0007",
        "trigger_event": "CONTROLLED_REVIEW_2026_10",
        "test_recipient_number": "+919060189531",
        "recipient_has_consented": True,
    })
    assert duplicate.status_code == 409


def test_local_dry_run_rejects_missing_consent_and_invalid_numbers(client):
    base = {"citizen_id": "CIT-0008", "trigger_event": "CONSENT_TEST"}
    no_consent = client.post("/api/calls/dry-run", json={**base, "test_recipient_number": "9060189531"})
    invalid = client.post("/api/calls/dry-run", json={**base, "test_recipient_number": "call me", "recipient_has_consented": True})
    assert no_consent.status_code == 422
    assert invalid.status_code == 422
