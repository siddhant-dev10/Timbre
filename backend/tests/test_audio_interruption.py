"""Test Suite for Transport-Layer Audio Interruption and Cancellation.

Verifies:
- Cancellation of active audio buffers after barge-in interruption.
- Rejection of cancelled audio with HTTP 410 Gone.
- Discarding late TTS audio responses after interruption.
- Race protection during concurrent turn execution.
- Prompt stopping of playback on user termination requests.
- Session isolation for audio clips.
"""
import asyncio
import time
import pytest
from unittest.mock import AsyncMock, patch

from app.services.audio_playback_manager import playback_manager, PlaybackStatus
from app.services.session_service import session_manager
from app.models.citizen import Citizen


@pytest.fixture
def mock_citizen(db):
    citizen = db.query(Citizen).filter(Citizen.id == "CIT-0001").first()
    return citizen


def test_audio_playback_cancellation_and_410_gone(client):
    """Verifies that an interrupted audio clip is marked CANCELLED and returns HTTP 410 Gone."""
    session_id = f"test-sess-{time.time()}"
    audio_id = f"aud-test-{time.time()}"
    fake_audio_bytes = b"ID3\x03\x00\x00\x00\x00\x00\x23fake_mp3_payload"

    # Register clip
    clip = playback_manager.register_clip(
        audio_id=audio_id,
        session_id=session_id,
        turn_id="turn-1",
        turn_index=1,
        audio_bytes=fake_audio_bytes,
    )
    assert clip.status == PlaybackStatus.ACTIVE

    # Check audio is accessible before interruption
    bytes_out, status_out = playback_manager.get_audio(audio_id)
    assert status_out == "OK"
    assert bytes_out == fake_audio_bytes

    # Trigger transport-layer cancellation (e.g. user barge-in)
    cancelled_count = playback_manager.cancel_session_playback(session_id, reason="barge_in")
    assert cancelled_count == 1

    # Check audio is now CANCELLED
    bytes_after, status_after = playback_manager.get_audio(audio_id)
    assert status_after == "CANCELLED"
    assert bytes_after is None

    # Verify API endpoint returns HTTP 410 Gone
    response = client.get(f"/api/v1/voice/audio/{audio_id}")
    assert response.status_code == 410
    assert "cancelled" in response.json()["detail"].lower()


@pytest.mark.asyncio
async def test_late_tts_response_discarded_after_interruption(db, mock_citizen):
    """Ensures a late TTS response cannot restart or register playback after an interruption."""
    session_id = f"test-late-tts-{time.time()}"
    session = session_manager.get_or_create_session(session_id, citizen=mock_citizen)

    # Patch elevenlabs to simulate a slow TTS response during which an interruption occurs
    async def slow_tts(text):
        # Simulate interruption occurring while TTS was in-flight
        playback_manager.cancel_session_playback(session.session_id, reason="user_barge_in")
        return b"late_arriving_audio_bytes"

    with patch("app.services.elevenlabs_service.elevenlabs_service.is_configured", return_value=True), \
         patch("app.services.elevenlabs_service.elevenlabs_service.synthesize_speech", side_effect=slow_tts), \
         patch("app.services.llm_service.llm_service.generate_response", new_callable=AsyncMock) as mock_llm:

        mock_llm.return_value = {
            "success": True,
            "response": "नमस्ते! यह एक परीक्षण उत्तर है।",
        }

        turn = await session_manager.execute_turn(
            session=session,
            citizen=mock_citizen,
            db_services=[],
            user_text="वोटर आईडी कार्ड के नियम क्या हैं?",
            synthesize_voice=True,
        )

        # The late TTS audio must be discarded because interruption occurred during synthesis
        assert turn.audio_url is None


@pytest.mark.asyncio
async def test_stop_intent_cancels_playback_immediately(db, mock_citizen):
    """Verifies that a user stop phrase immediately cancels playback and terminates session."""
    session_id = f"test-stop-{time.time()}"
    session = session_manager.get_or_create_session(session_id, citizen=mock_citizen)

    # Pre-register an audio clip
    clip_id = f"aud-pre-{time.time()}"
    playback_manager.register_clip(
        audio_id=clip_id,
        session_id=session.session_id,
        turn_id="turn-0",
        turn_index=0,
        audio_bytes=b"prior_speech",
    )

    turn = await session_manager.execute_turn(
        session=session,
        citizen=mock_citizen,
        db_services=[],
        user_text="बस करो मुझे कुछ नहीं सुनना, तुरंत फोन काटो",
        synthesize_voice=False,
    )

    assert turn.stop_requested is True
    assert session.status == "TERMINATED_BY_USER"
    assert "कॉल यहीं समाप्त" in turn.ai_response

    # Verify previous clip was cancelled by stop request
    bytes_out, status_out = playback_manager.get_audio(clip_id)
    assert status_out == "CANCELLED"


def test_session_isolation_for_audio_cancellation():
    """Verifies that cancelling playback in Session A does not affect Session B."""
    sess_a = f"sess-a-{time.time()}"
    sess_b = f"sess-b-{time.time()}"

    clip_a = f"clip-a-{time.time()}"
    clip_b = f"clip-b-{time.time()}"

    playback_manager.register_clip(clip_a, sess_a, "turn-1", 1, b"audio_a")
    playback_manager.register_clip(clip_b, sess_b, "turn-1", 1, b"audio_b")

    # Cancel session A only
    playback_manager.cancel_session_playback(sess_a, reason="interruption")

    bytes_a, status_a = playback_manager.get_audio(clip_a)
    bytes_b, status_b = playback_manager.get_audio(clip_b)

    assert status_a == "CANCELLED"
    assert status_b == "OK"
    assert bytes_b == b"audio_b"
