from datetime import date
from app.services.rules_engine import calculate_age, evaluate_all_services
from app.services.catalogue_data import OFFICIAL_SERVICES_CATALOGUE


def test_calculate_age_exact():
    ref = date(2026, 10, 28)
    # Birthday on or before ref date
    assert calculate_age(date(2008, 10, 28), ref) == 18
    assert calculate_age(date(2008, 10, 20), ref) == 18
    # Birthday after ref date in current year
    assert calculate_age(date(2008, 11, 15), ref) == 17
    assert calculate_age(date(1966, 10, 1), ref) == 60


def test_rules_engine_underage():
    ref = date(2026, 10, 28)
    citizen = {
        "id": "TEST-01",
        "date_of_birth": date(2010, 5, 1),
        "age": 16,
        "is_student": True,
        "simulated_income_bracket": "LOW"
    }
    results = evaluate_all_services(citizen, ref)
    voter_res = next((r for r in results if r.service.id == "SVC-VOTER-ID"), None)
    assert voter_res is not None
    assert voter_res.is_eligible is False
    assert voter_res.status == "INELIGIBLE"
    assert "Minimum statutory age" in voter_res.qualification_reason


def test_rules_engine_farmer_scheme():
    ref = date(2026, 10, 28)
    citizen_farmer = {
        "id": "TEST-FARMER",
        "date_of_birth": date(1985, 3, 10),
        "age": 41,
        "is_farmer": True,
        "occupation": "Farmer",
        "simulated_income_bracket": "LOW"
    }
    results = evaluate_all_services(citizen_farmer, ref)
    pmkisan = next((r for r in results if r.service.id == "SVC-PM-KISAN"), None)
    assert pmkisan is not None
    assert pmkisan.is_eligible is True
    assert pmkisan.status == "POTENTIALLY_ELIGIBLE"
