import json
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session
from app.database.session import get_db
from app.models.simulation import SimulationRecord
from app.models.citizen import Citizen
from app.schemas.simulation import SimulationRequest, SimulationResponse
from app.schemas.service_scheme import ServiceSchemeResponse, EligibilityResult
from app.services.simulation_service import execute_citizen_simulation

router = APIRouter(prefix="/simulations", tags=["Life-Event Simulations"])


def _to_simulation_response(rec: SimulationRecord, citizen: Optional[Citizen]) -> SimulationResponse:
    eligible_svcs = []
    try:
        raw_svcs = json.loads(rec.eligible_services)
        for s in raw_svcs:
            eligible_svcs.append(ServiceSchemeResponse(**s))
    except Exception:
        pass

    citizen_name = citizen.name if citizen else "Synthetic Citizen"

    return SimulationResponse(
        id=rec.id,
        citizen_id=rec.citizen_id,
        citizen_name=citizen_name,
        trigger_event=rec.trigger_event,
        previous_age=rec.previous_age,
        calculated_age=rec.calculated_age,
        previous_dob=rec.previous_dob.isoformat(),
        simulated_dob=rec.simulated_dob.isoformat(),
        eligible_services=eligible_svcs,
        detailed_results=[],
        preliminary_notes=rec.preliminary_notes,
        llm_explanation=rec.llm_explanation,
        created_at=rec.created_at.isoformat()
    )


@router.post("", response_model=SimulationResponse)
async def create_simulation(request: SimulationRequest, db: Session = Depends(get_db)):
    try:
        res = await execute_citizen_simulation(
            citizen_id=request.citizen_id,
            trigger_event=request.trigger_event,
            target_dob=request.target_dob,
            db=db
        )
        return res
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


@router.get("/{simulation_id}", response_model=SimulationResponse)
def get_simulation(simulation_id: str, db: Session = Depends(get_db)):
    rec = db.query(SimulationRecord).filter(SimulationRecord.id == simulation_id).first()
    if not rec:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Simulation '{simulation_id}' not found."
        )
    citizen = db.query(Citizen).filter(Citizen.id == rec.citizen_id).first()
    return _to_simulation_response(rec, citizen)


@router.get("", response_model=List[SimulationResponse])
def list_simulations(
    citizen_id: Optional[str] = Query(None),
    limit: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db)
):
    query = db.query(SimulationRecord)
    if citizen_id:
        query = query.filter(SimulationRecord.citizen_id == citizen_id)
    records = query.order_by(SimulationRecord.created_at.desc()).limit(limit).all()

    results = []
    for r in records:
        citizen = db.query(Citizen).filter(Citizen.id == r.citizen_id).first()
        results.append(_to_simulation_response(r, citizen))
    return results
