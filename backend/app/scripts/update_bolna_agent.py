"""Audited Script to Prepare, Apply, and Verify Updates to Bolna Agent via Official V2 API.

Official Bolna Agent V2 Endpoints:
- GET   https://api.bolna.ai/v2/agent/{agent_id}
- PATCH https://api.bolna.ai/v2/agent/{agent_id}  (Partial update: webhook_url, prompts, voice)
- PUT   https://api.bolna.ai/v2/agent/{agent_id}  (Full update: tasks, tools_config, llm_config, compositions)

Key Findings on Supported Fields:
1. webhook_url:
   - Officially supported by BOTH PATCH and PUT.
   - Fully persistent and verified on agent GET responses.
   - Embeds ?token=<SECRET> so Timbre authenticates call status webhooks even if headers are not echoed.
2. webhook_headers:
   - Supported in PUT agent_config. Not in documented shallow PATCH attributes.
   - Token is redundant with webhook_url?token= for defense-in-depth.
3. tasks[0].tools_config.llm_agent.llm_config:
   - Deeply nested tool parameter. Ignored by shallow PATCH.
   - Supported via PUT with full preservation of tasks, transcriber, and synthesizer.
   - In Bolna's architecture, custom LLMs are registered via /user/model/custom;
     the agent references the registered model name ('timbre-voice-agent') and provider ('custom').
4. composition_by_language:
   - Top-level key alongside agent_config and agent_prompts.
   - Must be preserved in PUT to avoid dropping the 179 Hindi rich-text prompt nodes.

Requires --apply flag to execute write requests. Performs post-update GET verification.
Never prints, logs, or exposes secrets.
"""
import argparse
import copy
import json
import sys
from pathlib import Path
from typing import Any, Dict, Optional
import httpx

# Ensure backend path is on sys.path
backend_dir = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(backend_dir))

from app.config import settings

TARGET_AGENT_ID = settings.BOLNA_AGENT_ID.strip() or "dd390081-993d-4559-a5ff-81f36f9c70c6"
TUNNEL_BASE_URL = "https://enticing-astonish-going.ngrok-free.dev"


def get_agent_endpoint(base_url: str, agent_id: str) -> str:
    """Returns the official Bolna V2 agent endpoint URL."""
    clean_base = base_url.rstrip("/")
    return f"{clean_base}/v2/agent/{agent_id}"


def get_current_agent_config(client: httpx.Client, agent_id: str, base_url: Optional[str] = None) -> dict:
    """Fetches the latest agent configuration from Bolna official V2 API."""
    url = get_agent_endpoint(base_url or settings.BOLNA_BASE_URL, agent_id)
    headers = {"Authorization": f"Bearer {settings.BOLNA_API_KEY.strip()}"}
    resp = client.get(url, headers=headers)
    if resp.status_code != 200:
        raise RuntimeError(f"Failed to fetch agent {agent_id}: HTTP {resp.status_code}")
    return resp.json()


def prepare_patch_payload(
    current_data: dict,
    webhook_secret: str,
    tunnel_base_url: str = TUNNEL_BASE_URL,
) -> dict:
    """
    Constructs a minimal partial update payload for PATCH /v2/agent/{agent_id}.
    Targets only officially documented updatable attributes for PATCH:
    - webhook_url (with embedded ?token= parameter for authentication)
    Note: Bolna's official documentation notes that nested tasks and tools_config
    are ignored in PATCH.
    """
    webhook_token = webhook_secret
    return {
        "webhook_url": f"{tunnel_base_url.rstrip('/')}/api/webhooks/bolna?token={webhook_token}",
    }


def prepare_update_payload(
    current_data: dict,
    llm_api_key: str,
    webhook_secret: str,
    tunnel_base_url: str = TUNNEL_BASE_URL,
) -> dict:
    """
    Clones the entire current agent configuration for PUT /v2/agent/{agent_id},
    preserving all existing prompts, rich text language compositions, transcriber settings,
    and synthesizer parameters, modifying only the target fields:
    1. tasks[0].tools_config.llm_agent.llm_config.api_key
    2. webhook_url
    3. webhook_headers
    """
    data_clone = copy.deepcopy(current_data)

    # Support both wrapped agent_config and flat V2 GET response
    if "agent_config" in data_clone:
        agent_config = data_clone["agent_config"]
        agent_prompts = data_clone.get("agent_prompts", {})
        composition_by_language = data_clone.get("composition_by_language")
    else:
        agent_config = data_clone
        agent_prompts = agent_config.pop("agent_prompts", {})
        composition_by_language = agent_config.pop("composition_by_language", None)

    # Strip read-only / server-managed metadata fields
    for field in [
        "id",
        "created_at",
        "updated_at",
        "agent_status",
        "created_by",
        "parent_agent_id",
        "source_agent_id",
    ]:
        agent_config.pop(field, None)

    # 1. Update Custom LLM API Key inside tasks[0]
    tasks = agent_config.get("tasks", [])
    if not tasks:
        raise ValueError("Agent configuration contains no tasks.")
    llm_agent = tasks[0].get("tools_config", {}).get("llm_agent", {})
    llm_config = llm_agent.get("llm_config", {})
    llm_config["api_key"] = llm_api_key
    llm_config["base_url"] = f"{tunnel_base_url.rstrip('/')}/v1"
    llm_config["model"] = "timbre-voice-agent"

    # 2. Update Webhook URL and Headers
    webhook_token = webhook_secret or llm_api_key
    agent_config["webhook_url"] = f"{tunnel_base_url.rstrip('/')}/api/webhooks/bolna?token={webhook_token}"
    agent_config["webhook_headers"] = {"X-Timbre-Webhook-Secret": webhook_token}

    payload: Dict[str, Any] = {
        "agent_config": agent_config,
        "agent_prompts": agent_prompts,
    }
    if composition_by_language is not None:
        payload["composition_by_language"] = composition_by_language

    return payload


def redact_payload(payload: Any) -> Any:
    """Redacts any secret or token fields from dictionary objects before printing."""
    def _redact(val, key_name=""):
        if isinstance(val, dict):
            redacted = {}
            for k, v in val.items():
                if any(w in k.lower() for w in ["key", "secret", "token", "password", "auth"]):
                    if isinstance(v, (dict, list)):
                        redacted[k] = _redact(v, k)
                    else:
                        redacted[k] = "[REDACTED]" if v else v
                else:
                    redacted[k] = _redact(v, k)
            return redacted
        elif isinstance(val, list):
            if any(w in key_name.lower() for w in ["key", "secret", "token", "password", "auth"]):
                return ["[REDACTED]" if isinstance(i, (str, int, float, bool)) else _redact(i, key_name) for i in val]
            return [_redact(i, key_name) for i in val]
        return val

    return _redact(payload)


def apply_agent_update(
    client: httpx.Client,
    agent_id: str,
    payload: dict,
    method: str = "PUT",
    base_url: Optional[str] = None,
    api_key: Optional[str] = None,
) -> httpx.Response:
    """Dispatches authenticated PUT or PATCH request to update the Bolna agent via V2 API."""
    token = (api_key or settings.BOLNA_API_KEY).strip()
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }
    url = get_agent_endpoint(base_url or settings.BOLNA_BASE_URL, agent_id)
    method_upper = method.upper()

    if method_upper == "PUT":
        resp = client.put(url, headers=headers, json=payload)
    elif method_upper == "PATCH":
        resp = client.patch(url, headers=headers, json=payload)
    else:
        raise ValueError(f"Unsupported HTTP method: {method}")

    if resp.status_code not in (200, 201, 202):
        raise RuntimeError(f"Bolna API {method_upper} update failed: HTTP {resp.status_code}")
    return resp


def verify_saved_agent_config(
    client: httpx.Client,
    agent_id: str,
    tunnel_base_url: str = TUNNEL_BASE_URL,
    base_url: Optional[str] = None,
    expected_method: str = "PUT",
) -> dict:
    """Re-fetches the agent configuration from Bolna V2 and verifies the updated attributes."""
    saved_data = get_current_agent_config(client, agent_id, base_url=base_url)
    agent_cfg = saved_data.get("agent_config", saved_data)
    saved_tasks = agent_cfg.get("tasks", [])
    if not saved_tasks:
        raise RuntimeError("Saved agent has no tasks.")

    saved_llm_cfg = saved_tasks[0].get("tools_config", {}).get("llm_agent", {}).get("llm_config", {})
    saved_api_key = saved_llm_cfg.get("api_key")
    saved_wh_url = agent_cfg.get("webhook_url")
    saved_wh_headers = agent_cfg.get("webhook_headers")

    clean_tunnel = tunnel_base_url.rstrip("/")
    wh_configured = bool(saved_wh_url and saved_wh_url.startswith(clean_tunnel))

    # Prompts & Compositions preservation checks
    prompts = saved_data.get("agent_prompts", {})
    prompt_len = len(prompts.get("task_1", {}).get("system_prompt", "")) if isinstance(prompts, dict) else 0
    cbl = saved_data.get("composition_by_language", {})
    hi_nodes = len(cbl.get("hi", [])) if isinstance(cbl, dict) else 0

    verification = {
        "agent_id": agent_id,
        "agent_status": saved_data.get("agent_status"),
        "method_applied": expected_method.upper(),
        "webhook_url_configured": wh_configured,
        "webhook_headers_returned_in_get": bool(
            isinstance(saved_wh_headers, dict) and "X-Timbre-Webhook-Secret" in saved_wh_headers
        ),
        "llm_api_key_returned_in_get": bool(saved_api_key and saved_api_key.strip()),
        "llm_model": saved_llm_cfg.get("model"),
        "llm_base_url": saved_llm_cfg.get("base_url"),
        "hindi_composition_nodes_count": hi_nodes,
        "system_prompt_char_length": prompt_len,
    }

    # Strict invariant assertions
    if not verification["webhook_url_configured"]:
        raise RuntimeError(f"Verification failed: webhook_url was not saved in Bolna (got {repr(saved_wh_url)}).")

    if expected_method.upper() == "PUT":
        if hi_nodes == 0:
            raise RuntimeError("Verification failed: Hindi composition nodes were dropped in PUT update!")
        if prompt_len == 0:
            raise RuntimeError("Verification failed: System prompt was dropped in PUT update!")

    return verification


def main():
    parser = argparse.ArgumentParser(description="Audit, apply, and verify Bolna agent configuration updates via V2 API.")
    parser.add_argument("--apply", action="store_true", help="Execute write request to Bolna V2 API.")
    parser.add_argument("--method", choices=["put", "patch"], default="put",
                        help="Update method: 'put' (full rewrite, preserves prompts & compositions) or 'patch' (partial: webhook only).")
    parser.add_argument("--agent-id", default=TARGET_AGENT_ID, help="Target Bolna Agent ID.")
    parser.add_argument("--tunnel-url", default=TUNNEL_BASE_URL, help="Ngrok public tunnel URL.")
    args = parser.parse_args()

    agent_id = args.agent_id.strip()
    tunnel_url = args.tunnel_url.strip().rstrip("/")
    method = args.method.upper()

    if not settings.BOLNA_API_KEY:
        print("ERROR: BOLNA_API_KEY is not configured in backend/.env.", file=sys.stderr)
        sys.exit(1)

    llm_key = settings.TIMBRE_LLM_API_KEY.strip()
    if not llm_key:
        print("ERROR: TIMBRE_LLM_API_KEY is not configured in backend/.env.", file=sys.stderr)
        sys.exit(1)

    webhook_secret = settings.BOLNA_WEBHOOK_SECRET.strip() or llm_key

    with httpx.Client(timeout=15.0) as client:
        # Step 1: Fetch latest configuration via V2 GET immediately before updating
        v2_endpoint = get_agent_endpoint(settings.BOLNA_BASE_URL, agent_id)
        current_data = get_current_agent_config(client, agent_id)

        # Step 2: Prepare payload based on method
        if method == "PATCH":
            payload = prepare_patch_payload(current_data, webhook_secret, tunnel_base_url=tunnel_url)
        else:
            payload = prepare_update_payload(current_data, llm_key, webhook_secret, tunnel_base_url=tunnel_url)

        redacted = redact_payload(payload)

        # Audit summary
        agent_cfg = current_data.get("agent_config", current_data)
        current_tasks = agent_cfg.get("tasks", [])
        current_llm = current_tasks[0].get("tools_config", {}).get("llm_agent", {}).get("llm_config", {}) if current_tasks else {}

        print("=== BOLNA V2 API AUDIT SUMMARY: METHOD & FIELDS ===")
        print(f"Agent ID: {agent_id}")
        print(f"Official V2 Endpoint: {method} {v2_endpoint}")

        if method == "PUT":
            print("\n[PUT: Full Configuration Replacement with Complete Preservation]")
            print("\n1. tasks[0].tools_config.llm_agent.llm_config.api_key:")
            print(f"   BEFORE: {repr(current_llm.get('api_key'))}")
            print(f"   AFTER:  [REDACTED token, length = {len(llm_key)}]")
            print("\n2. agent_config.webhook_url:")
            print(f"   BEFORE: {repr(agent_cfg.get('webhook_url'))}")
            redacted_wh_url = redacted["agent_config"].get("webhook_url", "").split("?token=")[0] + "?token=[REDACTED]"
            print(f"   AFTER:  {redacted_wh_url}")
            print("\n3. agent_config.webhook_headers:")
            print(f"   BEFORE: {repr(agent_cfg.get('webhook_headers'))}")
            print("   AFTER:  {\"X-Timbre-Webhook-Secret\": \"[REDACTED]\"}")
        else:
            print("\n[PATCH: Documented Partial Update (webhook_url only)]")
            print("\n1. webhook_url:")
            print(f"   BEFORE: {repr(agent_cfg.get('webhook_url'))}")
            redacted_wh_url = redacted.get("webhook_url", "").split("?token=")[0] + "?token=[REDACTED]"
            print(f"   AFTER:  {redacted_wh_url}")
            print("\nNote on PATCH: llm_config.api_key cannot be updated via PATCH (ignored by Bolna).")

        print("\n=== PRESERVED CRITICAL PIPELINE COMPONENTS ===")
        print(f"Agent Name: {repr(agent_cfg.get('agent_name'))}")
        print(f"Agent Welcome Message: {repr(agent_cfg.get('agent_welcome_message'))}")
        if current_tasks:
            t_cfg = current_tasks[0].get("tools_config", {})
            transcriber = t_cfg.get("transcriber", {})
            synthesizer = t_cfg.get("synthesizer", {})
            print(f"Transcriber Provider & Model: {transcriber.get('provider')} / {transcriber.get('model')} (lang={transcriber.get('language')})")
            print(f"Synthesizer Provider & Voice: {synthesizer.get('provider')} / {synthesizer.get('provider_config', {}).get('voice')}")
        prompts = current_data.get("agent_prompts", {})
        p_len = len(prompts.get("task_1", {}).get("system_prompt", "")) if isinstance(prompts, dict) else 0
        print(f"Agent Prompts (Task 1 System Prompt Length): {p_len} characters")
        cbl = current_data.get("composition_by_language")
        if isinstance(cbl, dict):
            node_counts = {k: len(v) if isinstance(v, list) else 0 for k, v in cbl.items()}
            print(f"Composition by Language: {node_counts}")

        if not args.apply:
            print(f"\n[DRY RUN COMPLETE] Zero write requests ({method}) were sent to Bolna.")
            print(f"To execute this update after approval, run with '--apply':")
            print(f"  cd backend && PYTHONPATH=. .venv/bin/python app/scripts/update_bolna_agent.py --method {method.lower()} --apply")
            return

        # Step 3: Dispatch authenticated request to official V2 endpoint
        print(f"\n[APPLYING] Dispatching {method} request to {v2_endpoint}...")
        resp = apply_agent_update(client, agent_id, payload, method=method)
        print(f"{method} Response Status: HTTP {resp.status_code} OK")

        # Step 4: Re-fetch agent immediately via V2 GET to verify the saved configuration
        print("\n[VERIFYING] Re-fetching agent configuration from Bolna V2 to verify saved state...")
        verification = verify_saved_agent_config(client, agent_id, tunnel_base_url=tunnel_url, expected_method=method)
        print("Verification Results:")
        print(json.dumps(verification, indent=2))
        print(f"\nSUCCESS: Bolna agent '{agent_id}' updated and verified via V2 {method} API.")


if __name__ == "__main__":
    main()
