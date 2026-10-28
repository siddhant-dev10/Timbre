from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import text
from app.database.session import get_db
from app.services.llm_service import llm_service
from app.services.bolna_service import bolna_service
from app.schemas.health import HealthResponse, ComponentHealth
from app.config import settings

router = APIRouter(tags=["Health & Status"])


@router.get("/health", response_model=HealthResponse)
async def get_health(db: Session = Depends(get_db)):
    # 1. Database check
    db_status = "healthy"
    db_details = "SQLite connected"
    try:
        db.execute(text("SELECT 1"))
    except Exception as e:
        db_status = "unavailable"
        db_details = str(e)

    # 2. Local LLM check
    llm_info = await llm_service.check_availability()
    llm_status = llm_info.get("status", "unavailable")
    llm_details = (
        f"Target: {llm_info.get('target_model')} "
        f"(Installed: {', '.join(llm_info.get('installed_models', [])) or 'none'})"
    )

    # 3. Bolna Voice check
    bolna_info = bolna_service.check_health()
    bolna_status = "healthy" if bolna_info.get("configured") else "demo_simulation"
    bolna_details = (
        f"Configured: {bolna_info.get('configured')}, "
        f"Real Calls Enabled: {bolna_info.get('real_calls_enabled')}"
    )

    overall_status = "ok"
    if db_status != "healthy":
        overall_status = "error"
    elif llm_status != "healthy":
        overall_status = "degraded"

    return HealthResponse(
        status=overall_status,
        version="1.0.0",
        mode="live" if settings.ENABLE_REAL_CALLS else "demo",
        database=ComponentHealth(status=db_status, details=db_details),
        local_llm=ComponentHealth(status=llm_status, details=llm_details),
        bolna_voice=ComponentHealth(status=bolna_status, details=bolna_details),
        real_calls_enabled=settings.ENABLE_REAL_CALLS
    )
