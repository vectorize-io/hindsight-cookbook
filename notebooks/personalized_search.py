"""
Personalized Search Agent with Hindsight Memory

A search assistant that learns your preferences, location, dietary needs,
and lifestyle to provide contextually relevant search results.

Requirements:
    pip install hindsight-client openai tavily-python

Environment Variables:
    HINDSIGHT_API_KEY - Your Hindsight API key
    OPENAI_API_KEY - Your OpenAI API key
    TAVILY_API_KEY - Your Tavily API key (for web search)
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

# Optional: Tavily for real web search
try:
    from tavily import TavilyClient
    tavily = TavilyClient(api_key=os.getenv("TAVILY_API_KEY"))
    HAS_TAVILY = True
except (ImportError, Exception) as e:
    HAS_TAVILY = False
    if "ImportError" in type(e).__name__:
        print("Note: Tavily not installed. Using simulated search results.")
    else:
        print("Note: Tavily API key not configured. Using simulated search results.")

USER_ID = "search-user-sarah"


def store_preference(preference: str) -> str:
    """Store a user preference learned from conversation."""
    hindsight.retain(
        bank_id=USER_ID,
        content=f"User preference: {preference}",
        metadata={"category": "preference"},
    )
    return f"Learned: {preference}"


def store_interaction(query: str, response: str) -> None:
    """Store a search interaction for future context."""
    hindsight.retain(
        bank_id=USER_ID,
        content=f"Search query: {query}\nResult highlights: {response[:200]}",
        metadata={"category": "search_history"},
    )


def get_user_context(query: str) -> str:
    """Retrieve relevant user context for personalizing search."""
    memories = hindsight.recall(
        bank_id=USER_ID,
        query=f"preferences location dietary lifestyle {query}",
        budget="mid",
    )

    if memories and memories.results:
        return "\n".join(f"- {m.text}" for m in memories.results[:6])
    return ""


def personalized_search(query: str) -> str:
    """
    Perform a search personalized to the user's preferences and context.
    """
    # Get user context
    user_context = get_user_context(query)

    # Enhance the query based on user preferences
    enhancement_prompt = f"""Given this user's preferences and the search query, suggest how to enhance the search.

User preferences:
{user_context if user_context else "No preferences recorded yet."}

Search query: {query}

Return a JSON object with:
- "enhanced_query": The improved search query incorporating relevant preferences
- "filters": Any specific filters to apply (e.g., "vegetarian", "within 5 miles")
- "reasoning": Brief explanation of personalizations applied"""

    enhancement = openai_client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": enhancement_prompt}],
        temperature=0.3,
        max_tokens=300,
    )

    enhanced_info = enhancement.choices[0].message.content

    # Perform the search (real or simulated)
    if HAS_TAVILY:
        search_results = tavily.search(
            query=query,
            search_depth="advanced",
            max_results=5,
        )
        results_text = "\n".join(
            f"- {r['title']}: {r['content'][:150]}..."
            for r in search_results.get('results', [])
        )
    else:
        # Simulated search results for demo
        results_text = f"[Simulated search results for: {query}]"

    # Generate personalized response
    response_prompt = f"""Based on the search results and user preferences, provide a personalized summary.

User preferences:
{user_context if user_context else "No preferences recorded yet."}

Query: {query}

Search enhancement applied:
{enhanced_info}

Search results:
{results_text}

Provide a helpful, personalized response that takes into account their preferences."""

    response = openai_client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": response_prompt}],
        temperature=0.7,
        max_tokens=500,
    )

    answer = response.choices[0].message.content

    # Store this interaction
    store_interaction(query, answer)

    return answer


def get_preference_profile() -> str:
    """Get a summary of the user's preference profile."""
    profile = hindsight.reflect(
        bank_id=USER_ID,
        query="""Summarize what we know about this user:
        - Location and neighborhood
        - Dietary preferences and restrictions
        - Work style and schedule
        - Hobbies and interests
        - Family situation
        - Shopping preferences""",
        budget="high",
    )
    return profile.text if hasattr(profile, 'text') else str(profile)


def main():
    print("=" * 60)
    print("  Personalized Search Agent with Memory")
    print("=" * 60)
    print()

    # Build up user profile through simulated conversation history
    print("Learning user preferences...")

    preferences = [
        "Lives in San Francisco, Mission District",
        "Works remotely as a software engineer",
        "Vegetarian, prefers organic food when possible",
        "Has a 5-year-old daughter named Emma",
        "Enjoys hiking and outdoor activities on weekends",
        "Prefers quiet coffee shops for remote work",
        "Lactose intolerant, uses oat milk",
        "Interested in sustainable and eco-friendly products",
        "Usually free on Tuesday and Thursday afternoons",
        "Husband is allergic to nuts",
    ]

    for pref in preferences:
        result = store_preference(pref)
        print(f"  {result}")

    # Perform personalized searches
    print("\n" + "=" * 60)
    print("  Personalized Search Results")
    print("=" * 60)

    searches = [
        "Find a good coffee shop for working remotely",
        "Restaurant recommendations for a family dinner",
        "Birthday gift ideas for a 5-year-old",
        "Best hiking trails near me",
        "Grocery delivery services",
    ]

    for query in searches:
        print(f"\nSearch: {query}")
        print("-" * 40)
        result = personalized_search(query)
        print(result)

        import time
        time.sleep(1)

    # Show preference profile
    print("\n" + "=" * 60)
    print("  User Preference Profile")
    print("=" * 60)
    print(get_preference_profile())

    # Clean up client connections
    hindsight.close()


if __name__ == "__main__":
    main()
