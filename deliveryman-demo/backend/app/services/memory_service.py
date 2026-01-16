"""Memory service wrapper around hindsight_litellm."""

import os
import json
import uuid
import asyncio
import concurrent.futures
from pathlib import Path
import hindsight_litellm
from ..config import HINDSIGHT_API_URL

# Thread pool for running sync hindsight_litellm calls from async context
_executor = concurrent.futures.ThreadPoolExecutor(max_workers=4)

# File to persist bank IDs across hot reloads
_BANK_IDS_FILE = Path(__file__).parent.parent.parent / ".bank_ids.json"

def _load_persisted_bank_ids() -> dict[str, str]:
    """Load bank IDs from file if it exists."""
    if _BANK_IDS_FILE.exists():
        try:
            with open(_BANK_IDS_FILE, "r") as f:
                data = json.load(f)
                print(f"Loaded persisted bank IDs: {data}")
                return data
        except Exception as e:
            print(f"Warning: Failed to load bank IDs file: {e}")
    return {}

def _save_persisted_bank_ids(bank_ids: dict[str, str]):
    """Save bank IDs to file for persistence across hot reloads."""
    try:
        with open(_BANK_IDS_FILE, "w") as f:
            json.dump(bank_ids, f)
        print(f"Saved bank IDs to file: {bank_ids}")
    except Exception as e:
        print(f"Warning: Failed to save bank IDs file: {e}")

def _get_bank_key(app_type: str, difficulty: str = None) -> str:
    """Get the key for bank storage (app:difficulty or just app if no difficulty)."""
    if difficulty:
        return f"{app_type}:{difficulty}"
    return app_type

def _get_or_create_default_bank_id(app_type: str, difficulty: str = None) -> str:
    """Get persisted bank ID or create a new random one."""
    key = _get_bank_key(app_type, difficulty)
    persisted = _load_persisted_bank_ids()
    if key in persisted:
        return persisted[key]
    # Generate new random ID - include difficulty in prefix for clarity
    prefix = f"{app_type}-{difficulty}" if difficulty else app_type
    new_id = f"{prefix}-{uuid.uuid4().hex[:8]}"
    persisted[key] = new_id
    _save_persisted_bank_ids(persisted)
    return new_id

# Per-app+difficulty bank state
# Keys are "app_type:difficulty" (e.g., "demo:easy", "bench:hard")
_app_bank_ids: dict[str, str] = {}  # key -> bank_id
_app_bank_history: dict[str, list[str]] = {}  # key -> list of bank_ids

# Current active app type and difficulty
_current_app_type: str = "demo"
_current_difficulty: str = "easy"

# Track whether we've already configured (to avoid reconfiguring in async context)
_configured: bool = False

# Bank background for memory extraction guidance
BANK_BACKGROUND = "Delivery agent. Remember employee locations, building layout, and optimal paths."


def generate_bank_id(app_type: str = "demo", difficulty: str = None, use_default: bool = True) -> str:
    """Generate a bank ID - uses persisted ID if use_default=True, else random."""
    diff = difficulty or _current_difficulty
    if use_default:
        return _get_or_create_default_bank_id(app_type, diff)
    prefix = f"{app_type}-{diff}" if diff else app_type
    return f"{prefix}-{uuid.uuid4().hex[:8]}"


def _add_to_history(bank_id: str, app_type: str = None, difficulty: str = None):
    """Add a bank ID to history if not already present."""
    global _app_bank_history
    app = app_type or _current_app_type
    diff = difficulty or _current_difficulty
    key = _get_bank_key(app, diff)
    if key not in _app_bank_history:
        _app_bank_history[key] = []
    if bank_id and bank_id not in _app_bank_history[key]:
        _app_bank_history[key].append(bank_id)


def get_bank_history(app_type: str = None, difficulty: str = None) -> list[str]:
    """Get the list of all bank IDs used in this session for an app+difficulty.

    Returns banks in reverse order (newest first).
    """
    app = app_type or _current_app_type
    diff = difficulty or _current_difficulty
    key = _get_bank_key(app, diff)
    history = _app_bank_history.get(key, []).copy()
    history.reverse()  # Newest first
    return history


def configure_memory(bank_id: str = None, set_background: bool = True, app_type: str = None, difficulty: str = None, use_default: bool = True) -> str:
    """Configure hindsight_litellm for the demo.

    Args:
        bank_id: Bank ID to use (uses default if not provided)
        set_background: Whether to set the bank background
        app_type: App type (demo or bench) for prefix and tracking
        difficulty: Difficulty level (easy, medium, hard) for separate banks
        use_default: Use deterministic default bank ID (persists across restarts)

    Returns:
        The bank_id being used
    """
    global _app_bank_ids, _current_app_type, _current_difficulty, _configured

    # Determine app and difficulty
    app = app_type or _current_app_type
    diff = difficulty or _current_difficulty
    key = _get_bank_key(app, diff)

    new_bank_id = bank_id or generate_bank_id(app, diff, use_default=use_default)
    _app_bank_ids[key] = new_bank_id
    _current_app_type = app
    _current_difficulty = diff

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
    _add_to_history(new_bank_id, app, diff)
    print(f"Hindsight memory enabled for bank: {new_bank_id} (app: {app}, difficulty: {diff})")
    return new_bank_id


def get_bank_id(app_type: str = None, difficulty: str = None) -> str:
    """Get the current bank ID for an app+difficulty."""
    app = app_type or _current_app_type
    diff = difficulty or _current_difficulty
    key = _get_bank_key(app, diff)
    return _app_bank_ids.get(key)


def set_bank_id(bank_id: str, set_background: bool = True, add_to_history: bool = True, app_type: str = None, difficulty: str = None):
    """Set the bank_id for memory operations.

    Args:
        bank_id: The bank ID to use
        set_background: Whether to set the bank background
        add_to_history: Whether to add this bank to history
        app_type: App type (demo or bench) for tracking
        difficulty: Difficulty level for tracking
    """
    global _app_bank_ids, _current_app_type, _current_difficulty
    app = app_type or _current_app_type
    diff = difficulty or _current_difficulty
    key = _get_bank_key(app, diff)
    _app_bank_ids[key] = bank_id
    _current_app_type = app
    _current_difficulty = diff
    hindsight_litellm.set_defaults(bank_id=bank_id)

    if add_to_history:
        _add_to_history(bank_id, app, diff)

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
            bank_id = get_bank_id()
            print(f"Bank background set for: {bank_id}")
        except Exception as e:
            print(f"Warning: Failed to set bank background: {e}")

    _executor.submit(_set_bg)


def ensure_bank_exists(app_type: str = None, difficulty: str = None) -> bool:
    """Ensure hindsight is configured for an app+difficulty. Returns True if successful."""
    global _configured
    app = app_type or _current_app_type
    diff = difficulty or _current_difficulty
    key = _get_bank_key(app, diff)
    # If already configured and bank exists for this app+difficulty, return
    if _configured and key in _app_bank_ids:
        return True
    try:
        configure_memory(app_type=app, difficulty=diff)
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
    print(f"[MEMORY] retain_async called - context={context}, doc_id={document_id}, content_len={len(content)}", flush=True)
    print(f"[MEMORY] Current bank_id for retain: {get_bank_id()}", flush=True)
    loop = asyncio.get_event_loop()

    def _do_retain():
        print(f"[MEMORY] Starting hindsight_litellm.retain...", flush=True)
        try:
            result = hindsight_litellm.retain(
                content,
                context=context,
                document_id=document_id,
                sync=True
            )
            print(f"[MEMORY] retain completed successfully", flush=True)
            return result
        except Exception as e:
            print(f"[MEMORY] retain FAILED: {e}", flush=True)
            raise

    return await loop.run_in_executor(_executor, _do_retain)


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


def reset_bank(session_id: str = None, app_type: str = None, difficulty: str = None) -> str:
    """Reset to a new memory bank (generates new random ID).

    Args:
        session_id: Optional session ID to include in bank name
        app_type: App type (demo or bench) for prefix
        difficulty: Difficulty level for the bank

    Returns:
        The new bank_id
    """
    app = app_type or _current_app_type
    diff = difficulty or _current_difficulty
    key = _get_bank_key(app, diff)
    # Generate new random ID with difficulty in prefix
    prefix = f"{app}-{diff}"
    new_id = f"{prefix}-{session_id or uuid.uuid4().hex[:8]}"
    # Update the persisted file with the new ID
    persisted = _load_persisted_bank_ids()
    persisted[key] = new_id
    _save_persisted_bank_ids(persisted)
    return configure_memory(bank_id=new_id, app_type=app, difficulty=diff, use_default=False)


def set_active_app(app_type: str, difficulty: str = None):
    """Set the active app type and difficulty, and switch to its bank."""
    global _current_app_type, _current_difficulty
    _current_app_type = app_type
    if difficulty:
        _current_difficulty = difficulty
    key = _get_bank_key(app_type, _current_difficulty)
    bank_id = _app_bank_ids.get(key)
    if bank_id:
        hindsight_litellm.set_defaults(bank_id=bank_id)
        print(f"Switched to app {app_type} (difficulty: {_current_difficulty}) with bank: {bank_id}")


def set_difficulty(difficulty: str, app_type: str = None) -> str:
    """Set the difficulty and configure/get the bank for it.

    This will create a new bank for the difficulty if one doesn't exist.

    Args:
        difficulty: The difficulty level (easy, medium, hard)
        app_type: Optional app type override

    Returns:
        The bank_id for the difficulty
    """
    global _current_difficulty
    app = app_type or _current_app_type
    _current_difficulty = difficulty
    key = _get_bank_key(app, difficulty)

    # Check if we already have a bank for this app+difficulty
    if key in _app_bank_ids:
        bank_id = _app_bank_ids[key]
        hindsight_litellm.set_defaults(bank_id=bank_id)
        print(f"Switched to existing bank for {app}:{difficulty} - {bank_id}")
        return bank_id

    # Create new bank for this difficulty
    return configure_memory(app_type=app, difficulty=difficulty)
