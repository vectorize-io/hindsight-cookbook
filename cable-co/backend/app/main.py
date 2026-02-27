"""CableConnect — FastAPI app with WebSocket endpoint for customer service copilot."""

import asyncio
from contextlib import asynccontextmanager
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from telecom_data import get_scenario, SCENARIOS, reset_runtime_state
from .services import memory_service
from .services.agent_service import process_scenario
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


app = FastAPI(title="CableConnect", lifespan=lifespan)

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
        self.mode: str = "memory_on"
        self.scenario_index: int = 0  # next scenario to process (1-based)
        self.scenarios_processed: int = 0
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
                "totalScenarios": len(SCENARIOS),
            },
        })

        while True:
            data = await websocket.receive_json()
            event_type = data.get("type", "")

            if event_type == "process_next":
                session.cancelled.clear()
                session.scenario_index += 1

                if session.scenario_index > len(SCENARIOS):
                    await websocket.send_json({
                        "type": "ERROR",
                        "payload": {"message": "All scenarios have been processed. Click Reset to start over."},
                    })
                    continue

                scenario = get_scenario(session.scenario_index)
                if not scenario:
                    await websocket.send_json({
                        "type": "ERROR",
                        "payload": {"message": f"Scenario {session.scenario_index} not found."},
                    })
                    continue

                session.scenarios_processed += 1

                await process_scenario(
                    websocket=websocket,
                    scenario=scenario,
                    mode=session.mode,
                    cancelled=session.cancelled,
                )

            elif event_type == "set_mode":
                session.mode = data.get("payload", {}).get("mode", "memory_off")
                await websocket.send_json({
                    "type": "CONNECTED",
                    "payload": {
                        "bankId": memory_service.get_bank_id(),
                        "mode": session.mode,
                        "totalScenarios": len(SCENARIOS),
                    },
                })

            elif event_type == "reset_memory":
                memory_service.clear_bank()
                session.scenario_index = 0
                session.scenarios_processed = 0
                reset_runtime_state()
                await websocket.send_json({
                    "type": "CONNECTED",
                    "payload": {
                        "bankId": memory_service.get_bank_id(),
                        "mode": session.mode,
                        "totalScenarios": len(SCENARIOS),
                    },
                })

            elif event_type == "cancel":
                session.cancelled.set()

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

@app.get("/api/scenarios")
async def get_scenarios_list():
    return {
        "scenarios": [
            {
                "index": s.scenario_index,
                "accountId": s.account_id,
                "category": s.category,
                "learningPairId": s.learning_pair_id,
                "isLearningTest": s.is_learning_test,
            }
            for s in SCENARIOS
        ]
    }


@app.get("/api/memory/bank")
async def get_bank():
    return {
        "bankId": memory_service.get_bank_id(),
    }


@app.post("/api/memory/bank/clear")
async def clear_bank():
    memory_service.clear_bank()
    return {"bankId": memory_service.get_bank_id(), "cleared": True}


@app.get("/api/memory/mental-models")
async def get_mental_models():
    models = await memory_service.get_mental_models_async()
    return {"models": models}


@app.post("/api/memory/mental-models/refresh")
async def refresh_models():
    result = await memory_service.refresh_mental_models_async()
    return result


@app.get("/api/stats")
async def get_stats():
    return {
        "scenariosSinceRefresh": memory_service.get_scenarios_since_refresh(),
        "refreshInterval": memory_service.get_refresh_interval(),
        "bankId": memory_service.get_bank_id(),
    }
