from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from sqlalchemy import text
from app.database.session import get_db
from app.services.llm_service import llm_service
from app.services.bolna_service import bolna_service
from app.services.elevenlabs_service import elevenlabs_service
from app.schemas.health import HealthResponse, ComponentHealth
from app.config import settings

router = APIRouter(tags=["Health & Status"])


@router.get("/health", response_model=HealthResponse)
async def get_health(
    check_connectivity: bool = Query(
        default=False,
        description="When true, performs live zero-cost authentication/connectivity checks with NVIDIA and ElevenLabs."
    ),
    db: Session = Depends(get_db)
):
    # 1. Database check
    db_status = "healthy"
    db_details = "SQLite connected"
    try:
        db.execute(text("SELECT 1"))
    except Exception as e:
        db_status = "unavailable"
        db_details = str(e)

    # 2. Cloud AI provider configuration and optional live connectivity check
    llm_info = await llm_service.check_availability(check_connectivity=check_connectivity)
    llm_status = llm_info.get("status", "unavailable")
    llm_details = llm_info.get("details") or (
        f"Provider: {llm_info.get('provider')}, model: {llm_info.get('model')}; "
        "credentials/configuration only, provider connectivity not checked"
    )

    # 3. Bolna Voice check (telephony provider for live PSTN calling)
    bolna_info = bolna_service.check_health()
    bolna_status = "healthy" if bolna_info.get("configured") else "demo_simulation"
    bolna_details = (
        f"Configured: {bolna_info.get('configured')}, "
        f"Real Calls Enabled: {bolna_info.get('real_calls_enabled')}"
    )
    if check_connectivity and bolna_info.get("api_key_set"):
        bolna_conn = await bolna_service.verify_connectivity()
        if bolna_conn.get("api_key_valid"):
            bolna_details = (
                f"API Key: Valid (Authenticated), Agent ID Configured: {bolna_info.get('configured')}, "
                f"Real Calls Enabled: {bolna_info.get('real_calls_enabled')}"
            )
        else:
            bolna_details = (
                f"API Key: Failed ({bolna_conn.get('details')}), Agent ID Configured: {bolna_info.get('configured')}, "
                f"Real Calls Enabled: {bolna_info.get('real_calls_enabled')}"
            )

    # 4. ElevenLabs Voice Synthesis check and optional live connectivity check
    elevenlabs_info = await elevenlabs_service.check_health_async(check_connectivity=check_connectivity)
    elevenlabs_status = elevenlabs_info.get("status", "unavailable")
    elevenlabs_details = elevenlabs_info.get("details") or (
        f"Provider: ElevenLabs, Custom Voice: Timbre, "
        f"Configured: {elevenlabs_info.get('configured')}, connectivity not checked, "
        f"Model: {elevenlabs_info.get('model_id')}"
    )

    overall_status = "ok"
    if db_status != "healthy":
        overall_status = "error"
    elif llm_status != "healthy" or elevenlabs_status != "healthy":
        overall_status = "degraded"

    return HealthResponse(
        status=overall_status,
        version="1.0.0",
        mode="live" if settings.ENABLE_REAL_CALLS else "demo",
        database=ComponentHealth(status=db_status, details=db_details),
        ai_provider=ComponentHealth(status=llm_status, details=llm_details),
        bolna_voice=ComponentHealth(status=bolna_status, details=bolna_details),
        elevenlabs_tts=ComponentHealth(status=elevenlabs_status, details=elevenlabs_details),
        real_calls_enabled=settings.ENABLE_REAL_CALLS,
        bolna_test_call_ready=bolna_info.get("test_call_ready", False),
    )
