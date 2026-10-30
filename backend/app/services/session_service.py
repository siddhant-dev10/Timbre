"""Call session and conversational turn-taking manager for Timbre.

Maintains multi-turn context, orchestrates the STT -> LLM -> TTS pipeline,
measures stage-by-stage latencies, and enforces Hindi response and safety policies.
"""
import base64
import json
import logging
import time
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple, Union

from app.config import settings
from app.models.citizen import Citizen
from app.models.service_scheme import ServiceScheme
from app.services.elevenlabs_service import elevenlabs_service
from app.services.llm_service import llm_service
from app.services.profile_context import minimal_profile_context
from app.services.rules_engine import evaluate_all_services
from app.services.whisper_service import whisper_service
from app.services.audio_playback_manager import playback_manager

logger = logging.getLogger("timbre.session")


class CallTurn:
    """Represents a single conversational turn in a telephone call."""

    def __init__(
        self,
        turn_index: int,
        user_transcript: str,
        ai_response: str,
        language: str,
        latencies: Dict[str, float],
        is_unclear: bool = False,
        stop_requested: bool = False,
        audio_url: Optional[str] = None,
        tts_error: Optional[str] = None,
    ) -> None:
        self.turn_id = f"turn-{uuid.uuid4().hex[:8]}"
        self.turn_index = turn_index
        self.timestamp = datetime.now(timezone.utc).isoformat()
        self.user_transcript = user_transcript
        self.ai_response = ai_response
        self.language = language
        self.latencies = latencies
        self.is_unclear = is_unclear
        self.stop_requested = stop_requested
        self.audio_url = audio_url
        self.tts_error = tts_error

    def to_dict(self) -> Dict[str, Any]:
        return {
            "turn_id": self.turn_id,
            "turn_index": self.turn_index,
            "timestamp": self.timestamp,
            "user_transcript": self.user_transcript,
            "ai_response": self.ai_response,
            "language": self.language,
            "latencies_ms": self.latencies,
            "is_unclear": self.is_unclear,
            "stop_requested": self.stop_requested,
            "audio_url": self.audio_url,
            "tts_error": self.tts_error,
        }


class CallSession:
    """Manages an active telephone conversation session with history and safety controls."""

    def __init__(
        self,
        session_id: str,
        citizen_id: str,
        citizen_name: str,
        language: str = "Hindi",
        is_simulation: bool = True,
    ) -> None:
        self.session_id = session_id
        self.citizen_id = citizen_id
        self.citizen_name = citizen_name
        self.language = language
        self.is_simulation = is_simulation
        self.created_at = datetime.now(timezone.utc).isoformat()
        self.status = "ACTIVE"  # ACTIVE, TERMINATED_BY_USER, COMPLETED, FAILED
        self.turns: List[CallTurn] = []
        self._history_for_llm: List[Dict[str, str]] = []

    def add_turn(self, turn: CallTurn) -> None:
        self.turns.append(turn)
        if turn.user_transcript:
            self._history_for_llm.append({"role": "user", "text": turn.user_transcript})
        if turn.ai_response:
            self._history_for_llm.append({"role": "assistant", "text": turn.ai_response})

    def get_llm_context(self) -> List[Dict[str, str]]:
        return self._history_for_llm[-10:]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "session_id": self.session_id,
            "citizen_id": self.citizen_id,
            "citizen_name": self.citizen_name,
            "language": self.language,
            "status": self.status,
            "created_at": self.created_at,
            "turn_count": len(self.turns),
            "turns": [turn.to_dict() for turn in self.turns],
        }


class CallSessionManager:
    """In-memory manager for active telephone sessions and turn orchestration."""

    def __init__(self) -> None:
        self._sessions: Dict[str, CallSession] = {}

    def get_or_create_session(
        self,
        session_id: Optional[str],
        citizen: Citizen,
        language: Optional[str] = None,
        is_simulation: bool = True,
    ) -> CallSession:
        sid = session_id or f"sess-{uuid.uuid4().hex[:12]}"
        if sid not in self._sessions:
            lang = language or citizen.preferred_language or settings.DEFAULT_CONVERSATION_LANGUAGE
            self._sessions[sid] = CallSession(
                session_id=sid,
                citizen_id=citizen.id,
                citizen_name=citizen.name,
                language=lang,
                is_simulation=is_simulation,
            )
        return self._sessions[sid]

    def get_session(self, session_id: str) -> Optional[CallSession]:
        return self._sessions.get(session_id)

    async def execute_turn(
        self,
        session: CallSession,
        citizen: Citizen,
        db_services: List[ServiceScheme],
        user_audio_bytes: Optional[bytes] = None,
        user_text: Optional[str] = None,
        synthesize_voice: bool = True,
    ) -> CallTurn:
        """
        Executes a complete conversational turn:
        Audio (or text) -> Whisper STT -> NVIDIA Nemotron LLM -> ElevenLabs TTS.
        Measures stage latencies and enforces conversation safety.
        """
        t_turn_start = time.perf_counter()
        latencies: Dict[str, float] = {}

        # 1. Speech Recognition (Whisper)
        transcript = ""
        is_unclear = False
        stop_requested = False

        if user_audio_bytes:
            stt_result = await whisper_service.transcribe_audio(
                user_audio_bytes,
                language="hi" if session.language.lower() == "hindi" else None
            )
            transcript = stt_result.get("text", "")
            is_unclear = stt_result.get("is_unclear", False)
            stop_requested = stt_result.get("stop_requested", False)
            latencies["transcription_ms"] = stt_result.get("latency_ms", 0.0)
        elif user_text is not None:
            transcript = user_text.strip()
            is_unclear = len(transcript) == 0
            stop_requested = whisper_service.detect_stop_intent(transcript)
            latencies["transcription_ms"] = 0.0
        else:
            raise ValueError("Either user_audio_bytes or user_text must be provided.")

        # 2. Check for stop intent or termination
        if stop_requested:
            session.status = "TERMINATED_BY_USER"
            playback_manager.cancel_session_playback(session.session_id, reason="stop_requested")
            conclusion_hi = "धन्यवाद, आपकी इच्छानुसार मैं यह कॉल यहीं समाप्त कर रहा हूँ। नमस्ते।"
            conclusion_en = "Thank you. As requested, I am ending this call now. Goodbye."
            ai_text = conclusion_en if session.language.lower() == "english" else conclusion_hi
            latencies["llm_ms"] = 0.0
        elif is_unclear:
            # Clarification policy: Ask politely to repeat instead of hallucinating
            clarification_hi = (
                "माफ़ कीजिए, आपकी आवाज़ स्पष्ट नहीं आई। क्या आप अपनी बात दोहरा सकते हैं?"
            )
            clarification_en = (
                "I apologize, I could not hear you clearly. Could you please repeat that?"
            )
            ai_text = clarification_en if session.language.lower() == "english" else clarification_hi
            latencies["llm_ms"] = 0.0
        else:
            # 3. NVIDIA Nemotron Grounded Reasoning
            t_llm_start = time.perf_counter()
            schemes_dicts = [
                {
                    "id": s.id,
                    "name": s.name,
                    "administering_body": s.administering_body,
                    "basic_eligibility_criteria": s.basic_eligibility_criteria,
                    "statutory_fee_inr": s.statutory_fee_inr,
                    "official_application_url": s.official_application_url,
                    "official_source_url": s.official_source_url,
                    "verification_status": s.verification_status,
                    "last_verification_date": s.last_verification_date.isoformat(),
                    "commonly_required_documents": json.loads(s.commonly_required_documents or "[]"),
                }
                for s in db_services
            ]

            system_prompt = llm_service.build_grounded_system_prompt(
                schemes_dicts, language=session.language
            )
            system_prompt += "\n\n" + minimal_profile_context(citizen, settings.parsed_reference_date)
            system_prompt += (
                "\nThis conversation is conducted via a voice telephone call. Keep replies brief, natural, "
                "respectful Hindi (Devanagari script), and speech-friendly. Ask only one question at a time. "
                "Never invent statutory rules, document requirements, or fees."
            )

            llm_result = await llm_service.generate_response(
                prompt=transcript,
                system_prompt=system_prompt,
                context=session.get_llm_context(),
                conversation_id=f"call:{session.session_id}",
            )
            t_llm_end = time.perf_counter()
            latencies["llm_ms"] = round((t_llm_end - t_llm_start) * 1000, 1)

            if llm_result.get("success"):
                ai_text = llm_result.get("response", "")
            else:
                ai_text = (
                    "माफ़ कीजिए, मुझे सर्वर से जानकारी प्राप्त करने में कठिनाई हो रही है। "
                    "कृपया कुछ समय बाद पुनः प्रयास करें।"
                )

        # 4. Speech Synthesis (ElevenLabs TTS) with cancellation guard
        audio_url = None
        tts_error = None
        turn_id = f"turn-{uuid.uuid4().hex[:8]}"
        turn_index = len(session.turns) + 1

        # Check if session was interrupted while LLM was processing
        is_cancelled = playback_manager.is_session_cancelled_since(session.session_id, t_turn_start)

        if synthesize_voice and elevenlabs_service.is_configured() and not is_cancelled:
            t_tts_start = time.perf_counter()
            try:
                audio_bytes = await elevenlabs_service.synthesize_speech(ai_text)
                t_tts_end = time.perf_counter()
                latencies["tts_ms"] = round((t_tts_end - t_tts_start) * 1000, 1)

                # Post-synthesis cancellation guard: ensure session was not interrupted during TTS generation
                if playback_manager.is_session_cancelled_since(session.session_id, t_turn_start):
                    logger.info("Discarding late TTS audio for session %s (interrupted during generation)", session.session_id)
                    audio_url = None
                else:
                    from app.api.voice import _audio_cache, _MAX_CACHE_ITEMS
                    audio_id = f"aud-call-{uuid.uuid4().hex[:10]}"
                    if len(_audio_cache) >= _MAX_CACHE_ITEMS:
                        _audio_cache.pop(next(iter(_audio_cache)))
                    _audio_cache[audio_id] = audio_bytes
                    playback_manager.register_clip(
                        audio_id=audio_id,
                        session_id=session.session_id,
                        turn_id=turn_id,
                        turn_index=turn_index,
                        audio_bytes=audio_bytes,
                    )
                    audio_url = f"/api/v1/voice/audio/{audio_id}"
            except Exception as exc:
                logger.warning("TTS generation skipped: %s", exc)
                tts_error = f"Speech generation unavailable: {exc}"
                latencies["tts_ms"] = 0.0
        else:
            latencies["tts_ms"] = 0.0

        t_turn_end = time.perf_counter()
        latencies["total_turn_ms"] = round((t_turn_end - t_turn_start) * 1000, 1)

        turn = CallTurn(
            turn_index=turn_index,
            user_transcript=transcript,
            ai_response=ai_text,
            language=session.language,
            latencies=latencies,
            is_unclear=is_unclear,
            stop_requested=stop_requested,
            audio_url=audio_url,
            tts_error=tts_error,
        )
        turn.turn_id = turn_id

        session.add_turn(turn)
        return turn


session_manager = CallSessionManager()
