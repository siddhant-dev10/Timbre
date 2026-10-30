"""Safe Authenticated Streaming Connection Test for Timbre Public Custom LLM Endpoint.

Sends exactly one streaming POST request (stream=True) to:
https://enticing-astonish-going.ngrok-free.dev/v1/chat/completions

Verifies:
1. HTTP status code is 200
2. Content-Type is text/event-stream
3. Server-Sent Events (SSE) formatting (data: {...})
4. JSON chunk schema (chat.completion.chunk)
5. Stream termination with 'data: [DONE]'
6. Complete response reconstruction from deltas
7. Time to first token/chunk (TTFT) and total duration
8. Request traversal through public ngrok URL

Never prints, logs, or exposes secrets.
"""
import json
import sys
import time
from pathlib import Path
from typing import Any, Dict, List
import httpx

# Ensure backend root is on sys.path
backend_dir = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(backend_dir))

from app.config import settings

TARGET_URL = "https://enticing-astonish-going.ngrok-free.dev/v1/chat/completions"
MODEL_NAME = "timbre-voice-agent"
TEST_MESSAGE = "Reply with exactly: Timbre streaming SSE connection test successful."


def run_streaming_test() -> Dict[str, Any]:
    llm_key = (settings.TIMBRE_LLM_API_KEY or "").strip()
    if not llm_key:
        print("ERROR: TIMBRE_LLM_API_KEY is not configured in backend/.env.", file=sys.stderr)
        sys.exit(1)

    payload = {
        "model": MODEL_NAME,
        "messages": [
            {"role": "user", "content": TEST_MESSAGE}
        ],
        "stream": True,
    }

    headers = {
        "Authorization": f"Bearer {llm_key}",
        "Content-Type": "application/json",
        "Accept": "text/event-stream",
        "User-Agent": "Bolna-Custom-LLM-Streamer/1.0",
    }

    results = {
        "target_url": TARGET_URL,
        "http_status": None,
        "content_type": None,
        "is_sse_content_type": False,
        "ttft_ms": None,
        "total_duration_ms": None,
        "raw_event_count": 0,
        "parsed_chunk_count": 0,
        "saw_done_marker": False,
        "all_chunks_valid_json": True,
        "all_chunks_match_schema": True,
        "reconstructed_content": "",
        "passed_through_ngrok": False,
        "errors": [],
    }

    start_time = time.perf_counter()
    first_chunk_time = None
    accumulated_content = []
    chunk_objects = []

    try:
        with httpx.Client(timeout=30.0) as client:
            with client.stream("POST", TARGET_URL, json=payload, headers=headers) as resp:
                results["http_status"] = resp.status_code
                content_type = resp.headers.get("content-type", "")
                results["content_type"] = content_type
                results["is_sse_content_type"] = "text/event-stream" in content_type

                if resp.status_code != 200:
                    results["errors"].append(f"HTTP {resp.status_code}: {resp.read().decode('utf-8', errors='replace')[:200]}")
                    results["total_duration_ms"] = (time.perf_counter() - start_time) * 1000
                    return results

                # Stream and parse SSE lines
                for line in resp.iter_lines():
                    if line is None:
                        continue
                    line_str = line.strip()
                    if not line_str:
                        continue

                    if first_chunk_time is None:
                        first_chunk_time = time.perf_counter()
                        results["ttft_ms"] = (first_chunk_time - start_time) * 1000

                    results["raw_event_count"] += 1

                    if not line_str.startswith("data:"):
                        results["errors"].append(f"Unexpected non-data SSE line: {line_str[:50]}")
                        continue

                    data_payload = line_str[5:].strip()

                    # Check for standard [DONE] termination marker
                    if data_payload == "[DONE]":
                        results["saw_done_marker"] = True
                        break

                    # Validate JSON chunk
                    try:
                        chunk = json.loads(data_payload)
                        chunk_objects.append(chunk)
                        results["parsed_chunk_count"] += 1

                        # Validate OpenAI chunk schema
                        if chunk.get("object") != "chat.completion.chunk":
                            results["all_chunks_match_schema"] = False

                        choices = chunk.get("choices", [])
                        if choices and isinstance(choices, list):
                            delta = choices[0].get("delta", {})
                            content_delta = delta.get("content")
                            if content_delta:
                                accumulated_content.append(content_delta)
                    except json.JSONDecodeError as jde:
                        results["all_chunks_valid_json"] = False
                        results["errors"].append(f"Invalid JSON in chunk: {str(jde)}")

        results["total_duration_ms"] = (time.perf_counter() - start_time) * 1000
        results["reconstructed_content"] = "".join(accumulated_content).strip()

    except Exception as exc:
        results["total_duration_ms"] = (time.perf_counter() - start_time) * 1000
        results["errors"].append(f"Exception during streaming: {type(exc).__name__}: {str(exc)}")
        return results

    # Verify request traversed public ngrok URL via ngrok local inspection API
    try:
        with httpx.Client(timeout=3.0) as local_client:
            ngrok_resp = local_client.get("http://127.0.0.1:4040/api/requests/http?limit=1")
        if ngrok_resp.status_code == 200:
            reqs = ngrok_resp.json().get("requests", [])
            if reqs:
                last_req = reqs[0]
                req_path = last_req.get("request", {}).get("uri", "")
                status_code = last_req.get("response", {}).get("status_code")
                if "/v1/chat/completions" in req_path and status_code == 200:
                    results["passed_through_ngrok"] = True
    except Exception:
        pass

    return results


def main():
    print("=== EXECUTING SAFE AUTHENTICATED SSE STREAMING TEST ===")
    res = run_streaming_test()

    print(f"Target URL: {res['target_url']}")
    print(f"HTTP Status: {res['http_status']}")
    print(f"Content-Type: {res['content_type']}")
    print(f"Is 'text/event-stream': {res['is_sse_content_type']}")
    print(f"Time to First Token/Chunk (TTFT): {res['ttft_ms']:.1f}ms" if res['ttft_ms'] else "TTFT: None")
    print(f"Total Stream Duration: {res['total_duration_ms']:.1f}ms" if res['total_duration_ms'] else "Total Duration: None")
    print(f"Raw SSE Lines Received: {res['raw_event_count']}")
    print(f"Parsed JSON Chunks: {res['parsed_chunk_count']}")
    print(f"All Chunks Valid JSON: {res['all_chunks_valid_json']}")
    print(f"All Chunks Match OpenAI Chunk Schema: {res['all_chunks_match_schema']}")
    print(f"Saw '[DONE]' Termination Marker: {res['saw_done_marker']}")
    print(f"Reconstructed Assistant Content: {repr(res['reconstructed_content'])}")
    print(f"Verified Request Traversed Public Ngrok URL: {res['passed_through_ngrok']}")

    if res['errors']:
        print(f"Errors Encountered: {res['errors']}")

    # Final Classification
    is_pass = (
        res["http_status"] == 200
        and res["is_sse_content_type"]
        and res["all_chunks_valid_json"]
        and res["all_chunks_match_schema"]
        and res["saw_done_marker"]
        and bool(res["reconstructed_content"])
        and res["passed_through_ngrok"]
        and not res["errors"]
    )

    if is_pass:
        print("\nCLASSIFICATION: PASS")
    else:
        print("\nCLASSIFICATION: FAIL")


if __name__ == "__main__":
    main()
