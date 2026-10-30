# Timbre Conversational Calling Agent: Telephony & Interaction Architecture

## 1. System Architecture

Timbre integrates real-time Automatic Speech Recognition (Whisper), grounded knowledge retrieval (RAG), conversational LLM reasoning (NVIDIA Nemotron), and high-fidelity speech synthesis (ElevenLabs) into a unified voice agent pipeline:

```
                      [ PSTN Telephone Network ]
                                 │
                                 ▼ (Inbound/Outbound Stream)
                    [ Bolna Telephony Gateway ]
                                 │
           ┌─────────────────────┴─────────────────────┐
           ▼                                           ▼
[ Speech-to-Text (STT) ]                     [ Audio Playback ]
• Live Call: Provider Transcriber             • Streaming MP3 Playback
• Local Test: Faster-Whisper Base             • Interruption Barge-in
           │                                           ▲
           ▼ [ Transcript ]                            │
┌──────────────────────────────────────────────────────┴──────────────┐
│                    Timbre Conversation Controller                   │
│                                                                     │
│  State Machine: IDLE ➔ INITIALIZING ➔ SPEAKING ➔ LISTENING ➔       │
│                 TRANSCRIBING ➔ RETRIEVING_CONTEXT ➔ THINKING ➔      │
│                 RESPONDING ➔ [RESUMING] ➔ SPEAKING / COMPLETED      │
│                                                                     │
│  • Memory & Agenda: Tracks current topic & remaining outline        │
│  • Interruption Handling: Invalidates stale audio tokens instantly  │
│  • Grounding Engine: Hybrid Vector + BM25 RAG Retrieval             │
└──────────────────────────────────────┬──────────────────────────────┘
                                       │
                      ┌────────────────┴────────────────┐
                      ▼                                 ▼
         [ NVIDIA Nemotron 120B ]           [ ElevenLabs TTS ]
         • Conversational Hindi Policy      • Model: Multilingual v2
         • Grounded on Knowledge Base       • Custom Timbre Voice
         • Brevity: 2-3 sentences max       • MP3 Streaming Cache
```

---

## 2. Interaction Dynamics (NotebookLM Paradigm)

1. **Agenda-Driven Narrative:** When Timbre initiates a call or discussion, it maintains a planned topic outline (`planned_agenda_points`).
2. **Natural Interruption (Barge-in):** If the citizen speaks while Timbre is talking, Timbre immediately:
   - Invalidates the active audio token (`active_audio_token = None`), preventing any stale audio playback.
   - Transitions state: `SPEAKING` $\rightarrow$ `LISTENING`.
   - Captures and transcribes the citizen's utterance.
3. **Contextual In-Topic Answer:** Retrieves relevant knowledge chunks, reasons over them with Nemotron, and provides a direct, concise Hindi answer.
4. **Smooth Narrative Resumption:** Once the question is answered, Timbre seamlessly transitions back to the unfinished narrative agenda using natural bridging phrases (*"जैसा कि हम चर्चा कर रहे थे..."* / *"As we were discussing..."*).

---

## 3. Telephony Webhooks & Resilience

- **Authentication:** All Bolna webhooks must deliver an authenticated `X-Timbre-Webhook-Secret` header verified using constant-time comparison (`secrets.compare_digest`).
- **Deduplication:** Bolna execution IDs and citizen trigger keys enforce strict idempotency. Duplicate delivery of completed or progress webhooks will not create redundant jobs.
- **Privacy & Redaction:** Full phone numbers are never stored in plain text; numbers are masked (`***9531`) and zero audio recordings are stored on third-party servers.

---

## 4. Mandatory Real-Call Safety Gate

Live telephone calls over PSTN are disabled by default (`ENABLE_REAL_CALLS=false`). Live calling requires satisfying all 9 mandatory requirements:

1. **Explicit Recipient Consent:** Written or verified affirmative consent from the participating individual.
2. **Explicit Number Confirmation:** Phone number validated in international E.164 format.
3. **Authorized Caller ID:** Verified DID or carrier-assigned virtual number. Indian telecom regulations (TRAI/DoT, TCCCPR 2018) strictly prohibit sending unverified personal numbers as CLI over PSTN.
4. **AI Identity Disclosure:** The agent must explicitly disclose its artificial identity within the opening 10 seconds.
5. **Script Review:** Full preview of the opening script must be presented to the user.
6. **Cost & Quota Transparency:** Telephony and TTS per-minute charges must be reviewed.
7. **Explicit Individual Authorization:** User must confirm individual one-call dispatch (with confirmation phrase *"CALL 1 TEST NUMBER"*).
8. **Active Call Cancellation Control:** The system must provide reliable cancellation for queued/scheduled calls.
9. **Zero Bulk or Automatic Dialing:** Bulk campaigns and automatic retries are strictly prohibited in Timbre's codebase.
