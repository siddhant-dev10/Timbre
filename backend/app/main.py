from contextlib import asynccontextmanager
from pathlib import Path
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import inspect, text
from app.config import settings
from app.database.session import engine, SessionLocal
from app.database.base import Base
from app.database.migrations import run_migrations
from app.models.citizen import Citizen
from app.scripts.seed_db import seed_database
from app.services.knowledge_service import knowledge_service
from app.api import health, citizens, services, chat, simulations, calls, webhooks, voice, knowledge, openai_compat, whatsapp


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Apply repeatable, backward-compatible additive migrations to existing tables
    run_migrations(engine)
    # Startup: Create tables and auto-seed if empty.
    Base.metadata.create_all(bind=engine)
    session = SessionLocal()
    try:
        citizen_count = session.query(Citizen).count()
        if citizen_count == 0:
            csv_path = Path(__file__).resolve().parent.parent.parent / "data" / "demo" / "Timbre_Fake_Citizens.csv"
            if csv_path.exists():
                seed_database(csv_path=csv_path, db_session=session)
        # Ensure statutory catalogue is indexed into knowledge base
        knowledge_service.seed_scheme_catalogue_if_empty(session)
    finally:
        session.close()
    yield
    # Shutdown logic if needed


app = FastAPI(
    title="Timbre — AI-Powered Indian Government-Services Voice Assistant",
    description="Mac-local development backend for fictional citizen simulations, statutory eligibility reasoning, NVIDIA Nemotron text generation, and ElevenLabs speech synthesis.",
    version="1.0.0",
    lifespan=lifespan
)

# CORS Configuration for Flutter desktop and web
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_origin_regex=r"^https?://(localhost|127\.0\.0\.1)(:\d+)?$",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount Health router at root
app.include_router(health.router)

# Mount OpenAI-compatible Custom LLM endpoint for Bolna telephony integration
app.include_router(openai_compat.router, prefix="/v1")
app.include_router(openai_compat.router)

# Mount WhatsApp routes at root level for flexible webhook pathing
app.include_router(whatsapp.router)

# Mount routers under /api and /api/v1 for seamless Flutter & REST client compatibility
for prefix in ["/api", "/api/v1"]:
    app.include_router(health.router, prefix=prefix)
    app.include_router(citizens.router, prefix=prefix)
    app.include_router(services.router, prefix=prefix)
    app.include_router(chat.router, prefix=prefix)
    app.include_router(simulations.router, prefix=prefix)
    app.include_router(calls.router, prefix=prefix)
    # Also support frontend convention /demo/calls
    app.include_router(calls.router, prefix=f"{prefix}/demo")
    app.include_router(webhooks.router, prefix=prefix)
    app.include_router(voice.router, prefix=prefix)
    app.include_router(knowledge.router, prefix=prefix)
    app.include_router(openai_compat.router, prefix=prefix)
    app.include_router(whatsapp.router, prefix=prefix)


@app.get("/")
def root():
    return {
        "project": "Timbre",
        "description": "AI-Powered Indian Government Services Assistant Backend",
        "version": "1.0.0",
        "status": "online",
        "docs_url": "/docs",
        "health_url": "/health",
        "demo_mode": not settings.ENABLE_REAL_CALLS,
        "whatsapp_mvp": "active",
    }
