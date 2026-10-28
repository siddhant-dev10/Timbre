# Timbre REST API Documentation

> **AI-Powered Indian Government Services Voice Assistant — Backend API Specification**

This document describes the REST API exposed by the ASUS TUF development server (Arch Linux) for the Flutter administrative cockpit and simulation client on macOS.

---

## 1. Server & Connectivity

- **Localhost Base URL**: `http://127.0.0.1:8000` (or `http://localhost:8000`)
- **ASUS LAN Base URL**: `http://10.32.72.23:8000` (or current local IP from `ip -br -4 addr show wlp45s0`)
- **Supported API Prefixes**:
  - `/api` (Standard REST endpoints)
  - `/api/v1` (Flutter client versioned prefix)
- **Interactive Documentation**:
  - OpenAPI Swagger UI: `http://10.32.72.23:8000/docs`
  - ReDoc: `http://10.32.72.23:8000/redoc`

### CORS Policy
The backend permits requests from Flutter web and desktop development hosts (`http://localhost:*`, `http://127.0.0.1:*`, `http://192.168.0.*`, and `app://*`). Allowed origins are configurable via `ALLOWED_ORIGINS` in `.env`.

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
Returns system operational status, database connectivity, and local LLM / Bolna availability.

**Response `200 OK`**:
```json
{
  "status": "ok",
  "version": "1.0.0",
  "mode": "demo",
  "database": {
    "status": "healthy",
    "details": "SQLite connected"
  },
  "local_llm": {
    "status": "healthy",
    "details": "Target: qwen3.5:9b (Installed: qwen3.5:9b)"
  },
  "bolna_voice": {
    "status": "demo_simulation",
    "details": "Configured: false, Real Calls Enabled: false"
  },
  "elevenlabs_tts": {
    "status": "credentials_pending",
    "details": "Provider: ElevenLabs, Custom Voice: Timbre, Configured: false, Model: eleven_multilingual_v2"
  },
  "real_calls_enabled": false
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
2. Local Qwen 3.5 9B generates Hinglish guidance.
3. ElevenLabs synthesizes spoken response using custom Timbre voice.
4. Returns both transcript and MP3 audio stream / base64 payload.

**Response `200 OK`**:
```json
{
  "conversation_id": "conv-uuid-5678",
  "citizen_id": "CIT-0001",
  "answer": "Namaste Aarav ji! Voter ID ke liye aap ECI portal voters.eci.gov.in par Form 6 bhar sakte hain.",
  "language": "Hinglish",
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
  "confidence_note": "Preliminary AI guidance based on verified official catalogue entries. Consult official portals for statutory application processing.",
  "llm_model": "qwen3.5:9b",
  "tts_provider": "ElevenLabs",
  "voice_name": "Timbre"
}
```

#### 3.8.4 Stream Synthesized Audio by ID
```http
GET /api/voice/audio/{audio_id}
GET /api/v1/voice/audio/{audio_id}
```
Streams cached audio clip (`audio/mpeg`) directly for media players (`just_audio`, `audioplayers`, browser).
