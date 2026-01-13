"""Memory service wrapper around hindsight_litellm.

Uses reflect with context for intelligent memory retrieval.
"""

import os
import uuid
import asyncio
import concurrent.futures
import hindsight_litellm
from ..config import HINDSIGHT_API_URL

# Thread pool for running sync hindsight_litellm calls from async context
_executor = concurrent.futures.ThreadPoolExecutor(max_workers=4)

# Bank IDs per difficulty level
_bank_ids: dict[str, str] = {}  # difficulty -> bank_id

# Current difficulty level
_current_difficulty: str = "easy"

# Track whether we've already configured (to avoid reconfiguring in async context)
_configured: bool = False

# History of bank IDs used in this session, per difficulty
_bank_history: dict[str, list[str]] = {"easy": [], "medium": [], "hard": []}

# Bank background - simple and focused on what to remember
BANK_BACKGROUND = "Delivery agent. Remember employee locations and building layout."


def generate_bank_id(difficulty: str = None) -> str:
    """Generate a new random bank ID for a difficulty level."""
    if difficulty is None:
        difficulty = _current_difficulty
    prefix = {"easy": "easy", "medium": "med", "hard": "hard"}.get(difficulty, "demo")
    return f"{prefix}-{uuid.uuid4().hex[:8]}"


def configure_memory(bank_id: str = None, difficulty: str = None) -> str:
    """Configure hindsight_litellm for the demo.

    Args:
        bank_id: Bank ID to use (generates random one if not provided)
        difficulty: Difficulty level (uses current if not provided)

    Returns:
        The bank_id being used
    """
    global _bank_ids, _configured, _current_difficulty

    if difficulty is None:
        difficulty = _current_difficulty
    else:
        _current_difficulty = difficulty

    new_bank_id = bank_id or generate_bank_id(difficulty)
    _bank_ids[difficulty] = new_bank_id

    hindsight_litellm.configure(
        hindsight_api_url=HINDSIGHT_API_URL,
        store_conversations=False,  # We store manually after delivery
        inject_memories=True,
        verbose=True,
    )

    hindsight_litellm.set_defaults(
        bank_id=new_bank_id,
        use_reflect=True,  # Use reflect with context for better retrieval
        budget="high",  # Use high budget for better memory retrieval
    )

    # Always set bank background for new banks
    try:
        hindsight_litellm.set_bank_background(background=BANK_BACKGROUND)
        print(f"Bank background set for: {new_bank_id}")
    except Exception as e:
        print(f"Warning: Failed to set bank background: {e}")

    # Don't call enable() - it monkey-patches litellm.completion which causes
    # double-popping of hindsight_query when using hindsight_litellm.completion() directly

    _configured = True
    _add_to_history(new_bank_id, difficulty)
    print(f"Hindsight memory enabled for bank: {new_bank_id} (difficulty: {difficulty})")
    return new_bank_id


def get_bank_id(difficulty: str = None) -> str:
    """Get the current bank ID for a difficulty level."""
    if difficulty is None:
        difficulty = _current_difficulty
    return _bank_ids.get(difficulty)


def set_bank_id(bank_id: str, difficulty: str = None, set_background: bool = True):
    """Set the bank_id for memory operations."""
    global _bank_ids, _current_difficulty
    if difficulty is None:
        difficulty = _current_difficulty
    else:
        _current_difficulty = difficulty

    _bank_ids[difficulty] = bank_id
    hindsight_litellm.set_defaults(bank_id=bank_id)
    _add_to_history(bank_id, difficulty)
    if set_background:
        try:
            hindsight_litellm.set_bank_background(background=BANK_BACKGROUND)
        except Exception as e:
            print(f"Warning: Failed to set bank background: {e}")


def _add_to_history(bank_id: str, difficulty: str = None):
    """Add a bank ID to the history (if not already present)."""
    global _bank_history
    if difficulty is None:
        difficulty = _current_difficulty
    if difficulty not in _bank_history:
        _bank_history[difficulty] = []
    if bank_id and bank_id not in _bank_history[difficulty]:
        _bank_history[difficulty].append(bank_id)


def get_bank_history(difficulty: str = None) -> list[str]:
    """Get the list of bank IDs used for a difficulty level."""
    if difficulty is None:
        difficulty = _current_difficulty
    return _bank_history.get(difficulty, []).copy()


def get_current_difficulty() -> str:
    """Get the current difficulty level."""
    return _current_difficulty


def set_current_difficulty(difficulty: str) -> str:
    """Set the current difficulty level and return the bank ID for it."""
    global _current_difficulty
    if difficulty not in ["easy", "medium", "hard"]:
        raise ValueError(f"Invalid difficulty: {difficulty}")
    _current_difficulty = difficulty

    # If no bank exists for this difficulty, create one
    if difficulty not in _bank_ids or not _bank_ids[difficulty]:
        return configure_memory(difficulty=difficulty)

    # Set the existing bank as active
    bank_id = _bank_ids[difficulty]
    hindsight_litellm.set_defaults(bank_id=bank_id)
    return bank_id


def set_document_id(document_id: str):
    """Set the document_id for grouping memories per delivery."""
    hindsight_litellm.set_document_id(document_id)


def completion_sync(**kwargs):
    """Call LLM with automatic memory injection (synchronous)."""
    return hindsight_litellm.completion(**kwargs)


class CompletionResult:
    """Wrapper to hold both the LLM response and injection debug info."""
    def __init__(self, response, injection_debug):
        self.response = response
        self.injection_debug = injection_debug
        # Proxy to response for backwards compatibility
        self.choices = response.choices


def _completion_with_debug(**kwargs):
    """Run completion and capture debug info in the same thread."""
    response = hindsight_litellm.completion(**kwargs)
    debug = hindsight_litellm.get_last_injection_debug()
    return CompletionResult(response, debug)


async def completion(**kwargs):
    """Call LLM with automatic memory injection (async-safe).

    Runs hindsight_litellm.completion in a thread pool to avoid
    event loop conflicts with FastAPI's async handlers.

    Returns a CompletionResult with both the response and injection_debug.
    """
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(_executor, lambda: _completion_with_debug(**kwargs))


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
    """Store content to Hindsight memory (synchronous)."""
    return hindsight_litellm.retain(content, sync=sync)


async def retain_async(content: str):
    """Store content to Hindsight memory (async-safe).

    Runs hindsight_litellm.retain in a thread pool to avoid
    event loop conflicts with FastAPI's async handlers.
    """
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(_executor, lambda: hindsight_litellm.retain(content, sync=True))


class ReflectResult:
    """Wrapper for reflect results."""
    def __init__(self, text: str, query: str, bank_id: str, based_on: list = None):
        self.text = text
        self.query = query
        self.bank_id = bank_id
        self.based_on = based_on or []


def reflect_sync(query: str, context: str = None) -> ReflectResult:
    """Call Hindsight reflect API (synchronous)."""
    result = hindsight_litellm.reflect(query=query, context=context)
    return ReflectResult(
        text=result.text,
        query=query,
        bank_id=get_bank_id(),
        based_on=result.based_on if hasattr(result, 'based_on') else []
    )


async def reflect_async(query: str, context: str = None) -> ReflectResult:
    """Call Hindsight reflect API (async-safe).

    Runs hindsight_litellm.reflect in a thread pool to avoid
    event loop conflicts with FastAPI's async handlers.
    """
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(_executor, lambda: reflect_sync(query, context))


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
