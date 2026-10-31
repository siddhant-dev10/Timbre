# Timbre: AI-Powered Civic Assistance Platform

Timbre is an AI-powered civic assistance platform designed to help Indian citizens discover government welfare schemes, understand statutory eligibility, identify required documents, and navigate application procedures in natural **Hindi**, **Hinglish**, and **English**.

> 📖 **Comprehensive Project Vision & Voice Calling Roadmap:** For an in-depth breakdown of the civic challenges faced by 1.4 billion Indian citizens, Timbre's multi-lingual RAG solutions, the future inbound & outbound voice call agent architecture, supported statutory schemes, and project acknowledgements, see [**`TIMBRE.md`**](TIMBRE.md).

For the current MVP, **WhatsApp text messaging** is the primary interface. Citizens can text questions (e.g. *"Main 18 saal ka ho gaya hoon. Mujhe kaun se government documents banwane chahiye?"*), and Timbre responds naturally, asks interactive clarifying questions, cites verified government portals, and provides step-by-step guidance.

The long-term vision includes **AI-powered inbound voice calling** for citizens who face smartphone or literacy barriers. All voice and telephony components are preserved as a future feature with strict safety locks (`ENABLE_REAL_CALLS=false`).

---

## 1. System Architecture

```
                       [ Indian Citizen / WhatsApp User ]
                                       │
                                       │ (Text message in Hindi / Hinglish / English)
                                       ▼
             [ WhatsApp Business Cloud API (Meta) OR OpenWA Gateway ]
                                       │
                                       │ POST /api/webhooks/whatsapp
                                       ▼
         ┌───────────────────────────────────────────────────────────┐
         │              Timbre WhatsApp Ingress & Router             │
         │                                                           │
         │ • Webhook Ingestion (OpenWA events & Meta Cloud API)      │
         │ • Cryptographic Signature Check (HMAC-SHA256)             │
         │ • Message Deduplication (wamid cache & database index)     │
         │ • Outgoing & Group & Status Echo Filtering                │
         │ • Sender Isolation & Session Management (wa_id in SQLite) │
         │ • Phone Number Privacy Masking (***3210)                  │
         └─────────────────────────────┬─────────────────────────────┘
                                       │
         ┌─────────────────────────────┴─────────────────────────────┐
         ▼                                                           ▼
┌─────────────────────────────────┐         ┌─────────────────────────────────┐
│   Multilingual FastEmbed RAG    │         │  Deterministic Rules & Schemes  │
│                                 │         │                                 │
│ • FastEmbed ONNX 384-D vectors  │         │ • Milestone age logic (18, 60)  │
│ • Multilingual MiniLM-L12       │         │ • 10+ Statutory Scheme Catalogues│
│ • Cross-script query expansion  │         │ • Strict preliminary disclaimers│
│ • Citations & official sources  │         │ • Grounded document criteria    │
└─────────────────────────────────┘         └─────────────────────────────────┘
         │                                                           │
         └─────────────────────────────┬─────────────────────────────┘
                                       │
                                       ▼
         ┌───────────────────────────────────────────────────────────┐
         │                 Timbre Conversational AI Brain            │
         │                                                           │
         │ • Language Matching (Hindi Devanagari, Hinglish, English) │
         │ • Context Continuity across multi-turn messages           │
         │ • Interactive Guidance: asks clarifying missing questions │
         │ • AI Identity Disclosure (never impersonates officials)   │
         │ • NVIDIA Nemotron 120B (with deterministic fallback)      │
         │ • Privacy Guard (rejects Aadhaar / OTP collection)        │
         └─────────────────────────────┬─────────────────────────────┘
                                       │
                                       │ Outbound delivery via active provider
                                       ▼
             [ OpenWA send-text API OR Meta WhatsApp Cloud API ]
                                       │
                                       ▼
                       [ Citizen Receives Reply on WhatsApp ]
```

---

## 2. Key MVP Features

- **OpenWA Gateway & WhatsApp Cloud API Support:** Multi-provider architecture supporting both the local **OpenWA WhatsApp Gateway** (session-based REST API) and Meta's official WhatsApp Business Cloud API.
- **Provider Abstraction (`BaseMessagingProvider`):** Complete decoupling of civic conversation logic from the messaging transport.
  - `OpenWAProvider`: Dispatches outbound messages via `POST /api/sessions/{sessionId}/messages/send-text` with automated session name-to-UUID resolution and HMAC-SHA256 signature verification (`X-OpenWA-Signature`).
  - `WhatsAppCloudProvider`: Meta Graph API v21.0 integration with verification handshake (`hub.challenge`) and signature verification (`X-Hub-Signature-256`).
  - `MockWhatsAppProvider`: In-memory simulation and testing provider for instant offline testing and demonstration without credentials.
- **Contextual Multi-Turn Dialogue:** Preserves conversational memory per citizen sender (`wa_id`) in SQLite. Avoids repetitive greetings in ongoing conversations.
- **Interactive Clarifying Questions:** When a citizen asks about a milestone (such as turning 18), Timbre outlines core identity documents (Voter ID Form 6, PAN Card Form 49A, Learner's Licence) and asks 1–2 clarifying questions (e.g. state of residence, existing age/address proofs) rather than overwhelming them.
- **Trilingual Language Adaptation:** Understands and replies in the citizen's chosen language:
  - **Devanagari Hindi:** Polished, respectful Hindi in Devanagari script.
  - **Hinglish:** Natural conversational Romanized Hindi.
  - **English:** Clear, polite Indian English.
- **Strict Privacy Invariants:** Phone numbers are masked (`***3210`) in logs and database views. Rejects and warns against sharing Aadhaar numbers, OTPs, or passwords.
- **Deterministic 384-D Multilingual RAG:** FastEmbed ONNX multilingual embeddings cross-referenced against official statutory schemes (Voter ID, PAN Card, Driving Licence, PM-KISAN, Ayushman Bharat, Old Age Pension, NSP Scholarship, Sukanya Samriddhi, E-Shram, UDID Disability).
- **Zero-Dependency Local Simulator:** Full conversational walkthrough and interactive CLI without requiring an active WhatsApp Business account.
- **Preserved Future Voice Capability:** Bolna telephony bridge, faster-whisper ASR, ElevenLabs TTS, and inbound call routing remain intact for future voice expansion. `ENABLE_REAL_CALLS=false` is strictly enforced.

---

## 3. Quickstart & Local Execution

### Prerequisites
- macOS (Apple Silicon recommended)
- Python 3.9+ with virtual environment
- NVIDIA API Key in `backend/.env` (optional; grounded fallback operates offline)

### Start FastAPI Backend
```bash
cd backend
source .venv/bin/activate
PYTHONPATH=. uvicorn app.main:app --host 127.0.0.1 --port 8000
```
- Health Check: `http://127.0.0.1:8000/health`
- WhatsApp Readiness Audit: `http://127.0.0.1:8000/api/whatsapp/readiness`
- Interactive API Documentation: `http://127.0.0.1:8000/docs`

---

## 4. Testing Conversation Without WhatsApp (Simulation Mode)

You do not need a Meta developer account or WhatsApp Business credentials to test or demo the conversation.

### Option A: Interactive Terminal Chat
Run the interactive terminal chat tool to converse with Timbre as a citizen:
```bash
PYTHONPATH=backend backend/.venv/bin/python3 backend/app/scripts/demo_whatsapp.py --interactive
```
Type your inquiries in Hindi, Hinglish, or English. Type `exit` to quit.

### Option B: Automated Walkthrough Script
Run the automated 5-turn civic walkthrough:
```bash
PYTHONPATH=backend backend/.venv/bin/python3 backend/app/scripts/demo_whatsapp.py
```
This tests:
1. Adulthood milestone inquiry in Hinglish (*"Main 18 saal ka ho gaya hoon..."*).
2. Follow-up state and document proof (*"Main Rajasthan se hoon..."*).
3. Statutory scheme inquiry in Devanagari Hindi (*"वृद्धावस्था पेंशन योजना..."*).
4. English query (*"What is the statutory fee and application process for PM-Kisan?"*).
5. User conclusion / stop intent (*"Theek hai, shukriya! Alvida."*).

### Option C: Via REST API
Send messages via curl to the simulation endpoint:
```bash
curl -X POST http://127.0.0.1:8000/api/whatsapp/simulate \
  -H "Content-Type: application/json" \
  -d '{
    "sender_phone": "919876543210",
    "sender_name": "Rohan",
    "message": "Main 18 saal ka ho gaya hoon. Mujhe kaun se government documents banwane chahiye?",
    "reset_conversation": true
  }'
```

---

## 5. Live WhatsApp Integration (OpenWA Gateway & Cloud API)

### Mode A: OpenWA Local Gateway (Recommended for Local Dev)

The local OpenWA instance runs on `http://localhost:2785` and manages linked WhatsApp Web sessions.

1. **Verify OpenWA Dashboard & Session:**
   - OpenWA Dashboard: `http://localhost:2785`
   - Active Session: `timbre`
   - Ensure the session is linked to your WhatsApp handset (scan QR code in dashboard if status is `qr_ready`).
2. **Configure `backend/.env`:**
   ```env
   OPENWA_BASE_URL=http://localhost:2785
   OPENWA_API_KEY=your_api_key_here
   OPENWA_SESSION_ID=timbre
   OPENWA_WEBHOOK_SECRET=
   OPENWA_TIMEOUT_SECONDS=15.0
   ```
   *(Note: If `OPENWA_API_KEY` is omitted, Timbre automatically searches `/Users/sidh._./OpenWA/data/.api-key` for local development).*
3. **Expose Local Webhook (ngrok):**
   ```bash
   ngrok http 8000
   ```
4. **Configure Webhook in OpenWA:**
   - In OpenWA dashboard, add or edit the webhook for session `timbre`:
     - **URL**: `https://<YOUR-NGROK-DOMAIN>/api/webhooks/whatsapp`
     - **Events**: `["message.received"]`
5. **Verify Readiness:**
   ```bash
   curl -s http://127.0.0.1:8000/api/whatsapp/readiness
   ```
   Should return `"status": "ready"`, `"provider_mode": "openwa"`.

---

### Mode B: Meta WhatsApp Business Cloud API

To connect Timbre directly to the official Meta Cloud API:

1. **Create a Meta Developer Account & App:**
   - Go to [developers.facebook.com](https://developers.facebook.com) and create a **Business** App.
   - Add the **WhatsApp** product to your app.
2. **Obtain API Credentials:**
   - In WhatsApp > API Setup, locate:
     - **Access Token** (`WHATSAPP_ACCESS_TOKEN`)
     - **Phone number ID** (`WHATSAPP_PHONE_NUMBER_ID`)
     - **App Secret** in App Settings > Basic (`WHATSAPP_APP_SECRET`)
3. **Configure `backend/.env`:**
   ```env
   WHATSAPP_API_BASE_URL=https://graph.facebook.com/v21.0
   WHATSAPP_ACCESS_TOKEN=your_meta_system_user_access_token
   WHATSAPP_PHONE_NUMBER_ID=your_phone_number_id
   WHATSAPP_VERIFY_TOKEN=your_custom_secret_verify_token
   WHATSAPP_APP_SECRET=your_app_secret
   ```
4. **Configure Webhook in Meta Developer Portal:**
   - In WhatsApp > Configuration > Callback URL:
     - **Callback URL**: `https://<YOUR-NGROK-DOMAIN>/api/webhooks/whatsapp`
     - **Verify Token**: The same value you set in `WHATSAPP_VERIFY_TOKEN`.
   - Click **Verify and Save**.
   - Under Webhook Fields, subscribe to **`messages`**.

---

## 6. Automated Quality Assurance

The test suite comprises **228 automated tests** (100% green across all suites):

```bash
# Run all backend unit and integration tests
PYTHONPATH=backend backend/.venv/bin/pytest backend/

# Run OpenWA-specific tests
PYTHONPATH=backend backend/.venv/bin/pytest backend/tests/test_openwa.py -v

# Run WhatsApp Cloud API tests
PYTHONPATH=backend backend/.venv/bin/pytest backend/tests/test_whatsapp.py -v
```

### Test Coverage Highlights:
- OpenWA Webhook test probe (`test`) and `message.received` event ingestion.
- OpenWA HMAC-SHA256 signature verification (`X-OpenWA-Signature`).
- OpenWA outbound send via `POST /api/sessions/{sessionId}/messages/send-text`.
- Session name (`timbre`) to UUID dynamic resolution.
- Filtering of outgoing echoes (`fromMe: true`), status broadcasts, and groups.
- Meta Webhook subscription verification handshake (`hub.challenge`).
- Meta cryptographic signature verification (`X-Hub-Signature-256`).
- Deduplication of incoming `wamid` / message IDs.
- Status receipt handling (`sent`, `delivered`, `read`).
- Sender conversation isolation (different `wa_id`s never mix context).
- Multi-turn context continuity and non-repetitive greetings.
- 18th birthday adulthood document discovery and interactive clarifying questions.
- Trilingual adaptation (Devanagari Hindi, Hinglish, English).
- Refusal of sensitive credentials (Aadhaar, OTP, passwords).
- Provider failure handling (graceful capture of OpenWA HTTP 409 client-not-ready).
- Strict enforcement of `ENABLE_REAL_CALLS=false`.

---

## 7. Current Limitations & Future Voice Vision

- **Media Types:** The current MVP processes text messages. Audio/image attachments prompt the user to send text inquiries.
- **Live Calls Disabled:** Outbound and inbound real phone calling remain strictly disabled in configuration (`ENABLE_REAL_CALLS=false`, `BOLNA_TEST_AGENT_VERIFIED=false`). Voice telephony infrastructure (Bolna, Faster-Whisper, ElevenLabs) is preserved for future voice releases.
- **Preliminary Guidance Disclaimer:** Timbre provides preliminary statutory guidance based on verified official government sources. Final applications are submitted on official government portals.
