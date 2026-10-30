from unittest.mock import patch


def test_root_endpoint(client):
    res = client.get("/")
    assert res.status_code == 200
    data = res.json()
    assert data["project"] == "Timbre"
    assert data["docs_url"] == "/docs"
    assert data["health_url"] == "/health"


def test_health_healthy(client):
    with patch("app.services.llm_service.llm_service.check_availability") as mock_llm, patch(
        "app.services.elevenlabs_service.elevenlabs_service.check_health"
    ) as mock_tts:
        mock_llm.return_value = {
            "available": True,
            "provider": "NVIDIA Nemotron API",
            "model": "nvidia/nemotron-3.5-super-vl-120b-a12b",
            "status": "healthy"
        }
        mock_tts.return_value = {"configured": True, "status": "healthy", "model_id": "eleven_multilingual_v2"}
        res = client.get("/health")
        assert res.status_code == 200
        data = res.json()
        assert data["status"] == "ok"
        assert data["database"]["status"] == "healthy"
        assert data["ai_provider"]["status"] == "healthy"
        assert data["real_calls_enabled"] is False


def test_health_llm_degraded_when_offline(client):
    with patch("app.services.llm_service.llm_service.check_availability") as mock_llm:
        mock_llm.return_value = {
            "available": False,
            "provider": "NVIDIA Nemotron API",
            "model": "nvidia/nemotron-3.5-super-vl-120b-a12b",
            "status": "credentials_pending",
        }
        res = client.get("/health")
        assert res.status_code == 200
        data = res.json()
        assert data["status"] == "degraded"
        assert data["ai_provider"]["status"] == "credentials_pending"


def test_health_does_not_treat_configured_credentials_as_live_connectivity(client):
    with patch("app.services.llm_service.llm_service.check_availability") as mock_llm, patch(
        "app.services.elevenlabs_service.elevenlabs_service.check_health"
    ) as mock_tts:
        mock_llm.return_value = {
            "available": True,
            "provider": "NVIDIA Nemotron API",
            "model": "nvidia/nemotron-3.5-super-vl-120b-a12b",
            "status": "configured",
        }
        mock_tts.return_value = {"configured": True, "status": "configured", "model_id": "eleven_multilingual_v2"}
        response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "degraded"
    assert response.json()["ai_provider"]["status"] == "configured"
    assert response.json()["elevenlabs_tts"]["status"] == "configured"


def test_health_api_v1_prefix(client):
    res = client.get("/api/v1/health")
    assert res.status_code == 200
    data = res.json()
    assert "version" in data


def test_health_with_live_connectivity_check_healthy(client):
    with patch("app.services.llm_service.llm_service.check_availability") as mock_llm, patch(
        "app.services.elevenlabs_service.elevenlabs_service.check_health_async"
    ) as mock_tts:
        mock_llm.return_value = {
            "available": True,
            "provider": "NVIDIA Nemotron API",
            "model": "nvidia/nemotron-3.5-super-vl-120b-a12b",
            "status": "healthy",
            "details": "NVIDIA API connected. Model nvidia/nemotron-3.5-super-vl-120b-a12b verified.",
        }
        mock_tts.return_value = {
            "configured": True,
            "status": "healthy",
            "provider": "ElevenLabs",
            "model_id": "eleven_multilingual_v2",
            "details": "ElevenLabs connected. Voice 'Timbre' verified.",
        }
        res = client.get("/health?check_connectivity=true")
        assert res.status_code == 200
        data = res.json()
        assert data["status"] == "ok"
        assert data["ai_provider"]["status"] == "healthy"
        assert data["elevenlabs_tts"]["status"] == "healthy"
        mock_llm.assert_called_once_with(check_connectivity=True)
        mock_tts.assert_called_once_with(check_connectivity=True)


def test_health_with_live_connectivity_check_failure(client):
    with patch("app.services.llm_service.llm_service.check_availability") as mock_llm, patch(
        "app.services.elevenlabs_service.elevenlabs_service.check_health_async"
    ) as mock_tts:
        mock_llm.return_value = {
            "available": False,
            "provider": "NVIDIA Nemotron API",
            "model": "nvidia/nemotron-3.5-super-vl-120b-a12b",
            "status": "unauthorized",
            "details": "NVIDIA authentication failed: API key rejected (HTTP 401).",
        }
        mock_tts.return_value = {
            "configured": True,
            "status": "healthy",
            "model_id": "eleven_multilingual_v2",
        }
        res = client.get("/health?check_connectivity=true")
        assert res.status_code == 200
        data = res.json()
        assert data["status"] == "degraded"
        assert data["ai_provider"]["status"] == "unauthorized"

