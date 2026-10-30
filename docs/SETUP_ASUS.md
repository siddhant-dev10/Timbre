# Timbre ASUS TUF Server Setup & Deployment Guide

> **Arch Linux Development Server & Local AI Machine Configuration**

This guide details the complete procedure for setting up, running, testing, and networking the Timbre backend on the ASUS TUF F15 development server running Arch Linux.

---

## 1. Hardware & System Profile

- **Device**: ASUS TUF Gaming F15 (FX506HF)
- **OS**: Arch Linux (Kernel 6.13+ x86_64)
- **CPU**: 11th Gen Intel® Core™ i5-11400H @ 2.70GHz (6 Cores / 12 Threads)
- **GPU**: NVIDIA GeForce RTX 2050 Mobile (4 GB GDDR6 VRAM, CUDA compute capability 8.6)
- **RAM**: 16 GB DDR4
- **Local Wi-Fi LAN IP**: `10.32.72.23` (Dynamically assigned; discover via `ip -br -4 addr show wlp45s0`)

---

## 2. Prerequisites & System Packages

Ensure the required system packages are present:
```bash
sudo pacman -S python git uvicorn
```

Verify NVIDIA driver and CUDA support:
```bash
nvidia-smi
```

---

## 3. Virtual Environment & Dependencies

Navigate to the repository backend directory and create a dedicated virtual environment:
```bash
cd /home/siddhant/Timbre/backend
python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
```

---

## 4. Environment Configuration

Copy the example environment configuration:
```bash
cp .env.example .env
```

Review key configuration variables in `.env`:
```ini
HOST=0.0.0.0
PORT=8000
ALLOWED_ORIGINS=http://localhost:3000,http://localhost:8080,http://127.0.0.1:3000,http://127.0.0.1:8080,app://*,http://192.168.0.123:8000
DATABASE_URL=sqlite:///./data/timbre.db
REFERENCE_DATE=2026-10-28
OLLAMA_BASE_URL=http://127.0.0.1:11434
OLLAMA_MODEL=qwen3.5:9b
OLLAMA_NUM_CTX=4096
BOLNA_BASE_URL=https://api.bolna.ai
BOLNA_API_KEY=
BOLNA_AGENT_ID=
ENABLE_REAL_CALLS=false

# ElevenLabs Text-to-Speech (Custom Timbre Voice)
ELEVENLABS_BASE_URL=https://api.elevenlabs.io
ELEVENLABS_API_KEY=
ELEVENLABS_VOICE_ID=
ELEVENLABS_TTS_MODEL_ID=eleven_multilingual_v2
ELEVENLABS_TIMEOUT_SECONDS=30.0
```

---

## 5. Dataset Generation & Database Seeding

1. **Generate the 100 Fictional Citizens**:
   Produces both `data/demo/Timbre_Fake_Citizens.csv` and formatted Excel workbook `data/demo/Timbre_Fake_Citizens.xlsx`:
   ```bash
   source .venv/bin/activate
   python app/scripts/generate_citizens.py
   ```

2. **Idempotently Seed SQLite Database**:
   Populates `citizens` and `services` tables:
   ```bash
   python app/scripts/seed_db.py
   ```

Running the seed script multiple times safely updates records without creating duplicates.

---

## 6. Local LLM (Ollama) Setup

Ollama runs locally as a systemd service listening on `127.0.0.1:11434`.

1. Verify Ollama status:
   ```bash
   systemctl status ollama
   ollama list
   ```

2. Ensure the Qwen model is available:
   ```bash
   ollama list | grep qwen
   ```

3. Test prompt generation:
   ```bash
   curl -X POST http://127.0.0.1:11434/api/generate \
     -H "Content-Type: application/json" \
     -d '{"model": "qwen3.5:9b", "prompt": "Namaste", "stream": false}'
   ```

---

## 7. Starting and Stopping the FastAPI Backend

### Foreground Interactive Mode
Launch the backend with live reloading:
```bash
cd /home/siddhant/Timbre/backend
source .venv/bin/activate
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```
To stop the server, press `Ctrl + C`.

### Background Mode
Run the backend in the background:
```bash
cd /home/siddhant/Timbre/backend
source .venv/bin/activate
nohup uvicorn app.main:app --host 0.0.0.0 --port 8000 > /tmp/timbre_backend.log 2>&1 &
echo $! > /tmp/timbre_backend.pid
```
To stop the background server:
```bash
kill $(cat /tmp/timbre_backend.pid) && rm /tmp/timbre_backend.pid
# Or by port:
fuser -k 8000/tcp
```

### Rediscovering ASUS LAN IP
If your Wi-Fi router assigns a different DHCP address to the ASUS:
```bash
ip -br -4 addr show wlp45s0
```
Update the MacBook frontend or environment with the new IP address.

---

## 8. ElevenLabs Text-to-Speech Integration

Timbre uses **ElevenLabs** to synthesize spoken responses using your custom **Timbre** voice, while **Qwen 3.5 9B** runs locally via Ollama to generate all conversational reasoning.

### Secure Credentials Setup
Open `.env` in a local terminal editor:
```bash
nano /home/siddhant/Timbre/backend/.env
```
Add your credentials:
```ini
ELEVENLABS_API_KEY=your_actual_elevenlabs_api_key_here
ELEVENLABS_VOICE_ID=your_custom_timbre_voice_id_here
ELEVENLABS_TTS_MODEL_ID=eleven_multilingual_v2
```
Save and exit (`Ctrl + O`, `Enter`, `Ctrl + X`).

> [!IMPORTANT]
> - Never paste API keys into public chat, logs, or commit history.
> - `.env` is Git-ignored by default.
> - The free plan provides 10,000 characters per month. Use `eleven_multilingual_v2` for high-quality Hinglish synthesis.

### Verifying Voice Status
Check health via curl:
```bash
curl -s http://127.0.0.1:8000/api/v1/voice/status | jq
```

---

## 9. Connecting from the MacBook Air M5

The Flutter administrative client running on your MacBook Air connects over the local Wi-Fi network:

- **ASUS LAN Server Endpoint**: `http://10.32.72.23:8000/api/v1` (or current LAN IP)
- **Swagger Documentation**: `http://10.32.72.23:8000/docs`
- **Health Check**: `http://10.32.72.23:8000/health`

### Testing Connection from macOS Terminal
```bash
curl http://10.32.72.23:8000/health
```

---

## 9. Running Automated Tests

Run the full pytest suite with isolated test fixtures:
```bash
cd /home/siddhant/Timbre/backend
source .venv/bin/activate
pytest tests/ -v
```

All external services (Ollama and Bolna.ai) are mocked during automated tests. Tests never initiate real outbound calls.

---

## 10. Call Safety Controls

- `ENABLE_REAL_CALLS` defaults to `false`.
- Fictional citizen records (`CIT-0001` through `CIT-0100` with placeholders `DEMO-PHONE-xxxx`) are strictly blocked from being dialed.
- Any live test call requires:
  1. `ENABLE_REAL_CALLS=true` in `.env`
  2. Explicit `is_real_call=true` in request payload
  3. Explicit `consent_confirmed=true`
  4. A real, consenting team member's phone number provided at runtime.
