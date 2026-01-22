"""Benchmark service - orchestrates benchmark runs with different agent modes."""

import json
import time
import asyncio
from typing import Optional
from fastapi import WebSocket

import sys
sys.path.insert(0, str(__file__).rsplit("/app/", 1)[0])

from building import (
    Building, Package, AgentState, Side, get_building,
    compute_optimal_steps, compute_path_efficiency,
)
from agent_tools import (
    AgentTools, get_tool_definitions_with_memory, execute_tool,
    MemoryToolHandler,
)
from .benchmark_types import (
    AgentMode, BenchmarkConfig, BenchmarkResults,
    DeliveryMetrics, TokenUsage, DeliveryQueue, generate_delivery_queue,
)
from .memory_service import (
    completion,
    retain_async,
    recall_async,
    reflect_async,
    format_recall_as_context,
    get_bank_id,
    set_bank_id,
    set_bank_mission_async,
    refresh_mental_models_async,
    clear_mental_models_async,
    record_delivery,
    reset_delivery_count,
    set_refresh_interval,
    configure_memory,
)
from ..websocket.events import event, EventType
from ..config import LLM_MODEL


def get_hindsight_query(recipient_name: str, custom_query: str = None) -> str:
    """Generate a memory query for the delivery."""
    if custom_query:
        return custom_query.replace("{recipient}", recipient_name)
    return f"Where does {recipient_name} work? What locations have I already checked? Only include building layout and optimal paths if known from past deliveries."


def format_messages_for_retain(messages: list, success: bool, steps: int, recipient: str = None) -> str:
    """Format conversation messages for storage to Hindsight."""
    items = []
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

    if success:
        items.append(f"OUTCOME: DELIVERY SUCCESSFUL in {steps} steps")
    else:
        items.append(f"OUTCOME: DELIVERY FAILED after {steps} steps")

    return "\n\n".join(items)


def extract_token_usage(response) -> TokenUsage:
    """Extract token usage from an LLM response."""
    usage = TokenUsage()
    if hasattr(response, 'usage') and response.usage:
        usage.prompt_tokens = getattr(response.usage, 'prompt_tokens', 0) or 0
        usage.completion_tokens = getattr(response.usage, 'completion_tokens', 0) or 0
        usage.total_tokens = getattr(response.usage, 'total_tokens', 0) or 0
    return usage


async def run_benchmark_delivery(
    building: Building,
    recipient_name: str,
    business_name: Optional[str],
    delivery_id: int,
    config: BenchmarkConfig,
    websocket: Optional[WebSocket] = None,
    is_repeat: bool = False,
) -> DeliveryMetrics:
    """Run a single benchmark delivery with the specified mode.

    Args:
        building: The building to navigate
        recipient_name: Name of the recipient
        business_name: Optional business name (may be None)
        delivery_id: Unique ID for this delivery
        config: Benchmark configuration
        websocket: Optional WebSocket for streaming events
        is_repeat: Whether this is a repeat visit to this recipient

    Returns:
        DeliveryMetrics with results
    """
    metrics = DeliveryMetrics(
        delivery_id=delivery_id,
        recipient=recipient_name,
        business=business_name,
        is_repeat=is_repeat,
        start_time=time.time(),
    )

    # Compute optimal steps
    metrics.optimal_steps = compute_optimal_steps(building, recipient_name)

    # Create package
    package = Package(
        id=str(delivery_id),
        recipient_name=recipient_name,
        business_name=business_name,
    )

    # Set up agent state based on difficulty
    if building.is_city_grid:
        agent_state = AgentState(floor=1, side=Side.STREET, grid_row=0, grid_col=0, current_building=None)
    elif building.is_multi_building:
        agent_state = AgentState(floor=1, side=Side.BUILDING_A)
    else:
        agent_state = AgentState(floor=1, side=Side.FRONT)
    agent_state.current_package = package

    # Determine max steps
    max_steps = max(config.min_steps, int(metrics.optimal_steps * config.step_multiplier))

    # Build system prompt
    base_system_prompt = "You are a delivery agent. Use the tools provided to get it delivered."
    system_prompt = base_system_prompt
    memory_context = None

    # Determine tools and memory handling based on mode
    include_memory = config.mode in [AgentMode.HINDSIGHT_MM, AgentMode.HINDSIGHT_MM_NOWAIT] and config.memory_query_mode in ["per_step", "both"]
    include_filesystem = config.mode == AgentMode.FILESYSTEM

    # Memory recall function for per-step queries
    async def recall_fn(query: str) -> str:
        if config.mode == AgentMode.REFLECT:
            result = await reflect_async(query=query, budget="high")
            return result.text if result and hasattr(result, 'text') else ""
        else:
            result = await recall_async(query=query, budget="high")
            return format_recall_as_context(result) if result else ""

    memory_handler = MemoryToolHandler(
        recall_fn=recall_fn if include_memory else None,
        notes_key=get_bank_id() or f"delivery-{delivery_id}",
    )

    # MEMORY INJECTION at start (unless no_memory mode)
    if config.mode != AgentMode.NO_MEMORY and config.memory_query_mode in ["inject_once", "both"]:
        try:
            memory_query = get_hindsight_query(recipient_name)

            if config.mode == AgentMode.REFLECT:
                result = await reflect_async(query=memory_query, budget="high")
                if result and hasattr(result, 'text') and result.text:
                    memory_context = result.text
                    metrics.memory_injected = True
            elif config.mode != AgentMode.FILESYSTEM:
                # Recall mode (including MM modes)
                result = await recall_async(query=memory_query, budget="high")
                if result and len(result) > 0:
                    memory_context = format_recall_as_context(result)
                    metrics.memory_injected = True

            if memory_context:
                system_prompt = f"{base_system_prompt}\n\n# Relevant Memory\n{memory_context}"

                if websocket:
                    await websocket.send_json(event(EventType.MEMORY_REFLECT, {
                        "method": "reflect" if config.mode == AgentMode.REFLECT else "recall",
                        "query": memory_query,
                        "text": memory_context,
                        "bankId": get_bank_id(),
                    }))

        except Exception as e:
            print(f"[BENCHMARK] Memory injection error: {e}")

    # Initial messages
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": f"Please deliver this package: {package}"}
    ]

    tools = AgentTools(building, agent_state)
    tool_defs = get_tool_definitions_with_memory(
        difficulty=building.difficulty,
        include_memory=include_memory,
        include_filesystem=include_filesystem,
    )

    success = False

    try:
        while agent_state.steps_taken < max_steps:
            if websocket:
                await websocket.send_json(event(EventType.AGENT_THINKING))

            # Call LLM
            t0 = time.time()
            response = await completion(
                model=config.model,
                messages=messages,
                tools=tool_defs,
                tool_choice="required",
                timeout=60,
            )
            timing = time.time() - t0

            # Track tokens
            token_usage = extract_token_usage(response)
            metrics.tokens.add(token_usage)

            message = response.choices[0].message

            if message.tool_calls:
                tool_results = []

                for tool_call in message.tool_calls:
                    tool_name = tool_call.function.name
                    arguments = json.loads(tool_call.function.arguments) if tool_call.function.arguments else {}

                    # Check if it's a memory tool (doesn't count as step)
                    mem_result, is_memory_tool = await memory_handler.execute(tool_name, arguments)
                    if is_memory_tool:
                        metrics.memory_query_count += 1
                        tool_results.append({
                            "tool_call_id": tool_call.id,
                            "role": "tool",
                            "content": mem_result
                        })
                        continue

                    # Execute regular tool
                    result = execute_tool(tools, tool_name, arguments)
                    tool_results.append({
                        "tool_call_id": tool_call.id,
                        "role": "tool",
                        "content": result
                    })

                    # Send action event
                    if websocket:
                        action_payload = {
                            "step": agent_state.steps_taken,
                            "toolName": tool_name,
                            "toolArgs": arguments,
                            "toolResult": result,
                            "thinking": message.content if message.content else None,
                            "floor": agent_state.floor,
                            "side": agent_state.side.value,
                            "timing": timing,
                        }
                        if hasattr(agent_state, 'grid_row'):
                            action_payload["gridRow"] = agent_state.grid_row
                            action_payload["gridCol"] = agent_state.grid_col
                            action_payload["currentBuilding"] = agent_state.current_building
                        await websocket.send_json(event(EventType.AGENT_ACTION, action_payload))

                    await asyncio.sleep(0.05)  # Small delay

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
                    break

            else:
                # No tool calls - nudge
                if message.content:
                    if websocket:
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

    except Exception as e:
        print(f"[BENCHMARK] Delivery error: {e}")
        import traceback
        traceback.print_exc()

    # Record results
    metrics.success = success
    metrics.steps_taken = agent_state.steps_taken
    metrics.end_time = time.time()

    # Store memory (unless no_memory mode)
    if config.mode != AgentMode.NO_MEMORY and config.mode != AgentMode.FILESYSTEM:
        try:
            final_convo = format_messages_for_retain(
                messages,
                success=success,
                steps=agent_state.steps_taken,
                recipient=recipient_name
            )
            if websocket:
                await websocket.send_json(event(EventType.MEMORY_STORING))
            t_store = time.time()
            await retain_async(
                final_convo,
                context=f"delivery:{recipient_name}:{'success' if success else 'failed'}",
                document_id=f"delivery-{delivery_id}"
            )
            store_timing = time.time() - t_store
            if websocket:
                await websocket.send_json(event(EventType.MEMORY_STORED, {"timing": store_timing}))
        except Exception as e:
            print(f"[BENCHMARK] Memory storage error: {e}")

    # Check for mental model consolidation
    if config.mode in [AgentMode.HINDSIGHT_MM, AgentMode.HINDSIGHT_MM_NOWAIT]:
        should_refresh = record_delivery()
        if should_refresh:
            metrics.consolidation_triggered = True
            if websocket:
                await websocket.send_json(event(EventType.MODELS_REFRESHING, {}))

            if config.mode == AgentMode.HINDSIGHT_MM and config.wait_for_consolidation:
                # Wait for consolidation
                try:
                    result = await refresh_mental_models_async()
                    if websocket:
                        await websocket.send_json(event(EventType.MODELS_REFRESHED, {"success": True}))
                except Exception as e:
                    print(f"[BENCHMARK] Consolidation error: {e}")
                    if websocket:
                        await websocket.send_json(event(EventType.MODELS_REFRESHED, {"success": False, "error": str(e)}))
            else:
                # Fire and forget
                asyncio.create_task(refresh_mental_models_async())

            reset_delivery_count()

    # Send completion event
    if websocket:
        if success:
            await websocket.send_json(event(EventType.DELIVERY_SUCCESS, {
                "message": f"Delivered to {recipient_name}",
                "steps": metrics.steps_taken,
                "optimalSteps": metrics.optimal_steps,
                "pathEfficiency": compute_path_efficiency(metrics.steps_taken, metrics.optimal_steps),
            }))
        else:
            await websocket.send_json(event(EventType.STEP_LIMIT_REACHED, {
                "message": f"Failed to deliver to {recipient_name}",
                "steps": metrics.steps_taken,
            }))

    return metrics


async def run_benchmark(
    config: BenchmarkConfig,
    websocket: Optional[WebSocket] = None,
    cancelled: asyncio.Event = None,
) -> BenchmarkResults:
    """Run a full benchmark with the specified configuration.

    Args:
        config: Benchmark configuration
        websocket: Optional WebSocket for streaming events
        cancelled: Event to signal cancellation

    Returns:
        BenchmarkResults with all metrics
    """
    results = BenchmarkResults(config=config)

    # Get building
    building = get_building(config.difficulty)

    # Set up memory bank
    if config.mode != AgentMode.NO_MEMORY and config.mode != AgentMode.FILESYSTEM:
        configure_memory(app_type="bench", difficulty=config.difficulty)
        set_refresh_interval(config.refresh_interval, app_type="bench", difficulty=config.difficulty)

        # Clear existing mental models for fresh start
        if config.mode in [AgentMode.HINDSIGHT_MM, AgentMode.HINDSIGHT_MM_NOWAIT]:
            await clear_mental_models_async()

    # Clear filesystem notes for fresh start
    if config.mode == AgentMode.FILESYSTEM:
        MemoryToolHandler.clear_notes()

    # Generate delivery queue
    queue = generate_delivery_queue(
        building=building,
        num_deliveries=config.num_deliveries,
        repeat_ratio=config.repeat_ratio,
        paired_mode=config.paired_mode,
        include_business=config.include_business,
        seed=config.seed,
    )

    # Send benchmark start event
    if websocket:
        await websocket.send_json(event(EventType.BENCHMARK_START, {
            "mode": config.mode.value,
            "numDeliveries": config.num_deliveries,
            "difficulty": config.difficulty,
        }))

    # Run deliveries
    for i, (recipient, business, is_repeat) in enumerate(queue):
        if cancelled and cancelled.is_set():
            break

        delivery_id = i + 1

        if websocket:
            await websocket.send_json(event(EventType.DELIVERY_START, {
                "deliveryId": delivery_id,
                "recipient": recipient,
                "business": business,
                "isRepeat": is_repeat,
                "progress": f"{delivery_id}/{config.num_deliveries}",
            }))

        metrics = await run_benchmark_delivery(
            building=building,
            recipient_name=recipient,
            business_name=business,
            delivery_id=delivery_id,
            config=config,
            websocket=websocket,
            is_repeat=is_repeat,
        )

        results.add_delivery(metrics)

        # Send progress update
        if websocket:
            await websocket.send_json(event(EventType.BENCHMARK_PROGRESS, {
                "completed": delivery_id,
                "total": config.num_deliveries,
                "currentEfficiency": metrics.path_efficiency,
                "avgEfficiency": results.avg_path_efficiency if results.efficiency_by_episode else 0,
            }))

    # Compute final metrics
    results.compute_final_metrics()

    # Send benchmark complete event
    if websocket:
        await websocket.send_json(event(EventType.BENCHMARK_COMPLETE, results.to_dict()))

    return results
