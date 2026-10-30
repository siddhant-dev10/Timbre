"""Unit and integration tests for Whisper Speech-to-Text service."""
import io
import pytest
from unittest.mock import MagicMock, patch

from app.services.whisper_service import (
    WhisperService,
    WhisperServiceError,
    whisper_service,
)


def test_whisper_health_check():
    health = whisper_service.check_health()
    assert health["status"] == "ready"
    assert "Faster-Whisper" in health["provider"]
    assert health["default_language"] == "hi"
    assert health["confidence_threshold"] > 0.0


@pytest.mark.parametrize(
    "phrase,expected",
    [
        ("रुको, मुझे यह नहीं चाहिए", True),
        ("कृपया कॉल काटो", True),
        ("बस बंद करो", True),
        ("I want to hang up now", True),
        ("Please stop the call", True),
        ("bye", True),
        ("मुझे वोटर आईडी बनवाना है", False),
        ("What are the documents needed?", False),
        ("हाँ, आगे बताइए", False),
    ],
)
def test_whisper_detect_stop_intent(phrase, expected):
    assert whisper_service.detect_stop_intent(phrase) is expected


def test_whisper_confidence_calculation():
    # High confidence: logprob close to 0, no_speech low
    conf_high = whisper_service._calculate_confidence(avg_logprob=-0.05, no_speech_prob=0.02)
    assert 0.85 <= conf_high <= 1.0

    # Low confidence: very negative logprob
    conf_low = whisper_service._calculate_confidence(avg_logprob=-2.8, no_speech_prob=0.40)
    assert conf_low < 0.30

    # High no-speech probability
    conf_silence = whisper_service._calculate_confidence(avg_logprob=-0.5, no_speech_prob=0.90)
    assert conf_silence <= 0.20


@pytest.mark.asyncio
async def test_whisper_rejects_empty_audio():
    with pytest.raises(ValueError, match="empty or too small"):
        await whisper_service.transcribe_audio(b"")

    with pytest.raises(ValueError, match="empty or too small"):
        await whisper_service.transcribe_audio(b"RIFF" + b"\x00" * 10)


@pytest.mark.asyncio
async def test_whisper_hindi_transcription_mocked():
    mock_seg = MagicMock()
    mock_seg.text = "नमस्ते मुझे राशन कार्ड के लिए आवेदन करना है"
    mock_seg.start = 0.0
    mock_seg.end = 2.4
    mock_seg.avg_logprob = -0.12
    mock_seg.no_speech_prob = 0.01

    mock_info = MagicMock()
    mock_info.language = "hi"
    mock_info.language_probability = 0.99
    mock_info.duration = 2.5
    mock_info.all_language_probs = None

    mock_model = MagicMock()
    mock_model.transcribe.return_value = ([mock_seg], mock_info)

    service = WhisperService()
    service._model = mock_model

    # Synthetic 64-byte audio dummy buffer
    fake_audio = b"RIFF" + b"\x00" * 60
    res = await service.transcribe_audio(fake_audio, language="hi")

    assert res["success"] is True
    assert "नमस्ते मुझे राशन कार्ड" in res["text"]
    assert res["language"] == "hi"
    assert res["confidence"] > 0.70
    assert res["is_unclear"] is False
    assert res["stop_requested"] is False
    assert res["latency_ms"] >= 0.0


@pytest.mark.asyncio
async def test_whisper_hinglish_with_english_words():
    mock_seg = MagicMock()
    mock_seg.text = "Mera Voter ID card aur PAN card verify kar do"
    mock_seg.start = 0.0
    mock_seg.end = 3.0
    mock_seg.avg_logprob = -0.15
    mock_seg.no_speech_prob = 0.02

    mock_info = MagicMock()
    mock_info.language = "hi"
    mock_info.language_probability = 0.88
    mock_info.duration = 3.0
    mock_info.all_language_probs = None

    mock_model = MagicMock()
    mock_model.transcribe.return_value = ([mock_seg], mock_info)

    service = WhisperService()
    service._model = mock_model

    fake_audio = b"RIFF" + b"\x00" * 60
    res = await service.transcribe_audio(fake_audio)

    assert res["success"] is True
    assert "Voter ID card" in res["text"]
    assert res["is_unclear"] is False


@pytest.mark.asyncio
async def test_whisper_unclear_noise_triggers_clarification():
    # Audio with very low confidence (e.g. background noise)
    mock_seg = MagicMock()
    mock_seg.text = "..."
    mock_seg.start = 0.0
    mock_seg.end = 1.0
    mock_seg.avg_logprob = -2.9
    mock_seg.no_speech_prob = 0.85

    mock_info = MagicMock()
    mock_info.language = "hi"
    mock_info.language_probability = 0.20
    mock_info.duration = 1.0
    mock_info.all_language_probs = None

    mock_model = MagicMock()
    mock_model.transcribe.return_value = ([mock_seg], mock_info)

    service = WhisperService()
    service._model = mock_model

    fake_audio = b"RIFF" + b"\x00" * 60
    res = await service.transcribe_audio(fake_audio)

    assert res["is_unclear"] is True
    assert res["clarification_needed"] is True
    assert "माफ़ कीजिए, आपकी आवाज़ स्पष्ट नहीं आई" in res["clarification_prompt"]


def test_transcribe_api_endpoint(client):
    # Test valid upload
    fake_audio = b"RIFF" + b"\x00" * 60
    with patch.object(whisper_service, "transcribe_audio") as mock_stt:
        mock_stt.return_value = {
            "success": True,
            "text": "नमस्ते, क्या मुझे पेंशन मिल सकती है?",
            "language": "hi",
            "language_probability": 0.98,
            "confidence": 0.92,
            "duration_seconds": 2.1,
            "latency_ms": 145.0,
            "is_unclear": False,
            "stop_requested": False,
            "clarification_needed": False,
            "clarification_prompt": None,
        }

        response = client.post(
            "/api/v1/voice/transcribe",
            files={"file": ("test.wav", fake_audio, "audio/wav")},
            data={"language": "hi"}
        )
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert "पेंशन" in data["text"]
        assert data["latency_ms"] == 145.0


def test_transcribe_api_endpoint_rejects_empty(client):
    response = client.post(
        "/api/v1/voice/transcribe",
        files={"file": ("empty.wav", b"short", "audio/wav")}
    )
    assert response.status_code == 400


@pytest.mark.asyncio
async def test_live_whisper_real_audio_pipeline():
    """Executes the real Faster-Whisper CTranslate2 model on real PCM WAV bytes without mocking."""
    import struct, wave
    wav_buf = io.BytesIO()
    with wave.open(wav_buf, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(16000)
        # 1.0 second of low-level ambient noise / silence
        pcm_data = struct.pack("<" + "h" * 16000, *([5] * 16000))
        wf.writeframes(pcm_data)

    res = await whisper_service.transcribe_audio(wav_buf.getvalue(), language="hi")
    assert res["success"] is True
    assert res["is_unclear"] is True
    assert res["clarification_needed"] is True
    assert res["latency_ms"] > 0
    assert "माफ़ कीजिए" in res["clarification_prompt"]

