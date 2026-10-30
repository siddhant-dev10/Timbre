import logging
from typing import Dict, Any, Optional
import httpx
from app.config import settings

logger = logging.getLogger("timbre.elevenlabs")


class ElevenLabsTTSService:
    """
    ElevenLabs Text-to-Speech synthesis service for Timbre.
    Server-side ElevenLabs TTS adapter for the optional custom Timbre voice.
    """

    def __init__(self):
        self.base_url = settings.ELEVENLABS_BASE_URL.rstrip("/")
        self.api_key = settings.ELEVENLABS_API_KEY.strip()
        self.voice_id = settings.ELEVENLABS_VOICE_ID.strip()
        self.model_id = settings.ELEVENLABS_TTS_MODEL_ID.strip() or "eleven_multilingual_v2"
        self.timeout = settings.ELEVENLABS_TIMEOUT_SECONDS

    def reload_config(self):
        """Reload credentials and settings from active settings instance."""
        self.base_url = settings.ELEVENLABS_BASE_URL.rstrip("/")
        self.api_key = settings.ELEVENLABS_API_KEY.strip()
        self.voice_id = settings.ELEVENLABS_VOICE_ID.strip()
        self.model_id = settings.ELEVENLABS_TTS_MODEL_ID.strip() or "eleven_multilingual_v2"
        self.timeout = settings.ELEVENLABS_TIMEOUT_SECONDS

    def is_configured(self) -> bool:
        """Checks whether the API key and Voice ID are present."""
        return bool(self.api_key and self.voice_id)

    def check_health(self) -> Dict[str, Any]:
        """
        Provides operational status for health check reporting (credentials configuration only).
        NEVER prints or reveals secret API keys.
        """
        configured = self.is_configured()
        return {
            "configured": configured,
            "status": "configured" if configured else "credentials_pending",
            "provider": "ElevenLabs",
            "voice_name": "Timbre",
            "voice_id_set": bool(self.voice_id),
            "voice_id": self.voice_id if self.voice_id else None,
            "model_id": self.model_id,
            "api_key_set": bool(self.api_key),
            "connectivity_checked": False,
            "details": f"Provider: ElevenLabs, Custom Voice: Timbre, Configured: {configured}, Model: {self.model_id}; connectivity not checked.",
        }

    async def check_health_async(self, check_connectivity: bool = False) -> Dict[str, Any]:
        """
        Provides operational status with optional live zero-credit voice verification.
        NEVER prints or reveals secret API keys.
        """
        base = self.check_health()
        if not check_connectivity or not self.is_configured():
            return base

        headers = {"xi-api-key": self.api_key}
        endpoint_url = f"{self.base_url}/v1/voices/{self.voice_id}"
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.get(endpoint_url, headers=headers)
            if resp.status_code == 200:
                v_data = resp.json()
                voice_name = v_data.get("name", "Timbre")
                return {
                    "configured": True,
                    "status": "healthy",
                    "provider": "ElevenLabs",
                    "voice_name": voice_name,
                    "voice_id_set": True,
                    "voice_id": self.voice_id,
                    "model_id": self.model_id,
                    "api_key_set": True,
                    "connectivity_checked": True,
                    "details": f"Provider: ElevenLabs, Custom Voice: '{voice_name}', Model: {self.model_id}; live connectivity verified.",
                }
            elif resp.status_code == 401:
                return {
                    "configured": False,
                    "status": "unauthorized",
                    "provider": "ElevenLabs",
                    "voice_name": "Timbre",
                    "voice_id_set": True,
                    "voice_id": self.voice_id,
                    "model_id": self.model_id,
                    "api_key_set": True,
                    "connectivity_checked": True,
                    "details": "ElevenLabs authentication failed: API key rejected (HTTP 401).",
                }
            elif resp.status_code == 404:
                return {
                    "configured": False,
                    "status": "voice_not_found",
                    "provider": "ElevenLabs",
                    "voice_name": "Timbre",
                    "voice_id_set": True,
                    "voice_id": self.voice_id,
                    "model_id": self.model_id,
                    "api_key_set": True,
                    "connectivity_checked": True,
                    "details": f"Configured ElevenLabs voice ID '{self.voice_id}' not found (HTTP 404).",
                }
            else:
                return {
                    "configured": False,
                    "status": "unavailable",
                    "provider": "ElevenLabs",
                    "voice_name": "Timbre",
                    "voice_id_set": True,
                    "voice_id": self.voice_id,
                    "model_id": self.model_id,
                    "api_key_set": True,
                    "connectivity_checked": True,
                    "details": f"ElevenLabs returned HTTP {resp.status_code}.",
                }
        except httpx.TimeoutException:
            return {
                "configured": True,
                "status": "unavailable",
                "provider": "ElevenLabs",
                "voice_name": "Timbre",
                "voice_id_set": True,
                "voice_id": self.voice_id,
                "model_id": self.model_id,
                "api_key_set": True,
                "connectivity_checked": True,
                "details": "ElevenLabs connectivity check timed out.",
            }
        except Exception as exc:
            return {
                "configured": True,
                "status": "unavailable",
                "provider": "ElevenLabs",
                "voice_name": "Timbre",
                "voice_id_set": True,
                "voice_id": self.voice_id,
                "model_id": self.model_id,
                "api_key_set": True,
                "connectivity_checked": True,
                "details": f"Could not reach ElevenLabs: {type(exc).__name__}",
            }

    async def synthesize_speech(
        self,
        text: str,
        voice_id: Optional[str] = None,
        model_id: Optional[str] = None,
        output_format: str = "mp3_44100_128"
    ) -> bytes:
        """
        Synthesizes spoken audio from text using ElevenLabs API.
        
        Parameters:
            text: Text to synthesize (Hindi, Hinglish, or English).
            voice_id: Optional voice ID override (defaults to configured Timbre voice).
            model_id: Optional model ID override (defaults to eleven_multilingual_v2).
            output_format: Target audio encoding format.
            
        Returns:
            bytes: Binary MP3 audio stream.
        """
        if not text or not text.strip():
            raise ValueError("Text to synthesize cannot be empty.")

        target_voice_id = (voice_id or self.voice_id).strip()
        target_model_id = (model_id or self.model_id).strip()

        if not self.api_key:
            raise RuntimeError(
                "ElevenLabs API key is not configured. "
                "Please configure ELEVENLABS_API_KEY in the backend .env file."
            )

        if not target_voice_id:
            raise RuntimeError(
                "ElevenLabs Voice ID is not configured. "
                "Please configure ELEVENLABS_VOICE_ID for the custom Timbre voice in the backend .env file."
            )

        endpoint_url = f"{self.base_url}/v1/text-to-speech/{target_voice_id}"
        params = {"output_format": output_format}

        headers = {
            "xi-api-key": self.api_key,
            "Content-Type": "application/json",
            "Accept": "audio/mpeg"
        }

        payload = {
            "text": text.strip(),
            "model_id": target_model_id,
            "voice_settings": {
                "stability": 0.5,
                "similarity_boost": 0.75,
                "style": 0.0,
                "use_speaker_boost": True
            }
        }

        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(
                    endpoint_url,
                    params=params,
                    headers=headers,
                    json=payload
                )

                if response.status_code == 200:
                    if not response.content:
                        raise RuntimeError("ElevenLabs returned an empty audio response.")
                    return response.content

                if response.status_code == 400:
                    try:
                        err_json = response.json()
                        err_detail = err_json.get("detail", {})
                        if isinstance(err_detail, dict):
                            msg = err_detail.get("message", "")
                            if "API key ID used as API key" in msg or err_detail.get("status") == "api_key_id_used_as_api_key":
                                raise PermissionError(
                                    "ElevenLabs rejected the API key: An API Key ID was supplied instead of the secret key. "
                                    "ElevenLabs secret API keys start with 'sk_' and are displayed when created or rotated in the ElevenLabs dashboard."
                                )
                    except PermissionError:
                        raise
                    except Exception:
                        pass
                    raise RuntimeError("ElevenLabs speech synthesis failed: HTTP 400 Bad Request.")

                if response.status_code == 401:
                    logger.error("ElevenLabs authentication failed (HTTP 401). Check ELEVENLABS_API_KEY.")
                    raise PermissionError(
                        "ElevenLabs API authentication failed (HTTP 401). "
                        "Please verify your ELEVENLABS_API_KEY in .env."
                    )

                if response.status_code in (402, 429):
                    logger.warning("ElevenLabs credit exhaustion or rate limit (HTTP %s).", response.status_code)
                    raise RuntimeError(
                        f"ElevenLabs service limit reached (HTTP {response.status_code}). "
                        "Quota exhausted or rate limit encountered."
                    )

                if response.status_code == 404:
                    logger.error("ElevenLabs Voice ID not found (HTTP 404).")
                    raise ValueError(
                        f"ElevenLabs Voice ID '{target_voice_id}' was not found (HTTP 404). "
                        "Verify that your custom Timbre voice ID is accurate."
                    )

                # Generic HTTP error - ensure headers and secrets are not leaked
                logger.error("ElevenLabs API HTTP error: %s", response.status_code)
                raise RuntimeError(
                    f"ElevenLabs speech synthesis failed with status code {response.status_code}."
                )

        except httpx.TimeoutException:
            logger.error("ElevenLabs TTS request timed out after %s seconds.", self.timeout)
            raise TimeoutError(f"ElevenLabs request timed out after {self.timeout}s.")
        except httpx.RequestError as exc:
            logger.error("Network communication error with ElevenLabs API: %s", type(exc).__name__)
            raise ConnectionError(f"Failed to connect to ElevenLabs API: {type(exc).__name__}")


elevenlabs_service = ElevenLabsTTSService()
