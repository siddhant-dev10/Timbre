"""Whisper Speech-to-Text service for Timbre.

Supports Hindi, Hinglish, and mixed Indian-English transcription with
latency measurement, confidence estimation, and telephone audio support.
"""
import io
import logging
import math
import re
import time
from typing import Any, Dict, List, Optional, Tuple, Union

from app.config import settings

logger = logging.getLogger("timbre.whisper")


class WhisperServiceError(RuntimeError):
    """Raised when speech recognition fails."""
    pass


class WhisperService:
    """Automatic Speech Recognition service using local Faster-Whisper."""

    # Words/phrases indicating user intent to stop or terminate the call (Hindi & English)
    STOP_WORDS_HI = [
        "रुको", "रुकिए", "बंद करो", "कॉल काटो", "फोन काटो", "फोन रखो",
        "रद्द करो", "नहीं चाहिए", "रहने दो", "समाप्त करो", "बात नहीं करनी"
    ]
    STOP_WORDS_HINGLISH = [
        "ruko", "rukiye", "band karo", "call kato", "phone kato", "phone rakho",
        "nahi chahiye", "khatam karo", "baat nahi karni", "call end karo", "bye"
    ]
    STOP_WORDS_EN = [
        "stop", "cancel", "hang up", "end call", "terminate", "disconnect", "bye", "goodbye"
    ]

    UNCLEAR_CLARIFICATION_PROMPT_HI = (
        "माफ़ कीजिए, आपकी आवाज़ स्पष्ट नहीं आई। क्या आप अपनी बात दोबारा दोहरा सकते हैं?"
    )

    def __init__(self) -> None:
        self.model_size = settings.WHISPER_MODEL_SIZE
        self.device = settings.WHISPER_DEVICE
        self.compute_type = settings.WHISPER_COMPUTE_TYPE
        self.default_language = settings.WHISPER_LANGUAGE
        self.confidence_threshold = settings.WHISPER_CONFIDENCE_THRESHOLD
        self._model: Any = None
        self._is_loading = False

    def _get_model(self) -> Any:
        """Lazily load the Whisper model to keep startup fast."""
        if self._model is not None:
            return self._model

        try:
            from faster_whisper import WhisperModel
            logger.info(
                "Loading Whisper model '%s' (device=%s, compute_type=%s)...",
                self.model_size, self.device, self.compute_type
            )
            t0 = time.time()
            self._model = WhisperModel(
                self.model_size,
                device=self.device,
                compute_type=self.compute_type,
            )
            logger.info("Whisper model loaded in %.2fs", time.time() - t0)
            return self._model
        except Exception as exc:
            logger.error("Failed to load faster-whisper model: %s", exc)
            raise WhisperServiceError(f"Whisper model could not be initialized: {exc}") from exc

    def is_configured(self) -> bool:
        """Checks if Whisper service is ready to transcribe."""
        return True

    def check_health(self) -> Dict[str, Any]:
        """Returns safe operational status without exposing internals."""
        return {
            "status": "ready",
            "provider": "Faster-Whisper (Local)",
            "model": self.model_size,
            "device": self.device,
            "compute_type": self.compute_type,
            "default_language": self.default_language,
            "confidence_threshold": self.confidence_threshold,
            "model_loaded": self._model is not None,
        }

    def detect_stop_intent(self, text: str) -> bool:
        """Determines if the transcribed user text signals call termination."""
        if not text:
            return False
        clean_text = text.strip().lower()
        # Check Hindi stop words/phrases (Devanagari)
        for term in self.STOP_WORDS_HI:
            if term in clean_text:
                return True
        # Check Hinglish stop words/phrases (Roman script)
        for term in self.STOP_WORDS_HINGLISH:
            if term in clean_text:
                return True
        # Check English stop words using regex word boundaries
        for term in self.STOP_WORDS_EN:
            if re.search(r"\b" + re.escape(term) + r"\b", clean_text):
                return True
        return False

    def _calculate_confidence(self, avg_logprob: float, no_speech_prob: float) -> float:
        """Maps Faster-Whisper log probabilities to a calibrated 0.0-1.0 confidence score."""
        if no_speech_prob > 0.60:
            return max(0.0, 1.0 - no_speech_prob)
        # avg_logprob typically ranges from -1.5 (poor) to 0.0 (perfect)
        try:
            linear_prob = math.exp(max(-3.0, min(0.0, avg_logprob)))
            # Penalize if no_speech_prob is non-trivial
            calibrated = linear_prob * (1.0 - (0.5 * no_speech_prob))
            return round(max(0.0, min(1.0, calibrated)), 3)
        except Exception:
            return 0.50

    async def transcribe_audio(
        self,
        audio_data: Union[bytes, io.BytesIO],
        language: Optional[str] = None,
        initial_prompt: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Transcribes audio data into text.
        
        Parameters:
            audio_data: Audio bytes (WAV, MP3, OGG, WebM) or BytesIO.
            language: Target language code ('hi' for Hindi, 'en' for English, or None for auto-detect).
            initial_prompt: Optional guiding context prompt (e.g. 'नमस्ते, यह भारतीय सरकारी योजना संवाद है।').
            
        Returns:
            Dict containing transcript, language, confidence, latency_ms, is_unclear, and stop_requested.
        """
        t_start = time.perf_counter()

        if isinstance(audio_data, bytes):
            if not audio_data or len(audio_data) < 32:
                raise ValueError("Audio data is empty or too small to contain valid audio.")
            audio_buffer = io.BytesIO(audio_data)
        elif isinstance(audio_data, io.BytesIO):
            audio_buffer = audio_data
        else:
            raise ValueError("Unsupported audio data format. Expected bytes or BytesIO.")

        target_lang = language or self.default_language
        prompt = initial_prompt or "नमस्ते, यह हिंदी और हिंग्लिश में बातचीत है।"

        model = self._get_model()

        try:
            segments, info = model.transcribe(
                audio_buffer,
                language=target_lang,
                task="transcribe",
                initial_prompt=prompt,
                beam_size=5,
                vad_filter=True,  # Voice activity filter to strip leading/trailing silence
                vad_parameters=dict(min_silence_duration_ms=400),
            )
            segment_list = list(segments)
        except Exception as exc:
            logger.error("Whisper transcription error: %s", exc)
            raise WhisperServiceError(f"Speech transcription failed: {exc}") from exc

        t_end = time.perf_counter()
        latency_ms = round((t_end - t_start) * 1000, 1)

        # Aggregate transcript and confidence
        text_parts = []
        confidences = []
        detailed_segments = []

        for seg in segment_list:
            text = seg.text.strip()
            if text:
                text_parts.append(text)
            seg_conf = self._calculate_confidence(seg.avg_logprob, seg.no_speech_prob)
            confidences.append(seg_conf)
            detailed_segments.append({
                "start": round(seg.start, 2),
                "end": round(seg.end, 2),
                "text": text,
                "confidence": seg_conf,
            })

        full_text = " ".join(text_parts).strip()
        overall_confidence = (
            round(sum(confidences) / len(confidences), 3) if confidences else 0.0
        )

        # Check if speech was unclear or noise-only
        lang_prob = getattr(info, "language_probability", 1.0) if hasattr(info, "language_probability") else 1.0
        is_unclear = bool(
            len(full_text) == 0
            or overall_confidence < self.confidence_threshold
            or (getattr(info, "all_language_probs", None) is not None and lang_prob < 0.25)
        )

        stop_requested = self.detect_stop_intent(full_text)

        result = {
            "success": True,
            "text": full_text,
            "language": info.language if hasattr(info, "language") else target_lang,
            "language_probability": round(getattr(info, "language_probability", 1.0), 3),
            "confidence": overall_confidence,
            "duration_seconds": round(getattr(info, "duration", 0.0), 2),
            "latency_ms": latency_ms,
            "is_unclear": is_unclear,
            "stop_requested": stop_requested,
            "clarification_needed": is_unclear,
            "clarification_prompt": self.UNCLEAR_CLARIFICATION_PROMPT_HI if is_unclear else None,
            "segments": detailed_segments,
        }

        logger.info(
            "Transcribed (%s, conf=%.2f, %0.1fms): '%s'",
            result["language"], overall_confidence, latency_ms, full_text[:60]
        )
        return result


whisper_service = WhisperService()
