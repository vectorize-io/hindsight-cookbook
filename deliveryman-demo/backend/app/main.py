"""FastAPI application for delivery agent demo with Hindsight memory."""

import asyncio
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
    """Initialize memory service at startup."""
    # Configure memory in a thread pool to avoid event loop issues
    # (hindsight_client uses sync code that internally runs async)
    import concurrent.futures
    loop = asyncio.get_event_loop()
    with concurrent.futures.ThreadPoolExecutor() as pool:
        await loop.run_in_executor(pool, memory_service.configure_memory)

# Include routers
app.include_router(building_router.router)


# Session state
sessions: dict = {}


class SessionState:
    def __init__(self, session_id: str):
        self.session_id = session_id
        self.delivery_counter = 0
        self.cancelled = asyncio.Event()


def get_or_create_session(client_id: str) -> SessionState:
    """Get or create a session for a client."""
    if client_id not in sessions:
        sessions[client_id] = SessionState(client_id)
    return sessions[client_id]


# Pydantic models
class HindsightSettings(BaseModel):
    inject: bool = True
    store: bool = True


class StartDeliveryPayload(BaseModel):
    recipientName: str
    includeBusiness: bool = False
    maxSteps: Optional[int] = None
    model: Optional[str] = None
    hindsight: Optional[HindsightSettings] = None


# REST endpoints for difficulty
@app.get("/api/difficulty")
async def get_difficulty():
    """Get current difficulty level."""
    difficulty = memory_service.get_current_difficulty()
    return {
        "difficulty": difficulty,
        "bankId": memory_service.get_bank_id(difficulty),
    }


class SetDifficultyRequest(BaseModel):
    difficulty: str


@app.post("/api/difficulty")
async def set_difficulty_endpoint(request: SetDifficultyRequest):
    """Set the difficulty level."""
    # Update building
    set_difficulty(request.difficulty)
    # Update memory service and get/create bank for this difficulty
    bank_id = memory_service.set_current_difficulty(request.difficulty)
    memory_service.ensure_bank_exists()
    return {
        "success": True,
        "difficulty": request.difficulty,
        "bankId": bank_id,
    }


# REST endpoints for memory
@app.get("/api/memory/bank")
async def get_memory_bank():
    """Get current memory bank ID."""
    return {
        "bankId": memory_service.get_bank_id(),
        "difficulty": memory_service.get_current_difficulty(),
    }


@app.post("/api/memory/ensure")
async def ensure_memory_bank():
    """Ensure memory bank exists."""
    success = memory_service.ensure_bank_exists()
    return {
        "success": success,
        "bankId": memory_service.get_bank_id(),
        "difficulty": memory_service.get_current_difficulty(),
    }


class SetBankRequest(BaseModel):
    bankId: str


@app.post("/api/memory/bank")
async def set_memory_bank(request: SetBankRequest):
    """Set the memory bank ID for the current difficulty."""
    difficulty = memory_service.get_current_difficulty()
    memory_service.set_bank_id(request.bankId, difficulty=difficulty)
    memory_service.ensure_bank_exists()
    return {
        "success": True,
        "bankId": memory_service.get_bank_id(),
        "difficulty": difficulty,
    }


@app.post("/api/memory/bank/new")
async def generate_new_bank():
    """Generate a new memory bank for the current difficulty."""
    difficulty = memory_service.get_current_difficulty()
    new_bank_id = memory_service.configure_memory(difficulty=difficulty)
    memory_service.ensure_bank_exists()
    return {
        "success": True,
        "bankId": new_bank_id,
        "difficulty": difficulty,
    }


@app.get("/api/memory/bank/history")
async def get_bank_history():
    """Get the history of bank IDs used for the current difficulty."""
    difficulty = memory_service.get_current_difficulty()
    return {
        "history": memory_service.get_bank_history(difficulty),
        "difficulty": difficulty,
    }


# WebSocket endpoint
@app.websocket("/ws/{client_id}")
async def websocket_endpoint(websocket: WebSocket, client_id: str):
    """WebSocket endpoint for real-time delivery updates."""
    print(f"WebSocket connection attempt from: {client_id}")
    print(f"  Headers: {dict(websocket.headers)}")
    await manager.connect(websocket, client_id)
    print(f"WebSocket connection accepted for: {client_id}")
    session = get_or_create_session(client_id)

    # Send connected event
    await websocket.send_json(event(EventType.CONNECTED, {
        "clientId": client_id,
        "bankId": memory_service.get_bank_id(),
    }))

    try:
        while True:
            data = await websocket.receive_json()
            event_type = data.get("type")

            if event_type == "start_delivery":
                payload = data.get("payload", {})

                # Reset cancellation flag
                session.cancelled.clear()

                # Create package
                building = get_building()
                recipient_name = payload.get("recipientName")
                include_business = payload.get("includeBusiness", False)
                max_steps = payload.get("maxSteps")
                model = payload.get("model")
                hindsight = payload.get("hindsight")

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

                # Run delivery
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
                # Generate a new bank ID to start fresh
                difficulty = memory_service.get_current_difficulty()
                new_bank_id = memory_service.configure_memory(difficulty=difficulty)
                memory_service.ensure_bank_exists()
                # Notify client of new bank ID
                await websocket.send_json(event(EventType.CONNECTED, {
                    "clientId": client_id,
                    "bankId": new_bank_id,
                }))

    except WebSocketDisconnect:
        manager.disconnect(client_id)


# Demo configuration endpoint
@app.get("/api/demo-config")
async def get_demo_config():
    """Get demo configuration for display in UI."""
    difficulty = memory_service.get_current_difficulty()
    tool_defs = get_tool_definitions(difficulty)
    # Extract simplified tool info for display
    tools_display = [
        {"name": t["function"]["name"], "description": t["function"]["description"]}
        for t in tool_defs
    ]
    return {
        "systemPrompt": "You are a delivery agent. Use the tools provided to get the package delivered.\n\n# Relevant Memory\n{hindsight_reflect_result}",
        "llmModel": LLM_MODEL,
        "hindsight": {
            "apiUrl": HINDSIGHT_API_URL,
            "bankId": memory_service.get_bank_id(),
            "method": "reflect",
            "queryTemplate": "Where does {recipient_name} work? What locations have I already checked? Only include building layout and optimal paths if known from past deliveries.",
            "budget": "high",
            "background": memory_service.BANK_BACKGROUND,
        },
        "tools": tools_display,
        "difficulty": difficulty,
    }


# Health check
@app.get("/health")
async def health():
    return {"status": "ok"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
