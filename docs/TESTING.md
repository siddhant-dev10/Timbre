# Timbre Automated Test Suite & Quality Assurance Specification

## 1. Quality Assurance Invariants

1. **Zero Unconsented Telephony:** Automated tests never place live telephone calls, never send SMS messages, and never incur third-party provider billing (`ENABLE_REAL_CALLS=false` enforced by default).
2. **Synthetic Data Exclusivity:** All automated tests use deterministic synthetic fixtures (`CIT-0001` through `CIT-0100`).
3. **No Private Secrets in Tests:** Tests verify authentication failure modes using dummy keys and mock responses. Real API keys in `backend/.env` are isolated from unit test mocks.
4. **Deterministic Knowledge Retrieval:** Embeddings are versioned and generated deterministically via ONNX FastEmbed; hashes or randomized algorithms are strictly forbidden.
5. **Real Local AI Inference Verification:** Faster-Whisper ASR is verified against real 16kHz PCM audio bytes on Apple Silicon CPU/MPS without mocking the underlying CTranslate2 model.

---

## 2. Test Suite Inventory

### Backend Test Suites (154 Automated Tests Passed)

| Test File | Count | Scope |
| :--- | :--- | :--- |
| `test_retrieval_evaluation.py` | 3 | **100-Query Cross-Lingual RAG Benchmark:** 80 in-domain queries across 10 statutory schemes (Hindi Devanagari, Hinglish, English, synonyms) + 20 out-of-domain rejection queries; cross-process vector stability and version incompatibility handling. |
| `test_audio_interruption.py` | 4 | Real-time audio interruption & barge-in: active buffer cancellation, late TTS response discard, HTTP 410 Gone on cancelled playback tokens, session isolation. |
| `test_notebooklm_conversational_engine.py` | 20 | **20 NotebookLM-style interaction scenarios:** Hindi, English, Hinglish, interruptions, follow-up questions, PDF retrieval, missing knowledge, out-of-scope queries, repeat requests, unclear speech, silence, provider timeouts/failures, webhook deduplication, stop intent, and stale audio prevention. |
| `test_knowledge_base.py` | 5 | Ingestion of PDF, Markdown, CSV, JSON; FastEmbed ONNX multilingual embeddings (384-D); hybrid retrieval; API endpoints; cascading deletion. |
| `test_whisper_service.py` | 18 | Real CTranslate2 Faster-Whisper inference on Apple Silicon (16kHz PCM WAV bytes), stop intent detection in Hindi/English, confidence calibration, invalid audio rejection, noise clarification triggers, `/transcribe` endpoint. |
| `test_conversational_turn.py` | 6 | End-to-end multi-turn pipeline (`/voice/turn`), stage latency tracking, stop intent termination, unclear clarification, ElevenLabs TTS integration. |
| `test_calls_safety.py` | 13 | Hard call safety invariant (`ENABLE_REAL_CALLS=false`), phone number masking (`***9531`), prohibition of dialing synthetic records, idempotent dry-run rehearsal. |
| `test_citizens.py` | 10 | SQLite CRUD, search, pagination, transactional CSV/JSON import, duplicate rejection, archive/restore, export. |
| `test_dataset_and_seeding.py` | 4 | Auto-seeding verification of 100 fictional records and 10 statutory schemes. |
| `test_elevenlabs_tts.py` | 15 | ElevenLabs TTS adapter, error status mapping (401, 402, 404, 429, 500), audio caching and streaming. |
| `test_llm_service.py` | 14 | NVIDIA Nemotron adapter, grounded system prompts, Hinglish/Hindi policy, timeout recovery. |
| `test_webhooks.py` | 7 | HMAC webhook verification (`X-Timbre-Webhook-Secret`), execution ID mapping, transcript ingestion, replay cache deduplication. |
| `test_rules_engine.py` | 3 | Deterministic age math, milestone evaluation (e.g. 18th birthday), statutory eligibility checks. |
| `test_services.py` | 4 | Statutory schemes catalogue query, category filtering, official portal URLs. |
| `test_health.py` | 5 | Health endpoint (`/health`), component statuses (DB, LLM, TTS, Telephony). |
| `test_simulations.py` | 3 | Milestone simulation lifecycle. |
| `test_bolna_service.py` | 3 | Bolna telephony provider client, parameter schemas, custom LLM integration spec. |
| `test_chat.py` | 6 | Chat endpoint and conversation history. |
| `test_profile_context.py` | 2 | Context isolation. |
| `test_controlled_demo.py` | 1 | Controlled demo workflow. |

### Frontend Test Suites (13 Automated Tests Passed)

| Test File | Tests | Scope |
| :--- | :--- | :--- |
| `api_call_repository_test.dart` | 2 | Verifies dry-run calls only target local rehearsal endpoint; approved test-call requires full review payload. |
| `app_state_test.dart` | 1 | Observable state management and initialization. |
| `citizen_test.dart` | 1 | Citizen model serialization and demographic fields. |
| `mock_repository_test.dart` | 1 | Mock repository isolation when explicitly requested via `--dart-define=TIMBRE_DEMO_MODE=true`. |
| `widget_test.dart` | 8 | Dashboard rendering, safety banners, navigation between Citizens, Chat, Calls, and Services. |

---

## 3. Running the Test Suites

### Backend Tests
```bash
cd /Users/sidh._./Timbre/backend
source .venv/bin/activate
PYTHONPATH=. pytest -v
```

### 100-Query Cross-Lingual Retrieval Benchmark
```bash
cd /Users/sidh._./Timbre/backend
source .venv/bin/activate
PYTHONPATH=. pytest tests/test_retrieval_evaluation.py -v -s
```

### Flutter Tests & Static Analysis
```bash
cd /Users/sidh._./Timbre/frontend
flutter analyze
flutter test
```
