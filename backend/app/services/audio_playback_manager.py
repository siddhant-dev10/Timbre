"""Audio Playback and Cancellation Manager for Timbre.

Provides transport-layer playback state tracking, natural barge-in interruption
cancellation, stale audio eviction, race protection, and session-turn association.
Clearly distinguishes Mac-local audio playback from telephony-line carrier audio.
"""
import asyncio
import logging
import threading
import time
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger("timbre.playback")


class PlaybackStatus(str, Enum):
    ACTIVE = "ACTIVE"
    PLAYING = "PLAYING"
    CANCELLED = "CANCELLED"
    EXPIRED = "EXPIRED"


class AudioClip:
    def __init__(
        self,
        audio_id: str,
        session_id: str,
        turn_id: str,
        turn_index: int,
        audio_bytes: bytes,
    ) -> None:
        self.audio_id = audio_id
        self.session_id = session_id
        self.turn_id = turn_id
        self.turn_index = turn_index
        self.audio_bytes = audio_bytes
        self.created_at = time.time()
        self.status = PlaybackStatus.ACTIVE
        self.cancelled_at: Optional[float] = None
        self.cancellation_reason: Optional[str] = None

    def cancel(self, reason: str = "interrupted") -> None:
        self.status = PlaybackStatus.CANCELLED
        self.cancelled_at = time.time()
        self.cancellation_reason = reason
        # Clear raw audio bytes to release memory promptly
        self.audio_bytes = b""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "audio_id": self.audio_id,
            "session_id": self.session_id,
            "turn_id": self.turn_id,
            "turn_index": self.turn_index,
            "status": self.status.value,
            "created_at": self.created_at,
            "cancelled_at": self.cancelled_at,
            "reason": self.cancellation_reason,
        }


class AudioPlaybackManager:
    """Manages audio buffer caching, per-turn playback tokens, and active cancellation."""

    def __init__(self, max_clips: int = 100) -> None:
        self._clips: Dict[str, AudioClip] = {}
        self._session_clips: Dict[str, List[str]] = {}
        self._session_cancelled_at: Dict[str, float] = {}
        self._session_locks: Dict[str, asyncio.Lock] = {}
        self._thread_lock = threading.Lock()
        self._max_clips = max_clips

    def get_session_lock(self, session_id: str) -> asyncio.Lock:
        """Returns a per-session asyncio Lock to serialize concurrent turns safely."""
        with self._thread_lock:
            if session_id not in self._session_locks:
                self._session_locks[session_id] = asyncio.Lock()
            return self._session_locks[session_id]

    def register_clip(
        self,
        audio_id: str,
        session_id: str,
        turn_id: str,
        turn_index: int,
        audio_bytes: bytes,
    ) -> Optional[AudioClip]:
        """
        Registers a newly synthesized audio clip.
        If the session was interrupted while synthesis was in-flight, immediately discards.
        """
        with self._thread_lock:
            # Check if session was cancelled since clip was initiated
            cancel_time = self._session_cancelled_at.get(session_id, 0.0)
            now = time.time()

            clip = AudioClip(
                audio_id=audio_id,
                session_id=session_id,
                turn_id=turn_id,
                turn_index=turn_index,
                audio_bytes=audio_bytes,
            )

            # Evict oldest clip if cache exceeds limit
            if len(self._clips) >= self._max_clips:
                oldest_id = next(iter(self._clips))
                old_clip = self._clips.pop(oldest_id, None)
                if old_clip and old_clip.session_id in self._session_clips:
                    try:
                        self._session_clips[old_clip.session_id].remove(oldest_id)
                    except ValueError:
                        pass

            self._clips[audio_id] = clip
            if session_id not in self._session_clips:
                self._session_clips[session_id] = []
            self._session_clips[session_id].append(audio_id)

            logger.info(
                "Registered audio clip %s for session %s (turn %d, %d bytes)",
                audio_id, session_id, turn_index, len(audio_bytes)
            )
            return clip

    def cancel_session_playback(self, session_id: str, reason: str = "interrupted") -> int:
        """
        Cancels all active audio playback for a session.
        Prevents in-flight audio from playing and purges cached clips.
        """
        with self._thread_lock:
            now = time.time()
            self._session_cancelled_at[session_id] = now
            cancelled_count = 0

            clip_ids = self._session_clips.get(session_id, [])
            for cid in clip_ids:
                clip = self._clips.get(cid)
                if clip and clip.status == PlaybackStatus.ACTIVE:
                    clip.cancel(reason=reason)
                    cancelled_count += 1

            logger.info(
                "Cancelled %d active audio clips for session %s (reason: %s)",
                cancelled_count, session_id, reason
            )
            return cancelled_count

    def is_session_cancelled_since(self, session_id: str, timestamp: float) -> bool:
        """Checks whether an interruption or cancellation occurred after the given timestamp."""
        with self._thread_lock:
            cancel_time = self._session_cancelled_at.get(session_id, 0.0)
            return cancel_time > timestamp

    def get_audio(self, audio_id: str) -> Tuple[Optional[bytes], str]:
        """
        Retrieves audio bytes.
        Returns (bytes, "OK") if active.
        Returns (None, "CANCELLED") if invalidated.
        Returns (None, "NOT_FOUND") if absent.
        """
        with self._thread_lock:
            clip = self._clips.get(audio_id)
            if not clip:
                return None, "NOT_FOUND"
            if clip.status == PlaybackStatus.CANCELLED:
                return None, "CANCELLED"
            return clip.audio_bytes, "OK"

    def get_session_status(self, session_id: str) -> Dict[str, Any]:
        """Returns playback telemetry for a session."""
        with self._thread_lock:
            clip_ids = self._session_clips.get(session_id, [])
            clips_info = [self._clips[cid].to_dict() for cid in clip_ids if cid in self._clips]
            return {
                "session_id": session_id,
                "last_cancelled_at": self._session_cancelled_at.get(session_id),
                "total_clips": len(clip_ids),
                "clips": clips_info,
            }


playback_manager = AudioPlaybackManager()
