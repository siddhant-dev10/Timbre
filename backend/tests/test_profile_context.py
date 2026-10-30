import json
from datetime import date
from types import SimpleNamespace

from app.services.profile_context import minimal_profile_context


def test_profile_context_includes_only_known_eligibility_facts():
    profile = SimpleNamespace(
        date_of_birth=date(2008, 10, 29),
        age=18,
        state="Maharashtra",
        education="College student",
        occupation="Student",
        simulated_income_bracket="LOW",
        is_student=True,
        is_farmer=False,
        is_senior_citizen=False,
        children=0,
        id="CIT-TEST",
        name="Fictional Name",
        phone_number="DEMO-PHONE-0000",
        email="fictional@example.com",
    )
    text = minimal_profile_context(profile, date(2026, 10, 29))
    payload = json.loads(text.split("\n", 1)[1])
    assert payload["age_on_reference_date"] == 18
    assert payload["state"] == "Maharashtra"
    assert "id" not in payload and "name" not in payload
    assert "phone_number" not in payload and "email" not in payload


def test_missing_profile_facts_are_omitted_and_explicitly_unknown():
    text = minimal_profile_context({}, date(2026, 10, 29))
    payload = json.loads(text.split("\n", 1)[1])
    assert "income_bracket" not in payload
    assert "missing facts are unknown" in text
