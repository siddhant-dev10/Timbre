"""OpenAI-Compatible Chat Completions API for Bolna Telephony Orchestration.

Allows telephony providers (such as Bolna Custom LLM integration) to query Timbre
as an authoritative conversational backend for every telephone turn.
Supports standard JSON responses and Server-Sent Events (SSE) streaming.
Enforces knowledge base grounding, Devanagari Hindi policy, and telephone brevity.
"""
import asyncio
import json
import logging
import re
import secrets
import time
import uuid
from typing import Any, Dict, List, Optional
from fastapi import APIRouter, Depends, Header, HTTPException, Query, Request, status
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.config import settings
from app.database.session import get_db
from app.services.knowledge_service import knowledge_service
from app.services.llm_service import llm_service
from app.services.whisper_service import whisper_service

logger = logging.getLogger("timbre.openai_compat")
router = APIRouter(tags=["Telephony Custom LLM (OpenAI-Compatible)"])


class ChatMessage(BaseModel):
    role: str
    content: Optional[Any] = ""
    name: Optional[str] = None


class ChatCompletionRequest(BaseModel):
    model_config = {"extra": "ignore"}
    model: Optional[str] = "timbre-voice-agent"
    messages: List[ChatMessage]
    temperature: Optional[float] = 0.7
    max_tokens: Optional[int] = 300
    stream: Optional[bool] = False
    user: Optional[str] = None


class ChatChoice(BaseModel):
    index: int
    message: ChatMessage
    finish_reason: str = "stop"


class UsageInfo(BaseModel):
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0


class ChatCompletionResponse(BaseModel):
    id: str
    object: str = "chat.completion"
    created: int
    model: str
    choices: List[ChatChoice]
    usage: UsageInfo


def _get_valid_llm_keys() -> List[str]:
    """Returns valid bearer tokens for authenticating inbound custom LLM calls."""
    keys = []
    if settings.TIMBRE_LLM_API_KEY and settings.TIMBRE_LLM_API_KEY.strip():
        keys.append(settings.TIMBRE_LLM_API_KEY.strip())
    if settings.BOLNA_WEBHOOK_SECRET and settings.BOLNA_WEBHOOK_SECRET.strip():
        keys.append(settings.BOLNA_WEBHOOK_SECRET.strip())
    return keys


def _verify_llm_auth(authorization: Optional[str]) -> None:
    """
    Enforces Bearer token authentication when TIMBRE_LLM_API_KEY or BOLNA_WEBHOOK_SECRET is set.
    Allows unauthenticated requests when no key is configured in backend/.env.
    """
    valid_keys = _get_valid_llm_keys()
    if not valid_keys:
        return

    if not authorization:
        logger.warning("Unauthorized access to Custom LLM endpoint: Missing Authorization header")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing Authorization header.",
        )

    token = (
        authorization[7:].strip()
        if authorization.startswith("Bearer ")
        else authorization.strip()
    )
    if not any(secrets.compare_digest(token, key) for key in valid_keys):
        logger.warning("Unauthorized access to Custom LLM endpoint: Token mismatch")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing Authorization header.",
        )


async def _sse_generator(text: str, model: str):
    """Yields OpenAI-compatible Server-Sent Events (SSE) chunks for streaming telephony."""
    completion_id = f"chatcmpl-{uuid.uuid4().hex[:12]}"
    created_ts = int(time.time())

    # 1. First chunk with assistant role
    first_chunk = {
        "id": completion_id,
        "object": "chat.completion.chunk",
        "created": created_ts,
        "model": model,
        "choices": [{"index": 0, "delta": {"role": "assistant", "content": ""}, "finish_reason": None}],
    }
    yield f"data: {json.dumps(first_chunk, ensure_ascii=False)}\n\n"

    # 2. Yield words/tokens
    words = text.split(" ")
    for idx, word in enumerate(words):
        chunk_content = word if idx == 0 else " " + word
        chunk = {
            "id": completion_id,
            "object": "chat.completion.chunk",
            "created": created_ts,
            "model": model,
            "choices": [{"index": 0, "delta": {"content": chunk_content}, "finish_reason": None}],
        }
        yield f"data: {json.dumps(chunk, ensure_ascii=False)}\n\n"
        await asyncio.sleep(0.015)

    # 3. Final stop chunk
    stop_chunk = {
        "id": completion_id,
        "object": "chat.completion.chunk",
        "created": created_ts,
        "model": model,
        "choices": [{"index": 0, "delta": {}, "finish_reason": "stop"}],
    }
    yield f"data: {json.dumps(stop_chunk, ensure_ascii=False)}\n\n"
    yield "data: [DONE]\n\n"


@router.get("/models")
async def list_models(authorization: Optional[str] = Header(default=None)):
    """Returns available models for standard OpenAI client compatibility."""
    _verify_llm_auth(authorization)

    now = int(time.time())
    return {
        "object": "list",
        "data": [
            {
                "id": "timbre-voice-agent",
                "object": "model",
                "created": now,
                "owned_by": "timbre",
                "permission": [],
                "root": "timbre-voice-agent",
                "parent": None,
            },
            {
                "id": "gpt-4o",
                "object": "model",
                "created": now,
                "owned_by": "timbre",
                "permission": [],
                "root": "gpt-4o",
                "parent": None,
            },
            {
                "id": "gpt-3.5-turbo",
                "object": "model",
                "created": now,
                "owned_by": "timbre",
                "permission": [],
                "root": "gpt-3.5-turbo",
                "parent": None,
            },
        ],
    }


@router.get("/models/{model_id}")
async def get_model(model_id: str, authorization: Optional[str] = Header(default=None)):
    """Returns model metadata for a specific model ID."""
    _verify_llm_auth(authorization)

    return {
        "id": model_id,
        "object": "model",
        "created": int(time.time()),
        "owned_by": "timbre",
        "permission": [],
        "root": model_id,
        "parent": None,
    }


@router.get("/integration-spec")
@router.get("/bolna-spec")
async def get_bolna_spec(public_url: Optional[str] = Query(default=None)):
    """
    Returns the exact configuration specification for connecting Bolna Custom LLM to Timbre.
    """
    url = (public_url or "https://<YOUR-PUBLIC-TUNNEL-URL>").rstrip("/")
    llm_key = settings.TIMBRE_LLM_API_KEY or settings.BOLNA_WEBHOOK_SECRET or "<SET_TIMBRE_LLM_API_KEY_IN_ENV>"
    webhook_secret = settings.BOLNA_WEBHOOK_SECRET or settings.TIMBRE_LLM_API_KEY or "<SET_BOLNA_WEBHOOK_SECRET_IN_ENV>"
    return {
        "bolna_custom_llm_config": {
            "provider": "custom",
            "family": "openai",
            "model": "timbre-voice-agent",
            "base_url": f"{url}/v1",
            "api_key": llm_key,
            "request_json": False,
            "stream": True,
            "temperature": 0.2,
        },
        "bolna_webhook_config": {
            "webhook_url": f"{url}/api/webhooks/bolna?token={webhook_secret}",
            "custom_header": "X-Timbre-Webhook-Secret",
            "custom_header_value": webhook_secret,
        },
        "supported_models": [
            "timbre-voice-agent",
            "gpt-4o",
            "gpt-3.5-turbo",
        ],
        "timbre_architecture": (
            "Bolna Cloud ASR -> HTTP POST /v1/chat/completions -> "
            "Timbre Multilingual RAG & Rules Engine (FastEmbed 384-D) -> "
            "NVIDIA Nemotron 120B Grounded Hindi Response -> Bolna ElevenLabs TTS -> Caller"
        ),
    }


@router.post("/chat/completions")
async def create_chat_completion(
    request: ChatCompletionRequest,
    db: Session = Depends(get_db),
    authorization: Optional[str] = Header(default=None),
):
    """
    Executes a grounded telephony conversational turn:
    1. Authenticates request if TIMBRE_LLM_API_KEY or BOLNA_WEBHOOK_SECRET is configured.
    2. Checks for user stop or termination intent.
    3. Performs RAG retrieval over verified statutory schemes.
    4. Enforces master system prompt rules (brevity, Devanagari Hindi, no hallucinations).
    5. Returns grounded answer formatted for telephony speech synthesis (JSON or SSE stream).
    """
    # Enforce Bearer token authentication
    _verify_llm_auth(authorization)

    # Extract conversation history and last user message
    user_message = ""
    history = []
    for msg in request.messages:
        raw_content = msg.content or ""
        if isinstance(raw_content, list):
            text_parts = [p.get("text", "") for p in raw_content if isinstance(p, dict) and "text" in p]
            content_str = " ".join(text_parts).strip()
        else:
            content_str = str(raw_content)

        if msg.role.lower() == "user":
            user_message = content_str
        history.append({"role": msg.role, "text": content_str})

    if not user_message.strip():
        resp_text = "माफ़ कीजिए, मुझे आपकी आवाज़ स्पष्ट नहीं आई। मैं टिम्ब्रे हूँ, एक एआई नागरिक सहायक। क्या आप अपनी बात दोहरा सकते हैं?"
        if request.stream:
            return StreamingResponse(_sse_generator(resp_text, request.model or "timbre-voice-agent"), media_type="text/event-stream")
        return _make_completion_response(resp_text, model=request.model or "timbre-voice-agent")

    # Word-level English check (strict full words, not substrings)
    is_english = (
        not any('\u0900' <= char <= '\u097f' for char in user_message)
        and bool(re.search(r"\b(what|how|why|can|could|please|tell|explain|where|who|when|document|documents|apply|application|scheme|schemes|pension|ration|eligibility|card|english)\b", user_message.lower()))
    )

    # 1. Stop intent detection
    if whisper_service.detect_stop_intent(user_message):
        resp_text = "धन्यवाद! आपकी इच्छानुसार मैं यह कॉल यहीं समाप्त कर रहा हूँ। नमस्ते।"
        if request.stream:
            return StreamingResponse(_sse_generator(resp_text, request.model or "timbre-voice-agent"), media_type="text/event-stream")
        return _make_completion_response(resp_text, model=request.model or "timbre-voice-agent")

    # 2. RAG Knowledge Retrieval
    retrieved_chunks = knowledge_service.search(db, user_message, top_k=3, min_score=0.30)
    context_str = ""
    if retrieved_chunks:
        evidences = []
        for c in retrieved_chunks:
            evidences.append(
                f"Scheme/Section: {c['section_heading']}\n"
                f"Source: {c['document_title']}\n"
                f"Details: {c['content']}"
            )
        context_str = "\n\n---\n\n".join(evidences)

    lang_instruction = (
        "LANGUAGE: The user is speaking in English. You MUST reply in natural, clear English."
        if is_english
        else "LANGUAGE: Reply in natural, spoken Hindi using Devanagari script (देवनागरी लिपि) by default."
    )

    # 3. Grounded System Prompt
    system_prompt = (
        "You are Timbre, an AI voice assistant for Indian public welfare and civic government services.\n"
        "TELEPHONE RULES:\n"
        "1. AI DISCLOSURE: Disclose you are Timbre, an AI civic assistant, when greeting or identifying yourself.\n"
        f"2. {lang_instruction}\n"
        "3. BREVITY: Keep answers short: 2-3 spoken sentences (maximum 40 words) for natural telephone listening.\n"
        "4. ASK ONE QUESTION: Ask at most ONE clarifying follow-up question at a time.\n"
        "5. STRICT GROUNDING: Base factual claims STRICTLY on the verified context below. Never invent rules, fees, deadlines, or claim to submit applications.\n"
        "6. UNCERTAINTY: If information is not in the context, politely state that verification is pending and direct the caller to the official government portal.\n\n"
        f"VERIFIED KNOWLEDGE BASE EVIDENCE:\n{context_str or 'No matching verified statutory records found.'}"
    )

    # 4. Generate answer via NVIDIA Nemotron or grounded fallback
    ai_text = ""
    if settings.NVIDIA_API_KEY.strip():
        llm_result = await llm_service.generate_response(
            prompt=user_message,
            system_prompt=system_prompt,
            context=history[-6:],
            conversation_id=f"bolna:{uuid.uuid4().hex[:8]}",
        )
        if llm_result.get("success"):
            ai_text = llm_result.get("response", "").strip()

    if not ai_text:
        # Grounded fallback if LLM is unavailable
        if retrieved_chunks:
            top_hit = retrieved_chunks[0]
            if is_english:
                ai_text = (
                    f"Hello, I am Timbre, an AI assistant. Information is available regarding {top_hit['section_heading']}. "
                    "For full statutory eligibility rules and official application procedures, please check the official government portal."
                )
            else:
                ai_text = (
                    f"नमस्ते! मैं टिम्ब्रे हूँ, एक एआई सहायक। आपके प्रश्न के अनुसार {top_hit['section_heading']} की जानकारी उपलब्ध है। "
                    f"विस्तृत नियमों और ऑनलाइन आवेदन के लिए कृपया आधिकारिक सरकारी पोर्टल देखें।"
                )
        else:
            if is_english:
                ai_text = (
                    "I am Timbre, an AI assistant. Verified official records on this specific topic could not be found. "
                    "Please verify with the official department portal."
                )
            else:
                ai_text = (
                    "मैं टिम्ब्रे हूँ, एक एआई सहायक। इस विषय पर अभी सत्यापित सरकारी जानकारी उपलब्ध नहीं है। "
                    "कृपया आधिकारिक संबंधित विभाग के पोर्टल पर जांच करें।"
                )

    if request.stream:
        return StreamingResponse(
            _sse_generator(ai_text, model=request.model or "timbre-voice-agent"),
            media_type="text/event-stream",
        )
    return _make_completion_response(ai_text, model=request.model or "timbre-voice-agent")


def _make_completion_response(text: str, model: str = "timbre-voice-agent") -> ChatCompletionResponse:
    prompt_words = 20
    completion_words = len(text.split())
    return ChatCompletionResponse(
        id=f"chatcmpl-{uuid.uuid4().hex[:12]}",
        created=int(time.time()),
        model=model,
        choices=[
            ChatChoice(
                index=0,
                message=ChatMessage(role="assistant", content=text),
                finish_reason="stop",
            )
        ],
        usage=UsageInfo(
            prompt_tokens=prompt_words * 2,
            completion_tokens=completion_words * 2,
            total_tokens=(prompt_words + completion_words) * 2,
        ),
    )
