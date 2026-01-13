"""Agent service - handles delivery execution with LLM and Hindsight memory."""

import json
import time
import asyncio
from typing import AsyncGenerator, Optional
from fastapi import WebSocket

import sys
sys.path.insert(0, str(__file__).rsplit("/app/", 1)[0])

from building import Building, Package, AgentState, Side, get_building
from agent_tools import AgentTools, get_tool_definitions, execute_tool
from .memory_service import (
    completion,
    retain_async,
    reflect_async,
    set_document_id,
    ensure_bank_exists,
    get_bank_id,
)
from ..websocket.events import (
    event, EventType, AgentActionPayload, DeliverySuccessPayload,
    DeliveryFailedPayload, StepLimitPayload
)
from ..config import LLM_MODEL


# Hindsight query template for memory lookup - includes recipient name
def get_hindsight_query(recipient_name: str) -> str:
    return f"Where does {recipient_name} work? What locations have I already checked? Only include building layout and optimal paths if known from past deliveries."


def format_messages_for_retain(messages: list, success: bool = True, steps: int = 0) -> str:
    """Format conversation messages for storage to Hindsight."""
    items = []
    for msg in messages:
        role = msg.get("role", "").upper()
        content = msg.get("content", "")
        tool_calls = msg.get("tool_calls", [])

        if role == "SYSTEM":
            continue

        if role == "TOOL":
            items.append(f"TOOL_RESULT: {content}")
            continue

        if tool_calls:
            tc_strs = []
            for tc in tool_calls:
                if hasattr(tc, 'function'):
                    tc_strs.append(f"{tc.function.name}({tc.function.arguments})")
                elif isinstance(tc, dict) and 'function' in tc:
                    func = tc['function']
                    tc_strs.append(f"{func.get('name', '')}({func.get('arguments', '')})")
            if tc_strs:
                items.append(f"ASSISTANT_TOOL_CALLS: {'; '.join(tc_strs)}")
            if content:
                items.append(f"ASSISTANT: {content}")
            continue

        if content:
            label = "USER" if role == "USER" else "ASSISTANT"
            items.append(f"{label}: {content}")

    # Add outcome message with step count
    if success:
        items.append(f"OUTCOME: DELIVERY SUCCESSFUL in {steps} steps - Package was delivered to the correct recipient.")
    else:
        items.append(f"OUTCOME: DELIVERY FAILED after {steps} steps - The delivery could not be completed.")

    return "\n\n".join(items)


async def run_delivery(
    websocket: WebSocket,
    building: Building,
    package: Package,
    delivery_id: int,
    max_steps: Optional[int] = None,
    cancelled: asyncio.Event = None,
    model: Optional[str] = None,
    hindsight: Optional[dict] = None,
):
    """Run a delivery, streaming events via WebSocket.

    Args:
        websocket: WebSocket connection to stream events to
        building: The building to navigate
        package: The package to deliver
        delivery_id: Unique ID for this delivery (for memory grouping)
        max_steps: Maximum steps allowed (None = no limit)
        cancelled: Event to signal cancellation
        model: LLM model to use (None = use default from config)
        hindsight: Hindsight settings (inject, store)
    """
    # Use provided model or fall back to default
    llm_model = model or LLM_MODEL

    # Configure hindsight based on settings
    # Note: We manually call reflect_async at the start, so we disable automatic injection
    use_memory = hindsight.get("inject", True) if hindsight else True
    store_conversations = hindsight.get("store", True) if hindsight else True

    # Disable automatic memory injection - we handle it manually via reflect at start
    import hindsight_litellm
    config = hindsight_litellm.get_config()
    if config:
        config.inject_memories = False

    # Ensure hindsight is configured
    ensure_bank_exists()

    # Set up agent state - starting position depends on difficulty
    if building.is_multi_building:
        # Medium mode: start at Building A, Floor 1
        agent_state = AgentState(floor=1, side=Side.BUILDING_A)
    else:
        # Easy/Hard mode: start at Floor 1, Front
        agent_state = AgentState(floor=1, side=Side.FRONT)
    agent_state.current_package = package

    # Set document ID for memory grouping
    set_document_id(f"delivery-{delivery_id}")

    # Call reflect ONCE at the start to get memory context
    memory_context = None
    reflect_query = get_hindsight_query(package.recipient_name)

    if use_memory:
        try:
            t_reflect = time.time()
            reflect_result = await reflect_async(query=reflect_query)
            reflect_timing = time.time() - t_reflect

            if reflect_result.text:
                memory_context = reflect_result.text

            # Send memory_reflect event to frontend
            await websocket.send_json(event(EventType.MEMORY_REFLECT, {
                "query": reflect_query,
                "text": reflect_result.text,
                "bankId": get_bank_id(),
                "timing": reflect_timing,
            }))
        except Exception as e:
            print(f"[AGENT] Reflect failed: {e}")
            # Send event with error
            await websocket.send_json(event(EventType.MEMORY_REFLECT, {
                "query": reflect_query,
                "text": None,
                "bankId": get_bank_id(),
                "error": str(e),
            }))

    # Build system prompt - include memory context if available
    system_prompt = "You are a delivery agent. Use the tools provided to get the package delivered."
    if memory_context:
        system_prompt += f"\n\n# Relevant Memory\n{memory_context}"

    # Initial messages
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": f"Please deliver this package: {package}"}
    ]

    tools = AgentTools(building, agent_state)
    success = False

    try:
        while max_steps is None or agent_state.steps_taken < max_steps:
            # Check for cancellation
            if cancelled and cancelled.is_set():
                await websocket.send_json(event(EventType.CANCELLED, {"message": "Delivery cancelled by user"}))
                return

            # Send thinking event
            await websocket.send_json(event(EventType.AGENT_THINKING))

            # Call LLM (memory already injected in system prompt)
            t0 = time.time()
            result = await completion(
                model=llm_model,
                messages=messages,
                tools=get_tool_definitions(building.difficulty),
                tool_choice="required",
                timeout=30,
            )
            response = result.response
            timing = time.time() - t0

            message = response.choices[0].message

            if message.tool_calls:
                tool_results = []

                for tool_call in message.tool_calls:
                    tool_name = tool_call.function.name
                    arguments = json.loads(tool_call.function.arguments) if tool_call.function.arguments else {}

                    result = execute_tool(tools, tool_name, arguments)

                    tool_results.append({
                        "tool_call_id": tool_call.id,
                        "role": "tool",
                        "content": result
                    })

                    # Send action event
                    await websocket.send_json(event(EventType.AGENT_ACTION, {
                        "step": agent_state.steps_taken,
                        "toolName": tool_name,
                        "toolArgs": arguments,
                        "toolResult": result,
                        "thinking": message.content if message.content else None,
                        "floor": agent_state.floor,
                        "side": agent_state.side.value,
                        "timing": timing,
                    }))

                    await asyncio.sleep(0.1)

                    if "SUCCESS!" in result:
                        success = True
                        break

                # Update messages
                serialized_tool_calls = [
                    {"id": tc.id, "type": "function", "function": {"name": tc.function.name, "arguments": tc.function.arguments}}
                    for tc in message.tool_calls
                ] if message.tool_calls else []
                messages.append({"role": "assistant", "content": message.content, "tool_calls": serialized_tool_calls})
                messages.extend(tool_results)

                if success:
                    # Store memory (if enabled)
                    if store_conversations:
                        await websocket.send_json(event(EventType.MEMORY_STORING))
                        final_convo = format_messages_for_retain(messages, success=True, steps=agent_state.steps_taken)
                        t_store = time.time()
                        await retain_async(final_convo)
                        store_timing = time.time() - t_store
                        await websocket.send_json(event(EventType.MEMORY_STORED, {"timing": store_timing}))

                    await websocket.send_json(event(EventType.DELIVERY_SUCCESS, {
                        "message": result,
                        "steps": agent_state.steps_taken
                    }))
                    return

            else:
                # No tool calls - nudge to use tools
                if message.content:
                    await websocket.send_json(event(EventType.AGENT_ACTION, {
                        "step": agent_state.steps_taken,
                        "toolName": "response",
                        "toolArgs": {},
                        "toolResult": message.content,
                        "floor": agent_state.floor,
                        "side": agent_state.side.value,
                        "timing": timing,
                    }))
                messages.append({"role": "assistant", "content": message.content})
                messages.append({"role": "user", "content": "Use the available tools to complete the delivery."})

        # Step limit reached - store failed delivery (if enabled)
        if store_conversations:
            await websocket.send_json(event(EventType.MEMORY_STORING))
            final_convo = format_messages_for_retain(messages, success=False, steps=agent_state.steps_taken)
            t_store = time.time()
            await retain_async(final_convo)
            store_timing = time.time() - t_store
            await websocket.send_json(event(EventType.MEMORY_STORED, {"timing": store_timing}))

        await websocket.send_json(event(EventType.STEP_LIMIT_REACHED, {
            "message": f"Exceeded {max_steps} step limit",
            "steps": agent_state.steps_taken
        }))

    except asyncio.CancelledError:
        await websocket.send_json(event(EventType.CANCELLED, {"message": "Delivery cancelled"}))
        raise

    except Exception as e:
        import traceback
        await websocket.send_json(event(EventType.ERROR, {
            "message": str(e),
            "traceback": traceback.format_exc()
        }))
