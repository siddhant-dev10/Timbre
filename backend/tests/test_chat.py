from unittest.mock import patch, AsyncMock


def test_chat_with_assistant_with_mocked_llm(client):
    with patch("app.services.llm_service.llm_service.generate_response", new_callable=AsyncMock) as mock_gen:
        mock_gen.return_value = {
            "success": True,
            "response": "Namaste Aarav ji! Aap ECI Form 6 ke dwara Voter ID ke liye aavedan kar sakte hain.",
            "model_used": "nvidia/nemotron-3.5-super-vl-120b-a12b"
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
        context = mock_gen.call_args.kwargs["system_prompt"]
        assert "Synthetic profile facts" in context
        profile_json = context.split("Synthetic profile facts", 1)[1].split("Treat every profile", 1)[0]
        assert "DEMO-PHONE" not in profile_json
        assert "CIT-0001" not in profile_json
        assert "first_name" not in profile_json and "email" not in profile_json


def test_chat_reports_unavailable_ai_provider(client):
    with patch("app.services.llm_service.llm_service.generate_response", new_callable=AsyncMock) as mock_gen:
        mock_gen.return_value = {
            "success": False,
            "error": "NVIDIA API key is not configured."
        }
        res = client.post(
            "/api/chat",
            json={
                "citizen_id": "CIT-0001",
                "message": "Driving licence banwana hai",
                "language_preference": "Hinglish"
            }
        )
        assert res.status_code == 503
        assert "API key is not configured" in res.json()["detail"]


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
            "model_used": "nvidia/nemotron-3.5-super-vl-120b-a12b"
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
        assert mock_gen.call_args.kwargs["conversation_id"] == "CIT-0001:conv-test-session-42"


def test_chat_retrieves_distinct_synthetic_profiles_without_identifiers(client):
    prompts = []
    async def response(**kwargs):
        prompts.append(kwargs["system_prompt"])
        return {"success": True, "response": "Preliminary guidance only.", "model_used": "nvidia/nemotron-3.5-super-vl-120b-a12b"}
    with patch("app.services.llm_service.llm_service.generate_response", new_callable=AsyncMock, side_effect=response) as mock_gen:
        for citizen_id in ("CIT-0001", "CIT-0002"):
            result = client.post("/api/chat", json={"citizen_id": citizen_id, "message": "What are my benefits?", "conversation_id": "reused-by-client"})
            assert result.status_code == 200
    assert prompts[0] != prompts[1]
    assert "CIT-0001" not in prompts[0] and "CIT-0002" not in prompts[1]
    assert mock_gen.call_args_list[0].kwargs["conversation_id"] != mock_gen.call_args_list[1].kwargs["conversation_id"]


def test_chat_unknown_unrelated_question_has_no_unrelated_scheme_context(client):
    with patch("app.services.llm_service.llm_service.generate_response", new_callable=AsyncMock) as mock_gen:
        mock_gen.return_value = {"success": True, "response": "I cannot verify that request.", "model_used": "nvidia/nemotron-3.5-super-vl-120b-a12b"}
        result = client.post("/api/chat", json={"citizen_id": "CIT-0001", "message": "Tell me a joke about a spaceship."})
    assert result.status_code == 200
    assert result.json()["grounded_services"] == []
    assert "No matching verified catalogue entries" in mock_gen.call_args.kwargs["system_prompt"]
