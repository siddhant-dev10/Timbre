import base64
from unittest.mock import AsyncMock, patch


MOCK_MP3 = b"\xff\xfb\x90dMOCK-TIMBRE-AUDIO"


def test_controlled_synthetic_event_chat_tts_and_call_rehearsal(client):
    llm_outputs = [
        "A simulated event produced preliminary local matches; please verify them on official sources.",
        "Voter registration details need official verification before you act.",
    ]
    with patch("app.services.llm_service.llm_service.generate_response", new_callable=AsyncMock) as llm, \
         patch("app.services.elevenlabs_service.elevenlabs_service.is_configured", return_value=True), \
         patch("app.services.elevenlabs_service.elevenlabs_service.synthesize_speech", new_callable=AsyncMock, return_value=MOCK_MP3) as tts:
        llm.side_effect = [
            {"success": True, "response": llm_outputs[0], "model_used": "nvidia/nemotron-3.5-super-vl-120b-a12b"},
            {"success": True, "response": llm_outputs[1], "model_used": "nvidia/nemotron-3.5-super-vl-120b-a12b"},
        ]
        simulation = client.post("/api/simulations", json={"citizen_id": "CIT-0001", "trigger_event": "MILESTONE_AGE_18"})
        assert simulation.status_code == 200
        chat = client.post("/api/chat", json={
            "citizen_id": "CIT-0001",
            "message": "Mujhe voter ID ke documents kaise verify karne chahiye?",
            "conversation_id": "controlled-demo",
            "synthesize_voice": True,
        })
        assert chat.status_code == 200
        assert chat.json()["audio_base64"]
        assert base64.b64decode(chat.json()["audio_base64"]) == MOCK_MP3
        rehearsal = client.post("/api/calls/dry-run", json={
            "citizen_id": "CIT-0001",
            "trigger_event": "CONTROLLED_SYNTHETIC_DEMO",
            "test_recipient_number": "9999999999",
            "recipient_has_consented": True,
        })
    assert rehearsal.status_code == 201
    assert rehearsal.json()["is_real_call"] is False
    assert rehearsal.json()["recipient_phone"] == "***9999"
    assert llm.await_count == 2
    tts.assert_awaited_once()
