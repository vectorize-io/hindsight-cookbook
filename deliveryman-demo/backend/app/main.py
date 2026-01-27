"""FastAPI application for delivery agent demo."""

import asyncio
import uuid
import random
import json
from datetime import datetime
from pathlib import Path
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel
from typing import Optional, List

import sys
sys.path.insert(0, str(__file__).rsplit("/app/", 1)[0])

from building import get_building, set_difficulty, get_current_difficulty, Package, compute_optimal_steps
from agent_tools import get_tool_definitions
from .routers import building as building_router
from .services import memory_service, agent_service
from .services.benchmark_service import run_benchmark
from .services.benchmark_types import AgentMode, BenchmarkConfig, generate_delivery_queue, DeliveryQueue
from .services.benchmark_charts import generate_dashboard_chart, generate_comparison_chart
from .websocket.manager import manager
from .websocket.events import event, EventType
from .config import LLM_MODEL, HINDSIGHT_API_URL, AVAILABLE_MODELS, BACKEND_PORT, HINDSIGHT_PORT, get_hindsight_url, set_hindsight_url

# Results directory
RESULTS_DIR = Path(__file__).parent.parent.parent / "results"


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
                bank_id = memory_service.configure_memory(app_type=app_type, difficulty=difficulty)
                print(f"Initialized bank for {app_type}:{difficulty} = {bank_id}")

    with concurrent.futures.ThreadPoolExecutor() as pool:
        await loop.run_in_executor(pool, init_all_banks)
    print(f"Memory service initialized for all app+difficulty combinations")

    # Refresh mental models in background (don't block startup - each refresh is slow due to agentic reflect)
    def refresh_all_models():
        difficulties = ["easy", "medium", "hard"]
        for app_type in ["demo", "bench"]:
            for difficulty in difficulties:
                bank_id = memory_service.get_bank_id(app_type, difficulty)
                if bank_id:
                    try:
                        memory_service.refresh_mental_models(bank_id=bank_id)
                        print(f"Mental models refreshed for {app_type}:{difficulty}")
                    except Exception as e:
                        print(f"Warning: Failed to refresh mental models for {app_type}:{difficulty}: {e}")

    import threading
    threading.Thread(target=refresh_all_models, daemon=True).start()
    print("Mental model refresh started in background")


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
    mission: Optional[str] = None  # Bank mission for mental models
    url: Optional[str] = None  # Override hindsight API URL for this request


class FastDeliveryRequest(BaseModel):
    recipientName: Optional[str] = None  # None = random
    businessName: Optional[str] = None  # Pre-determined business name from queue (None = determine by includeBusiness)
    isRepeat: bool = False  # Whether this is a repeat visit (from pre-generated queue)
    includeBusiness: str = "random"  # 'always', 'never', or 'random' (only used if businessName is None)
    maxSteps: Optional[int] = None  # Hard cap (None = use stepMultiplier calculation)
    model: Optional[str] = None  # None = use default
    hindsight: Optional[HindsightSettings] = None
    # Agent mode (determines tools and behavior)
    mode: str = "recall"  # no_memory, filesystem, recall, reflect, hindsight_mm, hindsight_mm_nowait
    # Benchmark settings (for eval framework parity)
    repeatRatio: float = 0.4
    pairedMode: bool = False
    memoryQueryMode: str = "inject_once"  # 'inject_once', 'per_step', 'both'
    waitForConsolidation: bool = True
    refreshInterval: int = 5
    preseedCoverage: float = 0.0  # 0.0-1.0, fraction of building knowledge to pre-seed
    mmQueryType: str = "recall"  # 'recall' or 'reflect' for MM modes
    # Step limit settings
    stepMultiplier: float = 5.0  # max_steps = optimal * multiplier
    minSteps: int = 15  # Floor for max_steps


class FastLoopRequest(BaseModel):
    count: int = 10
    includeBusiness: bool = False
    maxSteps: int = 150


# Request model for generating delivery queues
class QueueConfigRequest(BaseModel):
    """Configuration for a single queue to generate."""
    configId: str  # Unique identifier for this config
    numDeliveries: int = 10
    repeatRatio: float = 0.4
    pairedMode: bool = False
    includeBusiness: str = "random"  # 'always', 'never', 'random'
    seed: Optional[int] = None  # Random seed for reproducibility


class GenerateQueuesRequest(BaseModel):
    """Request to generate delivery queues for multiple configs."""
    configs: List[QueueConfigRequest]


@app.post("/api/benchmark/generate-queues")
async def generate_benchmark_queues(request: GenerateQueuesRequest):
    """Generate delivery queues for multiple benchmark configurations.

    This pre-generates the delivery sequences with proper repeat ratios,
    so that all configs can share the same queue structure for fair comparison.

    Returns a dict mapping configId -> queue data (recipients, businesses, isRepeat flags).
    """
    building = get_building()
    queues = {}

    for config in request.configs:
        queue = generate_delivery_queue(
            building=building,
            num_deliveries=config.numDeliveries,
            repeat_ratio=config.repeatRatio,
            paired_mode=config.pairedMode,
            include_business=config.includeBusiness,
            seed=config.seed,
        )

        queues[config.configId] = {
            "recipients": queue.recipients,
            "businesses": queue.businesses,
            "isRepeat": queue.is_repeat,
            "totalDeliveries": len(queue),
        }

    return {"queues": queues}


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
    # Reset delivery count since we just refreshed
    memory_service.reset_delivery_count(app, difficulty)
    return {"result": result, "bankId": bank_id}


class SetMissionRequest(BaseModel):
    mission: str


@app.put("/api/memory/mission")
async def set_bank_mission(request: SetMissionRequest, app: str = "demo", difficulty: str = "easy"):
    """Set the mission for a bank (used by mental models)."""
    bank_id = memory_service.get_bank_id(app, difficulty)
    result = memory_service.set_bank_mission(bank_id, request.mission)
    return {"result": result, "bankId": bank_id}


@app.get("/api/memory/mental-models/{model_id}")
async def get_mental_model(model_id: str, app: str = "demo", difficulty: str = "easy"):
    """Get a single mental model with full observations."""
    bank_id = memory_service.get_bank_id(app, difficulty)
    model = memory_service.get_mental_model(bank_id, model_id)
    return {"model": model, "bankId": bank_id}


class CreatePinnedModelRequest(BaseModel):
    name: str
    description: str = None


@app.post("/api/memory/mental-models/pinned")
async def create_pinned_model(request: CreatePinnedModelRequest, app: str = "demo", difficulty: str = "easy"):
    """Create a pinned mental model (user-defined topic to track)."""
    bank_id = memory_service.get_bank_id(app, difficulty)
    model = memory_service.create_pinned_model(bank_id, request.name, request.description)
    return {"model": model, "bankId": bank_id}


@app.delete("/api/memory/mental-models/{model_id}")
async def delete_mental_model(model_id: str, app: str = "demo", difficulty: str = "easy"):
    """Delete a mental model."""
    bank_id = memory_service.get_bank_id(app, difficulty)
    success = memory_service.delete_mental_model(bank_id, model_id)
    return {"success": success, "bankId": bank_id}


# Mental model refresh interval endpoints
@app.get("/api/memory/refresh-interval")
async def get_refresh_interval(app: str = "demo", difficulty: str = "easy"):
    """Get the mental model refresh interval (deliveries between refreshes)."""
    interval = memory_service.get_refresh_interval(app, difficulty)
    deliveries_since = memory_service.get_deliveries_since_refresh(app, difficulty)
    return {
        "interval": interval,
        "deliveriesSinceRefresh": deliveries_since,
        "app": app,
        "difficulty": difficulty,
    }


class SetRefreshIntervalRequest(BaseModel):
    interval: int


@app.post("/api/memory/refresh-interval")
async def set_refresh_interval(request: SetRefreshIntervalRequest, app: str = "demo", difficulty: str = "easy"):
    """Set the mental model refresh interval (deliveries between refreshes). 0 = disabled."""
    interval = memory_service.set_refresh_interval(request.interval, app, difficulty)
    return {
        "interval": interval,
        "app": app,
        "difficulty": difficulty,
    }


@app.post("/api/memory/refresh-interval/reset-counter")
async def reset_delivery_counter(app: str = "demo", difficulty: str = "easy"):
    """Reset the delivery counter for auto-refresh to 0."""
    memory_service.reset_delivery_count(app, difficulty)
    return {
        "deliveriesSinceRefresh": 0,
        "app": app,
        "difficulty": difficulty,
    }


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

@app.get("/api/config")
async def get_config():
    """Get global configuration including ports and URLs."""
    return {
        "backendPort": BACKEND_PORT,
        "hindsightPort": HINDSIGHT_PORT,
        "hindsightUrl": get_hindsight_url(),
        "hindsightDefaultUrl": HINDSIGHT_API_URL,
        "llmModel": LLM_MODEL,
        "availableModels": AVAILABLE_MODELS,
    }


class ConfigUpdateRequest(BaseModel):
    """Request to update configuration."""
    hindsightUrl: Optional[str] = None


@app.patch("/api/config")
async def update_config(request: ConfigUpdateRequest):
    """Update global configuration.

    Set hindsightUrl to null to reset to default.
    """
    if request.hindsightUrl is not None or request.hindsightUrl == "":
        # Empty string or null resets to default
        if request.hindsightUrl == "":
            set_hindsight_url(None)
        else:
            set_hindsight_url(request.hindsightUrl)

    return {
        "hindsightUrl": get_hindsight_url(),
        "hindsightDefaultUrl": HINDSIGHT_API_URL,
    }


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
        "availableModels": AVAILABLE_MODELS,
        "hindsight": {
            "apiUrl": get_hindsight_url(),
            "bankId": memory_service.get_bank_id(app, difficulty),
            "method": "reflect",
            "queryTemplate": QUERY_TEMPLATE,
            "budget": "high",
            "mission": memory_service.BANK_MISSION,
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

    # Use pre-determined business name if provided (from generated queue)
    # Otherwise, determine based on includeBusiness setting
    if request.businessName is not None:
        # Pre-determined from queue - use as-is (could be actual name or None)
        business_name = request.businessName
    else:
        # Fallback: determine based on includeBusiness setting
        if request.includeBusiness == "always":
            include_biz = True
        elif request.includeBusiness == "never":
            include_biz = False
        else:  # "random"
            include_biz = random.choice([True, False])
        business_name = emp_info[0].name if include_biz else None

    package = Package(
        id=f"{random.randint(1000, 9999)}",
        recipient_name=recipient_name,
        business_name=business_name
    )

    # Compute optimal steps for this delivery
    optimal_steps = compute_optimal_steps(building, recipient_name)

    # Calculate max_steps: max(min_steps, optimal * multiplier)
    # Apply hard cap if maxSteps is provided
    calculated_max = max(request.minSteps, int(optimal_steps * request.stepMultiplier))
    if request.maxSteps is not None:
        max_steps = min(calculated_max, request.maxSteps)  # Hard cap
    else:
        max_steps = calculated_max

    # Convert hindsight settings to dict if provided
    hindsight_dict = None
    if request.hindsight:
        # If a custom hindsight URL is provided, update the global config
        if request.hindsight.url:
            set_hindsight_url(request.hindsight.url)

        hindsight_dict = {
            "inject": request.hindsight.inject,
            "reflect": request.hindsight.reflect,
            "store": request.hindsight.store,
            "bankId": request.hindsight.bankId,
            "query": request.hindsight.query,
            "background": request.hindsight.background,
            "mission": request.hindsight.mission,
            "url": request.hindsight.url,
        }

    # Generate unique delivery ID for memory grouping
    delivery_id = random.randint(10000, 99999)

    # Run delivery with benchmark settings
    result = await agent_service.run_delivery_fast(
        building=building,
        package=package,
        max_steps=max_steps,
        model=request.model,
        hindsight=hindsight_dict,
        delivery_id=delivery_id,
        mode=request.mode,
        memory_query_mode=request.memoryQueryMode,
        wait_for_consolidation=request.waitForConsolidation,
        preseed_coverage=request.preseedCoverage,
        mm_query_type=request.mmQueryType,
    )

    result["recipientName"] = recipient_name
    result["businessName"] = business_name
    result["isRepeat"] = request.isRepeat
    result["optimalSteps"] = optimal_steps
    result["maxStepsAllowed"] = max_steps
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


# =============================================================================
# Benchmark Endpoints
# =============================================================================

class BenchmarkRequest(BaseModel):
    """Request model for starting a benchmark run."""
    mode: str = "recall"  # no_memory, filesystem, recall, reflect, hindsight_mm, hindsight_mm_nowait
    model: Optional[str] = None  # LLM model (None = use default)
    numDeliveries: int = 10
    repeatRatio: float = 0.4  # 40% repeat visits
    pairedMode: bool = False  # Each office visited exactly 2x
    includeBusiness: str = "random"  # always, never, random
    stepMultiplier: float = 5.0  # max_steps = optimal * multiplier
    minSteps: int = 15
    memoryQueryMode: str = "inject_once"  # inject_once, per_step, both
    waitForConsolidation: bool = True
    refreshInterval: int = 5  # 0 = disabled
    difficulty: str = "easy"
    seed: Optional[int] = None


@app.post("/api/benchmark/run")
async def run_benchmark_endpoint(request: BenchmarkRequest):
    """Run a benchmark with the specified configuration (non-streaming)."""
    try:
        mode = AgentMode(request.mode)
    except ValueError:
        return {"error": f"Invalid mode: {request.mode}. Valid modes: {[m.value for m in AgentMode]}"}

    config = BenchmarkConfig(
        mode=mode,
        model=request.model or LLM_MODEL,
        num_deliveries=request.numDeliveries,
        repeat_ratio=request.repeatRatio,
        paired_mode=request.pairedMode,
        include_business=request.includeBusiness,
        step_multiplier=request.stepMultiplier,
        min_steps=request.minSteps,
        memory_query_mode=request.memoryQueryMode,
        wait_for_consolidation=request.waitForConsolidation,
        refresh_interval=request.refreshInterval,
        difficulty=request.difficulty,
        seed=request.seed,
    )

    results = await run_benchmark(config=config)
    return results.to_dict()


@app.get("/api/benchmark/modes")
async def get_benchmark_modes():
    """Get available benchmark modes and their descriptions."""
    return {
        "modes": [
            {"id": "no_memory", "name": "No Memory", "description": "Stateless baseline - no memory injection or storage"},
            {"id": "filesystem", "name": "Filesystem", "description": "Agent manages own notes (read_notes/write_notes tools)"},
            {"id": "recall", "name": "Recall", "description": "Hindsight recall - raw fact retrieval"},
            {"id": "reflect", "name": "Reflect", "description": "Hindsight reflect - LLM-synthesized answers"},
            {"id": "hindsight_mm", "name": "Hindsight MM", "description": "Hindsight with mental models (wait for consolidation)"},
            {"id": "hindsight_mm_nowait", "name": "Hindsight MM (No Wait)", "description": "Mental models without waiting for consolidation"},
        ],
        "defaultMode": "recall",
    }


@app.get("/api/benchmark/presets")
async def get_benchmark_presets():
    """Get predefined benchmark configurations."""
    return {
        "presets": [
            {
                "id": "quick_test",
                "name": "Quick Test",
                "description": "5 deliveries, easy mode, recall",
                "config": {"mode": "recall", "numDeliveries": 5, "difficulty": "easy"},
            },
            {
                "id": "learning_test",
                "name": "Learning Test",
                "description": "20 deliveries, 50% repeat, mental models",
                "config": {"mode": "hindsight_mm", "numDeliveries": 20, "repeatRatio": 0.5, "difficulty": "easy"},
            },
            {
                "id": "paired_comparison",
                "name": "Paired Comparison",
                "description": "Each office visited exactly 2x for clear learning signal",
                "config": {"mode": "hindsight_mm", "numDeliveries": 12, "pairedMode": True, "difficulty": "easy"},
            },
            {
                "id": "full_benchmark",
                "name": "Full Benchmark",
                "description": "30 deliveries, medium difficulty",
                "config": {"mode": "hindsight_mm", "numDeliveries": 30, "difficulty": "medium"},
            },
            {
                "id": "no_memory_baseline",
                "name": "No Memory Baseline",
                "description": "10 deliveries without memory for comparison",
                "config": {"mode": "no_memory", "numDeliveries": 10, "difficulty": "easy"},
            },
        ],
    }


# Bank stats endpoint
@app.get("/api/memory/stats")
async def get_bank_stats(app: str = "demo", difficulty: str = "easy"):
    """Get statistics for a memory bank including consolidation status."""
    bank_id = memory_service.get_bank_id(app, difficulty)
    stats = memory_service.get_bank_stats(bank_id)
    return {"stats": stats, "bankId": bank_id}


# Clear mental models endpoint
@app.delete("/api/memory/mental-models")
async def clear_all_mental_models(app: str = "demo", difficulty: str = "easy"):
    """Clear all mental models for a bank."""
    bank_id = memory_service.get_bank_id(app, difficulty)
    result = await memory_service.clear_mental_models_async(bank_id)
    return {"result": result, "bankId": bank_id}


# =============================================================================
# Benchmark Save Endpoints
# =============================================================================

class BenchmarkResultData(BaseModel):
    """A single benchmark result for saving."""
    config: dict
    summary: dict
    learning: dict
    timeSeries: dict
    deliveries: List[dict]


class SaveBenchmarkRequest(BaseModel):
    """Request to save benchmark results."""
    results: List[BenchmarkResultData]
    generateCharts: bool = True
    saveDetailedLogs: bool = False  # Save per-delivery action logs in config subdirectories
    runName: Optional[str] = None  # Optional custom name for the run


@app.post("/api/benchmark/save")
async def save_benchmark_results(request: SaveBenchmarkRequest):
    """Save benchmark results to disk with optional chart generation.

    Saves to results/{run_name}/ directory:
    - results.json - All benchmark results (summary, without action logs)
    - {config_name}/delivery_{n}.json - Detailed logs for each delivery (if saveDetailedLogs=true)
    - {mode}_dashboard.svg - Dashboard for each config
    - comparison.svg - Comparison chart if multiple configs
    """
    # Generate run name
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    run_name = request.runName or f"benchmark_{timestamp}"

    # Sanitize run name for filesystem
    run_name = "".join(c if c.isalnum() or c in "-_" else "_" for c in run_name)

    # Create subdirectory for this benchmark run
    run_dir = RESULTS_DIR / run_name
    run_dir.mkdir(parents=True, exist_ok=True)

    saved_files = []

    # Convert results to dicts
    results_dicts = [r.model_dump() for r in request.results]

    # If saving detailed logs, extract actions and save to per-config subdirectories
    if request.saveDetailedLogs:
        for result in results_dicts:
            # Get config name, fallback to mode
            config_name = result["config"].get("name") or result["config"].get("mode", "unknown")
            # Sanitize config name for filesystem
            config_name = "".join(c if c.isalnum() or c in "-_" else "_" for c in config_name)

            # Create config subdirectory
            config_dir = run_dir / config_name
            config_dir.mkdir(parents=True, exist_ok=True)

            # Save each delivery's detailed log
            for i, delivery in enumerate(result.get("deliveries", []), start=1):
                if delivery.get("actions"):
                    delivery_log = {
                        "deliveryId": delivery.get("deliveryId", i),
                        "recipient": delivery.get("recipient"),
                        "business": delivery.get("business"),
                        "success": delivery.get("success"),
                        "stepsTaken": delivery.get("stepsTaken"),
                        "optimalSteps": delivery.get("optimalSteps"),
                        "pathEfficiency": delivery.get("pathEfficiency"),
                        "path": delivery.get("path"),
                        "tokens": delivery.get("tokens"),
                        "latencyMs": delivery.get("latencyMs"),
                        "actions": delivery.get("actions"),
                    }
                    log_path = config_dir / f"delivery_{i:03d}.json"
                    with open(log_path, "w") as f:
                        json.dump(delivery_log, f, indent=2)
                    saved_files.append(str(log_path))

            # Also save config summary in the config directory
            config_summary = {
                "config": result["config"],
                "summary": result["summary"],
                "learning": result["learning"],
            }
            summary_path = config_dir / "summary.json"
            with open(summary_path, "w") as f:
                json.dump(config_summary, f, indent=2)
            saved_files.append(str(summary_path))

    # Create summary results without action logs for main results.json
    summary_results = []
    for result in results_dicts:
        summary_result = {
            "config": result["config"],
            "summary": result["summary"],
            "learning": result["learning"],
            "timeSeries": result["timeSeries"],
            # Strip actions from deliveries for summary
            "deliveries": [
                {k: v for k, v in d.items() if k != "actions"}
                for d in result.get("deliveries", [])
            ],
        }
        summary_results.append(summary_result)

    # Save JSON results (summary without action logs)
    json_path = run_dir / "results.json"
    json_data = {
        "savedAt": datetime.now().isoformat(),
        "runName": run_name,
        "numConfigs": len(summary_results),
        "results": summary_results,
    }
    with open(json_path, "w") as f:
        json.dump(json_data, f, indent=2)
    saved_files.append(str(json_path))

    # Generate charts if requested
    if request.generateCharts and results_dicts:
        # Dashboard for each config
        for result in results_dicts:
            # Use config name for chart filename, fallback to mode
            config_name = result["config"].get("name") or result["config"].get("mode", "unknown")
            config_name = "".join(c if c.isalnum() or c in "-_" else "_" for c in config_name)
            svg_path = run_dir / f"{config_name}_dashboard.svg"
            try:
                generate_dashboard_chart(result, svg_path)
                saved_files.append(str(svg_path))
            except Exception as e:
                print(f"Warning: Failed to generate dashboard chart for {config_name}: {e}")

        # Comparison chart if multiple configs
        if len(results_dicts) > 1:
            comparison_path = run_dir / "comparison.svg"
            try:
                generate_comparison_chart(results_dicts, comparison_path)
                saved_files.append(str(comparison_path))
            except Exception as e:
                print(f"Warning: Failed to generate comparison chart: {e}")

    return {
        "success": True,
        "runName": run_name,
        "savedFiles": saved_files,
        "resultsDir": str(run_dir),
    }


@app.get("/api/benchmark/results")
async def list_benchmark_results():
    """List all saved benchmark results (each in its own subdirectory)."""
    if not RESULTS_DIR.exists():
        return {"results": []}

    results = []
    # Scan subdirectories for results.json files
    for run_dir in sorted(RESULTS_DIR.iterdir(), reverse=True):
        if not run_dir.is_dir():
            continue
        json_file = run_dir / "results.json"
        if not json_file.exists():
            continue
        try:
            with open(json_file) as f:
                data = json.load(f)
            # List files in the directory
            files = [f.name for f in run_dir.iterdir() if f.is_file()]
            results.append({
                "runName": run_dir.name,
                "savedAt": data.get("savedAt"),
                "numConfigs": data.get("numConfigs", len(data.get("results", []))),
                "files": files,
            })
        except Exception as e:
            results.append({
                "runName": run_dir.name,
                "error": str(e),
            })

    return {"results": results, "resultsDir": str(RESULTS_DIR)}


@app.get("/api/benchmark/results/{run_name}/{filename}")
async def get_benchmark_result(run_name: str, filename: str):
    """Get a specific file from a benchmark result directory."""
    filepath = RESULTS_DIR / run_name / filename

    if not filepath.exists():
        return {"error": f"File not found: {run_name}/{filename}"}

    if filepath.suffix == ".json":
        with open(filepath) as f:
            return json.load(f)
    elif filepath.suffix == ".svg":
        return FileResponse(filepath, media_type="image/svg+xml")
    else:
        return {"error": f"Unsupported file type: {filepath.suffix}"}


@app.delete("/api/benchmark/results/{run_name}")
async def delete_benchmark_result(run_name: str):
    """Delete a benchmark result directory and all its files."""
    run_dir = RESULTS_DIR / run_name

    if not run_dir.exists():
        return {"error": f"Directory not found: {run_name}"}

    # Delete all files in the directory
    deleted = []
    for f in run_dir.iterdir():
        f.unlink()
        deleted.append(str(f))

    # Remove the directory itself
    run_dir.rmdir()

    return {"success": True, "deleted": deleted, "directory": str(run_dir)}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
