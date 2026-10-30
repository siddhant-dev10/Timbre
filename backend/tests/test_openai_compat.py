"""Unit and Integration Tests for OpenAI-Compatible Custom LLM Bridge for Bolna."""
import json
import pytest
from app.config import settings


def _auth_headers():
    key = settings.TIMBRE_LLM_API_KEY or settings.BOLNA_WEBHOOK_SECRET
    return {"Authorization": f"Bearer {key}"} if key else {}


def test_models_endpoint(client):
    """GET /v1/models returns standard OpenAI models object listing timbre-voice-agent."""
    res = client.get("/v1/models", headers=_auth_headers())
    assert res.status_code == 200
    data = res.json()
    assert data["object"] == "list"
    assert len(data["data"]) >= 1
    assert data["data"][0]["id"] == "timbre-voice-agent"


def test_root_models_endpoint(client):
    """GET /models directly without /v1 prefix also succeeds."""
    res = client.get("/models", headers=_auth_headers())
    assert res.status_code == 200
    data = res.json()
    assert data["data"][0]["id"] == "timbre-voice-agent"


def test_bolna_integration_spec_endpoint(client):
    """GET /v1/integration-spec returns exact Bolna configuration parameters."""
    res = client.get("/v1/integration-spec?public_url=https://demo.timbre.test")
    assert res.status_code == 200
    spec = res.json()
    assert "bolna_custom_llm_config" in spec
    llm_cfg = spec["bolna_custom_llm_config"]
    assert llm_cfg["base_url"] == "https://demo.timbre.test/v1"
    assert llm_cfg["model"] == "timbre-voice-agent"
    assert llm_cfg["stream"] is True
    assert "bolna_webhook_config" in spec


def test_chat_completions_json_mode(client):
    """POST /v1/chat/completions returns standard OpenAI JSON format when stream=False."""
    res = client.post(
        "/v1/chat/completions",
        headers=_auth_headers(),
        json={
            "model": "timbre-voice-agent",
            "messages": [
                {"role": "user", "content": "Namaste, mujhe Ayushman Bharat card ke bare me batayein."}
            ],
            "stream": False,
        },
    )
    assert res.status_code == 200
    assert "application/json" in res.headers.get("content-type", "")
    data = res.json()
    assert data["object"] == "chat.completion"
    assert len(data["choices"]) == 1
    assert data["choices"][0]["message"]["role"] == "assistant"
    content = data["choices"][0]["message"]["content"]
    assert len(content) > 0
    assert "usage" in data
    assert data["usage"]["total_tokens"] > 0


def test_chat_completions_streaming_sse_mode(client):
    """POST /v1/chat/completions returns text/event-stream with SSE chunks when stream=True."""
    res = client.post(
        "/v1/chat/completions",
        headers=_auth_headers(),
        json={
            "model": "timbre-voice-agent",
            "messages": [
                {"role": "user", "content": "Kisan Credit Card kaise banaye?"}
            ],
            "stream": True,
        },
    )
    assert res.status_code == 200
    assert "text/event-stream" in res.headers.get("content-type", "")
    
    # Verify Server-Sent Events structure
    raw_lines = res.text.strip().split("\n\n")
    assert len(raw_lines) >= 3  # First chunk, content chunk(s), stop chunk, and [DONE]
    
    chunks = []
    saw_done = False
    for line in raw_lines:
        line = line.strip()
        if not line:
            continue
        assert line.startswith("data: ")
        data_str = line.replace("data: ", "", 1).strip()
        if data_str == "[DONE]":
            saw_done = True
            break
        chunk = json.loads(data_str)
        assert chunk["object"] == "chat.completion.chunk"
        assert len(chunk["choices"]) == 1
        chunks.append(chunk)

    assert saw_done is True
    assert len(chunks) >= 2


def test_chat_completions_stop_intent_hindi(client):
    """POST /v1/chat/completions detects Devanagari Hindi stop intent."""
    res = client.post(
        "/v1/chat/completions",
        headers=_auth_headers(),
        json={
            "model": "timbre-voice-agent",
            "messages": [
                {"role": "user", "content": "रुकिए, मुझे बात नहीं करनी, फोन काटो"}
            ],
            "stream": False,
        },
    )
    assert res.status_code == 200
    content = res.json()["choices"][0]["message"]["content"]
    assert "कॉल यहीं समाप्त" in content or "धन्यवाद" in content


def test_chat_completions_stop_intent_hinglish(client):
    """POST /v1/chat/completions detects Romanized Hinglish stop intent."""
    res = client.post(
        "/v1/chat/completions",
        headers=_auth_headers(),
        json={
            "model": "timbre-voice-agent",
            "messages": [
                {"role": "user", "content": "Ruko abhi phone kato mujhe nahi chahiye"}
            ],
            "stream": False,
        },
    )
    assert res.status_code == 200
    content = res.json()["choices"][0]["message"]["content"]
    assert "कॉल यहीं समाप्त" in content or "धन्यवाद" in content


def test_chat_completions_empty_message_handling(client):
    """POST /v1/chat/completions responds politely when speech is empty or inaudible."""
    res = client.post(
        "/v1/chat/completions",
        headers=_auth_headers(),
        json={
            "model": "timbre-voice-agent",
            "messages": [
                {"role": "user", "content": "   "}
            ],
            "stream": False,
        },
    )
    assert res.status_code == 200
    content = res.json()["choices"][0]["message"]["content"]
    assert "आवाज़ स्पष्ट नहीं आई" in content or "दोहरा" in content


def test_chat_completions_authentication_enforcement(client, monkeypatch):
    """POST /v1/chat/completions rejects unauthenticated calls when BOLNA_WEBHOOK_SECRET is set."""
    monkeypatch.setattr(settings, "BOLNA_WEBHOOK_SECRET", "super-secret-telephony-token-12345")

    # 1. Missing header -> 401
    res_unauth = client.post(
        "/v1/chat/completions",
        json={
            "model": "timbre-voice-agent",
            "messages": [{"role": "user", "content": "Hello"}],
        },
    )
    assert res_unauth.status_code == 401

    # 2. Invalid header -> 401
    res_wrong = client.post(
        "/v1/chat/completions",
        headers={"Authorization": "Bearer wrong-token"},
        json={
            "model": "timbre-voice-agent",
            "messages": [{"role": "user", "content": "Hello"}],
        },
    )
    assert res_wrong.status_code == 401

    # 3. Valid header -> 200
    res_ok = client.post(
        "/v1/chat/completions",
        headers={"Authorization": "Bearer super-secret-telephony-token-12345"},
        json={
            "model": "timbre-voice-agent",
            "messages": [{"role": "user", "content": "Voter ID card Form 6"}],
        },
    )
    assert res_ok.status_code == 200


def test_chat_completions_dedicated_timbre_llm_api_key(client, monkeypatch):
    """POST /v1/chat/completions enforces dedicated TIMBRE_LLM_API_KEY bearer token."""
    monkeypatch.setattr(settings, "TIMBRE_LLM_API_KEY", "dedicated-timbre-token-98765")
    monkeypatch.setattr(settings, "BOLNA_WEBHOOK_SECRET", "")

    # 1. Missing header -> 401
    res_unauth = client.post(
        "/v1/chat/completions",
        json={
            "model": "timbre-voice-agent",
            "messages": [{"role": "user", "content": "Hello"}],
        },
    )
    assert res_unauth.status_code == 401
    assert "Invalid or missing Authorization header" in res_unauth.json()["detail"]

    # 2. Invalid header -> 401
    res_wrong = client.post(
        "/v1/chat/completions",
        headers={"Authorization": "Bearer wrong-timbre-key"},
        json={
            "model": "timbre-voice-agent",
            "messages": [{"role": "user", "content": "Hello"}],
        },
    )
    assert res_wrong.status_code == 401

    # 3. Valid bearer token -> 200
    res_ok = client.post(
        "/v1/chat/completions",
        headers={"Authorization": "Bearer dedicated-timbre-token-98765"},
        json={
            "model": "timbre-voice-agent",
            "messages": [{"role": "user", "content": "Kisan Credit Card"}],
        },
    )
    assert res_ok.status_code == 200


def test_get_single_model_endpoint(client):
    """GET /v1/models/{model_id} returns model metadata."""
    res = client.get("/v1/models/timbre-voice-agent", headers=_auth_headers())
    assert res.status_code == 200
    data = res.json()
    assert data["object"] == "model"
    assert data["id"] == "timbre-voice-agent"


def test_chat_completions_list_content_support(client):
    """POST /v1/chat/completions parses message content when passed as list of text parts."""
    res = client.post(
        "/v1/chat/completions",
        headers=_auth_headers(),
        json={
            "model": "timbre-voice-agent",
            "messages": [
                {
                    "role": "user",
                    "content": [{"type": "text", "text": "Ayushman Bharat card ke bare me batayein"}],
                }
            ],
            "stream": False,
        },
    )
    assert res.status_code == 200
    assert len(res.json()["choices"][0]["message"]["content"]) > 0


def test_timbre_llm_api_key_env_loading(monkeypatch):
    """Verifies that pydantic Settings correctly binds TIMBRE_LLM_API_KEY from environment and .env file."""
    from pydantic_settings import BaseSettings, SettingsConfigDict
    import tempfile
    from pathlib import Path

    monkeypatch.delenv("TIMBRE_LLM_API_KEY", raising=False)

    with tempfile.NamedTemporaryFile("w", delete=False) as f:
        f.write("TIMBRE_LLM_API_KEY=audit-sample-token-42\n")
        f_path = f.name

    class TestSettings(BaseSettings):
        model_config = SettingsConfigDict(env_file=f_path, extra="ignore")
        TIMBRE_LLM_API_KEY: str = ""

    loaded = TestSettings()
    assert loaded.TIMBRE_LLM_API_KEY == "audit-sample-token-42"
    Path(f_path).unlink()


def test_models_authentication_enforcement(client, monkeypatch):
    """GET /v1/models and /v1/models/{model_id} reject missing or invalid Bearer tokens when TIMBRE_LLM_API_KEY is configured."""
    monkeypatch.setattr(settings, "TIMBRE_LLM_API_KEY", "models-auth-token-77777")
    monkeypatch.setattr(settings, "BOLNA_WEBHOOK_SECRET", "")

    # 1. Missing header on /v1/models -> 401
    res_list_unauth = client.get("/v1/models")
    assert res_list_unauth.status_code == 401
    assert "Invalid or missing Authorization header" in res_list_unauth.json()["detail"]

    # 2. Invalid header on /v1/models -> 401
    res_list_wrong = client.get("/v1/models", headers={"Authorization": "Bearer bad-token"})
    assert res_list_wrong.status_code == 401

    # 3. Valid header on /v1/models -> 200
    res_list_ok = client.get("/v1/models", headers={"Authorization": "Bearer models-auth-token-77777"})
    assert res_list_ok.status_code == 200
    assert res_list_ok.json()["object"] == "list"

    # 4. Missing header on /v1/models/{model_id} -> 401
    res_single_unauth = client.get("/v1/models/timbre-voice-agent")
    assert res_single_unauth.status_code == 401

    # 5. Invalid header on /v1/models/{model_id} -> 401
    res_single_wrong = client.get("/v1/models/timbre-voice-agent", headers={"Authorization": "Bearer bad-token"})
    assert res_single_wrong.status_code == 401

    # 6. Valid header on /v1/models/{model_id} -> 200
    res_single_ok = client.get(
        "/v1/models/timbre-voice-agent",
        headers={"Authorization": "Bearer models-auth-token-77777"},
    )
    assert res_single_ok.status_code == 200
    assert res_single_ok.json()["id"] == "timbre-voice-agent"
