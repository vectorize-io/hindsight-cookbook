"""
Fitness Coach with Hindsight Memory

A personalized fitness assistant that tracks your workouts, diet,
recovery, and progress over time to give contextual advice.

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

USER_ID = "fitness-user-anish"


def log_workout(workout_details: str) -> str:
    """Log a workout session with timestamp."""
    today = datetime.now().strftime("%B %d, %Y")

    hindsight.retain(
        bank_id=USER_ID,
        content=f"{today} - WORKOUT LOG: {workout_details}",
        metadata={"category": "workout", "date": today},
    )

    return f"Logged workout for {today}: {workout_details}"


def log_meal(meal_details: str) -> str:
    """Log a meal with timestamp."""
    today = datetime.now().strftime("%B %d, %Y")

    hindsight.retain(
        bank_id=USER_ID,
        content=f"{today} - MEAL LOG: {meal_details}",
        metadata={"category": "nutrition", "date": today},
    )

    return f"Logged meal for {today}: {meal_details}"


def log_recovery(recovery_details: str) -> str:
    """Log recovery information (sleep, soreness, etc.)."""
    today = datetime.now().strftime("%B %d, %Y")

    hindsight.retain(
        bank_id=USER_ID,
        content=f"{today} - RECOVERY LOG: {recovery_details}",
        metadata={"category": "recovery", "date": today},
    )

    return f"Logged recovery for {today}: {recovery_details}"


def store_user_profile(profile_info: str) -> str:
    """Store user profile information (age, weight, goals, restrictions)."""
    hindsight.retain(
        bank_id=USER_ID,
        content=f"USER PROFILE: {profile_info}",
        metadata={"category": "profile"},
    )

    return f"Stored profile info: {profile_info}"


def fitness_coach(user_query: str) -> str:
    """
    Get personalized fitness advice based on query and user history.
    """
    # Recall relevant memories
    memories = hindsight.recall(
        bank_id=USER_ID,
        query=f"fitness workout diet recovery goals {user_query}",
        budget="high",
    )

    # Build context from memories
    memory_context = ""
    if memories and memories.results:
        memory_context = "\n".join(
            f"- {m.text}" for m in memories.results[:10]
        )

    # Generate personalized advice
    system_prompt = f"""You are a knowledgeable and supportive fitness coach.
You have access to the user's workout history, diet logs, recovery notes, and personal profile.

What you know about this user:
{memory_context if memory_context else "No history recorded yet."}

Provide personalized, actionable advice based on their:
- Training history and progress
- Dietary preferences and restrictions
- Recovery patterns
- Personal goals

Be encouraging but realistic. Reference their specific history when relevant."""

    response = openai_client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_query},
        ],
        temperature=0.7,
        max_tokens=600,
    )

    advice = response.choices[0].message.content

    # Store the interaction
    hindsight.retain(
        bank_id=USER_ID,
        content=f"User asked: {user_query}\nCoach advised: {advice[:200]}...",
        metadata={"category": "coaching"},
    )

    return advice


def get_progress_report() -> str:
    """Generate a progress report based on workout history."""
    report = hindsight.reflect(
        bank_id=USER_ID,
        query="""Analyze this user's fitness journey:
        1. How consistent have they been with workouts?
        2. What progress have they made (weight lifted, exercises)?
        3. How is their recovery and sleep?
        4. What dietary patterns do you notice?
        5. What should they focus on next?""",
        budget="high",
    )
    return report.text if hasattr(report, 'text') else str(report)


def main():
    print("=" * 60)
    print("  Fitness Coach with Memory")
    print("=" * 60)
    print()

    # Set up user profile
    print("Setting up user profile...")
    profile_data = [
        "Name: Anish, Age: 26, Height: 5'10\", Weight: 72kg",
        "Goal: Building lean muscle, started gym 6 months ago",
        "Routine: Push-pull-legs split, 5x per week",
        "Rest days: Wednesday and Sunday",
        "Dietary restriction: Mild lactose intolerance, uses almond milk",
        "Health note: Occasional knee pain, avoids deep squats",
        "Supplements: Whey protein (lactose-free), magnesium",
        "Sleep: Aims for 7+ hours, performance drops under 6 hours",
    ]

    for info in profile_data:
        store_user_profile(info)
        print(f"  Stored: {info[:50]}...")

    # Log some workout history
    print("\nLogging workout history...")
    workouts = [
        "Push day: Bench press 3x8 @ 60kg, overhead press 4x12, tricep dips 3x10. Felt strong.",
        "Pull day: Deadlift 3x5 @ 80kg, barbell rows 4x10, bicep curls 3x12. Good session.",
        "Leg day: Leg press 4x12, hamstring curls 3x12, glute bridges 3x15. Knee felt okay.",
    ]

    for workout in workouts:
        print(f"  {log_workout(workout)[:60]}...")

    # Log meals
    print("\nLogging recent meals...")
    meals = [
        "Post-workout: Whey shake with almond milk, banana, oats",
        "Dinner: Grilled chicken, brown rice, steamed vegetables",
        "Snack: Greek yogurt (lactose-free) with berries",
    ]

    for meal in meals:
        print(f"  {log_meal(meal)[:60]}...")

    # Log recovery
    print("\nLogging recovery notes...")
    recovery = [
        "Slept 7.5 hours, feeling well rested",
        "Some DOMS in legs from yesterday, using turmeric milk",
    ]

    for note in recovery:
        print(f"  {log_recovery(note)[:60]}...")

    # Now interact with the coach
    print("\n" + "=" * 60)
    print("  Talking to your fitness coach...")
    print("=" * 60)

    queries = [
        "How much was I lifting for bench press recently?",
        "I slept poorly last night (only 5 hours). What should I do for today's workout?",
        "Suggest a post-workout meal that works with my dietary restrictions.",
        "My knee has been bothering me more. Any exercise modifications?",
        "Give me a summary of how I've been doing overall.",
    ]

    for query in queries:
        print(f"\nUser: {query}")
        print("-" * 40)
        response = fitness_coach(query)
        print(f"Coach: {response}")

        import time
        time.sleep(1)

    # Generate progress report
    print("\n" + "=" * 60)
    print("  Progress Report")
    print("=" * 60)
    print(get_progress_report())

    # Clean up client connections
    hindsight.close()


if __name__ == "__main__":
    main()
