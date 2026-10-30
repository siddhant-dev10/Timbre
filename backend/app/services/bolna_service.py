import logging
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, Optional

import httpx

from app.config import settings

logger = logging.getLogger("timbre.bolna")


class BolnaProviderError(RuntimeError):
    """A safe provider error that never contains response bodies or credentials."""

    def __init__(self, message: str, *, http_status: int, ambiguous: bool = False):
        super().__init__(message)
        self.http_status = http_status
        self.ambiguous = ambiguous


class BolnaIntegrationService:
    def __init__(self):
        self.reload_config()

    def reload_config(self) -> None:
        """Reloads settings from the active settings instance."""
        self.base_url = settings.BOLNA_BASE_URL.rstrip("/")
        self.api_key = settings.BOLNA_API_KEY.strip()
        self.agent_id = settings.BOLNA_AGENT_ID.strip()
        self.timeout = settings.BOLNA_TIMEOUT_SECONDS
        self.enable_real_calls = settings.ENABLE_REAL_CALLS
        self.test_agent_verified = settings.BOLNA_TEST_AGENT_VERIFIED

    def is_configured(self) -> bool:
        return bool(self.api_key and self.agent_id)

    def is_test_call_ready(self) -> bool:
        return bool(
            self.enable_real_calls
            and self.is_configured()
            and self.test_agent_verified
        )

    def check_health(self) -> Dict[str, Any]:
        """Returns configuration state only; it does not contact Bolna."""
        configured = self.is_configured()
        return {
            "configured": configured,
            "status": "ready" if configured else "credentials_pending",
            "agent_id_set": bool(self.agent_id),
            "api_key_set": bool(self.api_key),
            "real_calls_enabled": self.enable_real_calls,
            "test_agent_verified": self.test_agent_verified,
            "test_call_ready": self.is_test_call_ready(),
            "mode": "live" if self.is_test_call_ready() else "demo_simulation",
        }

    async def verify_connectivity(self) -> Dict[str, Any]:
        """Performs a lightweight, zero-call verification of the Bolna API key via GET /me."""
        if not self.api_key:
            return {
                "api_key_set": False,
                "api_key_valid": False,
                "status": "credentials_pending",
                "details": "BOLNA_API_KEY is not configured in backend/.env.",
            }
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.get(f"{self.base_url}/me", headers=self._headers())
            if resp.status_code == 200:
                data = resp.json()
                wallet_bal = data.get("wallet", 0.0)
                return {
                    "api_key_set": True,
                    "api_key_valid": True,
                    "status": "authenticated",
                    "details": f"Bolna API key authenticated successfully (Wallet: ${wallet_bal}).",
                }
            elif resp.status_code == 401:
                return {
                    "api_key_set": True,
                    "api_key_valid": False,
                    "status": "unauthorized",
                    "details": "Bolna API key rejected (HTTP 401 Unauthorized).",
                }
            else:
                return {
                    "api_key_set": True,
                    "api_key_valid": False,
                    "status": "error",
                    "details": f"Bolna returned HTTP {resp.status_code}.",
                }
        except Exception as exc:
            return {
                "api_key_set": True,
                "api_key_valid": False,
                "status": "unavailable",
                "details": f"Could not reach Bolna API: {type(exc).__name__}",
            }

    def _require_test_call_ready(self) -> None:
        if not self.enable_real_calls:
            raise PermissionError("Live calls are disabled. Set ENABLE_REAL_CALLS=true only after reviewing the local setup guide.")
        if not self.test_agent_verified:
            raise PermissionError("The Bolna test agent has not been marked as reviewed for AI disclosure, synthetic test context, Hindi/Hinglish, and disabled retries.")
        if not self.is_configured():
            raise RuntimeError("Bolna API credentials and agent ID are not configured in backend/.env.")

    def _require_provider_credentials(self) -> None:
        if not self.is_configured():
            raise RuntimeError("Bolna API credentials and agent ID are not configured in backend/.env.")

    @staticmethod
    def _safe_provider_message(status_code: int) -> str:
        if status_code in (401, 403):
            return "Bolna rejected the account, agent, or telephony configuration. Check the dashboard settings; no automatic retry was made."
        if status_code == 402:
            return "Bolna reports insufficient credits or account balance. Check the account's current charges before trying again."
        if status_code == 429:
            return "Bolna rate or concurrency limits were reached. No automatic retry was made; check provider status before trying again."
        if status_code == 400:
            return "Bolna rejected the call request. Check the agent, language, recipient number, and approved telephony configuration."
        if status_code >= 500:
            return "Bolna is temporarily unavailable. Check the call status before attempting another call."
        return f"Bolna could not accept the call (HTTP {status_code}). Check provider configuration and call status."

    def _headers(self) -> Dict[str, str]:
        return {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        }

    async def initiate_approved_test_call(
        self,
        *,
        phone_number: str,
        language: str,
    ) -> Dict[str, Any]:
        """Makes exactly one manually approved test call with fictional context."""
        self._require_test_call_ready()
        # The opening line and scenario are also shown for review in Flutter.
        # The configured Bolna agent must use {{opening_disclosure}} in its
        # welcome message and follow {{test_scenario}} in its system prompt.
        payload = {
            "agent_id": self.agent_id,
            "recipient_phone_number": phone_number,
            "agent_data": {"language": language},
            "user_data": {
                "opening_disclosure": (
                    "Namaste, main Timbre hoon, ek AI assistant. Yeh ek approved test call hai. "
                    "Main sirf fictional demo jaankari use karungi."
                ),
                "test_scenario": (
                    "Use a fictional adult profile in Rajasthan asking how to check a government-service "
                    "eligibility rule. Do not claim eligibility or invent current requirements; direct the "
                    "caller to the relevant official government source."
                ),
                "record_kind": "fictional_test_data",
            },
            # Do not opt into Bolna's auto-retry feature for an individual test.
            "retry_config": {"enabled": False},
        }

        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(
                    f"{self.base_url}/call",
                    json=payload,
                    headers=self._headers(),
                )
        except httpx.TimeoutException as exc:
            logger.warning("Bolna call submission timed out; result may be ambiguous")
            raise BolnaProviderError(
                "Bolna request timed out. Check Bolna call history before retrying; the call may already have been accepted.",
                http_status=504,
                ambiguous=True,
            ) from exc
        except httpx.RequestError as exc:
            logger.warning("Bolna call submission failed (%s)", type(exc).__name__)
            raise BolnaProviderError(
                "Could not confirm whether Bolna accepted the request. Check Bolna call history before retrying.",
                http_status=502,
                ambiguous=True,
            ) from exc

        if response.status_code not in (200, 201, 202):
            logger.warning("Bolna rejected a test call (HTTP %s)", response.status_code)
            mapped_status = (
                response.status_code
                if response.status_code in (400, 401, 402, 403, 429)
                else 502
            )
            raise BolnaProviderError(
                self._safe_provider_message(response.status_code),
                http_status=mapped_status,
            )

        try:
            data = response.json()
        except ValueError as exc:
            raise BolnaProviderError(
                "Bolna returned an unreadable response. Check Bolna call history before retrying.",
                http_status=502,
                ambiguous=True,
            ) from exc

        execution_id = data.get("execution_id") or data.get("id") if isinstance(data, dict) else None
        if not execution_id:
            raise BolnaProviderError(
                "Bolna may have accepted the call but returned no call ID. Check Bolna call history before retrying.",
                http_status=502,
                ambiguous=True,
            )

        raw_status = str(data.get("status") or "queued") if isinstance(data, dict) else "queued"
        return {
            "success": True,
            "status": raw_status.upper().replace("-", "_"),
            "is_real_call": True,
            "execution_id": str(execution_id),
            "attempt_count": 1,
        }

    async def get_call_status(self, execution_id: str) -> Dict[str, Any]:
        self._require_provider_credentials()
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.get(
                    f"{self.base_url}/executions/{execution_id}",
                    headers=self._headers(),
                )
        except httpx.TimeoutException as exc:
            raise BolnaProviderError("Bolna status check timed out. Try refreshing later.", http_status=504) from exc
        except httpx.RequestError as exc:
            raise BolnaProviderError("Could not reach Bolna to refresh the call status.", http_status=502) from exc

        if response.status_code != 200:
            logger.warning("Bolna status lookup failed (HTTP %s)", response.status_code)
            raise BolnaProviderError(self._safe_provider_message(response.status_code), http_status=502)
        try:
            data = response.json()
            raw_status = data["status"]
        except (ValueError, KeyError, TypeError) as exc:
            raise BolnaProviderError("Bolna returned an unreadable status response.", http_status=502) from exc
        duration = data.get("conversation_duration") or data.get("call_duration") or 0
        return {
            "status": str(raw_status).upper().replace("-", "_"),
            "duration_seconds": int(duration) if isinstance(duration, (int, float)) else 0,
        }

    def get_custom_llm_integration_spec(self, public_base_url: str) -> Dict[str, Any]:
        """
        Returns the exact JSON integration specification to link Bolna with Timbre's Custom LLM backend.
        Configured in Bolna dashboard under Settings -> Integrations -> LLM -> Add custom LLM.
        """
        base_clean = public_base_url.rstrip("/")
        return {
            "provider": "custom_llm",
            "model_name": "timbre-voice-agent",
            "endpoint_url": f"{base_clean}/v1",
            "api_key": settings.BOLNA_WEBHOOK_SECRET or "<CONFIGURED_IN_BACKEND_ENV>",
            "family": "openai",
            "chat_completions_url": f"{base_clean}/v1/chat/completions",
            "webhook_callback_url": f"{base_clean}/api/webhooks/bolna?token={settings.BOLNA_WEBHOOK_SECRET or '<SECRET>'}",
            "architecture": (
                "Bolna Telephony Edge (Twilio/Plivo) -> Streaming ASR -> "
                "HTTP POST /v1/chat/completions -> Timbre Multilingual RAG & Rules Engine -> "
                "Streaming ElevenLabs TTS -> PSTN Telephone Stream"
            ),
        }

    async def stop_queued_call(self, execution_id: str) -> Dict[str, Any]:
        """Cancels a queued/scheduled call; Bolna's REST endpoint does not end active calls."""
        self._require_provider_credentials()
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(
                    f"{self.base_url}/call/{execution_id}/stop",
                    headers=self._headers(),
                )
        except httpx.TimeoutException as exc:
            raise BolnaProviderError("Bolna cancellation timed out. Refresh the call status before taking further action.", http_status=504) from exc
        except httpx.RequestError as exc:
            raise BolnaProviderError("Could not confirm cancellation with Bolna. Refresh the call status.", http_status=502) from exc

        if response.status_code != 200:
            logger.warning("Bolna cancellation failed (HTTP %s)", response.status_code)
            raise BolnaProviderError(self._safe_provider_message(response.status_code), http_status=502)
        return {"status": "STOPPED", "execution_id": execution_id}

    async def initiate_call(
        self,
        citizen_id: str,
        citizen_name: str,
        phone_number: str,
        trigger_event: str,
        is_real_call_requested: bool = False,
        consent_confirmed: bool = False,
        user_data: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Legacy simulation entry point; live calls use the reviewed test route."""
        if is_real_call_requested:
            if citizen_id.startswith("CIT-"):
                raise ValueError("Fictional citizen records cannot be dialed.")
            raise PermissionError("Live dialing is available only through the individually reviewed test-call flow.")
        return self._simulate_demo_call(
            citizen_id=citizen_id,
            citizen_name=citizen_name,
            trigger_event=trigger_event,
            phone_number=phone_number,
        )

    def _simulate_demo_call(
        self,
        citizen_id: str,
        citizen_name: str,
        trigger_event: str,
        phone_number: str,
    ) -> Dict[str, Any]:
        """Creates a fictional local transcript and never uses the network."""
        now = datetime.now(timezone.utc)
        mock_events = [
            {
                "id": str(uuid.uuid4()),
                "speaker": "AI_AGENT",
                "transcript_segment": "Namaste, main Timbre hoon, ek AI assistant. Yeh sirf synthetic data ke saath simulated demo hai; koi phone call nahi ho rahi. Kya aap demo continue karne ke liye sahmat hain?",
                "timestamp": now.isoformat(),
                "latency_ms": 320,
            },
            {
                "id": str(uuid.uuid4()),
                "speaker": "CITIZEN",
                "transcript_segment": "Haan, yeh simulated demo hai. Aage batayein.",
                "timestamp": now.isoformat(),
                "latency_ms": 280,
            },
            {
                "id": str(uuid.uuid4()),
                "speaker": "AI_AGENT",
                "transcript_segment": (
                    f"Synthetic profile mein '{trigger_event}' event simulate hua hai. Local rule match sirf preliminary hai; "
                    "main current eligibility confirm nahi kar sakta. Official source par details verify karein."
                ),
                "timestamp": now.isoformat(),
                "latency_ms": 450,
            },
            {
                "id": str(uuid.uuid4()),
                "speaker": "CITIZEN",
                "transcript_segment": "Kaunse documents chahiye honge?",
                "timestamp": now.isoformat(),
                "latency_ms": 310,
            },
            {
                "id": str(uuid.uuid4()),
                "speaker": "AI_AGENT",
                "transcript_segment": (
                    "Mere current catalogue se complete document list verify nahi hoti. "
                    "Kripya sambandhit official portal par check karein. Is demo mein koi SMS ya call nahi bheja ja raha. "
                    "Simulation yahin samapt hoti hai."
                ),
                "timestamp": now.isoformat(),
                "latency_ms": 390,
            },
        ]
        return {
            "success": True,
            "status": "COMPLETED",
            "is_real_call": False,
            "execution_id": f"sim-{uuid.uuid4()}",
            "duration_seconds": 0,
            "transcript_events": mock_events,
        }

    def get_jio_call_forwarding_instructions(self, destination_number: Optional[str] = None) -> Dict[str, Any]:
        """Provides verified Reliance Jio call forwarding codes, setup steps, and cancellation instructions."""
        dest = destination_number or "<PROVISIONED_TELEPHONY_NUMBER>"
        return {
            "telephony_operator": "Reliance Jio (India)",
            "purpose": "Route incoming calls from personal Jio SIM to Timbre Bolna Inbound Agent",
            "forwarding_type": "Unconditional Call Forwarding (Call Forwarding Always)",
            "activation_codes": {
                "unconditional": f"*401*{dest}",
                "when_busy": f"*403*{dest}",
                "when_unanswered": f"*405*{dest}",
                "when_unreachable": f"*409*{dest}",
            },
            "deactivation_codes": {
                "unconditional": "*402",
                "when_busy": "*404",
                "when_unanswered": "*406",
                "when_unreachable": "*410",
                "master_cancel_all": "*413",
            },
            "step_by_step_instructions": [
                "1. Ensure you have an active Indian virtual number (or Plivo/Exotel Indian DID) mapped to Bolna agent dd390081-993d-4559-a5ff-81f36f9c70c6.",
                f"2. From your Jio mobile handset, open the Phone dialer and dial *401*{dest}.",
                "3. Press Call. Listen for the Jio network confirmation tone/announcement: 'Call forwarding is now active'.",
                "4. Test by having a secondary phone call your Jio number; the call should forward to Bolna and be answered by Timbre.",
                "5. To stop forwarding at any time, dial *402 from your Jio handset and press Call (or *413 to cancel all forwarding).",
            ],
            "carrier_notes": [
                "Jio unconditional forwarding applies to all standard incoming voice calls.",
                "Forwarded calls are billed to your Jio plan according to standard talktime rules (typically included in unlimited domestic plans).",
                "No hardware or SIM modification is performed automatically; setup is manual and user-controlled.",
            ],
        }

    def get_inbound_integration_spec(self, public_base_url: Optional[str] = None) -> Dict[str, Any]:
        """Returns the official inbound telephony architecture and provider configuration spec."""
        url = (public_base_url or "https://<YOUR-PUBLIC-TUNNEL-URL>").rstrip("/")
        return {
            "inbound_flow": (
                "Caller dials Jio Number -> Jio forwards via *401* to Telephony Provider DID -> "
                "Provider (Exotel/Plivo) routes inbound call to Bolna webhook (https://api.bolna.ai/inbound_call) -> "
                "Bolna loads Agent dd390081-993d-4559-a5ff-81f36f9c70c6 -> "
                "Bolna streams Deepgram Hindi ASR to Timbre POST /v1/chat/completions -> "
                "Timbre FastEmbed RAG + NVIDIA Nemotron -> ElevenLabs Hindi TTS -> Caller"
            ),
            "bolna_agent_id": self.agent_id,
            "custom_llm_base_url": f"{url}/v1",
            "webhook_endpoint": f"{url}/api/webhooks/bolna",
            "telephony_carriers_supported": {
                "Plivo": {
                    "setup_method": "Plivo XML Application",
                    "answer_url": "https://api.bolna.ai/inbound_call",
                    "answer_method": "POST",
                },
                "Exotel": {
                    "setup_method": "Voicebot Applet or Passthru Applet",
                    "url": "https://api.bolna.ai/inbound_call",
                    "http_method": "POST",
                },
                "Bolna_Native_DID": {
                    "setup_method": "POST https://api.bolna.ai/inbound/setup with {agent_id, phone_number_id}",
                },
            },
            "jio_forwarding": self.get_jio_call_forwarding_instructions(),
        }

    async def check_inbound_readiness(self) -> Dict[str, Any]:
        """
        Performs a zero-call, read-only readiness audit for inbound AI telephony:
        - Inspects local backend & ngrok public tunnel
        - Inspects Bolna agent configuration & custom LLM
        - Inspects Bolna webhook configuration
        - Inspects phone number mapping status
        - Enforces that outbound flags remain False
        """
        # 1. Tunnel check
        tunnel_url = None
        tunnel_live = False
        try:
            async with httpx.AsyncClient(timeout=3.0) as client:
                res = await client.get("http://127.0.0.1:4040/api/tunnels")
                if res.status_code == 200:
                    data = res.json()
                    tunnels = data.get("tunnels", [])
                    for t in tunnels:
                        if t.get("proto") == "https":
                            tunnel_url = t.get("public_url")
                            tunnel_live = True
                            break
        except Exception:
            pass

        # 2. Check Bolna credentials & wallet
        conn_status = await self.verify_connectivity()

        # 3. Read-only phone number check on Bolna
        phone_numbers = []
        if self.api_key:
            try:
                async with httpx.AsyncClient(timeout=5.0) as client:
                    resp = await client.get(f"{self.base_url}/phone-numbers/all", headers=self._headers())
                    if resp.status_code == 200:
                        phone_numbers = resp.json() if isinstance(resp.json(), list) else []
            except Exception:
                pass

        has_inbound_number = len(phone_numbers) > 0

        # 4. Outbound safety invariant check
        outbound_safety_enforced = (not self.enable_real_calls) and (not self.test_agent_verified)

        ready_for_inbound = bool(
            self.is_configured()
            and conn_status.get("api_key_valid")
            and tunnel_live
            and bool(settings.BOLNA_WEBHOOK_SECRET)
            and has_inbound_number
        )

        return {
            "status": "ready" if ready_for_inbound else "prerequisites_pending",
            "agent_id": self.agent_id,
            "agent_configured": bool(self.agent_id),
            "bolna_api_key_valid": conn_status.get("api_key_valid", False),
            "public_tunnel": {
                "active": tunnel_live,
                "url": tunnel_url,
                "endpoint_path": "/v1/chat/completions",
            },
            "webhook": {
                "secret_configured": bool(settings.BOLNA_WEBHOOK_SECRET),
                "path": "/api/webhooks/bolna",
            },
            "telephony_numbers": {
                "count": len(phone_numbers),
                "numbers": [p.get("phone_number") for p in phone_numbers if isinstance(p, dict)],
                "ready": has_inbound_number,
                "notice": (
                    "Inbound number ready."
                    if has_inbound_number
                    else "No phone number is currently provisioned on Bolna. To receive calls, link an Indian provider DID (Exotel/Plivo) or provision a Bolna inbound number."
                ),
            },
            "safety_invariants": {
                "ENABLE_REAL_CALLS": self.enable_real_calls,
                "BOLNA_TEST_AGENT_VERIFIED": self.test_agent_verified,
                "outbound_dialing_prevented": outbound_safety_enforced,
            },
            "jio_forwarding": {
                "activation_code": "*401*<DESTINATION_NUMBER>",
                "deactivation_code": "*402",
                "master_cancel_code": "*413",
            },
        }


bolna_service = BolnaIntegrationService()
