# Timbre REST API Documentation

> **AI-Powered Indian Government Services Voice Assistant — Backend API Specification**

This document describes the REST API exposed by the Mac-local FastAPI development server for the Timbre Flutter desktop application.

---

## 1. Server & Connectivity

- **Localhost Base URL**: `http://127.0.0.1:8000` (or `http://localhost:8000`)
- **Supported API Prefixes**:
  - `/api` (Standard REST endpoints)
  - `/api/v1` (Flutter client versioned prefix)
- **Interactive Documentation**:
  - OpenAPI Swagger UI: `http://127.0.0.1:8000/docs`
  - ReDoc: `http://127.0.0.1:8000/redoc`

### CORS Policy
The backend permits requests from Flutter desktop development hosts (`http://localhost:*`, `http://127.0.0.1:*`). Allowed origins are configurable via `ALLOWED_ORIGINS` in `backend/.env`.

---

## 2. Authentication & Safety Headers

All endpoints operate in **Demo Mode** by default (`ENABLE_REAL_CALLS=false`).
- Public endpoints require no authentication token for prototype evaluation.
- Real telecom calls are strictly gated and disabled by default.

---

## 3. Endpoints

### 3.1 System Health
```http
GET /health
GET /api/v1/health
```
Returns system operational status, database connectivity, NVIDIA Nemotron AI status, Faster-Whisper ASR status, and ElevenLabs / Bolna configuration.

**Response `200 OK`**:
```json
{
  "status": "degraded",
  "version": "1.0.0",
  "mode": "demo",
  "database": {
    "status": "healthy",
    "details": "SQLite connected"
  },
  "ai_provider": {
    "status": "credentials_pending",
    "details": "Provider: NVIDIA Nemotron API, model: nvidia/nemotron-3.5-super-vl-120b-a12b; credentials/configuration only, provider connectivity not checked"
  },
  "bolna_voice": {
    "status": "demo_simulation",
    "details": "Configured: False, Real Calls Enabled: False"
  },
  "elevenlabs_tts": {
    "status": "credentials_pending",
    "details": "Provider: ElevenLabs, Custom Voice: Timbre, Configured: False, connectivity not checked, Model: eleven_multilingual_v2"
  },
  "real_calls_enabled": false,
  "bolna_test_call_ready": false
}
```

---

### 3.2 Citizen Management

#### List Fictional Citizens
```http
GET /api/citizens?limit=20&offset=0&q=Maharashtra
GET /api/v1/citizens
```
**Query Parameters**:
- `limit` (int, default `20`, max `100`): Page size.
- `offset` (int, default `0`): Pagination offset.
- `q` (string, optional): Case-insensitive search on citizen name, district, or state.
- `age` (int, optional): Exact age filter.

**Response `200 OK`**:
```json
{
  "total": 100,
  "limit": 20,
  "offset": 0,
  "citizens": [
    {
      "id": "CIT-0001",
      "first_name": "Aarav",
      "last_name": "Sharma",
      "name": "Aarav Sharma",
      "date_of_birth": "2008-11-15",
      "age": 17,
      "gender": "MALE",
      "state": "Uttar Pradesh",
      "district": "Varanasi",
      "city_or_village": "Kashi",
      "rural_or_urban": "URBAN",
      "preferred_language": "Hindi",
      "education": "Higher Secondary Student",
      "occupation": "High School Student",
      "employment_status": "Student",
      "synthetic_family_income": 140500,
      "simulated_income_bracket": "LOW",
      "family_size": 4,
      "marital_status": "Single",
      "children": 0,
      "is_student": true,
      "is_farmer": false,
      "is_senior_citizen": false,
      "simulated_life_event": "Approaching age 18",
      "potentially_relevant_services": ["SVC-VOTER-ID", "SVC-LEARNER-LICENCE", "SVC-PAN-CARD"],
      "eligibility_notes": "Turning 18 next month; eligible for advance ECI Form 6 voter enrollment.",
      "required_documents": ["Birth Certificate", "10th Marksheet", "Aadhaar Card", "Passport Photo"],
      "demo_only": true,
      "is_fictional": true,
      "phone_number": "DEMO-PHONE-0001",
      "email": "cit0001@example.com",
      "pincode": "221001"
    }
  ]
}
```

#### Get Single Citizen
```http
GET /api/citizens/{citizen_id}
GET /api/v1/citizens/{citizen_id}
```
**Response `200 OK`**: Single citizen JSON object.
**Response `404 Not Found`**: `{"detail": "Citizen record 'CIT-9999' not found."}`

#### Patch Citizen Date of Birth (Life-Event Trigger)
```http
PATCH /api/citizens/{citizen_id}
GET /api/v1/citizens/{citizen_id}
Content-Type: application/json

{
  "date_of_birth": "2008-10-20"
}
```
**Response `200 OK`**:
```json
{
  "citizen_id": "CIT-0001",
  "previous_age": 17,
  "calculated_age": 18,
  "event_detected": "MILESTONE_AGE_18",
  "citizen": { ... }
}
```

#### Evaluate Scheme Eligibility
```http
POST /api/citizens/{citizen_id}/evaluate
POST /api/v1/citizens/{citizen_id}/evaluate
```
**Response `200 OK`**:
```json
{
  "citizen_id": "CIT-0001",
  "calculated_age": 18,
  "eligible_services": [
    {
      "id": "SVC-VOTER-ID",
      "service_code": "ECI-VOTER-FORM6",
      "name": "Voter ID Card Registration (Form 6)",
      "category": "Civic Identity",
      "administering_body": "Election Commission of India (ECI)",
      "official_application_url": "https://voters.eci.gov.in/",
      "statutory_fee_inr": 0.0,
      "verification_status": "VERIFIED"
    }
  ],
  "detailed_results": [
    {
      "id": "elg-CIT-0001-ECI-VOTER-FORM6",
      "citizen_id": "CIT-0001",
      "is_eligible": true,
      "status": "POTENTIALLY_ELIGIBLE",
      "qualification_reason": "Applicant is 18 years old (meets statutory minimum age 18 threshold for general elector enrollment under Form 6).",
      "missing_documents": ["Proof of Age", "Proof of Ordinary Residence", "Recent Passport-size Photograph"],
      "disclaimer": "Preliminary guidance only. Statutory eligibility is determined solely by official Indian authorities upon original document verification."
    }
  ],
  "call_job_scheduled": false
}
```

---

### 3.3 Government Services Catalogue

#### List All Services
```http
GET /api/services
GET /api/v1/services
```
**Response `200 OK`**:
Array of statutory government service catalogue entries with official verified URLs (`voters.eci.gov.in`, `parivahan.gov.in`, `pmkisan.gov.in`, etc.).

#### Get Service Detail
```http
GET /api/services/{service_id}
GET /api/v1/services/{service_id}
```
`service_id` can be the catalogue ID (`SVC-VOTER-ID`) or official code (`ECI-VOTER-FORM6`).

---

### 3.4 Grounded Conversational AI (Chat)

```http
POST /api/chat
POST /api/v1/chat
Content-Type: application/json

{
  "citizen_id": "CIT-0001",
  "message": "Mujhe Voter ID card kaise apply karna hoga?",
  "conversation_id": "conv-1234",
  "language_preference": "Hinglish"
}
```

**Response `200 OK`**:
```json
{
  "conversation_id": "conv-1234",
  "citizen_id": "CIT-0001",
  "answer": "Namaste Aarav ji! Aap 18 saal ke ho chuke hain, isliye aap naye Voter ID card ke liye ECI Form 6 online bhar sakte hain. Iske liye voters.eci.gov.in portal par jayein. Zaroori documents: Aadhaar card ya 10th marksheet (age proof ke liye), electricity bill (address proof), aur ek passport photo. Aavedan bilkul free hai.",
  "language": "Hinglish",
  "grounded_services": [
    {
      "id": "SVC-VOTER-ID",
      "name": "Voter ID Card Registration (Form 6)",
      "official_application_url": "https://voters.eci.gov.in/"
    }
  ],
  "confidence_note": "Preliminary AI guidance based on verified official catalogue entries. Consult official portals for statutory application processing.",
  "llm_model": "qwen3.5:9b"
}
```

---

### 3.5 Life-Event Simulations

#### Trigger Simulation
```http
POST /api/simulations
POST /api/v1/simulations
Content-Type: application/json

{
  "citizen_id": "CIT-0001",
  "trigger_event": "MILESTONE_AGE_18"
}
```
**Response `200 OK`**:
```json
{
  "id": "c71a39f0-c241-4c12-9c96-f94d306bc86d",
  "citizen_id": "CIT-0001",
  "citizen_name": "Aarav Sharma",
  "trigger_event": "MILESTONE_AGE_18",
  "previous_age": 17,
  "calculated_age": 18,
  "previous_dob": "2008-11-15",
  "simulated_dob": "2008-10-28",
  "eligible_services": [...],
  "detailed_results": [...],
  "preliminary_notes": "Simulated event 'MILESTONE_AGE_18' updated age from 17 to 18. Identified 3 statutory government schemes with preliminary match.",
  "llm_explanation": "Badhai ho Aarav ji! Aapne safalta-purvak 18th birthday milestone reach kiya hai...",
  "created_at": "2026-10-28T10:50:00Z"
}
```

---

### 3.6 Outbound Calls & Audio Telemetry

#### Dispatch Outbound Call
```http
POST /api/calls
POST /api/v1/demo/calls
Content-Type: application/json

{
  "citizen_id": "CIT-0001",
  "trigger_event": "MILESTONE_AGE_18",
  "is_real_call": false
}
```
**Response `201 Created`**:
```json
{
  "id": "job-87192",
  "citizen_id": "CIT-0001",
  "citizen_name": "Aarav Sharma",
  "trigger_event": "MILESTONE_AGE_18",
  "job_status": "COMPLETED",
  "idempotency_key": "call-CIT-0001-MILESTONE_AGE_18",
  "attempt_count": 1,
  "scheduled_at": "2026-10-28T10:50:00Z",
  "duration_seconds": 45,
  "is_real_call": false,
  "recipient_phone": "DEMO-PHONE-0001",
  "transcript_events": [
    {
      "id": "ev-1",
      "speaker": "AI_AGENT",
      "transcript_segment": "Namaste Aarav ji! Main Bharat Assist se bol raha hoon...",
      "timestamp": "2026-10-28T10:50:02Z",
      "latency_ms": 320
    },
    {
      "id": "ev-2",
      "speaker": "CITIZEN",
      "transcript_segment": "Haan boliye, kya baat hai?",
      "timestamp": "2026-10-28T10:50:04Z",
      "latency_ms": 280
    }
  ]
}
```

*Note: Attempting to call the same citizen with the same trigger event returns `HTTP 409 Conflict` (Idempotency Enforced).*

#### Get Call Details & Transcript
```http
GET /api/calls/{call_id}
GET /api/v1/demo/calls/{call_id}
```

---

### 3.7 Bolna.ai Webhook Receiver

```http
POST /api/webhooks/bolna
POST /api/v1/webhooks/bolna
Content-Type: application/json

{
  "id": "execution-uuid-1234",
  "status": "completed",
  "call_duration": 48,
  "transcript": "Namaste! Haan maine Voter ID application samajh liya hai."
}
```
**Response `200 OK`**:
```json
{
  "status": "processed",
  "job_id": "job-uuid",
  "job_status": "COMPLETED"
}
```

---

### 3.8 ElevenLabs Voice Synthesis & Spoken Dialogue

#### 3.8.1 Voice Service Status
```http
GET /api/voice/status
GET /api/v1/voice/status
```
Returns safe diagnostic health of the ElevenLabs TTS provider without revealing credentials.

**Response `200 OK`**:
```json
{
  "configured": true,
  "status": "ready",
  "provider": "ElevenLabs",
  "voice_name": "Timbre",
  "voice_id_set": true,
  "voice_id": "your_custom_voice_id",
  "model_id": "eleven_multilingual_v2",
  "api_key_set": true
}
```

#### 3.8.2 Direct Text-to-Speech Synthesis
```http
POST /api/voice/synthesize
POST /api/v1/voice/synthesize
Content-Type: application/json

{
  "text": "Namaste! Voter ID form 6 aavedan ke liye voters.eci.gov.in par login karein."
}
```
**Response `200 OK`**:
- `Content-Type: audio/mpeg`
- Body: Binary MP3 audio stream for playback.

#### 3.8.3 Conversational Spoken AI Chat
```http
POST /api/voice/chat
POST /api/v1/voice/chat
Content-Type: application/json

{
  "citizen_id": "CIT-0001",
  "message": "Mujhe Voter ID card banwana hai, kaise karoon?",
  "language_preference": "Hinglish"
}
```
Executes full voice pipeline:
1. Grounding schemes retrieved for citizen from statutory catalogue.
2. NVIDIA Nemotron (`nvidia/nemotron-3.5-super-vl-120b-a12b`) generates grounded Hindi/Hinglish guidance.
3. ElevenLabs synthesizes spoken response using custom Timbre voice (`eleven_multilingual_v2`).
4. Returns both transcript and MP3 audio stream / base64 payload.

**Response `200 OK`**:
```json
{
  "conversation_id": "conv-uuid-5678",
  "citizen_id": "CIT-0001",
  "answer": "नमस्ते! 18 वर्ष की आयु होने पर आप वोटर आईडी कार्ड के लिए आवेदन कर सकते हैं।",
  "language": "Hindi",
  "audio_base64": "//uQZAAAAAAAAAAAAAAAAAAAAAAAWGluZwAAAA8AAA...",
  "audio_format": "audio/mpeg",
  "audio_url": "/api/v1/voice/audio/aud-a1b2c3d4e5f6",
  "grounded_services": [
    {
      "service_code": "SVC-VOTER-ID",
      "name": "Voter Registration (Form 6 - National Voters' Services Portal)",
      "official_portal_url": "https://voters.eci.gov.in"
    }
  ],
  "confidence_note": "Preliminary guidance based on Timbre's stored service catalogue. Check the official portal for current rules and application processing.",
  "llm_model": "nvidia/nemotron-3.5-super-vl-120b-a12b",
  "tts_provider": "ElevenLabs",
  "voice_name": "Timbre"
}
```

#### 3.8.4 Stream Synthesized Audio by ID
```http
GET /api/voice/audio/{audio_id}
GET /api/v1/voice/audio/{audio_id}
```
Streams cached audio clip (`audio/mpeg`) directly for media players (`audioplayers`, browser).

---

### 3.9 Speech-to-Text & Telephone Conversational Turns

#### 3.9.1 Whisper Speech Recognition
```http
POST /api/voice/transcribe
POST /api/v1/voice/transcribe
```
Transcribes uploaded audio (WAV, MP3, WebM) or base64 audio payload using Faster-Whisper.

**Request**:
- Multipart Form: `file` (binary audio), optional `language="hi"`.
- Or Form: `audio_base64`, optional `language="hi"`.

**Response `200 OK`**:
```json
{
  "success": true,
  "text": "नमस्ते मुझे राशन कार्ड के लिए आवेदन करना है",
  "language": "hi",
  "language_probability": 0.99,
  "confidence": 0.94,
  "duration_seconds": 2.5,
  "latency_ms": 280.4,
  "is_unclear": false,
  "stop_requested": false,
  "clarification_needed": false,
  "clarification_prompt": null
}
```

#### 3.9.2 Full Conversational Turn (STT → LLM → TTS)
```http
POST /api/voice/turn
POST /api/v1/voice/turn
```
Executes one complete spoken conversational turn: transcribes caller audio, reasons over citizen profile and service catalogue using NVIDIA Nemotron in Hindi, synthesizes spoken audio via ElevenLabs, and tracks turn latencies.

**Request**:
```json
{
  "citizen_id": "CIT-0001",
  "session_id": "sess-optional-id",
  "audio_base64": "<base64_audio_payload>",
  "text": "नमस्ते, मुझे नया वोटर कार्ड बनवाना है।",
  "language": "Hindi",
  "synthesize_voice": true
}
```

**Response `200 OK`**:
```json
{
  "session_id": "sess-c9c48f536566",
  "turn_id": "turn-aabcde3d",
  "turn_index": 1,
  "user_transcript": "नमस्ते, मुझे नया वोटर कार्ड बनवाना है।",
  "ai_response": "नमस्ते! मैं टिम्ब्र हूँ, आपकी AI सहायक। वोटर आईडी बनवाने में मैं आपकी मदद कर सकता हूँ। कृपया बताएं, आपकी उम्र कितनी है?",
  "language": "Hindi",
  "latencies_ms": {
    "transcription_ms": 280.5,
    "llm_ms": 1124.2,
    "tts_ms": 792.9,
    "total_turn_ms": 2210.6
  },
  "is_unclear": false,
  "stop_requested": false,
  "audio_url": "/api/v1/voice/audio/aud-call-0260025b83",
  "audio_base64": null,
  "tts_error": null,
  "session_status": "ACTIVE"
}
```

#### 3.9.3 Call Session History & Diagnostics
```http
GET /api/voice/turn/{session_id}
GET /api/v1/voice/turn/{session_id}
```
Retrieves all turns, timestamps, and stage latency measurements for an active call session.

#### 3.9.4 Terminate Call Session
```http
POST /api/voice/turn/{session_id}/terminate
POST /api/v1/voice/turn/{session_id}/terminate
```
Concludes the call session gracefully and transitions status to `COMPLETED`.

#### 3.9.5 Audio Interruption & Barge-in Control
```http
POST /api/voice/playback/{session_id}/cancel
POST /api/v1/voice/playback/{session_id}/cancel
```
Immediately invalidates the active audio token, marks active playback buffers as cancelled, and discards any late-arriving TTS synthesis responses for this session.

**Response `200 OK`**:
```json
{
  "status": "cancelled",
  "session_id": "sess-c9c48f536566",
  "cancelled_audio_id": "aud-turn-12345"
}
```

```http
GET /api/voice/playback/{session_id}/audio/{audio_id}
GET /api/v1/voice/playback/{session_id}/audio/{audio_id}
```
Streams active audio buffer with real-time cancellation enforcement. If this audio buffer was cancelled by a user interruption or stop intent, the endpoint immediately returns `HTTP 410 Gone` to stop client media players from playing stale audio.

---

### 3.10 OpenAI-Compatible Custom LLM Telephony Bridge

These standard endpoints allow telephony providers (such as Bolna or any OpenAI-compatible voice agent platform) to connect directly to Timbre as a Custom LLM brain.

#### 3.10.1 Chat Completions
```http
POST /v1/chat/completions
```
Accepts OpenAI-format chat completion requests, automatically injects relevant statutory welfare context from Timbre's FastEmbed 384-D RAG knowledge base, formats multi-turn dialogue, and returns standard OpenAI JSON choices with stop reasons and usage metrics.

**Request**:
```json
{
  "model": "nvidia/nemotron-3.5-super-vl-120b-a12b",
  "messages": [
    {"role": "user", "content": "Namaste, mujhe Ayushman card ke baare mein bataiye."}
  ],
  "temperature": 0.2
}
```

**Response `200 OK`**:
```json
{
  "id": "chatcmpl-958da5c00ef8",
  "object": "chat.completion",
  "created": 1793287897,
  "model": "nvidia/nemotron-3.5-super-vl-120b-a12b",
  "choices": [
    {
      "index": 0,
      "message": {
        "role": "assistant",
        "content": "नमस्ते! आपके प्रश्न के अनुसार Ayushman Bharat PM-JAY (Golden Card) की जानकारी उपलब्ध है।...",
        "name": null
      },
      "finish_reason": "stop"
    }
  ],
  "usage": {
    "prompt_tokens": 40,
    "completion_tokens": 54,
    "total_tokens": 94
  }
}
```

#### 3.10.2 Model List
```http
GET /v1/models
```
Returns list of available models (`timbre-voice-agent`).

