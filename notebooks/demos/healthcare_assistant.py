"""
Healthcare Assistant with Hindsight Memory

A supportive healthcare chatbot that remembers patient history,
symptoms, medications, and preferences to provide personalized guidance.

DISCLAIMER: This is a demo application and should NOT be used for actual
medical advice. Always consult qualified healthcare professionals.

Requirements:
    pip install hindsight-client openai

Environment Variables:
    HINDSIGHT_API_KEY - Your Hindsight API key
    OPENAI_API_KEY - Your OpenAI API key
"""

import os
from datetime import datetime
from openai import OpenAI
from hindsight_client import Hindsight

# Initialize clients
hindsight = Hindsight(
    api_key=os.getenv("HINDSIGHT_API_KEY"),
    base_url=os.getenv("HINDSIGHT_BASE_URL", "https://api.hindsight.vectorize.io"),
)

openai_client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))


def get_patient_bank_id(patient_id: str) -> str:
    """Generate bank ID for a patient."""
    return f"patient-{patient_id}"


def store_patient_info(patient_id: str, info: str, category: str = "general") -> str:
    """
    Store patient information (symptoms, allergies, medications, etc.)

    Args:
        patient_id: Unique patient identifier
        info: Information to store
        category: Type of info (symptoms, allergies, medications, vitals, etc.)
    """
    bank_id = get_patient_bank_id(patient_id)
    today = datetime.now().strftime("%B %d, %Y")

    hindsight.retain(
        bank_id=bank_id,
        content=f"{today} - {category.upper()}: {info}",
        metadata={"category": category, "date": today},
    )

    return f"Recorded {category}: {info}"


def get_patient_history(patient_id: str, query: str) -> str:
    """Retrieve relevant patient history."""
    bank_id = get_patient_bank_id(patient_id)

    memories = hindsight.recall(
        bank_id=bank_id,
        query=query,
        budget="high",
    )

    if memories and memories.results:
        return "\n".join(f"- {m.text}" for m in memories.results[:10])
    return "No relevant history found."


def healthcare_chat(patient_id: str, user_message: str) -> str:
    """
    Chat with the healthcare assistant.
    """
    bank_id = get_patient_bank_id(patient_id)

    # Retrieve relevant patient history
    history = get_patient_history(
        patient_id,
        f"symptoms medications allergies conditions {user_message}"
    )

    # Generate response
    system_prompt = f"""You are a supportive healthcare assistant chatbot.

IMPORTANT DISCLAIMERS:
- You are NOT a doctor and cannot provide medical diagnoses
- Always recommend consulting healthcare professionals for serious concerns
- Never prescribe medications or suggest stopping prescribed treatments

Your role:
- Listen empathetically to patient concerns
- Remember and reference their medical history
- Provide general health information and wellness tips
- Help track symptoms over time
- Remind about medications and appointments
- Suggest when to seek professional care

Patient History:
{history}

Guidelines:
- Be warm and supportive
- Ask clarifying questions when needed
- Reference their history when relevant
- Flag any concerning symptoms for professional review"""

    response = openai_client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_message},
        ],
        temperature=0.7,
        max_tokens=600,
    )

    answer = response.choices[0].message.content

    # Store this interaction
    hindsight.retain(
        bank_id=bank_id,
        content=f"Patient concern: {user_message}\nGuidance provided: {answer[:200]}...",
        metadata={"category": "consultation"},
    )

    return answer


def get_health_summary(patient_id: str) -> str:
    """Generate a health summary for the patient."""
    bank_id = get_patient_bank_id(patient_id)

    summary = hindsight.reflect(
        bank_id=bank_id,
        query="""Summarize this patient's health profile:
        1. Known conditions and diagnoses
        2. Current medications
        3. Allergies and sensitivities
        4. Recent symptoms reported
        5. Lifestyle factors mentioned
        6. Any patterns or trends in their health""",
        budget="high",
    )
    return summary.text if hasattr(summary, 'text') else str(summary)


def schedule_appointment(patient_id: str, appointment_type: str, preferred_time: str) -> str:
    """Schedule an appointment (demo - generates mock confirmation)."""
    import random
    confirmation_id = f"APT-{random.randint(10000, 99999)}"

    store_patient_info(
        patient_id,
        f"Appointment scheduled: {appointment_type} - Preferred time: {preferred_time} - Confirmation: {confirmation_id}",
        category="appointment"
    )

    return f"Appointment requested: {appointment_type}\nPreferred time: {preferred_time}\nConfirmation ID: {confirmation_id}\n\nA staff member will confirm the exact time within 24 hours."


def main():
    print("=" * 60)
    print("  Healthcare Assistant with Memory")
    print("=" * 60)
    print("\nDISCLAIMER: This is a demo. Not for real medical advice.")
    print()

    patient_id = "john-doe-123"

    # Set up patient profile
    print("Setting up patient profile...")

    patient_info = [
        ("Age: 45, Male, Height: 5'11\", Weight: 185 lbs", "demographics"),
        ("Allergy: Penicillin - causes hives", "allergies"),
        ("Allergy: Shellfish - causes throat swelling", "allergies"),
        ("Current medication: Lisinopril 10mg daily for blood pressure", "medications"),
        ("Current medication: Metformin 500mg twice daily for Type 2 diabetes", "medications"),
        ("Condition: Diagnosed with Type 2 diabetes in 2020", "conditions"),
        ("Condition: Mild hypertension, well-controlled", "conditions"),
        ("Family history: Father had heart disease", "family_history"),
        ("Lifestyle: Sedentary job, trying to exercise more", "lifestyle"),
    ]

    for info, category in patient_info:
        result = store_patient_info(patient_id, info, category)
        print(f"  {result}")

    # Simulate conversation
    print("\n" + "=" * 60)
    print("  Healthcare Chat")
    print("=" * 60)

    conversations = [
        "Hi, I've been having headaches for the past few days. Should I be worried?",
        "The headaches are mostly in the afternoon. I've also been feeling more tired than usual.",
        "I've been checking my blood sugar and it's been a bit higher lately, around 140-150 fasting.",
        "Should I adjust my Metformin dose?",
        "Can you remind me what allergies I have? I'm going to a new restaurant.",
        "I'd like to schedule a check-up with my doctor.",
    ]

    for message in conversations:
        print(f"\nPatient: {message}")
        print("-" * 40)
        response = healthcare_chat(patient_id, message)
        print(f"Assistant: {response}")

        import time
        time.sleep(1)

    # Schedule appointment
    print("\n" + "=" * 60)
    print("  Scheduling Appointment")
    print("=" * 60)
    print(schedule_appointment(patient_id, "General checkup", "Next Tuesday afternoon"))

    # Health summary
    print("\n" + "=" * 60)
    print("  Patient Health Summary")
    print("=" * 60)
    print(get_health_summary(patient_id))

    # Clean up client connections
    hindsight.close()


if __name__ == "__main__":
    main()
