"""
Movie Recommendation Assistant with Hindsight Memory

A personalized movie recommender that remembers your preferences,
watch history, and tastes to give better suggestions over time.

Requirements:
    pip install hindsight-client openai

Environment Variables:
    HINDSIGHT_API_KEY - Your Hindsight API key
    OPENAI_API_KEY - Your OpenAI API key
"""

import os
from openai import OpenAI
from hindsight_client import Hindsight

# Initialize clients
hindsight = Hindsight(
    api_key=os.getenv("HINDSIGHT_API_KEY"),
    base_url=os.getenv("HINDSIGHT_BASE_URL", "https://api.hindsight.vectorize.io"),
)

openai_client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

USER_ID = "movie-fan-123"


def get_recommendation(user_query: str) -> str:
    """
    Get a movie recommendation based on user query and remembered preferences.
    """
    # Recall relevant memories about this user's movie preferences
    memories = hindsight.recall(
        bank_id=USER_ID,
        query=f"movie preferences tastes genres {user_query}",
        budget="mid",
    )

    # Build context from memories
    memory_context = ""
    if memories and memories.results:
        memory_context = "\n".join(
            f"- {m.text}" for m in memories.results[:5]
        )

    # Generate recommendation with context
    system_prompt = f"""You are a helpful movie recommendation assistant.
You remember the user's preferences and past conversations to give personalized suggestions.

What you know about this user:
{memory_context if memory_context else "No previous preferences recorded yet."}

Give thoughtful, personalized recommendations based on their tastes.
If they mention new preferences, acknowledge them."""

    response = openai_client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_query},
        ],
        temperature=0.7,
        max_tokens=500,
    )

    recommendation = response.choices[0].message.content

    # Store this interaction for future context
    hindsight.retain(
        bank_id=USER_ID,
        content=f"User asked: {user_query}\nRecommendation given: {recommendation}",
        metadata={"category": "movie_recommendation"},
    )

    return recommendation


def store_preference(preference: str) -> None:
    """Store an explicit user preference."""
    hindsight.retain(
        bank_id=USER_ID,
        content=f"User preference: {preference}",
        metadata={"category": "preference"},
    )
    print(f"Stored preference: {preference}")


def get_preference_summary() -> str:
    """Get a summary of what we know about the user's movie tastes."""
    summary = hindsight.reflect(
        bank_id=USER_ID,
        query="Summarize this user's movie preferences, favorite genres, actors they like, and movies they've mentioned enjoying or disliking.",
        budget="high",
    )
    return summary.text if hasattr(summary, 'text') else str(summary)


def main():
    print("=" * 60)
    print("  Movie Recommendation Assistant with Memory")
    print("=" * 60)
    print()

    # Simulate a conversation over time
    conversations = [
        "I'm looking for a movie to watch tonight. Any suggestions?",
        "I really loved Inception and Interstellar. Christopher Nolan is amazing!",
        "Can you suggest something similar to those? I like mind-bending plots.",
        "Actually, I'm not in the mood for something heavy. Something lighter?",
        "I watched The Grand Budapest Hotel last week and loved it!",
        "What should I watch tonight? Remember what I like!",
    ]

    for i, query in enumerate(conversations, 1):
        print(f"\n[Conversation {i}]")
        print(f"User: {query}")
        print("-" * 40)

        response = get_recommendation(query)
        print(f"Assistant: {response}")
        print()

        # Small delay to simulate real conversation
        import time
        time.sleep(1)

    # Show what we've learned
    print("\n" + "=" * 60)
    print("  What I've learned about your movie tastes:")
    print("=" * 60)
    print(get_preference_summary())

    # Clean up client connections
    hindsight.close()


if __name__ == "__main__":
    main()
