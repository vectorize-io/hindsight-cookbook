"""
Agent Tools Module

Defines the tools available to the delivery agent for navigating
the building and gathering information.
"""

from typing import Callable
from building import Building, Side, AgentState, get_building


class AgentTools:
    """
    Tools available to the delivery agent.
    Each tool returns a string describing the result.
    """

    def __init__(self, building: Building, state: AgentState, on_action: Callable[[str, str], None] = None):
        """
        Initialize agent tools.

        Args:
            building: The building to navigate
            state: The agent's current state
            on_action: Callback function called with (action_name, result) for each action
        """
        self.building = building
        self.state = state
        self.on_action = on_action or (lambda a, r: None)

    def _record_action(self, action: str, result: str) -> str:
        """Record an action and return the result."""
        self.state.steps_taken += 1
        self.on_action(action, result)
        return result

    def go_up(self) -> str:
        """Move up one floor."""
        if self.state.floor >= self.building.max_floor:
            result = f"Cannot go up. Already at the top floor (Floor {self.state.floor})."
            return self._record_action("go_up", result)

        self.state.floor += 1
        result = f"Moved up to Floor {self.state.floor}."
        return self._record_action("go_up", result)

    def go_down(self) -> str:
        """Move down one floor."""
        if self.state.floor <= self.building.min_floor:
            result = f"Cannot go down. Already at the bottom floor (Floor {self.state.floor})."
            return self._record_action("go_down", result)

        self.state.floor -= 1
        result = f"Moved down to Floor {self.state.floor}."
        return self._record_action("go_down", result)

    def go_to_front(self) -> str:
        """Go to the front side of the current floor."""
        if self.state.side == Side.FRONT:
            result = "Already at the front side of this floor."
            return self._record_action("go_to_front", result)

        self.state.side = Side.FRONT
        result = f"Moved to the front side of Floor {self.state.floor}."
        return self._record_action("go_to_front", result)

    def go_to_back(self) -> str:
        """Go to the back side of the current floor."""
        if self.state.side == Side.BACK:
            result = "Already at the back side of this floor."
            return self._record_action("go_to_back", result)

        self.state.side = Side.BACK
        result = f"Moved to the back side of Floor {self.state.floor}."
        return self._record_action("go_to_back", result)

    def look_at_business(self) -> str:
        """Look at the business sign at the current location."""
        business = self.building.get_business(self.state.floor, self.state.side)
        if business:
            result = f"The business here is: {business.name}"
            return self._record_action("look_at_business", result)
        else:
            result = "No business at this location."
            return self._record_action("look_at_business", result)

    def get_employee_list(self) -> str:
        """Get the list of employees at the current business."""
        business = self.building.get_business(self.state.floor, self.state.side)
        if not business:
            result = "No business at this location."
            return self._record_action("get_employee_list", result)

        if not business.employees:
            result = f"{business.name} has no employees listed."
            return self._record_action("get_employee_list", result)

        employee_list = "\n".join([
            f"  - {emp.name} ({emp.role})"
            for emp in business.employees
        ])
        result = f"Employees at {business.name}:\n{employee_list}"
        return self._record_action("get_employee_list", result)

    def deliver_package(self, recipient_name: str) -> str:
        """
        Attempt to deliver the package to the recipient at the current location.

        Args:
            recipient_name: Name of the person to deliver to
        """
        if not self.state.current_package:
            result = "No package to deliver."
            return self._record_action("deliver_package", result)

        pkg = self.state.current_package

        # Verify the agent is delivering to the correct recipient (the one on the package)
        if recipient_name.lower() != pkg.recipient_name.lower():
            result = f"FAILED: Package is addressed to {pkg.recipient_name}, not {recipient_name}. Check the package details."
            return self._record_action("deliver_package", result)

        business = self.building.get_business(self.state.floor, self.state.side)
        if not business:
            result = "No business at this location to deliver to."
            return self._record_action("deliver_package", result)

        # Check if the correct recipient works here
        recipient_found = any(
            emp.name.lower() == recipient_name.lower()
            for emp in business.employees
        )

        if recipient_found:
            self.state.packages_delivered += 1
            self.state.current_package = None
            result = f"SUCCESS! Package #{pkg.id} delivered to {recipient_name} at {business.name}!"
            return self._record_action("deliver_package", result)
        else:
            result = f"FAILED: {recipient_name} does not work at {business.name}. Try another location."
            return self._record_action("deliver_package", result)

    def check_current_location(self) -> str:
        """Check the agent's current location in the building."""
        result = f"Current location: Floor {self.state.floor}, {self.state.side.value} side"
        return self._record_action("check_current_location", result)


# Tool definitions for LLM function calling
TOOL_DEFINITIONS = [
    {
        "type": "function",
        "function": {
            "name": "go_up",
            "description": "Move up one floor in the building.",
            "parameters": {
                "type": "object",
                "properties": {},
                "required": []
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "go_down",
            "description": "Move down one floor in the building.",
            "parameters": {
                "type": "object",
                "properties": {},
                "required": []
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "go_to_front",
            "description": "Go to the front side of the current floor.",
            "parameters": {
                "type": "object",
                "properties": {},
                "required": []
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "go_to_back",
            "description": "Go to the back side of the current floor.",
            "parameters": {
                "type": "object",
                "properties": {},
                "required": []
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "look_at_business",
            "description": "Look at the business sign at your current location.",
            "parameters": {
                "type": "object",
                "properties": {},
                "required": []
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_employee_list",
            "description": "Get the list of employees at your current location.",
            "parameters": {
                "type": "object",
                "properties": {},
                "required": []
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "deliver_package",
            "description": "Attempt to deliver the package to the specified recipient at your current location.",
            "parameters": {
                "type": "object",
                "properties": {
                    "recipient_name": {
                        "type": "string",
                        "description": "The name of the person to deliver the package to"
                    }
                },
                "required": ["recipient_name"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "check_current_location",
            "description": "Check your current location in the building.",
            "parameters": {
                "type": "object",
                "properties": {},
                "required": []
            }
        }
    }
]


def execute_tool(tools: AgentTools, tool_name: str, arguments: dict) -> str:
    """Execute a tool by name with the given arguments."""
    tool_map = {
        "go_up": tools.go_up,
        "go_down": tools.go_down,
        "go_to_front": tools.go_to_front,
        "go_to_back": tools.go_to_back,
        "look_at_business": tools.look_at_business,
        "get_employee_list": tools.get_employee_list,
        "deliver_package": lambda: tools.deliver_package(arguments.get("recipient_name", "")),
        "check_current_location": tools.check_current_location,
    }

    if tool_name in tool_map:
        return tool_map[tool_name]()
    else:
        return f"Unknown tool: {tool_name}"
