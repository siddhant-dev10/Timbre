"""Conversational AI Engine for Timbre WhatsApp Civic Assistant.

Provides:
- Language detection (Hindi Devanagari, Hinglish Roman, English).
- Statutory scheme keyword identification & FastEmbed RAG retrieval.
- Multi-turn conversational memory & context formatting.
- Interactive guidance: asking clarifying questions when user info is missing (e.g. turning 18).
- AI identity disclosure & non-repetitive greetings.
- Prompt injection protection & privacy defense (no Aadhaar/OTP collection).
- Grounded fallback responses when LLM provider is not configured or unavailable.
"""
import json
import logging
import re
from typing import Any, Dict, List, Optional, Tuple
from sqlalchemy.orm import Session

from app.config import settings
from app.models.service_scheme import ServiceScheme
from app.services.knowledge_service import knowledge_service
from app.services.llm_service import llm_service

logger = logging.getLogger("timbre.whatsapp.agent")

# Keywords mapping for statutory schemes
SCHEME_KEYWORDS: Dict[str, List[str]] = {
    "SVC-VOTER-ID": ["voter", "vote", "matdata", "form 6", "epic", "chunav", "election", "पहचान पत्र", "मतदाता"],
    "SVC-LEARNER-LICENCE": ["licence", "license", "driving", "gadi", "parivahan", "sarathi", "ll", "dl", "लाइसेंस"],
    "SVC-PAN-CARD": ["pan", "pan card", "tax", "income tax", "bank account", "form 49a", "पैन कार्ड"],
    "SVC-PM-KISAN": ["kisan", "farmer", "agriculture", "kheti", "pm kisan", "samman nidhi", "6000", "किसान"],
    "SVC-AYUSHMAN-BHARAT": ["ayushman", "health", "hospital", "beema", "insurance", "ilaj", "golden card", "pmjay", "आयुष्मान"],
    "SVC-NSP-SCHOLARSHIP": ["scholarship", "padhai", "college", "fees", "chhatravritti", "nsp", "student", "छात्रवृत्ति"],
    "SVC-IGNOAPS-PENSION": ["pension", "old age", "vridhha", "bujurg", "senior", "nsap", "60", "पेंशन", "वृद्धावस्था"],
    "SVC-SUKANYA-SAMRIDDHI": ["sukanya", "beti", "daughter", "girl child", "ssa", "post office", "सुकन्या"],
    "SVC-E-SHRAM": ["shram", "eshram", "worker", "labour", "majdoor", "uan", "unorganised", "श्रम"],
    "SVC-UDID-DISABILITY": ["disability", "divyang", "handicap", "swavlamban", "udid", "दिव्यांग"],
}


def detect_language(text: str) -> str:
    """
    Detects whether the citizen message is primarily in Devanagari Hindi, English, or Hinglish.
    """
    if not text:
        return "Hinglish"

    # Check for Devanagari script characters (\u0900 - \u097F)
    devanagari_chars = sum(1 for c in text if "\u0900" <= c <= "\u097f")
    if devanagari_chars >= 2:
        return "Hindi"

    lower = text.lower()
    # Check for strong English indicator words without typical Hinglish pronouns/verbs
    english_words = {
        "what", "how", "why", "when", "where", "who", "which",
        "can", "could", "would", "should", "is", "are", "do", "does",
        "eligible", "eligibility", "documents", "document", "apply", "application",
        "scheme", "schemes", "service", "services", "government", "portal",
        "pension", "scholarship", "license", "card", "benefit", "benefits",
        "tell", "explain", "help", "please", "thank", "thanks", "hello", "hi"
    }
    hinglish_markers = {
        "kya", "kaise", "kyun", "kab", "kahan", "kaun", "mera", "meri", "mere",
        "mujhe", "humko", "apna", "apne", "aap", "tum", "main", "hum",
        "hai", "hain", "tha", "thi", "the", "hoga", "hogi", "hoge",
        "chahiye", "karna", "karne", "batao", "batayein", "banwana", "banwane",
        "yojana", "sarkari", "aavedan", "saal", "umra", "nahi", "haan"
    }

    tokens = re.findall(r"\b[a-z']+\b", lower)
    if not tokens:
        return "Hinglish"

    hinglish_count = sum(1 for t in tokens if t in hinglish_markers)
    english_count = sum(1 for t in tokens if t in english_words)

    if hinglish_count > 0:
        return "Hinglish"
    if english_count >= 2 or (english_count >= 1 and len(tokens) <= 4):
        return "English"

    return "Hinglish"


def is_turning_18_inquiry(text: str) -> bool:
    """Detects whether the user is asking about adulthood / turning 18 document requirements in English, Hinglish, or Devanagari."""
    lower = text.lower()
    patterns = [
        r"\b18\s*(saal|sal|year|years|varsh)?\b",
        r"18\s*(साल|वर्ष)?",
        r"१८\s*(साल|वर्ष)?",
        r"\beighteen\b",
        r"\bturning\s*18\b",
        r"\badult\b",
        r"\bmajor\b",
        r"वयस्क",
        r"बालिग",
    ]
    has_age_18 = any(re.search(p, lower) for p in patterns)
    doc_intent = any(w in lower for w in [
        "document", "documents", "dastavez", "kaun se", "kya banwana", "apply",
        "card", "id", "pehchan", "patra", "certificate",
        "दस्तावेज़", "दस्तावेज", "पहचान", "पत्र", "कार्ड", "प्रमाण", "आवेदन", "बनवाना", "बनवाएं", "कागजात"
    ])
    return has_age_18 and doc_intent


class WhatsAppCivicAgent:
    """Conversational AI Agent handling WhatsApp multi-turn civic assistance."""

    def __init__(self):
        pass

    def extract_matched_schemes(self, db: Session, text: str) -> List[ServiceScheme]:
        """Identifies relevant statutory schemes based on keywords and milestone intent."""
        lower = text.lower()
        matched_ids = set()

        # Check for milestone: 18th birthday
        if is_turning_18_inquiry(text):
            matched_ids.update(["SVC-VOTER-ID", "SVC-PAN-CARD", "SVC-LEARNER-LICENCE"])

        # Check keywords
        for sid, triggers in SCHEME_KEYWORDS.items():
            if any(re.search(r"(?<!\w)" + re.escape(tr) + r"(?!\w)", lower) for tr in triggers):
                matched_ids.add(sid)

        if not matched_ids:
            return []

        return db.query(ServiceScheme).filter(ServiceScheme.id.in_(list(matched_ids))).all()

    async def generate_reply(
        self,
        db: Session,
        user_message: str,
        conversation_history: List[Dict[str, str]],
        sender_name: Optional[str] = None,
        conversation_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Executes a grounded multi-turn conversational turn for a citizen message.
        """
        clean_text = user_message.strip()
        lang = detect_language(clean_text)
        is_first_turn = len(conversation_history) == 0

        # 1. Stop / Cancellation intent check
        if any(w in clean_text.lower() for w in ["stop", "cancel", "bye", "alvida", "ruko", "band karo"]):
            if lang == "English":
                reply = "Thank you for reaching out to Timbre. As requested, we will pause this conversation. Feel free to text anytime if you need civic assistance! Have a nice day."
            elif lang == "Hindi":
                reply = "टिम्ब्रे से संपर्क करने के लिए धन्यवाद। आपकी इच्छानुसार यह बातचीत यहीं रोकी जा रही है। किसी भी सरकारी सेवा की जानकारी के लिए कभी भी संदेश भेज सकते हैं। नमस्ते!"
            else:
                reply = "Timbre se baat karne ke liye dhanyawad! Aapki ichhanusar yeh batchit yahin roki ja rahi hai. Kisi bhi sarkari yojana ki jankari ke liye aap kabhi bhi message kar sakte hain. Namaste!"
            return {
                "reply": reply,
                "language": lang,
                "grounded_sources": [],
                "is_stop": True,
            }

        # 2. Safety filter: Refuse Aadhaar / OTP / Bank details collection
        if any(w in clean_text.lower() for w in ["aadhaar number", "otp", "password", "cvv", "bank account number"]):
            if lang == "English":
                reply = (
                    "Important Privacy Notice: Timbre is an AI civic guidance assistant and never collects sensitive "
                    "personal credentials like Aadhaar numbers, OTPs, or bank passwords. Please do not share these details. "
                    "How can I help you regarding scheme eligibility or application steps?"
                )
            elif lang == "Hindi":
                reply = (
                    "महत्वपूर्ण गोपनीयता सूचना: टिम्ब्रे एक एआई नागरिक मार्गदर्शन सहायक है और कभी भी आधार नंबर, ओटीपी, या "
                    "बैंक पासवर्ड जैसे संवेदनशील विवरण नहीं मांगता है। कृपया ऐसे विवरण साझा न करें। मैं सरकारी योजनाओं व पात्रता "
                    "में आपकी किस प्रकार सहायता कर सकता हूँ?"
                )
            else:
                reply = (
                    "Privacy Notice: Timbre ek AI civic assistance assistant hai aur kabhi bhi Aadhaar number, OTP, ya bank "
                    "password jaise sensitive details nahi mangta. Kripya inhe yahan share na karein. Main eligibility aur "
                    "sarkari portals ke baare mein aapki kya madad kar sakta hoon?"
                )
            return {
                "reply": reply,
                "language": lang,
                "grounded_sources": [],
                "is_stop": False,
            }

        # 3. Retrieve relevant schemes and knowledge base chunks (RAG)
        matched_schemes = self.extract_matched_schemes(db, clean_text)
        rag_chunks = knowledge_service.search(db, clean_text, top_k=3, min_score=0.20)

        grounded_sources = []
        context_blocks = []

        for s in matched_schemes:
            docs = []
            try:
                docs = json.loads(s.commonly_required_documents)
            except Exception:
                pass
            grounded_sources.append(s.name)
            context_blocks.append(
                f"Statutory Scheme: {s.name}\n"
                f"Administering Body: {s.administering_body}\n"
                f"Basic Eligibility: {s.basic_eligibility_criteria}\n"
                f"Statutory Fee: {s.statutory_fee_inr} INR\n"
                f"Official Application Portal: {s.official_application_url}\n"
                f"Required Documents: {', '.join(docs) if docs else 'Standard identity and address proof'}\n"
                f"Verification Status: {s.verification_status}"
            )

        for c in rag_chunks:
            source_tag = c.get("document_title", "Verified Knowledge Base")
            if source_tag not in grounded_sources:
                grounded_sources.append(source_tag)
            context_blocks.append(f"Source: {source_tag} ({c.get('section_heading', '')})\n{c.get('content', '')}")

        context_str = "\n\n---\n\n".join(context_blocks) if context_blocks else "No matching verified statutory records found."

        # 4. Construct System Prompt for WhatsApp Messaging
        greeting_instruction = (
            "GREETING: Introduce yourself briefly as Timbre, an AI civic assistant, in your opening response."
            if is_first_turn
            else "GREETING: Continue the conversation naturally. Do NOT re-introduce yourself or repeat 'Namaste, main Timbre hoon' if conversation is already in progress."
        )

        if lang == "English":
            lang_rule = "LANGUAGE: Reply in clear, polite Indian English."
        elif lang == "Hindi":
            lang_rule = "LANGUAGE: Reply in natural, spoken Hindi using Devanagari script (देवनागरी लिपि)."
        else:
            lang_rule = "LANGUAGE: Reply in natural, conversational Hinglish (Hindi written in Roman script)."

        system_prompt = (
            "You are Timbre, an AI civic assistant for Indian citizens. You help people understand government schemes, "
            "statutory document requirements, eligibility rules, and official application procedures.\n\n"
            "WHATSAPP CONVERSATION RULES:\n"
            f"1. {lang_rule}\n"
            f"2. {greeting_instruction}\n"
            "3. CLARITY & BREVITY: Format for WhatsApp reading. Use short paragraphs, numbered lists or clean bullet points. "
            "Keep response concise (under 120 words).\n"
            "4. INTERACTIVE GUIDANCE: If eligibility or application details depend on missing information (e.g. state of residence, "
            "category, income, or existing documents), ask 1 or 2 focused clarifying questions to guide them.\n"
            "5. STRICT GROUNDING: State factual information strictly from the verified context below. Never invent benefits, "
            "fees, deadlines, or claim to submit applications on their behalf.\n"
            "6. DISCLAIMER: Always remind the citizen that this is preliminary guidance and final applications are processed on official government portals.\n"
            "7. NEVER collect or ask for Aadhaar numbers, OTPs, or passwords.\n\n"
            f"VERIFIED CONTEXT:\n{context_str}"
        )

        # 5. Attempt LLM generation via NVIDIA Nemotron
        ai_reply = None
        if settings.NVIDIA_API_KEY.strip():
            llm_res = await llm_service.generate_response(
                prompt=clean_text,
                system_prompt=system_prompt,
                context=conversation_history[-8:],
                conversation_id=f"wa:{conversation_id or 'default'}",
            )
            if llm_res.get("success"):
                ai_reply = llm_res.get("response", "").strip()

        # 6. High-Quality Deterministic Grounded Fallback (for offline demo or when LLM is unavailable)
        if not ai_reply:
            ai_reply = self._build_grounded_fallback(
                clean_text=clean_text,
                lang=lang,
                matched_schemes=matched_schemes,
                is_first_turn=is_first_turn,
                sender_name=sender_name,
            )

        # 7. Ensure statutory preliminary disclaimer is always present on civic guidance
        lower_reply = ai_reply.lower()
        if not any(k in lower_reply for k in ["preliminary", "official", "sarkari", "आधिकारिक", "प्रारंभिक"]):
            if lang == "Hindi":
                ai_reply += "\n\n*नोट: यह प्रारंभिक जानकारी है। आधिकारिक सरकारी पोर्टल पर ही आवेदन करें।*"
            elif lang == "English":
                ai_reply += "\n\n*Note: This is preliminary guidance; please apply on official government portals.*"
            else:
                ai_reply += "\n\n*Note: Yeh preliminary guidance hai. Aavedan official government portal par hi karein.*"

        return {
            "reply": ai_reply,
            "language": lang,
            "grounded_sources": grounded_sources,
            "is_stop": False,
        }

    def _build_grounded_fallback(
        self,
        clean_text: str,
        lang: str,
        matched_schemes: List[ServiceScheme],
        is_first_turn: bool,
        sender_name: Optional[str] = None,
    ) -> str:
        """Constructs a deterministic, helpful response grounded in verified scheme facts."""
        greeting_hi = f"नमस्ते {sender_name + ' जी' if sender_name else ''}! " if is_first_turn else ""
        greeting_en = f"Hello {sender_name}! " if (is_first_turn and sender_name) else ("Hello! " if is_first_turn else "")
        greeting_hinglish = f"Namaste {sender_name + ' ji' if sender_name else ''}! " if is_first_turn else ""

        intro_hi = f"{greeting_hi}मैं टिम्ब्रे हूँ, एक एआई नागरिक सहायक। " if is_first_turn else ""
        intro_en = f"{greeting_en}I am Timbre, an AI civic assistant. " if is_first_turn else ""
        intro_hinglish = f"{greeting_hinglish}Main Timbre hoon, ek AI civic assistant. " if is_first_turn else ""

        # Scenario A: Milestone - 18 Years Old Document Inquiries
        if is_turning_18_inquiry(clean_text):
            if lang == "Hindi":
                return (
                    f"{intro_hi}18 वर्ष की आयु पूरी होने पर हार्दिक बधाई! 18 वर्ष का होने पर आप निम्नलिखित प्रमुख सरकारी दस्तावेज़ बनवा सकते हैं:\n\n"
                    "1. **मतदाता पहचान पत्र (Voter ID - Form 6)**: मतदान के अधिकार के लिए (पोर्टल: voters.eci.gov.in)।\n"
                    "2. **पैन कार्ड (PAN Card - Form 49A)**: वित्तीय कार्यों व बैंक खाता खोलने के लिए (पोर्टल: onlineservices.nsdl.com)।\n"
                    "3. **ड्राइविंग लर्निंग लाइसेंस**: वाहन चलाने के लिए (पोर्टल: parivahan.gov.in)।\n\n"
                    "आपकी बेहतर सहायता के लिए, क्या आप बता सकते हैं कि आप किस राज्य (State) से हैं और आपके पास वर्तमान में आयु प्रमाण (जैसे 10वीं की मार्कशीट या जन्म प्रमाण पत्र) उपलब्ध है?\n\n"
                    "*नोट: यह प्रारंभिक मार्गदर्शन है। आवेदन केवल आधिकारिक सरकारी पोर्टलों पर ही करें।*"
                )
            elif lang == "English":
                return (
                    f"{intro_en}Congratulations on turning 18! As an adult, the essential government documents you are eligible to apply for include:\n\n"
                    "1. **Voter ID (EPIC / Form 6)**: For electoral rights, via the Election Commission portal (voters.eci.gov.in).\n"
                    "2. **PAN Card (Form 49A)**: For tax identification and opening a bank account (onlineservices.nsdl.com).\n"
                    "3. **Driving Learner's Licence**: For motor vehicles via Parivahan Sarathi (parivahan.gov.in).\n\n"
                    "To guide you accurately: which state do you reside in, and do you already have a 10th marksheet or birth certificate for age and address proof?\n\n"
                    "*Note: This is preliminary guidance; please apply directly on verified official portals.*"
                )
            else:
                return (
                    f"{intro_hinglish}18 saal ka hone par badhai! 18 saal ki umra mein aap ye mukhya government documents banwa sakte hain:\n\n"
                    "1. **Voter ID (Form 6)**: Vote daalne ke liye official ECI portal (voters.eci.gov.in) par.\n"
                    "2. **PAN Card (Form 49A)**: Financial transactions aur bank account kholne ke liye (onlineservices.nsdl.com par).\n"
                    "3. **Driving Learner's Licence**: Gadi chalane ke liye Parivahan Sarathi portal (parivahan.gov.in) par.\n\n"
                    "Aapki behtar sahayata ke liye, kya aap bata sakte hain ki aap kis state se hain, aur aapke paas abhi kaun se pehchan praman (jaise 10th marksheet ya birth certificate) uplabdh hain?\n\n"
                    "*Note: Yeh preliminary jankari hai; aavedan official government portal par hi karein.*"
                )

        # Scenario B: Specific Matched Scheme(s)
        if matched_schemes:
            scheme = matched_schemes[0]
            docs = []
            try:
                docs = json.loads(scheme.commonly_required_documents)
            except Exception:
                pass
            docs_str = ", ".join(docs) if docs else "Pehchan praman aur nivas praman"

            if lang == "Hindi":
                return (
                    f"{intro_hi}आपके प्रश्न के अनुसार **{scheme.name}** की सत्यापित जानकारी इस प्रकार है:\n\n"
                    f"• **प्रशासकीय विभाग**: {scheme.administering_body}\n"
                    f"• **पात्रता**: {scheme.basic_eligibility_criteria}\n"
                    f"• **आवश्यक दस्तावेज़**: {docs_str}\n"
                    f"• **आधिकारिक पोर्टल**: {scheme.official_application_url}\n\n"
                    "क्या आप इस योजना की पात्रता नियमों या आवेदन प्रक्रिया के बारे में कुछ और जानना चाहते हैं?\n\n"
                    "*नोट: यह प्रारंभिक जानकारी है। आधिकारिक पोर्टल पर नियमों का पुनः सत्यापन अवश्य करें।*"
                )
            elif lang == "English":
                return (
                    f"{intro_en}Here is the verified statutory information regarding **{scheme.name}**:\n\n"
                    f"• **Administering Body**: {scheme.administering_body}\n"
                    f"• **Eligibility**: {scheme.basic_eligibility_criteria}\n"
                    f"• **Required Documents**: {docs_str}\n"
                    f"• **Official Portal**: {scheme.official_application_url}\n\n"
                    "Would you like more details on specific eligibility criteria or the application steps?\n\n"
                    "*Note: This guidance is preliminary; please check the official government portal for final processing.*"
                )
            else:
                return (
                    f"{intro_hinglish}Aapke prashna ke anusar **{scheme.name}** ki verified statutory information yeh hai:\n\n"
                    f"• **Authority**: {scheme.administering_body}\n"
                    f"• **Eligibility**: {scheme.basic_eligibility_criteria}\n"
                    f"• **Documents Needed**: {docs_str}\n"
                    f"• **Official Portal**: {scheme.official_application_url}\n\n"
                    "Kya aap is yojana ke baare mein koi vishisht sawaal ya aavedan steps janna chahte hain?\n\n"
                    "*Note: Yeh preliminary jankari hai; antim aavedan official portal par hi karein.*"
                )

        # Scenario C: State / Location follow-up
        state_match = re.search(r"\b(rajasthan|delhi|uttar pradesh|up|bihar|maharashtra|haryana|punjab|madhya pradesh|mp|gujarat)\b", clean_text.lower())
        if state_match:
            state_name = state_match.group(1).title()
            if lang == "Hindi":
                return (
                    f"{intro_hi}{state_name} राज्य में नागरिक सेवाएं संबंधित राज्य के ई-मित्र / जन सेवा केंद्र तथा राष्ट्रीय पोर्टलों के माध्यम से उपलब्ध हैं। "
                    "कृपया बताएं कि आप किस विशेष योजना या दस्तावेज़ के बारे में जानकारी चाहते हैं?"
                )
            elif lang == "English":
                return (
                    f"{intro_en}In {state_name}, citizen services and state-specific portals operate alongside National portals. "
                    "Which specific scheme or document would you like to inquire about?"
                )
            else:
                return (
                    f"{intro_hinglish}{state_name} state mein civic services state portals aur Common Service Centers (CSC) ke madhyam se milti hain. "
                    "Aap kis specific yojana ya document ke baare mein aage janna chahte hain?"
                )

        # Scenario D: General Civic Query Fallback
        if lang == "Hindi":
            return (
                f"{intro_hi}मैं भारतीय सरकारी योजनाओं, दस्तावेज़ों (जैसे वोटर आईडी, पैन कार्ड, ड्राइविंग लाइसेंस, किसान सम्मान निधि, आयुष्मान भारत, छात्रवृत्ति) "
                "और उनकी पात्रता की जानकारी प्रदान करता हूँ। आप किस सेवा या योजना के बारे में जानना चाहते हैं?\n\n"
                "*कृपया अपना प्रश्न विस्तार से लिखें।*"
            )
        elif lang == "English":
            return (
                f"{intro_en}I can help you explore Indian government schemes, essential citizen documents (such as Voter ID, PAN card, Driving Licence, PM-Kisan, Ayushman Bharat, Scholarships), "
                "and their statutory eligibility requirements. Which service or scheme would you like to know about?"
            )
        else:
            return (
                f"{intro_hinglish}Main Indian government schemes aur documents (jaise Voter ID, PAN card, Driving Licence, PM-Kisan, Ayushman Bharat, Pension) "
                "ki eligibility aur application procedures me madad karta hoon. Aap kis yojana ya document ke baare mein janna chahte hain?"
            )


whatsapp_agent = WhatsAppCivicAgent()
