"""Memory service wrapper around hindsight_litellm and hindsight_client.

This module provides memory operations for the deliveryman demo using:
- hindsight_litellm: For retain, recall, reflect operations
- hindsight_client: For typed bank operations (create, stats, reflections)
"""

import uuid
import asyncio
import concurrent.futures
import hindsight_litellm
from hindsight_litellm import (
    aretain,
    arecall,
    areflect,
    RecallResponse,
    ReflectResult,
    RetainResult,
    HindsightError,
)
from hindsight_client import Hindsight
from ..config import get_hindsight_url, set_hindsight_url, HINDSIGHT_API_URL

# Debug logging for memory service
DEBUG_MEMORY = True

def _debug_mem(msg: str):
    """Print debug message for memory operations."""
    if DEBUG_MEMORY:
        print(f"[MEM_DEBUG] {msg}", flush=True)


# Hindsight client instance (typed API for bank operations)
_hindsight_client: Hindsight | None = None
_hindsight_client_url: str | None = None

# HTTP client for operations not in hindsight_client (consolidation, stats)
import httpx
_http_client: httpx.Client | None = None
_http_client_url: str | None = None


def _get_hindsight_client(hindsight_url: str = None) -> Hindsight:
    """Get or create Hindsight client for typed API operations.

    Args:
        hindsight_url: Optional override URL. If not provided, uses get_hindsight_url().
    """
    global _hindsight_client, _hindsight_client_url
    url = hindsight_url or get_hindsight_url()

    # Recreate client if URL changed
    if _hindsight_client is None or _hindsight_client_url != url:
        _hindsight_client = Hindsight(base_url=url, timeout=60.0)
        _hindsight_client_url = url
    return _hindsight_client


def _get_http_client(hindsight_url: str = None) -> httpx.Client:
    """Get or create HTTP client for operations not in hindsight_client.

    Args:
        hindsight_url: Optional override URL. If not provided, uses get_hindsight_url().
    """
    global _http_client, _http_client_url
    url = hindsight_url or get_hindsight_url()

    # Recreate client if URL changed
    if _http_client is None or _http_client_url != url:
        if _http_client is not None:
            _http_client.close()
        _http_client = httpx.Client(base_url=url, timeout=60.0)
        _http_client_url = url
    return _http_client


def initialize_memory(hindsight_url: str = None):
    """Initialize the memory service with the specified Hindsight URL.

    Args:
        hindsight_url: URL of the Hindsight API (None = use default from env)
    """
    global _hindsight_client, _hindsight_client_url, _http_client, _http_client_url

    if hindsight_url:
        set_hindsight_url(hindsight_url)

    # Re-initialize the clients with the new URL
    if _hindsight_client is not None:
        _hindsight_client = None
        _hindsight_client_url = None
    if _http_client is not None:
        _http_client.close()
        _http_client = None
        _http_client_url = None


# Thread pool for running sync operations from async context
_executor = concurrent.futures.ThreadPoolExecutor(max_workers=4)

def _get_bank_key(app_type: str, difficulty: str = None) -> str:
    """Get the key for bank storage (app:difficulty or just app if no difficulty)."""
    if difficulty:
        return f"{app_type}:{difficulty}"
    return app_type

# Per-app+difficulty bank state
# Keys are "app_type:difficulty" (e.g., "demo:easy", "bench:hard")
_app_bank_ids: dict[str, str] = {}  # key -> bank_id
_app_bank_history: dict[str, list[str]] = {}  # key -> list of bank_ids

# Current active app type and difficulty
_current_app_type: str = "demo"
_current_difficulty: str = "easy"

# Track whether we've already configured (to avoid reconfiguring in async context)
_configured: bool = False

# Mental model refresh settings
# Tracks deliveries since last refresh per app+difficulty
_deliveries_since_refresh: dict[str, int] = {}  # key -> count
_refresh_interval: dict[str, int] = {}  # key -> interval (0 = disabled)
DEFAULT_REFRESH_INTERVAL = 5  # Refresh every 5 deliveries by default

# Bank background for memory extraction guidance
BANK_BACKGROUND = "Delivery agent. Remember employee locations, building layout, and optimal paths."

# Bank mission for mental models - same as background for simplicity
BANK_MISSION = "Delivery agent. Remember employee locations, building layout, and optimal paths."

# Default mental models (reflections) to create for each bank
# Each tuple is (name, source_query)
DEFAULT_MENTAL_MODELS = [
    ("Employee Locations", "Where is each employee located? What floor, side, and business does each person work at?"),
    ("Building Layout", "What businesses and areas are on each floor? How are the buildings connected?"),
    ("Optimal Delivery Paths", "What steps were taken to deliver to each employee? When was it faster to use a bridge, stairs, or ground passage?"),
]


def generate_bank_id(app_type: str = "demo", difficulty: str = None) -> str:
    """Generate a new random bank ID."""
    diff = difficulty or _current_difficulty
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


def configure_memory(
    bank_id: str = None,
    set_background: bool = True,
    app_type: str = None,
    difficulty: str = None,
    set_mission: bool = True,
    create_mental_models: bool = True,
) -> str:
    """Configure hindsight_litellm for the demo.

    Args:
        bank_id: Bank ID to use (generates new random one if not provided)
        set_background: Whether to set the bank background
        app_type: App type (demo or bench) for prefix and tracking
        difficulty: Difficulty level (easy, medium, hard) for separate banks
        set_mission: Whether to set the bank mission (for mental models)
        create_mental_models: Whether to create default mental models (reflections)

    Returns:
        The bank_id being used
    """
    global _app_bank_ids, _current_app_type, _current_difficulty, _configured

    # Determine app and difficulty
    app = app_type or _current_app_type
    diff = difficulty or _current_difficulty
    key = _get_bank_key(app, diff)

    new_bank_id = bank_id or generate_bank_id(app, diff)
    _app_bank_ids[key] = new_bank_id
    _current_app_type = app
    _current_difficulty = diff

    # Create the bank in Hindsight (idempotent - will skip if exists)
    create_bank(
        bank_id=new_bank_id,
        name=new_bank_id,
        background=BANK_BACKGROUND if set_background else None,
        mission=BANK_MISSION if set_mission else None,
    )

    # Configure static settings (API URL, storage options, etc.)
    # Note: bank_id is tracked locally and passed to each call
    hindsight_litellm.configure(
        hindsight_api_url=get_hindsight_url(),
        bank_id=new_bank_id,  # Set default bank_id
        store_conversations=False,  # We store manually after delivery
        inject_memories=False,  # We inject manually using recall/reflect
        budget="high",  # Use high budget for better memory retrieval
        use_reflect=True,  # Use reflect for intelligent memory synthesis
        verbose=True,
    )

    # Enable the integration
    hindsight_litellm.enable()

    _configured = True
    _add_to_history(new_bank_id, app, diff)
    print(f"Hindsight memory enabled for bank: {new_bank_id} (app: {app}, difficulty: {diff})")

    # Create default mental models (reflections) for new banks
    if create_mental_models:
        create_default_mental_models(bank_id=new_bank_id)

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

    # Reconfigure hindsight with the new bank_id
    hindsight_litellm.configure(
        hindsight_api_url=get_hindsight_url(),
        bank_id=bank_id,
        store_conversations=False,
        inject_memories=False,
        budget="high",
        use_reflect=True,
        verbose=True,
    )

    if add_to_history:
        _add_to_history(bank_id, app, diff)

    if set_background:
        # Set mission via HTTP API (async-safe)
        set_bank_mission_sync(bank_id, BANK_MISSION)
        print(f"Bank mission set for: {bank_id}")


def set_bank_mission_sync(bank_id: str, mission: str = None, hindsight_url: str = None):
    """Set bank mission using httpx (synchronous, event-loop safe).

    Args:
        bank_id: The bank ID to set mission for
        mission: The mission text (defaults to BANK_MISSION)
        hindsight_url: Optional override URL
    """
    m = mission or BANK_MISSION
    try:
        client = _get_http_client(hindsight_url)
        response = client.put(
            f"/v1/default/banks/{bank_id}",
            json={"mission": m},
        )
        response.raise_for_status()
        print(f"[MEMORY] Bank mission set for: {bank_id}")
    except Exception as e:
        print(f"[MEMORY] Failed to set bank mission: {e}")


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


# Current document ID for grouping related memories
_current_document_id: str | None = None


def set_document_id(document_id: str):
    """Set the document_id for grouping memories per delivery."""
    global _current_document_id
    _current_document_id = document_id


def get_document_id() -> str | None:
    """Get the current document_id."""
    return _current_document_id


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


async def retain_async(
    content: str,
    context: str = None,
    session_id: str = None,
    bank_id: str = None,
    hindsight_url: str = None,
    tags: list[str] = None,
) -> RetainResult:
    """Async store content to Hindsight memory.

    Args:
        content: The text content to store
        context: Context description for the memory
        session_id: Optional session ID for grouping related memories (replaces document_id)
        bank_id: Override bank_id (for parallel execution with separate banks)
        hindsight_url: Override Hindsight API URL (for using different backends)
        tags: Optional tags for filtering during recall/reflect

    Returns:
        RetainResult with success status and items_count
    """
    bid = bank_id or get_bank_id()
    url = hindsight_url or get_hindsight_url()
    _debug_mem(f"RETAIN_ASYNC called:")
    _debug_mem(f"  bank_id={bid}")
    _debug_mem(f"  context={context}")
    _debug_mem(f"  session_id={session_id}")
    _debug_mem(f"  content_len={len(content)}")
    _debug_mem(f"  hindsight_url={url}")
    _debug_mem(f"  tags={tags}")

    import time
    t0 = time.time()
    try:
        # Use native async aretain from hindsight_litellm
        result = await aretain(
            content,
            bank_id=bid,
            context=context,
            document_id=session_id,  # API still uses document_id internally
            tags=tags,
            hindsight_api_url=url,
        )
        elapsed = time.time() - t0
        _debug_mem(f"  <<< RETAIN success in {elapsed:.2f}s (bank={bid})")
        return result
    except HindsightError as e:
        elapsed = time.time() - t0
        _debug_mem(f"  !!! RETAIN FAILED in {elapsed:.2f}s: {e}")
        raise
    except Exception as e:
        elapsed = time.time() - t0
        _debug_mem(f"  !!! RETAIN FAILED in {elapsed:.2f}s: {e}")
        raise


def recall_sync(
    query: str,
    budget: str = "high",
    max_tokens: int = 4096,
    bank_id: str = None,
    hindsight_url: str = None,
    fact_types: list[str] = None,
    tags: list[str] = None,
    tags_match: str = "any",
) -> RecallResponse:
    """Synchronous recall - get raw memories directly.

    Args:
        query: The question to search memories for
        budget: Search depth (low, mid, high)
        max_tokens: Maximum tokens to return
        bank_id: Override bank_id (for parallel execution with separate banks)
        hindsight_url: Override Hindsight API URL (for using different backends)
        fact_types: Filter by types (world, experience, opinion, observation)
        tags: Filter memories by tags
        tags_match: Tag matching mode (any, all, any_strict, all_strict)

    Returns:
        RecallResponse with list of RecallResult objects (each has text, fact_type, weight)
    """
    bid = bank_id or get_bank_id()
    url = hindsight_url or get_hindsight_url()
    _debug_mem(f"RECALL_SYNC called:")
    _debug_mem(f"  bank_id={bid}")
    _debug_mem(f"  hindsight_url={url}")
    _debug_mem(f"  query={query[:80]}...")
    _debug_mem(f"  budget={budget}, fact_types={fact_types}, tags={tags}")
    import time
    t0 = time.time()
    try:
        result = hindsight_litellm.recall(
            query=query,
            bank_id=bid,
            budget=budget,
            max_tokens=max_tokens,
            fact_types=fact_types,
            hindsight_api_url=url,
        )
        elapsed = time.time() - t0
        num_results = len(result) if result else 0
        _debug_mem(f"  <<< RECALL returned {num_results} facts in {elapsed:.2f}s")
        if result and len(result) > 0:
            _debug_mem(f"  First fact: {result[0].text[:100]}...")
        return result
    except HindsightError as e:
        elapsed = time.time() - t0
        _debug_mem(f"  !!! RECALL FAILED in {elapsed:.2f}s: {e}")
        raise


async def recall_async(
    query: str,
    budget: str = "high",
    max_tokens: int = 4096,
    bank_id: str = None,
    hindsight_url: str = None,
    fact_types: list[str] = None,
    tags: list[str] = None,
    tags_match: str = "any",
) -> RecallResponse:
    """Async recall - get raw memories directly.

    Returns a list of memory facts without LLM synthesis.
    Each result has: text, fact_type, weight.

    Args:
        query: The question to search memories for
        budget: Search depth (low, mid, high)
        max_tokens: Maximum tokens to return
        bank_id: Override bank_id (for parallel execution with separate banks)
        hindsight_url: Override Hindsight API URL (for using different backends)
        fact_types: Filter by types (world, experience, opinion, observation)
        tags: Filter memories by tags
        tags_match: Tag matching mode (any, all, any_strict, all_strict)

    Returns:
        RecallResponse with list of RecallResult objects
    """
    bid = bank_id or get_bank_id()
    url = hindsight_url or get_hindsight_url()
    _debug_mem(f"RECALL_ASYNC called:")
    _debug_mem(f"  bank_id={bid}")
    _debug_mem(f"  hindsight_url={url}")
    _debug_mem(f"  query={query[:80]}...")
    _debug_mem(f"  budget={budget}, fact_types={fact_types}, tags={tags}")

    import time
    t0 = time.time()
    try:
        # Use native async arecall from hindsight_litellm
        result = await arecall(
            query=query,
            bank_id=bid,
            budget=budget,
            max_tokens=max_tokens,
            fact_types=fact_types,
            hindsight_api_url=url,
        )
        elapsed = time.time() - t0
        num_results = len(result) if result else 0
        _debug_mem(f"  <<< RECALL returned {num_results} facts in {elapsed:.2f}s")
        if result and len(result) > 0:
            _debug_mem(f"  First fact: {result[0].text[:100]}...")
        return result
    except HindsightError as e:
        elapsed = time.time() - t0
        _debug_mem(f"  !!! RECALL FAILED in {elapsed:.2f}s: {e}")
        raise


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


def reflect_sync(
    query: str,
    budget: str = "high",
    context: str = None,
    bank_id: str = None,
    hindsight_url: str = None,
    response_schema: dict = None,
) -> ReflectResult:
    """Synchronous reflect - get synthesized memory-based answer.

    Args:
        query: The question to answer based on memories
        budget: Search depth (low, mid, high)
        context: Additional context for reflection
        bank_id: Override bank_id (for parallel execution with separate banks)
        hindsight_url: Override Hindsight API URL (for using different backends)
        response_schema: Optional JSON schema for structured output

    Returns:
        ReflectResult with synthesized answer text
    """
    bid = bank_id or get_bank_id()
    url = hindsight_url or get_hindsight_url()
    _debug_mem(f"REFLECT_SYNC called:")
    _debug_mem(f"  bank_id={bid}")
    _debug_mem(f"  hindsight_url={url}")
    _debug_mem(f"  query={query[:80]}...")
    _debug_mem(f"  budget={budget}")
    _debug_mem(f"  context={context[:50] if context else 'None'}...")
    import time
    t0 = time.time()
    try:
        result = hindsight_litellm.reflect(
            query=query,
            bank_id=bid,
            budget=budget,
            context=context,
            response_schema=response_schema,
            hindsight_api_url=url,
        )
        elapsed = time.time() - t0
        result_len = len(result.text) if result and hasattr(result, 'text') and result.text else 0
        _debug_mem(f"  <<< REFLECT returned {result_len} chars in {elapsed:.2f}s")
        if result and hasattr(result, 'text') and result.text:
            _debug_mem(f"  Result: {result.text[:100]}...")
        return result
    except HindsightError as e:
        elapsed = time.time() - t0
        _debug_mem(f"  !!! REFLECT FAILED in {elapsed:.2f}s: {e}")
        raise


async def reflect_async(
    query: str,
    budget: str = "high",
    context: str = None,
    bank_id: str = None,
    hindsight_url: str = None,
    response_schema: dict = None,
) -> ReflectResult:
    """Async reflect - get synthesized memory-based answer.

    Uses an LLM to synthesize a coherent answer based on the bank's memories.
    This is more intelligent than raw recall - it generates a contextual response.

    Args:
        query: The question to answer based on memories (e.g., "Where does Alice work?")
        budget: Search depth (low, mid, high) - controls how many memories are considered
        context: Additional context for reflection
        bank_id: Override bank_id (for parallel execution with separate banks)
        hindsight_url: Override Hindsight API URL (for using different backends)
        response_schema: Optional JSON schema for structured output

    Returns:
        ReflectResult with synthesized answer text
    """
    bid = bank_id or get_bank_id()
    url = hindsight_url or get_hindsight_url()
    _debug_mem(f"REFLECT_ASYNC called:")
    _debug_mem(f"  bank_id={bid}")
    _debug_mem(f"  hindsight_url={url}")
    _debug_mem(f"  query={query[:80]}...")
    _debug_mem(f"  budget={budget}")
    _debug_mem(f"  context={context[:50] if context else 'None'}...")

    import time
    t0 = time.time()
    try:
        # Use native async areflect from hindsight_litellm
        result = await areflect(
            query=query,
            bank_id=bid,
            budget=budget,
            context=context,
            response_schema=response_schema,
            hindsight_api_url=url,
        )
        elapsed = time.time() - t0
        result_len = len(result.text) if result and hasattr(result, 'text') and result.text else 0
        _debug_mem(f"  <<< REFLECT returned {result_len} chars in {elapsed:.2f}s")
        if result and hasattr(result, 'text') and result.text:
            _debug_mem(f"  Result: {result.text[:100]}...")
        return result
    except HindsightError as e:
        elapsed = time.time() - t0
        _debug_mem(f"  !!! REFLECT FAILED in {elapsed:.2f}s: {e}")
        raise


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
    # Generate new random ID with difficulty in prefix
    prefix = f"{app}-{diff}"
    new_id = f"{prefix}-{session_id or uuid.uuid4().hex[:8]}"
    return configure_memory(bank_id=new_id, app_type=app, difficulty=diff)


def set_active_app(app_type: str, difficulty: str = None):
    """Set the active app type and difficulty, and switch to its bank."""
    global _current_app_type, _current_difficulty
    _current_app_type = app_type
    if difficulty:
        _current_difficulty = difficulty
    key = _get_bank_key(app_type, _current_difficulty)
    bank_id = _app_bank_ids.get(key)
    if bank_id:
        # Reconfigure hindsight with the new bank_id
        hindsight_litellm.configure(
            hindsight_api_url=get_hindsight_url(),
            bank_id=bank_id,
            store_conversations=False,
            inject_memories=False,
            budget="high",
            use_reflect=True,
            verbose=True,
        )
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
        # Reconfigure hindsight with the existing bank_id
        hindsight_litellm.configure(
            hindsight_api_url=get_hindsight_url(),
            bank_id=bank_id,
            store_conversations=False,
            inject_memories=False,
            budget="high",
            use_reflect=True,
            verbose=True,
        )
        print(f"Switched to existing bank for {app}:{difficulty} - {bank_id}")
        return bank_id

    # Create new bank for this difficulty
    return configure_memory(app_type=app, difficulty=difficulty)


# =============================================================================
# Bank Operations (using hindsight_client for typed API)
# =============================================================================

def create_bank(
    bank_id: str,
    name: str = None,
    background: str = None,
    mission: str = None,
    hindsight_url: str = None,
) -> dict:
    """Create a memory bank in Hindsight.

    Uses httpx directly instead of hindsight_client to avoid event loop conflicts
    when called from within an async context (e.g., WebSocket handlers).

    Args:
        bank_id: Unique bank ID
        name: Optional display name (defaults to bank_id)
        background: Optional bank background/context
        mission: Optional mission for mental models
        hindsight_url: Optional override URL

    Returns:
        Bank profile response
    """
    try:
        client = _get_http_client(hindsight_url)
        body = {"name": name or bank_id}
        if mission:
            body["mission"] = mission
        response = client.put(
            f"/v1/default/banks/{bank_id}",
            json=body,
        )
        response.raise_for_status()
        print(f"[MEMORY] Created/updated bank: {bank_id}")
        return {"bank_id": bank_id, "name": name or bank_id, "mission": mission}
    except Exception as e:
        print(f"[MEMORY] Error creating bank {bank_id}: {e}")
        return {}


# =============================================================================
# Mental Models / Reflections API (using hindsight_client)
# =============================================================================

def set_bank_mission(bank_id: str = None, mission: str = None, hindsight_url: str = None) -> dict:
    """Set the mission for a memory bank (used by mental models and reflect).

    Args:
        bank_id: Bank ID (uses current if not provided)
        mission: Mission text (uses BANK_MISSION if not provided)
        hindsight_url: Optional override URL

    Returns:
        Response from the API
    """
    bid = bank_id or get_bank_id()
    if not bid:
        print("[MEMORY] Cannot set mission: no bank_id")
        return {}

    mission_text = mission or BANK_MISSION

    try:
        client = _get_http_client(hindsight_url)
        response = client.put(
            f"/v1/default/banks/{bid}",
            json={"mission": mission_text},
        )
        response.raise_for_status()
        print(f"[MEMORY] Set bank mission for {bid}")
        return {"bank_id": bid, "mission": mission_text}
    except Exception as e:
        print(f"[MEMORY] Failed to set bank mission: {e}")
        return {}


async def set_bank_mission_async(bank_id: str = None, mission: str = None, hindsight_url: str = None) -> dict:
    """Async version of set_bank_mission."""
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(
        _executor,
        lambda: set_bank_mission(bank_id, mission, hindsight_url)
    )


def refresh_reflection(
    bank_id: str = None,
    reflection_id: str = None,
    sync: bool = True,
    poll_interval: float = 0.5,
    timeout: float = 60.0,
    hindsight_url: str = None,
) -> dict:
    """Refresh a single reflection by re-running its source query.

    Args:
        bank_id: Bank ID (uses current if not provided)
        reflection_id: The reflection ID to refresh
        sync: If True, wait for refresh to complete (default: True)
        poll_interval: Seconds between status polls when sync=True
        timeout: Maximum seconds to wait when sync=True
        hindsight_url: Optional override URL

    Returns:
        Dict with operation_id or completion status
    """
    import time

    bid = bank_id or get_bank_id()
    if not bid or not reflection_id:
        print("[MEMORY] Cannot refresh reflection: missing bank_id or reflection_id")
        return {}

    client = _get_http_client(hindsight_url)

    try:
        response = client.post(f"/v1/default/banks/{bid}/mental-models/{reflection_id}/refresh")
        response.raise_for_status()
        result = response.json()
        operation_id = result.get("operation_id")
        print(f"[MEMORY] Refresh triggered for reflection {reflection_id} (operation_id: {operation_id})")

        if not sync or not operation_id:
            return {"success": True, "status": "queued", "operation_id": operation_id}

        # Poll for completion
        start_time = time.time()
        while time.time() - start_time < timeout:
            time.sleep(poll_interval)
            try:
                status_response = client.get(f"/v1/default/banks/{bid}/operations/{operation_id}")
                status_response.raise_for_status()
                op_status = status_response.json()
                current_status = op_status.get("status")

                if current_status == "completed":
                    print(f"[MEMORY] Reflection {reflection_id} refresh completed")
                    return {"success": True, "status": "completed", "operation_id": operation_id}
                elif current_status == "failed":
                    error_msg = op_status.get("error_message", "Unknown error")
                    print(f"[MEMORY] Reflection {reflection_id} refresh failed: {error_msg}")
                    return {"success": False, "status": "failed", "error": error_msg}
                elif current_status == "not_found":
                    return {"success": True, "status": "completed", "operation_id": operation_id}
            except Exception as poll_error:
                print(f"[MEMORY] Error polling operation status: {poll_error}")

        return {"success": False, "status": "timeout", "operation_id": operation_id}

    except Exception as e:
        print(f"[MEMORY] Failed to refresh reflection: {e}")
        return {"success": False, "error": str(e)}


def refresh_mental_models(
    bank_id: str = None,
    subtype: str = None,
    sync: bool = True,
    poll_interval: float = 0.5,
    timeout: float = 60.0,
    hindsight_url: str = None,
) -> dict:
    """Refresh all mental models (reflections) for a bank.

    This triggers a refresh of all reflections, which re-runs their source queries
    through the reflect API to update their content with new memories.

    Args:
        bank_id: Bank ID (uses current if not provided)
        subtype: Optional subtype filter (unused, kept for backwards compatibility)
        sync: If True, wait for all refreshes to complete (default: True)
        poll_interval: Seconds between status polls when sync=True
        timeout: Maximum seconds to wait per reflection when sync=True
        hindsight_url: Optional override URL

    Returns:
        Dict with:
        - success: True if all refreshes succeeded
        - refreshed: Number of reflections refreshed
        - operation_ids: List of operation IDs for tracking
    """
    bid = bank_id or get_bank_id()
    if not bid:
        print("[MEMORY] Cannot refresh mental models: no bank_id")
        return {"success": False, "error": "No bank_id"}

    # Get all reflections for the bank
    reflections = get_reflections(bank_id=bid, hindsight_url=hindsight_url)
    if not reflections:
        print(f"[MEMORY] No mental models to refresh for {bid}")
        return {"success": True, "refreshed": 0, "operation_ids": []}

    print(f"[MEMORY] Refreshing {len(reflections)} mental models for {bid}")

    operation_ids = []
    success_count = 0

    for reflection in reflections:
        reflection_id = reflection.get("id")
        if not reflection_id:
            continue

        result = refresh_reflection(
            bank_id=bid,
            reflection_id=reflection_id,
            sync=sync,
            poll_interval=poll_interval,
            timeout=timeout,
            hindsight_url=hindsight_url,
        )

        if result.get("success"):
            success_count += 1
            if result.get("operation_id"):
                operation_ids.append(result["operation_id"])

    print(f"[MEMORY] Refreshed {success_count}/{len(reflections)} mental models for {bid}")

    return {
        "success": success_count == len(reflections),
        "refreshed": success_count,
        "total": len(reflections),
        "operation_ids": operation_ids,
    }


async def refresh_mental_models_async(
    bank_id: str = None,
    subtype: str = None,
    hindsight_url: str = None,
) -> dict:
    """Async version of refresh_mental_models."""
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(
        _executor,
        lambda: refresh_mental_models(bank_id, subtype, hindsight_url=hindsight_url)
    )


# --- Mental Model Refresh Interval Management ---

def get_refresh_interval(app_type: str = None, difficulty: str = None) -> int:
    """Get the mental model refresh interval for an app+difficulty.

    Returns:
        Number of deliveries between refreshes (0 = disabled)
    """
    app = app_type or _current_app_type
    diff = difficulty or _current_difficulty
    key = _get_bank_key(app, diff)
    return _refresh_interval.get(key, DEFAULT_REFRESH_INTERVAL)


def set_refresh_interval(interval: int, app_type: str = None, difficulty: str = None) -> int:
    """Set the mental model refresh interval for an app+difficulty.

    Args:
        interval: Number of deliveries between refreshes (0 = disabled)
        app_type: App type (uses current if not provided)
        difficulty: Difficulty level (uses current if not provided)

    Returns:
        The new interval value
    """
    global _refresh_interval
    app = app_type or _current_app_type
    diff = difficulty or _current_difficulty
    key = _get_bank_key(app, diff)
    _refresh_interval[key] = max(0, interval)  # Ensure non-negative
    print(f"[MEMORY] Refresh interval set to {interval} for {key}")
    return _refresh_interval[key]


def get_deliveries_since_refresh(app_type: str = None, difficulty: str = None) -> int:
    """Get the number of deliveries since last mental model refresh."""
    app = app_type or _current_app_type
    diff = difficulty or _current_difficulty
    key = _get_bank_key(app, diff)
    return _deliveries_since_refresh.get(key, 0)


def record_delivery(app_type: str = None, difficulty: str = None) -> bool:
    """Record a delivery and check if mental model refresh is needed.

    Args:
        app_type: App type (uses current if not provided)
        difficulty: Difficulty level (uses current if not provided)

    Returns:
        True if refresh should be triggered, False otherwise
    """
    global _deliveries_since_refresh
    app = app_type or _current_app_type
    diff = difficulty or _current_difficulty
    key = _get_bank_key(app, diff)

    # Increment delivery count
    _deliveries_since_refresh[key] = _deliveries_since_refresh.get(key, 0) + 1
    count = _deliveries_since_refresh[key]

    # Check if refresh is needed
    interval = get_refresh_interval(app, diff)
    if interval > 0 and count >= interval:
        print(f"[MEMORY] {count} deliveries reached, refresh triggered for {key}")
        return True

    print(f"[MEMORY] Delivery recorded for {key}: {count}/{interval if interval > 0 else 'disabled'}")
    return False


def reset_delivery_count(app_type: str = None, difficulty: str = None):
    """Reset the delivery count after a refresh."""
    global _deliveries_since_refresh
    app = app_type or _current_app_type
    diff = difficulty or _current_difficulty
    key = _get_bank_key(app, diff)
    _deliveries_since_refresh[key] = 0
    print(f"[MEMORY] Delivery count reset for {key}")


def get_reflections(bank_id: str = None, subtype: str = None, hindsight_url: str = None) -> list:
    """Get all reflections (pinned topics) for a bank.

    NOTE: Reflections are user-created pinned topics, NOT auto-generated mental models.
    For mental model counts, use get_bank_stats() which returns total_mental_models.

    Args:
        bank_id: Bank ID (uses current if not provided)
        subtype: Optional filter ('structural', 'emergent', or 'pinned')
        hindsight_url: Optional override URL

    Returns:
        List of reflections
    """
    bid = bank_id or get_bank_id()
    if not bid:
        print("[MEMORY] Cannot get reflections: no bank_id")
        return []

    client = _get_http_client(hindsight_url)
    params = {}
    if subtype:
        params["subtype"] = subtype

    try:
        response = client.get(
            f"/v1/default/banks/{bid}/mental-models",
            params=params if params else None
        )
        response.raise_for_status()
        result = response.json()
        reflections = result.get("items", [])
        print(f"[MEMORY] Got {len(reflections)} reflections for {bid}")
        return reflections
    except Exception as e:
        print(f"[MEMORY] Failed to get reflections: {e}")
        return []


# Alias for backwards compatibility
def get_mental_models(bank_id: str = None, subtype: str = None, hindsight_url: str = None) -> list:
    """Alias for get_reflections (for backwards compatibility)."""
    return get_reflections(bank_id, subtype, hindsight_url)


async def get_reflections_async(bank_id: str = None, subtype: str = None, hindsight_url: str = None) -> list:
    """Async version of get_reflections."""
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(
        _executor,
        lambda: get_reflections(bank_id, subtype, hindsight_url)
    )


# Alias for backwards compatibility
async def get_mental_models_async(bank_id: str = None, subtype: str = None, hindsight_url: str = None) -> list:
    """Alias for get_reflections_async (for backwards compatibility)."""
    return await get_reflections_async(bank_id, subtype, hindsight_url)


def get_reflection(bank_id: str = None, reflection_id: str = None, hindsight_url: str = None) -> dict:
    """Get a single reflection with full details including observations.

    Args:
        bank_id: Bank ID (uses current if not provided)
        reflection_id: The reflection ID
        hindsight_url: Optional override URL

    Returns:
        Reflection with observations and freshness metadata
    """
    bid = bank_id or get_bank_id()
    if not bid or not reflection_id:
        print("[MEMORY] Cannot get reflection: missing bank_id or reflection_id")
        return {}

    client = _get_http_client(hindsight_url)

    try:
        response = client.get(f"/v1/default/banks/{bid}/mental-models/{reflection_id}")
        response.raise_for_status()
        result = response.json()
        print(f"[MEMORY] Got reflection {reflection_id} for {bid}")
        return result
    except Exception as e:
        print(f"[MEMORY] Failed to get reflection: {e}")
        return {}


# Alias for backwards compatibility
def get_mental_model(bank_id: str = None, model_id: str = None, hindsight_url: str = None) -> dict:
    """Alias for get_reflection (for backwards compatibility)."""
    return get_reflection(bank_id, model_id, hindsight_url)


async def get_reflection_async(bank_id: str = None, reflection_id: str = None, hindsight_url: str = None) -> dict:
    """Async version of get_reflection."""
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(
        _executor,
        lambda: get_reflection(bank_id, reflection_id, hindsight_url)
    )


# Alias for backwards compatibility
async def get_mental_model_async(bank_id: str = None, model_id: str = None, hindsight_url: str = None) -> dict:
    """Alias for get_reflection_async (for backwards compatibility)."""
    return await get_reflection_async(bank_id, model_id, hindsight_url)


def create_reflection(
    bank_id: str = None,
    name: str = None,
    source_query: str = None,
    tags: list[str] = None,
    max_tokens: int = 2048,
    hindsight_url: str = None,
) -> dict:
    """Create a reflection (called "mental model" in UI).

    Reflections are living documents that auto-update when relevant memories are stored.
    The source_query is run through the reflect API to generate initial content.

    Args:
        bank_id: Bank ID (uses current if not provided)
        name: Name of the reflection (e.g., "Employee Locations")
        source_query: Query to run to generate content
        tags: Optional tags for filtering
        max_tokens: Max tokens for generated content (default 2048)
        hindsight_url: Optional override URL

    Returns:
        Dict with operation_id to track async creation
    """
    bid = bank_id or get_bank_id()
    if not bid or not name or not source_query:
        print("[MEMORY] Cannot create reflection: missing bank_id, name, or source_query")
        return {}

    client = _get_http_client(hindsight_url)

    try:
        response = client.post(
            f"/v1/default/banks/{bid}/mental-models",
            json={
                "name": name,
                "source_query": source_query,
                "tags": tags or [],
                "max_tokens": max_tokens,
                "trigger": {"refresh_after_consolidation": True},
            }
        )
        response.raise_for_status()
        result = response.json()
        print(f"[MEMORY] Created reflection '{name}' for {bid} (operation_id: {result.get('operation_id')})")
        return result
    except Exception as e:
        print(f"[MEMORY] Failed to create reflection: {e}")
        return {}


# Alias for backwards compatibility (UI calls these "mental models")
def create_mental_model(
    bank_id: str = None,
    name: str = None,
    source_query: str = None,
    tags: list[str] = None,
    max_tokens: int = 2048,
    hindsight_url: str = None,
) -> dict:
    """Alias for create_reflection (UI calls these 'mental models')."""
    return create_reflection(bank_id, name, source_query, tags, max_tokens, hindsight_url)


async def create_reflection_async(
    bank_id: str = None,
    name: str = None,
    source_query: str = None,
    tags: list[str] = None,
    max_tokens: int = 2048,
    hindsight_url: str = None,
) -> dict:
    """Async version of create_reflection."""
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(
        _executor,
        lambda: create_reflection(bank_id, name, source_query, tags, max_tokens, hindsight_url)
    )


# Alias for backwards compatibility (UI calls these "mental models")
async def create_mental_model_async(
    bank_id: str = None,
    name: str = None,
    source_query: str = None,
    tags: list[str] = None,
    max_tokens: int = 2048,
    hindsight_url: str = None,
) -> dict:
    """Alias for create_reflection_async (UI calls these 'mental models')."""
    return await create_reflection_async(bank_id, name, source_query, tags, max_tokens, hindsight_url)


def create_default_mental_models(bank_id: str = None, hindsight_url: str = None) -> list[dict]:
    """Create the default mental models (reflections) for a bank.

    Creates reflections for:
    - Employee Locations
    - Building Layout
    - Optimal Delivery Paths

    Args:
        bank_id: Bank ID (uses current if not provided)
        hindsight_url: Optional override URL

    Returns:
        List of created reflection operation results
    """
    bid = bank_id or get_bank_id()
    if not bid:
        print("[MEMORY] Cannot create default mental models: no bank_id")
        return []

    results = []
    for name, source_query in DEFAULT_MENTAL_MODELS:
        result = create_reflection(
            bank_id=bid,
            name=name,
            source_query=source_query,
            hindsight_url=hindsight_url,
        )
        if result:
            results.append(result)

    print(f"[MEMORY] Created {len(results)} default mental models for {bid}")
    return results


async def create_default_mental_models_async(bank_id: str = None, hindsight_url: str = None) -> list[dict]:
    """Async version of create_default_mental_models."""
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(
        _executor,
        lambda: create_default_mental_models(bank_id, hindsight_url)
    )


def delete_reflection(bank_id: str = None, reflection_id: str = None, hindsight_url: str = None) -> bool:
    """Delete a reflection.

    Args:
        bank_id: Bank ID (uses current if not provided)
        reflection_id: The reflection ID to delete
        hindsight_url: Optional override URL

    Returns:
        True if successful
    """
    bid = bank_id or get_bank_id()
    if not bid or not reflection_id:
        print("[MEMORY] Cannot delete reflection: missing bank_id or reflection_id")
        return False

    client = _get_http_client(hindsight_url)

    try:
        response = client.delete(f"/v1/default/banks/{bid}/mental-models/{reflection_id}")
        response.raise_for_status()
        print(f"[MEMORY] Deleted reflection {reflection_id} from {bid}")
        return True
    except Exception as e:
        print(f"[MEMORY] Failed to delete reflection: {e}")
        return False


# Alias for backwards compatibility
def delete_mental_model(bank_id: str = None, model_id: str = None, hindsight_url: str = None) -> bool:
    """Alias for delete_reflection (for backwards compatibility)."""
    return delete_reflection(bank_id, model_id, hindsight_url)


async def delete_reflection_async(bank_id: str = None, reflection_id: str = None, hindsight_url: str = None) -> bool:
    """Async version of delete_reflection."""
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(
        _executor,
        lambda: delete_reflection(bank_id, reflection_id, hindsight_url)
    )


# Alias for backwards compatibility
async def delete_mental_model_async(bank_id: str = None, model_id: str = None, hindsight_url: str = None) -> bool:
    """Alias for delete_reflection_async (for backwards compatibility)."""
    return await delete_reflection_async(bank_id, model_id, hindsight_url)


def clear_mental_models(bank_id: str = None, hindsight_url: str = None) -> dict:
    """Clear all mental model facts for a bank.

    This deletes the auto-generated mental_model fact types created by consolidation.
    Use this to reset consolidated knowledge before a new benchmark run.

    NOTE: This is different from reflections - it clears the fact types, not pinned topics.

    Args:
        bank_id: Bank ID (uses current if not provided)
        hindsight_url: Optional override URL

    Returns:
        Response with deletion status
    """
    bid = bank_id or get_bank_id()
    if not bid:
        print("[MEMORY] Cannot clear mental models: no bank_id")
        return {"success": False, "error": "No bank_id"}

    client = _get_http_client(hindsight_url)

    try:
        # DELETE /observations clears the observation fact types (formerly mental_model facts)
        response = client.delete(f"/v1/default/banks/{bid}/observations")
        response.raise_for_status()
        result = response.json()
        deleted_count = result.get("deleted", 0)
        print(f"[MEMORY] Cleared {deleted_count} mental models from {bid}")
        return {"success": True, "deleted": deleted_count}
    except Exception as e:
        print(f"[MEMORY] Failed to clear mental models: {e}")
        return {"success": False, "error": str(e)}


async def clear_mental_models_async(bank_id: str = None, hindsight_url: str = None) -> dict:
    """Async version of clear_mental_models."""
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(
        _executor,
        lambda: clear_mental_models(bank_id, hindsight_url)
    )


def get_bank_stats(bank_id: str = None, hindsight_url: str = None) -> dict:
    """Get statistics for a memory bank including consolidation status.

    Args:
        bank_id: Bank ID (uses current if not provided)
        hindsight_url: Optional override URL

    Returns:
        Bank statistics including:
        - total_nodes: Total number of memory nodes
        - total_links: Total number of links
        - total_documents: Total documents stored
        - pending_consolidation: Memories not yet processed into mental models
        - total_mental_models: Total number of mental models
        - last_consolidated_at: When consolidation last ran
    """
    bid = bank_id or get_bank_id()
    if not bid:
        print("[MEMORY] Cannot get bank stats: no bank_id")
        return {}

    client = _get_http_client(hindsight_url)

    try:
        response = client.get(f"/v1/default/banks/{bid}/stats")
        response.raise_for_status()
        result = response.json()
        print(f"[MEMORY] Got stats for {bid}: {result.get('total_nodes', 0)} nodes, {result.get('total_mental_models', 0)} mental models")
        return result
    except Exception as e:
        print(f"[MEMORY] Failed to get bank stats: {e}")
        return {}


async def get_bank_stats_async(bank_id: str = None, hindsight_url: str = None) -> dict:
    """Async version of get_bank_stats."""
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(
        _executor,
        lambda: get_bank_stats(bank_id, hindsight_url)
    )


def wait_for_pending_consolidation(
    bank_id: str = None,
    poll_interval: float = 2.0,
    timeout: float = 300.0,
    hindsight_url: str = None,
) -> bool:
    """Wait for pending_consolidation to reach 0 (all memories processed into mental models).

    This matches the eval framework behavior where we wait for the background
    consolidation worker to process memories after each retain.

    NOTE: Requires HINDSIGHT_API_ENABLE_OBSERVATIONS=true on the Hindsight server.

    Args:
        bank_id: Bank ID (uses current if not provided)
        poll_interval: Seconds between status polls (default: 2.0)
        timeout: Maximum seconds to wait (default: 300.0)
        hindsight_url: Optional override URL

    Returns:
        True if consolidation completed, False if timed out
    """
    import time

    bid = bank_id or get_bank_id()
    if not bid:
        print("[MEMORY] Cannot wait for consolidation: no bank_id")
        return False

    _debug_mem(f"WAIT_FOR_CONSOLIDATION called:")
    _debug_mem(f"  bank_id={bid}")
    _debug_mem(f"  poll_interval={poll_interval}s, timeout={timeout}s")

    start_time = time.time()
    poll_count = 0
    while True:
        elapsed = time.time() - start_time
        if elapsed > timeout:
            _debug_mem(f"  !!! CONSOLIDATION TIMEOUT after {timeout}s for {bid}")
            print(f"[MEMORY] Consolidation did not complete within {timeout}s for {bid}")
            return False

        stats = get_bank_stats(bid, hindsight_url)
        pending = stats.get("pending_consolidation", 0)
        total_mm = stats.get("total_mental_models", 0)

        poll_count += 1
        if pending == 0:
            _debug_mem(f"  <<< CONSOLIDATION COMPLETE for {bid} after {poll_count} polls, {elapsed:.1f}s")
            _debug_mem(f"  Mental models in bank: {total_mm}")
            print(f"[MEMORY] Consolidation complete for {bid} (no pending memories)")
            return True

        _debug_mem(f"  Polling #{poll_count}: {pending} pending, {total_mm} mental models, {elapsed:.1f}s elapsed")
        print(f"[MEMORY] Waiting for consolidation: {pending} pending, {elapsed:.1f}s elapsed for {bid}")
        time.sleep(poll_interval)


async def wait_for_pending_consolidation_async(
    bank_id: str = None,
    poll_interval: float = 2.0,
    timeout: float = 300.0,
    hindsight_url: str = None,
) -> bool:
    """Async version of wait_for_pending_consolidation."""
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(
        _executor,
        lambda: wait_for_pending_consolidation(bank_id, poll_interval, timeout, hindsight_url)
    )
