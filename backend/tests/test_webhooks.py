def test_bolna_webhook_processing(client):
    # First create a call job with execution id
    create_res = client.post(
        "/api/calls",
        json={
            "citizen_id": "CIT-0006",
            "trigger_event": "WEBHOOK_TEST",
            "is_real_call": False
        }
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
        }
    )
    assert webhook_res.status_code == 200
    assert webhook_res.json()["status"] == "processed"
    assert webhook_res.json()["job_status"] == "COMPLETED"


def test_bolna_webhook_unmatched(client):
    webhook_res = client.post(
        "/api/webhooks/bolna",
        json={
            "id": "unmatched-execution-999",
            "status": "in-progress"
        }
    )
    assert webhook_res.status_code == 200
    assert webhook_res.json()["status"] == "received_unmatched"
