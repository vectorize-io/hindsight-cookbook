"""Memory service wrapper around hindsight_litellm."""

import os
import uuid
import asyncio
import concurrent.futures
import hindsight_litellm
from ..config import HINDSIGHT_API_URL

# Thread pool for running sync hindsight_litellm calls from async context
_executor = concurrent.futures.ThreadPoolExecutor(max_workers=4)


_current_bank_id: str = None


def configure_memory(session_id: str = None) -> str:
    """Configure hindsight_litellm for a session.

    Args:
        session_id: Unique session ID (generated if not provided)

    Returns:
        The bank_id for this session
    """
    global _current_bank_id

    if session_id:
        _current_bank_id = f"delivery-agent-{session_id}"
    else:
        _current_bank_id = f"delivery-agent-{uuid.uuid4().hex[:8]}"

    hindsight_litellm.configure(
        hindsight_api_url=HINDSIGHT_API_URL,
        store_conversations=False,
        inject_memories=True,
        verbose=True,
    )

    hindsight_litellm.set_defaults(
        bank_id=_current_bank_id,
        use_reflect=False,
    )

    hindsight_litellm.enable()

    return _current_bank_id


def get_bank_id() -> str:
    """Get the current session's bank ID."""
    return _current_bank_id


def set_document_id(document_id: str):
    """Set the document_id for grouping memories per delivery."""
    hindsight_litellm.set_document_id(document_id)


def completion_sync(**kwargs):
    """Call LLM with automatic memory injection (synchronous)."""
    return hindsight_litellm.completion(**kwargs)


async def completion(**kwargs):
    """Call LLM with automatic memory injection (async-safe).

    Runs hindsight_litellm.completion in a thread pool to avoid
    event loop conflicts with FastAPI's async handlers.
    """
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(_executor, lambda: hindsight_litellm.completion(**kwargs))


def get_last_injection_debug():
    """Get injection debug info from the last completion call."""
    try:
        result = hindsight_litellm.get_last_injection_debug()
        print(f"[MEMORY_SERVICE] get_last_injection_debug returned: {result}")
        return result
    except Exception as e:
        print(f"[MEMORY_SERVICE] get_last_injection_debug error: {e}")
        return None


def retain(content: str, sync: bool = False):
    """Store content to Hindsight memory."""
    return hindsight_litellm.retain(content, sync=sync)


def reset_bank(session_id: str = None) -> str:
    """Reset to a new memory bank.

    Returns:
        The new bank_id
    """
    return configure_memory(session_id=session_id or uuid.uuid4().hex[:8])
