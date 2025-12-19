"""
Delivery Agent Module

LLM-powered agent that navigates the building to deliver packages.
Uses hindsight_litellm for automatic memory injection and storage.
"""

import os
import json
from typing import Generator, Optional
from dataclasses import dataclass, field

from building import Building, Package, AgentState, Side, get_building
from agent_tools import AgentTools, TOOL_DEFINITIONS, execute_tool
import memory


@dataclass
class DeliveryResult:
    """Result of a delivery attempt."""
    success: bool
    steps_taken: int
    actions: list[tuple[str, str]] = field(default_factory=list)
    error: Optional[str] = None


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

    Uses hindsight_litellm for:
    - Automatic memory recall and injection into prompts
    - Automatic conversation storage (full conversation stored per LLM call)
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
            model: LLM model to use
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

    def _build_system_prompt(self, package: Package) -> str:
        """Build the system prompt for the agent."""
        return "You are a delivery agent. Use the tools provided to complete the current delivery. Any memories provided are from past deliveries - use them to learn about the building layout and employee locations, but always focus on the current package being delivered."

    def _record_action(self, action: str, result: str):
        """Record an action for display."""
        self.actions.append(ActionEvent(
            action=action,
            result=result,
            floor=self.state.floor,
            side=self.state.side.value
        ))

    def deliver_package(
        self,
        package: Package,
        max_steps: int = 50,
        on_action: callable = None
    ) -> DeliveryResult:
        """
        Attempt to deliver a package.

        Uses hindsight_litellm.completion() which automatically:
        - Recalls relevant memories and injects them into the prompt
        - Stores the conversation after completion

        Args:
            package: The package to deliver
            max_steps: Maximum number of steps before giving up
            on_action: Callback function called after each action

        Returns:
            DeliveryResult with success status and metrics
        """
        self.reset_state()
        self.state.current_package = package

        # Build system prompt (memories will be auto-injected by hindsight_litellm)
        system_prompt = self._build_system_prompt(package)

        # Create tools instance
        tools = AgentTools(
            self.building,
            self.state,
            on_action=self._record_action
        )

        # Initial messages
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": f"Please deliver this package: {package}"}
        ]

        # Agent loop
        delivery_success = False
        error = None

        while self.state.steps_taken < max_steps:
            try:
                # Call LLM with automatic memory injection
                response = memory.completion(
                    model=self.model,
                    messages=messages,
                    tools=TOOL_DEFINITIONS,
                    tool_choice="auto"
                )

                message = response.choices[0].message

                # Check if agent wants to use tools
                if message.tool_calls:
                    # Process each tool call
                    tool_results = []
                    for tool_call in message.tool_calls:
                        tool_name = tool_call.function.name
                        arguments = json.loads(tool_call.function.arguments) if tool_call.function.arguments else {}

                        # Execute the tool
                        result = execute_tool(tools, tool_name, arguments)
                        tool_results.append({
                            "tool_call_id": tool_call.id,
                            "role": "tool",
                            "content": result
                        })

                        # Callback for UI updates
                        if on_action:
                            on_action(ActionEvent(
                                action=tool_name,
                                result=result,
                                floor=self.state.floor,
                                side=self.state.side.value
                            ))

                        # Check if delivery was successful
                        if "SUCCESS!" in result:
                            delivery_success = True
                            break

                    # Add tool results to messages
                    messages.append({"role": "assistant", "content": message.content, "tool_calls": message.tool_calls})
                    messages.extend(tool_results)

                    if delivery_success:
                        break

                else:
                    # No tool calls, agent might be done or confused
                    if message.content:
                        messages.append({"role": "assistant", "content": message.content})
                        # Prompt to continue
                        messages.append({"role": "user", "content": "Please continue with the delivery. Use the available tools to navigate and deliver the package."})

            except Exception as e:
                error = str(e)
                break

        return DeliveryResult(
            success=delivery_success,
            steps_taken=self.state.steps_taken,
            actions=[(a.action, a.result) for a in self.actions],
            error=error
        )
