"""NVIDIA Nemotron adapter using NVIDIA's OpenAI-compatible chat API."""
import logging
from typing import Any, Dict, List, Optional

import httpx

from app.config import settings

logger = logging.getLogger("timbre.ai")


class NVIDIAProvider:
    """NVIDIA-hosted Nemotron API adapter; conversation history is process-local."""

    def __init__(self) -> None:
        self._history: Dict[str, List[Dict[str, str]]] = {}

    async def check_availability(self, check_connectivity: bool = False) -> Dict[str, Any]:
        configured = bool(settings.NVIDIA_API_KEY.strip())
        if not configured:
            return {
                "available": False,
                "status": "credentials_pending",
                "provider": "NVIDIA Nemotron API",
                "model": settings.NVIDIA_MODEL,
                "connectivity_checked": check_connectivity,
                "details": "NVIDIA_API_KEY is not configured in backend/.env.",
            }

        if not check_connectivity:
            return {
                "available": True,
                "status": "configured",
                "provider": "NVIDIA Nemotron API",
                "model": settings.NVIDIA_MODEL,
                "connectivity_checked": False,
                "details": f"Provider: NVIDIA Nemotron API, model: {settings.NVIDIA_MODEL}; credentials present, connectivity not checked.",
            }

        # Perform lightweight, zero-token connectivity check via GET /models
        url = f"{settings.NVIDIA_BASE_URL.rstrip('/')}/models"
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.get(url, headers=self._headers())
            if resp.status_code == 200:
                data = resp.json()
                models = [m.get("id") for m in data.get("data", []) if isinstance(m, dict)]
                model_found = settings.NVIDIA_MODEL in models
                return {
                    "available": True,
                    "status": "healthy",
                    "provider": "NVIDIA Nemotron API",
                    "model": settings.NVIDIA_MODEL,
                    "connectivity_checked": True,
                    "model_verified": model_found,
                    "details": f"Provider: NVIDIA Nemotron API, model: {settings.NVIDIA_MODEL}; live connectivity verified.",
                }
            elif resp.status_code == 401:
                return {
                    "available": False,
                    "status": "unauthorized",
                    "provider": "NVIDIA Nemotron API",
                    "model": settings.NVIDIA_MODEL,
                    "connectivity_checked": True,
                    "details": "NVIDIA authentication failed: API key rejected (HTTP 401).",
                }
            elif resp.status_code == 403:
                return {
                    "available": False,
                    "status": "forbidden",
                    "provider": "NVIDIA Nemotron API",
                    "model": settings.NVIDIA_MODEL,
                    "connectivity_checked": True,
                    "details": "NVIDIA access forbidden for this account or model (HTTP 403).",
                }
            else:
                return {
                    "available": False,
                    "status": "unavailable",
                    "provider": "NVIDIA Nemotron API",
                    "model": settings.NVIDIA_MODEL,
                    "connectivity_checked": True,
                    "details": f"NVIDIA endpoint returned HTTP {resp.status_code}.",
                }
        except httpx.TimeoutException:
            return {
                "available": False,
                "status": "unavailable",
                "provider": "NVIDIA Nemotron API",
                "model": settings.NVIDIA_MODEL,
                "connectivity_checked": True,
                "details": "NVIDIA connectivity check timed out.",
            }
        except Exception as exc:
            return {
                "available": False,
                "status": "unavailable",
                "provider": "NVIDIA Nemotron API",
                "model": settings.NVIDIA_MODEL,
                "connectivity_checked": True,
                "details": f"Could not reach NVIDIA: {type(exc).__name__}",
            }

    def build_grounded_system_prompt(
        self, relevant_services: List[Dict[str, Any]], language: str = "Hindi"
    ) -> str:
        services = []
        for service in relevant_services:
            if service.get("verification_status") != "VERIFIED":
                services.append("\n".join([
                    f"Service: {service.get('name', 'Unknown service')}",
                    f"Verification status: {service.get('verification_status', 'NEEDS_REVIEW')}",
                    f"Official source listed for review: {service.get('official_source_url', 'unknown')}",
                    "This entry is pending human source review. Do not use it to state eligibility, documents, fees, deadlines, or application steps.",
                ]))
                continue
            services.append("\n".join([
                f"Service: {service['name']}",
                f"Authority: {service['administering_body']}",
                f"Eligibility: {service['basic_eligibility_criteria']}",
                f"Fee (catalogue): {service.get('statutory_fee_inr', 'unknown')} INR",
                f"Official portal: {service['official_application_url']}",
                f"Official source: {service.get('official_source_url', 'unknown')}",
                f"Verification status: {service.get('verification_status', 'NEEDS_REVIEW')}",
                f"Last checked: {service.get('last_verification_date', 'unknown')}",
                "Documents: " + ", ".join(service.get("commonly_required_documents", [])),
            ]))

        lang_lower = (language or "hindi").lower()
        if lang_lower == "english":
            language_instruction = "Reply in polite, clear Indian English."
        elif lang_lower == "hinglish":
            language_instruction = "Reply in natural, concise Hinglish using Roman script."
        else:
            language_instruction = (
                "Reply in natural, polite, spoken Hindi using Devanagari script (देवनागरी लिपि). "
                "Understand Hinglish and mixed English words naturally, but keep your spoken response in Hindi."
            )

        return (
            "You are Timbre, a conversational AI voice assistant for Indian public welfare and government services.\n\n"
            f"COMMUNICATION RULES:\n"
            f"1. {language_instruction}\n"
            "2. Keep replies natural and concise for telephone listening: 2-3 short spoken sentences (maximum 40-50 words).\n"
            "3. Ask at most ONE clear question at a time. Never overwhelm the caller with multiple questions or lists.\n"
            "4. Be respectful, warm, and helpful (use 'आप', 'नमस्ते'). Do not repeat the exact same sentence turn after turn.\n"
            "5. Never claim to be human. Introduce Timbre as an AI assistant ('मैं एक AI सहायक हूँ') when appropriate.\n"
            "6. If the citizen wants to stop, cancel, or hang up ('रुको', 'फोन काटो', 'नहीं चाहिए', 'stop', 'bye'), politely conclude ('धन्यवाद, मैं यह कॉल समाप्त कर रहा हूँ। नमस्ते।') and stop.\n"
            "7. Grounding Invariant: Use ONLY verified catalogue facts below. Never invent document requirements, fees, application links, or eligibility promises. "
            "If an entry is unverified or information is missing, state that it is unverified and advise checking the official portal.\n"
            "8. Never read or ask for sensitive numbers like Aadhaar or bank account details.\n\n"
            "Catalogue entries:\n"
            + ("\n\n".join(services) if services else "No matching verified catalogue entries.")
        )

    def _messages(self, prompt: str, system_prompt: Optional[str], context: Optional[List[Dict[str, str]]], conversation_id: Optional[str]):
        history = list(context or self._history.get(conversation_id or "", []))
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.extend(
            {"role": turn["role"], "content": turn["text"]}
            for turn in history[-10:]
            if turn.get("role") in ("user", "assistant") and turn.get("text")
        )
        messages.append({"role": "user", "content": prompt})
        return messages, history

    def _payload(self, messages: List[Dict[str, str]], stream: bool = False) -> Dict[str, Any]:
        effort = settings.NVIDIA_REASONING_EFFORT.strip().lower()
        if effort not in {"none", "low", "high"}:
            effort = "none"
        return {
            "model": settings.NVIDIA_MODEL,
            "messages": messages,
            "max_tokens": settings.NVIDIA_MAX_TOKENS,
            "temperature": settings.NVIDIA_TEMPERATURE,
            "top_p": settings.NVIDIA_TOP_P,
            "reasoning_effort": effort,
            "stream": stream,
        }

    def _headers(self) -> Dict[str, str]:
        return {"Authorization": f"Bearer {settings.NVIDIA_API_KEY.strip()}", "Content-Type": "application/json"}

    def _error(self, status_code: int) -> str:
        messages = {
            400: "NVIDIA rejected the request. Check the configured model and generation settings.",
            401: "NVIDIA authentication failed. Check NVIDIA_API_KEY in backend/.env.",
            403: "NVIDIA access is unavailable for this account or model.",
            402: "NVIDIA account or endpoint payment limit was reached.",
            429: "NVIDIA quota or rate limit reached. Check the Build endpoint limits and retry later.",
            503: "NVIDIA endpoint is temporarily unavailable. Please retry shortly.",
        }
        return messages.get(status_code, f"NVIDIA request failed (HTTP {status_code}).")

    async def generate_response(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        context: Optional[List[Dict[str, str]]] = None,
        conversation_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        if not settings.NVIDIA_API_KEY.strip():
            return {"success": False, "error": "NVIDIA API key is not configured."}
        messages, history = self._messages(prompt, system_prompt, context, conversation_id)
        url = f"{settings.NVIDIA_BASE_URL.rstrip('/')}/chat/completions"
        try:
            async with httpx.AsyncClient(timeout=settings.NVIDIA_TIMEOUT_SECONDS) as client:
                response = await client.post(url, headers=self._headers(), json=self._payload(messages))
            if response.status_code not in (200, 202):
                logger.warning("NVIDIA request failed with HTTP %s", response.status_code)
                return {"success": False, "error": self._error(response.status_code), "status_code": response.status_code}
            if response.status_code == 202:
                return {"success": False, "error": "NVIDIA accepted the request but has not completed it yet. Please retry.", "status_code": 503}
            data = response.json()
            choices = data.get("choices", []) if isinstance(data, dict) else []
            message = choices[0].get("message", {}) if choices and isinstance(choices[0], dict) else {}
            answer = message.get("content", "") if isinstance(message, dict) else ""
            if not isinstance(answer, str) or not answer.strip():
                return {"success": False, "error": "NVIDIA returned no text. Please try again."}
            answer = answer.strip()
            if conversation_id:
                history.extend([{"role": "user", "text": prompt}, {"role": "assistant", "text": answer}])
                self._history[conversation_id] = history[-20:]
            return {"success": True, "response": answer, "model_used": settings.NVIDIA_MODEL}
        except httpx.TimeoutException:
            logger.warning("NVIDIA request timed out")
            return {"success": False, "error": "NVIDIA request timed out. Please retry."}
        except httpx.RequestError as exc:
            logger.warning("NVIDIA network request failed (%s)", type(exc).__name__)
            return {"success": False, "error": "Could not reach NVIDIA. Check the Mac's internet connection."}
        except (ValueError, KeyError, TypeError, IndexError):
            logger.warning("NVIDIA returned an invalid response payload")
            return {"success": False, "error": "NVIDIA returned an invalid response. Please retry."}


llm_service = NVIDIAProvider()
