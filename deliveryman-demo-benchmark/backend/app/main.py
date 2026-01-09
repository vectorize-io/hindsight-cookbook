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

from building import get_building, Package
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

# Include routers
app.include_router(building_router.router)


# Session state (in-memory for simplicity)
sessions: dict = {}


class SessionState:
    def __init__(self, session_id: str):
        self.session_id = session_id
        self.bank_id = memory_service.configure_memory(session_id)
        self.delivery_counter = 0
        self.deliveries_completed = 0
        self.total_steps = 0
        self.delivery_history = []
        self.cancelled = asyncio.Event()


def get_or_create_session(client_id: str) -> SessionState:
    """Get or create a session for a client."""
    if client_id not in sessions:
        sessions[client_id] = SessionState(client_id)
    return sessions[client_id]


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


# REST endpoints for memory management
@app.get("/api/memory/bank")
async def get_memory_bank():
    """Get current memory bank ID."""
    return {"bankId": memory_service.get_bank_id()}


@app.post("/api/memory/reset")
async def reset_memory_bank():
    """Reset to a new memory bank."""
    new_bank_id = memory_service.reset_bank()
    return {"newBankId": new_bank_id}


# WebSocket endpoint
@app.websocket("/ws/{client_id}")
async def websocket_endpoint(websocket: WebSocket, client_id: str):
    """WebSocket endpoint for real-time delivery updates."""
    print(f"WebSocket connection attempt from client: {client_id}")
    print(f"WebSocket headers: {dict(websocket.headers)}")
    await manager.connect(websocket, client_id)
    print(f"WebSocket connected: {client_id}")
    session = get_or_create_session(client_id)

    # Send connected event with session info
    await websocket.send_json(event(EventType.CONNECTED, {
        "clientId": client_id,
        "bankId": session.bank_id,
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
                session.bank_id = memory_service.reset_bank(client_id)
                await websocket.send_json(event("memory_reset", {"bankId": session.bank_id}))

            elif event_type == "reset_stats":
                session.deliveries_completed = 0
                session.total_steps = 0
                session.delivery_history = []
                await websocket.send_json(event("stats_reset"))

    except WebSocketDisconnect:
        manager.disconnect(client_id)


# Demo configuration endpoint
SYSTEM_PROMPT = "You are a delivery agent. Use the tools provided to get it delivered."

@app.get("/api/demo-config")
async def get_demo_config():
    """Get demo configuration for display in UI."""
    return {
        "systemPrompt": SYSTEM_PROMPT,
        "llmModel": LLM_MODEL,
        "hindsight": {
            "apiUrl": HINDSIGHT_API_URL,
            "storeConversations": False,
            "injectMemories": True,
            "useReflect": False,
        },
        "tools": [
            {"name": "go_up", "description": "Move up one floor"},
            {"name": "go_down", "description": "Move down one floor"},
            {"name": "go_to_front", "description": "Move to front side of building"},
            {"name": "go_to_back", "description": "Move to back side of building"},
            {"name": "get_employee_list", "description": "Get list of all employees and their locations"},
            {"name": "check_current_location", "description": "Check current location in building"},
            {"name": "deliver_package", "description": "Attempt to deliver package at current location"},
        ]
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
        }

    # Run delivery
    result = await agent_service.run_delivery_fast(
        building=building,
        package=package,
        max_steps=request.maxSteps,
        model=request.model,
        hindsight=hindsight_dict,
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
