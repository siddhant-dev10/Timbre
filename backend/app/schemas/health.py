from typing import Dict, Any, Optional
from pydantic import BaseModel


class ComponentHealth(BaseModel):
    status: str  # healthy, degraded, unavailable
    details: Optional[str] = None


class HealthResponse(BaseModel):
    status: str  # ok, degraded, error
    version: str = "1.0.0"
    mode: str = "demo"
    database: ComponentHealth
    local_llm: ComponentHealth
    bolna_voice: ComponentHealth
    real_calls_enabled: bool = False
