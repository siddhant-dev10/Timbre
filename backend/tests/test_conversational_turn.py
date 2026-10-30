"""End-to-end tests for the conversational turn pipeline and call session management."""
import pytest
from unittest.mock import AsyncMock, patch

from app.models.citizen import Citizen
from app.services.session_service import session_manager


@pytest.fixture
def test_citizen(db):
    citizen = db.query(Citizen).filter(Citizen.id == "CIT-0001").first()
    return citizen


def test_turn_pipeline_text_input(client, test_citizen):
    # Test turn with direct text input
    with patch("app.services.llm_service.llm_service.generate_response", new_callable=AsyncMock) as mock_llm:
        mock_llm.return_value = {
            "success": True,
            "response": "नमस्ते आरव! 18 वर्ष की आयु होने पर आप वोटर आईडी कार्ड के लिए आवेदन कर सकते हैं। क्या आप फॉर्म 6 की प्रक्रिया जानना चाहते हैं?",
            "model_used": "nvidia/nemotron-3.5-super-vl-120b-a12b",
        }

        response = client.post(
            "/api/v1/voice/turn",
            json={
                "citizen_id": "CIT-0001",
                "text": "नमस्ते, मैं 18 साल का हो गया हूँ। मुझे क्या करना चाहिए?",
                "language": "Hindi",
                "synthesize_voice": False,
            },
        )

        assert response.status_code == 200
        data = response.json()
        assert data["turn_index"] == 1
        assert "वोटर आईडी" in data["ai_response"]
        assert data["language"] == "Hindi"
        assert data["is_unclear"] is False
        assert data["stop_requested"] is False
        assert data["session_status"] == "ACTIVE"
        assert "llm_ms" in data["latencies_ms"]
        assert "total_turn_ms" in data["latencies_ms"]


def test_turn_pipeline_multi_turn_history(client, test_citizen):
    session_id = "test-multiturn-session-123"

    with patch("app.services.llm_service.llm_service.generate_response", new_callable=AsyncMock) as mock_llm:
        # Turn 1
        mock_llm.return_value = {
            "success": True,
            "response": "नमस्ते! मैं टिमब्रे एआई सहायक हूँ। आप किस सरकारी योजना के बारे में पूछना चाहते हैं?",
            "model_used": "nvidia/nemotron-3.5-super-vl-120b-a12b",
        }
        res1 = client.post(
            "/api/v1/voice/turn",
            json={
                "citizen_id": "CIT-0001",
                "session_id": session_id,
                "text": "नमस्ते, क्या आप मेरी मदद कर सकते हैं?",
                "language": "Hindi",
                "synthesize_voice": False,
            },
        )
        assert res1.status_code == 200
        assert res1.json()["turn_index"] == 1

        # Turn 2: Follow-up question
        mock_llm.return_value = {
            "success": True,
            "response": "वोटर आईडी के लिए आपको आयु प्रमाण और निवास प्रमाण की आवश्यकता होगी। क्या आपके पास ये दस्तावेज़ उपलब्ध हैं?",
            "model_used": "nvidia/nemotron-3.5-super-vl-120b-a12b",
        }
        res2 = client.post(
            "/api/v1/voice/turn",
            json={
                "citizen_id": "CIT-0001",
                "session_id": session_id,
                "text": "हाँ, मुझे वोटर आईडी के दस्तावेज़ बताइए।",
                "language": "Hindi",
                "synthesize_voice": False,
            },
        )
        assert res2.status_code == 200
        assert res2.json()["turn_index"] == 2
        assert "दस्तावेज़" in res2.json()["ai_response"]

        # Check session history endpoint
        hist_res = client.get(f"/api/v1/voice/turn/{session_id}")
        assert hist_res.status_code == 200
        history = hist_res.json()
        assert history["turn_count"] == 2
        assert history["status"] == "ACTIVE"
        assert len(history["turns"]) == 2


def test_turn_pipeline_stop_request_terminates(client, test_citizen):
    response = client.post(
        "/api/v1/voice/turn",
        json={
            "citizen_id": "CIT-0001",
            "text": "बस रुको, मुझे अब बात नहीं करनी, फोन काटो।",
            "language": "Hindi",
            "synthesize_voice": False,
        },
    )
    assert response.status_code == 200
    data = response.json()
    assert data["stop_requested"] is True
    assert data["session_status"] == "TERMINATED_BY_USER"
    assert "समाप्त" in data["ai_response"]


def test_turn_pipeline_unclear_audio_clarification(client, test_citizen):
    # Simulated unclear input (empty or unintelligible)
    response = client.post(
        "/api/v1/voice/turn",
        json={
            "citizen_id": "CIT-0001",
            "text": "",  # Empty/unclear input
            "language": "Hindi",
            "synthesize_voice": False,
        },
    )
    assert response.status_code == 200
    data = response.json()
    assert data["is_unclear"] is True
    assert "स्पष्ट नहीं आई" in data["ai_response"]
    assert "दोहरा" in data["ai_response"]


def test_turn_session_termination_endpoint(client, test_citizen):
    session_id = "test-term-sess-456"
    client.post(
        "/api/v1/voice/turn",
        json={
            "citizen_id": "CIT-0001",
            "session_id": session_id,
            "text": "नमस्ते",
            "synthesize_voice": False,
        },
    )

    term_res = client.post(f"/api/v1/voice/turn/{session_id}/terminate")
    assert term_res.status_code == 200
    assert term_res.json()["status"] == "COMPLETED"


def test_turn_with_elevenlabs_tts_integration(client, test_citizen):
    fake_audio_bytes = b"ID3\x03\x00\x00\x00" + b"\x00" * 200
    with patch("app.services.llm_service.llm_service.generate_response", new_callable=AsyncMock) as mock_llm, \
         patch("app.services.elevenlabs_service.elevenlabs_service.synthesize_speech", new_callable=AsyncMock) as mock_tts, \
         patch("app.services.elevenlabs_service.elevenlabs_service.is_configured", return_value=True):

        mock_llm.return_value = {
            "success": True,
            "response": "नमस्ते! मैं आपकी सहायता के लिए तैयार हूँ।",
            "model_used": "nvidia/nemotron-3.5-super-vl-120b-a12b",
        }
        mock_tts.return_value = fake_audio_bytes

        response = client.post(
            "/api/v1/voice/turn",
            json={
                "citizen_id": "CIT-0001",
                "text": "नमस्ते",
                "language": "Hindi",
                "synthesize_voice": True,
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert data["audio_url"] is not None
        assert "aud-call-" in data["audio_url"]
        assert "tts_ms" in data["latencies_ms"]
        assert data["tts_error"] is None
