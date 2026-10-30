# Timbre Technical Architecture & Engineering Specifications

## 1. End-to-End System Architecture

Timbre provides an AI-powered civic assistance platform for Indian citizens with WhatsApp messaging as the primary MVP interface and Bolna/Faster-Whisper voice integration as a preserved future capability.

```
                           [ Indian Citizen / WhatsApp User ]
                                           │
                                           │ Text Message
                                           ▼
             [ Meta WhatsApp Cloud API v21.0  OR  OpenWA Local Gateway ]
                                           │
                                           │ HTTPS POST /api/webhooks/whatsapp
                                           │ Headers: X-Hub-Signature-256 / X-OpenWA-Signature
                                           ▼
                      ┌─────────────────────────────────────────┐
                      │      Timbre Webhook & Ingress Router    │
                      │                                         │
                      │ • Meta Handshake (hub.challenge)        │
                      │ • OpenWA Test Probe (event: test)       │
                      │ • Cryptographic HMAC-SHA256 Signature   │
                      │ • Replay Cache (message ID deduplication│
                      │ • Echo, Status Broadcast & Group Filter │
                      └────────────────────┬────────────────────┘
                                           │
                                           ▼
                      ┌─────────────────────────────────────────┐
                      │    Messaging Provider Abstraction       │
                      │                                         │
                      │ • BaseMessagingProvider (ABC)           │
                      │ • OpenWAProvider (Local REST Gateway)   │
                      │ • WhatsAppCloudProvider (Live Meta API) │
                      │ • MockWhatsAppProvider (Local Sandbox)  │
                      └────────────────────┬────────────────────┘
                                           │
                                           ▼
                      ┌─────────────────────────────────────────┐
                      │      Session & Persistence Layer        │
                      │                                         │
                      │ • WhatsAppConversation (Isolated wa_id) │
                      │ • WhatsAppMessage (Audit & Direction)   │
                      │ • Phone Number Privacy Masking (***3210)│
                      └────────────────────┬────────────────────┘
                                           │
                  ┌────────────────────────┴────────────────────────┐
                  ▼                                                 ▼
     ┌─────────────────────────┐                       ┌─────────────────────────┐
     │  Multilingual FastEmbed │                       │   Statutory Scheme DB   │
     │                         │                       │                         │
     │ • ONNX MiniLM-L12       │                       │ • 10+ Welfare Schemes   │
     │ • 384-D Dense Vectors   │                       │ • Milestone Age Rules   │
     │ • Hybrid Lexical Match  │                       │ • Official Portal URLs  │
     └────────────┬────────────┘                       └────────────┬────────────┘
                  │                                                 │
                  └────────────────────────┬────────────────────────┘
                                           │
                                           ▼
                      ┌─────────────────────────────────────────┐
                      │     WhatsAppCivicAgent (AI Brain)       │
                      │                                         │
                      │ • Language Detection (Hi / Hinglish / En│
                      │ • Clarifying Questions for Missing Data │
                      │ • NVIDIA Nemotron 120B Generative Turn  │
                      │ • Deterministic Grounded Fallback       │
                      │ • Non-Repetitive Greeting Enforcement   │
                      │ • Strict Statutory Disclaimers          │
                      │ • Aadhaar / OTP Privacy Rejection Guard │
                      └────────────────────┬────────────────────┘
                                           │
                                           ▼
                      ┌─────────────────────────────────────────┐
                      │       Outbound Message Dispatch         │
                      │                                         │
                      │ • POST /v21.0/{phone_number_id}/messages│
                      │ • Delivery Status Audit Log             │
                      └─────────────────────────────────────────┘
```

---

## 2. WhatsApp Integration & Webhook Architecture

Timbre supports dual messaging providers: the local **OpenWA WhatsApp Gateway** and the official **Meta WhatsApp Business Cloud API**.

### 2.1 OpenWA Gateway Protocol
OpenWA dispatches real-time events from local linked WhatsApp sessions:
- Route: `POST /api/webhooks/whatsapp`
- Headers:
  - `X-OpenWA-Event`: e.g. `message.received`, `test`
  - `X-OpenWA-Signature`: `sha256=<hex_digest>` (when secret configured)
  - `X-OpenWA-Idempotency-Key`: unique per delivery attempt
  - `X-OpenWA-Delivery-Id`: unique delivery UUID
- Payload:
  - `event`: string event identifier (`message.received`, `test`)
  - `sessionId`: session UUID (e.g. `ed741830-3751-45ae-81b1-41d6ad72d9dc`)
  - `data`: message data object (`id`, `chatId`, `from`, `body`, `fromMe`, `isGroup`, `isStatusBroadcast`)
- Outbound Delivery:
  - `POST {OPENWA_BASE_URL}/api/sessions/{sessionId}/messages/send-text`
  - Headers: `X-API-Key`, `Content-Type: application/json`, `Idempotency-Key`
  - Body: `{"chatId": "phone@c.us", "text": "..."}`
- Dynamic Session Resolution: If `OPENWA_SESSION_ID` is set to a friendly name (e.g. `timbre`), Timbre queries `GET /api/sessions` to map it to the active UUID automatically.
- Echo & Noise Filtering:
  - `fromMe == true` or `direction == "outgoing"`: ignored (`ignored_outgoing_message`)
  - `isStatusBroadcast == true` or `chatId == "status@broadcast"`: ignored (`ignored_status_broadcast`)
  - `isGroup == true` or `chatId.endswith("@g.us")`: ignored (`ignored_group_message`)
  - Empty text or non-text media without caption: ignored (`ignored_no_usable_text`)

### 2.2 Meta Cloud API Webhook Verification Handshake
Meta performs an initial GET request to establish callback validity:
- Route: `GET /api/webhooks/whatsapp`
- Query Parameters: `hub.mode=subscribe`, `hub.verify_token`, `hub.challenge`
- Verification: Constant-time comparison using `secrets.compare_digest(hub_verify_token, settings.WHATSAPP_VERIFY_TOKEN)`.
- Response: Returns `hub.challenge` with `Content-Type: text/plain` and HTTP 200.

### 2.3 Payload Cryptographic Signature Verification
Both providers support HMAC-SHA256 request signing:
- OpenWA: `X-OpenWA-Signature: sha256=<hex_digest>` using `OPENWA_WEBHOOK_SECRET`
- Meta: `X-Hub-Signature-256: sha256=<hex_digest>` using `WHATSAPP_APP_SECRET`
- Verification: Constant-time verification using `secrets.compare_digest(received_hash, expected_hash)`.

### 2.4 Deduplication & Idempotency
- Messaging gateways guarantee at-least-once delivery; network retries can deliver identical messages multiple times.
- Each incoming WhatsApp message has a unique message ID (`id` or `wamid`).
- Deduplication Architecture:
  1. **In-Memory Replay Cache:** Ring buffer of the last 1,000 processed IDs.
  2. **Database Unique Constraint:** `whatsapp_messages.wamid` has a unique indexed column.
  3. Duplicate submissions immediately return `{"status": "ok", "details": {"status": "duplicate_ignored"}}` with HTTP 200, preventing redundant LLM calls or duplicate replies.

### 2.5 Status Receipt Handling
- Status receipts (`sent`, `delivered`, `read`) are acknowledged immediately with HTTP 200 (`{"status": "status_acknowledged"}`) without triggering conversational turns.

---

## 3. Conversational AI Engine & Knowledge Retrieval

### 3.1 Language Detection & Script Matching
The agent classifies the incoming message into:
- **Devanagari Hindi:** Matches Unicode range `\u0900`–`\u097F`. The response is formulated in natural, respectful Hindi using Devanagari script.
- **Hinglish:** Romanized Hindi with grammatical markers (*"kaise"*, *"kya"*, *"banwana"*, *"saal"*, *"aavedan"*). The response is formulated in conversational Romanized Hinglish.
- **English:** Predominantly English civic terminology (*"what"*, *"how"*, *"apply"*, *"eligibility"*). The response is formulated in polite Indian English.

### 3.2 Milestone Guidance (Adulthood & Turning 18)
When a citizen mentions turning 18 or reaching adulthood:
1. Grounding context automatically loads:
   - **Voter ID (Form 6):** Election Commission of India (`voters.eci.gov.in`), ₹0 fee.
   - **PAN Card (Form 49A):** Protean / UTIITSL, ₹107 fee.
   - **Driving Learner's Licence:** MoRTH Parivahan Sarathi (`parivahan.gov.in`), ₹150 fee.
2. The agent outlines these core documents and asks 1–2 focused clarifying questions:
   - State of residence (to guide state portal vs central portal).
   - Existing identity proofs (e.g. 10th marksheet or birth certificate for DOB verification).

### 3.3 Context Continuity & Anti-Repetition
- Conversations are keyed strictly by sender `wa_id`.
- For `turn_index == 0`, Timbre introduces itself with its AI civic assistant disclosure.
- For `turn_index > 0`, the agent continues the discussion directly without re-introducing itself or repeating greetings.

### 3.4 Hybrid RAG & Scheme Index
- **Model:** `sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2` executed via `fastembed.TextEmbedding` (384-dimensional dense vectors).
- **Hybrid Scoring:**
  $$\text{Score} = 0.65 \times \text{Cosine Sim} + 0.35 \times \text{Lexical Overlap} + \text{Salient Heading Bonus}$$
- **Cross-lingual Synonyms:** Maps Roman and Devanagari synonyms for civic terms (e.g. "matdata" -> "voter", "licence" -> "parivahan", "kisan" -> "agriculture").

---

## 4. Database Schema & Conversation Management

SQLite schema additions for WhatsApp messaging:

### Table: `whatsapp_conversations`
| Column | Type | Constraints | Description |
|---|---|---|---|
| `id` | VARCHAR(64) | PRIMARY KEY | Unique conversation identifier (UUID) |
| `wa_id` | VARCHAR(32) | UNIQUE, INDEX | Citizen WhatsApp ID / phone digits |
| `phone_number_masked` | VARCHAR(32) | NOT NULL | Privacy-masked phone (`***3210`) |
| `contact_name` | VARCHAR(128) | NULLABLE | WhatsApp profile display name |
| `language_preference` | VARCHAR(32) | NOT NULL | Default `"Hinglish"` |
| `status` | VARCHAR(32) | NOT NULL | Default `"ACTIVE"` |
| `last_message_at` | DATETIME | DEFAULT utc_now | Timestamp of last message |
| `created_at` | DATETIME | DEFAULT utc_now | Session creation timestamp |
| `updated_at` | DATETIME | DEFAULT utc_now | Session update timestamp |

### Table: `whatsapp_messages`
| Column | Type | Constraints | Description |
|---|---|---|---|
| `id` | VARCHAR(64) | PRIMARY KEY | Unique message identifier (UUID) |
| `conversation_id` | VARCHAR(64) | FOREIGN KEY, INDEX | Reference to `whatsapp_conversations.id` |
| `wa_id` | VARCHAR(32) | INDEX | Citizen WhatsApp ID |
| `wamid` | VARCHAR(128) | UNIQUE, INDEX | Meta message ID (for deduplication) |
| `direction` | VARCHAR(16) | NOT NULL | `"inbound"` or `"outbound"` |
| `message_type` | VARCHAR(32) | NOT NULL | Default `"text"` |
| `content` | TEXT | NOT NULL | Message body text |
| `delivery_status` | VARCHAR(32) | NOT NULL | `"received"`, `"sent"`, `"failed"`, `"simulated"` |
| `meta_json` | TEXT | NOT NULL | Metadata (sources, language, error) |
| `created_at` | DATETIME | DEFAULT utc_now | Message creation timestamp |

---

## 5. Security, Privacy & Reliability

1. **Aadhaar / PII Shield:**
   - Timbre explicitly refuses to request, collect, or store sensitive numbers (Aadhaar, PAN, OTP, passwords, bank account numbers).
   - If a citizen volunteers an Aadhaar number or OTP, the safety filter intercepts the message and responds with a strict privacy notice advising them not to share credentials.
2. **Conversation Isolation:**
   - Senders cannot access or influence another user's conversation history.
   - History retrieval is scoped strictly to `conversation_id` and `wa_id`.
3. **Prompt Injection Defense:**
   - User text is wrapped as untrusted citizen dialogue and bounded by system instructions.
   - The agent rejects attempts to override statutory facts, grant false eligibility, or collect fees.
4. **Provider Fault Tolerance:**
   - Network errors, timeouts, or Meta API 5xx responses are caught and logged without exposing tokens or crashing the process. Outbound records are marked as `failed` with safe error codes.
5. **Masked Logging:**
   - Operational logs display only masked numbers (`***3210`). Full numbers are never logged in plaintext.

---

## 6. Environment Variables Reference

| Variable | Description | Default | Required for Live WhatsApp |
|---|---|---|---|
| `OPENWA_BASE_URL` | Local OpenWA Gateway REST API | `http://localhost:2785` | Yes (for OpenWA) |
| `OPENWA_API_KEY` | OpenWA master API key (auto-detected from data directory if omitted) | `""` | Yes (for OpenWA) |
| `OPENWA_SESSION_ID` | OpenWA session name or UUID | `timbre` | Yes (for OpenWA) |
| `OPENWA_WEBHOOK_SECRET` | HMAC-SHA256 signature secret for `X-OpenWA-Signature` | `""` | Optional |
| `OPENWA_TIMEOUT_SECONDS` | Outbound HTTP timeout for OpenWA REST calls | `15.0` | No |
| `WHATSAPP_API_BASE_URL` | Meta Graph API base endpoint | `https://graph.facebook.com/v21.0` | No |
| `WHATSAPP_ACCESS_TOKEN` | Meta System User / Temporary Access Token | `""` | Yes (for Cloud API) |
| `WHATSAPP_PHONE_NUMBER_ID` | WhatsApp Business Test / Production Phone Number ID | `""` | Yes (for Cloud API) |
| `WHATSAPP_VERIFY_TOKEN` | Secret string for Meta Webhook challenge | `""` | Yes (for Cloud API) |
| `WHATSAPP_APP_SECRET` | Meta App Secret for HMAC-SHA256 signature verification | `""` | Recommended |
| `WHATSAPP_TIMEOUT_SECONDS` | Outbound HTTP timeout for Meta API calls | `15.0` | No |
| `NVIDIA_API_KEY` | NVIDIA Build API Key for Nemotron 120B | `""` | Optional (fallback active) |
| `ENABLE_REAL_CALLS` | Hard safety invariant for real telephony | `false` | Must remain `false` |
| `BOLNA_TEST_AGENT_VERIFIED`| Telephony review flag | `false` | Must remain `false` |

---

## 7. Testing Strategy & Baseline

The test suite runs with zero external network dependencies:
- **WhatsApp & OpenWA Automated Tests (`test_openwa.py` + `test_whatsapp.py`):** 27 passing tests.
- **OpenWA Test Suite (`test_openwa.py`):**
  - Webhook HMAC-SHA256 signature verification (`X-OpenWA-Signature`).
  - OpenWA dashboard test event probe acknowledgement (`event: "test"`).
  - Inbound citizen message processing and outbound OpenWA reply delivery.
  - Outgoing bot message echo filtering (`fromMe: true`).
  - Status broadcast filtering (`isStatusBroadcast: true`).
  - Group message filtering (`@g.us`, `isGroup: true`).
  - Non-text and empty message filtering.
  - Message deduplication by message ID and delivery ID.
  - Safe error handling for disconnected clients (HTTP 409 `qr_ready`).
  - Dynamic session name-to-UUID resolution (`timbre` -> UUID).
  - Non-message lifecycle event handling (`session.status`).
  - Phone number normalization (`+91...`, `@s.whatsapp.net` -> `@c.us`).
  - Telephony safety locks (`ENABLE_REAL_CALLS=false`).
- **Meta WhatsApp Test Suite (`test_whatsapp.py`):**
  - Webhook verification challenge (`hub.mode=subscribe`).
  - HMAC-SHA256 signature verification (valid, invalid, missing).
  - Deduplication via `wamid`.
  - Delivery status receipt handling.
  - Context isolation between independent senders.
  - Multi-turn continuity and milestone discovery (18th birthday).
  - Trilingual language handling (Hindi, Hinglish, English).
  - Privacy guard (refusal of Aadhaar / OTP collection).
  - Provider failure and retry resilience.
  - Telephony safety locks (`ENABLE_REAL_CALLS=false`).
