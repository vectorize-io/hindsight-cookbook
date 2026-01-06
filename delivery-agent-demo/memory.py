"""
Hindsight Memory Integration Module

Uses hindsight_litellm package for automatic memory injection and storage.
The demo only uses completion() - Hindsight handles everything automatically.
"""

import os
import uuid
import hindsight_litellm


# Current bank ID (set per session)
_current_bank_id: str = None


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
    # DEBUG: Log that we're using hindsight_litellm
    with open("/tmp/demo.log", "a") as f:
        f.write(f"\n[HINDSIGHT] Calling hindsight_litellm.completion()\n")
        f.write(f"[HINDSIGHT] Bank ID: {_current_bank_id}\n")
        f.write(f"[HINDSIGHT] Model: {kwargs.get('model', 'N/A')}\n")
        f.write(f"[HINDSIGHT] Tools passed: {len(kwargs.get('tools', []))} tools\n")

    try:
        result = hindsight_litellm.completion(**kwargs)
        # DEBUG: Log after completion
        with open("/tmp/demo.log", "a") as f:
            f.write(f"[HINDSIGHT] Completion returned successfully\n")
        return result
    except Exception as e:
        with open("/tmp/demo.log", "a") as f:
            f.write(f"[HINDSIGHT] ERROR: {e}\n")
        raise


def retain(content: str):
    """
    Explicitly store content to Hindsight memory.

    Use this for storing information that won't be captured by automatic
    conversation storage (e.g., final tool results when conversation ends).
    """
    return hindsight_litellm.retain(content)


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
