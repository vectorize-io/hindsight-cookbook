"""
Hindsight Memory Integration Module

Uses hindsight_litellm package for memory operations.
"""

import os
import uuid
import hindsight_litellm
from typing import Optional, Tuple


# Current bank ID (set per session)
_current_bank_id: str = None


def configure_memory(api_url: str = None, verbose: bool = False, session_id: str = None):
    """
    Configure hindsight_litellm for the delivery agent.

    Args:
        api_url: Hindsight API URL (defaults to HINDSIGHT_API_URL env var or localhost:8888)
        verbose: Enable debug logging
        session_id: Unique session ID (generated if not provided)
    """
    global _current_bank_id

    url = api_url or os.environ.get("HINDSIGHT_API_URL", "http://localhost:8888")

    # Generate unique bank ID per session
    if session_id:
        _current_bank_id = f"delivery-agent-{session_id}"
    else:
        _current_bank_id = f"delivery-agent-{uuid.uuid4().hex[:8]}"

    hindsight_litellm.configure(
        hindsight_api_url=url,
        bank_id=_current_bank_id,
        bank_name="Delivery Agent Memory",
        store_conversations=False,  # Disabled - we manually store observations via retain()
        inject_memories=True,
        use_reflect=False,  # Use raw memories for precise location facts
        max_memory_tokens=2048,
        verbose=verbose,
    )
    hindsight_litellm.enable()

    return _current_bank_id


def get_bank_id() -> str:
    """Get the current session's bank ID."""
    return _current_bank_id


# Track recently stored memories for display
_recent_memories: list[str] = []


def retain(content: str, context: str = None) -> Tuple[bool, str]:
    """
    Store a memory in Hindsight.

    Args:
        content: The memory content to store
        context: Optional context for the memory

    Returns:
        Tuple of (success, content) - content is returned for display purposes
    """
    global _recent_memories
    try:
        import time
        t0 = time.time()
        result = hindsight_litellm.retain(
            content=content,
            context=context or "Building exploration and delivery"
        )
        t1 = time.time()
        print(f"[TIMING] retain() took {t1-t0:.2f}s")
        if result.success:
            _recent_memories.append(content)
        return (result.success, content)
    except Exception as e:
        print(f"Warning: Failed to retain memory: {e}")
        return (False, content)


def get_recent_memories() -> list[str]:
    """Get list of recently stored memories."""
    return _recent_memories.copy()


def clear_recent_memories():
    """Clear the recent memories list."""
    global _recent_memories
    _recent_memories = []


def recall(query: str, limit: int = 5) -> list[str]:
    """
    Retrieve relevant memories from Hindsight.

    Args:
        query: The query to search for
        limit: Maximum number of results

    Returns:
        List of memory strings
    """
    try:
        memories = hindsight_litellm.recall(query, budget="mid")
        return [m.text for m in memories[:limit]]
    except Exception as e:
        print(f"Warning: Failed to recall memories: {e}")
        return []


def reflect(query: str) -> str:
    """
    Get synthesized context from Hindsight.

    Args:
        query: The query to reflect on

    Returns:
        Synthesized response
    """
    try:
        result = hindsight_litellm.reflect(query)
        return result.text if result else ""
    except Exception as e:
        print(f"Warning: Failed to reflect: {e}")
        return ""


def clear_memories() -> bool:
    """Clear all memories by reconfiguring with a fresh bank."""
    try:
        # Disable, cleanup, and reconfigure
        hindsight_litellm.disable()
        hindsight_litellm.cleanup()
        configure_memory()
        return True
    except Exception:
        return False


def get_memory_count() -> int:
    """Get approximate memory count (not directly supported, return 0)."""
    # hindsight_litellm doesn't expose stats directly
    # We could make a direct API call, but keeping it simple
    return 0


def completion(**kwargs):
    """
    Call LLM with automatic memory injection and storage.

    This is a pass-through to hindsight_litellm.completion()
    which handles:
    - Recalling relevant memories based on the conversation
    - Injecting them into the system prompt
    - Storing the conversation after the response
    """
    return hindsight_litellm.completion(**kwargs)


# Helper functions for formatting observations

def format_business_observation(floor: int, side: str, business_name: str) -> str:
    """Format a business location observation."""
    return f"{business_name} is located on Floor {floor}, {side} side of the building."


def format_employee_observation(business_name: str, employee_name: str, role: str = None) -> str:
    """Format an employee location observation."""
    if role:
        return f"{employee_name} ({role}) works at {business_name}."
    return f"{employee_name} works at {business_name}."


def format_delivery_success(recipient: str, business: str, floor: int, side: str, steps: int) -> str:
    """Format a successful delivery memory."""
    return (
        f"Successfully delivered to {recipient} at {business}. "
        f"{business} is on Floor {floor}, {side} side. Delivery took {steps} steps."
    )
