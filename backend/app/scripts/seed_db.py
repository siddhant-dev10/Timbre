import csv
import json
import os
import sys
from datetime import date
from pathlib import Path

# Add backend directory to sys.path so app imports work
backend_dir = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(backend_dir))

from app.database.session import engine, SessionLocal
from app.database.base import Base
from app.models.citizen import Citizen
from app.models.service_scheme import ServiceScheme
from app.services.catalogue_data import OFFICIAL_SERVICES_CATALOGUE
from app.config import settings


def seed_database(csv_path: Path = None, db_session = None):
    # Create all tables if not exist
    Base.metadata.create_all(bind=engine)

    repo_root = backend_dir.parent
    if csv_path is None:
        csv_path = repo_root / "data" / "demo" / "Timbre_Fake_Citizens.csv"

    if not csv_path.exists():
        raise FileNotFoundError(f"Citizens CSV file not found at: {csv_path}")

    session = db_session or SessionLocal()
    try:
        # 1. Seed Service Catalogue Idempotently
        for svc in OFFICIAL_SERVICES_CATALOGUE:
            existing_svc = session.query(ServiceScheme).filter_by(id=svc["id"]).first()
            if existing_svc:
                # Update attributes in place
                existing_svc.name = svc["name"]
                existing_svc.service_code = svc["service_code"]
                existing_svc.category = svc["category"]
                existing_svc.administering_body = svc["administering_body"]
                existing_svc.intended_beneficiaries = svc["intended_beneficiaries"]
                existing_svc.basic_eligibility_criteria = svc["basic_eligibility_criteria"]
                existing_svc.commonly_required_documents = json.dumps(svc.get("commonly_required_documents", []))
                existing_svc.application_channel = svc["application_channel"]
                existing_svc.statutory_fee_inr = svc.get("statutory_fee_inr", 0.0)
                existing_svc.official_application_url = svc["official_application_url"]
                existing_svc.official_source_url = svc["official_source_url"]
                existing_svc.description_english = svc["description_english"]
                existing_svc.description_hinglish = svc["description_hinglish"]
                existing_svc.min_age = svc.get("min_age", 18)
                existing_svc.max_age = svc.get("max_age")
                existing_svc.last_verification_date = svc["last_verification_date"]
                existing_svc.verification_status = svc["verification_status"]
            else:
                new_svc = ServiceScheme(
                    id=svc["id"],
                    service_code=svc["service_code"],
                    name=svc["name"],
                    category=svc["category"],
                    administering_body=svc["administering_body"],
                    intended_beneficiaries=svc["intended_beneficiaries"],
                    basic_eligibility_criteria=svc["basic_eligibility_criteria"],
                    commonly_required_documents=json.dumps(svc.get("commonly_required_documents", [])),
                    application_channel=svc["application_channel"],
                    statutory_fee_inr=svc.get("statutory_fee_inr", 0.0),
                    official_application_url=svc["official_application_url"],
                    official_source_url=svc["official_source_url"],
                    description_english=svc["description_english"],
                    description_hinglish=svc["description_hinglish"],
                    min_age=svc.get("min_age", 18),
                    max_age=svc.get("max_age"),
                    last_verification_date=svc["last_verification_date"],
                    verification_status=svc["verification_status"]
                )
                session.add(new_svc)
        session.commit()

        # 2. Seed Fictional Citizens Idempotently
        citizens_inserted = 0
        citizens_updated = 0

        with open(csv_path, mode="r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                cid = row["citizen_id"]
                dob = date.fromisoformat(row["date_of_birth"])
                
                # Check for existing record
                existing_cit = session.query(Citizen).filter_by(id=cid).first()
                if existing_cit:
                    existing_cit.first_name = row["first_name"]
                    existing_cit.last_name = row["last_name"]
                    existing_cit.name = row["name"]
                    existing_cit.date_of_birth = dob
                    existing_cit.age = int(row["age"])
                    existing_cit.gender = row["gender"]
                    existing_cit.state = row["state"]
                    existing_cit.district = row["district"]
                    existing_cit.city_or_village = row["city_or_village"]
                    existing_cit.rural_or_urban = row["rural_or_urban"]
                    existing_cit.preferred_language = row["preferred_language"]
                    existing_cit.education = row["education"]
                    existing_cit.occupation = row["occupation"]
                    existing_cit.employment_status = row["employment_status"]
                    existing_cit.synthetic_family_income = int(row["synthetic_family_income"])
                    existing_cit.simulated_income_bracket = row["simulated_income_bracket"]
                    existing_cit.family_size = int(row["family_size"])
                    existing_cit.marital_status = row["marital_status"]
                    existing_cit.children = int(row["children"])
                    existing_cit.is_student = row["is_student"].lower() in ("true", "1")
                    existing_cit.is_farmer = row["is_farmer"].lower() in ("true", "1")
                    existing_cit.is_senior_citizen = row["is_senior_citizen"].lower() in ("true", "1")
                    existing_cit.simulated_life_event = row["simulated_life_event"]
                    existing_cit.potentially_relevant_services = row["potentially_relevant_services"]
                    existing_cit.eligibility_notes = row["eligibility_notes"]
                    existing_cit.required_documents = row["required_documents"]
                    existing_cit.demo_only = True
                    existing_cit.phone_number = row["phone_number"]
                    existing_cit.email = row["email"]
                    existing_cit.pincode = row["pincode"]
                    citizens_updated += 1
                else:
                    new_cit = Citizen(
                        id=cid,
                        first_name=row["first_name"],
                        last_name=row["last_name"],
                        name=row["name"],
                        date_of_birth=dob,
                        age=int(row["age"]),
                        gender=row["gender"],
                        state=row["state"],
                        district=row["district"],
                        city_or_village=row["city_or_village"],
                        rural_or_urban=row["rural_or_urban"],
                        preferred_language=row["preferred_language"],
                        education=row["education"],
                        occupation=row["occupation"],
                        employment_status=row["employment_status"],
                        synthetic_family_income=int(row["synthetic_family_income"]),
                        simulated_income_bracket=row["simulated_income_bracket"],
                        family_size=int(row["family_size"]),
                        marital_status=row["marital_status"],
                        children=int(row["children"]),
                        is_student=row["is_student"].lower() in ("true", "1"),
                        is_farmer=row["is_farmer"].lower() in ("true", "1"),
                        is_senior_citizen=row["is_senior_citizen"].lower() in ("true", "1"),
                        simulated_life_event=row["simulated_life_event"],
                        potentially_relevant_services=row["potentially_relevant_services"],
                        eligibility_notes=row["eligibility_notes"],
                        required_documents=row["required_documents"],
                        demo_only=True,
                        phone_number=row["phone_number"],
                        email=row["email"],
                        pincode=row["pincode"]
                    )
                    session.add(new_cit)
                    citizens_inserted += 1

        session.commit()
        total_citizens = session.query(Citizen).count()
        total_services = session.query(ServiceScheme).count()
        print(f"Seed complete: {citizens_inserted} inserted, {citizens_updated} updated.")
        print(f"Database currently holds {total_citizens} citizens and {total_services} services.")
        return total_citizens, total_services
    finally:
        if db_session is None:
            session.close()


def main():
    seed_database()


if __name__ == "__main__":
    main()
