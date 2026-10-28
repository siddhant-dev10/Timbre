import logging
import uuid
from datetime import datetime, timezone
from typing import Dict, Any, Optional, List
import httpx
from app.config import settings

logger = logging.getLogger("timbre.bolna")


class BolnaIntegrationService:
    def __init__(self):
        self.base_url = settings.BOLNA_BASE_URL.rstrip("/")
        self.api_key = settings.BOLNA_API_KEY.strip()
        self.agent_id = settings.BOLNA_AGENT_ID.strip()
        self.timeout = settings.BOLNA_TIMEOUT_SECONDS
        self.enable_real_calls = settings.ENABLE_REAL_CALLS

    def is_configured(self) -> bool:
        """Checks if Bolna credentials and agent ID are present."""
        return bool(self.api_key and self.agent_id)

    def check_health(self) -> Dict[str, Any]:
        """Provides operational status without exposing secret tokens."""
        configured = self.is_configured()
        return {
            "configured": configured,
            "status": "ready" if configured else "credentials_pending",
            "agent_id_set": bool(self.agent_id),
            "api_key_set": bool(self.api_key),
            "real_calls_enabled": self.enable_real_calls,
            "mode": "live" if (configured and self.enable_real_calls) else "demo_simulation"
        }

    async def initiate_call(
        self,
        citizen_id: str,
        citizen_name: str,
        phone_number: str,
        trigger_event: str,
        is_real_call_requested: bool = False,
        consent_confirmed: bool = False,
        user_data: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Initiates a call job.
        Strict Safety Invariants:
        1. Fictional citizens (CIT-* or DEMO-PHONE-*) are NEVER dialed over telecommunications networks.
        2. Real calls require BOTH:
           - Global settings.ENABLE_REAL_CALLS == True
           - Explicit runtime is_real_call_requested == True
           - Explicit runtime consent_confirmed == True
           - A valid, non-demo phone number supplied at runtime.
        3. If any safety check fails or in demo mode, a synthetic demo call job is safely queued and simulated.
        """
        # Hard check for synthetic citizen identifiers
        is_synthetic_citizen = citizen_id.startswith("CIT-") or "DEMO" in phone_number.upper()

        if is_real_call_requested:
            if is_synthetic_citizen:
                raise ValueError("Safety Violation: Fictional citizen records cannot be dialed. Real calls require a consenting team member's phone number.")
            
            if not self.enable_real_calls:
                raise PermissionError("Real calls are disabled on this server (ENABLE_REAL_CALLS is false in configuration).")

            if not consent_confirmed:
                raise PermissionError("Explicit consent confirmation is mandatory to initiate an outbound call.")

            if not self.is_configured():
                raise RuntimeError("Bolna.ai credentials (BOLNA_API_KEY and BOLNA_AGENT_ID) are not configured.")

            return await self._dispatch_real_bolna_call(
                phone_number=phone_number,
                citizen_name=citizen_name,
                trigger_event=trigger_event,
                user_data=user_data or {}
            )
        else:
            # Default: Simulated demo call
            return self._simulate_demo_call(
                citizen_id=citizen_id,
                citizen_name=citizen_name,
                trigger_event=trigger_event,
                phone_number=phone_number
            )

    async def _dispatch_real_bolna_call(
        self,
        phone_number: str,
        citizen_name: str,
        trigger_event: str,
        user_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Dispatches an authorized real call to the Bolna.ai API."""
        url = f"{self.base_url}/call"
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        payload = {
            "agent_id": self.agent_id,
            "recipient_phone_number": phone_number,
            "user_data": {
                **user_data,
                "citizen_name": citizen_name,
                "trigger_event": trigger_event,
                "dispatched_at": datetime.now(timezone.utc).isoformat()
            }
        }

        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                res = await client.post(url, json=payload, headers=headers)
                if res.status_code in (200, 201):
                    data = res.json()
                    return {
                        "success": True,
                        "status": "QUEUED",
                        "is_real_call": True,
                        "execution_id": data.get("id") or data.get("execution_id"),
                        "raw_response": data
                    }
                else:
                    logger.error(f"Bolna API error: HTTP {res.status_code}")
                    return {
                        "success": False,
                        "status": "FAILED",
                        "is_real_call": True,
                        "error": f"Bolna API returned HTTP {res.status_code}: {res.text}"
                    }
        except Exception as e:
            logger.error(f"Failed to communicate with Bolna API: {e}")
            return {
                "success": False,
                "status": "FAILED",
                "is_real_call": True,
                "error": str(e)
            }

    def _simulate_demo_call(
        self,
        citizen_id: str,
        citizen_name: str,
        trigger_event: str,
        phone_number: str
    ) -> Dict[str, Any]:
        """Generates realistic simulation events and transcript for the Flutter dashboard."""
        now = datetime.now(timezone.utc)
        mock_events = [
            {
                "id": str(uuid.uuid4()),
                "speaker": "AI_AGENT",
                "transcript_segment": f"Namaste {citizen_name} ji! Main Bharat Assist se bol raha hoon. Kya aapke paas 2 minute hain?",
                "timestamp": now.isoformat(),
                "latency_ms": 320
            },
            {
                "id": str(uuid.uuid4()),
                "speaker": "CITIZEN",
                "transcript_segment": "Haan boliye, kya baat hai?",
                "timestamp": now.isoformat(),
                "latency_ms": 280
            },
            {
                "id": str(uuid.uuid4()),
                "speaker": "AI_AGENT",
                "transcript_segment": (
                    f"Aapne hal hi mein {trigger_event} milestone achieve kiya hai. Aap ECI Voter ID Form 6 "
                    "aur Driving Licence ke liye eligible hain. Kya aap aavedan process samajhna chahenge?"
                ),
                "timestamp": now.isoformat(),
                "latency_ms": 450
            },
            {
                "id": str(uuid.uuid4()),
                "speaker": "CITIZEN",
                "transcript_segment": "Achha! Konsa documents chahiye honge?",
                "timestamp": now.isoformat(),
                "latency_ms": 310
            },
            {
                "id": str(uuid.uuid4()),
                "speaker": "AI_AGENT",
                "transcript_segment": (
                    "Sirf aapka Aadhaar card aur ek passport size photo chahiye. "
                    "Aap voters.eci.gov.in portal par jakar free aavedan kar sakte hain. "
                    "Main aapke registered number par official link bhej deta hoon."
                ),
                "timestamp": now.isoformat(),
                "latency_ms": 390
            }
        ]

        return {
            "success": True,
            "status": "COMPLETED",
            "is_real_call": False,
            "execution_id": f"sim-{uuid.uuid4()}",
            "duration_seconds": 45,
            "transcript_events": mock_events
        }


bolna_service = BolnaIntegrationService()
