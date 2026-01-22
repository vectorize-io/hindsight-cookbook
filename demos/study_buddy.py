"""
Study Buddy with Hindsight Memory

A personalized study assistant that tracks what you've learned,
identifies knowledge gaps, and helps with spaced repetition.

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

USER_ID = "student-physics-101"


def record_study_session(topic: str, notes: str, confidence: str = "medium") -> str:
    """
    Record a study session with topic, notes, and self-assessed confidence.

    Args:
        topic: The topic studied
        notes: Key points or summary of what was learned
        confidence: Self-assessment (low/medium/high)
    """
    today = datetime.now().strftime("%B %d, %Y")

    content = f"""{today} - STUDY SESSION
Topic: {topic}
Confidence Level: {confidence}
Notes: {notes}"""

    hindsight.retain(
        bank_id=USER_ID,
        content=content,
        metadata={
            "category": "study_session",
            "topic": topic,
            "confidence": confidence,
            "date": today,
        },
    )

    return f"Recorded study session on '{topic}' (confidence: {confidence})"


def record_question(topic: str, question: str, understood: bool) -> str:
    """Record a question asked during study, and whether it was understood."""
    today = datetime.now().strftime("%B %d, %Y")

    content = f"""{today} - QUESTION
Topic: {topic}
Question: {question}
Understood: {"Yes" if understood else "No - needs review"}"""

    hindsight.retain(
        bank_id=USER_ID,
        content=content,
        metadata={
            "category": "question",
            "topic": topic,
            "understood": str(understood),
        },
    )

    return f"Recorded question on '{topic}'"


def study_buddy(user_query: str) -> str:
    """
    Interact with the study buddy - ask questions, get explanations,
    or request study recommendations.
    """
    # Recall relevant study history
    memories = hindsight.recall(
        bank_id=USER_ID,
        query=f"study session topic notes questions {user_query}",
        budget="high",
    )

    # Build context from memories
    memory_context = ""
    if memories and memories.results:
        memory_context = "\n".join(
            f"- {m.text}" for m in memories.results[:8]
        )

    # Generate response
    system_prompt = f"""You are a helpful study buddy and tutor.
You have access to the student's study history, including:
- Topics they've studied and their notes
- Their self-assessed confidence levels
- Questions they've asked and whether they understood the answers

Study History:
{memory_context if memory_context else "No study history recorded yet."}

Your role:
1. Answer questions about topics they're studying
2. Identify knowledge gaps based on their history
3. Suggest topics to review (spaced repetition)
4. Provide encouragement and study tips
5. Connect new concepts to things they've already learned

Be supportive and pedagogical. Reference their previous learning when relevant."""

    response = openai_client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_query},
        ],
        temperature=0.7,
        max_tokens=800,
    )

    answer = response.choices[0].message.content

    # Store this interaction
    hindsight.retain(
        bank_id=USER_ID,
        content=f"Student asked: {user_query}\nExplanation given: {answer[:300]}...",
        metadata={"category": "tutoring"},
    )

    return answer


def get_review_suggestions() -> str:
    """Get suggestions for topics to review based on spaced repetition."""
    suggestions = hindsight.reflect(
        bank_id=USER_ID,
        query="""Analyze this student's study history and suggest:
        1. Topics with low confidence that need more review
        2. Topics studied a while ago that should be revisited
        3. Questions that weren't fully understood
        4. Connections between topics they might have missed

        Prioritize by what would most improve their understanding.""",
        budget="high",
    )
    return suggestions.text if hasattr(suggestions, 'text') else str(suggestions)


def get_knowledge_summary(topic: str = None) -> str:
    """Get a summary of what the student knows about a topic (or overall)."""
    query = f"Summarize what this student knows about {topic}" if topic else \
            "Summarize this student's overall knowledge and progress"

    summary = hindsight.reflect(
        bank_id=USER_ID,
        query=query,
        budget="high",
    )
    return summary.text if hasattr(summary, 'text') else str(summary)


def main():
    print("=" * 60)
    print("  Study Buddy with Memory")
    print("=" * 60)
    print()

    # Simulate study sessions over time
    print("Recording study sessions...")

    sessions = [
        {
            "topic": "Classical Mechanics - Newton's Laws",
            "notes": "Covered F=ma, action-reaction pairs, inertia. Solved problems on inclined planes.",
            "confidence": "high",
        },
        {
            "topic": "Classical Mechanics - Conservation of Momentum",
            "notes": "Elastic vs inelastic collisions. Struggled with 2D collision problems.",
            "confidence": "low",
        },
        {
            "topic": "Classical Mechanics - Generalized Coordinates",
            "notes": "Introduction to Lagrangian mechanics. Degrees of freedom concept.",
            "confidence": "medium",
        },
        {
            "topic": "Waves - Simple Harmonic Motion",
            "notes": "SHM equations, period, frequency. Connected to springs and pendulums.",
            "confidence": "high",
        },
        {
            "topic": "Waves - Frequency Domain",
            "notes": "Started Fourier transforms. Math is confusing, need more practice.",
            "confidence": "low",
        },
    ]

    for session in sessions:
        result = record_study_session(**session)
        print(f"  {result}")

    # Record some questions
    print("\nRecording questions...")

    questions = [
        ("Conservation of Momentum", "Why is momentum conserved in collisions?", True),
        ("Conservation of Momentum", "How do I solve 2D collision problems?", False),
        ("Generalized Coordinates", "What's the advantage of Lagrangian over Newtonian?", True),
        ("Frequency Domain", "When do I use Fourier transforms vs Laplace?", False),
    ]

    for topic, question, understood in questions:
        result = record_question(topic, question, understood)
        print(f"  {result}")

    # Interactive study session
    print("\n" + "=" * 60)
    print("  Study Session")
    print("=" * 60)

    queries = [
        "Can you explain generalized coordinates again? I remember we covered it but I'm fuzzy on the details.",
        "What topics should I review before my exam next week?",
        "I'm still confused about 2D collision problems. Can you walk me through an example?",
        "How does Fourier transform connect to what I learned about SHM?",
        "What are my biggest knowledge gaps right now?",
    ]

    for query in queries:
        print(f"\nStudent: {query}")
        print("-" * 40)
        response = study_buddy(query)
        print(f"Study Buddy: {response}")

        import time
        time.sleep(1)

    # Get review suggestions
    print("\n" + "=" * 60)
    print("  Recommended Review Topics")
    print("=" * 60)
    print(get_review_suggestions())

    # Get knowledge summary
    print("\n" + "=" * 60)
    print("  Knowledge Summary")
    print("=" * 60)
    print(get_knowledge_summary())

    # Clean up client connections
    hindsight.close()


if __name__ == "__main__":
    main()
