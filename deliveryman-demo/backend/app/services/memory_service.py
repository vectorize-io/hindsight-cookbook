"""Memory service wrapper around hindsight_litellm."""

import uuid
import asyncio
import concurrent.futures
import httpx
import hindsight_litellm
from ..config import HINDSIGHT_API_URL

# HTTP client for direct API calls (mental models, mission)
_http_client: httpx.Client | None = None

def _get_http_client() -> httpx.Client:
    """Get or create HTTP client for direct Hindsight API calls."""
    global _http_client
    if _http_client is None:
        _http_client = httpx.Client(base_url=HINDSIGHT_API_URL, timeout=60.0)
    return _http_client

# Thread pool for running sync hindsight_litellm calls from async context
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


def configure_memory(bank_id: str = None, set_background: bool = True, app_type: str = None, difficulty: str = None, set_mission: bool = True) -> str:
    """Configure hindsight_litellm for the demo.

    Args:
        bank_id: Bank ID to use (generates new random one if not provided)
        set_background: Whether to set the bank background
        app_type: App type (demo or bench) for prefix and tracking
        difficulty: Difficulty level (easy, medium, hard) for separate banks
        set_mission: Whether to set the bank mission (for mental models)

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
    hindsight_litellm.configure(
        hindsight_api_url=HINDSIGHT_API_URL,
        store_conversations=False,  # We store manually after delivery
        inject_memories=False,  # We inject manually using recall/reflect
        verbose=True,
    )

    # Set per-call defaults (bank_id, budget, reflect settings)
    hindsight_litellm.set_defaults(
        bank_id=new_bank_id,
        use_reflect=True,  # Use reflect for intelligent memory synthesis
        budget="high",  # Use high budget for better memory retrieval
    )

    # Enable the integration
    hindsight_litellm.enable()

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
    # Update the defaults' bank_id
    hindsight_litellm.set_defaults(bank_id=bank_id)

    if add_to_history:
        _add_to_history(bank_id, app, diff)

    if set_background:
        try:
            hindsight_litellm.set_bank_mission(mission=BANK_MISSION)
            print(f"Bank mission set for: {bank_id}")
        except Exception as e:
            print(f"Warning: Failed to set bank mission: {e}")


def set_bank_mission_async(mission: str = None):
    """Set bank mission in a thread pool to avoid event loop issues.

    This is a fire-and-forget operation that won't block.
    """
    m = mission or BANK_MISSION
    def _set_mission():
        try:
            hindsight_litellm.set_bank_mission(mission=m)
            bank_id = get_bank_id()
            print(f"Bank mission set for: {bank_id}")
        except Exception as e:
            print(f"Warning: Failed to set bank mission: {e}")

    _executor.submit(_set_mission)


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


# =============================================================================
# Bank Creation API (direct HTTP calls to Hindsight)
# =============================================================================

def create_bank(bank_id: str, name: str = None, background: str = None, mission: str = None) -> dict:
    """Create a memory bank in Hindsight.

    Args:
        bank_id: Unique bank ID
        name: Optional display name (defaults to bank_id)
        background: Optional bank background/context
        mission: Optional mission for mental models

    Returns:
        Response from the API
    """
    client = _get_http_client()

    payload = {
        "name": name or bank_id,
    }
    if background:
        payload["background"] = background
    if mission:
        payload["mission"] = mission

    try:
        # Use PUT /v1/default/banks/{bank_id} to create/update bank
        response = client.put(f"/v1/default/banks/{bank_id}", json=payload)
        if response.status_code == 200 or response.status_code == 201:
            print(f"[MEMORY] Created/updated bank: {bank_id}")
            return response.json()
        else:
            print(f"[MEMORY] Failed to create bank {bank_id}: {response.status_code} - {response.text}")
            return {}
    except Exception as e:
        print(f"[MEMORY] Error creating bank {bank_id}: {e}")
        return {}


# =============================================================================
# Mental Models API (direct HTTP calls to Hindsight)
# =============================================================================

def set_bank_mission(bank_id: str = None, mission: str = None) -> dict:
    """Set the mission for a memory bank (used by mental models).

    Args:
        bank_id: Bank ID (uses current if not provided)
        mission: Mission text (uses BANK_MISSION if not provided)

    Returns:
        Response from the API
    """
    bid = bank_id or get_bank_id()
    if not bid:
        print("[MEMORY] Cannot set mission: no bank_id")
        return {}

    mission_text = mission or BANK_MISSION
    client = _get_http_client()

    try:
        response = client.put(
            f"/v1/default/banks/{bid}/mission",
            json={"mission": mission_text}
        )
        response.raise_for_status()
        result = response.json()
        print(f"[MEMORY] Set bank mission for {bid}")
        return result
    except Exception as e:
        print(f"[MEMORY] Failed to set bank mission: {e}")
        return {}


async def set_bank_mission_async(bank_id: str = None, mission: str = None) -> dict:
    """Async version of set_bank_mission."""
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(
        _executor,
        lambda: set_bank_mission(bank_id, mission)
    )


def refresh_mental_models(bank_id: str = None, subtype: str = None, sync: bool = True, poll_interval: float = 0.5, timeout: float = 60.0) -> dict:
    """Refresh mental models for a bank.

    This triggers the Hindsight backend to analyze memories and create/update
    mental models based on the bank's mission and stored experiences.

    Args:
        bank_id: Bank ID (uses current if not provided)
        subtype: Optional subtype filter ('structural' or 'emergent')
        sync: If True, poll until refresh completes before returning (default: True)
        poll_interval: Seconds between status polls when sync=True (default: 0.5)
        timeout: Maximum seconds to wait when sync=True (default: 60.0)

    Returns:
        Response with operation status
    """
    import time

    bid = bank_id or get_bank_id()
    if not bid:
        print("[MEMORY] Cannot refresh mental models: no bank_id")
        return {}

    client = _get_http_client()
    body = {}
    if subtype:
        body["subtype"] = subtype

    try:
        # Submit the refresh operation
        response = client.post(
            f"/v1/default/banks/{bid}/mental-models/refresh",
            json=body if body else None,
        )
        response.raise_for_status()
        result = response.json()
        operation_id = result.get("operation_id")
        print(f"[MEMORY] Mental models refresh triggered for {bid}, operation_id: {operation_id}")

        if not sync or not operation_id:
            return result

        # Poll for completion
        start_time = time.time()
        while time.time() - start_time < timeout:
            time.sleep(poll_interval)
            try:
                status_response = client.get(
                    f"/v1/default/banks/{bid}/operations/{operation_id}"
                )
                status_response.raise_for_status()
                status = status_response.json()
                op_status = status.get("status")
                print(f"[MEMORY] Refresh operation {operation_id} status: {op_status}")

                if op_status == "completed":
                    print(f"[MEMORY] Mental models refresh completed for {bid}")
                    return {"success": True, "operation_id": operation_id, "status": "completed"}
                elif op_status == "failed":
                    error_msg = status.get("error_message", "Unknown error")
                    print(f"[MEMORY] Mental models refresh failed for {bid}: {error_msg}")
                    return {"success": False, "operation_id": operation_id, "status": "failed", "error": error_msg}
                elif op_status == "not_found":
                    # Operation completed and was removed from storage
                    print(f"[MEMORY] Mental models refresh completed for {bid} (operation cleaned up)")
                    return {"success": True, "operation_id": operation_id, "status": "completed"}
                # Still pending, continue polling
            except Exception as poll_error:
                print(f"[MEMORY] Error polling operation status: {poll_error}")

        print(f"[MEMORY] Mental models refresh timed out after {timeout}s for {bid}")
        return {"success": False, "operation_id": operation_id, "status": "timeout"}

    except Exception as e:
        print(f"[MEMORY] Failed to refresh mental models: {e}")
        return {}


async def refresh_mental_models_async(bank_id: str = None, subtype: str = None) -> dict:
    """Async version of refresh_mental_models."""
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(
        _executor,
        lambda: refresh_mental_models(bank_id, subtype)
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


def get_mental_models(bank_id: str = None, subtype: str = None) -> list:
    """Get all mental models for a bank.

    Args:
        bank_id: Bank ID (uses current if not provided)
        subtype: Optional filter ('structural', 'emergent', or 'pinned')

    Returns:
        List of mental models
    """
    bid = bank_id or get_bank_id()
    if not bid:
        print("[MEMORY] Cannot get mental models: no bank_id")
        return []

    client = _get_http_client()
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
        # API returns "items" but we normalize to "models"
        models = result.get("items", result.get("models", []))
        print(f"[MEMORY] Got {len(models)} mental models for {bid}")
        return models
    except Exception as e:
        print(f"[MEMORY] Failed to get mental models: {e}")
        return []


async def get_mental_models_async(bank_id: str = None, subtype: str = None) -> list:
    """Async version of get_mental_models."""
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(
        _executor,
        lambda: get_mental_models(bank_id, subtype)
    )


def get_mental_model(bank_id: str = None, model_id: str = None) -> dict:
    """Get a single mental model with full details including observations.

    Args:
        bank_id: Bank ID (uses current if not provided)
        model_id: The mental model ID

    Returns:
        Mental model with observations and freshness metadata
    """
    bid = bank_id or get_bank_id()
    if not bid or not model_id:
        print("[MEMORY] Cannot get mental model: missing bank_id or model_id")
        return {}

    client = _get_http_client()

    try:
        response = client.get(f"/v1/default/banks/{bid}/mental-models/{model_id}")
        response.raise_for_status()
        result = response.json()
        print(f"[MEMORY] Got mental model {model_id} for {bid}")
        return result
    except Exception as e:
        print(f"[MEMORY] Failed to get mental model: {e}")
        return {}


async def get_mental_model_async(bank_id: str = None, model_id: str = None) -> dict:
    """Async version of get_mental_model."""
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(
        _executor,
        lambda: get_mental_model(bank_id, model_id)
    )


def create_pinned_model(bank_id: str = None, name: str = None, description: str = None) -> dict:
    """Create a pinned mental model (user-defined topic to track).

    Args:
        bank_id: Bank ID (uses current if not provided)
        name: Name of the model (e.g., "Employee Locations")
        description: Description of what to track

    Returns:
        Created mental model
    """
    bid = bank_id or get_bank_id()
    if not bid or not name:
        print("[MEMORY] Cannot create pinned model: missing bank_id or name")
        return {}

    client = _get_http_client()

    try:
        response = client.post(
            f"/v1/default/banks/{bid}/mental-models",
            json={
                "name": name,
                "description": description or name,
                "subtype": "pinned"
            }
        )
        response.raise_for_status()
        result = response.json()
        print(f"[MEMORY] Created pinned model '{name}' for {bid}")
        return result
    except Exception as e:
        print(f"[MEMORY] Failed to create pinned model: {e}")
        return {}


async def create_pinned_model_async(bank_id: str = None, name: str = None, description: str = None) -> dict:
    """Async version of create_pinned_model."""
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(
        _executor,
        lambda: create_pinned_model(bank_id, name, description)
    )


def delete_mental_model(bank_id: str = None, model_id: str = None) -> bool:
    """Delete a mental model.

    Args:
        bank_id: Bank ID (uses current if not provided)
        model_id: The mental model ID to delete

    Returns:
        True if successful
    """
    bid = bank_id or get_bank_id()
    if not bid or not model_id:
        print("[MEMORY] Cannot delete mental model: missing bank_id or model_id")
        return False

    client = _get_http_client()

    try:
        response = client.delete(f"/v1/default/banks/{bid}/mental-models/{model_id}")
        response.raise_for_status()
        print(f"[MEMORY] Deleted mental model {model_id} from {bid}")
        return True
    except Exception as e:
        print(f"[MEMORY] Failed to delete mental model: {e}")
        return False


async def delete_mental_model_async(bank_id: str = None, model_id: str = None) -> bool:
    """Async version of delete_mental_model."""
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(
        _executor,
        lambda: delete_mental_model(bank_id, model_id)
    )
