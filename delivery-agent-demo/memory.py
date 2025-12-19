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

    hindsight_litellm.configure(
        hindsight_api_url=url,
        bank_id=_current_bank_id,
        bank_name="Delivery Agent Memory",
        store_conversations=True,  # Auto-store conversation after each LLM call
        inject_memories=True,      # Auto-inject relevant memories before each LLM call
        use_reflect=False,         # Use raw facts, not synthesized responses
        verbose=verbose,
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
    config = hindsight_litellm.get_config()
    if config:
        # Reconfigure with the new document_id
        hindsight_litellm.configure(
            hindsight_api_url=config.hindsight_api_url,
            bank_id=config.bank_id,
            bank_name=config.bank_name,
            store_conversations=config.store_conversations,
            inject_memories=config.inject_memories,
            use_reflect=config.use_reflect,
            verbose=config.verbose,
            document_id=document_id,
        )


def completion(**kwargs):
    """
    Call LLM with automatic memory injection and storage.

    This is a pass-through to hindsight_litellm.completion() which handles:
    - Recalling relevant memories based on the conversation
    - Injecting them into the system prompt
    - Storing the conversation after the response (with document_id grouping)
    - Deduplicating facts automatically
    """
    return hindsight_litellm.completion(**kwargs)
