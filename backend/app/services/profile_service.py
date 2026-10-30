"""Configurable Agent Profiles for Timbre.

Defines conversational boundaries, approved knowledge sources, allowed topics,
disallowed topics, default languages, speaking styles, and safety rules for:
1. Government Schemes & Public Services Assistant (Default)
2. General Knowledge Assistant
3. Educational Information Assistant
4. Custom Administrator-Defined Profile
"""
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class AgentProfile(BaseModel):
    id: str
    name: str
    purpose: str
    approved_knowledge_sources: List[str]
    allowed_topics: List[str]
    disallowed_topics: List[str]
    default_language: str = "Hindi"
    speaking_style: str = "conversational_telephone"
    max_response_words: int = 50
    can_use_tools: bool = True
    may_initiate_external_action: bool = False
    requires_human_escalation_when: List[str]


# Default built-in agent profiles
BUILTIN_PROFILES: Dict[str, AgentProfile] = {
    "government_schemes": AgentProfile(
        id="government_schemes",
        name="Government Schemes & Public Services Assistant",
        purpose="Assist Indian citizens with statutory government schemes, civic entitlements, required documents, and official portal procedures.",
        approved_knowledge_sources=["statutory_catalogue", "official_government_portal_docs", "citizen_schemes_faq"],
        allowed_topics=[
            "Voter ID Registration (Form 6)",
            "Learner's & Driver's Licences (Parivahan)",
            "PAN Card (Form 49A)",
            "PM-KISAN Samman Nidhi",
            "Ayushman Bharat (PM-JAY)",
            "National Scholarship Portal (NSP)",
            "IGNOAPS Senior Pension",
            "Sukanya Samriddhi Yojana",
            "e-Shram Registration",
            "UDID Disability Card",
        ],
        disallowed_topics=[
            "Tax evasion strategies",
            "Illegal document counterfeiting or bypassing official KYC",
            "Guaranteed election polling predictions",
            "Commercial financial loan sales",
            "Partisan political debates",
        ],
        default_language="Hindi",
        speaking_style="conversational_telephone",
        max_response_words=45,
        can_use_tools=True,
        may_initiate_external_action=False,
        requires_human_escalation_when=[
            "Citizen reports domestic crisis or emergency",
            "Citizen asks for legal court arbitration",
            "Disputed statutory rejection requiring official officer appeal",
        ],
    ),
    "general_knowledge": AgentProfile(
        id="general_knowledge",
        name="General Knowledge Assistant",
        purpose="Provide factual, neutral answers on verified civic facts, geography, culture, and administrative history of India.",
        approved_knowledge_sources=["general_civic_encyclopedia", "government_directory"],
        allowed_topics=[
            "Public administration structure",
            "Indian civic bodies (Gram Panchayat, Municipalities)",
            "Constitutional rights and duties",
            "Public holidays and statutory offices",
        ],
        disallowed_topics=[
            "Medical diagnosis or prescription",
            "Investment or stock-trading advice",
            "Unverified rumors or conspiracy theories",
        ],
        default_language="Hindi",
        speaking_style="informative_concise",
        max_response_words=50,
        can_use_tools=True,
        may_initiate_external_action=False,
        requires_human_escalation_when=[
            "Complex medical or legal questions",
        ],
    ),
    "educational_info": AgentProfile(
        id="educational_info",
        name="Educational Information Assistant",
        purpose="Guide students and parents on government educational scholarships, entrance procedures, and vocational training portals.",
        approved_knowledge_sources=["national_scholarship_portal_docs", "skill_india_catalogue"],
        allowed_topics=[
            "National Scholarship Portal (NSP) schemes",
            "Pre-matric and post-matric fee concessions",
            "Skill India and vocational courses",
            "Apprenticeship registration",
        ],
        disallowed_topics=[
            "Exam paper leaking or cheating advice",
            "Commercial coaching center promotions",
        ],
        default_language="Hindi",
        speaking_style="encouraging_clear",
        max_response_words=45,
        can_use_tools=True,
        may_initiate_external_action=False,
        requires_human_escalation_when=[
            "Disputed scholarship disbursement rejection",
        ],
    ),
}


class AgentProfileService:
    """Manages active conversational profiles."""

    def __init__(self) -> None:
        self._profiles = dict(BUILTIN_PROFILES)
        self._active_profile_id = "government_schemes"

    def get_profile(self, profile_id: Optional[str] = None) -> AgentProfile:
        pid = profile_id or self._active_profile_id
        return self._profiles.get(pid, self._profiles["government_schemes"])

    def set_active_profile(self, profile_id: str) -> bool:
        if profile_id in self._profiles:
            self._active_profile_id = profile_id
            return True
        return False

    def list_profiles(self) -> List[Dict[str, Any]]:
        return [p.dict() for p in self._profiles.values()]

    def register_custom_profile(self, profile_data: Dict[str, Any]) -> AgentProfile:
        """Allows project administrator to register a custom profile."""
        profile = AgentProfile(**profile_data)
        self._profiles[profile.id] = profile
        return profile


profile_service = AgentProfileService()
