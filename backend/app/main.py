from contextlib import asynccontextmanager
from pathlib import Path
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.config import settings
from app.database.session import engine, SessionLocal
from app.database.base import Base
from app.models.citizen import Citizen
from app.scripts.seed_db import seed_database
from app.api import health, citizens, services, chat, simulations, calls, webhooks


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: Create tables and auto-seed if empty
    Base.metadata.create_all(bind=engine)
    session = SessionLocal()
    try:
        citizen_count = session.query(Citizen).count()
        if citizen_count == 0:
            csv_path = Path(__file__).resolve().parent.parent.parent / "data" / "demo" / "Timbre_Fake_Citizens.csv"
            if csv_path.exists():
                seed_database(csv_path=csv_path, db_session=session)
    finally:
        session.close()
    yield
    # Shutdown logic if needed


app = FastAPI(
    title="Timbre — AI-Powered Indian Government-Services Voice Assistant",
    description="Development and buildathon backend for citizen simulations, statutory eligibility reasoning, Ollama Qwen inference, and Bolna voice integration.",
    version="1.0.0",
    lifespan=lifespan
)

# CORS Configuration for Flutter desktop and web
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_origin_regex=r"^https?://(localhost|127\.0\.0\.1|10\.\d+\.\d+\.\d+|192\.168\.\d+\.\d+)(:\d+)?$",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount Health router at root
app.include_router(health.router)

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


@app.get("/")
def root():
    return {
        "project": "Timbre",
        "description": "AI-Powered Indian Government Services Voice Assistant Backend",
        "version": "1.0.0",
        "status": "online",
        "docs_url": "/docs",
        "health_url": "/health",
        "demo_mode": not settings.ENABLE_REAL_CALLS
    }
