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
- **Local Wi-Fi LAN IP**: `10.32.72.23`

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
ALLOWED_ORIGINS=http://localhost:3000,http://localhost:8080,http://127.0.0.1:3000,http://127.0.0.1:8080,app://*,http://10.32.72.23:8000
DATABASE_URL=sqlite:///./data/timbre.db
REFERENCE_DATE=2026-10-28
OLLAMA_BASE_URL=http://127.0.0.1:11434
OLLAMA_MODEL=qwen3.5:9b
OLLAMA_NUM_CTX=4096
BOLNA_BASE_URL=https://api.bolna.ai
BOLNA_API_KEY=
BOLNA_AGENT_ID=
ENABLE_REAL_CALLS=false
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

## 7. Starting the FastAPI Backend

Launch the backend with live reloading:
```bash
cd /home/siddhant/Timbre/backend
source .venv/bin/activate
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

The server binds to `0.0.0.0:8000` to allow access from other devices on your local network.

---

## 8. Connecting from the MacBook Air M5

The Flutter administrative client running on your MacBook Air connects over the local Wi-Fi network:

- **ASUS LAN Server Endpoint**: `http://10.32.72.23:8000/api/v1`
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
