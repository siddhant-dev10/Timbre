# Timbre

> **AI-Powered, Voice-First Government Services Assistant for India (Concept: Bharat Assist)**

[![Status: Frontend Milestone 1 Implemented](https://img.shields.io/badge/Status-Frontend%20Milestone%201%20Implemented-brightgreen.svg)](#j-project-status-and-contribution)
[![Architecture: Voice--First AI](https://img.shields.io/badge/Architecture-Voice--First%20AI-blue.svg)](#c-proposed-solution)
[![Interface: Flutter Dashboard](https://img.shields.io/badge/Interface-Flutter%203.19+%20%2F%20Dart%203.3+-02569B.svg)](#d-core-features)
[![Documentation: TECH.md](https://img.shields.io/badge/Technical%20Docs-TECH.md-009688.svg)](TECH.md)
[![Frontend Guide: FRONTEND.md](https://img.shields.io/badge/Frontend%20Docs-FRONTEND.md-teal.svg)](FRONTEND.md)

---

## A. Project Introduction

**Timbre** is an AI-powered, voice-first public service assistant platform. **Bharat Assist** is the core product concept powering Timbre: a proactive civic AI assistant designed to connect Indian citizens with statutory government documents, welfare schemes, and civic entitlements through natural, code-switched Hinglish conversations.

### Why Voice-First Matters for India

India's digital public infrastructure has expanded rapidly through platforms like Aadhaar, DigiLocker, Parivahan Sewa, and the National Voter's Service Portal. However, millions of citizens still encounter steep barriers when attempting to access these benefits:

- **The Digital Literacy Barrier**: Many citizens who own basic feature phones or shared family smartphones find multi-step web forms, CAPTCHA challenges, OTP flows, and multi-tier menu hierarchies intimidating.
- **The Information Discovery Deficit**: Citizens often only learn about essential government schemes—such as voter registration, learner's driving licences, educational scholarships, or welfare pensions—months or years after they become eligible, frequently missing critical application windows.
- **Linguistic Reality**: Everyday communication across Indian households occurs in fluid vernaculars and code-switched dialogues (such as **Hinglish**—Hindi interwoven with everyday English terms like *form*, *date of birth*, *licence*, *website*, and *portal*). Traditional automated telephone helplines rely on formal, rigid scripts that fail to understand natural colloquial phrasing.

Timbre bridges this divide by delivering **proactive, natural spoken dialogue**. Instead of requiring a citizen to search unfamiliar websites, the system identifies life milestones—such as turning 18 years old—and conducts a simulated, natural voice conversation in Hinglish to explain what documents they qualify for, what papers they need, and where to apply officially.

## Documentation

| Guide | Contents |
| :--- | :--- |
| [Technical architecture](TECH.md) | System design, two-machine architecture, data schemas, API specifications, and implementation guidance |
| [Frontend specification](FRONTEND.md) | Frontend implementation plan, folder structure, and UI/state architecture |
| [Core features](#d-core-features) | Product capabilities categorized by implementation state |
| [Real-world use cases](#e-real-world-use-cases) | Example citizen scenarios and conversational outcomes |
| [Project roadmap](#i-project-roadmap) | Development phases and current milestone progress |

---

## B. Problem Statement

Navigating government services in India presents four recurring challenges for everyday citizens:

1. **Awareness & Timeliness**: Citizens are rarely informed automatically when they qualify for a new entitlement or civic obligation (e.g., enrolling on the electoral roll at age 18, applying for a learner's driving permit, or linking statutory identities).
2. **Procedural Complexity**: Official notification gazettes and departmental circulars are written in formal administrative vocabulary that is difficult for non-specialists to interpret.
3. **Misinformation & Middlemen Exploitation**: Unofficial third-party portals, fraudulent cyber-café operators, and touts frequently charge exorbitant illegal fees for services that the government provides free or at nominal statutory charges.
4. **Rigid Helplines**: Existing Interactive Voice Response (IVR) helplines force callers through cumbersome numeric menus (*"Press 1 for Hindi, Press 2 for Services..."*), offering zero tolerance for follow-up questions, speech interruptions, or spontaneous topic changes.

---

## C. Proposed Solution

Timbre introduces an **event-driven, conversational voice assistance model**:

```
[ Citizen Lifecycle Event (e.g., Citizen Turns 18) ]
                        │
                        ▼
         [ Eligibility Evaluation Engine ]
                        │
                        ▼
       [ Deduplicated Simulated Outbound Call ]
                        │
                        ▼
     [ Real-Time Conversational Voice Session ]
   ├── Conducted in natural, colloquial Hinglish
   ├── Allows speech interruptions (barge-in) at any time
   ├── Supports natural topic switching (e.g., Voter ID ⇄ Driving Licence)
   └── Grounded strictly in verified official government data
```

By pairing lifecycle event detection with natural conversational voice intelligence, Timbre transforms government service delivery from a **passive, pull-based search chore** into a **proactive, push-based civic advisory service**.

---

## D. Core Features & Implementation Status

The following matrix documents the core features of Timbre, clearly identifying what is implemented in the repository, what is in active backend development on the ASUS laptop, and what is planned for subsequent phases:

| # | Feature | Status | Description & Repository Evidence |
| :-: | :--- | :---: | :--- |
| **1** | **Synthetic Citizen Management** | **Implemented (Frontend Demo)** | 100% fictional Indian citizen registry displayed in the Flutter console with search, filtering, and safety indicators (`frontend/lib/models/citizen.dart`). |
| **2** | **Age & Profile Updates** | **Implemented (Frontend Demo)** | Reactive life-event simulation controls allowing operators to adjust citizen dates of birth (`frontend/lib/screens/simulation/simulation_screen.dart`). |
| **3** | **Age-Related Event Detection** | **Implemented (Frontend Demo) / ASUS Backend In-Progress** | Detection of milestone transitions (e.g. crossing age 18 threshold `MILESTONE_AGE_18`) with automated job triggering. |
| **4** | **Government-Service Eligibility Evaluation** | **Implemented (Frontend Demo) / ASUS Backend In-Progress** | Programmatic rule engine evaluating qualification across ECI Voter Registration Form 6, MoRTH Parivahan Learner's Licence, and PM-JAY (`frontend/lib/screens/eligibility/`). |
| **5** | **Simulated Outbound-Call Triggering** | **Implemented (Frontend Demo)** | In-memory idempotent call queue manager generating simulated outbound voice jobs with deduplication keys (`frontend/lib/models/call_job.dart`). |
| **6** | **Natural Real-Time Hinglish Voice Conversations** | **In Progress (ASUS AGY)** | Spoken dialogue integration using local Qwen through Ollama and Bolna.ai on the ASUS TUF laptop. |
| **7** | **Interruption Handling & Turn-Taking** | **In Progress (ASUS AGY)** | Sub-second voice activity detection (barge-in) and turn-taking managed by Bolna.ai and the voice bridge. |
| **8** | **Government-Domain Topic Switching** | **In Progress (ASUS AGY)** | Context-preserving dialogue manager allowing callers to switch freely between government schemes in a single session. |
| **9** | **Service Guidance (Aadhaar, Voter ID, Driving Licence)** | **Implemented (Frontend Directory)** | Verified government scheme catalog with statutory fee tables, portal URLs, and application document checklists (`frontend/lib/screens/services/`). |
| **10** | **Verified Information & Official Portal Retrieval** | **Planned (ASUS Knowledge Base)** | Grounded fact lookup from curated public records to prevent hallucinations during speech synthesis. |
| **11** | **Call Status, Transcripts, & Event History** | **Implemented (Frontend Console)** | Call monitor displaying job queue states (`QUEUED`, `IN_PROGRESS`, `COMPLETED`), latency telemetry, and sample Hinglish transcript bubbles (`frontend/lib/screens/calls/`). |
| **12** | **Flutter Administration Dashboard** | **Implemented (MacBook Air M5)** | Production-ready Flutter administrative console running on macOS Desktop and Chrome with responsive navigation rail, health pill, and theme (`frontend/lib/`). |
| **13** | **Error Handling & Duplicate-Event Prevention** | **Implemented (Frontend) / Planned (DB)** | Deterministic idempotency key verification (`CALL_AGE18_<id>_<year>`) preventing duplicate call creation on repeated triggers. |

> [!NOTE]
> *Status Classification Guide*:
> - **Implemented (Frontend Demo)**: Fully written, verified, and passing automated Flutter test suites locally via the isolated demo data provider.
> - **In Progress (ASUS AGY)**: Active backend development on the ASUS TUF laptop (FastAPI, Ollama/Qwen, Bolna.ai).
> - **Planned**: Architectural design and contract documented, awaiting joint integration.

---

## E. Real-World Use Cases

The following concrete operational scenarios illustrate how Timbre behaves across diverse citizen interactions:

### Use Case 1: Milestone Outreach (Citizen Reaches Age 18)
- **Trigger**: The simulation clock advances or an administrator updates synthetic citizen Aarav Sharma's date of birth, crossing the 18-year statutory threshold.
- **System Behaviour**: The backend eligibility engine detects the milestone, qualifies Aarav for Voter Registration (ECI Form 6) and a Learner's Driving Licence (Parivahan), creates an idempotent call job, and initiates a simulated outbound voice call.
- **Expected Outcome**: The simulated phone rings. When answered, the assistant introduces itself transparently as an AI assistant from Timbre (Bharat Assist), congratulates Aarav on turning 18, and informs him that he is now eligible to apply for his Voter ID and Learner's Licence.

### Use Case 2: Fluid Cross-Service Topic Switching
- **Trigger**: During a conversation regarding Aadhaar address update requirements, the citizen spontaneously asks: *"Achha, driving licence banwane ke liye test kahan dena hota hai?"*
- **System Behaviour**: The conversational engine detects the shift in topic from UIDAI Aadhaar services to MoRTH Parivahan services. It maintains the user's demographic context without requiring a restart or menu navigation.
- **Expected Outcome**: The assistant acknowledges the transition smoothly (*"Driving licence ke baare mein bhi bata deta hoon..."*), explains that the learner's test can often be taken online on Parivahan Sewa while the permanent driving test occurs at the local RTO, and asks if they want to review the required documents.

### Use Case 3: Official Portal & Anti-Fraud Verification
- **Trigger**: A citizen mentions that an internet café operator requested ₹500 to submit an online Voter ID application.
- **System Behaviour**: The assistant references verified statutory records from the Election Commission of India knowledge base.
- **Expected Outcome**: The assistant informs the citizen that submitting Form 6 on the official ECI portal (`voters.eci.gov.in`) or the Voter Helpline App is completely **free of cost**, warns against paying unauthorized third parties, and offers to explain the direct online steps.

### Use Case 4: Simplifying Bureaucratic Document Jargon
- **Trigger**: The citizen expresses confusion over technical requirements: *"Ye 'Proof of Ordinary Residence' ka matlab kya hota hai? Mere paas koi gazetted officer ka sign nahi hai."*
- **System Behaviour**: The assistant's vernacular clarification layer translates statutory legal requirements into everyday household examples.
- **Expected Outcome**: The assistant reassures the citizen in simple Hinglish that a gazetted officer's signature is not mandatory if they have common alternatives—such as an electricity bill in their family's name, a water bill, a bank passbook, or a current rent agreement.

### Use Case 5: Polite Boundary Enforcement & Redirection
- **Trigger**: The caller asks an out-of-scope question: *"Agle mahine cricket match kaun jeetega?"* or asks for political opinions.
- **System Behaviour**: The domain guardrail detects that the query falls outside government welfare services and civic documentation.
- **Expected Outcome**: The assistant politely declines with empathy and redirects the caller back to government services: *"Main cricket ya rajneeti par charcha nahi kar sakta, lekin agar aapko Voter ID, Ration Card ya kisi sarkari yojana ke baare mein jankari chahiye, toh main zaroor madad kar sakta hoon."*

### Use Case 6: Dynamic Propagation of Updated Service Rules
- **Trigger**: A government department updates statutory rules (e.g., Parivahan introduces contactless Aadhaar-based authentication for Learner's Licences, removing the physical RTO visit requirement).
- **System Behaviour**: The administrator updates the verified knowledge base record for `LEARNERS_LICENCE_MORTH`.
- **Expected Outcome**: In all subsequent voice calls, the assistant immediately quotes the updated procedure—explaining that if their Aadhaar is linked to their mobile number, they can take the online learner's test from home without visiting the RTO.

### Use Case 7: Call Failure, Retries, and Duplicate Prevention
- **Trigger**: A simulated outbound call encounters a busy signal, network drop, or goes unanswered.
- **System Behaviour**: The call dispatcher catches the failure event, updates the call job status to `RETRY_SCHEDULED`, increments the retry counter, and checks the idempotency key.
- **Expected Outcome**: The system does not spawn a new job. It schedules a retry after an exponential back-off window (e.g., 15 minutes). If the maximum retry threshold (e.g., 2 attempts) is exceeded, the job is marked `FAILED_EXHAUSTED` and logged in the audit trail without harassing the citizen.

---

## F. End-to-End Workflow

The complete operational lifecycle of Timbre unfolds in seven clear stages:

```mermaid
flowchart TD
    A["1. Citizen Lifecycle Event\n(Synthetic profile turns 18 or is updated)"] --> B["2. Eligibility Engine Evaluation\n(Evaluates rules against citizen attributes)"]
    B --> C["3. Deduplicated Call Job Creation\n(Idempotent queue entry generated)"]
    C --> D["4. Simulated Voice Session Launch\n(Realtime Hinglish speech channel established)"]
    D --> E["5. Spoken Dialogue & Fact Retrieval\n(Conversational guidance & official links provided)"]
    E --> F["6. Session Teardown & Logging\n(Transcripts, latency, & outcomes stored)"]
    F --> G["7. Admin Telemetry Inspection\n(Audited via Flutter management console)"]
```

1. **Lifecycle Event Ingestion**: A synthetic citizen's profile reaches an eligibility milestone (e.g., age 18) either through scheduled time advancement or administrator testing.
2. **Eligibility Evaluation**: The backend rule engine matches the citizen's age, location, and existing documents against statutory scheme rules.
3. **Deduplicated Job Queuing**: A single outbound call job is scheduled with an idempotency key to prevent repeat calls.
4. **Voice Session Initialization**: The voice orchestrator opens a simulated real-time audio session configured with cultural context and domain guidelines.
5. **Interactive Spoken Guidance**: The citizen and the AI converse in Hinglish. The citizen can interrupt, ask for simpler explanations, and explore multiple schemes.
6. **Telemetry & Transcript Archiving**: When the call concludes, the audio state, text transcript, recognized intent, and resolution status are written to the audit log.
7. **Administrative Review**: Operators inspect call outcomes, review transcripts, and verify system performance via the Flutter dashboard.

---

## G. Example Conversation

The following dialogue illustrates a typical real-time conversation between Timbre and a newly eligible fictional citizen:

> **AI Assistant**: *"Namaste Aarav ji! Main Timbre se bol raha hoon, Bharat Assist automated AI government service sahayak. Aap 18 saal ke ho gaye hain, isliye main aapko badhai dene aur do zaroori sarkari dastavezon ke baare mein batane ke liye call kar raha hoon."*
>
> **Citizen (Aarav)**: *"Haan ji namaste. Kaunse dastavej?"*
>
> **AI Assistant**: *"Pehla hai aapka Voter ID card, jisse aap aane wale elections mein vote daal sakte hain. Aur doosra hai Learner's Driving Licence. Kya aap inke baare mein janna chahte hain?"*
>
> **Citizen (Aarav)**: *"Voter ID ke liye toh mujhe cyber café jana padega na? Wahan ₹300 mang rahe the."*
>
> **AI Assistant**: *"Nahi Aarav ji, cyber café par paise dene ki bilkul zaroorat nahi hai. Election Commission of India ke official portal `voters.eci.gov.in` par Form 6 bharna bilkul muft (free) hai. Aap apne phone se hi photo aur age proof upload karke apply kar sakte hain."*
>
> **Citizen (Aarav)** *(interrupting)*: *"Achha rukiye! Lekin mere paas abhi Voter ID nahi hai, toh kya main Driving Licence ke liye apply kar sakta hoon?"*
>
> **AI Assistant**: *"Ji bilkul! Driving Licence ke liye Voter ID zaroori nahi hai. Agar aapke paas Aadhaar Card hai, toh aap Parivahan portal `parivahan.gov.in` par jakar Learner's Licence ke liye online test de sakte hain. Kya aapka mobile number aapke Aadhaar se linked hai?"*
>
> **Citizen (Aarav)**: *"Haan, linked hai."*
>
> **AI Assistant**: *"Tab toh bohot aasan hai. Aap bina RTO jaye ghar baithe online Learner's Licence test de sakte hain. Iski sarkari fees lagbhag ₹150 se ₹200 hoti hai jo directly portal par pay hoti hai. Kya main aapke phone par in dono official websites ke links bhej doon?"*
>
> **Citizen (Aarav)**: *"Haan, bhej dijiye. Bohot shukriya aapka!"*
>
> **AI Assistant**: *"Aapka swagat hai Aarav ji. Kisi bhi anjaan vyakti ko extra paise na dein. Shubh din!"*

---

## H. Prototype Boundaries & Responsible AI

To ensure ethical design, transparency, and safety, Timbre operates under explicit structural constraints:

- **100% Synthetic Records**: The system uses only generated fictional citizen profiles. It does not store, process, or link to real citizen Personally Identifiable Information (PII).
- **Simulated Outbound Calls**: All calls are simulated within a local test harness or in-app dashboard player. The system does not dial live telephone numbers on the public switched telephone network (PSTN).
- **No National Database Access**: Timbre does not possess integration, access credentials, or connections to UIDAI Aadhaar, the National Population Register, or state databases.
- **Independent Proof of Concept**: This project is an independent architectural prototype. It is **not** an official government service, is not endorsed by the Government of India, and is not affiliated with any ministry.
- **Transparent AI Identity**: The voice assistant identifies itself as an automated AI system in its opening sentence to prevent caller confusion.
- **Future Production Prerequisites**: Any eventual deployment over actual telecom networks will mandate explicit citizen opt-in consent, integration with authorized Telecom Commercial Communications Customer Preference Regulations (TCCCPR) DND registries, and formal statutory approvals.

---

## I. Project Roadmap

```mermaid
flowchart LR
    P1["Phase 1\nFrontend & Dashboard Milestone (Done)"] --> P2["Phase 2\nBackend & Local LLM Integration"]
    P2 --> P3["Phase 3\nJoint Contract & Telemetry Validation"]
    P3 --> P4["Phase 4\nPublic Scaling & Regional Languages"]
```

### Phase 1: Frontend & Administration Milestone (Completed on MacBook Air M5)
- [x] Product vision and conversational architecture ([`README.md`](README.md)).
- [x] Technical architecture, database schemas, and API design specifications ([`TECH.md`](TECH.md)).
- [x] Frontend architecture and engineering guide ([`FRONTEND.md`](FRONTEND.md)).
- [x] Flutter application scaffolding under `frontend/` targeting macOS Desktop and Chrome.
- [x] Administrative dashboard layout with NavigationRail and Material 3 accessible theme.
- [x] Fictional citizen registry and detailed profile sheet (`frontend/lib/screens/citizens/`).
- [x] Interactive milestone life-event simulator (crossing age 18 threshold) (`frontend/lib/screens/simulation/`).
- [x] Scheme eligibility engine display (Voter ID Form 6, Parivahan Licence, PM-JAY) (`frontend/lib/screens/eligibility/`).
- [x] Simulated outbound-call queue monitor with idempotency key tracking and Hinglish transcript inspector (`frontend/lib/screens/calls/`).
- [x] Backend connectivity health indicator and dynamic host URL configuration (`frontend/lib/widgets/backend_health_pill.dart`).
- [x] Automated unit and widget test suite with 100% pass rate (`flutter test`).

### Phase 2: Backend & Voice AI Integration (In Progress on ASUS TUF)
- [ ] Python / FastAPI REST and WebSocket API gateway (`backend/`).
- [ ] Local LLM integration using Ollama and Qwen for Hinglish conversational turn generation.
- [ ] Voice pipeline integration using Bolna.ai for speech-to-speech interaction.
- [ ] Relational persistence and schema migrations in PostgreSQL / Supabase.
- [ ] Backend unit and integration test suite.

### Phase 3: Contract Alignment, Integration & Observability
- [ ] Codex coordination and validation of shared REST and WebSocket API contracts.
- [ ] End-to-end integration tests between MacBook frontend and ASUS backend.
- [ ] Real-time audio stream bridging and latency benchmarking.
- [ ] Conversational safety evaluations (anti-hallucination guardrails, boundary enforcement).

### Phase 4: Future Telecom & Public Scale
- [ ] Integration with Government of India's Project Bhashini for 22 scheduled regional languages.
- [ ] Inbound citizen helpline capabilities.
- [ ] Authorized Indian CPaaS telephony integration with TRAI/DoT regulatory compliance.
- [ ] Post-call automated SMS / WhatsApp dispatches containing official portal links.

---

## J. Project Status and Contribution

### Current Repository Status
Timbre's **Frontend Milestone 1** is fully implemented and verifiable in the `frontend/` directory on the `macbook-agy` branch. It runs completely standalone in local demo mode using synthetic data without requiring the backend server. The backend stack (FastAPI, Ollama/Qwen, Bolna.ai) is currently under active development on the ASUS TUF laptop. Controlled integration and merging into `main` will be coordinated via Codex once backend endpoints and shared contracts are confirmed.

### How to Run the Frontend Locally
```bash
# Clone the repository and navigate to the frontend directory
cd frontend

# Install Flutter dependencies
flutter pub get

# Run the test suite
flutter test

# Launch the administrative dashboard on macOS Desktop
flutter run -d macos

# Or launch in Google Chrome
flutter run -d chrome
```

### Licensing
No license has been selected yet for this repository. All rights are reserved pending licensing determination. A formal license file will be added to the repository root once an open-source or permissive license is selected.

---

*For technical architecture, data schemas, and API specifications, continue to [TECH.md](TECH.md).*
