from unittest.mock import patch


def test_root_endpoint(client):
    res = client.get("/")
    assert res.status_code == 200
    data = res.json()
    assert data["project"] == "Timbre"
    assert data["docs_url"] == "/docs"
    assert data["health_url"] == "/health"


def test_health_healthy(client):
    with patch("app.services.llm_service.llm_service.check_availability") as mock_llm:
        mock_llm.return_value = {
            "available": True,
            "target_model_ready": True,
            "target_model": "qwen3.5:9b",
            "installed_models": ["qwen3.5:9b"],
            "status": "healthy"
        }
        res = client.get("/health")
        assert res.status_code == 200
        data = res.json()
        assert data["status"] == "ok"
        assert data["database"]["status"] == "healthy"
        assert data["local_llm"]["status"] == "healthy"
        assert data["real_calls_enabled"] is False


def test_health_llm_degraded_when_offline(client):
    with patch("app.services.llm_service.llm_service.check_availability") as mock_llm:
        mock_llm.return_value = {
            "available": False,
            "target_model_ready": False,
            "target_model": "qwen3.5:9b",
            "installed_models": [],
            "status": "unavailable",
            "error": "Connection refused"
        }
        res = client.get("/health")
        assert res.status_code == 200
        data = res.json()
        assert data["status"] == "degraded"
        assert data["local_llm"]["status"] == "unavailable"


def test_health_api_v1_prefix(client):
    res = client.get("/api/v1/health")
    assert res.status_code == 200
    data = res.json()
    assert "version" in data
