from unittest.mock import patch, AsyncMock


def test_chat_with_assistant_with_mocked_llm(client):
    with patch("app.services.llm_service.llm_service.generate_response", new_callable=AsyncMock) as mock_gen:
        mock_gen.return_value = {
            "success": True,
            "response": "Namaste Aarav ji! Aap ECI Form 6 ke dwara Voter ID ke liye aavedan kar sakte hain.",
            "model_used": "qwen3.5:9b"
        }
        res = client.post(
            "/api/chat",
            json={
                "citizen_id": "CIT-0001",
                "message": "Mujhe Voter ID card kaise milega?",
                "language_preference": "Hinglish"
            }
        )
        assert res.status_code == 200
        data = res.json()
        assert data["citizen_id"] == "CIT-0001"
        assert "ECI Form 6" in data["answer"]
        assert len(data["grounded_services"]) > 0
        assert data["grounded_services"][0]["id"] == "SVC-VOTER-ID"


def test_chat_fallback_when_llm_unavailable(client):
    with patch("app.services.llm_service.llm_service.generate_response", new_callable=AsyncMock) as mock_gen:
        mock_gen.return_value = {
            "success": False,
            "response": "Local LLM is currently initializing or downloading.",
            "error": "Connection refused"
        }
        res = client.post(
            "/api/chat",
            json={
                "citizen_id": "CIT-0001",
                "message": "Driving licence banwana hai",
                "language_preference": "Hinglish"
            }
        )
        assert res.status_code == 200
        data = res.json()
        assert data["citizen_id"] == "CIT-0001"
        assert "preliminary guidance" in data["answer"].lower()
        assert data["llm_model"] == "catalogue-grounded-fallback"


def test_chat_invalid_citizen_id(client):
    res = client.post(
        "/api/chat",
        json={
            "citizen_id": "CIT-NONEXISTENT",
            "message": "Hello"
        }
    )
    assert res.status_code == 404


def test_chat_multiturn_conversation_id(client):
    with patch("app.services.llm_service.llm_service.generate_response", new_callable=AsyncMock) as mock_gen:
        mock_gen.return_value = {
            "success": True,
            "response": "Haan, aapke documents verify hone par voter slip milegi.",
            "model_used": "qwen3.5:9b"
        }
        res = client.post(
            "/api/chat",
            json={
                "citizen_id": "CIT-0001",
                "message": "Aur kya documents lagenge?",
                "conversation_id": "conv-test-session-42",
                "language_preference": "Hinglish"
            }
        )
        assert res.status_code == 200
        data = res.json()
        assert data["conversation_id"] == "conv-test-session-42"
        assert mock_gen.call_args.kwargs["conversation_id"] == "conv-test-session-42"
