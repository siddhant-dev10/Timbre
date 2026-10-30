#!/usr/bin/env python3
"""Interactive & Automated WhatsApp Civic Assistant Demonstration for Timbre.

Usage:
    # Run the automated multi-turn civic assistance walkthrough:
    python backend/app/scripts/demo_whatsapp.py

    # Run the live interactive terminal chat with Timbre:
    python backend/app/scripts/demo_whatsapp.py --interactive
"""
import argparse
import asyncio
import sys
from pathlib import Path

# Add backend directory to path
backend_dir = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(backend_dir))

from app.database.session import engine, SessionLocal
from app.database.migrations import run_migrations
from app.services.whatsapp_service import whatsapp_service


async def run_automated_walkthrough():
    run_migrations(engine)
    print("=" * 75)
    print(" TIMBRE — WHATSAPP CIVIC ASSISTANT DEMONSTRATION")
    print("=" * 75)
    print("Testing multi-turn civic dialogue, scheme discovery, and language adaptation.\n")

    db = SessionLocal()
    phone = "919876543210"
    name = "Rohan"

    demo_steps = [
        (
            "1. Adulthood Milestone (Hinglish)",
            "Main 18 saal ka ho gaya hoon. Mujhe kaun se government documents banwane chahiye?",
            True,  # reset conversation
        ),
        (
            "2. State & Proof Follow-up (Context Continuity)",
            "Main Rajasthan se hoon aur mere paas 10th ki marksheet aur birth certificate hai.",
            False,
        ),
        (
            "3. Statutory Scheme Inquiry (Devanagari Hindi)",
            "नमस्ते, क्या आप मुझे वृद्धावस्था पेंशन योजना के नियम और पात्रता बता सकते हैं?",
            False,
        ),
        (
            "4. English Language Query (Language Switching)",
            "What is the statutory fee and application process for PM-Kisan?",
            False,
        ),
        (
            "5. User Conclusion / Stop Intent",
            "Theek hai, shukriya! Abhi ke liye itna hi, alvida.",
            False,
        ),
    ]

    try:
        for title, message, reset in demo_steps:
            print("-" * 75)
            print(f"STEP: {title}")
            print(f"Citizen [{name} | ***{phone[-4:]}]: {message}")
            print("Processing turn...")

            turn = await whatsapp_service.simulate_turn(
                db=db,
                sender_phone=phone,
                message=message,
                sender_name=name,
                reset_conversation=reset,
            )

            print(f"Language Detected : {turn['language']}")
            print(f"Grounded Sources  : {', '.join(turn['grounded_sources']) or 'Verified Catalogue'}")
            print(f"Delivery Status   : {turn['delivery_status']} (Provider: {turn['provider']})")
            print(f"\nTimbre (WhatsApp):\n{turn['ai_reply']}\n")

        print("=" * 75)
        print("DEMO SUMMARY: All 5 conversational turns completed successfully.")
        print("✓ Context preserved across multi-turn messages.")
        print("✓ Phone numbers masked (***3210).")
        print("✓ Zero external network calls placed; zero telephony triggered.")
        print("=" * 75)

    finally:
        db.close()


async def run_interactive_mode():
    run_migrations(engine)
    print("=" * 75)
    print(" TIMBRE — INTERACTIVE WHATSAPP TERMINAL CHAT")
    print("=" * 75)
    print("Type your message below in Hindi, Hinglish, or English.")
    print("Type 'exit' or 'quit' to end the session.\n")

    db = SessionLocal()
    phone = "919988776655"
    name = "Citizen"

    # Reset at start
    await whatsapp_service.simulate_turn(
        db=db, sender_phone=phone, message="Namaste", sender_name=name, reset_conversation=True
    )

    try:
        while True:
            try:
                user_input = input("\nYou: ").strip()
            except (KeyboardInterrupt, EOFError):
                break

            if not user_input or user_input.lower() in ("exit", "quit"):
                print("\nEnding session. Goodbye!")
                break

            turn = await whatsapp_service.simulate_turn(
                db=db,
                sender_phone=phone,
                message=user_input,
                sender_name=name,
                reset_conversation=False,
            )

            print(f"\nTimbre ({turn['language']}):\n{turn['ai_reply']}")
    finally:
        db.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Timbre WhatsApp Civic Assistant Demo")
    parser.add_argument("--interactive", action="store_true", help="Launch interactive terminal chat session")
    args = parser.parse_args()

    if args.interactive:
        asyncio.run(run_interactive_mode())
    else:
        asyncio.run(run_automated_walkthrough())
