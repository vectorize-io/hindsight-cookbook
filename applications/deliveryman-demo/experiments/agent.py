"""Simple delivery agent for Hindsight experiments."""

import json
from dataclasses import dataclass, field
from typing import Optional, List, Dict, Any, Callable
from enum import Enum

from building import Side, BUILDING_LAYOUT, get_business_at, get_employees_at, get_employee_location


@dataclass
class Package:
    recipient_name: str
    id: int = 1


@dataclass
class AgentState:
    floor: int = 1
    side: Side = Side.FRONT
    steps_taken: int = 0
    current_package: Optional[Package] = None
    action_history: List[Dict[str, Any]] = field(default_factory=list)
    delivered: bool = False

    def location_str(self) -> str:
        if self.side == Side.MIDDLE:
            return f"Floor {self.floor}, MIDDLE hallway"
        business = get_business_at(self.floor, self.side)
        biz_name = business.name if business else "unknown"
        return f"Floor {self.floor}, {self.side.value} side at {biz_name}"


class AgentTools:
    """Tool implementations for the delivery agent."""

    def __init__(self, state: AgentState):
        self.state = state

    def go_up(self) -> str:
        """Move up one floor via elevator."""
        self.state.steps_taken += 1
        if self.state.floor >= 3:
            result = "Cannot go up. Already at the top floor."
        else:
            self.state.floor += 1
            self.state.side = Side.MIDDLE
            result = f"Took elevator up to Floor {self.state.floor}. Now in the middle hallway."
        self._record_action("go_up", {}, result)
        return result

    def go_down(self) -> str:
        """Move down one floor via elevator."""
        self.state.steps_taken += 1
        if self.state.floor <= 1:
            result = "Cannot go down. Already at the bottom floor."
        else:
            self.state.floor -= 1
            self.state.side = Side.MIDDLE
            result = f"Took elevator down to Floor {self.state.floor}. Now in the middle hallway."
        self._record_action("go_down", {}, result)
        return result

    def go_to_front(self) -> str:
        """Walk to the front side of current floor."""
        self.state.steps_taken += 1
        if self.state.side == Side.FRONT:
            result = "Already at the front side of this floor."
        else:
            self.state.side = Side.FRONT
            business = get_business_at(self.state.floor, Side.FRONT)
            result = f"Walked to the front side of Floor {self.state.floor}. Now at {business.name}."
        self._record_action("go_to_front", {}, result)
        return result

    def go_to_back(self) -> str:
        """Walk to the back side of current floor."""
        self.state.steps_taken += 1
        if self.state.side == Side.BACK:
            result = "Already at the back side of this floor."
        else:
            self.state.side = Side.BACK
            business = get_business_at(self.state.floor, Side.BACK)
            result = f"Walked to the back side of Floor {self.state.floor}. Now at {business.name}."
        self._record_action("go_to_back", {}, result)
        return result

    def check_current_location(self) -> str:
        """Check current location in the building."""
        self.state.steps_taken += 1
        result = f"Current location: {self.state.location_str()}"
        self._record_action("check_current_location", {}, result)
        return result

    def get_employee_list(self) -> str:
        """Get list of employees at current location."""
        self.state.steps_taken += 1
        if self.state.side == Side.MIDDLE:
            result = "You're in the middle hallway. Go to the front or back side to see employees."
        else:
            employees = get_employees_at(self.state.floor, self.state.side)
            business = get_business_at(self.state.floor, self.state.side)
            if employees:
                emp_list = "\n".join([f"  - {e.name} ({e.role})" for e in employees])
                result = f"Employees at {business.name}:\n{emp_list}"
            else:
                result = f"{business.name} has no employees listed."
        self._record_action("get_employee_list", {}, result)
        return result

    def deliver_package(self, recipient_name: str) -> str:
        """Attempt to deliver package to recipient."""
        self.state.steps_taken += 1
        pkg = self.state.current_package

        if not pkg:
            result = "No package to deliver."
        elif self.state.side == Side.MIDDLE:
            result = "FAILED: You're in the middle hallway. Go to the front or back side to deliver."
        elif pkg.recipient_name.lower() != recipient_name.lower():
            result = f"FAILED: Package is addressed to {pkg.recipient_name}, not {recipient_name}."
        else:
            # Check if recipient is at current location
            employees = get_employees_at(self.state.floor, self.state.side)
            business = get_business_at(self.state.floor, self.state.side)
            recipient_here = any(e.name.lower() == recipient_name.lower() for e in employees)

            if recipient_here:
                result = f"SUCCESS! Package delivered to {recipient_name} at {business.name}!"
                self.state.delivered = True
                self.state.current_package = None
            else:
                result = f"FAILED: {recipient_name} does not work at {business.name}. Try another location."

        self._record_action("deliver_package", {"recipient_name": recipient_name}, result)
        return result

    def _record_action(self, name: str, args: dict, result: str):
        self.state.action_history.append({
            "step": self.state.steps_taken,
            "action": name,
            "args": args,
            "result": result,
            "location": self.state.location_str(),
        })

    def execute(self, tool_name: str, args: dict) -> str:
        """Execute a tool by name."""
        tool_map = {
            "go_up": self.go_up,
            "go_down": self.go_down,
            "go_to_front": self.go_to_front,
            "go_to_back": self.go_to_back,
            "check_current_location": self.check_current_location,
            "get_employee_list": self.get_employee_list,
            "deliver_package": self.deliver_package,
        }

        if tool_name not in tool_map:
            return f"Unknown tool: {tool_name}"

        func = tool_map[tool_name]
        if tool_name == "deliver_package":
            return func(args.get("recipient_name", ""))
        return func()


# Tool definitions for LLM
TOOL_DEFINITIONS = [
    {
        "type": "function",
        "function": {
            "name": "go_up",
            "description": "Take the elevator up one floor. You will end up in the MIDDLE hallway.",
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "go_down",
            "description": "Take the elevator down one floor. You will end up in the MIDDLE hallway.",
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "go_to_front",
            "description": "Walk to the FRONT side of the current floor to reach the business there.",
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "go_to_back",
            "description": "Walk to the BACK side of the current floor to reach the business there.",
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "check_current_location",
            "description": "Check your current location in the building (floor and side).",
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_employee_list",
            "description": "Get the list of employees at your current location. Only works when at FRONT or BACK side, not in the MIDDLE hallway.",
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "deliver_package",
            "description": "Deliver the package to the specified recipient. Must be at the correct location (FRONT or BACK side where the recipient works).",
            "parameters": {
                "type": "object",
                "properties": {
                    "recipient_name": {
                        "type": "string",
                        "description": "The name of the person to deliver to",
                    },
                },
                "required": ["recipient_name"],
            },
        },
    },
]
