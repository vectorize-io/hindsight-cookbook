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
    compute_optimal_steps, compute_path_efficiency, compute_remaining_steps,
)
from agent_tools import (
    AgentTools, get_tool_definitions_with_memory, execute_tool,
    MemoryToolHandler,
)
from .benchmark_types import (
    AgentMode, BenchmarkConfig, BenchmarkResults,
    DeliveryMetrics, DeliveryQueue, generate_delivery_queue,
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
    wait_for_pending_consolidation_async,
    initialize_memory,
    BANK_MISSION,
)
from ..config import set_hindsight_url
from ..websocket.events import event, EventType
from ..config import LLM_MODEL


def generate_preseed_facts(building: Building, coverage: float) -> str:
    """Generate pre-seed facts about the building for memory.

    Args:
        building: The building to generate facts for
        coverage: Fraction of employees to include (0.0-1.0)

    Returns:
        String of facts separated by newlines
    """
    import random

    facts = []

    # Building structure facts
    if hasattr(building, 'floors') and building.floors:
        facts.append(f"The building has {len(building.floors)} floors.")

    # Get all employees and select subset based on coverage
    all_employees = list(building.all_employees.items())
    num_to_include = max(1, int(len(all_employees) * coverage))
    selected = random.sample(all_employees, min(num_to_include, len(all_employees)))

    # Generate facts for selected employees
    businesses_mentioned = set()
    for emp_name, (business, _) in selected:
        # Employee location fact
        facts.append(f"{emp_name} works at {business.name} on floor {business.floor}.")

        # Business location fact (once per business)
        if business.name not in businesses_mentioned:
            side_name = business.side.value if hasattr(business.side, 'value') else str(business.side)
            facts.append(f"{business.name} is located on floor {business.floor}, {side_name} side.")
            businesses_mentioned.add(business.name)

    return "\n".join(facts)


def get_hindsight_query(recipient_name: str, custom_query: str = None) -> str:
    """Generate a memory query for the delivery."""
    if custom_query:
        return custom_query.replace("{recipient}", recipient_name)
    return f"Where does {recipient_name} work? What locations have I already checked? Only include building layout and optimal paths if known from past deliveries."


def _format_delivery_context_for_query(messages: list, recipient: str = None) -> str:
    """Format the current delivery conversation as context for per-step Hindsight queries.

    This gives Hindsight the running delivery history so it can provide more contextual responses.

    Args:
        messages: The current conversation messages
        recipient: The delivery recipient name

    Returns:
        Formatted context string with delivery progress
    """
    items = []
    if recipient:
        items.append(f"Delivering to: {recipient}")

    for msg in messages:
        role = msg.get("role", "").upper()
        content = msg.get("content", "")
        tool_calls = msg.get("tool_calls", [])

        # Skip system prompt (too verbose for context)
        if role == "SYSTEM":
            continue

        if role == "TOOL":
            # Include tool results (these show what the agent has discovered)
            items.append(f"Observed: {content[:200]}")  # Truncate long results
            continue

        if tool_calls:
            # Show what actions the agent took
            for tc in tool_calls:
                if hasattr(tc, 'function'):
                    items.append(f"Action: {tc.function.name}")
                elif isinstance(tc, dict) and 'function' in tc:
                    items.append(f"Action: {tc['function'].get('name', '')}")

    # Limit context length to avoid making query too long
    context = "\n".join(items[-10:])  # Keep last 10 items
    return context


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


async def update_filesystem_notes_with_llm(
    existing_notes: str,
    recipient: str,
    business_name: str,
    target_floor: int,
    target_side: str,
    success: bool,
    steps_taken: int,
    model: str,
) -> str:
    """Use an LLM to update notes based on delivery outcome.

    This makes filesystem mode more comparable to Hindsight, which also uses
    LLM processing to extract and organize information.

    Args:
        existing_notes: Current notes content
        recipient: Recipient name
        business_name: Business name where recipient works
        target_floor: Floor number
        target_side: Side of building (e.g., "front", "back")
        success: Whether delivery succeeded
        steps_taken: Number of steps taken in this delivery
        model: LLM model to use

    Returns:
        Updated notes content
    """
    # Build the delivery summary
    if success:
        delivery_summary = f"""DELIVERY COMPLETED SUCCESSFULLY
- Recipient: {recipient}
- Location: Floor {target_floor}, {target_side} side
- Business: {business_name or "Unknown"}
- Steps taken: {steps_taken}"""
    else:
        delivery_summary = f"""DELIVERY FAILED
- Recipient: {recipient}
- Target was: Floor {target_floor}, {target_side} side, {business_name or "Unknown business"}
- Steps taken before failure: {steps_taken}
- Note: Could not complete delivery within step limit"""

    # Build the prompt for the LLM
    system_prompt = """You are a note-taking assistant for a delivery agent. Your job is to maintain concise, useful notes about building layouts and employee locations.

Guidelines:
- Keep notes concise and scannable (use short lines, not paragraphs)
- Focus on information useful for future deliveries: employee names, their locations (floor, side), business names
- Update or correct existing information if the new delivery provides better data
- Remove outdated or incorrect information
- You can also note patterns, shortcuts, or tips discovered during deliveries
- If a delivery failed, still note any useful information learned (e.g., "John Smith is NOT on Floor 1")

Output ONLY the updated notes, nothing else. No explanations or commentary."""

    user_prompt = f"""Here are the current notes:
---
{existing_notes if existing_notes else "(No notes yet)"}
---

Here is information from the most recent delivery:
---
{delivery_summary}
---

Please update the notes to incorporate any useful information from this delivery. Output only the updated notes."""

    try:
        response = await completion(
            model=model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            timeout=30,
        )

        updated_notes = response.choices[0].message.content.strip()
        return updated_notes
    except Exception as e:
        print(f"[BENCHMARK] LLM notes update error: {e}")
        # Fallback to simple append if LLM fails
        if success:
            new_line = f"{recipient} - Floor {target_floor} {target_side}, {business_name or 'Unknown'}"
            if existing_notes:
                return f"{existing_notes}\n{new_line}"
            return new_line
        return existing_notes or ""


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

    # Determine max steps: max(min_steps, optimal * multiplier), capped by max_steps if set
    max_steps = max(config.min_steps, int(metrics.optimal_steps * config.step_multiplier))
    if config.max_steps is not None:
        max_steps = min(max_steps, config.max_steps)

    # Error tracking: get target position
    errors = 0
    target_floor, target_side, target_building_name = 1, Side.FRONT, None
    if recipient_name in building.all_employees:
        target_business, _ = building.all_employees[recipient_name]
        target_floor = target_business.floor
        target_side = target_business.side
        if building.is_city_grid and hasattr(target_business, 'building_name'):
            target_building_name = target_business.building_name

    # Build system prompt based on mode
    if config.mode == AgentMode.FILESYSTEM:
        if config.memory_query_mode in ["per_step", "both"]:
            # Per-step or both: agent can read notes during delivery
            base_system_prompt = """You are a delivery agent navigating a building to deliver packages.

Your goal is to find the target office and deliver the package as efficiently as possible.

You have access to read_notes() to check your memory at any time.
- Use read_notes() to recall what you know about the building and employees
- Notes contain information from previous deliveries - use them to navigate efficiently!"""
        else:
            # inject_once: notes are auto-injected, no tools needed
            base_system_prompt = "You are a delivery agent. Use the tools provided to get it delivered."
    else:
        base_system_prompt = "You are a delivery agent. Use the tools provided to get it delivered."

    system_prompt = base_system_prompt
    memory_context = None

    # Determine tools based on mode
    # Filesystem gets read_notes tool in per_step or both modes
    include_filesystem = config.mode == AgentMode.FILESYSTEM and config.memory_query_mode in ["per_step", "both"]

    # Memory handler for filesystem mode (read_notes/write_notes)
    filesystem_notes_key = get_bank_id() or f"delivery-{delivery_id}"
    memory_handler = MemoryToolHandler(
        recall_fn=None,
        notes_key=filesystem_notes_key,
    )

    # Helper to determine if we should use reflect vs recall
    def should_use_reflect() -> bool:
        return (
            config.mode == AgentMode.REFLECT or
            (config.mode in [AgentMode.HINDSIGHT_MM, AgentMode.HINDSIGHT_MM_NOWAIT] and config.mm_query_type == "reflect")
        )

    # MEMORY INJECTION at start (unless no_memory or filesystem mode)
    if config.mode not in [AgentMode.NO_MEMORY, AgentMode.FILESYSTEM] and config.memory_query_mode in ["inject_once", "both"]:
        try:
            memory_query = get_hindsight_query(recipient_name, config.query)

            if should_use_reflect():
                result = await reflect_async(query=memory_query, budget="high", bank_id=config.bank_id)
                if result and hasattr(result, 'text') and result.text:
                    memory_context = result.text
                    metrics.memory_injected = True
            else:
                # Recall mode (including MM modes with mm_query_type="recall")
                result = await recall_async(query=memory_query, budget="high", bank_id=config.bank_id)
                if result and len(result) > 0:
                    memory_context = format_recall_as_context(result)
                    metrics.memory_injected = True

            if memory_context:
                system_prompt = f"{base_system_prompt}\n\n# Relevant Memory\n{memory_context}"

                if websocket:
                    await websocket.send_json(event(EventType.MEMORY_REFLECT, {
                        "method": "reflect" if should_use_reflect() else "recall",
                        "query": memory_query,
                        "text": memory_context,
                        "bankId": get_bank_id(),
                    }))

        except Exception as e:
            print(f"[BENCHMARK] Memory injection error: {e}")

    # FILESYSTEM NOTES INJECTION at start (for inject_once or both modes)
    if config.mode == AgentMode.FILESYSTEM and config.memory_query_mode in ["inject_once", "both"]:
        existing_notes = MemoryToolHandler.get_notes(filesystem_notes_key)
        if existing_notes:
            system_prompt = f"{base_system_prompt}\n\n# Your Notes\n{existing_notes}"
            metrics.memory_injected = True

            if websocket:
                await websocket.send_json(event(EventType.MEMORY_REFLECT, {
                    "method": "filesystem",
                    "query": "read_notes",
                    "text": existing_notes,
                    "bankId": filesystem_notes_key,
                }))

    # Initial messages
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": f"Please deliver this package: {package}"}
    ]

    tools = AgentTools(building, agent_state)
    tool_defs = get_tool_definitions_with_memory(
        difficulty=building.difficulty,
        include_memory=False,  # No remember tool - we use automatic per-step injection
        include_filesystem=include_filesystem,
    )

    # Determine if we should do per-step memory injection
    # Per-step only makes sense for REFLECT (not RECALL) because:
    # - Recall returns static facts that don't change during a delivery
    # - Reflect synthesizes context-aware guidance that benefits from knowing current location/progress
    do_per_step_injection = (
        config.memory_query_mode in ["per_step", "both"] and
        should_use_reflect()  # Only for reflect mode or MM modes with mm_query_type="reflect"
    )

    success = False

    try:
        while agent_state.steps_taken < max_steps:
            if websocket:
                await websocket.send_json(event(EventType.AGENT_THINKING))

            # PER-STEP MEMORY INJECTION (REFLECT ONLY): Query Hindsight before each LLM call
            # This only runs for reflect mode - recall returns static facts that don't benefit from per-step queries
            if do_per_step_injection:
                try:
                    # Build query with current location and full delivery history as context
                    current_location = agent_state.position_str()
                    memory_query = f"How do I reach {recipient_name}?"

                    # Build context from delivery history (reflects benefits from knowing what's been tried)
                    delivery_context = _format_delivery_context_for_query(messages, recipient_name)
                    context_str = f"I am at {current_location}. I need to deliver to {recipient_name}."
                    if delivery_context:
                        context_str += f"\n\nDelivery progress:\n{delivery_context}"

                    # Include context in query (per Hindsight API recommendation)
                    contextual_query = f"{memory_query}\n\nContext: {context_str}"

                    # Always reflect for per-step (recall doesn't benefit from per-step)
                    result = await reflect_async(query=contextual_query, budget="high", bank_id=config.bank_id)
                    step_memory = result.text if result and hasattr(result, 'text') else None

                    if step_memory:
                        # Inject memory guidance as a system message
                        messages.append({
                            "role": "system",
                            "content": f"Memory guidance: {step_memory}"
                        })
                        metrics.memory_query_count += 1

                        if websocket:
                            await websocket.send_json(event(EventType.MEMORY_REFLECT, {
                                "method": "reflect",
                                "query": contextual_query,
                                "text": step_memory,
                                "bankId": get_bank_id(),
                                "perStep": True,
                            }))

                except Exception as e:
                    print(f"[BENCHMARK] Per-step memory injection error: {e}")

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

                    # Track position for error detection
                    prev_position = agent_state.position_str()
                    remaining_before = compute_remaining_steps(
                        current_floor=agent_state.floor,
                        current_side=agent_state.side,
                        target_floor=target_floor,
                        target_side=target_side,
                        building=building,
                        current_building=agent_state.current_building,
                        target_building_name=target_building_name,
                        grid_row=agent_state.grid_row,
                        grid_col=agent_state.grid_col,
                    )

                    # Execute regular tool
                    result = execute_tool(tools, tool_name, arguments)

                    # Check for non-optimal move (error tracking)
                    # An error is: failed tool call (position unchanged) OR move that doesn't improve distance
                    new_position = agent_state.position_str()
                    is_movement_tool = tool_name in ["go_up", "go_down", "go_to_front", "go_to_back",
                                                      "cross_bridge", "go_to_building", "enter_building",
                                                      "exit_building", "move_north", "move_south",
                                                      "move_east", "move_west"]

                    if is_movement_tool:
                        if new_position == prev_position:
                            # Failed tool call (e.g., "Cannot go up. Already at top floor")
                            errors += 1
                        else:
                            # Position changed - check if it improved distance
                            remaining_after = compute_remaining_steps(
                                current_floor=agent_state.floor,
                                current_side=agent_state.side,
                                target_floor=target_floor,
                                target_side=target_side,
                                building=building,
                                current_building=agent_state.current_building,
                                target_building_name=target_building_name,
                                grid_row=agent_state.grid_row,
                                grid_col=agent_state.grid_col,
                            )
                            if remaining_after >= remaining_before:
                                # Moved in wrong direction
                                errors += 1

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
    metrics.errors = errors
    metrics.error_rate = errors / max(agent_state.steps_taken, 1)

    # FILESYSTEM AUTO-WRITE: Use LLM to update notes with delivery learnings
    if config.mode == AgentMode.FILESYSTEM:
        try:
            existing_notes = MemoryToolHandler.get_notes(filesystem_notes_key)
            target_side_str = target_side.value if hasattr(target_side, 'value') else str(target_side)

            if websocket:
                await websocket.send_json(event(EventType.MEMORY_STORING))

            updated_notes = await update_filesystem_notes_with_llm(
                existing_notes=existing_notes,
                recipient=recipient_name,
                business_name=business_name,
                target_floor=target_floor,
                target_side=target_side_str,
                success=success,
                steps_taken=agent_state.steps_taken,
                model=config.model,
            )

            # Save updated notes
            MemoryToolHandler._notes_storage[filesystem_notes_key] = updated_notes

            if websocket:
                await websocket.send_json(event(EventType.MEMORY_STORED, {
                    "method": "filesystem",
                    "notes": updated_notes,
                    "bankId": filesystem_notes_key,
                }))
        except Exception as e:
            print(f"[BENCHMARK] Filesystem notes update error: {e}")

    # Store memory to Hindsight (unless no_memory or filesystem mode)
    if config.mode not in [AgentMode.NO_MEMORY, AgentMode.FILESYSTEM]:
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
                document_id=f"delivery-{delivery_id}",
                bank_id=config.bank_id
            )
            store_timing = time.time() - t_store
            if websocket:
                await websocket.send_json(event(EventType.MEMORY_STORED, {"timing": store_timing}))

            # For MM modes with wait_for_consolidation, wait for pending_consolidation to reach 0
            # This matches the eval framework behavior - wait after EVERY retain, not just after N deliveries
            if config.mode == AgentMode.HINDSIGHT_MM and config.wait_for_consolidation:
                if websocket:
                    await websocket.send_json(event(EventType.MODELS_REFRESHING, {"message": "Waiting for consolidation..."}))
                try:
                    t_consolidate = time.time()
                    success_consolidation = await wait_for_pending_consolidation_async(bank_id=config.bank_id, poll_interval=2.0, timeout=300.0)
                    consolidate_timing = time.time() - t_consolidate
                    metrics.consolidation_triggered = True
                    if websocket:
                        await websocket.send_json(event(EventType.MODELS_REFRESHED, {
                            "success": success_consolidation,
                            "timing": consolidate_timing
                        }))
                except Exception as e:
                    print(f"[BENCHMARK] Consolidation wait error: {e}")
                    if websocket:
                        await websocket.send_json(event(EventType.MODELS_REFRESHED, {"success": False, "error": str(e)}))
        except Exception as e:
            print(f"[BENCHMARK] Memory storage error: {e}")

    # Track delivery count for refresh interval (used for periodic explicit consolidation)
    if config.mode in [AgentMode.HINDSIGHT_MM, AgentMode.HINDSIGHT_MM_NOWAIT]:
        should_refresh = record_delivery()
        # For nowait mode, we can optionally trigger explicit consolidation at intervals
        if should_refresh and config.mode == AgentMode.HINDSIGHT_MM_NOWAIT:
            # Fire and forget - don't wait for consolidation
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

    # Set hindsight URL if specified in config
    if config.hindsight_url:
        set_hindsight_url(config.hindsight_url)
        initialize_memory(config.hindsight_url)

    # Set up memory bank
    if config.mode != AgentMode.NO_MEMORY and config.mode != AgentMode.FILESYSTEM:
        # Only set mission for mental model modes (recall/reflect should NOT have mission)
        # This matches the eval framework behavior where mission enables mental model generation
        should_set_mission = config.mode in [AgentMode.HINDSIGHT_MM, AgentMode.HINDSIGHT_MM_NOWAIT]

        # Use custom bank_id if provided
        if config.bank_id:
            set_bank_id(config.bank_id, app_type="bench", difficulty=config.difficulty)
        else:
            configure_memory(
                app_type="bench",
                difficulty=config.difficulty,
                set_mission=should_set_mission
            )

        set_refresh_interval(config.refresh_interval, app_type="bench", difficulty=config.difficulty)

        # Set custom mission if provided
        if config.mission:
            await set_bank_mission_async(get_bank_id(), config.mission)

        # Clear existing mental models for fresh start (only for MM modes)
        if should_set_mission:
            await clear_mental_models_async()

        # Pre-seed memory with building knowledge if preseed_coverage > 0
        if config.preseed_coverage > 0:
            preseed_facts = generate_preseed_facts(building, config.preseed_coverage)
            if preseed_facts:
                await retain_async(
                    preseed_facts,
                    context="building_knowledge:preseed",
                    document_id="preseed-building-knowledge",
                    bank_id=config.bank_id
                )
                if websocket:
                    await websocket.send_json(event(EventType.MEMORY_STORED, {
                        "message": f"Pre-seeded {len(preseed_facts.splitlines())} facts",
                        "preseed": True,
                    }))

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
