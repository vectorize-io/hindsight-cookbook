"""ClaimsIQ — FastAPI app with WebSocket endpoint for claims triage agent."""

import asyncio
import uuid
from contextlib import asynccontextmanager
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from claims_data import generate_claim, list_scenarios, claim_to_dict, get_claim
from .services import memory_service
from .services.agent_service import process_claim
from .config import BACKEND_PORT


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialize memory bank on startup."""
    try:
        memory_service.configure_memory()
        print("[STARTUP] Memory bank initialized")
    except Exception as e:
        print(f"[STARTUP] Memory init failed (will retry on first request): {e}")
    yield


app = FastAPI(title="ClaimsIQ", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---------------------------------------------------------------------------
# Session state per WebSocket client
# ---------------------------------------------------------------------------

class SessionState:
    def __init__(self):
        self.mode: str = "no_memory"
        self.claims_processed: int = 0
        self.cancelled: asyncio.Event = asyncio.Event()

_sessions: dict[str, SessionState] = {}

# ---------------------------------------------------------------------------
# WebSocket endpoint
# ---------------------------------------------------------------------------

@app.websocket("/ws/{client_id}")
async def websocket_endpoint(websocket: WebSocket, client_id: str):
    await websocket.accept()
    session = SessionState()
    _sessions[client_id] = session

    try:
        # Send connected event
        await websocket.send_json({
            "type": "CONNECTED",
            "payload": {
                "bankId": memory_service.get_bank_id(),
                "mode": session.mode,
            },
        })

        while True:
            data = await websocket.receive_json()
            event_type = data.get("type", "")

            if event_type == "process_claim":
                session.cancelled.clear()
                scenario_id = data.get("payload", {}).get("scenarioId")
                max_steps = data.get("payload", {}).get("maxSteps", 20)
                claim = generate_claim(scenario_id=scenario_id)
                session.claims_processed += 1

                await process_claim(
                    websocket=websocket,
                    claim=claim,
                    mode=session.mode,
                    max_steps=max_steps,
                    cancelled=session.cancelled,
                )

            elif event_type == "cancel":
                session.cancelled.set()

            elif event_type == "set_mode":
                session.mode = data.get("payload", {}).get("mode", "no_memory")
                await websocket.send_json({
                    "type": "CONNECTED",
                    "payload": {
                        "bankId": memory_service.get_bank_id(),
                        "mode": session.mode,
                    },
                })

            elif event_type == "reset_memory":
                new_bank = memory_service.reset_bank()
                session.mode = data.get("payload", {}).get("mode", session.mode)
                await websocket.send_json({
                    "type": "CONNECTED",
                    "payload": {
                        "bankId": new_bank,
                        "mode": session.mode,
                    },
                })

    except WebSocketDisconnect:
        print(f"[WS] Client {client_id} disconnected")
    except Exception as e:
        print(f"[WS] Error for {client_id}: {e}")
        import traceback
        traceback.print_exc()
    finally:
        _sessions.pop(client_id, None)


# ---------------------------------------------------------------------------
# REST endpoints
# ---------------------------------------------------------------------------

@app.get("/api/claims/random")
async def get_random_claim():
    claim = generate_claim()
    return claim_to_dict(claim)


@app.get("/api/claims/scenarios")
async def get_scenarios():
    return {"scenarios": list_scenarios()}


@app.post("/api/claims/generate")
async def generate_specific_claim(body: dict):
    scenario_id = body.get("scenarioId")
    claim = generate_claim(scenario_id=scenario_id)
    return claim_to_dict(claim)


@app.get("/api/memory/bank")
async def get_bank():
    return {
        "bankId": memory_service.get_bank_id(),
        "history": memory_service.get_bank_history(),
    }


@app.post("/api/memory/bank/new")
async def new_bank():
    bank_id = memory_service.reset_bank()
    return {"bankId": bank_id}


@app.get("/api/memory/mental-models")
async def get_mental_models():
    models = await memory_service.get_reflections_async()
    return {"models": models}


@app.post("/api/memory/mental-models/refresh")
async def refresh_models():
    result = await memory_service.refresh_mental_models_async()
    return result


@app.get("/api/stats")
async def get_stats():
    return {
        "claimsSinceRefresh": memory_service.get_claims_since_refresh(),
        "refreshInterval": memory_service.get_refresh_interval(),
        "bankId": memory_service.get_bank_id(),
    }
