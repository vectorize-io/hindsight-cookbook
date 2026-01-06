"""
Delivery Agent Module

LLM-powered agent that navigates the building to deliver packages.
Uses hindsight_litellm for automatic memory injection and storage.

Note: The delivery loop is implemented directly in app.py (both UI and FF modes)
rather than in this class, to enable better UI integration. This module provides:
- DeliveryAgent: Agent state management and system prompt building
- ActionEvent: Data class for recording agent actions
"""

import os
from dataclasses import dataclass

from building import Building, AgentState, get_building


@dataclass
class ActionEvent:
    """An action taken by the agent."""
    action: str
    result: str
    floor: int
    side: str


class DeliveryAgent:
    """
    LLM-powered delivery agent that learns from experience using Hindsight.

    This class manages agent state and provides the system prompt.
    The actual delivery loop is implemented in app.py for UI integration.

    Uses hindsight_litellm for:
    - Automatic memory recall and injection into prompts
    - Conversation storage via explicit retain() calls
    """

    def __init__(
        self,
        building: Building = None,
        model: str = None,
    ):
        """
        Initialize the delivery agent.

        Args:
            building: The building to navigate (defaults to singleton)
            model: LLM model to use (defaults to LLM_MODEL env var or gpt-4o-mini)
        """
        self.building = building or get_building()
        self.model = model or os.environ.get("LLM_MODEL", "openai/gpt-4o-mini")

        # Agent state
        self.state = AgentState()
        self.actions: list[ActionEvent] = []

    def reset_state(self):
        """Reset the agent's state for a new delivery."""
        self.state = AgentState()
        self.actions = []

    def _build_system_prompt(self, package) -> str:
        """Build the system prompt for the agent.

        Args:
            package: The Package to deliver

        Returns:
            System prompt string for the LLM
        """
        return "You are a delivery agent. Use the tools provided to get it delivered."

    def _record_action(self, action: str, result: str):
        """Record an action for display.

        Args:
            action: Name of the action/tool called
            result: Result string from the action
        """
        self.actions.append(ActionEvent(
            action=action,
            result=result,
            floor=self.state.floor,
            side=self.state.side.value
        ))
