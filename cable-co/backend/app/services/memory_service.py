"""Memory service — Hindsight integration for CableConnect.

Uses hindsight_client directly for retain/recall/reflect (with API key auth).
Uses hindsight_litellm only for LLM completion passthrough.
"""

import asyncio
import time
import concurrent.futures
import hindsight_litellm
from hindsight_client import Hindsight
from ..config import get_hindsight_url, HINDSIGHT_API_KEY, HINDSIGHT_BANK_NAME
import httpx

# Thread pool for running sync operations from async context
_executor = concurrent.futures.ThreadPoolExecutor(max_workers=4)

# Hindsight client (with API key)
_hs_client: Hindsight | None = None

# HTTP client for bank/mental-model management
_http_client: httpx.Client | None = None
_http_client_url: str | None = None

_configured: bool = False

# Scenario tracking for mental model refresh
_scenarios_since_refresh: int = 0
_refresh_interval: int = 5
DEFAULT_REFRESH_INTERVAL = 5

# Bank configuration
BANK_MISSION = (
    "I am a customer service AI copilot at CableConnect, a cable and internet provider. "
    "I learn company policies, billing adjustment limits, dispatch procedures, "
    "retention eligibility rules, and outage handling protocols from CSR feedback "
    "to make better suggestions over time."
)

DEFAULT_MENTAL_MODELS = [
    (
        "Customer Communication Style",
        "How should I talk to customers? What tone and language does the CSR expect? "
        "What jargon or internal terminology should I avoid? How concise should my responses be? "
        "What have CSRs corrected about my wording, phrasing, or communication approach?",
    ),
    (
        "Conversation Flow & Resolution",
        "When should I resolve an interaction? What steps must I take before ending the conversation? "
        "How do I handle follow-up questions? Should I let the customer end the call or can I end it? "
        "What feedback have CSRs given about wrapping up conversations too early or presuming to end them?",
    ),
    (
        "Investigation & Problem Solving",
        "How thoroughly should I investigate before suggesting a response? What lookups should I do "
        "for billing inquiries, technical issues, credit requests, and retention scenarios? "
        "What has the CSR corrected about not checking enough information before responding? "
        "Should I compare past bills? Check outage status? Run diagnostics before dispatch?",
    ),
    (
        "Policy & Business Rules",
        "What are the credit and adjustment limits? What are the rules for outage credits? "
        "When must I run diagnostics before scheduling a technician? What are the retention offer "
        "eligibility requirements (tenure, etc.)? What policy mistakes have CSRs corrected?",
    ),
]


def _get_hs_client() -> Hindsight:
    """Get or create the Hindsight client with API key."""
    global _hs_client
    if _hs_client is None:
        _hs_client = Hindsight(
            base_url=get_hindsight_url(),
            api_key=HINDSIGHT_API_KEY or None,
            timeout=60.0,
        )
    return _hs_client


def _get_http_client() -> httpx.Client:
    global _http_client, _http_client_url
    url = get_hindsight_url()
    if _http_client is None or _http_client_url != url:
        if _http_client is not None:
            _http_client.close()
        headers = {}
        if HINDSIGHT_API_KEY:
            headers["Authorization"] = f"Bearer {HINDSIGHT_API_KEY}"
        _http_client = httpx.Client(base_url=url, timeout=60.0, headers=headers)
        _http_client_url = url
    return _http_client


def get_bank_id() -> str:
    return HINDSIGHT_BANK_NAME


def configure_memory() -> str:
    """Configure Hindsight for CableConnect. Returns the bank name."""
    global _configured

    bank_id = HINDSIGHT_BANK_NAME

    # Create/ensure bank via HTTP (PUT is idempotent)
    _create_bank(bank_id, mission=BANK_MISSION)

    # Configure hindsight_litellm (used only for completion passthrough)
    configure_kwargs = {
        "hindsight_api_url": get_hindsight_url(),
        "bank_id": bank_id,
        "store_conversations": False,
        "inject_memories": False,
        "verbose": True,
    }
    if HINDSIGHT_API_KEY:
        configure_kwargs["api_key"] = HINDSIGHT_API_KEY
    hindsight_litellm.configure(**configure_kwargs)
    hindsight_litellm.enable()

    _configured = True
    print(f"[MEMORY] Configured bank: {bank_id}")

    # Ensure mental models exist
    _ensure_mental_models(bank_id)
    return bank_id


def _create_bank(bank_id: str, mission: str = None):
    """Create a bank via HTTP API (PUT is idempotent)."""
    try:
        client = _get_http_client()
        body = {"name": bank_id}
        if mission:
            body["mission"] = mission
        response = client.put(f"/v1/default/banks/{bank_id}", json=body)
        response.raise_for_status()
        print(f"[MEMORY] Bank ready: {bank_id}")
    except Exception as e:
        print(f"[MEMORY] Error creating bank {bank_id}: {e}")


def clear_bank() -> bool:
    """Delete the bank and re-create it fresh with mental models."""
    global _scenarios_since_refresh, _hs_client
    bank_id = HINDSIGHT_BANK_NAME
    try:
        client = _get_http_client()
        response = client.delete(f"/v1/default/banks/{bank_id}")
        response.raise_for_status()
        print(f"[MEMORY] Deleted bank: {bank_id}")
    except Exception as e:
        print(f"[MEMORY] Error deleting bank {bank_id}: {e}")

    # Reset client so it reconnects fresh
    _hs_client = None
    _scenarios_since_refresh = 0
    configure_memory()
    return True


def ensure_bank_exists() -> bool:
    global _configured
    if _configured:
        return True
    try:
        configure_memory()
        return True
    except Exception as e:
        print(f"[MEMORY] Error configuring: {e}")
        return False


# ---------------------------------------------------------------------------
# Memory operations — using hindsight_client directly
# ---------------------------------------------------------------------------

async def completion(**kwargs):
    """LLM completion via hindsight_litellm (async-safe)."""
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(_executor, lambda: hindsight_litellm.completion(**kwargs))


async def retain_async(content: str, context: str = None, session_id: str = None, bank_id: str = None, tags: list[str] = None):
    bid = bank_id or get_bank_id()
    t0 = time.time()
    try:
        client = _get_hs_client()
        if tags:
            # Use retain_batch to support per-item tags
            item = {"content": content}
            if context:
                item["context"] = context
            if tags:
                item["tags"] = tags
            result = await client.aretain_batch(
                bank_id=bid,
                items=[item],
                document_id=session_id,
            )
        else:
            result = await client.aretain(
                bank_id=bid,
                content=content,
                context=context,
                document_id=session_id,
            )
        print(f"[MEMORY] Retain success in {time.time()-t0:.2f}s (bank={bid})")
        return result
    except Exception as e:
        print(f"[MEMORY] Retain failed in {time.time()-t0:.2f}s: {e}")
        import traceback
        traceback.print_exc()
        raise


async def recall_async(query: str, budget: str = "high", bank_id: str = None):
    bid = bank_id or get_bank_id()
    t0 = time.time()
    try:
        client = _get_hs_client()
        result = await client.arecall(
            bank_id=bid,
            query=query,
            budget=budget,
        )
        num = len(result) if result else 0
        print(f"[MEMORY] Recall returned {num} facts in {time.time()-t0:.2f}s")
        return result
    except Exception as e:
        print(f"[MEMORY] Recall failed in {time.time()-t0:.2f}s: {e}")
        import traceback
        traceback.print_exc()
        raise


def format_recall_as_context(recall_response) -> str:
    if not recall_response:
        return ""
    return "\n".join(f"- {r.text}" for r in recall_response)


async def reflect_async(query: str, budget: str = "high", context: str = None, bank_id: str = None):
    bid = bank_id or get_bank_id()
    t0 = time.time()
    try:
        client = _get_hs_client()
        result = await client.areflect(
            bank_id=bid,
            query=query,
            budget=budget,
            context=context,
        )
        rlen = len(result.text) if result and hasattr(result, "text") and result.text else 0
        print(f"[MEMORY] Reflect returned {rlen} chars in {time.time()-t0:.2f}s")
        return result
    except Exception as e:
        print(f"[MEMORY] Reflect failed in {time.time()-t0:.2f}s: {e}")
        import traceback
        traceback.print_exc()
        raise


# ---------------------------------------------------------------------------
# Mental models
# ---------------------------------------------------------------------------

def get_mental_models(bank_id: str = None) -> list:
    bid = bank_id or get_bank_id()
    if not bid:
        return []
    client = _get_http_client()
    try:
        response = client.get(f"/v1/default/banks/{bid}/mental-models")
        response.raise_for_status()
        return response.json().get("items", [])
    except Exception as e:
        print(f"[MEMORY] Failed to get mental models: {e}")
        return []


async def get_mental_models_async(bank_id: str = None) -> list:
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(_executor, lambda: get_mental_models(bank_id))


def create_mental_model(bank_id: str = None, name: str = None, source_query: str = None) -> dict:
    bid = bank_id or get_bank_id()
    if not bid or not name or not source_query:
        return {}
    client = _get_http_client()
    try:
        response = client.post(
            f"/v1/default/banks/{bid}/mental-models",
            json={"name": name, "source_query": source_query, "tags": [], "max_tokens": 2048},
        )
        response.raise_for_status()
        result = response.json()
        print(f"[MEMORY] Created mental model '{name}' for {bid}")
        return result
    except Exception as e:
        print(f"[MEMORY] Failed to create mental model: {e}")
        return {}


def _ensure_mental_models(bank_id: str = None) -> list[dict]:
    """Create mental models only if they don't already exist."""
    bid = bank_id or get_bank_id()
    if not bid:
        return []
    existing = get_mental_models(bank_id=bid)
    existing_names = {m.get("name") for m in existing}
    results = []
    for name, source_query in DEFAULT_MENTAL_MODELS:
        if name not in existing_names:
            r = create_mental_model(bank_id=bid, name=name, source_query=source_query)
            if r:
                results.append(r)
    if results:
        print(f"[MEMORY] Created {len(results)} new mental models for {bid}")
    else:
        print(f"[MEMORY] All {len(existing)} mental models already exist for {bid}")
    return results


def refresh_mental_model(bank_id: str = None, reflection_id: str = None) -> dict:
    bid = bank_id or get_bank_id()
    if not bid or not reflection_id:
        return {}
    client = _get_http_client()
    try:
        response = client.post(f"/v1/default/banks/{bid}/mental-models/{reflection_id}/refresh")
        response.raise_for_status()
        result = response.json()
        operation_id = result.get("operation_id")

        # Poll for completion
        start_time = time.time()
        while time.time() - start_time < 60:
            time.sleep(0.5)
            try:
                status_response = client.get(f"/v1/default/banks/{bid}/operations/{operation_id}")
                status_response.raise_for_status()
                op = status_response.json()
                if op.get("status") in ("completed", "not_found"):
                    return {"success": True, "status": "completed"}
                if op.get("status") == "failed":
                    return {"success": False, "status": "failed", "error": op.get("error_message")}
            except Exception:
                pass
        return {"success": False, "status": "timeout"}
    except Exception as e:
        print(f"[MEMORY] Failed to refresh reflection: {e}")
        return {"success": False, "error": str(e)}


def refresh_mental_models(bank_id: str = None) -> dict:
    bid = bank_id or get_bank_id()
    if not bid:
        return {"success": False, "error": "No bank_id"}
    reflections = get_mental_models(bank_id=bid)
    if not reflections:
        return {"success": True, "refreshed": 0}
    success_count = 0
    for r in reflections:
        rid = r.get("id")
        if rid:
            result = refresh_mental_model(bank_id=bid, reflection_id=rid)
            if result.get("success"):
                success_count += 1
    return {"success": success_count == len(reflections), "refreshed": success_count, "total": len(reflections)}


async def refresh_mental_models_async(bank_id: str = None) -> dict:
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(_executor, lambda: refresh_mental_models(bank_id))


# ---------------------------------------------------------------------------
# Scenario tracking for refresh interval
# ---------------------------------------------------------------------------

def record_scenario() -> bool:
    global _scenarios_since_refresh
    _scenarios_since_refresh += 1
    if _refresh_interval > 0 and _scenarios_since_refresh >= _refresh_interval:
        return True
    return False


def reset_scenario_count():
    global _scenarios_since_refresh
    _scenarios_since_refresh = 0


def get_scenarios_since_refresh() -> int:
    return _scenarios_since_refresh


def set_refresh_interval(interval: int):
    global _refresh_interval
    _refresh_interval = max(0, interval)


def get_refresh_interval() -> int:
    return _refresh_interval
