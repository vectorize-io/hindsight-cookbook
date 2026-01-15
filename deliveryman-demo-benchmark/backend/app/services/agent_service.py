"""Agent service - handles delivery execution with LLM."""

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
    retain,
    retain_async,
    recall_async,
    reflect_async,
    format_recall_as_context,
    get_last_injection_debug,
    set_document_id,
    set_bank_id,
    set_bank_background_async,
)
from ..websocket.events import (
    event, EventType, AgentActionPayload, DeliverySuccessPayload,
    DeliveryFailedPayload, StepLimitPayload
)
from ..config import LLM_MODEL


def get_hindsight_query(recipient_name: str, custom_query: str = None) -> str:
    """Generate a memory query for the delivery.

    Args:
        recipient_name: Name of the package recipient
        custom_query: Optional custom query from demo settings

    Returns:
        A query string to use with reflect/recall
    """
    if custom_query:
        # Replace {recipient} placeholder if present
        return custom_query.replace("{recipient}", recipient_name)

    # Default query focusing on recipient location
    return f"Where does {recipient_name} work? What locations have I already checked? Only include building layout and optimal paths if known from past deliveries."


def format_messages_for_retain(messages: list, success: bool = True, steps: int = 0, recipient: str = None) -> str:
    """Format conversation messages for storage to Hindsight.

    Args:
        messages: List of message dicts from the conversation
        success: Whether the delivery succeeded
        steps: Number of steps taken
        recipient: Name of the recipient (optional, for context)
    """
    items = []

    # Add delivery context at the start
    if recipient:
        items.append(f"DELIVERY TO: {recipient}")

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

    # Add outcome message with steps
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
        hindsight: Hindsight settings (inject, reflect, store, query)
    """
    # Use provided model or fall back to default
    llm_model = model or LLM_MODEL

    # Configure hindsight based on settings
    inject_memories = hindsight.get("inject", True) if hindsight else True
    use_reflect = hindsight.get("reflect", False) if hindsight else False  # False = recall, True = reflect
    store_conversations = hindsight.get("store", True) if hindsight else True
    custom_bank_id = hindsight.get("bankId") if hindsight else None
    custom_query = hindsight.get("query") if hindsight else None
    custom_background = hindsight.get("background") if hindsight else None

    # Update hindsight defaults if custom bank_id provided
    if custom_bank_id:
        set_bank_id(custom_bank_id, set_background=False)

    # Set custom bank background if provided (guides memory extraction)
    # Uses async-safe version to avoid event loop conflicts
    if custom_background:
        set_bank_background_async(custom_background)

    # Set up agent state - starting position depends on difficulty
    if building.is_city_grid:
        # Hard mode: start on road at (0, 0) - top-left corner, in front of Tech Corp
        agent_state = AgentState(floor=1, side=Side.STREET, grid_row=0, grid_col=0, current_building=None)
    elif building.is_multi_building:
        # Medium mode: start at Building A, Floor 1
        agent_state = AgentState(floor=1, side=Side.BUILDING_A)
    else:
        # Easy mode: start at Floor 1, Front
        agent_state = AgentState(floor=1, side=Side.FRONT)
    agent_state.current_package = package

    # Set document ID for memory grouping
    set_document_id(f"delivery-{delivery_id}")

    # Build system prompt - may be augmented with memory
    base_system_prompt = "You are a delivery agent. Use the tools provided to get it delivered."
    system_prompt = base_system_prompt
    memory_context = None
    memory_method = "reflect" if use_reflect else "recall"
    raw_memories = []  # For recall mode - list of individual facts

    # MEMORY INJECTION: Call recall or reflect ONCE at start to get relevant memories
    if inject_memories:
        try:
            await websocket.send_json(event(EventType.AGENT_THINKING))  # Show we're recalling
            print(f"[MEMORY] Using {memory_method} for recipient: {package.recipient_name}")

            # Generate the memory query
            memory_query = get_hindsight_query(package.recipient_name, custom_query)
            print(f"[MEMORY] Query: {memory_query}")

            t_memory = time.time()

            if use_reflect:
                # REFLECT MODE: Use LLM to synthesize memories into coherent answer
                result = await reflect_async(query=memory_query, budget="high")
                memory_timing = time.time() - t_memory
                print(f"[MEMORY] Reflect took {memory_timing:.2f}s")

                if result and hasattr(result, 'text') and result.text:
                    memory_context = result.text
                    print(f"[MEMORY] Got reflected context: {memory_context[:200]}...")
            else:
                # RECALL MODE: Get raw facts without LLM synthesis
                result = await recall_async(query=memory_query, budget="high")
                memory_timing = time.time() - t_memory
                print(f"[MEMORY] Recall took {memory_timing:.2f}s")

                if result and len(result) > 0:
                    # Format raw memories as context
                    memory_context = format_recall_as_context(result)
                    # Also store raw memories for UI display
                    raw_memories = [{"text": r.text, "type": r.fact_type, "weight": r.weight} for r in result]
                    print(f"[MEMORY] Got {len(result)} raw memories")

            # Inject memory into system prompt if we have any
            if memory_context:
                system_prompt = f"{base_system_prompt}\n\n# Relevant Memory\n{memory_context}"

                # Send memory event to frontend
                await websocket.send_json(event(EventType.MEMORY_REFLECT, {
                    "method": memory_method,
                    "query": memory_query,
                    "context": memory_context,
                    "memories": raw_memories if not use_reflect else [],  # Raw facts for recall mode
                    "count": len(raw_memories) if not use_reflect else 1,
                    "timing": memory_timing,
                }))
            else:
                print("[MEMORY] No memories found")
                # Send empty memory event
                await websocket.send_json(event(EventType.MEMORY_REFLECT, {
                    "method": memory_method,
                    "query": memory_query,
                    "context": None,
                    "memories": [],
                    "count": 0,
                    "timing": memory_timing,
                }))

        except Exception as e:
            print(f"[MEMORY] Error during {memory_method}: {e}")
            import traceback
            traceback.print_exc()
            # Continue without memory injection if it fails

    # Initial messages with (possibly augmented) system prompt
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": f"Please deliver this package: {package}"}
    ]

    tools = AgentTools(building, agent_state)
    success = False
    error_msg = None

    try:
        while max_steps is None or agent_state.steps_taken < max_steps:
            # Check for cancellation
            if cancelled and cancelled.is_set():
                await websocket.send_json(event(EventType.CANCELLED, {"message": "Delivery cancelled by user"}))
                return

            # Send thinking event
            await websocket.send_json(event(EventType.AGENT_THINKING))

            # Call LLM
            t0 = time.time()

            # Call LLM without per-call memory injection (we did it at the start)
            response = await completion(
                model=llm_model,
                messages=messages,
                tools=get_tool_definitions(building.difficulty),
                tool_choice="required",
                timeout=30,
            )
            timing = time.time() - t0

            # Memory was injected at start, so we track it for the first action only
            injection_info = None
            if agent_state.steps_taken == 1 and memory_context:
                injection_info = {
                    "injected": True,
                    "count": 1,
                    "context": memory_context,
                }

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
                    action_payload = {
                        "step": agent_state.steps_taken,
                        "toolName": tool_name,
                        "toolArgs": arguments,
                        "toolResult": result,
                        "thinking": message.content if message.content else None,
                        "floor": agent_state.floor,
                        "side": agent_state.side.value,
                        "timing": timing,
                        "memoryInjection": injection_info,
                        "llmDetails": {
                            "toolCalls": [{"name": tc.function.name, "arguments": tc.function.arguments}
                                         for tc in message.tool_calls]
                        }
                    }
                    # Add hard mode grid position if available
                    if hasattr(agent_state, 'grid_row'):
                        action_payload["gridRow"] = agent_state.grid_row
                        action_payload["gridCol"] = agent_state.grid_col
                        action_payload["currentBuilding"] = agent_state.current_building
                    await websocket.send_json(event(EventType.AGENT_ACTION, action_payload))

                    # Small delay between actions to allow frontend animation
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
                        final_convo = format_messages_for_retain(
                            messages,
                            success=True,
                            steps=agent_state.steps_taken,
                            recipient=package.recipient_name
                        )
                        t_store = time.time()
                        await retain_async(
                            final_convo,
                            context=f"delivery:{package.recipient_name}:success",
                            document_id=f"delivery-{delivery_id}"
                        )
                        store_timing = time.time() - t_store
                        await websocket.send_json(event(EventType.MEMORY_STORED, {"timing": store_timing}))

                    # Send success
                    await websocket.send_json(event(EventType.DELIVERY_SUCCESS, {
                        "message": result,
                        "steps": agent_state.steps_taken
                    }))
                    return

            else:
                # No tool calls - nudge to use tools
                if message.content:
                    action_payload = {
                        "step": agent_state.steps_taken,
                        "toolName": "response",
                        "toolArgs": {},
                        "toolResult": message.content,
                        "floor": agent_state.floor,
                        "side": agent_state.side.value,
                        "timing": timing,
                    }
                    # Add hard mode grid position if available
                    if hasattr(agent_state, 'grid_row'):
                        action_payload["gridRow"] = agent_state.grid_row
                        action_payload["gridCol"] = agent_state.grid_col
                        action_payload["currentBuilding"] = agent_state.current_building
                    await websocket.send_json(event(EventType.AGENT_ACTION, action_payload))
                messages.append({"role": "assistant", "content": message.content})
                messages.append({"role": "user", "content": "Use the available tools to complete the delivery."})

        # Step limit reached - store failed delivery (if enabled)
        if store_conversations:
            await websocket.send_json(event(EventType.MEMORY_STORING))
            final_convo = format_messages_for_retain(
                messages,
                success=False,
                steps=agent_state.steps_taken,
                recipient=package.recipient_name
            )
            t_store = time.time()
            await retain_async(
                final_convo,
                context=f"delivery:{package.recipient_name}:failed",
                document_id=f"delivery-{delivery_id}"
            )
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


async def run_delivery_fast(
    building: Building,
    package: Package,
    max_steps: int = 150,
    model: Optional[str] = None,
    hindsight: Optional[dict] = None,
    delivery_id: int = 0,
) -> dict:
    """Run a delivery without WebSocket streaming (fast-forward mode).

    Args:
        building: The building to navigate
        package: The package to deliver
        max_steps: Maximum steps allowed
        model: LLM model to use (None = use default from config)
        hindsight: Hindsight settings (inject, reflect, store, query)
        delivery_id: Unique ID for this delivery (for memory grouping)

    Returns:
        dict with success, steps, and actions taken
    """
    # Use provided model or fall back to default
    llm_model = model or LLM_MODEL

    # Configure hindsight based on settings
    inject_memories = hindsight.get("inject", True) if hindsight else True
    use_reflect = hindsight.get("reflect", False) if hindsight else False  # False = recall, True = reflect
    store_conversations = hindsight.get("store", True) if hindsight else True
    custom_bank_id = hindsight.get("bankId") if hindsight else None
    custom_query = hindsight.get("query") if hindsight else None
    custom_background = hindsight.get("background") if hindsight else None

    # Update hindsight defaults if custom bank_id provided
    if custom_bank_id:
        set_bank_id(custom_bank_id, set_background=False)

    # Set custom bank background if provided (guides memory extraction)
    # Uses async-safe version to avoid event loop conflicts
    if custom_background:
        set_bank_background_async(custom_background)

    # Set up agent state - starting position depends on difficulty
    if building.is_city_grid:
        # Hard mode: start on road at (0, 0) - top-left corner, in front of Tech Corp
        agent_state = AgentState(floor=1, side=Side.STREET, grid_row=0, grid_col=0, current_building=None)
    elif building.is_multi_building:
        # Medium mode: start at Building A, Floor 1
        agent_state = AgentState(floor=1, side=Side.BUILDING_A)
    else:
        # Easy mode: start at Floor 1, Front
        agent_state = AgentState(floor=1, side=Side.FRONT)
    agent_state.current_package = package

    # Set document ID for memory grouping
    set_document_id(f"delivery-{delivery_id}")

    # Build system prompt - may be augmented with memory
    base_system_prompt = "You are a delivery agent. Use the tools provided to get it delivered."
    system_prompt = base_system_prompt
    memory_context = None
    memory_method = "reflect" if use_reflect else "recall"

    # MEMORY INJECTION: Call recall or reflect ONCE at start to get relevant memories
    if inject_memories:
        try:
            memory_query = get_hindsight_query(package.recipient_name, custom_query)

            if use_reflect:
                # REFLECT MODE: Use LLM to synthesize memories
                result = await reflect_async(query=memory_query, budget="high")
                if result and hasattr(result, 'text') and result.text:
                    memory_context = result.text
            else:
                # RECALL MODE: Get raw facts without LLM synthesis
                result = await recall_async(query=memory_query, budget="high")
                if result and len(result) > 0:
                    memory_context = format_recall_as_context(result)

            if memory_context:
                system_prompt = f"{base_system_prompt}\n\n# Relevant Memory\n{memory_context}"
        except Exception as e:
            print(f"[MEMORY] Error during {memory_method}: {e}")

    # Initial messages with (possibly augmented) system prompt
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": f"Please deliver this package: {package}"}
    ]

    tools = AgentTools(building, agent_state)
    success = False
    actions = []

    try:
        while agent_state.steps_taken < max_steps:
            # Call LLM without per-call memory injection
            t0 = time.time()
            response = await completion(
                model=llm_model,
                messages=messages,
                tools=get_tool_definitions(building.difficulty),
                tool_choice="required",
                timeout=30,
            )
            timing = time.time() - t0

            # Track memory count for first action only
            memory_count = 1 if agent_state.steps_taken == 1 and memory_context else 0

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

                    actions.append({
                        "step": agent_state.steps_taken,
                        "tool": tool_name,
                        "args": arguments,
                        "result": result[:100] if len(result) > 100 else result,
                        "timing": round(timing * 1000),
                        "memoryCount": memory_count,
                    })

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
                        final_convo = format_messages_for_retain(
                            messages,
                            success=True,
                            steps=agent_state.steps_taken,
                            recipient=package.recipient_name
                        )
                        await retain_async(
                            final_convo,
                            context=f"delivery:{package.recipient_name}:success",
                            document_id=f"delivery-{delivery_id}"
                        )
                    break

            else:
                # No tool calls - nudge to use tools
                messages.append({"role": "assistant", "content": message.content})
                messages.append({"role": "user", "content": "Use the available tools to complete the delivery."})

        # If we exit the loop without success, store the failed delivery
        if not success and store_conversations:
            final_convo = format_messages_for_retain(
                messages,
                success=False,
                steps=agent_state.steps_taken,
                recipient=package.recipient_name
            )
            await retain_async(
                final_convo,
                context=f"delivery:{package.recipient_name}:failed",
                document_id=f"delivery-{delivery_id}"
            )

        return {
            "success": success,
            "steps": agent_state.steps_taken,
            "actions": actions,
            "floor": agent_state.floor,
            "side": agent_state.side.value,
            "memoryInjected": memory_context is not None,
        }

    except Exception as e:
        import traceback
        return {
            "success": False,
            "steps": agent_state.steps_taken,
            "actions": actions,
            "error": str(e),
            "traceback": traceback.format_exc(),
        }
