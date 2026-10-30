import copy
import httpx
import pytest

from app.scripts.update_bolna_agent import (
    get_agent_endpoint,
    get_current_agent_config,
    prepare_patch_payload,
    prepare_update_payload,
    redact_payload,
    apply_agent_update,
    verify_saved_agent_config,
)


@pytest.fixture
def sample_bolna_v2_agent():
    return {
        "id": "dd390081-993d-4559-a5ff-81f36f9c70c6",
        "agent_name": "Timbre civic assistance",
        "agent_status": "processed",
        "agent_welcome_message": "नमस्ते, मैं Timbre की तरफ से बात कर रही हूँ.",
        "agent_type": "simple_llm_agent",
        "webhook_url": None,
        "webhook_headers": None,
        "created_at": "2026-10-29T17:02:14.992028",
        "updated_at": "2026-10-29T19:12:22.703698",
        "created_by": "user-uuid-123",
        "parent_agent_id": None,
        "source_agent_id": None,
        "tasks": [
            {
                "task_type": "conversation",
                "toolchain": {"execution": "parallel", "pipelines": [["transcriber", "llm", "synthesizer"]]},
                "task_config": {
                    "hangup_after_silence": 10,
                    "incremental_delay": 400,
                    "number_of_words_for_interruption": 2,
                    "call_terminate": 90,
                    "ambient_noise": False,
                },
                "tools_config": {
                    "transcriber": {
                        "provider": "deepgram",
                        "model": "nova-3",
                        "language": "hi",
                        "encoding": "linear16",
                        "stream": True,
                    },
                    "synthesizer": {
                        "provider": "elevenlabs",
                        "stream": True,
                        "provider_config": {
                            "voice": "Riya Rao - Confident and Professional",
                            "voice_id": "mfMM3ijQgz8QtMeKifko",
                            "model": "eleven_turbo_v2_5",
                        },
                    },
                    "llm_agent": {
                        "agent_type": "simple_llm_agent",
                        "llm_config": {
                            "model": "timbre-voice-agent",
                            "base_url": "https://enticing-astonish-going.ngrok-free.dev/v1",
                            "family": "openai",
                            "provider": "custom",
                            "api_key": None,
                        },
                    },
                },
            }
        ],
        "agent_prompts": {
            "task_1": {
                "system_prompt": "You are Timbre, a civic assistant for Rajasthan government services." * 100
            }
        },
        "composition_by_language": {
            "en": [],
            "hi": [{"type": "text", "text": f"नमस्ते {i}"} for i in range(179)],
        },
    }


# =====================================================================
# 1. Endpoint Selection Tests
# =====================================================================

def test_endpoint_selection_targets_v2():
    agent_id = "dd390081-993d-4559-a5ff-81f36f9c70c6"
    base_url = "https://api.bolna.ai"
    endpoint = get_agent_endpoint(base_url, agent_id)

    assert endpoint == f"https://api.bolna.ai/v2/agent/{agent_id}"
    assert "/agent/v2" not in endpoint
    # Ensure legacy deprecated endpoint is never generated
    assert endpoint != f"https://api.bolna.ai/agent/{agent_id}"


def test_get_current_agent_config_calls_v2_endpoint(monkeypatch, sample_bolna_v2_agent):
    recorded_urls = []

    def fake_get(url, headers=None):
        recorded_urls.append(url)
        return httpx.Response(200, json=sample_bolna_v2_agent, request=httpx.Request("GET", url))

    client = httpx.Client()
    monkeypatch.setattr(client, "get", fake_get)

    data = get_current_agent_config(client, "test-agent-id", base_url="https://api.bolna.ai")
    assert len(recorded_urls) == 1
    assert recorded_urls[0] == "https://api.bolna.ai/v2/agent/test-agent-id"
    assert data["agent_name"] == "Timbre civic assistance"


# =====================================================================
# 2. Method Selection: PATCH vs PUT Tests
# =====================================================================

def test_prepare_patch_payload_targets_only_supported_fields(sample_bolna_v2_agent):
    secret_token = "my-webhook-secret-token"
    tunnel = "https://enticing-astonish-going.ngrok-free.dev"

    patch_payload = prepare_patch_payload(
        sample_bolna_v2_agent,
        webhook_secret=secret_token,
        tunnel_base_url=tunnel,
    )

    # In PATCH, only shallow attributes are valid
    assert "webhook_url" in patch_payload
    assert patch_payload["webhook_url"] == f"{tunnel}/api/webhooks/bolna?token={secret_token}"

    # Critical: PATCH MUST NOT include tasks or tools_config (they are ignored by Bolna)
    assert "tasks" not in patch_payload
    assert "tools_config" not in patch_payload
    assert "agent_config" not in patch_payload


def test_prepare_update_payload_preserves_all_179_hindi_composition_nodes(sample_bolna_v2_agent):
    secret_llm_key = "super-secret-timbre-llm-token-12345"
    secret_wh_secret = "super-secret-wh-token-67890"
    tunnel = "https://enticing-astonish-going.ngrok-free.dev"

    payload = prepare_update_payload(
        sample_bolna_v2_agent,
        llm_api_key=secret_llm_key,
        webhook_secret=secret_wh_secret,
        tunnel_base_url=tunnel,
    )

    # Top-level keys must be agent_config, agent_prompts, composition_by_language
    assert "agent_config" in payload
    assert "agent_prompts" in payload
    assert "composition_by_language" in payload

    # Exactly 179 Hindi composition nodes must be preserved
    assert len(payload["composition_by_language"]["hi"]) == 179
    assert payload["composition_by_language"]["hi"][0]["text"] == "नमस्ते 0"
    assert payload["composition_by_language"]["hi"][178]["text"] == "नमस्ते 178"

    # Entire system prompt preserved
    assert len(payload["agent_prompts"]["task_1"]["system_prompt"]) > 5000

    cfg = payload["agent_config"]

    # Read-only server-managed fields must be stripped from agent_config
    for stripped_field in [
        "id", "created_at", "updated_at", "agent_status", "created_by", "parent_agent_id", "source_agent_id"
    ]:
        assert stripped_field not in cfg

    # Core metadata preserved
    assert cfg["agent_name"] == "Timbre civic assistance"
    assert cfg["agent_type"] == "simple_llm_agent"
    assert cfg["agent_welcome_message"] == "नमस्ते, मैं Timbre की तरफ से बात कर रही हूँ."

    # Transcriber & Synthesizer preserved
    task = cfg["tasks"][0]
    assert task["tools_config"]["transcriber"]["provider"] == "deepgram"
    assert task["tools_config"]["transcriber"]["model"] == "nova-3"
    assert task["tools_config"]["synthesizer"]["provider"] == "elevenlabs"
    assert task["tools_config"]["synthesizer"]["provider_config"]["voice"] == "Riya Rao - Confident and Professional"

    # Targeted fields correctly updated
    llm_cfg = task["tools_config"]["llm_agent"]["llm_config"]
    assert llm_cfg["api_key"] == secret_llm_key
    assert llm_cfg["base_url"] == f"{tunnel}/v1"
    assert llm_cfg["model"] == "timbre-voice-agent"

    assert cfg["webhook_url"] == f"{tunnel}/api/webhooks/bolna?token={secret_wh_secret}"
    assert cfg["webhook_headers"] == {"X-Timbre-Webhook-Secret": secret_wh_secret}


def test_prepare_update_payload_rejects_empty_tasks(sample_bolna_v2_agent):
    invalid = copy.deepcopy(sample_bolna_v2_agent)
    invalid["tasks"] = []
    with pytest.raises(ValueError, match="no tasks"):
        prepare_update_payload(invalid, "key", "sec")


def test_apply_agent_update_dispatches_put(monkeypatch):
    recorded_calls = []

    def fake_put(url, headers=None, json=None):
        recorded_calls.append((url, headers, json))
        return httpx.Response(200, json={"status": "success"}, request=httpx.Request("PUT", url))

    client = httpx.Client()
    monkeypatch.setattr(client, "put", fake_put)

    dummy_payload = {"agent_config": {"agent_name": "Timbre"}, "agent_prompts": {}}
    resp = apply_agent_update(
        client,
        agent_id="test-agent-id",
        payload=dummy_payload,
        method="PUT",
        base_url="https://api.bolna.ai",
        api_key="bolna-test-key",
    )

    assert resp.status_code == 200
    assert len(recorded_calls) == 1
    url, headers, payload = recorded_calls[0]
    assert url == "https://api.bolna.ai/v2/agent/test-agent-id"
    assert headers["Authorization"] == "Bearer bolna-test-key"
    assert payload == dummy_payload


def test_apply_agent_update_dispatches_patch(monkeypatch):
    recorded_calls = []

    def fake_patch(url, headers=None, json=None):
        recorded_calls.append((url, headers, json))
        return httpx.Response(200, json={"message": "success", "state": "updated"}, request=httpx.Request("PATCH", url))

    client = httpx.Client()
    monkeypatch.setattr(client, "patch", fake_patch)

    patch_payload = {"webhook_url": "https://example.com/webhook"}
    resp = apply_agent_update(
        client,
        agent_id="test-agent-id",
        payload=patch_payload,
        method="PATCH",
        base_url="https://api.bolna.ai",
        api_key="bolna-test-key",
    )

    assert resp.status_code == 200
    assert len(recorded_calls) == 1
    url, headers, payload = recorded_calls[0]
    assert url == "https://api.bolna.ai/v2/agent/test-agent-id"
    assert payload == patch_payload


def test_apply_agent_update_rejects_invalid_method(monkeypatch):
    client = httpx.Client()
    with pytest.raises(ValueError, match="Unsupported HTTP method"):
        apply_agent_update(client, "id", {}, method="POST")


# =====================================================================
# 3. Safe Error Handling & Failed Updates Tests (No Leaked Secrets)
# =====================================================================

@pytest.mark.parametrize("status_code,err_body", [
    (400, "Validation error: unsupported field or bad schema"),
    (401, "Unauthorized: invalid bolna api key"),
    (404, "Agent not found"),
    (500, "Internal Server Error"),
])
def test_failed_update_safe_error_handling(monkeypatch, status_code, err_body):
    secret_key = "super-secret-auth-key-never-leak"

    def fake_failing_put(url, headers=None, json=None):
        return httpx.Response(status_code, text=err_body, request=httpx.Request("PUT", url))

    client = httpx.Client()
    monkeypatch.setattr(client, "put", fake_failing_put)

    with pytest.raises(RuntimeError) as exc_info:
        apply_agent_update(
            client,
            agent_id="test-agent-id",
            payload={"some": "payload"},
            method="PUT",
            base_url="https://api.bolna.ai",
            api_key=secret_key,
        )

    # Ensure status code is reported, but secret key is NEVER leaked in the exception message
    assert str(status_code) in str(exc_info.value)
    assert secret_key not in str(exc_info.value)


def test_get_current_agent_config_error_handling(monkeypatch):
    def fake_failing_get(url, headers=None):
        return httpx.Response(500, text="Internal Server Error", request=httpx.Request("GET", url))

    client = httpx.Client()
    monkeypatch.setattr(client, "get", fake_failing_get)

    with pytest.raises(RuntimeError) as exc_info:
        get_current_agent_config(client, "test-agent-id", base_url="https://api.bolna.ai")

    assert "HTTP 500" in str(exc_info.value)


def test_redact_payload_scrubs_all_secrets():
    payload = {
        "agent_config": {
            "api_key": "private-key-1",
            "webhook_token": "private-token-2",
            "auth_secret": "private-secret-3",
            "nested": {
                "user_password": "super-password",
                "safe_field": "keep-this-visible",
            },
            "list_of_secrets": [
                {"token": "tok-1"},
                {"safe": "ok"},
            ],
        }
    }
    redacted = redact_payload(payload)

    assert redacted["agent_config"]["api_key"] == "[REDACTED]"
    assert redacted["agent_config"]["webhook_token"] == "[REDACTED]"
    assert redacted["agent_config"]["auth_secret"] == "[REDACTED]"
    assert redacted["agent_config"]["nested"]["user_password"] == "[REDACTED]"
    assert redacted["agent_config"]["nested"]["safe_field"] == "keep-this-visible"
    assert redacted["agent_config"]["list_of_secrets"][0]["token"] == "[REDACTED]"
    assert redacted["agent_config"]["list_of_secrets"][1]["safe"] == "ok"


# =====================================================================
# 4. Post-Update Verification Invariants & Dropped Fields Detection
# =====================================================================

def test_verify_saved_agent_config_detects_missing_webhook_url(monkeypatch, sample_bolna_v2_agent):
    saved_mock = copy.deepcopy(sample_bolna_v2_agent)
    saved_mock["webhook_url"] = None

    def fake_get(url, headers=None):
        return httpx.Response(200, json=saved_mock, request=httpx.Request("GET", url))

    client = httpx.Client()
    monkeypatch.setattr(client, "get", fake_get)

    with pytest.raises(RuntimeError, match="webhook_url was not saved"):
        verify_saved_agent_config(client, "agent-id", base_url="https://api.bolna.ai")


def test_verify_saved_agent_config_detects_dropped_hindi_composition_nodes(monkeypatch, sample_bolna_v2_agent):
    saved_mock = copy.deepcopy(sample_bolna_v2_agent)
    saved_mock["webhook_url"] = "https://enticing-astonish-going.ngrok-free.dev/api/webhooks/bolna?token=xyz"
    # Hindi composition nodes dropped to 0
    saved_mock["composition_by_language"]["hi"] = []

    def fake_get(url, headers=None):
        return httpx.Response(200, json=saved_mock, request=httpx.Request("GET", url))

    client = httpx.Client()
    monkeypatch.setattr(client, "get", fake_get)

    with pytest.raises(RuntimeError, match="Hindi composition nodes were dropped"):
        verify_saved_agent_config(client, "agent-id", expected_method="PUT", base_url="https://api.bolna.ai")


def test_verify_saved_agent_config_detects_dropped_system_prompt(monkeypatch, sample_bolna_v2_agent):
    saved_mock = copy.deepcopy(sample_bolna_v2_agent)
    saved_mock["webhook_url"] = "https://enticing-astonish-going.ngrok-free.dev/api/webhooks/bolna?token=xyz"
    saved_mock["agent_prompts"]["task_1"]["system_prompt"] = ""

    def fake_get(url, headers=None):
        return httpx.Response(200, json=saved_mock, request=httpx.Request("GET", url))

    client = httpx.Client()
    monkeypatch.setattr(client, "get", fake_get)

    with pytest.raises(RuntimeError, match="System prompt was dropped"):
        verify_saved_agent_config(client, "agent-id", expected_method="PUT", base_url="https://api.bolna.ai")


def test_verify_saved_agent_config_success_put(monkeypatch, sample_bolna_v2_agent):
    saved_mock = copy.deepcopy(sample_bolna_v2_agent)
    saved_mock["webhook_url"] = "https://enticing-astonish-going.ngrok-free.dev/api/webhooks/bolna?token=xyz"
    saved_mock["webhook_headers"] = {"X-Timbre-Webhook-Secret": "xyz"}

    def fake_get(url, headers=None):
        return httpx.Response(200, json=saved_mock, request=httpx.Request("GET", url))

    client = httpx.Client()
    monkeypatch.setattr(client, "get", fake_get)

    result = verify_saved_agent_config(client, "agent-id", expected_method="PUT", base_url="https://api.bolna.ai")
    assert result["webhook_url_configured"] is True
    assert result["hindi_composition_nodes_count"] == 179
    assert result["system_prompt_char_length"] > 5000
    assert result["method_applied"] == "PUT"


def test_verify_saved_agent_config_success_patch(monkeypatch, sample_bolna_v2_agent):
    saved_mock = copy.deepcopy(sample_bolna_v2_agent)
    saved_mock["webhook_url"] = "https://enticing-astonish-going.ngrok-free.dev/api/webhooks/bolna?token=xyz"

    def fake_get(url, headers=None):
        return httpx.Response(200, json=saved_mock, request=httpx.Request("GET", url))

    client = httpx.Client()
    monkeypatch.setattr(client, "get", fake_get)

    result = verify_saved_agent_config(client, "agent-id", expected_method="PATCH", base_url="https://api.bolna.ai")
    assert result["webhook_url_configured"] is True
    assert result["method_applied"] == "PATCH"
