import csv
import io
import json
import uuid
from datetime import date, datetime, timezone
from typing import Optional, List
from fastapi import APIRouter, Depends, HTTPException, Query, status, UploadFile, File
from sqlalchemy.orm import Session
from sqlalchemy import or_, and_
from app.database.session import get_db
from app.models.citizen import Citizen
from app.schemas.citizen import (
    CitizenResponse,
    CitizenListResponse,
    CitizenUpdate,
    CitizenDobPatchResponse,
    CitizenBase,
)
from app.schemas.service_scheme import CitizenEvaluationResponse
from app.services.rules_engine import calculate_age, evaluate_all_services
from app.config import settings

router = APIRouter(prefix="/citizens", tags=["Citizens"])


def _to_response_model(c: Citizen) -> CitizenResponse:
    pot_services = []
    try:
        pot_services = json.loads(c.potentially_relevant_services)
    except Exception:
        pass

    req_docs = []
    try:
        req_docs = json.loads(c.required_documents)
    except Exception:
        pass

    return CitizenResponse(
        id=c.id,
        first_name=c.first_name,
        last_name=c.last_name,
        name=c.name,
        date_of_birth=c.date_of_birth.isoformat(),
        age=c.age,
        gender=c.gender,
        state=c.state,
        district=c.district,
        city_or_village=c.city_or_village,
        rural_or_urban=c.rural_or_urban,
        preferred_language=c.preferred_language,
        education=c.education,
        occupation=c.occupation,
        employment_status=c.employment_status,
        synthetic_family_income=c.synthetic_family_income,
        simulated_income_bracket=c.simulated_income_bracket,
        family_size=c.family_size,
        marital_status=c.marital_status,
        children=c.children,
        is_student=c.is_student,
        is_farmer=c.is_farmer,
        is_senior_citizen=c.is_senior_citizen,
        simulated_life_event=c.simulated_life_event,
        potentially_relevant_services=pot_services,
        eligibility_notes=c.eligibility_notes,
        required_documents=req_docs,
        demo_only=c.demo_only,
        is_fictional=(c.record_source or "synthetic") == "synthetic",
        phone_number=c.phone_number,
        email=c.email,
        pincode=c.pincode,
        record_source=c.record_source or "synthetic",
        archived_at=c.archived_at,
        created_at=c.created_at,
        updated_at=c.updated_at
    )


@router.get("", response_model=CitizenListResponse)
def get_citizens(
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    q: Optional[str] = Query(None, description="Search by name, district, or state"),
    age: Optional[int] = Query(None, description="Filter by exact age"),
    include_archived: bool = Query(False),
    archived_only: bool = Query(False),
    sort_by: str = Query("id", pattern="^(id|name|age|state|created_at)$"),
    sort_order: str = Query("asc", pattern="^(asc|desc)$"),
    db: Session = Depends(get_db)
):
    query = db.query(Citizen)
    if archived_only:
        query = query.filter(Citizen.archived_at.is_not(None))
    elif not include_archived:
        query = query.filter(Citizen.archived_at.is_(None))
    if q:
        search_filter = f"%{q}%"
        query = query.filter(
            or_(
                Citizen.name.ilike(search_filter),
                Citizen.state.ilike(search_filter),
                Citizen.district.ilike(search_filter),
                Citizen.city_or_village.ilike(search_filter),
                Citizen.phone_number.ilike(search_filter),
                Citizen.email.ilike(search_filter)
            )
        )
    if age is not None:
        query = query.filter(Citizen.age == age)

    total = query.count()
    sort_column = getattr(Citizen, sort_by)
    sort_column = sort_column.desc() if sort_order == "desc" else sort_column.asc()
    records = query.order_by(sort_column, Citizen.id).offset(offset).limit(limit).all()

    return CitizenListResponse(
        total=total,
        limit=limit,
        offset=offset,
        citizens=[_to_response_model(c) for c in records]
    )


@router.post("", response_model=CitizenResponse, status_code=status.HTTP_201_CREATED)
def create_citizen(payload: CitizenBase, db: Session = Depends(get_db)):
    values = payload.model_dump()
    values["id"] = f"REC-{uuid.uuid4().hex[:12].upper()}"
    values["age"] = calculate_age(payload.date_of_birth, settings.parsed_reference_date)
    values["name"] = f"{payload.first_name.strip()} {payload.last_name.strip()}"
    values["demo_only"] = payload.record_source == "synthetic"
    values["is_senior_citizen"] = values["age"] >= 60 if not payload.is_senior_citizen else True
    values["potentially_relevant_services"] = json.dumps(payload.potentially_relevant_services)
    values["required_documents"] = json.dumps(payload.required_documents)
    record = Citizen(**values)
    db.add(record)
    try:
        db.commit()
    except Exception as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail="Record could not be created; check duplicate identifiers and field values.") from exc
    db.refresh(record)
    return _to_response_model(record)


@router.get("/export")
def export_citizens(format: str = Query("json", pattern="^(json|csv)$"), db: Session = Depends(get_db)):
    records = db.query(Citizen).filter(Citizen.archived_at.is_(None)).order_by(Citizen.id).all()
    rows = [ _to_response_model(record).model_dump(mode="json") for record in records ]
    if format == "json":
        return {"count": len(rows), "citizens": rows}
    output = io.StringIO()
    fields = list(rows[0].keys()) if rows else ["id", "first_name", "last_name", "date_of_birth", "state", "district", "city_or_village"]
    writer = csv.DictWriter(output, fieldnames=fields)
    writer.writeheader()
    for row in rows:
        row["potentially_relevant_services"] = json.dumps(row["potentially_relevant_services"], ensure_ascii=False)
        row["required_documents"] = json.dumps(row["required_documents"], ensure_ascii=False)
        writer.writerow(row)
    from fastapi.responses import Response
    return Response(output.getvalue(), media_type="text/csv; charset=utf-8", headers={"Content-Disposition": "attachment; filename=timbre-records.csv"})


@router.post("/import")
async def import_citizens(file: UploadFile = File(...), db: Session = Depends(get_db)):
    """Validate a whole CSV/JSON batch before committing it atomically."""
    content = await file.read(5_000_001)
    if len(content) > 5_000_000:
        raise HTTPException(status_code=413, detail="Import is limited to 5 MB.")
    try:
        decoded = content.decode("utf-8-sig")
        if (file.filename or "").lower().endswith(".json") or (file.content_type or "").endswith("json"):
            rows = json.loads(decoded)
            if isinstance(rows, dict):
                rows = rows.get("citizens", rows.get("records"))
        else:
            rows = list(csv.DictReader(io.StringIO(decoded)))
        if not isinstance(rows, list):
            raise ValueError("Expected a list of records or CSV rows.")
    except (UnicodeDecodeError, json.JSONDecodeError, ValueError) as exc:
        raise HTTPException(status_code=422, detail=f"Could not parse import file: {exc}") from exc
    if not rows or len(rows) > 5000:
        raise HTTPException(status_code=422, detail="Import must contain between 1 and 5000 records.")
    required = {"first_name", "last_name", "date_of_birth", "state", "district", "city_or_village"}
    errors, normalized, seen_ids, seen_identities = [], [], set(), set()
    for index, row in enumerate(rows, 1):
        if not isinstance(row, dict):
            errors.append({"row": index, "error": "record must be an object"})
            continue
        missing = sorted(key for key in required if row.get(key) in (None, ""))
        if missing:
            errors.append({"row": index, "missing_fields": missing})
            continue
        try:
            row = {k: v for k, v in row.items() if k in CitizenBase.model_fields}
            for key in ("potentially_relevant_services", "required_documents"):
                if isinstance(row.get(key), str):
                    row[key] = json.loads(row[key])
            payload = CitizenBase.model_validate(row)
            rid = str(rows[index - 1].get("id") or f"IMP-{uuid.uuid4().hex[:12].upper()}")
            if rid in seen_ids or db.query(Citizen.id).filter(Citizen.id == rid).first():
                errors.append({"row": index, "duplicate_id": rid})
                continue
            identity = (payload.first_name.strip().casefold(), payload.last_name.strip().casefold(), payload.date_of_birth)
            if identity in seen_identities or db.query(Citizen.id).filter(
                and_(Citizen.first_name.ilike(payload.first_name.strip()), Citizen.last_name.ilike(payload.last_name.strip()), Citizen.date_of_birth == payload.date_of_birth)
            ).first():
                errors.append({"row": index, "error": "duplicate record identity (name and date of birth)"})
                continue
            seen_ids.add(rid)
            seen_identities.add(identity)
            values = payload.model_dump()
            values.update(id=rid, name=f"{payload.first_name.strip()} {payload.last_name.strip()}", age=calculate_age(payload.date_of_birth, settings.parsed_reference_date), demo_only=payload.record_source == "synthetic", potentially_relevant_services=json.dumps(payload.potentially_relevant_services), required_documents=json.dumps(payload.required_documents))
            normalized.append(Citizen(**values))
        except Exception as exc:
            # Avoid echoing rejected row values (which may contain contact data).
            errors.append({"row": index, "error": "invalid field value or format"})
    if errors:
        return {"imported": 0, "rejected": len(errors), "errors": errors, "committed": False}
    try:
        db.add_all(normalized)
        db.commit()
    except Exception as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail="Import transaction failed; no records were saved.") from exc
    return {"imported": len(normalized), "rejected": 0, "errors": [], "committed": True}


@router.get("/{citizen_id}", response_model=CitizenResponse)
def get_citizen(citizen_id: str, db: Session = Depends(get_db)):
    citizen = db.query(Citizen).filter(Citizen.id == citizen_id, Citizen.archived_at.is_(None)).first()
    if not citizen:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Citizen record '{citizen_id}' not found."
        )
    return _to_response_model(citizen)


@router.patch("/{citizen_id}", response_model=CitizenDobPatchResponse)
def update_citizen(
    citizen_id: str,
    update_data: CitizenUpdate,
    db: Session = Depends(get_db)
):
    citizen = db.query(Citizen).filter(Citizen.id == citizen_id, Citizen.archived_at.is_(None)).first()
    if not citizen:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Citizen record '{citizen_id}' not found."
        )

    previous_age = citizen.age
    event_detected = None

    if update_data.date_of_birth:
        ref_date = settings.parsed_reference_date
        new_age = calculate_age(update_data.date_of_birth, ref_date)
        citizen.date_of_birth = update_data.date_of_birth
        citizen.age = new_age

        if previous_age < 18 and new_age >= 18:
            event_detected = "MILESTONE_AGE_18"
            citizen.simulated_life_event = "Turned 18 years of age (Adult Majority)"
        elif previous_age < 60 and new_age >= 60:
            event_detected = "SENIOR_CITIZEN_60"
            citizen.simulated_life_event = "Became a senior citizen (60+)"

    fields = update_data.model_dump(exclude_unset=True)
    for field, value in fields.items():
        if field in {"first_name", "last_name", "date_of_birth"} or value is None:
            continue
        if field in {"potentially_relevant_services", "required_documents"}:
            value = json.dumps(value)
        if field == "record_source":
            citizen.demo_only = value == "synthetic"
        setattr(citizen, field, value)
    if update_data.first_name is not None:
        citizen.first_name = update_data.first_name.strip()
    if update_data.last_name is not None:
        citizen.last_name = update_data.last_name.strip()
    citizen.name = f"{citizen.first_name} {citizen.last_name}"
    if update_data.date_of_birth is not None:
        citizen.is_senior_citizen = citizen.age >= 60

    db.commit()
    db.refresh(citizen)

    return CitizenDobPatchResponse(
        citizen_id=citizen.id,
        previous_age=previous_age,
        calculated_age=citizen.age,
        event_detected=event_detected,
        citizen=_to_response_model(citizen)
    )


@router.post("/{citizen_id}/archive", response_model=CitizenResponse)
def archive_citizen(citizen_id: str, db: Session = Depends(get_db)):
    citizen = db.query(Citizen).filter(Citizen.id == citizen_id).first()
    if not citizen:
        raise HTTPException(status_code=404, detail="Record not found.")
    citizen.archived_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(citizen)
    return _to_response_model(citizen)


@router.post("/{citizen_id}/restore", response_model=CitizenResponse)
def restore_citizen(citizen_id: str, db: Session = Depends(get_db)):
    citizen = db.query(Citizen).filter(Citizen.id == citizen_id).first()
    if not citizen:
        raise HTTPException(status_code=404, detail="Record not found.")
    citizen.archived_at = None
    db.commit()
    db.refresh(citizen)
    return _to_response_model(citizen)


@router.post("/{citizen_id}/evaluate", response_model=CitizenEvaluationResponse)
def evaluate_citizen(citizen_id: str, db: Session = Depends(get_db)):
    citizen = db.query(Citizen).filter(Citizen.id == citizen_id).first()
    if not citizen:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Citizen record '{citizen_id}' not found."
        )

    ref_date = settings.parsed_reference_date
    citizen_snapshot = {
        "id": citizen.id,
        "first_name": citizen.first_name,
        "last_name": citizen.last_name,
        "date_of_birth": citizen.date_of_birth,
        "age": citizen.age,
        "gender": citizen.gender,
        "state": citizen.state,
        "district": citizen.district,
        "rural_or_urban": citizen.rural_or_urban,
        "simulated_income_bracket": citizen.simulated_income_bracket,
        "is_student": citizen.is_student,
        "is_farmer": citizen.is_farmer,
        "is_senior_citizen": citizen.is_senior_citizen,
        "occupation": citizen.occupation,
        "simulated_life_event": citizen.simulated_life_event,
        "children": citizen.children
    }

    eval_results = evaluate_all_services(citizen_snapshot, ref_date)
    eligible_schemes = [res.service for res in eval_results if res.is_eligible]

    return CitizenEvaluationResponse(
        citizen_id=citizen.id,
        calculated_age=citizen.age,
        eligible_services=eligible_schemes,
        detailed_results=eval_results,
        call_job_scheduled=False
    )
