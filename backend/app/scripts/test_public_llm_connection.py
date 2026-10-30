"""Safe Authenticated Connection Test for Timbre Public Custom LLM Endpoint.

Sends exactly one non-streaming request to:
https://enticing-astonish-going.ngrok-free.dev/v1/chat/completions

Uses TIMBRE_LLM_API_KEY securely loaded from backend/.env.
Never prints, logs, or exposes secrets.
"""
import json
import sys
import time
from pathlib import Path
import httpx

# Ensure backend root is on sys.path
backend_dir = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(backend_dir))

from app.config import settings

TARGET_URL = "https://enticing-astonish-going.ngrok-free.dev/v1/chat/completions"
MODEL_NAME = "timbre-voice-agent"
TEST_MESSAGE = "Reply with exactly: Timbre connection test successful."


def main():
    llm_key = (settings.TIMBRE_LLM_API_KEY or "").strip()
    if not llm_key:
        print("ERROR: TIMBRE_LLM_API_KEY is not configured in backend/.env.", file=sys.stderr)
        sys.exit(1)

    payload = {
        "model": MODEL_NAME,
        "messages": [
            {"role": "user", "content": TEST_MESSAGE}
        ],
        "stream": False,
    }

    headers = {
        "Authorization": f"Bearer {llm_key}",
        "Content-Type": "application/json",
        "User-Agent": "Bolna-Custom-LLM/1.0",
    }

    start_time = time.perf_counter()
    try:
        with httpx.Client(timeout=30.0) as client:
            resp = client.post(TARGET_URL, json=payload, headers=headers)
        elapsed_sec = time.perf_counter() - start_time
    except Exception as exc:
        elapsed_sec = time.perf_counter() - start_time
        print("=== TEST EXECUTION FAILURE ===")
        print(f"Target URL: {TARGET_URL}")
        print(f"Error Type: {type(exc).__name__}")
        print(f"Error Details: {str(exc)}")
        print(f"Request Duration: {elapsed_sec:.3f}s")
        sys.exit(1)

    print("=== TIMBRE PUBLIC CUSTOM LLM CONNECTION TEST ===")
    print(f"Target URL: {TARGET_URL}")
    print(f"HTTP Status Code: {resp.status_code}")
    print(f"Request Duration: {elapsed_sec:.3f}s ({elapsed_sec * 1000:.1f}ms)")

    # 1. Verify JSON validity
    is_valid_json = False
    data = None
    try:
        data = resp.json()
        is_valid_json = True
    except Exception as json_err:
        print(f"JSON Parsing Error: {json_err}")
        print(f"Raw Response Body (first 200 chars): {resp.text[:200]}")

    print(f"Is Valid JSON: {is_valid_json}")

    if not is_valid_json or not isinstance(data, dict):
        print("RESULT: FAIL (Response is not valid JSON dictionary)")
        sys.exit(1)

    # 2. Check OpenAI Chat Completion Fields
    expected_top_fields = ["id", "object", "created", "model", "choices", "usage"]
    present_top_fields = [f for f in expected_top_fields if f in data]
    missing_top_fields = [f for f in expected_top_fields if f not in data]
    has_expected_fields = len(missing_top_fields) == 0

    print(f"Expected Chat-Completion Fields Present: {has_expected_fields}")
    print(f"  Present fields: {present_top_fields}")
    if missing_top_fields:
        print(f"  Missing fields: {missing_top_fields}")

    # 3. Check choices and assistant response
    choices = data.get("choices", [])
    has_choices = isinstance(choices, list) and len(choices) > 0
    assistant_content = ""
    finish_reason = ""

    if has_choices:
        msg = choices[0].get("message", {})
        assistant_content = msg.get("content", "")
        finish_reason = choices[0].get("finish_reason", "")

    is_non_empty = bool(assistant_content and assistant_content.strip())
    print(f"Assistant Returned Non-Empty Response: {is_non_empty}")
    print(f"  Response Model: {repr(data.get('model'))}")
    print(f"  Finish Reason: {repr(finish_reason)}")
    print(f"  Assistant Content: {repr(assistant_content)}")

    usage = data.get("usage", {})
    print(f"  Usage: prompt_tokens={usage.get('prompt_tokens')}, completion_tokens={usage.get('completion_tokens')}, total_tokens={usage.get('total_tokens')}")

    # 4. Verify request passed through ngrok
    passed_through_ngrok = False
    try:
        with httpx.Client(timeout=3.0) as local_client:
            ngrok_resp = local_client.get("http://127.0.0.1:4040/api/requests/http?limit=1")
        if ngrok_resp.status_code == 200:
            reqs = ngrok_resp.json().get("requests", [])
            if reqs:
                last_req = reqs[0]
                req_path = last_req.get("request", {}).get("uri", "")
                status_code = last_req.get("response", {}).get("status_code")
                if "/v1/chat/completions" in req_path and status_code == resp.status_code:
                    passed_through_ngrok = True
    except Exception:
        pass

    print(f"Verified Request Passed Through Public Ngrok URL: {passed_through_ngrok}")

    # 5. Final Classification
    if resp.status_code == 200 and is_valid_json and has_expected_fields and is_non_empty and passed_through_ngrok:
        print("\nCLASSIFICATION: PASS")
    else:
        print("\nCLASSIFICATION: FAIL")


if __name__ == "__main__":
    main()
