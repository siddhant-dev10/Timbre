import pytest
from app.config import settings

TEST_WEBHOOK_SECRET = "local-test-webhook-secret"


@pytest.fixture(autouse=True)
def configured_webhook_secret(monkeypatch):
    monkeypatch.setattr(settings, "BOLNA_WEBHOOK_SECRET", TEST_WEBHOOK_SECRET)


def test_bolna_webhook_processing(client):
    # First create a call job with execution id
    create_res = client.post(
        "/api/calls",
        json={
            "citizen_id": "CIT-0006",
            "trigger_event": "WEBHOOK_TEST",
            "is_real_call": False
        },
    )
    assert create_res.status_code == 201
    exec_id = create_res.json()["bolna_execution_id"]

    # Send webhook payload from Bolna
    webhook_res = client.post(
        "/api/webhooks/bolna",
        json={
            "id": exec_id,
            "status": "completed",
            "call_duration": 58,
            "transcript": "Namaste! Haan maine aavedan samajh liya hai."
        },
        headers={"X-Timbre-Webhook-Secret": TEST_WEBHOOK_SECRET},
    )
    assert webhook_res.status_code == 200
    assert webhook_res.json()["status"] == "processed"
    assert webhook_res.json()["job_status"] == "COMPLETED"
    saved_job = client.get(f"/api/calls/{create_res.json()['id']}").json()
    saved_text = " ".join(event["transcript_segment"] for event in saved_job["transcript_events"])
    assert "aavedan samajh liya" not in saved_text
    assert "omitted from local log" in saved_text


def test_bolna_webhook_unmatched(client):
    webhook_res = client.post(
        "/api/webhooks/bolna",
        json={
            "id": "unmatched-execution-999",
            "status": "in-progress"
        },
        headers={"X-Timbre-Webhook-Secret": TEST_WEBHOOK_SECRET},
    )
    assert webhook_res.status_code == 200
    assert webhook_res.json()["status"] == "received_unmatched"
@pytest.mark.parametrize("provider_status", ["busy", "no-answer", "canceled", "failed"])
def test_bolna_terminal_failure_statuses_are_mapped(client, provider_status):
    created = client.post("/api/calls", json={
        "citizen_id": "CIT-0010",
        "trigger_event": f"WEBHOOK_{provider_status.upper().replace('-', '_')}",
        "is_real_call": False,
    })
    assert created.status_code == 201
    updated = client.post("/api/webhooks/bolna", json={
        "id": created.json()["bolna_execution_id"],
        "status": provider_status,
    }, headers={"X-Timbre-Webhook-Secret": TEST_WEBHOOK_SECRET})
    assert updated.status_code == 200
    assert updated.json()["job_status"] == "FAILED"


def test_bolna_webhook_rejects_missing_or_invalid_auth(client, monkeypatch):
    payload = {"id": "unmatched", "status": "completed"}
    assert client.post("/api/webhooks/bolna", json=payload).status_code == 401
    assert client.post("/api/webhooks/bolna", json=payload, headers={"X-Timbre-Webhook-Secret": "wrong"}).status_code == 401
    monkeypatch.setattr(settings, "BOLNA_WEBHOOK_SECRET", "")
    assert client.post("/api/webhooks/bolna", json=payload).status_code == 503


def test_bolna_webhook_bearer_and_query_token_auth(client):
    payload = {"id": "auth-test-exec", "status": "ringing"}
    # Authorization: Bearer
    bearer_res = client.post(
        "/api/webhooks/bolna",
        json=payload,
        headers={"Authorization": f"Bearer {TEST_WEBHOOK_SECRET}"},
    )
    assert bearer_res.status_code == 200

    # Query param ?token=
    query_res = client.post(
        f"/api/webhooks/bolna?token={TEST_WEBHOOK_SECRET}",
        json={"id": "auth-query-exec", "status": "ringing"},
    )
    assert query_res.status_code == 200


def test_bolna_webhook_duplicate_replay_prevention(client):
    payload = {"id": "replay-exec-001", "status": "completed"}
    # First delivery
    res1 = client.post(
        "/api/webhooks/bolna",
        json=payload,
        headers={"X-Timbre-Webhook-Secret": TEST_WEBHOOK_SECRET},
    )
    assert res1.status_code == 200
    assert res1.json()["status"] in ("processed", "received_unmatched")

    # Second delivery with exact same ID and status (duplicate webhook)
    res2 = client.post(
        "/api/webhooks/bolna",
        json=payload,
        headers={"X-Timbre-Webhook-Secret": TEST_WEBHOOK_SECRET},
    )
    assert res2.status_code == 200
    assert res2.json()["status"] == "duplicate_ignored"

