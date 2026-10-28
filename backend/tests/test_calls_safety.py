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
    assert "safety violation" in res.json()["detail"].lower()


def test_safety_rejection_real_calls_disabled_by_default(client):
    # Using a non-synthetic ID but real calls disabled on server
    res = client.post(
        "/api/calls",
        json={
            "citizen_id": "CIT-0004",
            "trigger_event": "REAL_CALL_FLAG_CHECK",
            "is_real_call": True,
            "consented_phone_number": "+919876543210",
            "consent_confirmed": False
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
    with pytest.raises(RuntimeError, match="not configured"):
        import asyncio
        asyncio.run(svc.initiate_call(
            citizen_id="REAL-123",
            citizen_name="Test Citizen",
            phone_number="+919876543210",
            trigger_event="REAL_EVENT",
            is_real_call_requested=True,
            consent_confirmed=True
        ))
