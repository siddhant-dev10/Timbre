# Bolna Telephony & Custom LLM Integration Guide for Timbre

This guide documents the end-to-end integration between **Bolna.ai** cloud telephony and **Timbre's** Mac-local grounded AI brain.

---

## 1. System Architecture

```
                   [ PSTN Telephone Network (Caller / Recipient) ]
                                         │
                                         ▼ (SIP / WebRTC Audio)
                            [ Bolna Telephony Gateway ]
                                         │
               ┌─────────────────────────┴─────────────────────────┐
               ▼ (Speech-to-Text)                                  ▲ (Text-to-Speech)
      [ Streaming ASR ]                                   [ ElevenLabs TTS ]
    (Deepgram / Whisper / Sarvam)                       (Voice: Timbre / Hindi)
               │                                                   │
               ▼ (Transcribed Hindi/English text)                  │ (Audio chunks)
   ┌───────────────────────────────────────────────────────────────┴────────────────┐
   │                           Secure Public Tunnel                                 │
   │               (ngrok / Cloudflare Tunnel -> localhost:8000)                    │
   └───────────────────────────────────────┬────────────────────────────────────────┘
                                           │
                                           ▼ (OpenAI-compatible Chat Completions)
   ┌────────────────────────────────────────────────────────────────────────────────┐
   │                       Timbre FastAPI Backend (Mac-Local)                       │
   │                                                                                │
   │  1. Ingress Auth: Validates Bearer token / X-Timbre-Webhook-Secret             │
   │  2. Stop Intent: Checks for "ruko", "phone kato", "stop", "nahi chahiye"       │
   │  3. RAG Retrieval: FastEmbed ONNX 384-D dense search over statutory catalogue  │
   │  4. Master Prompt: Enforces brevity (2-3 sentences), Hindi Devanagari, ground  │
   │  5. Reasoning: NVIDIA Nemotron 120B generates grounded civic response          │
   │  6. Streaming Egress: Server-Sent Events (SSE) token chunks -> Bolna           │
   │  7. Webhook Handler: Authenticated post-call duration & status tracking        │
   └────────────────────────────────────────────────────────────────────────────────┘
```

---

## 2. Secure Local Environment Configuration (`backend/.env`)

Configure the following variables in `backend/.env` on your Mac.

> [!IMPORTANT]
> Never commit `backend/.env` to Git and never share API keys in chat or public repositories.
> Generate a strong random webhook secret using: `python3 -c "import secrets; print(secrets.token_hex(24))"`

| Variable | Description | Initial Value for Demo Prep |
| :--- | :--- | :---: |
| `BOLNA_API_KEY` | Your Bolna account API key from dashboard | *(Enter your Bolna API key locally)* |
| `BOLNA_AGENT_ID` | The Agent ID generated after creating the agent in Bolna | *(Copy from Bolna Agent URL/Settings)* |
| `BOLNA_WEBHOOK_SECRET` | A secure random secret shared between Timbre and Bolna | *(Generate with `secrets.token_hex(24)`)* |
| `BOLNA_TEST_AGENT_VERIFIED` | Local attestation that you reviewed the agent config | `false` *(Set `true` only after review)* |
| `ENABLE_REAL_CALLS` | Master hard safety invariant gating live telephony | `false` *(Keep `false` during testing)* |

---

## 3. Public HTTPS Tunnel Setup (Local Development)

Because Bolna cloud servers cannot reach `http://localhost:8000`, a secure HTTPS tunnel is required when conducting live phone calls or receiving live webhooks.

### Option A: Using ngrok (Recommended)
```bash
# In a separate terminal on your Mac:
ngrok http 8000
```
Note the HTTPS forwarding URL (e.g. `https://abcd-12-34-56-78.ngrok-free.app`).

### Option B: Using Cloudflare Tunnel
```bash
cloudflared tunnel --url http://localhost:8000
```

> [!NOTE]
> Only `/v1/chat/completions`, `/v1/models`, and `/api/webhooks/bolna` need to be reached by Bolna.
> Timbre authenticates requests using your configured `BOLNA_WEBHOOK_SECRET`.

---

## 4. Bolna Dashboard Configuration Checklist

Follow these exact steps in the [Bolna Dashboard](https://www.bolna.ai/dashboard):

### Step 1: Create a New Agent
1. Navigate to **Agents** $\rightarrow$ **Create New Agent**.
2. **Agent Name:** `Timbre - Indian Civic Voice Assistant`
3. **Agent Description:** `AI voice agent providing grounded guidance on Indian statutory welfare schemes.`

### Step 2: Configure Speech Recognition (Transcriber)
- **Provider:** Deepgram or Whisper
- **Model:** Nova-2 or Whisper Multilingual
- **Language:** Hindi (`hi`) or Bilingual Hindi/English
- **Voice Activity Detection (VAD):** Enable interruption / barge-in.
- **Endpointing:** `300ms` (balances natural pauses with fast turn-taking).

### Step 3: Configure Speech Synthesis (Voice / TTS)
- **Provider:** ElevenLabs
- **Model:** `eleven_turbo_v2_5` or `eleven_multilingual_v2`
- **Voice:** Select your custom **Timbre** voice ID (or a natural Indian Hindi voice like `Aarav` / `Aditi`).
- **Temperature / Stability:** `0.5`
- **Similarity Boost:** `0.75`

### Step 4: Configure the Brain (Custom LLM Connection)
1. In the Agent editor, go to **LLM Configuration**.
2. Select **Provider:** **Custom LLM** (or **Other OpenAI-Compatible**).
3. **Base URL:** `https://<YOUR-TUNNEL-URL>/v1`
4. **Model Name:** `timbre-voice-agent`
5. **API Key:** Paste your `BOLNA_WEBHOOK_SECRET` from `backend/.env`.
6. **Streaming:** **Enabled (True)** *(Timbre supports Server-Sent Events streaming)*.
7. **Temperature:** `0.2` (enforces grounded, deterministic responses).

### Step 5: Configure Greeting & System Prompt in Bolna
**Welcome Message (First 5 seconds mandatory disclosure):**
```
नमस्ते, मैं टिम्ब्र हूँ, एक AI सहायक। मैं भारतीय सरकारी योजनाओं और नागरिक सेवाओं की जानकारी में आपकी सहायता कर सकता हूँ। आप किस योजना के बारे में जानना चाहते हैं?
```

**System Prompt (Fallback & Guardrails):**
```
You are Timbre, a conversational AI voice assistant for Indian civic and welfare services.
1. Always introduce yourself as an AI assistant. You are NOT an official government officer.
2. Reply in concise spoken Hindi (2-3 sentences max).
3. Base all claims on the grounded context provided by the custom LLM. Never invent fees or deadlines.
4. If the caller says "ruko", "phone kato", "stop", or "nahi chahiye", politely end the conversation.
5. NEVER ask for or record Aadhaar numbers, OTPs, PINs, or bank passwords.
```

### Step 6: Configure Webhooks & Telephony Safety
1. Go to **Settings** $\rightarrow$ **Webhook Configuration**:
   - **Webhook URL:** `https://<YOUR-TUNNEL-URL>/api/webhooks/bolna?token=<YOUR_BOLNA_WEBHOOK_SECRET>`
   - **Custom Headers:**
     - Key: `X-Timbre-Webhook-Secret`
     - Value: `<YOUR_BOLNA_WEBHOOK_SECRET>`
2. Go to **Call Settings**:
   - **Max Duration:** `180` seconds (3 minutes max).
   - **Automatic Retries:** **Disabled (0 retries)**.
   - **Silence Timeout:** `30` seconds.

---

## 5. Demonstration Options for Tomorrow's Demo

### Option 1: Controlled Local Rehearsal Demo (100% Zero-Risk, Recommended)
**Why choose this:** It runs completely locally on your Mac, incurs **zero phone billing**, requires **no public tunnels**, and demonstrates full multi-turn conversational AI with masked telephone privacy.

1. Keep backend running on `http://127.0.0.1:8000`.
2. Open Timbre UI $\rightarrow$ **Calls Screen** $\rightarrow$ **Local Dry-Run Rehearsal**.
3. Select a synthetic citizen profile (e.g. `CIT-0001` Aarav Sharma).
4. Enter test recipient number `+919876543210` and confirm consent.
5. Click **Run Controlled Rehearsal**.
6. The system executes the complete conversation, displaying stage latencies, statutory disclaimers, and grounded advice.

### Option 2: Live Phone Call Demonstration (PSTN Telephony)
**Prerequisites Checklist:**
- [ ] Recipient has provided explicit affirmative consent to receive one demonstration call.
- [ ] Recipient phone number verified in E.164 format (e.g. `+919876543210`).
- [ ] Active public tunnel running (`ngrok http 8000`).
- [ ] Bolna Agent ID configured in `backend/.env` (`BOLNA_AGENT_ID=...`).
- [ ] `BOLNA_API_KEY` and `BOLNA_WEBHOOK_SECRET` configured in `backend/.env`.
- [ ] Agent reviewed for AI disclosure and 0 retries: set `BOLNA_TEST_AGENT_VERIFIED=true` in `backend/.env`.
- [ ] Flip `ENABLE_REAL_CALLS=true` in `backend/.env`.
- [ ] In Timbre UI, select **Approved Live Test**, review opening script, type confirmation phrase `CALL ONCE`, and dispatch.

---

## 6. Verification & Health Commands

```bash
# 1. Verify backend health and zero-cost live provider authentication
curl -s "http://127.0.0.1:8000/health?check_connectivity=true"

# 2. Inspect copy-paste Bolna configuration spec
curl -s "http://127.0.0.1:8000/v1/integration-spec?public_url=https://YOUR-TUNNEL.ngrok-free.app"

# 3. Test OpenAI chat completion endpoint (JSON mode)
curl -s -X POST http://127.0.0.1:8000/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{"messages":[{"role":"user","content":"Ayushman card ke baare mein batayein"}]}'

# 4. Test OpenAI chat completion endpoint (SSE streaming mode)
curl -s -N -X POST http://127.0.0.1:8000/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{"messages":[{"role":"user","content":"Voter ID online apply kaise karein?"}],"stream":true}'

# 5. Run automated test suite (167 passing tests)
PYTHONPATH=backend backend/.venv/bin/pytest backend/ -q
```
