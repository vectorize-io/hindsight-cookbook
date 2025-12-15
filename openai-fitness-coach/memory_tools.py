#!/usr/bin/env python3
"""
Memory tools for OpenAI Agent to interact with Hindsight.

These functions are called by the OpenAI Agent via function calling
to store and retrieve memories from the Hindsight backend.
"""
import requests
from typing import List, Dict, Optional
from datetime import datetime

API_URL = "http://localhost:8888/api/v1"
AGENT_ID = "fitness-coach"


def retrieve_memories(
    query: str,
    fact_types: Optional[List[str]] = None,
    top_k: int = 20
) -> Dict:
    """
    Retrieve relevant memories from Hindsight based on a query.

    Args:
        query: Search query describing what memories to retrieve
        fact_types: Types of facts to search (world, agent, opinion)
        top_k: Number of results to return

    Returns:
        Dictionary with search results
    """
    payload = {
        "agent_id": AGENT_ID,
        "query": query,
        "fact_type": fact_types or ["world", "agent", "opinion"],
        "thinking_budget": 100,
        "top_k": top_k
    }

    try:
        response = requests.post(
            f"{API_URL}/agents/{AGENT_ID}/memories/search",
            json=payload,
            timeout=30
        )

        if response.status_code == 200:
            return response.json()
        else:
            return {"error": f"Failed to retrieve memories: {response.status_code}"}

    except Exception as e:
        return {"error": str(e)}


def search_workouts(
    after_date: Optional[str] = None,
    before_date: Optional[str] = None,
    workout_type: Optional[str] = None
) -> Dict:
    """
    Search for workout history within a date range.

    Args:
        after_date: Search workouts after this date (YYYY-MM-DD)
        before_date: Search workouts before this date (YYYY-MM-DD)
        workout_type: Filter by workout type (cardio, strength, yoga, running, etc.)

    Returns:
        Dictionary with workout results
    """
    query_parts = []

    if workout_type:
        # Handle variations: "running" -> "run running cardio"
        if workout_type.lower() in ["running", "run"]:
            query_parts.append("run running cardio distance pace")
        elif workout_type.lower() in ["cycling", "ride", "bike"]:
            query_parts.append("ride cycling bike")
        elif workout_type.lower() in ["swimming", "swim"]:
            query_parts.append("swim swimming")
        else:
            query_parts.append(workout_type)
    else:
        # General workout query
        query_parts.append("workout exercise training activity completed")

    if after_date:
        query_parts.append(f"after {after_date}")
    if before_date:
        query_parts.append(f"before {before_date}")

    query = " ".join(query_parts)

    return retrieve_memories(
        query=query,
        fact_types=["world", "agent"],
        top_k=50
    )


def get_nutrition_summary(
    after_date: Optional[str] = None,
    before_date: Optional[str] = None
) -> Dict:
    """
    Get nutrition/meal history within a date range.

    Args:
        after_date: Get meals after this date (YYYY-MM-DD)
        before_date: Get meals before this date (YYYY-MM-DD)

    Returns:
        Dictionary with meal results
    """
    query_parts = ["meal", "nutrition", "food", "ate", "calories", "protein"]
    if after_date:
        query_parts.append(f"after {after_date}")
    if before_date:
        query_parts.append(f"before {before_date}")

    query = " ".join(query_parts)

    return retrieve_memories(
        query=query,
        fact_types=["world", "agent"],
        top_k=30
    )


def get_user_goals() -> Dict:
    """
    Retrieve the user's fitness goals.

    Returns:
        Dictionary with goal results
    """
    return retrieve_memories(
        query="fitness goals objectives targets",
        fact_types=["agent"],
        top_k=10
    )


def get_coach_opinions(about: Optional[str] = None) -> Dict:
    """
    Retrieve opinions the coach has formed about the user.

    Args:
        about: Optional topic to filter opinions (e.g., "consistency", "nutrition")

    Returns:
        Dictionary with opinion results
    """
    query = about if about else "user behavior patterns habits"

    return retrieve_memories(
        query=query,
        fact_types=["opinion"],
        top_k=20
    )


def store_memory(
    content: str,
    memory_type: str = "world",
    context: Optional[str] = None,
    event_date: Optional[str] = None
) -> Dict:
    """
    Store a new memory in Hindsight.

    Args:
        content: The memory content/description
        memory_type: Type of memory (world, agent, opinion)
        context: Optional context/category
        event_date: Optional event date (ISO format)

    Returns:
        Dictionary with storage result
    """
    payload = {
        "agent_id": AGENT_ID,
        "items": [{
            "content": content,
            "context": context or "general",
            "event_date": event_date or datetime.now().isoformat(),
            "memory_type": memory_type
        }]
    }

    try:
        response = requests.post(
            f"{API_URL}/agents/{AGENT_ID}/memories",
            json=payload,
            timeout=30
        )

        if response.status_code == 200:
            return {"success": True, "message": "Memory stored successfully"}
        else:
            return {"success": False, "error": f"Failed to store memory: {response.status_code}"}

    except Exception as e:
        return {"success": False, "error": str(e)}


# Tool definitions for OpenAI function calling
MEMORY_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "retrieve_memories",
            "description": "General memory search across all user data workouts, meals and goals. Use this as your primary search tool when you need comprehensive context. Supports semantic search with natural language queries.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Natural language query - be descriptive. Examples: 'all running activities', 'recent 5K runs', 'fastest pace', 'training last month', 'nutrition this week'"
                    },
                    "fact_types": {
                        "type": "array",
                        "items": {
                            "type": "string",
                            "enum": ["world", "agent", "opinion"]
                        },
                        "description": "Types of facts to retrieve. IMPORTANT: Leave this empty or include ALL types ['world', 'agent', 'opinion'] to ensure you retrieve all relevant memories. Filtering by specific types may miss important data."
                    },
                    "top_k": {
                        "type": "integer",
                        "description": "Number of results to return. IMPORTANT: Use at least 20-30 to ensure you get all relevant context including preferences. Default: 20",
                        "default": 20
                    }
                },
                "required": ["query"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "search_workouts",
            "description": "Search for workout and activity history including runs, rides, swims, strength training. Use this for questions about training, running, cycling, exercise patterns, distances, paces.",
            "parameters": {
                "type": "object",
                "properties": {
                    "after_date": {
                        "type": "string",
                        "description": "Search workouts after this date (YYYY-MM-DD format)"
                    },
                    "before_date": {
                        "type": "string",
                        "description": "Search workouts before this date (YYYY-MM-DD format)"
                    },
                    "workout_type": {
                        "type": "string",
                        "description": "Filter by workout type. Use 'running' for runs, 'cycling' for rides, 'swimming' for swims, 'strength' for gym workouts, 'yoga' for yoga/stretching"
                    }
                },
                "required": []
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_nutrition_summary",
            "description": "Get the user's meal and nutrition history within a date range.",
            "parameters": {
                "type": "object",
                "properties": {
                    "after_date": {
                        "type": "string",
                        "description": "Get meals after this date (YYYY-MM-DD format)"
                    },
                    "before_date": {
                        "type": "string",
                        "description": "Get meals before this date (YYYY-MM-DD format)"
                    }
                },
                "required": []
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_user_goals",
            "description": "Retrieve the user's fitness goals and objectives.",
            "parameters": {
                "type": "object",
                "properties": {},
                "required": []
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_coach_opinions",
            "description": "Get opinions and observations the coach has formed about the user's behavior patterns and habits.",
            "parameters": {
                "type": "object",
                "properties": {
                    "about": {
                        "type": "string",
                        "description": "Optional topic to filter opinions (e.g., 'consistency', 'nutrition', 'recovery')"
                    }
                },
                "required": []
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "store_memory",
            "description": "Store new information. CRITICAL: You must use this in TWO situations: (1) When user tells you about workouts/meals/goals - store as 'world' or 'agent', AND (2) When YOU give advice or recognize achievements - store as 'opinion'. Always store your own coaching observations so you can reference them later!",
            "parameters": {
                "type": "object",
                "properties": {
                    "content": {
                        "type": "string",
                        "description": "Description of what happened. Be specific and include details like distances, times, paces, foods, quantities, etc."
                    },
                    "memory_type": {
                        "type": "string",
                        "enum": ["world", "agent", "opinion"],
                        "description": "Type of memory: 'world' for things user did (workouts, meals), 'agent' for user's goals/intentions, 'opinion' for YOUR coaching advice and observations. YOU MUST use 'opinion' when storing advice you give!"
                    },
                    "context": {
                        "type": "string",
                        "description": "Category/context (e.g., 'workout-running', 'meal-breakfast', 'goal', 'coaching-advice', 'coaching-observation')"
                    },
                    "event_date": {
                        "type": "string",
                        "description": "When this happened in ISO format (YYYY-MM-DDTHH:MM:SS). Use current time if user doesn't specify."
                    }
                },
                "required": ["content", "memory_type"]
            }
        }
    }
]


# Map function names to actual functions
FUNCTION_MAP = {
    "retrieve_memories": retrieve_memories,
    "search_workouts": search_workouts,
    "get_nutrition_summary": get_nutrition_summary,
    "get_user_goals": get_user_goals,
    "get_coach_opinions": get_coach_opinions,
    "store_memory": store_memory
}
