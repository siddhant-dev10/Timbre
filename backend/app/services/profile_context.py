"""Minimize synthetic profile facts sent to hosted model providers."""
import json
from datetime import date
from typing import Any, Dict, Mapping

from app.services.rules_engine import calculate_age


def minimal_profile_context(citizen: Any, reference_date: date) -> str:
    """Return only eligibility-relevant facts; exclude names, IDs, contact and exact income."""
    def get(name: str) -> Any:
        return citizen.get(name) if isinstance(citizen, Mapping) else getattr(citizen, name, None)

    dob = get("date_of_birth")
    age = calculate_age(dob, reference_date) if dob else get("age")
    facts: Dict[str, Any] = {
        "age_on_reference_date": age,
        "reference_date": reference_date.isoformat(),
        "state": get("state"),
        "education": get("education"),
        "occupation": get("occupation"),
        "income_bracket": get("simulated_income_bracket"),
        "is_student": get("is_student"),
        "is_farmer": get("is_farmer"),
        "is_senior_citizen": get("is_senior_citizen"),
        "children_count": get("children"),
    }
    facts = {key: value for key, value in facts.items() if value is not None and value != ""}
    return (
        "Synthetic profile facts (use only for preliminary matching; missing facts are unknown, "
        "not negative):\n" + json.dumps(facts, ensure_ascii=False, sort_keys=True)
    )
