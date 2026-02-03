"""
Hindsight Memory Integration Module

Uses hindsight_litellm package for automatic memory injection and storage.
The demo only uses completion() - Hindsight handles everything automatically.
"""

import os
import uuid
import hindsight_litellm


# Debug mode - set to True to enable verbose logging
DEBUG = os.environ.get("DEBUG", "").lower() in ("1", "true")

# Current bank ID (set per session)
_current_bank_id: str = None


def _debug_log(msg: str):
    """Write to debug log only if DEBUG is enabled."""
    if DEBUG:
        with open("/tmp/demo.log", "a") as f:
            f.write(f"{msg}\n")


def configure_memory(api_url: str = None, verbose: bool = True, session_id: str = None):
    """
    Configure hindsight_litellm for the delivery agent.

    Args:
        api_url: Hindsight API URL (defaults to HINDSIGHT_API_URL env var or localhost:8888)
        verbose: Enable debug logging (for injection debug info)
        session_id: Unique session ID (generated if not provided)
    """
    global _current_bank_id

    url = api_url or os.environ.get("HINDSIGHT_API_URL", "http://localhost:8888")

    # Generate unique bank ID per session
    if session_id:
        _current_bank_id = f"delivery-agent-{session_id}"
    else:
        _current_bank_id = f"delivery-agent-{uuid.uuid4().hex[:8]}"

    # Configure static settings
    hindsight_litellm.configure(
        hindsight_api_url=url,
        store_conversations=False,  # Disabled - we explicitly retain at delivery success
        inject_memories=True,       # Auto-inject relevant memories before each LLM call
        verbose=verbose,
    )

    # Set per-call defaults
    hindsight_litellm.set_defaults(
        bank_id=_current_bank_id,
        use_reflect=False,         # Use raw facts, not synthesized responses
    )

    hindsight_litellm.enable()

    return _current_bank_id


def get_bank_id() -> str:
    """Get the current session's bank ID."""
    return _current_bank_id


def set_document_id(document_id: str):
    """
    Set the document_id for grouping memories per delivery.

    When document_id is set, Hindsight uses upsert behavior:
    - Same document_id = replace previous version
    - Hindsight deduplicates facts automatically

    Args:
        document_id: Unique ID for this delivery (e.g., "delivery-1")
    """
    # Use the new clean API from hindsight_litellm
    hindsight_litellm.set_document_id(document_id)


def completion(**kwargs):
    """
    Call LLM with automatic memory injection and storage.

    This is a pass-through to hindsight_litellm.completion() which handles:
    - Recalling relevant memories based on the conversation
    - Injecting them into the system prompt
    - Storing the conversation after the response (with document_id grouping)
    - Deduplicating facts automatically
    """
    _debug_log(f"[HINDSIGHT] completion() bank={_current_bank_id}, model={kwargs.get('model', 'N/A')}")

    try:
        result = hindsight_litellm.completion(**kwargs)
        # Log injection info if debug enabled
        if DEBUG:
            try:
                injection_debug = hindsight_litellm.get_last_injection_debug()
                if injection_debug:
                    _debug_log(f"[HINDSIGHT] Injection: injected={injection_debug.injected}, count={injection_debug.results_count}")
            except Exception:
                pass  # Silently ignore debug errors
        return result
    except Exception as e:
        _debug_log(f"[HINDSIGHT] ERROR: {e}")
        raise


def retain(content: str, sync: bool = False):
    """
    Explicitly store content to Hindsight memory.

    Use this for storing information that won't be captured by automatic
    conversation storage (e.g., final tool results when conversation ends).

    Args:
        content: The text content to store
        sync: If True, block until storage completes. If False (default),
            run in background thread for better performance.
    """
    return hindsight_litellm.retain(content, sync=sync)


def get_pending_storage_errors():
    """
    Get any pending storage errors from async background storage.

    Storage runs asynchronously by default for performance. Call this
    at delivery completion to check if any storage operations failed.

    Returns:
        List of HindsightError exceptions from failed storage operations.
        Returns empty list if no errors.
    """
    return hindsight_litellm.get_pending_storage_errors()


def get_pending_retain_errors():
    """
    Get any pending errors from async background retain operations.

    When using retain(sync=False), errors are collected in the background.
    Call this periodically to check for and handle any failures.

    Returns:
        List of exceptions from failed background retain operations.
        The list is cleared after calling this function.
    """
    return hindsight_litellm.get_pending_retain_errors()
