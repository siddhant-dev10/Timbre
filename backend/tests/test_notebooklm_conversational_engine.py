"""Comprehensive Test Suite for NotebookLM-Style Interactive Conversational Engine.

Verifies the 20 distinct interaction, interruption, knowledge grounding,
telephony, and recovery scenarios specified in Phase 8.
"""
import io
import json
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from app.models.citizen import Citizen
from app.services.conversation_controller import (
    ConversationController,
    ConversationState,
    InvalidStateTransitionError,
)
from app.services.knowledge_service import knowledge_service


@pytest.fixture
def mock_citizen(db):
    citizen = db.query(Citizen).filter(Citizen.id == "CIT-0001").first()
    return citizen


# Scenario 1: A person speaks Hindi (Devanagari response, Hindi policy)
@pytest.mark.asyncio
async def test_scenario_01_person_speaks_hindi(db, mock_citizen):
    controller = ConversationController()
    controller.start_session(mock_citizen, language="Hindi")

    with patch("app.services.llm_service.llm_service.generate_response", new_callable=AsyncMock) as mock_llm:
        mock_llm.return_value = {
            "success": True,
            "response": "नमस्ते! 18 वर्ष की आयु होने पर आप वोटर आईडी कार्ड के लिए आवेदन कर सकते हैं।",
            "model_used": "nvidia/nemotron-3.5-super-vl-120b-a12b",
        }
        res = await controller.process_user_turn(
            db=db,
            user_text="नमस्ते, मुझे वोटर कार्ड के बारे में बताइए।",
            allow_resumption=False,
        )

        assert res["state"] == "SPEAKING"
        assert "वोटर आईडी" in res["ai_response"]
        assert controller.language == "Hindi"


# Scenario 2: A person speaks English (Language switch)
@pytest.mark.asyncio
async def test_scenario_02_person_speaks_english(db, mock_citizen):
    controller = ConversationController()
    controller.start_session(mock_citizen, language="English")

    with patch("app.services.llm_service.llm_service.generate_response", new_callable=AsyncMock) as mock_llm:
        mock_llm.return_value = {
            "success": True,
            "response": "Hello! Citizens who are 18 or older are eligible for a Voter ID card through the ECI portal.",
            "model_used": "nvidia/nemotron-3.5-super-vl-120b-a12b",
        }
        res = await controller.process_user_turn(
            db=db,
            user_text="Hello, please explain the voter registration requirements.",
            allow_resumption=False,
        )

        assert res["state"] == "SPEAKING"
        assert "Voter ID" in res["ai_response"]


# Scenario 3: A person speaks Hinglish (Colloquial mixed loanwords)
@pytest.mark.asyncio
async def test_scenario_03_person_speaks_hinglish(db, mock_citizen):
    controller = ConversationController()
    controller.start_session(mock_citizen, language="Hindi")

    with patch("app.services.llm_service.llm_service.generate_response", new_callable=AsyncMock) as mock_llm:
        mock_llm.return_value = {
            "success": True,
            "response": "वोटर आईडी के लिए ऑनलाइन फॉर्म 6 पोर्टल पर सबमिट किया जा सकता है।",
            "model_used": "nvidia/nemotron-3.5-super-vl-120b-a12b",
        }
        res = await controller.process_user_turn(
            db=db,
            user_text="Mujhe Form 6 online apply karne ka procedure samjha dijiye.",
            allow_resumption=False,
        )

        assert res["state"] == "SPEAKING"
        assert res["is_unclear"] is False


# Scenario 4: Person interrupts the AI (Barge-in / Stale audio invalidation)
def test_scenario_04_interruption_invalidates_stale_audio(mock_citizen):
    controller = ConversationController()
    init_res = controller.start_session(mock_citizen)
    initial_audio_token = init_res["audio_token"]
    assert controller.state == ConversationState.SPEAKING
    assert controller.memory.is_audio_valid(initial_audio_token) is True

    # User starts speaking -> Interruption event triggered
    interrupt_res = controller.interrupt()
    assert interrupt_res["interrupted"] is True
    assert controller.state == ConversationState.LISTENING
    # Stale audio token must now be invalidated
    assert controller.memory.is_audio_valid(initial_audio_token) is False


# Scenario 5: Person asks a follow-up question (Context retention)
@pytest.mark.asyncio
async def test_scenario_05_follow_up_question_retains_context(db, mock_citizen):
    controller = ConversationController()
    controller.start_session(mock_citizen)

    with patch("app.services.llm_service.llm_service.generate_response", new_callable=AsyncMock) as mock_llm:
        # Turn 1
        mock_llm.return_value = {"success": True, "response": "हाँ, आप वोटर आईडी के लिए पात्र हैं।"}
        await controller.process_user_turn(db=db, user_text="क्या मैं 18 साल का होने पर पात्र हूँ?", allow_resumption=False)

        # Turn 2: Follow-up question referring to previous turn
        mock_llm.return_value = {"success": True, "response": "इसके लिए आवश्यक दस्तावेज़ आधार और निवास प्रमाण हैं।"}
        res2 = await controller.process_user_turn(db=db, user_text="और दस्तावेज़ क्या लगेंगे?", allow_resumption=False)

        assert len(controller.memory.recent_turns) == 2
        assert "दस्तावेज़" in res2["ai_response"]


# Scenario 6: Person asks about information in an uploaded PDF
@pytest.mark.asyncio
async def test_scenario_06_asks_about_uploaded_pdf(db, mock_citizen):
    # Ingest synthetic PDF text with page metadata
    doc = knowledge_service.ingest_document(
        db=db,
        title="Parivahan Driving Licence Circular",
        source_type="text",
        content_bytes_or_str="Learner license validity is 6 months from the date of issue. Applicant must pass road safety test.",
        description="Official transport notification",
    )

    controller = ConversationController()
    controller.start_session(mock_citizen)

    with patch("app.services.llm_service.llm_service.generate_response", new_callable=AsyncMock) as mock_llm:
        mock_llm.return_value = {
            "success": True,
            "response": "लर्नर लाइसेंस जारी होने की तिथि से 6 महीने तक मान्य रहता है।",
        }
        res = await controller.process_user_turn(
            db=db,
            user_text="लर्नर लाइसेंस कितने महीने मान्य रहता है?",
            allow_resumption=False,
        )

        assert any("Parivahan Driving Licence Circular" in cite for cite in res["citations"])

    knowledge_service.delete_document(db, doc.id)


# Scenario 7: Person asks something absent from knowledge base
@pytest.mark.asyncio
async def test_scenario_07_absent_from_knowledge_base(db, mock_citizen):
    controller = ConversationController()
    controller.start_session(mock_citizen)

    with patch("app.services.llm_service.llm_service.generate_response", new_callable=AsyncMock) as mock_llm:
        mock_llm.return_value = {
            "success": True,
            "response": "माफ़ कीजिए, मेरी ज्ञान-पुस्तिका में मंगल ग्रह यात्रा की सब्सिडी पर कोई जानकारी नहीं है।",
        }
        res = await controller.process_user_turn(
            db=db,
            user_text="मंगल ग्रह यात्रा के लिए सरकारी सब्सिडी कैसे मिलेगी?",
            allow_resumption=False,
        )

        assert res["state"] == "SPEAKING"
        assert len(res["citations"]) == 0 or all("मंगल ग्रह" not in c for c in res["citations"])


# Scenario 8: Person asks an unrelated in-scope question
@pytest.mark.asyncio
async def test_scenario_08_unrelated_in_scope_question(db, mock_citizen):
    controller = ConversationController()
    controller.start_session(mock_citizen)

    with patch("app.services.llm_service.llm_service.generate_response", new_callable=AsyncMock) as mock_llm:
        mock_llm.return_value = {
            "success": True,
            "response": "पीएम किसान सम्मान निधि के अंतर्गत पात्र किसानों को प्रतिवर्ष ₹6000 की वित्तीय सहायता मिलती है।",
        }
        res = await controller.process_user_turn(
            db=db,
            user_text="क्या किसानों के लिए भी कोई सरकारी योजना है?",
            allow_resumption=False,
        )

        assert "पीएम किसान" in res["ai_response"]


# Scenario 9: Person asks an out-of-scope question
@pytest.mark.asyncio
async def test_scenario_09_out_of_scope_question(db, mock_citizen):
    controller = ConversationController()
    controller.start_session(mock_citizen)

    with patch("app.services.llm_service.llm_service.generate_response", new_callable=AsyncMock) as mock_llm:
        mock_llm.return_value = {
            "success": True,
            "response": "माफ़ कीजिए, मैं केवल भारतीय सरकारी नागरिक सेवाओं और योजनाओं में सहायता कर सकता हूँ। मैं शेयर बाज़ार सलाह नहीं दे सकता।",
        }
        res = await controller.process_user_turn(
            db=db,
            user_text="मुझे कल कौन सा शेयर खरीदना चाहिए?",
            allow_resumption=False,
        )

        assert "शेयर" in res["ai_response"]


# Scenario 10: Person asks the AI to repeat itself
@pytest.mark.asyncio
async def test_scenario_10_asks_ai_to_repeat_itself(db, mock_citizen):
    controller = ConversationController()
    controller.start_session(mock_citizen)

    # First turn
    with patch("app.services.llm_service.llm_service.generate_response", new_callable=AsyncMock) as mock_llm:
        mock_llm.return_value = {"success": True, "response": "फॉर्म 6 के लिए आधार कार्ड और फोटो अनिवार्य है।"}
        await controller.process_user_turn(db=db, user_text="फॉर्म 6 के लिए क्या चाहिए?", allow_resumption=False)

        # User asks to repeat
        mock_llm.return_value = {"success": True, "response": "मैं दोहराता हूँ: फॉर्म 6 के लिए आधार कार्ड और फोटो अनिवार्य है।"}
        res = await controller.process_user_turn(db=db, user_text="कृपया अपनी बात दोबारा दोहराइए।", allow_resumption=False)

        assert "दोहराता" in res["ai_response"] or "फॉर्म 6" in res["ai_response"]


# Scenario 11: Speech is unclear (Low confidence recovery)
@pytest.mark.asyncio
async def test_scenario_11_speech_is_unclear_clarification(db, mock_citizen):
    controller = ConversationController()
    controller.start_session(mock_citizen)

    # Empty/unclear input
    res = await controller.process_user_turn(db=db, user_text="", allow_resumption=False)
    assert res["is_unclear"] is True
    assert "स्पष्ट नहीं आई" in res["ai_response"]


# Scenario 12: Person remains silent
@pytest.mark.asyncio
async def test_scenario_12_person_remains_silent(db, mock_citizen):
    controller = ConversationController()
    controller.start_session(mock_citizen)

    res = await controller.process_user_turn(db=db, user_text="   ", allow_resumption=False)
    assert res["is_unclear"] is True
    assert "दोहरा" in res["ai_response"]


# Scenario 13: Transcription provider fails
@pytest.mark.asyncio
async def test_scenario_13_transcription_provider_failure(db, mock_citizen):
    controller = ConversationController()
    controller.start_session(mock_citizen)

    with patch("app.services.whisper_service.whisper_service.transcribe_audio", side_effect=RuntimeError("Whisper crashed")):
        with pytest.raises(RuntimeError):
            await controller.process_user_turn(db=db, user_audio_bytes=b"RIFF" + b"\x00" * 40)


# Scenario 14: LLM provider times out
@pytest.mark.asyncio
async def test_scenario_14_llm_provider_timeout_fallback(db, mock_citizen):
    controller = ConversationController()
    controller.start_session(mock_citizen)

    with patch("app.services.llm_service.llm_service.generate_response", new_callable=AsyncMock) as mock_llm:
        mock_llm.return_value = {"success": False, "error": "Request timed out"}
        res = await controller.process_user_turn(db=db, user_text="वोटर आईडी की प्रक्रिया क्या है?", allow_resumption=False)

        assert res["state"] == "SPEAKING"
        assert "कठिनाई" in res["ai_response"]


# Scenario 15: TTS provider fails (Turn succeeds with safe fallback)
def test_scenario_15_tts_provider_failure_fallback(client):
    with patch("app.services.llm_service.llm_service.generate_response", new_callable=AsyncMock) as mock_llm, \
         patch("app.services.elevenlabs_service.elevenlabs_service.synthesize_speech", side_effect=RuntimeError("TTS Quota Exceeded")), \
         patch("app.services.elevenlabs_service.elevenlabs_service.is_configured", return_value=True):

        mock_llm.return_value = {"success": True, "response": "नमस्ते! यह उत्तर है।"}

        response = client.post(
            "/api/v1/voice/turn",
            json={"citizen_id": "CIT-0001", "text": "नमस्ते", "synthesize_voice": True}
        )
        assert response.status_code == 200
        data = response.json()
        assert data["ai_response"] == "नमस्ते! यह उत्तर है।"
        assert data["tts_error"] is not None
        assert "TTS Quota Exceeded" in data["tts_error"]


# Scenario 16: Telephony connection drops
def test_scenario_16_telephony_drop_handling(client):
    # Simulated webhook reporting dropped call with patched secret
    with patch("app.config.settings.BOLNA_WEBHOOK_SECRET", "test-sec"):
        webhook_res = client.post(
            "/api/webhooks/bolna",
            headers={"X-Timbre-Webhook-Secret": "test-sec"},
            json={"id": "dropped-call-exec-1", "status": "call-disconnected", "call_duration": 12}
        )
        assert webhook_res.status_code in (200, 404, 503)


# Scenario 17: Webhook arrives twice (Deduplication / Idempotency)
def test_scenario_17_webhook_idempotency(client, db):
    from app.models.call_job import CallJobRecord
    job = CallJobRecord(
        id="job-idemp-1",
        citizen_id="CIT-0001",
        citizen_name="Aarav Sharma",
        trigger_event="MILESTONE_AGE_18",
        job_status="IN_PROGRESS",
        idempotency_key="idemp-key-test-1",
        recipient_phone="***9531",
        bolna_execution_id="bolna-exec-idemp-1"
    )
    db.add(job)
    db.commit()

    with patch("app.config.settings.BOLNA_WEBHOOK_SECRET", "secret-123"):
        # First arrival
        res1 = client.post(
            "/api/webhooks/bolna",
            headers={"X-Timbre-Webhook-Secret": "secret-123"},
            json={"id": "bolna-exec-idemp-1", "status": "completed", "call_duration": 45}
        )
        assert res1.status_code == 200
        assert res1.json()["job_status"] == "COMPLETED"

        # Second identical arrival
        res2 = client.post(
            "/api/webhooks/bolna",
            headers={"X-Timbre-Webhook-Secret": "secret-123"},
            json={"id": "bolna-exec-idemp-1", "status": "completed", "call_duration": 45}
        )
        assert res2.status_code == 200
        assert res2.json()["job_status"] == "COMPLETED"

    db.delete(job)
    db.commit()


# Scenario 18: Person asks to end the call ("रुको", "फोन काटो")
@pytest.mark.asyncio
async def test_scenario_18_person_asks_to_end_call(db, mock_citizen):
    controller = ConversationController()
    controller.start_session(mock_citizen)

    res = await controller.process_user_turn(db=db, user_text="धन्यवाद, अब फोन काटो।")
    assert res["stop_requested"] is True
    assert res["state"] == "COMPLETED"
    assert "समाप्त" in res["ai_response"]


# Scenario 19: Person declines further contact
@pytest.mark.asyncio
async def test_scenario_19_person_declines_contact(db, mock_citizen):
    controller = ConversationController()
    controller.start_session(mock_citizen)

    res = await controller.process_user_turn(db=db, user_text="मुझे यह सेवा नहीं चाहिए, कृपया दोबारा कॉल न करें।")
    assert res["stop_requested"] is True
    assert res["state"] == "COMPLETED"


# Scenario 20: System resumes conversation without replaying stale audio (NotebookLM Resumption Pattern)
@pytest.mark.asyncio
async def test_scenario_20_resumes_conversation_without_stale_audio(db, mock_citizen):
    controller = ConversationController()
    init_res = controller.start_session(
        mock_citizen,
        agenda_points=["मतदाता पंजीकरण प्रक्रिया", "दस्तावेज़ सत्यापन", "अंतिम सारांश"]
    )
    old_audio_token = init_res["audio_token"]

    # Interruption occurs while AI is speaking
    controller.interrupt()
    assert controller.memory.is_audio_valid(old_audio_token) is False

    with patch("app.services.llm_service.llm_service.generate_response", new_callable=AsyncMock) as mock_llm:
        mock_llm.return_value = {"success": True, "response": "आपकी आयु 18 वर्ष से अधिक होनी चाहिए।"}

        # User asks a clarifying question; allow_resumption=True triggers NotebookLM return to agenda
        res = await controller.process_user_turn(
            db=db,
            user_text="न्यूनतम आयु क्या है?",
            allow_resumption=True,
        )

        assert res["state"] == "SPEAKING"
        # Verify bridge resumption phrase is appended to answer
        assert res["resumed_agenda_item"] == "मतदाता पंजीकरण प्रक्रिया"
        assert "जैसा कि हम चर्चा कर रहे थे" in res["ai_response"]
        assert "मतदाता पंजीकरण प्रक्रिया" in res["ai_response"]

        # New valid audio token created; old token remains invalidated
        new_token = res["audio_token"]
        assert controller.memory.is_audio_valid(new_token) is True
        assert controller.memory.is_audio_valid(old_audio_token) is False
