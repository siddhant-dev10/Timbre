import base64
import pytest
import httpx
from unittest.mock import AsyncMock, patch, MagicMock
from fastapi.testclient import TestClient
from app.main import app
from app.services.elevenlabs_service import ElevenLabsTTSService, elevenlabs_service
from app.config import settings

client = TestClient(app)

MOCK_MP3_BYTES = b"\xff\xfb\x90d\x00\x00\x00\x00\x00MOCK_ELEVENLABS_AUDIO_STREAM_TIMBRE"


def test_elevenlabs_unconfigured_health():
    """Verify ElevenLabs health check when unconfigured."""
    with patch.object(settings, "ELEVENLABS_API_KEY", ""), \
         patch.object(settings, "ELEVENLABS_VOICE_ID", ""):
        service = ElevenLabsTTSService()
        health = service.check_health()
        assert health["configured"] is False
        assert health["status"] == "credentials_pending"
        assert health["provider"] == "ElevenLabs"
        assert health["voice_name"] == "Timbre"
        assert health["api_key_set"] is False


def test_health_endpoint_includes_elevenlabs():
    """Verify /api/v1/health reports elevenlabs_tts component health."""
    response = client.get("/api/v1/health")
    assert response.status_code == 200
    data = response.json()
    assert "elevenlabs_tts" in data
    assert data["elevenlabs_tts"]["status"] in ("configured", "credentials_pending")


@pytest.mark.asyncio
async def test_elevenlabs_unconfigured_raises_error():
    """Calling synthesis when unconfigured raises a clear error."""
    service = ElevenLabsTTSService()
    service.api_key = ""
    service.voice_id = ""

    with pytest.raises(RuntimeError) as exc_info:
        await service.synthesize_speech("Namaste citizen")
    assert "ELEVENLABS_API_KEY" in str(exc_info.value)


@pytest.mark.asyncio
async def test_elevenlabs_empty_text_raises_value_error():
    """Calling synthesis with empty text raises ValueError."""
    service = ElevenLabsTTSService()
    service.api_key = "test_key"
    service.voice_id = "test_voice"

    with pytest.raises(ValueError) as exc_info:
        await service.synthesize_speech("   ")
    assert "cannot be empty" in str(exc_info.value)


@pytest.mark.asyncio
async def test_elevenlabs_synthesize_success_mocked():
    """Mocked ElevenLabs API returns audio bytes without consuming credits."""
    service = ElevenLabsTTSService()
    service.api_key = "mock_secret_key_123"
    service.voice_id = "timbre_custom_voice_id"

    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.content = MOCK_MP3_BYTES

    with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
        mock_post.return_value = mock_resp

        result = await service.synthesize_speech(
            text="Namaste, aapka voter card ke liye aavedan swikrit hua hai."
        )

        assert result == MOCK_MP3_BYTES
        mock_post.assert_called_once()
        call_kwargs = mock_post.call_args.kwargs
        assert call_kwargs["headers"]["xi-api-key"] == "mock_secret_key_123"
        assert call_kwargs["json"]["text"] == "Namaste, aapka voter card ke liye aavedan swikrit hua hai."
        assert call_kwargs["json"]["model_id"] == "eleven_multilingual_v2"


@pytest.mark.asyncio
async def test_elevenlabs_synthesize_auth_failure():
    """Mocked 401 Unauthorized raises PermissionError without leaking secret."""
    service = ElevenLabsTTSService()
    service.api_key = "invalid_secret_key"
    service.voice_id = "timbre_voice"

    mock_resp = MagicMock()
    mock_resp.status_code = 401

    with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
        mock_post.return_value = mock_resp

        with pytest.raises(PermissionError) as exc_info:
            await service.synthesize_speech("Hello test")
        assert "401" in str(exc_info.value)
        assert "invalid_secret_key" not in str(exc_info.value)


@pytest.mark.asyncio
async def test_elevenlabs_synthesize_key_id_used_as_key():
    """Mocked 400 when API key ID is used instead of secret key raises helpful PermissionError."""
    service = ElevenLabsTTSService()
    service.api_key = "mock_key_id_0123456789abcdef0123456789abcdef"
    service.voice_id = "timbre_voice"

    mock_resp = MagicMock()
    mock_resp.status_code = 400
    mock_resp.json.return_value = {
        "detail": {
            "type": "authentication_error",
            "code": "invalid_api_key",
            "message": "API key ID used as API key - only valid API keys can be used. API keys start with 'sk_'",
            "status": "api_key_id_used_as_api_key"
        }
    }

    with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
        mock_post.return_value = mock_resp

        with pytest.raises(PermissionError) as exc_info:
            await service.synthesize_speech("Hello test")
        assert "start with 'sk_'" in str(exc_info.value)


@pytest.mark.asyncio
async def test_elevenlabs_synthesize_quota_exhausted():
    """Mocked 402/429 raises RuntimeError indicating quota or rate limit."""
    service = ElevenLabsTTSService()
    service.api_key = "test_key"
    service.voice_id = "timbre_voice"

    mock_resp = MagicMock()
    mock_resp.status_code = 402

    with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
        mock_post.return_value = mock_resp

        with pytest.raises(RuntimeError) as exc_info:
            await service.synthesize_speech("Hello test")
        assert "limit reached" in str(exc_info.value) or "402" in str(exc_info.value)


@pytest.mark.asyncio
async def test_elevenlabs_synthesize_voice_not_found():
    """Mocked 404 raises ValueError with target voice ID."""
    service = ElevenLabsTTSService()
    service.api_key = "test_key"
    service.voice_id = "nonexistent_voice_id"

    mock_resp = MagicMock()
    mock_resp.status_code = 404

    with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
        mock_post.return_value = mock_resp

        with pytest.raises(ValueError) as exc_info:
            await service.synthesize_speech("Hello test")
        assert "404" in str(exc_info.value)


@pytest.mark.asyncio
async def test_elevenlabs_timeout():
    """Mocked timeout raises TimeoutError."""
    service = ElevenLabsTTSService()
    service.api_key = "test_key"
    service.voice_id = "timbre_voice"

    with patch("httpx.AsyncClient.post", side_effect=httpx.TimeoutException("Read timed out")):
        with pytest.raises(TimeoutError) as exc_info:
            await service.synthesize_speech("Hello test")
        assert "timed out" in str(exc_info.value)


def test_api_voice_synthesize_endpoint_mocked():
    """Test POST /api/v1/voice/synthesize returns binary audio stream."""
    with patch.object(elevenlabs_service, "is_configured", return_value=True), \
         patch.object(elevenlabs_service, "synthesize_speech", new_callable=AsyncMock) as mock_synth:
        mock_synth.return_value = MOCK_MP3_BYTES

        resp = client.post(
            "/api/v1/voice/synthesize",
            json={"text": "Voter ID aavedan ke baare mein jaankari."}
        )

        assert resp.status_code == 200
        assert resp.headers["content-type"] == "audio/mpeg"
        assert resp.content == MOCK_MP3_BYTES


def test_api_voice_synthesize_unconfigured_returns_503():
    """Test POST /api/v1/voice/synthesize returns 503 when credentials pending."""
    with patch.object(elevenlabs_service, "is_configured", return_value=False):
        resp = client.post(
            "/api/v1/voice/synthesize",
            json={"text": "Test"}
        )
        assert resp.status_code == 503
        assert "not configured" in resp.json()["detail"]


def test_api_voice_synthesize_rejects_overlong_input():
    resp = client.post("/api/v1/voice/synthesize", json={"text": "x" * 4001})
    assert resp.status_code == 422


def test_api_voice_chat_end_to_end_mocked():
    """
    Test full end-to-end voice chat endpoint:
    NVIDIA Nemotron text generation + ElevenLabs TTS audio synthesis.
    """
    mock_llm_response = {
        "success": True,
        "response": "Namaste Aarav ji! Voter ID Form 6 ke liye aap voters.eci.gov.in par apply kar sakte hain.",
        "model_used": "nvidia/nemotron-3.5-super-vl-120b-a12b"
    }

    with patch("app.services.llm_service.llm_service.generate_response", new_callable=AsyncMock) as mock_llm, \
         patch.object(elevenlabs_service, "is_configured", return_value=True), \
         patch.object(elevenlabs_service, "synthesize_speech", new_callable=AsyncMock) as mock_synth:
        
        mock_llm.return_value = mock_llm_response
        mock_synth.return_value = MOCK_MP3_BYTES

        resp = client.post(
            "/api/v1/voice/chat",
            json={
                "citizen_id": "CIT-0001",
                "message": "Mujhe Voter ID banwana hai, kaise karoon?",
                "language_preference": "Hinglish"
            }
        )

        assert resp.status_code == 200
        data = resp.json()
        assert data["citizen_id"] == "CIT-0001"
        assert "Voter ID" in data["answer"]
        assert data["audio_base64"] is not None
        assert base64.b64decode(data["audio_base64"]) == MOCK_MP3_BYTES
        assert data["tts_provider"] == "ElevenLabs"
        assert data["voice_name"] == "Timbre"
        assert data["audio_url"] is not None

        # Verify streaming audio from cached audio_url
        audio_stream_resp = client.get(data["audio_url"])
        assert audio_stream_resp.status_code == 200
        assert audio_stream_resp.headers["content-type"] == "audio/mpeg"
        assert audio_stream_resp.content == MOCK_MP3_BYTES


def test_chat_with_synthesize_voice_flag_mocked():
    """Verify POST /api/v1/chat respects synthesize_voice flag."""
    mock_llm_response = {
        "success": True,
        "response": "Driving licence test online de sakte hain.",
        "model_used": "nvidia/nemotron-3.5-super-vl-120b-a12b"
    }

    with patch("app.services.llm_service.llm_service.generate_response", new_callable=AsyncMock) as mock_llm, \
         patch.object(elevenlabs_service, "is_configured", return_value=True), \
         patch.object(elevenlabs_service, "synthesize_speech", new_callable=AsyncMock) as mock_synth:
        
        mock_llm.return_value = mock_llm_response
        mock_synth.return_value = MOCK_MP3_BYTES

        resp = client.post(
            "/api/v1/chat",
            json={
                "citizen_id": "CIT-0001",
                "message": "Learner licence kaise milega?",
                "synthesize_voice": True
            }
        )

        assert resp.status_code == 200
        data = resp.json()
        assert data["audio_base64"] is not None
        assert base64.b64decode(data["audio_base64"]) == MOCK_MP3_BYTES
