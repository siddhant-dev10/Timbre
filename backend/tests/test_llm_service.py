from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import httpx

from app.config import settings
from app.services.llm_service import NVIDIAProvider


@pytest.mark.parametrize(
    ("configured_effort", "expected_effort"),
    [("none", "none"), ("low", "low"), ("high", "high"), ("medium", "none")],
)
def test_reasoning_effort_uses_values_supported_by_selected_nvidia_model(
    configured_effort, expected_effort
):
    service = NVIDIAProvider()
    with patch.object(settings, "NVIDIA_REASONING_EFFORT", configured_effort):
        payload = service._payload([], stream=False)
    assert payload["reasoning_effort"] == expected_effort


@pytest.mark.asyncio
async def test_nvidia_openai_compatible_chat_uses_server_key_and_content_only():
    service = NVIDIAProvider()
    response = MagicMock(status_code=200)
    response.json.return_value = {
        "choices": [{"message": {"reasoning_content": "private reasoning", "content": "Namaste, Form 6 official portal par hai."}}]
    }
    with patch.object(settings, "NVIDIA_API_KEY", "test-key"), patch(
        "httpx.AsyncClient.post", new_callable=AsyncMock, return_value=response
    ) as post:
        result = await service.generate_response(
            "Voter ID kaise apply karun?", system_prompt="Concise Hinglish", conversation_id="test"
        )

    assert result["success"] is True
    assert "private reasoning" not in result["response"]
    assert "Form 6" in result["response"]
    assert post.call_args.args[0] == "https://integrate.api.nvidia.com/v1/chat/completions"
    assert post.call_args.kwargs["headers"]["Authorization"] == "Bearer test-key"
    assert post.call_args.kwargs["json"]["messages"][0] == {"role": "system", "content": "Concise Hinglish"}
    assert post.call_args.kwargs["json"]["model"] == "nvidia/nemotron-3.5-super-vl-120b-a12b"
    assert post.call_args.kwargs["json"]["reasoning_effort"] == "none"
    assert post.call_args.kwargs["json"]["stream"] is False


@pytest.mark.asyncio
async def test_nvidia_unconfigured_returns_safe_error_without_network_call():
    service = NVIDIAProvider()
    with patch.object(settings, "NVIDIA_API_KEY", ""), patch(
        "httpx.AsyncClient.post", new_callable=AsyncMock
    ) as post:
        result = await service.generate_response("Hello")

    assert result["success"] is False
    assert "not configured" in result["error"]
    post.assert_not_called()


@pytest.mark.asyncio
async def test_nvidia_quota_error_is_clear_and_does_not_leak_provider_body():
    service = NVIDIAProvider()
    response = MagicMock(status_code=429)
    response.text = "sensitive provider response"
    with patch.object(settings, "NVIDIA_API_KEY", "test-key"), patch(
        "httpx.AsyncClient.post", new_callable=AsyncMock, return_value=response
    ):
        result = await service.generate_response("hello")
    assert result["status_code"] == 429
    assert "quota" in result["error"].lower()
    assert "sensitive" not in result["error"]


@pytest.mark.parametrize("status_code, expected", [
    (401, "authentication"), (403, "access"), (429, "quota"), (503, "temporarily unavailable")
])
@pytest.mark.asyncio
async def test_nvidia_provider_errors_are_safe(status_code, expected):
    service = NVIDIAProvider()
    response = MagicMock(status_code=status_code)
    response.text = "provider payload that must not be surfaced"
    with patch.object(settings, "NVIDIA_API_KEY", "test-key"), patch(
        "httpx.AsyncClient.post", new_callable=AsyncMock, return_value=response
    ):
        result = await service.generate_response("hello")
    assert result["success"] is False
    assert expected in result["error"].lower()
    assert "provider payload" not in result["error"]


@pytest.mark.asyncio
async def test_nvidia_timeout_is_reported_and_next_request_recovers():
    service = NVIDIAProvider()
    response = MagicMock(status_code=200)
    response.json.return_value = {"choices": [{"message": {"content": "Recovered safely."}}]}
    with patch.object(settings, "NVIDIA_API_KEY", "test-key"), patch(
        "httpx.AsyncClient.post", new_callable=AsyncMock,
        side_effect=[httpx.ReadTimeout("timeout"), response]
    ):
        failed = await service.generate_response("first")
        recovered = await service.generate_response("second")
    assert failed["success"] is False and "timed out" in failed["error"]
    assert recovered["success"] is True and recovered["response"] == "Recovered safely."


@pytest.mark.asyncio
async def test_nvidia_malformed_response_is_safe():
    service = NVIDIAProvider()
    response = MagicMock(status_code=200)
    response.json.return_value = {"unexpected": []}
    with patch.object(settings, "NVIDIA_API_KEY", "test-key"), patch(
        "httpx.AsyncClient.post", new_callable=AsyncMock, return_value=response
    ):
        result = await service.generate_response("hello")
    assert result["success"] is False
    assert "no text" in result["error"].lower()


@pytest.mark.asyncio
async def test_nvidia_reuses_only_successful_conversation_history():
    service = NVIDIAProvider()
    first = MagicMock(status_code=200)
    first.json.return_value = {"choices": [{"message": {"content": "First answer."}}]}
    second = MagicMock(status_code=200)
    second.json.return_value = {"choices": [{"message": {"content": "Follow-up answer."}}]}
    with patch.object(settings, "NVIDIA_API_KEY", "test-key"), patch(
        "httpx.AsyncClient.post", new_callable=AsyncMock, side_effect=[first, second]
    ) as post:
        await service.generate_response("First question", conversation_id="same-profile")
        await service.generate_response("Can you clarify?", conversation_id="same-profile")
    messages = post.call_args.kwargs["json"]["messages"]
    assert {"role": "user", "content": "First question"} in messages
    assert {"role": "assistant", "content": "First answer."} in messages
    assert {"role": "user", "content": "Can you clarify?"} in messages
