import json
import uuid
from datetime import date, datetime, timezone
from typing import Dict, Any, Optional, List
from sqlalchemy.orm import Session
from app.config import settings
from app.models.citizen import Citizen
from app.models.simulation import SimulationRecord
from app.services.rules_engine import calculate_age, evaluate_all_services
from app.services.profile_context import minimal_profile_context
from app.services.llm_service import llm_service
from app.schemas.simulation import SimulationResponse
from app.schemas.service_scheme import ServiceSchemeResponse, EligibilityResult


async def execute_citizen_simulation(
    citizen_id: str,
    trigger_event: str,
    target_dob: Optional[date],
    db: Session
) -> SimulationResponse:
    citizen = db.query(Citizen).filter(Citizen.id == citizen_id).first()
    if not citizen:
        raise ValueError(f"Citizen with ID '{citizen_id}' not found.")

    ref_date = settings.parsed_reference_date
    previous_dob = citizen.date_of_birth
    previous_age = citizen.age

    # Recalculate DOB and age if event triggers an age transition
    new_dob = target_dob or previous_dob
    if trigger_event == "MILESTONE_AGE_18":
        # Simulate turning 18 on reference date
        new_dob = date(ref_date.year - 18, ref_date.month, ref_date.day)
    elif trigger_event == "SENIOR_CITIZEN_60":
        new_dob = date(ref_date.year - 60, ref_date.month, ref_date.day)

    new_age = calculate_age(new_dob, ref_date)

    # Prepare citizen snapshot for rules evaluation
    citizen_snapshot = {
        "id": citizen.id,
        "first_name": citizen.first_name,
        "last_name": citizen.last_name,
        "date_of_birth": new_dob,
        "age": new_age,
        "gender": citizen.gender,
        "state": citizen.state,
        "district": citizen.district,
        "rural_or_urban": citizen.rural_or_urban,
        "simulated_income_bracket": citizen.simulated_income_bracket,
        "is_student": citizen.is_student or (trigger_event in ("STARTING_COLLEGE", "SCHOLARSHIP_EXPLORATION")),
        "is_farmer": citizen.is_farmer or (trigger_event == "FARMER_SUPPORT"),
        "is_senior_citizen": citizen.is_senior_citizen or (new_age >= 60),
        "occupation": citizen.occupation,
        "simulated_life_event": trigger_event,
        "children": citizen.children
    }

    # Deterministic rule engine evaluation
    detailed_results = evaluate_all_services(citizen_snapshot, ref_date)
    eligible_schemes = [res.service for res in detailed_results if res.is_eligible]

    preliminary_notes = (
        f"Simulated event '{trigger_event}' updated age from {previous_age} to {new_age}. "
        f"Identified {len(eligible_schemes)} catalogue-rule matches for preliminary review."
    )

    # Local LLM explanation grounded in catalogue results
    llm_explanation = ""
    prompt = (
        f"A synthetic demo profile has a simulated event '{trigger_event}'. "
        f"The deterministic local rules produced {len(eligible_schemes)} preliminary catalogue matches. "
        "Explain briefly in polite Hinglish that these are not official decisions and identify only "
        "the next verification step supported by the catalogue. Do not invent schemes or details."
    )

    llm_res = await llm_service.generate_response(
        prompt=prompt,
        system_prompt=(
            llm_service.build_grounded_system_prompt([s.model_dump() for s in eligible_schemes], language="Hinglish")
            + "\n\n" + minimal_profile_context(citizen_snapshot, ref_date)
        )
    )

    if llm_res.get("success"):
        llm_explanation = llm_res.get("response", "")
    else:
        llm_explanation = (
            "AI explanation is temporarily unavailable. Local rule matches are preliminary only; "
            "please verify each result on its official source before acting."
        )

    # Persist simulation history
    sim_id = str(uuid.uuid4())
    record = SimulationRecord(
        id=sim_id,
        citizen_id=citizen.id,
        trigger_event=trigger_event,
        previous_age=previous_age,
        calculated_age=new_age,
        previous_dob=previous_dob,
        simulated_dob=new_dob,
        eligible_services=json.dumps([s.model_dump() for s in eligible_schemes]),
        preliminary_notes=preliminary_notes,
        llm_explanation=llm_explanation,
        created_at=datetime.now(timezone.utc)
    )
    db.add(record)
    
    # Update citizen record in demo database
    citizen.date_of_birth = new_dob
    citizen.age = new_age
    citizen.simulated_life_event = trigger_event
    db.commit()

    return SimulationResponse(
        id=sim_id,
        citizen_id=citizen.id,
        citizen_name=citizen.name,
        trigger_event=trigger_event,
        previous_age=previous_age,
        calculated_age=new_age,
        previous_dob=previous_dob.isoformat(),
        simulated_dob=new_dob.isoformat(),
        eligible_services=eligible_schemes,
        detailed_results=detailed_results,
        preliminary_notes=preliminary_notes,
        llm_explanation=llm_explanation,
        created_at=datetime.now(timezone.utc).isoformat()
    )
