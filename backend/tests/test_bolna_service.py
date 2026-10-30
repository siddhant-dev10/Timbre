import asyncio

import httpx
import pytest

from app.services.bolna_service import BolnaIntegrationService, BolnaProviderError


class FakeAsyncClient:
    response = None
    calls = []

    def __init__(self, **kwargs):
        self.timeout = kwargs.get("timeout")

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        return None

    async def post(self, url, *, json=None, headers=None):
        self.calls.append((url, json, headers))
        return self.response

    async def get(self, url, *, headers=None):
        self.calls.append((url, None, headers))
        return self.response


def _ready_service():
    service = BolnaIntegrationService()
    service.api_key = "unit-test-token"
    service.agent_id = "unit-test-agent"
    service.enable_real_calls = True
    service.test_agent_verified = True
    return service


def test_call_submission_uses_one_call_no_personal_context_or_retry(monkeypatch):
    FakeAsyncClient.calls = []
    FakeAsyncClient.response = httpx.Response(
        201,
        json={"status": "queued", "execution_id": "execution-123"},
        request=httpx.Request("POST", "https://api.bolna.ai/call"),
    )
    monkeypatch.setattr("app.services.bolna_service.httpx.AsyncClient", FakeAsyncClient)
    result = asyncio.run(
        _ready_service().initiate_approved_test_call(
            phone_number="+919000000099",
            language="hi",
        )
    )

    assert result["status"] == "QUEUED"
    assert result["execution_id"] == "execution-123"
    assert len(FakeAsyncClient.calls) == 1
    url, payload, headers = FakeAsyncClient.calls[0]
    assert url == "https://api.bolna.ai/call"
    assert payload["recipient_phone_number"] == "+919000000099"
    assert payload["agent_data"] == {"language": "hi"}
    assert payload["retry_config"] == {"enabled": False}
    assert "from_phone_number" not in payload
    assert payload["user_data"]["record_kind"] == "fictional_test_data"
    assert "phone" not in str(payload["user_data"]).lower()
    assert headers["Authorization"].startswith("Bearer ")


def test_quota_error_is_clear_without_returning_provider_body(monkeypatch):
    FakeAsyncClient.calls = []
    FakeAsyncClient.response = httpx.Response(
        402,
        json={"message": "PRIVATE_PROVIDER_RESPONSE"},
        request=httpx.Request("POST", "https://api.bolna.ai/call"),
    )
    monkeypatch.setattr("app.services.bolna_service.httpx.AsyncClient", FakeAsyncClient)
    with pytest.raises(BolnaProviderError) as error:
        asyncio.run(
            _ready_service().initiate_approved_test_call(
                phone_number="+919000000099",
                language="hi",
            )
        )
    assert "insufficient credits" in str(error.value).lower()
    assert "PRIVATE_PROVIDER_RESPONSE" not in str(error.value)


def test_submission_timeout_is_marked_ambiguous_and_not_retried(monkeypatch):
    class TimeoutClient(FakeAsyncClient):
        async def post(self, url, *, json=None, headers=None):
            self.calls.append((url, json, headers))
            raise httpx.ReadTimeout("private timeout details")

    TimeoutClient.calls = []
    monkeypatch.setattr("app.services.bolna_service.httpx.AsyncClient", TimeoutClient)
    with pytest.raises(BolnaProviderError) as error:
        asyncio.run(
            _ready_service().initiate_approved_test_call(
                phone_number="+919000000099",
                language="hi",
            )
        )
    assert error.value.ambiguous is True
    assert "check bolna call history before retrying" in str(error.value).lower()
    assert len(TimeoutClient.calls) == 1
