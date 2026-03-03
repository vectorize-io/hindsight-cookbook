"""Memory service — Hindsight integration for ClaimsIQ.

Provides retain, recall, reflect, and mental model management.
"""

import uuid
import asyncio
import time
import concurrent.futures
import hindsight_litellm
from hindsight_litellm import (
    aretain,
    arecall,
    areflect,
)
from ..config import get_hindsight_url
import httpx

# Thread pool for running sync operations from async context
_executor = concurrent.futures.ThreadPoolExecutor(max_workers=4)

_http_client: httpx.Client | None = None
_http_client_url: str | None = None

# Bank state
_bank_id: str | None = None
_bank_history: list[str] = []
_configured: bool = False

# Claim tracking for mental model refresh
_claims_since_refresh: int = 0
_refresh_interval: int = 5  # Refresh every N claims
DEFAULT_REFRESH_INTERVAL = 5

# Bank configuration
BANK_MISSION = (
    "I am an insurance claims processing agent. I learn coverage rules, "
    "adjuster assignments, fraud patterns, and escalation thresholds to "
    "process claims accurately and efficiently."
)

BANK_DISPOSITION = {
    "skepticism": 3,
    "literalism": 4,
    "empathy": 2,
}

DEFAULT_MENTAL_MODELS = [
    (
        "Coverage Rules Matrix",
        "What are the coverage rules for each policy type? Which claim categories "
        "are covered or excluded by each policy (Platinum, Gold, Silver, Bronze, "
        "Home Shield, Auto Plus)?",
    ),
    (
        "Adjuster Assignment Guide",
        "Which adjusters handle which types of claims in which regions? When should "
        "claims be assigned to senior adjusters? Who is the fraud specialist?",
    ),
    (
        "Escalation & Threshold Rules",
        "What are the escalation rules based on claim amounts? When is manager "
        "review required? When should fraud specialists be involved? What is the "
        "difference between water damage and flood damage?",
    ),
    (
        "Prior Claims & Fraud Patterns",
        "What have I learned about checking prior claims history? Which claimants "
        "or policies have fraud flags? When should prior history affect the decision?",
    ),
]


def _get_http_client(hindsight_url: str = None) -> httpx.Client:
    global _http_client, _http_client_url
    url = hindsight_url or get_hindsight_url()
    if _http_client is None or _http_client_url != url:
        if _http_client is not None:
            _http_client.close()
        _http_client = httpx.Client(base_url=url, timeout=60.0)
        _http_client_url = url
    return _http_client


def generate_bank_id() -> str:
    return f"claims-{uuid.uuid4().hex[:8]}"


def configure_memory(bank_id: str = None) -> str:
    """Configure Hindsight for ClaimsIQ. Returns the bank_id."""
    global _bank_id, _configured

    new_bank_id = bank_id or generate_bank_id()
    _bank_id = new_bank_id

    # Create bank via HTTP
    _create_bank(new_bank_id, mission=BANK_MISSION)

    # Configure hindsight_litellm
    hindsight_litellm.configure(
        hindsight_api_url=get_hindsight_url(),
        bank_id=new_bank_id,
        store_conversations=False,
        inject_memories=False,
        recall_budget="high",
        use_reflect=True,
        verbose=True,
    )
    hindsight_litellm.enable()

    _configured = True
    if new_bank_id not in _bank_history:
        _bank_history.append(new_bank_id)

    print(f"[MEMORY] Configured bank: {new_bank_id}")

    # Create default mental models
    create_default_mental_models(bank_id=new_bank_id)
    return new_bank_id


def _create_bank(bank_id: str, mission: str = None):
    """Create a bank via HTTP API."""
    try:
        client = _get_http_client()
        body = {"name": bank_id}
        if mission:
            body["mission"] = mission
        response = client.put(f"/v1/default/banks/{bank_id}", json=body)
        response.raise_for_status()
        print(f"[MEMORY] Created bank: {bank_id}")
    except Exception as e:
        print(f"[MEMORY] Error creating bank {bank_id}: {e}")


def get_bank_id() -> str | None:
    return _bank_id


def set_bank_id(bank_id: str):
    """Switch to an existing bank."""
    global _bank_id
    _bank_id = bank_id
    hindsight_litellm.configure(
        hindsight_api_url=get_hindsight_url(),
        bank_id=bank_id,
        store_conversations=False,
        inject_memories=False,
        recall_budget="high",
        use_reflect=True,
        verbose=True,
    )
    if bank_id not in _bank_history:
        _bank_history.append(bank_id)


def get_bank_history() -> list[str]:
    return list(reversed(_bank_history))


def reset_bank() -> str:
    """Create a new bank and switch to it."""
    global _claims_since_refresh
    _claims_since_refresh = 0
    return configure_memory()


def ensure_bank_exists() -> bool:
    global _configured
    if _configured and _bank_id:
        return True
    try:
        configure_memory()
        return True
    except Exception as e:
        print(f"[MEMORY] Error configuring: {e}")
        return False


# ---------------------------------------------------------------------------
# Memory operations
# ---------------------------------------------------------------------------

async def completion(**kwargs):
    """LLM completion via hindsight_litellm (async-safe)."""
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(_executor, lambda: hindsight_litellm.completion(**kwargs))


async def retain_async(content: str, context: str = None, session_id: str = None, bank_id: str = None):
    bid = bank_id or get_bank_id()
    url = get_hindsight_url()
    t0 = time.time()
    try:
        result = await aretain(
            content,
            bank_id=bid,
            context=context,
            document_id=session_id,
            hindsight_api_url=url,
        )
        print(f"[MEMORY] Retain success in {time.time()-t0:.2f}s (bank={bid})")
        return result
    except Exception as e:
        print(f"[MEMORY] Retain failed in {time.time()-t0:.2f}s: {e}")
        raise


async def recall_async(query: str, budget: str = "high", bank_id: str = None):
    bid = bank_id or get_bank_id()
    url = get_hindsight_url()
    t0 = time.time()
    try:
        result = await arecall(query=query, bank_id=bid, budget=budget, hindsight_api_url=url)
        num = len(result) if result else 0
        print(f"[MEMORY] Recall returned {num} facts in {time.time()-t0:.2f}s")
        return result
    except Exception as e:
        print(f"[MEMORY] Recall failed in {time.time()-t0:.2f}s: {e}")
        raise


def format_recall_as_context(recall_response) -> str:
    if not recall_response:
        return ""
    return "\n".join(f"- {r.text}" for r in recall_response)


async def reflect_async(query: str, budget: str = "high", context: str = None, bank_id: str = None):
    bid = bank_id or get_bank_id()
    url = get_hindsight_url()
    t0 = time.time()
    try:
        result = await areflect(query=query, bank_id=bid, budget=budget, context=context, hindsight_api_url=url)
        rlen = len(result.text) if result and hasattr(result, "text") and result.text else 0
        print(f"[MEMORY] Reflect returned {rlen} chars in {time.time()-t0:.2f}s")
        return result
    except Exception as e:
        print(f"[MEMORY] Reflect failed in {time.time()-t0:.2f}s: {e}")
        raise


# ---------------------------------------------------------------------------
# Mental models / reflections
# ---------------------------------------------------------------------------

def get_reflections(bank_id: str = None) -> list:
    bid = bank_id or get_bank_id()
    if not bid:
        return []
    client = _get_http_client()
    try:
        response = client.get(f"/v1/default/banks/{bid}/mental-models")
        response.raise_for_status()
        return response.json().get("items", [])
    except Exception as e:
        print(f"[MEMORY] Failed to get reflections: {e}")
        return []


async def get_reflections_async(bank_id: str = None) -> list:
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(_executor, lambda: get_reflections(bank_id))


def create_reflection(bank_id: str = None, name: str = None, source_query: str = None) -> dict:
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
        print(f"[MEMORY] Created reflection '{name}' for {bid}")
        return result
    except Exception as e:
        print(f"[MEMORY] Failed to create reflection: {e}")
        return {}


def create_default_mental_models(bank_id: str = None) -> list[dict]:
    bid = bank_id or get_bank_id()
    if not bid:
        return []
    results = []
    for name, source_query in DEFAULT_MENTAL_MODELS:
        r = create_reflection(bank_id=bid, name=name, source_query=source_query)
        if r:
            results.append(r)
    print(f"[MEMORY] Created {len(results)} default mental models for {bid}")
    return results


def refresh_reflection(bank_id: str = None, reflection_id: str = None) -> dict:
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
    reflections = get_reflections(bank_id=bid)
    if not reflections:
        return {"success": True, "refreshed": 0}
    success_count = 0
    for r in reflections:
        rid = r.get("id")
        if rid:
            result = refresh_reflection(bank_id=bid, reflection_id=rid)
            if result.get("success"):
                success_count += 1
    return {"success": success_count == len(reflections), "refreshed": success_count, "total": len(reflections)}


async def refresh_mental_models_async(bank_id: str = None) -> dict:
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(_executor, lambda: refresh_mental_models(bank_id))


# ---------------------------------------------------------------------------
# Claim tracking for refresh interval
# ---------------------------------------------------------------------------

def record_claim() -> bool:
    """Record a processed claim. Returns True if refresh should be triggered."""
    global _claims_since_refresh
    _claims_since_refresh += 1
    if _refresh_interval > 0 and _claims_since_refresh >= _refresh_interval:
        return True
    return False


def reset_claim_count():
    global _claims_since_refresh
    _claims_since_refresh = 0


def get_claims_since_refresh() -> int:
    return _claims_since_refresh


def set_refresh_interval(interval: int):
    global _refresh_interval
    _refresh_interval = max(0, interval)


def get_refresh_interval() -> int:
    return _refresh_interval
