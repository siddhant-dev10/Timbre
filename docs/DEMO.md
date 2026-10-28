# Timbre End-to-End Demonstration Script

> **Step-by-Step Prototype Evaluation Walkthrough for Buildathon Evaluators**

This guide provides a structured walkthrough demonstrating the capabilities of Timbre, connecting the Flutter administrative cockpit on macOS to the local AI backend running on the ASUS TUF F15 (Arch Linux).

---

## Pre-Flight Check

1. **Verify Backend Health & Network**:
   ```bash
   curl http://10.32.72.23:8000/health
   ```
   Ensure `status` is `ok`, `database` is `healthy`, and `local_llm` shows `healthy` with the local Qwen model.

2. **Open the Flutter Dashboard**:
   On your MacBook, launch the Timbre application:
   ```bash
   cd frontend && flutter run -d macos
   ```
   Confirm the **Backend Health Pill** in the top navigation bar displays `Connected [10.32.72.23:8000]`.

---

## Demonstration Workflow

### Step 1: Synthetic Citizen Inspection
- Navigate to the **Citizens** screen in the Flutter UI.
- Verify that **100 fictional citizen records** are loaded.
- Inspect citizen `CIT-0001` (Aarav Sharma):
  - Notice the visible `is_fictional = true` badge.
  - Notice the synthetic phone number placeholder (`DEMO-PHONE-0001`).
  - Notice the declared age (17) as of reference date `2026-10-28`.

### Step 2: Triggering a Life Event Simulation
- In the citizen details drawer or row action, click **"Simulate 18th Birthday"** (or dispatch `POST /api/simulations` with `MILESTONE_AGE_18`).
- Observe the immediate age recalculation:
  - Age updates deterministically from `17` to `18`.
  - The milestone indicator `MILESTONE_AGE_18` appears.

### Step 3: Rule Engine Evaluation
- The backend deterministic rule engine evaluates the citizen's updated profile against the statutory service catalogue:
  - **ECI Voter ID Registration (Form 6)**: Status changes from `INELIGIBLE` $\rightarrow$ `POTENTIALLY_ELIGIBLE`.
  - **MoRTH Learner's Driving Licence (Parivahan)**: Evaluated as `POTENTIALLY_ELIGIBLE`.
- Review the qualification reasons and the list of commonly required statutory documents (Proof of Age, Address, Photograph).
- Notice the prominent statutory disclaimer: preliminary guidance only.

### Step 4: Local LLM Natural Reasoning (Hinglish)
- In the **Chat / Assistant** tab, ask:
  *"Mujhe Voter ID card ke liye kaise apply karna hoga?"*
- The local Qwen model reasons over the retrieved official catalogue context and answers in natural Hinglish:
  - Explains the online Form 6 procedure.
  - Cites the official portal URL (`https://voters.eci.gov.in/`).
  - Confirms the zero statutory fee.

### Step 5: Simulated Outbound Voice Call & Telemetry
- Trigger a simulated outbound call for citizen `CIT-0001`.
- Navigate to the **Call Monitor** screen.
- Observe the pipeline status transition:
  `QUEUED` $\rightarrow$ `IN_PROGRESS` $\rightarrow$ `COMPLETED`.
- Inspect the interactive **Transcript Viewer**:
  - Color-coded chat bubbles showing bidirectional Hinglish dialogue.
  - Simulated latency metrics (e.g., 320ms, 280ms) and voice activity timestamps.

### Step 6: Safety Invariant Verification
- Confirm that no real telephone calls are ever made during the demo (`ENABLE_REAL_CALLS=false`).
- Confirm that attempting to dispatch a live telecom call to a fictional citizen (`CIT-*`) is strictly blocked with `HTTP 403 Forbidden`.
