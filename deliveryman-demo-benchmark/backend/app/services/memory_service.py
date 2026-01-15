"""Memory service wrapper around hindsight_litellm."""

import os
import uuid
import asyncio
import concurrent.futures
import hindsight_litellm
from ..config import HINDSIGHT_API_URL

# Thread pool for running sync hindsight_litellm calls from async context
_executor = concurrent.futures.ThreadPoolExecutor(max_workers=4)

# Current bank ID
_current_bank_id: str = None

# Bank history - list of all bank IDs used in this session
_bank_history: list[str] = []

# Track whether we've already configured (to avoid reconfiguring in async context)
_configured: bool = False

# Bank background for memory extraction guidance
BANK_BACKGROUND = "Delivery agent. Remember employee locations, building layout, and optimal paths."


def generate_bank_id(prefix: str = "bench") -> str:
    """Generate a new random bank ID."""
    return f"{prefix}-{uuid.uuid4().hex[:8]}"


def _add_to_history(bank_id: str):
    """Add a bank ID to history if not already present."""
    global _bank_history
    if bank_id and bank_id not in _bank_history:
        _bank_history.append(bank_id)


def get_bank_history() -> list[str]:
    """Get the list of all bank IDs used in this session."""
    return _bank_history.copy()


def configure_memory(bank_id: str = None, set_background: bool = True) -> str:
    """Configure hindsight_litellm for the demo.

    Args:
        bank_id: Bank ID to use (generates random one if not provided)
        set_background: Whether to set the bank background

    Returns:
        The bank_id being used
    """
    global _current_bank_id, _configured

    new_bank_id = bank_id or generate_bank_id()
    _current_bank_id = new_bank_id

    hindsight_litellm.configure(
        hindsight_api_url=HINDSIGHT_API_URL,
        store_conversations=False,  # We store manually after delivery
        inject_memories=False,  # We inject manually using recall/reflect
        verbose=True,
    )

    hindsight_litellm.set_defaults(
        bank_id=new_bank_id,
        use_reflect=True,  # Use reflect for intelligent memory synthesis
        budget="high",  # Use high budget for better memory retrieval
    )

    # Set bank background for new banks
    if set_background:
        try:
            hindsight_litellm.set_bank_background(background=BANK_BACKGROUND)
            print(f"Bank background set for: {new_bank_id}")
        except Exception as e:
            print(f"Warning: Failed to set bank background: {e}")

    _configured = True
    _add_to_history(new_bank_id)
    print(f"Hindsight memory enabled for bank: {new_bank_id}")
    return new_bank_id


def get_bank_id() -> str:
    """Get the current bank ID."""
    return _current_bank_id


def set_bank_id(bank_id: str, set_background: bool = True, add_to_history: bool = True):
    """Set the bank_id for memory operations.

    Args:
        bank_id: The bank ID to use
        set_background: Whether to set the bank background
        add_to_history: Whether to add this bank to history
    """
    global _current_bank_id
    _current_bank_id = bank_id
    hindsight_litellm.set_defaults(bank_id=bank_id)

    if add_to_history:
        _add_to_history(bank_id)

    if set_background:
        try:
            hindsight_litellm.set_bank_background(background=BANK_BACKGROUND)
            print(f"Bank background set for: {bank_id}")
        except Exception as e:
            print(f"Warning: Failed to set bank background: {e}")


def set_bank_background_async(background: str = None):
    """Set bank background in a thread pool to avoid event loop issues.

    This is a fire-and-forget operation that won't block.
    """
    bg = background or BANK_BACKGROUND
    def _set_bg():
        try:
            hindsight_litellm.set_bank_background(background=bg)
            print(f"Bank background set for: {_current_bank_id}")
        except Exception as e:
            print(f"Warning: Failed to set bank background: {e}")

    _executor.submit(_set_bg)


def ensure_bank_exists() -> bool:
    """Ensure hindsight is configured. Returns True if successful."""
    global _configured
    # If already configured, don't reconfigure (avoids async event loop issues)
    if _configured:
        return True
    try:
        configure_memory()
        return True
    except Exception as e:
        print(f"[MEMORY] Error configuring hindsight: {e}")
        return False


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


def retain(content: str, sync: bool = True):
    """Store content to Hindsight memory (synchronous by default)."""
    return hindsight_litellm.retain(content, sync=sync)


async def retain_async(content: str, context: str = None, document_id: str = None):
    """Async store content to Hindsight memory.

    Args:
        content: The text content to store
        context: Context description for the memory
        document_id: Optional document ID for grouping related memories
    """
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(
        _executor,
        lambda: hindsight_litellm.retain(
            content,
            context=context,
            document_id=document_id,
            sync=True  # Wait for completion
        )
    )


def recall_sync(query: str, budget: str = "high", max_tokens: int = 4096):
    """Synchronous recall - get raw memories directly.

    Args:
        query: The question to search memories for
        budget: Search depth (low, mid, high)
        max_tokens: Maximum tokens to return

    Returns:
        RecallResponse with list of RecallResult objects (each has text, fact_type, weight)
    """
    return hindsight_litellm.recall(
        query=query,
        budget=budget,
        max_tokens=max_tokens,
    )


async def recall_async(query: str, budget: str = "high", max_tokens: int = 4096):
    """Async recall - get raw memories directly.

    Returns a list of memory facts without LLM synthesis.
    Each result has: text, fact_type, weight.

    Args:
        query: The question to search memories for
        budget: Search depth (low, mid, high)
        max_tokens: Maximum tokens to return

    Returns:
        RecallResponse with list of RecallResult objects
    """
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(
        _executor,
        lambda: recall_sync(query, budget, max_tokens)
    )


def format_recall_as_context(recall_response) -> str:
    """Format recall results as a text context for injection into prompts.

    Args:
        recall_response: RecallResponse from recall_async/recall_sync

    Returns:
        Formatted string of memories
    """
    if not recall_response or len(recall_response) == 0:
        return ""

    lines = []
    for result in recall_response:
        lines.append(f"- {result.text}")
    return "\n".join(lines)


def reflect_sync(query: str, budget: str = "high", context: str = None):
    """Synchronous reflect - get synthesized memory-based answer.

    Args:
        query: The question to answer based on memories
        budget: Search depth (low, mid, high)
        context: Additional context for reflection

    Returns:
        ReflectResult with synthesized answer text
    """
    return hindsight_litellm.reflect(
        query=query,
        budget=budget,
        context=context,
    )


async def reflect_async(query: str, budget: str = "high", context: str = None):
    """Async reflect - get synthesized memory-based answer.

    Uses an LLM to synthesize a coherent answer based on the bank's memories.
    This is more intelligent than raw recall - it generates a contextual response.

    Args:
        query: The question to answer based on memories (e.g., "Where does Alice work?")
        budget: Search depth (low, mid, high) - controls how many memories are considered
        context: Additional context for reflection

    Returns:
        ReflectResult with synthesized answer text
    """
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(
        _executor,
        lambda: reflect_sync(query, budget, context)
    )


def reset_bank(session_id: str = None) -> str:
    """Reset to a new memory bank.

    Returns:
        The new bank_id
    """
    return configure_memory(bank_id=f"bench-{session_id or uuid.uuid4().hex[:8]}")
