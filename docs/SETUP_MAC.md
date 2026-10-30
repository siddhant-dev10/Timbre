# Mac setup

## Backend and local secrets

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp -n .env.example .env  # only creates the file when it does not already exist
# Edit backend/.env in a local editor and set NVIDIA_API_KEY.
# For speech, also set ELEVENLABS_API_KEY and ELEVENLABS_VOICE_ID.
uvicorn app.main:app --host 127.0.0.1 --port 8000
```

The required text model is `nvidia/nemotron-3.5-super-vl-120b-a12b`, through NVIDIA's OpenAI-compatible base URL `https://integrate.api.nvidia.com/v1`. Optional settings are `NVIDIA_TIMEOUT_SECONDS`, `NVIDIA_MAX_TOKENS`, `NVIDIA_TEMPERATURE`, `NVIDIA_TOP_P`, and `NVIDIA_REASONING_EFFORT` (`none`, `low`, or `high`). Default reasoning effort is `none` for lower latency; increase it when a task needs more deliberate reasoning. Keys are read only by the backend and must never be passed to Flutter build arguments.

Whisper speech recognition runs via local `faster-whisper` (`base` model, int8 quantization on CPU). It converts spoken audio (WAV, MP3, WebM) into Hindi/English text with calibrated confidence scores, voice activity filtering, and latency instrumentation. If speech is unclear, it triggers a polite clarification prompt rather than hallucinating. If the caller requests termination ("रुको", "फोन काटो", "stop"), it marks the session terminated and concludes gracefully.

ElevenLabs uses `ELEVENLABS_TTS_MODEL_ID=eleven_multilingual_v2` and the configured Timbre voice ID. Spoken conversational turns are coordinated via `POST /api/v1/voice/turn`: caller audio is transcribed by Whisper, reasoned over in Devanagari Hindi by NVIDIA Nemotron, and synthesized into natural Hindi speech via ElevenLabs, tracking stage-by-stage latencies.

The Calls screen has a **Local dry-run** mode. It needs a synthetic profile, a test number, and recipient consent. The backend validates the number, stores only its last four digits, and creates a fictional transcript. It never contacts Bolna or any phone network. This is not an audio conversation.

## Records and SQLite

The original generated dataset is the initial 100-record source. Startup seeds it only when the configured database has no citizen rows. Existing SQLite files are upgraded additively with `record_source` and `archived_at` fields. There is no migration framework; make a backup before updating a database. Stop FastAPI, then back up from the repository root:

```bash
sqlite3 backend/data/timbre.db ".backup 'backend/data/timbre-backup.db'"
```

Restore by stopping the backend and replacing `backend/data/timbre.db` with the backup file. Keep backups private; the database may contain imported personal data.

In backend mode, Citizens supports add/edit, archive/restore, CSV/JSON import, and CSV export. Import files are UTF-8, up to 5 MB and 5,000 records. JSON may be an array or an object containing `citizens`. Required fields are `first_name`, `last_name`, `date_of_birth` (`YYYY-MM-DD`), `state`, `district`, and `city_or_village`. Optional `record_source` is `synthetic` or `real` and defaults to `synthetic`; existing 100 rows remain synthetic. Duplicate IDs, duplicate name/date identities, and missing required fields reject the entire batch. The import report avoids echoing rejected field values. Export includes active records only. The built-in form creates synthetic records and edits common identity/location fields; fuller edits are supported through the API and import format.

The live local API returned all 100 active records. Health reported SQLite healthy and NVIDIA/ElevenLabs configured (provider connectivity is not polled by `/health`); Bolna was not configured, so overall health was degraded. Startup and automated tests do not call paid providers.

## Optional approved phone test

Live dialing is locked by default. Do not enable it until a Bolna account and a manually configured test agent are ready. Bolna hosts the telephony and real-time voice pipeline; the Mac backend submits one approved call with a synthetic scenario. It does not send a citizen record, name, ID, or other profile values to Bolna.

1. Create a Bolna account and API key in its dashboard. Create one agent with Hindi/English language support, speech recognition, a streaming LLM, ElevenLabs or another supported TTS voice, and a greeting that speaks the exact AI disclosure shown in Timbre. In the agent's prompt, use the per-call `opening_disclosure` and `test_scenario` variables sent by Timbre.
2. Disable retries and batch calling in the agent. Set a short maximum call duration. Test speech, language switching, interruptions, and the greeting in Bolna's own non-phone test console before enabling any call.
3. In the ignored `backend/.env`, set `BOLNA_API_KEY`, `BOLNA_AGENT_ID`, and a randomly generated `BOLNA_WEBHOOK_SECRET`. In the Bolna agent's Webhook Configuration, enable custom headers and set `X-Timbre-Webhook-Secret` to the same value. Timbre rejects webhook requests without this header. The webhook endpoint must be publicly reachable; restrict inbound traffic to Bolna's current documented source IPs/firewall allowlist. Set `BOLNA_TEST_AGENT_VERIFIED=true`, and only then `ENABLE_REAL_CALLS=true`. Keep the file local and restart the backend. The agent-verified setting is your local attestation that its AI disclosure, fictional prompt, language setup, no-retry setting, and short duration limit were reviewed.
4. In Timbre, select **Approved live test**, enter a number whose owner has agreed to receive one call, review the displayed script and disclosure, inspect Bolna's account default outbound caller ID in its dashboard, and check the caller-ID review box only after confirming that number is authorized for this test. Then type `CALL ONCE`. A final confirmation dialog is shown before the single call request is sent.

To connect the selected Nemotron model to a Bolna agent, use **Settings → Integrations → LLM → Custom LLM**, choose **Other (OpenAI-compatible)**, and configure base URL `https://integrate.api.nvidia.com/v1` and model ID `nvidia/nemotron-3.5-super-vl-120b-a12b`. Enter a valid NVIDIA key directly into Bolna's provider credential form. Bolna sends streaming chat-completions requests. This is separate from Timbre's local non-streaming chat API. One minimal request to the previous Ultra model returned HTTP 403. After rotating the local NVIDIA key, a minimal request to Super VL returned HTTP 200 with a short non-empty Hinglish response. This does not establish sustained quality, quota, or Bolna streaming behavior.

Bolna's current ElevenLabs integration documents the models `eleven_turbo_v2_5`, `eleven_flash_v2_5`, `eleven_v3_conversational`, and `eleven_v4_turbo`; it does not list Timbre's standalone `eleven_multilingual_v2` model. Keep `ELEVENLABS_TTS_MODEL_ID=eleven_multilingual_v2` for Timbre's explicit Speak action. For a Bolna call agent, choose a supported model and verify the existing voice ID appears in the connected account's voice picker before marking the agent ready. After rotating the local ElevenLabs secret, short English and Hindi synthesis requests returned HTTP 200 with non-empty `audio/mpeg` MP3 data. The configured voice and direct synthesis are therefore authenticated; playback through the Flutter app remains unverified. Bolna's Hindi guidance also lists Hindi/code-switching transcription options such as Sarvam and Soniox; their provider setup and usage may add charges.

The required telephony configuration is not present in this repository's current local setup. Do not put credentials in the Codex chat. If creating the settings file, run `cd backend && cp -n .env.example .env`, then enter `BOLNA_API_KEY` and `BOLNA_AGENT_ID` in a local editor. Bolna's dashboard supplies the API key and agent ID. Never put them in Flutter build arguments.

Bolna's API uses the account's default caller number if `from_phone_number` is omitted; if a sender number is passed, Bolna's call API requires it to be a number purchased in that Bolna account. Timbre omits the caller-number field. The proposed personal caller ID is neither verified nor used. For India, provider, number, and regulatory requirements may depend on the call purpose; confirm eligible number types and verification with Bolna and the relevant carrier before any live call.

Pricing is not free: Bolna's public page lists pay-as-you-go from $0.06/minute, with telephony and platform charges on top, and $5 in new-account trial credits. Trial accounts are limited to calls to verified numbers and up to two concurrent calls. Provider pricing, verification, and trial availability can change; check the dashboard before a call. NVIDIA and ElevenLabs usage may also be billed separately if their own provider accounts are connected to the agent.

Timbre can refresh status and cancel a call while Bolna reports it queued or scheduled. Bolna's documented stop API does not provide an app-side hang-up for an active phone call. The recipient must hang up from their phone; this limitation means the app does not yet provide reliable active-call termination. If a submission times out, the result is marked unknown and must be checked in Bolna before any retry. Timbre never retries automatically and does not copy provider transcripts or recordings into SQLite.

## Flutter desktop app

Building and running the macOS app requires full Xcode, not only Xcode Command Line Tools. On 2026-10-29, `xcode-select -p` returned `/Library/Developer/CommandLineTools`, and `flutter build macos --debug` stopped with `Xcode not installed; this is necessary for iOS and macOS development.` Native build, launch, and speaker playback are therefore unverified.

To install and configure full Xcode on this Mac:
1. Download Xcode from the Mac App Store or https://developer.apple.com/xcode/.
2. Select Xcode as the active developer toolchain:
   ```bash
   sudo xcode-select --switch /Applications/Xcode.app/Contents/Developer
   sudo xcodebuild -license accept
   ```
3. Verify CocoaPods installation:
   ```bash
   sudo gem install cocoapods
   cd frontend/macos && pod install
   ```

In a second terminal:

```bash
cd frontend
flutter pub get
flutter run -d macos
```

Note: `AppConfig.isDemoMode` defaults to `false`, connecting directly to the Mac-local FastAPI backend at `http://127.0.0.1:8000/api/v1`. To run Flutter completely offline with mock repositories, launch with:
```bash
flutter run -d macos --dart-define=TIMBRE_DEMO_MODE=true
```

Backend health is `http://127.0.0.1:8000/health`; API docs are at `http://127.0.0.1:8000/docs`.

## Provider access and limits

The selected model is `nvidia/nemotron-3.5-super-vl-120b-a12b`, called through the NVIDIA-hosted OpenAI-compatible API. Model selection considered the following current NVIDIA Build entries:

| Model | Hindi / Hinglish | Latency | Reasoning and tools | NVIDIA Build access |
| --- | --- | --- | --- | --- |
| `nvidia/nemotron-3.5-super-vl-120b-a12b` — selected | NVIDIA reports 100B Indic continued-pretraining tokens spanning 22 Indian languages; Hindi/Hinglish conversation quality still needs evaluation. | 12B active parameters plus native multi-token prediction. NVIDIA reports up to 4,856 output tokens/s/GPU and at least 50 tokens/s/user on a specific GB200 workload; hosted endpoint latency is not published. | Configurable reasoning and tool-assisted workflows; its OpenAI-compatible API supports streaming and tool parameters. | NVIDIA Build lists a free prototype endpoint, subject to trial terms, account access, and quotas. A minimal request with the rotated local key returned HTTP 200. |
| `nvidia/nemotron-3-ultra-550b-a55b` | Hindi is explicitly listed; Hinglish still needs evaluation. | 55B active parameters with multi-token prediction; hosted endpoint latency is not published. | NVIDIA positions it for frontier reasoning, complex agentic workflows, multilingual reasoning, and tool use. | Trial access and quotas depend on the account. The previous request to this model returned HTTP 403. |
| `nvidia/nemotron-3.5-lightning-30b-a3b` | Hindi is not listed in its supported languages. | 3B active parameters; NVIDIA markets it as its fastest 30B A3B model, but hosted endpoint latency is not published. | Agentic and tool-use oriented; its model card describes general reasoning and chat but lists fewer supported languages than Super VL's Indic training. | NVIDIA Build lists a free endpoint, subject to trial terms and account-specific quotas. |
| `nvidia/nemotron-3.5-bolt-e4b` | Hindi/Hinglish are not listed; the card lists English, Spanish, French, German, Italian, and Japanese. | 4B effective parameters; no hosted latency benchmark is published. | Compact reasoning/tool-calling model with strong small-model agentic benchmarks; NVIDIA primarily recommends it for customization and post-training, not direct production inference. | NVIDIA Build lists a free endpoint under trial terms; language fit is poor for this use. |
| `nvidia/nemotron-voicechat` | Hindi support is not established in its model card. | Full-duplex speech-to-speech; NVIDIA reports a 0.26-second turn-taking benchmark, not hosted end-to-end latency. | One speech model handles input and output audio. It would replace the selected ElevenLabs TTS path. | Early-access endpoint; account approval may be required. |

Nemotron 3.5 Super VL remains the selected candidate for its 12B active size, native multi-token prediction, Indic continued pretraining across 22 Indian languages, reasoning controls, and tool-use support. NVIDIA's throughput figures are from a specific GB200 workload, not a hosted first-token latency guarantee. Ultra explicitly lists Hindi and targets frontier reasoning, but activates 55B parameters. Lightning is advertised as the fastest 30B A3B model, but Hindi is not listed. Bolt E4B is smaller and supports tools but its card lists no Hindi and recommends customization rather than direct production use. VoiceChat is NVIDIA's full-duplex candidate, but Hindi support is not established and it would replace the separate ElevenLabs TTS path. Hinglish quality and actual hosted endpoint latency remain unverified. See NVIDIA's [Super VL model card](https://build.nvidia.com/nvidia/nemotron-3.5-super-vl-120b-a12b/modelcard), [Super and Lightning performance notes](https://research.nvidia.com/labs/nemotron/Nemotron-3.5-Super-and-Lightning/), [Bolt E4B model card](https://build.nvidia.com/nvidia/nemotron-3.5-bolt-e4b/modelcard), [Lightning model card](https://build.nvidia.com/nvidia/nemotron-3.5-lightning-30b-a3b/modelcard), [Ultra model card](https://build.nvidia.com/nvidia/nemotron-3-ultra-550b-a55b/modelcard), and [VoiceChat model card](https://build.nvidia.com/nvidia/nemotron-voicechat/modelcard).

NVIDIA Build currently lists the Super VL hosted prototype endpoint as free, under NVIDIA's API trial terms and account-specific quotas. An earlier request to Ultra returned HTTP 403; after rotating the local NVIDIA key, Super VL returned HTTP 200. This confirms a response for the selected endpoint, not ongoing quota or production entitlement. Trial terms may retain prompts and outputs; send only synthetic, non-sensitive text. Neither model is run locally on a typical Mac.

NVIDIA's model entry currently shows **Free Endpoint: Available**; free access is subject to NVIDIA API trial terms and account-specific rate/quota limits, not a production SLA. During account setup, the dashboard showed a 40 RPM limit; check the current Build dashboard because limits may change. ElevenLabs currently lists a Free plan with 10,000 monthly credits; `eleven_multilingual_v2` costs 1 credit per input character through the API, and its API limit is 10,000 characters per request. The two short provider checks consumed credits/quota; no project tests call either provider. Check the account's live balance before generating. Current references: [NVIDIA model endpoint](https://build.nvidia.com/nvidia/nemotron-3.5-super-vl-120b-a12b), [ElevenLabs pricing](https://elevenlabs.io/pricing), and [ElevenLabs API pricing](https://elevenlabs.io/pricing/api).

For a Bolna phone agent, configure this model as an OpenAI-compatible streaming chat-completions endpoint. Bolna handles streaming within its agent; Timbre's local chat API remains request/response JSON. Test the configured model in Bolna's non-phone console before enabling the call gate.

On 2026-10-29, an earlier request to NVIDIA Ultra returned HTTP 403 and earlier ElevenLabs requests failed authentication. After local rotation, one NVIDIA Super VL prompt returned HTTP 200 with a short Hinglish response; short English and Hindi ElevenLabs requests returned HTTP 200 with valid MP3 headers and non-empty audio. These are minimal authentication and response checks, not a full model-quality evaluation or playback test. The current local environment has no Bolna API key or agent ID configured. No call or SMS was attempted, and no credentials are included in repository example files.
