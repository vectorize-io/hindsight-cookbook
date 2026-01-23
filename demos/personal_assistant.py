"""
Personal AI Assistant with Hindsight Memory

A general-purpose personal assistant that remembers your preferences,
schedule, family, work context, and past conversations.

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

USER_ID = "assistant-user-alex"


def remember(info: str, category: str = "general") -> str:
    """
    Store information to remember.

    Args:
        info: Information to remember
        category: Type (reminder, preference, event, person, etc.)
    """
    today = datetime.now().strftime("%B %d, %Y")

    hindsight.retain(
        bank_id=USER_ID,
        content=f"{today}: {info}",
        metadata={"category": category, "date": today},
    )

    return f"I'll remember: {info}"


def recall_context(query: str) -> str:
    """Recall relevant memories for context."""
    memories = hindsight.recall(
        bank_id=USER_ID,
        query=query,
        budget="high",
    )

    if memories and memories.results:
        return "\n".join(f"- {m.text}" for m in memories.results[:8])
    return ""


def chat(user_message: str) -> str:
    """
    Chat with the personal assistant.
    """
    # Get relevant context
    context = recall_context(user_message)

    # Generate response
    system_prompt = f"""You are a helpful personal AI assistant with long-term memory.
You remember the user's preferences, schedule, family, work context, and past conversations.

What you remember about this user:
{context if context else "No memories recorded yet."}

Your capabilities:
- Remember things when asked ("Remember that...", "Don't forget...")
- Recall past information ("What did I tell you about...", "When is...")
- Provide personalized suggestions based on known preferences
- Help with scheduling and reminders
- Have natural conversations while maintaining context

Be helpful, proactive, and reference relevant memories naturally."""

    response = openai_client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_message},
        ],
        temperature=0.7,
        max_tokens=500,
    )

    answer = response.choices[0].message.content

    # Check if user is asking to remember something
    lower_msg = user_message.lower()
    if any(phrase in lower_msg for phrase in ["remember that", "don't forget", "remind me", "note that"]):
        # Extract and store the information
        hindsight.retain(
            bank_id=USER_ID,
            content=f"User asked to remember: {user_message}",
            metadata={"category": "reminder"},
        )

    # Store the interaction
    hindsight.retain(
        bank_id=USER_ID,
        content=f"Conversation - User: {user_message[:100]} | Assistant: {answer[:100]}",
        metadata={"category": "conversation"},
    )

    return answer


def get_summary(topic: str = None) -> str:
    """Get a summary of memories, optionally filtered by topic."""
    query = f"Summarize what you know about {topic}" if topic else \
            "Summarize everything you know about this user"

    summary = hindsight.reflect(
        bank_id=USER_ID,
        query=query,
        budget="high",
    )
    return summary.text if hasattr(summary, 'text') else str(summary)


def main():
    print("=" * 60)
    print("  Personal AI Assistant with Memory")
    print("=" * 60)
    print()

    # Build up context through conversation
    print("Building context...")

    initial_context = [
        ("My name is Alex and I work as a product manager at TechCorp", "personal"),
        ("My wife's name is Sarah and we have two kids: Emma (7) and Jack (4)", "family"),
        ("I prefer morning meetings and try to keep afternoons for deep work", "preference"),
        ("My mom's birthday is March 15th", "event"),
        ("I'm trying to read more - currently reading 'Atomic Habits'", "hobby"),
        ("I have a weekly team standup every Monday at 10am", "schedule"),
        ("I'm allergic to cats", "health"),
        ("My favorite coffee is a flat white with oat milk", "preference"),
        ("I'm training for a half marathon in April", "goal"),
    ]

    for info, category in initial_context:
        result = remember(info, category)
        print(f"  {result}")

    # Interactive conversation
    print("\n" + "=" * 60)
    print("  Conversation")
    print("=" * 60)

    conversations = [
        "Hey, what's my wife's name again?",
        "Remember that my Q1 review is next Thursday at 2pm",
        "I need a gift idea for my mom's birthday",
        "What time is my Monday standup?",
        "Can you recommend a coffee order for me?",
        "What books am I reading?",
        "I finished Atomic Habits! It was great. Now starting 'Deep Work'",
        "What do you know about my work schedule preferences?",
        "Remind me - do I have any health things you should know about if we get a pet?",
        "What should I focus on this month with my training?",
    ]

    for message in conversations:
        print(f"\nAlex: {message}")
        print("-" * 40)
        response = chat(message)
        print(f"Assistant: {response}")

        import time
        time.sleep(1)

    # Summary
    print("\n" + "=" * 60)
    print("  What I Know About You")
    print("=" * 60)
    print(get_summary())

    print("\n" + "=" * 60)
    print("  Your Family")
    print("=" * 60)
    print(get_summary("family"))

    # Clean up client connections
    hindsight.close()


if __name__ == "__main__":
    main()
