"""WebSocket event types."""

from typing import TypedDict, Optional, Any, Literal
from dataclasses import dataclass, asdict


# Server -> Client Events

@dataclass
class MemoryInjectionInfo:
    injected: bool
    count: int
    context: Optional[str] = None


@dataclass
class AgentActionPayload:
    step: int
    toolName: str
    toolResult: str
    floor: int
    side: str
    timing: float
    memoryInjection: Optional[dict] = None
    llmDetails: Optional[dict] = None


@dataclass
class DeliverySuccessPayload:
    message: str
    steps: int


@dataclass
class DeliveryFailedPayload:
    message: str
    reason: str


@dataclass
class StepLimitPayload:
    message: str
    steps: int


@dataclass
class ErrorPayload:
    message: str
    traceback: Optional[str] = None


def event(event_type: str, payload: Any = None) -> dict:
    """Create a WebSocket event."""
    result = {"type": event_type}
    if payload is not None:
        if hasattr(payload, "__dict__"):
            result["payload"] = asdict(payload) if hasattr(payload, "__dataclass_fields__") else payload.__dict__
        else:
            result["payload"] = payload
    return result


# Event type constants
class EventType:
    CONNECTED = "connected"
    DELIVERY_STARTED = "delivery_started"
    AGENT_THINKING = "agent_thinking"
    AGENT_ACTION = "agent_action"
    MEMORY_REFLECT = "memory_reflect"  # Initial memory recall at start
    MEMORY_STORING = "memory_storing"
    MEMORY_STORED = "memory_stored"
    DELIVERY_SUCCESS = "delivery_success"
    DELIVERY_FAILED = "delivery_failed"
    STEP_LIMIT_REACHED = "step_limit_reached"
    CANCELLED = "cancelled"
    ERROR = "error"
