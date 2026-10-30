from datetime import date, datetime, timezone
from typing import List, Dict, Any, Tuple
from app.services.catalogue_data import OFFICIAL_SERVICES_CATALOGUE
from app.schemas.service_scheme import ServiceSchemeResponse, EligibilityResult


def calculate_age(dob: date, reference_date: date) -> int:
    """Deterministic age calculation considering calendar year and birthday boundaries."""
    age = reference_date.year - dob.year
    if (reference_date.month, reference_date.day) < (dob.month, dob.day):
        age -= 1
    return age


def evaluate_citizen_service(
    service_dict: Dict[str, Any],
    citizen_data: Dict[str, Any],
    reference_date: date
) -> EligibilityResult:
    """
    Evaluates a single citizen's preliminary eligibility against a statutory scheme.
    Enforces deterministic logic and maintains a strict disclaimer that only competent
    government authorities make definitive determinations.
    """
    sid = service_dict["id"]
    dob = citizen_data.get("date_of_birth")
    if isinstance(dob, str):
        dob = date.fromisoformat(dob)
    
    age = citizen_data.get("age")
    if age is None and dob:
        age = calculate_age(dob, reference_date)
    age = age or 0

    income_bracket = str(citizen_data.get("simulated_income_bracket", "")).upper()
    is_farmer = bool(citizen_data.get("is_farmer", False))
    is_student = bool(citizen_data.get("is_student", False))
    is_senior = bool(citizen_data.get("is_senior_citizen", False)) or age >= 60
    occupation = str(citizen_data.get("occupation", "")).lower()
    life_event = str(citizen_data.get("simulated_life_event", "")).lower()
    children = int(citizen_data.get("children", 0))

    is_eligible = False
    status = "INELIGIBLE"
    reason = ""
    missing_docs: List[str] = list(service_dict.get("commonly_required_documents", []))

    if sid == "SVC-VOTER-ID":
        if age >= 18:
            is_eligible = True
            status = "POTENTIALLY_ELIGIBLE"
            reason = f"Applicant is {age} years old (meets statutory minimum age 18 threshold for general elector enrollment under Form 6)."
        elif age == 17:
            is_eligible = False
            status = "NEEDS_MORE_INFO"
            reason = f"Applicant is {age} years old and may submit advance application under ECI quarterly qualifying dates."
        else:
            is_eligible = False
            status = "INELIGIBLE"
            reason = f"Applicant is {age} years old. Minimum statutory age for voter registration is 18."

    elif sid == "SVC-LEARNER-LICENCE":
        if age >= 18:
            is_eligible = True
            status = "POTENTIALLY_ELIGIBLE"
            reason = f"Applicant is {age} years old (meets age criteria for Light Motor Vehicle Learner's Licence)."
        elif age >= 16:
            is_eligible = True
            status = "POTENTIALLY_ELIGIBLE"
            reason = f"Applicant is {age} years old (meets age threshold for gearless two-wheeler up to 50cc with parental consent)."
        else:
            is_eligible = False
            status = "INELIGIBLE"
            reason = f"Applicant is {age} years old (below minimum age 16 for motorcycle without gear)."

    elif sid == "SVC-PAN-CARD":
        if age >= 18:
            is_eligible = True
            status = "POTENTIALLY_ELIGIBLE"
            reason = f"Applicant is an adult ({age} years old) eligible for direct independent PAN card issuance."
        else:
            is_eligible = True
            status = "POTENTIALLY_ELIGIBLE"
            reason = f"Applicant is a minor ({age} years old) eligible for PAN card issuance with parent/guardian as representative assessee."

    elif sid == "SVC-PM-KISAN":
        if is_farmer or "farmer" in occupation or "agriculture" in occupation:
            is_eligible = True
            status = "POTENTIALLY_ELIGIBLE"
            reason = "Profile indicates agricultural occupation / farmer household with cultivable land eligibility."
        else:
            is_eligible = False
            status = "INELIGIBLE"
            reason = "PM-KISAN requires ownership of cultivable agricultural land parcels as registered in state revenue records."

    elif sid == "SVC-AYUSHMAN-BHARAT":
        if age >= 70:
            is_eligible = True
            status = "POTENTIALLY_ELIGIBLE"
            reason = f"Applicant is {age} years old (qualifies for universal senior citizen Ayushman cover regardless of income)."
        elif income_bracket in ["BPL", "LOW"]:
            is_eligible = True
            status = "POTENTIALLY_ELIGIBLE"
            reason = f"Family income category is {income_bracket}, matching SECC/NFSA deprivation screening profiles."
        else:
            is_eligible = False
            status = "NEEDS_MORE_INFO"
            reason = "Ayushman Bharat coverage requires inclusion in SECC 2011/NFSA beneficiary lists or age 70+."

    elif sid == "SVC-NSP-SCHOLARSHIP":
        if (is_student or "student" in occupation) and 16 <= age <= 30 and income_bracket in ["BPL", "LOW"]:
            is_eligible = True
            status = "POTENTIALLY_ELIGIBLE"
            reason = f"Enrolled student aged {age} within qualifying income threshold for post-matric central scholarship schemes."
        elif is_student:
            is_eligible = False
            status = "NEEDS_MORE_INFO"
            reason = "Student enrollment indicated, but family income must fall below scheme-specific annual ceilings."
        else:
            is_eligible = False
            status = "INELIGIBLE"
            reason = "Scheme requires active full-time enrollment in a recognised higher secondary or collegiate institution."

    elif sid == "SVC-IGNOAPS-PENSION":
        if age >= 60 and income_bracket in ["BPL", "LOW"]:
            is_eligible = True
            status = "POTENTIALLY_ELIGIBLE"
            reason = f"Senior citizen aged {age} from {income_bracket} economic group meets preliminary NSAP old-age pension criteria."
        elif age >= 60:
            is_eligible = False
            status = "NEEDS_MORE_INFO"
            reason = f"Age criterion met ({age} years), but IGNOAPS requires verified Below Poverty Line (BPL) status."
        else:
            is_eligible = False
            status = "INELIGIBLE"
            reason = f"Applicant is {age} years old. Minimum statutory age for IGNOAPS is 60."

    elif sid == "SVC-SUKANYA-SAMRIDDHI":
        if children > 0 or "child" in life_event or "daughter" in life_event:
            is_eligible = True
            status = "POTENTIALLY_ELIGIBLE"
            reason = "Profile indicates parent/guardian of young children eligible for girl child SSA savings account."
        else:
            is_eligible = False
            status = "INELIGIBLE"
            reason = "SSA account can only be opened for a girl child below 10 years of age by natural or legal guardians."

    elif sid == "SVC-E-SHRAM":
        if 16 <= age <= 59 and ("daily" in occupation or "wage" in occupation or "worker" in occupation or "labour" in occupation or "self" in occupation or is_farmer):
            is_eligible = True
            status = "POTENTIALLY_ELIGIBLE"
            reason = f"Age {age} within unorganised worker bracket (16-59) with qualifying informal/self-employed occupation."
        elif 16 <= age <= 59 and income_bracket in ["BPL", "LOW"]:
            is_eligible = True
            status = "POTENTIALLY_ELIGIBLE"
            reason = f"Age {age} within eligible bracket and low-income informal sector profile."
        else:
            is_eligible = False
            status = "INELIGIBLE"
            reason = "e-Shram is reserved for unorganised workers aged 16-59 not enrolled in EPFO/ESIC."

    elif sid == "SVC-UDID-DISABILITY":
        if "disability" in life_event or "udid" in life_event:
            is_eligible = True
            status = "POTENTIALLY_ELIGIBLE"
            reason = "Disability milestone or event indicated; requires 40%+ benchmark certificate from medical board."
        else:
            is_eligible = False
            status = "NEEDS_MORE_INFO"
            reason = "Requires certification of 40% or more benchmark disability by a competent district medical authority."

    service_response = ServiceSchemeResponse(
        id=service_dict["id"],
        service_code=service_dict["service_code"],
        name=service_dict["name"],
        service_name=service_dict.get("service_name", service_dict["name"]),
        category=service_dict["category"],
        administering_body=service_dict["administering_body"],
        intended_beneficiaries=service_dict["intended_beneficiaries"],
        basic_eligibility_criteria=service_dict["basic_eligibility_criteria"],
        commonly_required_documents=service_dict.get("commonly_required_documents", []),
        required_docs=service_dict.get("commonly_required_documents", []),
        application_channel=service_dict["application_channel"],
        application_mode=service_dict.get("application_mode", service_dict["application_channel"]),
        statutory_fee_inr=float(service_dict.get("statutory_fee_inr", 0.0)),
        official_application_url=service_dict["official_application_url"],
        official_portal_url=service_dict.get("official_portal_url", service_dict["official_application_url"]),
        official_source_url=service_dict["official_source_url"],
        description_english=service_dict["description_english"],
        description_hinglish=service_dict["description_hinglish"],
        min_age=int(service_dict.get("min_age", 18)),
        max_age=service_dict.get("max_age"),
        last_verification_date=service_dict["last_verification_date"].isoformat() if isinstance(service_dict["last_verification_date"], date) else str(service_dict["last_verification_date"]),
        verification_status=service_dict["verification_status"]
    )

    return EligibilityResult(
        id=f"elg-{citizen_data.get('id', 'CIT')}-{service_dict['service_code']}",
        citizen_id=str(citizen_data.get("id", "")),
        service=service_response,
        is_eligible=is_eligible,
        status=status,
        evaluated_at=datetime.now(timezone.utc).isoformat(),
        qualification_reason=reason,
        missing_documents=missing_docs if is_eligible else []
    )


def evaluate_all_services(
    citizen_data: Dict[str, Any],
    reference_date: date
) -> List[EligibilityResult]:
    """Evaluates citizen against all schemes in the official catalogue."""
    results = []
    for svc in OFFICIAL_SERVICES_CATALOGUE:
        result = evaluate_citizen_service(svc, citizen_data, reference_date)
        results.append(result)
    return results
