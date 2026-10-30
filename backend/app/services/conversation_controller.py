"""Reusable Conversation Controller for Timbre.

Implements the Google NotebookLM-inspired interactive conversational state machine:
- Formal, testable state transitions (IDLE, INITIALIZING, SPEAKING, LISTENING, etc.)
- Natural barge-in interruption handling with stale audio token invalidation
- Multi-dimensional conversation memory (agenda tracking, resumption pointer, unresolved questions)
- Grounded RAG retrieval integration and graceful error recovery
"""
from enum import Enum
import logging
import time
import uuid
from typing import Any, Dict, List, Optional, Set, Tuple

from app.models.citizen import Citizen
from app.services.elevenlabs_service import elevenlabs_service
from app.services.knowledge_service import knowledge_service
from app.services.llm_service import llm_service
from app.services.profile_service import profile_service
from app.services.whisper_service import whisper_service
from app.services.audio_playback_manager import playback_manager

logger = logging.getLogger("timbre.controller")


class ConversationState(str, Enum):
    IDLE = "IDLE"
    INITIALIZING = "INITIALIZING"
    SPEAKING = "SPEAKING"
    LISTENING = "LISTENING"
    TRANSCRIBING = "TRANSCRIBING"
    THINKING = "THINKING"
    RETRIEVING_CONTEXT = "RETRIEVING_CONTEXT"
    RESPONDING = "RESPONDING"
    RESUMING = "RESUMING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


class InvalidStateTransitionError(RuntimeError):
    """Raised when an illegal conversational state transition is attempted."""
    pass


# Strict formal transition graph
VALID_TRANSITIONS: Dict[ConversationState, Set[ConversationState]] = {
    ConversationState.IDLE: {
        ConversationState.INITIALIZING,
        ConversationState.FAILED,
    },
    ConversationState.INITIALIZING: {
        ConversationState.SPEAKING,
        ConversationState.LISTENING,
        ConversationState.FAILED,
    },
    ConversationState.SPEAKING: {
        ConversationState.LISTENING,   # Natural barge-in interruption
        ConversationState.RESUMING,    # Resuming previous agenda point
        ConversationState.COMPLETED,   # Call concluded
        ConversationState.FAILED,
    },
    ConversationState.LISTENING: {
        ConversationState.TRANSCRIBING,
        ConversationState.SPEAKING,    # False trigger / resume
        ConversationState.COMPLETED,
        ConversationState.FAILED,
    },
    ConversationState.TRANSCRIBING: {
        ConversationState.RETRIEVING_CONTEXT,
        ConversationState.RESPONDING,  # Direct response (clarification or termination)
        ConversationState.SPEAKING,    # Silence detected, continue playback
        ConversationState.FAILED,
    },
    ConversationState.RETRIEVING_CONTEXT: {
        ConversationState.THINKING,
        ConversationState.FAILED,
    },
    ConversationState.THINKING: {
        ConversationState.RESPONDING,
        ConversationState.FAILED,
    },
    ConversationState.RESPONDING: {
        ConversationState.SPEAKING,
        ConversationState.RESUMING,    # Smooth resumption of interrupted narrative agenda
        ConversationState.COMPLETED,
        ConversationState.FAILED,
    },
    ConversationState.RESUMING: {
        ConversationState.SPEAKING,
        ConversationState.COMPLETED,
        ConversationState.FAILED,
    },
    ConversationState.COMPLETED: {
        ConversationState.IDLE,
    },
    ConversationState.FAILED: {
        ConversationState.IDLE,
        ConversationState.INITIALIZING,
    },
}


class ConversationMemory:
    """Maintains rich, multi-dimensional conversational state across turns."""

    def __init__(self, conversation_id: str, citizen_id: str) -> None:
        self.conversation_id = conversation_id
        self.citizen_id = citizen_id
        self.recent_turns: List[Dict[str, Any]] = []
        self.current_topic: Optional[str] = None
        self.current_document_id: Optional[str] = None
        self.planned_agenda_points: List[str] = []
        self.current_agenda_index: int = 0
        self.agent_last_spoken_response: Optional[str] = None
        self.unresolved_questions: List[str] = []
        self.next_action_followup: Optional[str] = None
        self.active_audio_token: Optional[str] = None
        self.created_at = time.time()

    def get_remaining_agenda(self) -> List[str]:
        return self.planned_agenda_points[self.current_agenda_index:]

    def advance_agenda(self) -> Optional[str]:
        if self.current_agenda_index < len(self.planned_agenda_points):
            item = self.planned_agenda_points[self.current_agenda_index]
            self.current_agenda_index += 1
            self.current_topic = item
            return item
        return None

    def invalidate_audio(self) -> None:
        """Invalidates current in-flight audio to prevent stale playback after interruption."""
        self.active_audio_token = None

    def new_audio_token(self) -> str:
        token = f"tok-{uuid.uuid4().hex[:8]}"
        self.active_audio_token = token
        return token

    def is_audio_valid(self, token: str) -> bool:
        return self.active_audio_token == token

    def to_dict(self) -> Dict[str, Any]:
        return {
            "conversation_id": self.conversation_id,
            "citizen_id": self.citizen_id,
            "current_topic": self.current_topic,
            "agenda_index": self.current_agenda_index,
            "agenda_total": len(self.planned_agenda_points),
            "remaining_agenda_count": len(self.get_remaining_agenda()),
            "last_spoken": self.agent_last_spoken_response,
            "unresolved_questions": self.unresolved_questions,
            "turn_count": len(self.recent_turns),
        }


class ConversationController:
    """Orchestrates interactive conversational turns, interruptions, and resumption."""

    def __init__(self, session_id: Optional[str] = None) -> None:
        self.session_id = session_id or f"ctrl-{uuid.uuid4().hex[:12]}"
        self.state: ConversationState = ConversationState.IDLE
        self.state_history: List[Tuple[ConversationState, float]] = [(ConversationState.IDLE, time.time())]
        self.memory: Optional[ConversationMemory] = None
        self.profile = profile_service.get_profile()
        self.language = "Hindi"

    def transition_to(self, new_state: ConversationState) -> None:
        """Enforces legal state transitions and records state history."""
        allowed = VALID_TRANSITIONS.get(self.state, set())
        if new_state not in allowed:
            err = (
                f"Illegal conversation state transition from {self.state.value} to {new_state.value}. "
                f"Allowed transitions: {[s.value for s in allowed]}"
            )
            logger.error(err)
            raise InvalidStateTransitionError(err)

        logger.info("Controller [%s]: %s -> %s", self.session_id, self.state.value, new_state.value)
        self.state = new_state
        self.state_history.append((new_state, time.time()))

    def start_session(
        self,
        citizen: Citizen,
        profile_id: Optional[str] = None,
        agenda_points: Optional[List[str]] = None,
        language: str = "Hindi",
    ) -> Dict[str, Any]:
        """Initializes conversation with citizen context and planned agenda points."""
        self.transition_to(ConversationState.INITIALIZING)
        self.profile = profile_service.get_profile(profile_id)
        self.language = language
        self.memory = ConversationMemory(
            conversation_id=self.session_id,
            citizen_id=citizen.id,
        )

        # Set default presentation agenda points if none provided
        self.memory.planned_agenda_points = agenda_points or [
            "वोटर आईडी (Form 6) पात्रता और प्रक्रिया",
            "आवश्यक पहचान और निवास प्रमाण दस्तावेज़",
            "आधिकारिक पोर्टल voters.eci.gov.in पर ऑनलाइन आवेदन",
        ]

        # Transition to speaking the opening introduction
        self.transition_to(ConversationState.SPEAKING)
        opening_audio_token = self.memory.new_audio_token()
        opening_hi = (
            f"नमस्ते {citizen.name}! मैं टिमब्रे हूँ, आपका एआई सहायक। "
            f"आज हम आपके लिए महत्वपूर्ण नागरिक सेवाओं और योजनाओं पर चर्चा करेंगे।"
        )
        self.memory.agent_last_spoken_response = opening_hi

        return {
            "session_id": self.session_id,
            "state": self.state.value,
            "opening_message": opening_hi,
            "audio_token": opening_audio_token,
            "agenda": self.memory.planned_agenda_points,
        }

    def interrupt(self) -> Dict[str, Any]:
        """
        Handles natural barge-in interruption when the citizen speaks while AI is speaking.
        Immediately halts active audio playback and shifts to LISTENING.
        """
        if self.state != ConversationState.SPEAKING:
            logger.warning("Interruption called while in state %s; ignoring.", self.state.value)
            return {"interrupted": False, "state": self.state.value}

        # 1. Invalidate current audio token to prevent stale audio playback
        if self.memory:
            self.memory.invalidate_audio()

        # Transport-layer active playback buffer cancellation
        playback_manager.cancel_session_playback(self.session_id, reason="barge_in_interruption")

        # 2. Shift state immediately to LISTENING
        self.transition_to(ConversationState.LISTENING)
        return {
            "interrupted": True,
            "session_id": self.session_id,
            "state": self.state.value,
            "stale_audio_cleared": True,
        }

    async def process_user_turn(
        self,
        db: Any,
        user_audio_bytes: Optional[bytes] = None,
        user_text: Optional[str] = None,
        allow_resumption: bool = True,
    ) -> Dict[str, Any]:
        """
        Full conversational turn with RAG retrieval, grounded answer, and agenda resumption.
        """
        if not self.memory:
            raise RuntimeError("Session has not been initialized. Call start_session first.")

        # Ensure we are in LISTENING before transcribing
        if self.state == ConversationState.SPEAKING:
            self.interrupt()

        if self.state != ConversationState.LISTENING:
            self.transition_to(ConversationState.LISTENING)

        # 1. Transcription (STT)
        self.transition_to(ConversationState.TRANSCRIBING)
        t_start = time.perf_counter()

        transcript = ""
        is_unclear = False
        stop_requested = False

        if user_audio_bytes:
            stt_res = await whisper_service.transcribe_audio(
                user_audio_bytes,
                language="hi" if self.language.lower() == "hindi" else None
            )
            transcript = stt_res.get("text", "")
            is_unclear = stt_res.get("is_unclear", False)
            stop_requested = stt_res.get("stop_requested", False)
        elif user_text is not None:
            transcript = user_text.strip()
            is_unclear = len(transcript) == 0
            stop_requested = whisper_service.detect_stop_intent(transcript)
        else:
            raise ValueError("Either user_audio_bytes or user_text must be provided.")

        # 2. Check for Stop Intent (Termination)
        if stop_requested:
            self.transition_to(ConversationState.RESPONDING)
            conclusion_hi = "धन्यवाद! आपकी इच्छानुसार मैं यह बातचीत यहीं समाप्त कर रहा हूँ। नमस्ते।"
            self.memory.agent_last_spoken_response = conclusion_hi
            self.transition_to(ConversationState.COMPLETED)
            return {
                "session_id": self.session_id,
                "state": self.state.value,
                "user_transcript": transcript,
                "ai_response": conclusion_hi,
                "citations": [],
                "stop_requested": True,
                "resumed_agenda_item": None,
            }

        # 3. Check for Unclear Speech (Clarification recovery)
        if is_unclear:
            self.transition_to(ConversationState.RESPONDING)
            clarification_hi = "माफ़ कीजिए, आपकी आवाज़ स्पष्ट नहीं आई। क्या आप अपनी बात दोबारा दोहरा सकते हैं?"
            self.memory.agent_last_spoken_response = clarification_hi
            self.transition_to(ConversationState.SPEAKING)
            return {
                "session_id": self.session_id,
                "state": self.state.value,
                "user_transcript": transcript,
                "ai_response": clarification_hi,
                "citations": [],
                "is_unclear": True,
                "resumed_agenda_item": None,
            }

        # 4. Contextual Knowledge Retrieval (RAG)
        self.transition_to(ConversationState.RETRIEVING_CONTEXT)
        retrieved_chunks = knowledge_service.search(
            db=db,
            query=transcript,
            top_k=3,
            min_score=0.15,
        )

        # 5. NVIDIA Nemotron Reasoning & Response Generation
        self.transition_to(ConversationState.THINKING)
        rag_context_blocks = []
        citations = []
        for chk in retrieved_chunks:
            rag_context_blocks.append(f"{chk['citation']}\n{chk['content']}")
            citations.append(chk["citation"])

        rag_text = "\n\n".join(rag_context_blocks) if rag_context_blocks else "No matching verified documents found in knowledge base."

        system_prompt = (
            f"You are Timbre, a grounded voice assistant following profile '{self.profile.name}'.\n"
            f"COMMUNICATION RULES:\n"
            f"1. Reply in natural, respectful {self.language} (Devanagari script if Hindi).\n"
            f"2. Keep responses brief for voice conversation: 2-3 short sentences (under 45 words).\n"
            f"3. Ground your answer strictly in the provided Knowledge Base below. Never invent fees or requirements.\n"
            f"4. If the information is not in the knowledge base, state politely that the document does not mention it.\n\n"
            f"KNOWLEDGE BASE EVIDENCE:\n{rag_text}"
        )

        llm_res = await llm_service.generate_response(
            prompt=transcript,
            system_prompt=system_prompt,
            conversation_id=f"ctrl:{self.session_id}",
        )

        answer_text = llm_res.get("response", "माफ़ कीजिए, जानकारी प्राप्त करने में कठिनाई हुई।")

        # 6. Smooth Resumption of Interrupted Overview / Agenda (NotebookLM Pattern)
        resumed_point = None
        if allow_resumption and self.memory.get_remaining_agenda():
            resumed_point = self.memory.advance_agenda()
            if resumed_point:
                bridge_phrase = (
                    f" जैसा कि हम चर्चा कर रहे थे, अब हम '{resumed_point}' पर आगे बढ़ते हैं।"
                    if self.language.lower() == "hindi"
                    else f" As we were discussing, moving on to '{resumed_point}'."
                )
                answer_text = f"{answer_text.strip()}{bridge_phrase}"

        # 7. Transition to RESPONDING then SPEAKING
        self.transition_to(ConversationState.RESPONDING)
        self.memory.agent_last_spoken_response = answer_text
        self.memory.recent_turns.append({
            "user_transcript": transcript,
            "ai_response": answer_text,
            "citations": citations,
            "timestamp": time.time(),
        })

        if resumed_point:
            self.transition_to(ConversationState.RESUMING)
        self.transition_to(ConversationState.SPEAKING)

        audio_token = self.memory.new_audio_token()

        return {
            "session_id": self.session_id,
            "state": self.state.value,
            "user_transcript": transcript,
            "ai_response": answer_text,
            "citations": citations,
            "audio_token": audio_token,
            "is_unclear": False,
            "stop_requested": False,
            "resumed_agenda_item": resumed_point,
            "remaining_agenda": self.memory.get_remaining_agenda(),
        }
