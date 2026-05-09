---
description: "Vapi voice AI calls with persistent caller memory via Hindsight"
tags: { sdk: "hindsight-vapi", topic: "Voice" }
---

# Vapi Memory

Give your [Vapi](https://vapi.ai) voice assistants persistent memory across calls. Caller-relevant context is recalled at call start and injected into the assistant's system prompt; the full transcript is retained when the call ends. Same caller, next call → the assistant already knows them.

## What This Demonstrates

- **Recall on `assistant-request`** — Vapi's per-call hook returns `assistantOverrides` with relevant memories pre-injected
- **Retain on `end-of-call-report`** — full transcript stored to Hindsight async (never blocks the webhook)
- **Per-call injection** — Vapi has no per-turn hook, so memory is loaded once at call start (unlike Pipecat which injects per-turn)
- **Caller-keyed memory** — bank ID derived from the caller's phone number so memory follows the user

## Architecture

```
Call starts
     │
     ▼
Vapi POST /webhook  type=assistant-request
     │
     ▼
HindsightVapiWebhook.handle(event)
     │
     ├─ recall(query, bank=caller_number)
     │
     └─ return assistantOverrides {
           "model": { "messages": [{role: "system",
                                    content: "...prior memories..."}]}
        }

Call in progress (assistant + caller talking)

Call ends
     │
     ▼
Vapi POST /webhook  type=end-of-call-report  + transcript
     │
     ▼
HindsightVapiWebhook.handle(event)
     │
     └─ retain(transcript) — fire-and-forget
```

## Prerequisites

1. **Hindsight running**

   ```bash
   export OPENAI_API_KEY=your-key
   docker run --rm -it --pull always -p 8888:8888 -p 9999:9999 \
     -e HINDSIGHT_API_LLM_API_KEY=$OPENAI_API_KEY \
     -e HINDSIGHT_API_LLM_MODEL=o3-mini \
     -v $HOME/.hindsight-docker:/home/hindsight/.pg0 \
     ghcr.io/vectorize-io/hindsight:latest
   ```

2. **Python 3.10+**

3. **Install dependencies**

   ```bash
   cd applications/vapi-memory
   pip install -r requirements.txt
   ```

## Quick Start

### 1. Run the webhook server

```bash
python webhook_server.py
# → Listening on http://0.0.0.0:8000/webhook
```

### 2. Simulate a Vapi call (no Vapi account needed)

In a second shell:

```bash
# Turn 1 — assistant-request: caller arrives, no memory yet
python simulate_call.py --caller "+15551234567" assistant-request

# Turn 2 — end-of-call-report: deliver a transcript so Hindsight retains it
python simulate_call.py --caller "+15551234567" end-of-call-report \
  --transcript "User: My name is Alex and I prefer email over phone calls.\
                Assistant: Got it Alex, I'll remember that."

# Wait a few seconds for Hindsight to extract facts...

# Turn 3 — new call from same caller. Watch the assistantOverrides come back
# with prior memories injected into the system prompt.
python simulate_call.py --caller "+15551234567" assistant-request
```

`simulate_call.py` prints the full webhook response, so you can see the `assistantOverrides.model.messages[0].content` containing recalled memories on the second call.

### 3. Wire to a real Vapi assistant

In your Vapi assistant config, set the **Server URL** to a publicly reachable host (use [ngrok](https://ngrok.com) or [Cloudflare Tunnel](https://www.cloudflare.com/products/tunnel/) for local dev):

```bash
ngrok http 8000
# → https://abc123.ngrok.io → forward to localhost:8000
```

Set Vapi's webhook URL to `https://abc123.ngrok.io/webhook` and place a test call. The server will receive `assistant-request` and `end-of-call-report` events automatically.

## Core Files

| File | Description |
|------|-------------|
| `webhook_server.py` | FastAPI app exposing `/webhook` — wires `HindsightVapiWebhook` into the request handler |
| `simulate_call.py` | Helper that POSTs simulated `assistant-request` + `end-of-call-report` events to the local server |
| `requirements.txt` | `hindsight-vapi`, `fastapi`, `uvicorn`, `httpx` |

## How It Works

### 1. Construct the webhook handler

```python
from hindsight_vapi import HindsightVapiWebhook

memory = HindsightVapiWebhook(
    bank_id="vapi-demo",         # static or derived per-call (see below)
    hindsight_api_url="http://localhost:8888",
)
```

### 2. Mount it on a FastAPI route

```python
from fastapi import FastAPI, Request

app = FastAPI()

@app.post("/webhook")
async def vapi_webhook(request: Request):
    event = await request.json()
    response = await memory.handle(event)
    return response or {}
```

`memory.handle(event)` looks at `event["message"]["type"]`:

- `assistant-request` → recalls memories for the caller, returns
  `{"assistantOverrides": {"model": {"messages": [{"role": "system", "content": "...memories..."}]}}}`
- `end-of-call-report` → retains the transcript, returns `None` (FastAPI sends `{}`)
- anything else → returns `None`

### 3. Per-caller memory

To key memory to the caller (so each phone number has its own bank), build the webhook handler per-event:

```python
@app.post("/webhook")
async def vapi_webhook(request: Request):
    event = await request.json()
    msg = event.get("message", {})
    caller = msg.get("call", {}).get("customer", {}).get("number") or "anonymous"

    memory = HindsightVapiWebhook(
        bank_id=f"vapi:caller:{caller}",
        hindsight_api_url="http://localhost:8888",
    )
    response = await memory.handle(event)
    return response or {}
```

## Customization

### Hindsight Cloud

```python
import os
memory = HindsightVapiWebhook(
    bank_id="vapi-demo",
    hindsight_api_url="https://api.hindsight.vectorize.io",
    api_key=os.environ["HINDSIGHT_API_KEY"],
)
```

### Configure once, instantiate cheaply

```python
from hindsight_vapi import HindsightVapiWebhook, configure

configure(
    hindsight_api_url="http://localhost:8888",
    api_key=os.environ.get("HINDSIGHT_API_KEY"),
)

# Subsequent constructions don't need URL/key
memory = HindsightVapiWebhook(bank_id=f"vapi:caller:{caller}")
```

## Common Issues

**Recall returns nothing on first call**
- Memory only exists after at least one `end-of-call-report` event for that bank. Run a call (or `simulate_call.py end-of-call-report`) first.

**Webhook responds slowly**
- Recall is in the hot path; retention is fire-and-forget. If recall is slow, set a lower `recall_budget` in `configure()`.

**"No Hindsight API URL configured"**
- Pass `hindsight_api_url=` or call `configure()` first.

---

**Built with:**
- [Vapi](https://vapi.ai) — voice AI platform
- [hindsight-vapi](https://github.com/vectorize-io/hindsight/tree/main/hindsight-integrations/vapi) — Hindsight memory webhook for Vapi
- [Hindsight](https://github.com/vectorize-io/hindsight) — Long-term memory for AI agents
