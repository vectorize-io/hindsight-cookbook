"""
FastAPI webhook server with persistent memory for Vapi voice calls.

Receives Vapi server events at POST /webhook:

  - assistant-request     → recalls memories for the caller, returns
                            assistantOverrides with the prior context
                            injected into the assistant's system prompt
  - end-of-call-report    → retains the transcript to Hindsight (async)

The memory bank is keyed to the caller's phone number, so each user
gets their own context that persists across calls.

Usage:
    python webhook_server.py

    # In another shell, simulate calls:
    python simulate_call.py --caller "+15551234567" assistant-request
    python simulate_call.py --caller "+15551234567" end-of-call-report \
        --transcript "User: Hi, my name is Alex. Assistant: Hi Alex!"

Prerequisites:
    - Hindsight running on localhost:8888 (see README)
    - pip install -r requirements.txt
"""

from __future__ import annotations

import os
from typing import Any

from fastapi import FastAPI, Request
from hindsight_vapi import HindsightVapiWebhook, configure

HINDSIGHT_URL = os.environ.get("HINDSIGHT_URL", "http://localhost:8888")
HINDSIGHT_API_KEY = os.environ.get("HINDSIGHT_API_KEY")
PORT = int(os.environ.get("PORT", "8000"))

# Configure Hindsight once at module import. Per-call HindsightVapiWebhook
# instances inherit URL + key from this global config.
configure(hindsight_api_url=HINDSIGHT_URL, api_key=HINDSIGHT_API_KEY)

app = FastAPI(title="Hindsight + Vapi memory webhook")


def _bank_id_for(event: dict[str, Any]) -> str:
    """Derive a per-caller bank ID from a Vapi event.

    Vapi puts caller identity at message.call.customer.number for inbound
    calls. Fall back to 'anonymous' so the webhook never crashes on
    unexpected event shapes.
    """
    msg = event.get("message", {}) or {}
    customer = (msg.get("call") or {}).get("customer") or {}
    caller = customer.get("number") or "anonymous"
    return f"vapi:caller:{caller}"


@app.post("/webhook")
async def vapi_webhook(request: Request) -> dict[str, Any]:
    event = await request.json()
    bank_id = _bank_id_for(event)

    memory = HindsightVapiWebhook(bank_id=bank_id)
    response = await memory.handle(event)
    return response or {}


@app.get("/healthz")
async def healthz() -> dict[str, str]:
    return {"status": "ok", "hindsight_url": HINDSIGHT_URL}


if __name__ == "__main__":
    import uvicorn

    print(f"Webhook server starting on http://0.0.0.0:{PORT}/webhook")
    print(f"Hindsight URL: {HINDSIGHT_URL}")
    uvicorn.run(app, host="0.0.0.0", port=PORT)
