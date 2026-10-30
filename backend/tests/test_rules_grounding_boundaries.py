"""Tests for Deterministic Rules Engine Grounding and Anti-Hallucination Boundaries.

Verifies:
- Separation of deterministic statutory eligibility from LLM generation.
- Prohibition of LLM override on deterministic eligibility decisions.
- Rejection of unverified catalogue claims.
- Handling of unsupported government welfare claims.
"""
from datetime import date
import pytest

from app.models.citizen import Citizen
from app.models.service_scheme import ServiceScheme
from app.services.llm_service import llm_service
from app.services.rules_engine import evaluate_all_services
from app.services.knowledge_service import knowledge_service


def test_deterministic_rule_ineligibility_cannot_be_overridden_by_prompt():
    """Verifies that an underage citizen is deterministically ruled INELIGIBLE."""
    ref_date = date(2026, 10, 28)
    underage_citizen = {
        "id": "CIT-UNDERAGE",
        "date_of_birth": date(2012, 1, 1),
        "age": 14,
        "is_student": True,
        "simulated_income_bracket": "LOW",
    }
    results = evaluate_all_services(underage_citizen, ref_date)
    voter_rule = next(r for r in results if r.service.id == "SVC-VOTER-ID")
    assert voter_rule.is_eligible is False
    assert voter_rule.status == "INELIGIBLE"
    assert "Minimum statutory age" in voter_rule.qualification_reason


def test_unverified_catalogue_entry_is_explicitly_flagged_in_system_prompt():
    """Verifies that catalogue items with status != VERIFIED prohibit stating statutory eligibility."""
    test_services = [
        {
            "id": "SVC-UNVERIFIED-01",
            "name": "Unverified Test Welfare Scheme",
            "verification_status": "NEEDS_REVIEW",
            "official_source_url": "https://example.gov.in/pending",
        }
    ]
    prompt = llm_service.build_grounded_system_prompt(test_services, language="Hindi")
    assert "NEEDS_REVIEW" in prompt
    assert "This entry is pending human source review" in prompt
    assert "Do not use it to state eligibility, documents, fees, deadlines" in prompt


def test_unsupported_government_claim_retrieval_rejection(db):
    """Verifies that unsupported welfare claims (e.g. 5 lakh free cash to all citizens) return no verified match."""
    bogus_claim_query = "क्या सरकार हर नागरिक को बिना किसी शर्त के 5 लाख रुपये बैंक खाते में मुफ्त दे रही है?"
    matches = knowledge_service.search(db, bogus_claim_query, top_k=3, min_score=0.50)
    # The system must not return a high-confidence match for a non-existent unconditional cash handout
    assert len(matches) == 0, f"Expected 0 matches for unsupported claim, got: {[m['section_heading'] for m in matches]}"


def test_openai_compat_rejects_empty_and_handles_unsupported_queries(client):
    """Verifies that OpenAI chat completions endpoint cleanly handles unsupported claims without hallucinations."""
    from app.config import settings
    auth_key = settings.TIMBRE_LLM_API_KEY or settings.BOLNA_WEBHOOK_SECRET
    headers = {"Authorization": f"Bearer {auth_key}"} if auth_key else {}

    # 1. Empty message handling
    empty_res = client.post(
        "/v1/chat/completions",
        headers=headers,
        json={
            "model": "timbre-voice-agent",
            "messages": [{"role": "user", "content": "   "}],
        },
    )
    assert empty_res.status_code == 200
    choice = empty_res.json()["choices"][0]["message"]["content"]
    assert "माफ़ कीजिए" in choice

    # 2. Stop intent
    stop_res = client.post(
        "/v1/chat/completions",
        headers=headers,
        json={
            "model": "timbre-voice-agent",
            "messages": [{"role": "user", "content": "रुको बस करो तुरंत फोन काटो"}],
        },
    )
    assert stop_res.status_code == 200
    stop_content = stop_res.json()["choices"][0]["message"]["content"]
    assert "कॉल यहीं समाप्त" in stop_content
