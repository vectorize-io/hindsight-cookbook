"""FastAPI application for delivery agent demo."""

import asyncio
import uuid
import random
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional

import sys
sys.path.insert(0, str(__file__).rsplit("/app/", 1)[0])

from building import get_building, set_difficulty, get_current_difficulty, Package
from agent_tools import get_tool_definitions
from .routers import building as building_router
from .services import memory_service, agent_service
from .websocket.manager import manager
from .websocket.events import event, EventType
from .config import LLM_MODEL, HINDSIGHT_API_URL


app = FastAPI(title="Delivery Agent API", version="1.0.0")

# CORS for frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
async def startup_event():
    """Initialize memory service at startup - creates banks for all app+difficulty combinations."""
    # Configure memory in a thread pool to avoid event loop issues
    # (hindsight_client uses sync code that internally runs async)
    import concurrent.futures
    loop = asyncio.get_event_loop()

    def init_all_banks():
        # Initialize both demo and benchmark apps with separate banks for each difficulty
        difficulties = ["easy", "medium", "hard"]
        for app_type in ["demo", "bench"]:
            for difficulty in difficulties:
                memory_service.configure_memory(app_type=app_type, difficulty=difficulty)
                print(f"Initialized bank for {app_type}:{difficulty} = {memory_service.get_bank_id(app_type, difficulty)}")

    with concurrent.futures.ThreadPoolExecutor() as pool:
        await loop.run_in_executor(pool, init_all_banks)
    print(f"Memory service initialized for all app+difficulty combinations")


# Include routers
app.include_router(building_router.router)


# Session state (in-memory for simplicity)
sessions: dict = {}


class SessionState:
    def __init__(self, session_id: str, app_type: str = "demo", difficulty: str = "easy"):
        self.session_id = session_id
        self.app_type = app_type
        self.difficulty = difficulty
        # Use existing bank for this app+difficulty or ensure one exists
        existing_bank = memory_service.get_bank_id(app_type, difficulty)
        if existing_bank:
            self.bank_id = existing_bank
        else:
            # Fallback: create bank if none exists (shouldn't happen normally)
            self.bank_id = memory_service.configure_memory(app_type=app_type, difficulty=difficulty)
        self.delivery_counter = 0
        self.deliveries_completed = 0
        self.total_steps = 0
        self.delivery_history = []
        self.cancelled = asyncio.Event()

    def set_difficulty(self, difficulty: str):
        """Switch to a different difficulty level and its bank."""
        self.difficulty = difficulty
        self.bank_id = memory_service.set_difficulty(difficulty, self.app_type)
        return self.bank_id


def get_or_create_session(client_id: str, app_type: str = "demo") -> SessionState:
    """Get or create a session for a client."""
    # Include app_type in key to keep sessions separate per app
    session_key = f"{app_type}:{client_id}"
    if session_key not in sessions:
        sessions[session_key] = SessionState(client_id, app_type)
    return sessions[session_key]


# Pydantic models for requests
class StartDeliveryRequest(BaseModel):
    recipientName: str
    includeBusiness: bool = False
    maxSteps: Optional[int] = None


class CancelDeliveryRequest(BaseModel):
    deliveryId: Optional[str] = None


class HindsightSettings(BaseModel):
    inject: bool = True
    reflect: bool = False
    store: bool = True
    bankId: Optional[str] = None  # Custom bank ID for evaluation
    query: Optional[str] = None  # Custom memory query (use {recipient} as placeholder)
    background: Optional[str] = None  # Bank background context for memory extraction


class FastDeliveryRequest(BaseModel):
    recipientName: Optional[str] = None  # None = random
    includeBusiness: bool = False
    maxSteps: int = 150
    model: Optional[str] = None  # None = use default
    hindsight: Optional[HindsightSettings] = None


class FastLoopRequest(BaseModel):
    count: int = 10
    includeBusiness: bool = False
    maxSteps: int = 150


# REST endpoints for difficulty
@app.get("/api/difficulty")
async def get_difficulty(app: str = "demo", difficulty: str = None):
    """Get current difficulty level and bank ID."""
    current_diff = difficulty or get_current_difficulty()
    return {
        "difficulty": current_diff,
        "bankId": memory_service.get_bank_id(app, current_diff),
    }


class SetDifficultyRequest(BaseModel):
    difficulty: str


@app.post("/api/difficulty")
async def set_difficulty_endpoint(request: SetDifficultyRequest, app: str = "demo"):
    """Set the difficulty level and switch to its memory bank."""
    # Update building difficulty
    set_difficulty(request.difficulty)
    # Switch memory service to this difficulty's bank
    bank_id = memory_service.set_difficulty(request.difficulty, app)
    return {
        "success": True,
        "difficulty": request.difficulty,
        "bankId": bank_id,
    }


# REST endpoints for memory management
@app.get("/api/memory/bank")
async def get_memory_bank(app: str = "demo", difficulty: str = "easy"):
    """Get current memory bank ID for app+difficulty."""
    return {"bankId": memory_service.get_bank_id(app, difficulty)}


@app.post("/api/memory/ensure")
async def ensure_memory_bank(app: str = "demo", difficulty: str = "easy"):
    """Ensure memory bank exists with proper background."""
    success = memory_service.ensure_bank_exists(app, difficulty)
    return {
        "success": success,
        "bankId": memory_service.get_bank_id(app, difficulty),
    }


@app.post("/api/memory/reset")
async def reset_memory_bank(app: str = "demo", difficulty: str = "easy"):
    """Reset to a new memory bank for app+difficulty."""
    new_bank_id = memory_service.reset_bank(app_type=app, difficulty=difficulty)
    return {"newBankId": new_bank_id}


@app.post("/api/memory/bank/new")
async def generate_new_bank(app: str = "demo", difficulty: str = "easy"):
    """Generate a new memory bank for app+difficulty."""
    new_bank_id = memory_service.configure_memory(app_type=app, difficulty=difficulty, use_default=False)
    memory_service.ensure_bank_exists(app, difficulty)
    return {"bankId": new_bank_id}


@app.get("/api/memory/bank/history")
async def get_bank_history(app: str = "demo", difficulty: str = "easy"):
    """Get history of bank IDs used for app+difficulty."""
    return {
        "history": memory_service.get_bank_history(app, difficulty),
        "currentBankId": memory_service.get_bank_id(app, difficulty),
    }


class SetBankRequest(BaseModel):
    bankId: str


@app.post("/api/memory/bank")
async def set_memory_bank(request: SetBankRequest, app: str = "demo", difficulty: str = "easy"):
    """Set the active memory bank ID for app+difficulty."""
    memory_service.set_bank_id(request.bankId, app_type=app, difficulty=difficulty)
    return {"bankId": memory_service.get_bank_id(app, difficulty)}


# Mental models endpoints
@app.get("/api/memory/mental-models")
async def get_mental_models(app: str = "demo", difficulty: str = "easy", subtype: str = None):
    """Get mental models for a bank."""
    bank_id = memory_service.get_bank_id(app, difficulty)
    models = memory_service.get_mental_models(bank_id, subtype=subtype)
    return {"models": models, "bankId": bank_id}


@app.post("/api/memory/mental-models/refresh")
async def refresh_mental_models(app: str = "demo", difficulty: str = "easy", subtype: str = None):
    """Trigger mental models refresh for a bank."""
    bank_id = memory_service.get_bank_id(app, difficulty)
    result = memory_service.refresh_mental_models(bank_id, subtype=subtype)
    return {"result": result, "bankId": bank_id}


class SetMissionRequest(BaseModel):
    mission: str


@app.put("/api/memory/mission")
async def set_bank_mission(request: SetMissionRequest, app: str = "demo", difficulty: str = "easy"):
    """Set the mission for a bank (used by mental models)."""
    bank_id = memory_service.get_bank_id(app, difficulty)
    result = memory_service.set_bank_mission(bank_id, request.mission)
    return {"result": result, "bankId": bank_id}


# WebSocket endpoint
@app.websocket("/ws/{client_id}")
async def websocket_endpoint(websocket: WebSocket, client_id: str, app: str = "demo", difficulty: str = "easy"):
    """WebSocket endpoint for real-time delivery updates."""
    print(f"WebSocket connection attempt from client: {client_id} (app: {app}, difficulty: {difficulty})")
    print(f"WebSocket headers: {dict(websocket.headers)}")
    await manager.connect(websocket, client_id)
    print(f"WebSocket connected: {client_id} (app: {app}, difficulty: {difficulty})")
    session = get_or_create_session(client_id, app)
    session.difficulty = difficulty
    session.bank_id = memory_service.get_bank_id(app, difficulty) or memory_service.configure_memory(app_type=app, difficulty=difficulty)

    # Ensure correct app type and difficulty is active for memory operations
    memory_service.set_active_app(app, difficulty)

    # Send connected event with session info
    await websocket.send_json(event(EventType.CONNECTED, {
        "clientId": client_id,
        "bankId": session.bank_id,
        "difficulty": session.difficulty,
    }))

    try:
        while True:
            data = await websocket.receive_json()
            event_type = data.get("type")
            print(f"WebSocket received event: {event_type}", flush=True)

            if event_type == "start_delivery":
                payload = data.get("payload", {})

                # Reset cancellation flag
                session.cancelled.clear()

                # Create package
                building = get_building()
                recipient_name = payload.get("recipientName")
                include_business = payload.get("includeBusiness", False)
                max_steps = payload.get("maxSteps")
                model = payload.get("model")  # Custom model override
                hindsight = payload.get("hindsight")  # Hindsight settings

                # Find employee's business
                emp_info = building.find_employee(recipient_name)
                business_name = emp_info[0].name if emp_info and include_business else None

                package = Package(
                    id=f"{random.randint(1000, 9999)}",
                    recipient_name=recipient_name,
                    business_name=business_name
                )

                session.delivery_counter += 1

                # Send delivery started event
                await websocket.send_json(event(EventType.DELIVERY_STARTED, {
                    "deliveryId": session.delivery_counter,
                    "package": {
                        "id": package.id,
                        "recipientName": package.recipient_name,
                        "businessName": package.business_name,
                    }
                }))

                # Run delivery in background task
                async def run_and_track():
                    try:
                        await agent_service.run_delivery(
                            websocket=websocket,
                            building=building,
                            package=package,
                            delivery_id=session.delivery_counter,
                            max_steps=max_steps,
                            cancelled=session.cancelled,
                            model=model,
                            hindsight=hindsight,
                        )
                    except asyncio.CancelledError:
                        pass

                task = asyncio.create_task(run_and_track())
                manager.set_delivery_task(client_id, task)

            elif event_type == "cancel_delivery":
                session.cancelled.set()
                manager.cancel_delivery(client_id)

            elif event_type == "reset_memory":
                # Generate a new random bank ID to start fresh for current difficulty
                new_bank_id = memory_service.reset_bank(app_type=session.app_type, difficulty=session.difficulty)
                session.bank_id = new_bank_id
                print(f"Memory reset - new bank: {new_bank_id} (app: {session.app_type}, difficulty: {session.difficulty})", flush=True)
                # Notify client of new bank ID
                await websocket.send_json(event(EventType.CONNECTED, {
                    "clientId": client_id,
                    "bankId": new_bank_id,
                    "difficulty": session.difficulty,
                }))

            elif event_type == "set_difficulty":
                # Switch to a different difficulty's bank
                payload = data.get("payload", {})
                new_difficulty = payload.get("difficulty", session.difficulty)
                new_bank_id = session.set_difficulty(new_difficulty)
                # Also update building difficulty
                set_difficulty(new_difficulty)
                print(f"Difficulty changed to {new_difficulty} - bank: {new_bank_id}", flush=True)
                # Notify client of the change
                await websocket.send_json(event(EventType.CONNECTED, {
                    "clientId": client_id,
                    "bankId": new_bank_id,
                    "difficulty": new_difficulty,
                }))

            elif event_type == "reset_stats":
                session.deliveries_completed = 0
                session.total_steps = 0
                session.delivery_history = []
                await websocket.send_json(event("stats_reset"))

    except WebSocketDisconnect:
        manager.disconnect(client_id)


# Demo configuration endpoint
SYSTEM_PROMPT = "You are a delivery agent. Use the tools provided to get it delivered."

QUERY_TEMPLATE = "Where does {recipient} work? What locations have I already checked? Only include building layout and optimal paths if known from past deliveries."

@app.get("/api/demo-config")
async def get_demo_config(app: str = "demo", difficulty: str = "easy"):
    """Get demo configuration for display in UI."""
    current_difficulty = get_current_difficulty()
    tool_defs = get_tool_definitions(current_difficulty)
    # Extract simplified tool info for display
    tools_display = [
        {"name": t["function"]["name"], "description": t["function"]["description"]}
        for t in tool_defs
    ]
    return {
        "systemPrompt": SYSTEM_PROMPT,
        "llmModel": LLM_MODEL,
        "hindsight": {
            "apiUrl": HINDSIGHT_API_URL,
            "bankId": memory_service.get_bank_id(app, difficulty),
            "method": "reflect",
            "queryTemplate": QUERY_TEMPLATE,
            "budget": "high",
            "background": memory_service.BANK_BACKGROUND,
        },
        "tools": tools_display,
        "difficulty": current_difficulty,
    }


# Fast-forward delivery endpoints (no WebSocket, returns results directly)
@app.post("/api/delivery/fast")
async def fast_delivery(request: FastDeliveryRequest):
    """Run a single delivery in fast-forward mode (no streaming)."""
    building = get_building()

    # Get recipient (random if not specified)
    if request.recipientName:
        recipient_name = request.recipientName
    else:
        # building.floors is dict[int, dict[Side, Business]]
        all_employees = list(building.all_employees.keys())
        recipient_name = random.choice(all_employees)

    # Find employee's business
    emp_info = building.find_employee(recipient_name)
    if not emp_info:
        return {"error": f"Employee {recipient_name} not found"}

    business_name = emp_info[0].name if request.includeBusiness else None

    package = Package(
        id=f"{random.randint(1000, 9999)}",
        recipient_name=recipient_name,
        business_name=business_name
    )

    # Convert hindsight settings to dict if provided
    hindsight_dict = None
    if request.hindsight:
        hindsight_dict = {
            "inject": request.hindsight.inject,
            "reflect": request.hindsight.reflect,
            "store": request.hindsight.store,
            "bankId": request.hindsight.bankId,
            "query": request.hindsight.query,
            "background": request.hindsight.background,
        }

    # Generate unique delivery ID for memory grouping
    delivery_id = random.randint(10000, 99999)

    # Run delivery
    result = await agent_service.run_delivery_fast(
        building=building,
        package=package,
        max_steps=request.maxSteps,
        model=request.model,
        hindsight=hindsight_dict,
        delivery_id=delivery_id,
    )

    result["recipientName"] = recipient_name
    return result


@app.post("/api/delivery/fast-loop")
async def fast_delivery_loop(request: FastLoopRequest):
    """Run multiple deliveries in fast-forward mode."""
    building = get_building()
    results = []

    # Get all employees for random selection
    all_employees = list(building.all_employees.keys())

    for i in range(request.count):
        recipient_name = random.choice(all_employees)

        # Find employee's business
        emp_info = building.find_employee(recipient_name)
        business_name = emp_info[0].name if emp_info and request.includeBusiness else None

        package = Package(
            id=f"{random.randint(1000, 9999)}",
            recipient_name=recipient_name,
            business_name=business_name
        )

        # Run delivery
        result = await agent_service.run_delivery_fast(
            building=building,
            package=package,
            max_steps=request.maxSteps,
        )

        result["deliveryNumber"] = i + 1
        result["recipientName"] = recipient_name
        results.append(result)

    # Compute summary
    successes = sum(1 for r in results if r.get("success"))
    total_steps = sum(r.get("steps", 0) for r in results)

    return {
        "results": results,
        "summary": {
            "total": len(results),
            "successes": successes,
            "failures": len(results) - successes,
            "successRate": successes / len(results) if results else 0,
            "totalSteps": total_steps,
            "avgSteps": total_steps / len(results) if results else 0,
        }
    }


# Health check
@app.get("/health")
async def health():
    return {"status": "ok"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
