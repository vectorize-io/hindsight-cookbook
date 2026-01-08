"""Agent service - handles delivery execution with LLM."""

import json
import time
import asyncio
from typing import AsyncGenerator, Optional
from fastapi import WebSocket

import sys
sys.path.insert(0, str(__file__).rsplit("/app/", 1)[0])

from building import Building, Package, AgentState, get_building
from agent_tools import AgentTools, TOOL_DEFINITIONS, execute_tool
from .memory_service import (
    completion,
    retain,
    get_last_injection_debug,
    set_document_id,
)
from ..websocket.events import (
    event, EventType, AgentActionPayload, DeliverySuccessPayload,
    DeliveryFailedPayload, StepLimitPayload
)
from ..config import LLM_MODEL


def format_messages_for_retain(messages: list) -> str:
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

    return "\n\n".join(items)


async def run_delivery(
    websocket: WebSocket,
    building: Building,
    package: Package,
    delivery_id: int,
    max_steps: Optional[int] = None,
    cancelled: asyncio.Event = None,
):
    """Run a delivery, streaming events via WebSocket.

    Args:
        websocket: WebSocket connection to stream events to
        building: The building to navigate
        package: The package to deliver
        delivery_id: Unique ID for this delivery (for memory grouping)
        max_steps: Maximum steps allowed (None = no limit)
        cancelled: Event to signal cancellation
    """
    # Set up agent state
    agent_state = AgentState()
    agent_state.current_package = package

    # Set document ID for memory grouping
    set_document_id(f"delivery-{delivery_id}")

    # Initial messages
    messages = [
        {"role": "system", "content": "You are a delivery agent. Use the tools provided to get it delivered."},
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

            # Debug: Check hindsight state before completion
            import hindsight_litellm
            config = hindsight_litellm.get_config()
            defaults = hindsight_litellm.get_defaults()
            print(f"[AGENT DEBUG] Before completion:")
            print(f"[AGENT DEBUG]   inject_memories={config.inject_memories if config else 'N/A'}")
            print(f"[AGENT DEBUG]   bank_id={defaults.bank_id if defaults else 'N/A'}")
            print(f"[AGENT DEBUG]   use_reflect={defaults.use_reflect if defaults else 'N/A'}")
            print(f"[AGENT DEBUG]   user_query={messages[-1].get('content', '')[:50] if messages else 'N/A'}")

            response = await completion(
                model=LLM_MODEL,
                messages=messages,
                tools=TOOL_DEFINITIONS,
                tool_choice="required",
                timeout=30,
            )
            timing = time.time() - t0

            # Get injection debug info - always include it so UI shows memory status
            injection_info = None
            injection_debug = get_last_injection_debug()
            print(f"[MEMORY DEBUG] injection_debug: {injection_debug}")
            if injection_debug:
                print(f"[MEMORY DEBUG] injected={injection_debug.injected}, count={injection_debug.results_count}")
                print(f"[MEMORY DEBUG] bank_id used: {injection_debug.bank_id}")
                print(f"[MEMORY DEBUG] query: {injection_debug.query}")
                print(f"[MEMORY DEBUG] error: {injection_debug.error}")
                print(f"[MEMORY DEBUG] context length: {len(injection_debug.memory_context) if injection_debug.memory_context else 0}")
                # Always include injection info so UI can show status
                injection_info = {
                    "injected": injection_debug.injected,
                    "count": injection_debug.results_count or 0,
                    "context": injection_debug.memory_context if injection_debug.injected else None,
                    # Debug: include bank_id and error in response
                    "bankId": injection_debug.bank_id,
                    "query": injection_debug.query,
                    "error": injection_debug.error,
                }
            else:
                print("[MEMORY DEBUG] No injection_debug returned")

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
                        "memoryInjection": injection_info,
                        "llmDetails": {
                            "toolCalls": [{"name": tc.function.name, "arguments": tc.function.arguments}
                                         for tc in message.tool_calls]
                        }
                    }))

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
                    # Store memory
                    await websocket.send_json(event(EventType.MEMORY_STORING))
                    final_convo = format_messages_for_retain(messages)
                    t_store = time.time()
                    retain(final_convo)
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

        # Step limit reached
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
