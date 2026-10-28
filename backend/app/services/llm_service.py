import json
import logging
from typing import List, Dict, Any, Optional
import httpx
from app.config import settings
from app.services.catalogue_data import OFFICIAL_SERVICES_CATALOGUE

logger = logging.getLogger("timbre.llm")


class OllamaService:
    def __init__(self):
        self.base_url = settings.OLLAMA_BASE_URL.rstrip("/")
        self.model_name = settings.OLLAMA_MODEL
        self.timeout = settings.OLLAMA_TIMEOUT_SECONDS
        self.num_ctx = settings.OLLAMA_NUM_CTX
        # Cache active conversation token contexts for ongoing multi-turn conversations
        self.conversation_contexts: Dict[str, List[int]] = {}

    async def check_availability(self) -> Dict[str, Any]:
        """Checks if Ollama service is reachable and whether the target model is installed."""
        try:
            async with httpx.AsyncClient(timeout=3.0) as client:
                res = await client.get(f"{self.base_url}/api/tags")
                if res.status_code != 200:
                    return {
                        "available": False,
                        "status": "degraded",
                        "error": f"Ollama HTTP {res.status_code}",
                        "models": []
                    }
                data = res.json()
                models = [m.get("name") for m in data.get("models", [])]
                
                # Check for model match (exact or prefix)
                has_target = any(self.model_name in m or m.startswith(self.model_name) for m in models)
                return {
                    "available": True,
                    "target_model_ready": has_target,
                    "target_model": self.model_name,
                    "installed_models": models,
                    "status": "healthy" if has_target else "model_downloading"
                }
        except Exception as e:
            logger.warning(f"Ollama connection check failed: {e}")
            return {
                "available": False,
                "target_model_ready": False,
                "target_model": self.model_name,
                "error": str(e),
                "status": "unavailable"
            }

    async def generate_response(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        context: Optional[List[int]] = None,
        conversation_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Sends generation request to Ollama with configurable context window.
        Returns generated text and context tokens for ongoing multi-turn conversations.
        """
        avail = await self.check_availability()
        if not avail.get("available") or not avail.get("target_model_ready"):
            return {
                "success": False,
                "response": (
                    "Local LLM is currently initializing or downloading (Qwen 3 9B). "
                    "Grounded catalogue rules and fallback guidance are active."
                ),
                "error": avail.get("error") or "Model not loaded",
                "model_used": "none"
            }

        # Retrieve prior context tokens for this conversation if available
        if conversation_id and not context and conversation_id in self.conversation_contexts:
            context = self.conversation_contexts[conversation_id]

        payload: Dict[str, Any] = {
            "model": self.model_name,
            "prompt": prompt,
            "stream": False,
            "options": {
                "num_ctx": self.num_ctx,
                "temperature": 0.4,
                "num_predict": 300
            }
        }
        if system_prompt:
            payload["system"] = system_prompt
        if context:
            payload["context"] = context

        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                resp = await client.post(f"{self.base_url}/api/generate", json=payload)
                if resp.status_code == 200:
                    data = resp.json()
                    raw_response = data.get("response", "").strip()
                    thinking = data.get("thinking", "").strip()

                    # Handle thinking models where response may be within or following thinking trace
                    if not raw_response and thinking:
                        lines = [line.strip() for line in thinking.split("\n") if line.strip()]
                        for line in reversed(lines):
                            if any(k in line.lower() for k in ["draft", "reply", "answer", "pehle", "namaste", "aavedan"]):
                                candidate = line.split(":", 1)[-1].replace("*", "").replace('"', '').strip()
                                if len(candidate) > 20:
                                    raw_response = candidate
                                    break
                        if not raw_response and lines:
                            raw_response = lines[-1].replace("*", "").replace('"', '').strip()

                    ctx_tokens = data.get("context")
                    if conversation_id and ctx_tokens:
                        self.conversation_contexts[conversation_id] = ctx_tokens

                    return {
                        "success": True,
                        "response": raw_response or "Guidance generated from verified government catalogue.",
                        "thinking": thinking,
                        "context": ctx_tokens,
                        "model_used": self.model_name
                    }
                else:
                    return {
                        "success": False,
                        "response": f"Ollama returned HTTP {resp.status_code}",
                        "error": resp.text,
                        "model_used": self.model_name
                    }
        except httpx.TimeoutException:
            logger.error("Ollama request timed out.")
            return {
                "success": False,
                "response": "LLM inference request timed out. Please retry shortly.",
                "error": "TimeoutException",
                "model_used": self.model_name
            }
        except Exception as e:
            logger.error(f"Error calling Ollama: {e}")
            return {
                "success": False,
                "response": "Could not connect to local Ollama inference server.",
                "error": str(e),
                "model_used": self.model_name
            }

    def build_grounded_system_prompt(self, relevant_services: List[Dict[str, Any]], language: str = "Hinglish") -> str:
        """
        Constructs a concise, domain-grounded system prompt incorporating verified
        statutory Indian government catalogue items.
        """
        services_text = []
        for s in relevant_services:
            services_text.append(
                f"- Scheme: {s['name']} (ID: {s['id']})\n"
                f"  Authority: {s['administering_body']}\n"
                f"  Eligibility: {s['basic_eligibility_criteria']}\n"
                f"  Fee: {s.get('statutory_fee_inr', 0.0)} INR\n"
                f"  Official Portal: {s['official_application_url']}\n"
                f"  Required Documents: {', '.join(s.get('commonly_required_documents', []))}"
            )

        grounding_block = "\n\n".join(services_text)

        lang_instruction = (
            "Respond in clear, natural Hinglish (Hindi written in Roman script mixed with common English administrative terms). "
            "Keep the tone respectful, friendly, and empowering."
            if language.lower() in ("hinglish", "hindi-english") else
            ("Respond purely in clear Hindi (Devanagari script)." if language.lower() == "hindi" else
             "Respond in professional, clear Indian English.")
        )

        return (
            "You are Timbre, an AI voice and digital assistant for Indian public welfare and government services.\n"
            f"{lang_instruction}\n\n"
            "MANDATORY CONVERSATIONAL GUIDELINES:\n"
            "1. Answer ONLY based on the verified government schemes provided below. If official information is missing or unverified, explicitly acknowledge the limitation rather than guessing.\n"
            "2. Never claim or pretend that an application has been submitted, registered, or approved. Clearly distinguish confirmed criteria from potential preliminary eligibility.\n"
            "3. State that all eligibility advice is preliminary and subject to physical document verification by official authorities.\n"
            "4. Ask polite, targeted follow-up questions if critical information (such as age, schooling status, land records, or income) is missing.\n"
            "5. Explain required documents and next steps using the exact official portal URLs provided.\n"
            "6. Keep responses conversational, respectful, warm, and concise (2-4 sentences max), perfectly tuned for voice interaction.\n\n"
            f"VERIFIED SCHEMES CATALOGUE CONTEXT:\n{grounding_block}"
        )


llm_service = OllamaService()
