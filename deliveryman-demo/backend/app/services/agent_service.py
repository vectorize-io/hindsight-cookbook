"""Agent service - handles delivery execution with LLM."""

import json
import time
import asyncio
from typing import AsyncGenerator, Optional
from fastapi import WebSocket

import sys
sys.path.insert(0, str(__file__).rsplit("/app/", 1)[0])

from building import Building, Package, AgentState, Side, get_building, compute_optimal_steps, compute_path_efficiency, compute_remaining_steps
from agent_tools import AgentTools, get_tool_definitions, execute_tool, get_tool_definitions_with_memory, MemoryToolHandler
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
    get_bank_id,
    set_bank_mission_async,
    refresh_mental_models_async,
    record_delivery,
    reset_delivery_count,
    get_mental_models_async,
    get_bank_stats_async,
    wait_for_pending_consolidation_async,  # Wait for consolidation after retain
    BANK_MISSION,  # Default mission for hindsight
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


def generate_preseed_facts(building: Building, coverage: float = 1.0) -> list[str]:
    """Generate preseed facts algorithmically from building data.

    These facts represent knowledge an agent would gain from exploring
    the building. Used to skip the expensive exploration phase.

    Args:
        building: The building to generate facts for
        coverage: Fraction of employees/offices to include (0.0-1.0)

    Returns:
        List of fact strings
    """
    import random

    facts: list[str] = []

    # Get all employees
    all_employees = list(building.all_employees.items())

    # Subset based on coverage
    if coverage < 1.0:
        num_to_include = max(1, int(len(all_employees) * coverage))
        random.shuffle(all_employees)
        selected_employees = all_employees[:num_to_include]
    else:
        selected_employees = all_employees

    # Generate employee location facts
    for emp_name, (business, employee) in selected_employees:
        # Fact: Employee -> business and floor
        facts.append(
            f"{emp_name} works at {business.name} on floor {business.floor}."
        )
        # Fact: Business location
        facts.append(
            f"{business.name} is located on floor {business.floor}, {business.side.value} side."
        )

    # Generate building structure facts
    if building.is_city_grid:
        facts.append("This is a city grid with multiple buildings arranged in rows and columns.")
        facts.append("Navigate using go_to_building(name), go_up, go_down, go_to_front, go_to_back.")
    elif building.is_multi_building:
        facts.append("There are two connected buildings: Building A and Building B.")
        facts.append("Use go_to_building_a or go_to_building_b to switch between them.")
    else:
        facts.append(f"The building has {building.floors} floors.")
        facts.append("Each floor has a front side and back side with different businesses.")

    # Add navigation hints
    facts.append("Use go_up/go_down to change floors, go_to_front/go_to_back to change sides.")
    facts.append("Once at the correct location, use deliver_package to complete delivery.")

    return facts


async def preseed_memory(facts: list[str], delivery_id: int) -> None:
    """Pre-seed memory with building knowledge facts.

    Args:
        facts: List of fact strings to store
        delivery_id: Delivery ID for context
    """
    if not facts:
        return

    # Combine facts into a single document
    content = "Building Knowledge (Pre-seeded):\n\n" + "\n".join(f"- {fact}" for fact in facts)

    try:
        await retain_async(
            content,
            context="Pre-seeded building knowledge for delivery agent",
            document_id=f"preseed-{delivery_id}"
        )
    except Exception as e:
        print(f"[MEMORY] Failed to preseed facts: {e}")


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
    import sys
    print(f"=== DELIVERY STARTED: {package.recipient_name} (ID: {delivery_id}) ===", flush=True)
    print(f"Hindsight settings: {hindsight}", flush=True)
    sys.stdout.flush()

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
    if custom_background:
        await set_bank_mission_async(custom_bank_id, custom_background)

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
                    "text": memory_context,  # Frontend expects 'text' not 'context'
                    "bankId": get_bank_id(),
                    "memories": raw_memories if not use_reflect else [],  # Raw facts for recall mode
                    "count": len(raw_memories) if not use_reflect else 1,
                    "timing": memory_timing,
                }))
            else:
                print("[MEMORY] No memories found", flush=True)
                # Send empty memory event
                await websocket.send_json(event(EventType.MEMORY_REFLECT, {
                    "method": memory_method,
                    "query": memory_query,
                    "text": None,  # Frontend expects 'text' not 'context'
                    "bankId": get_bank_id(),
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
                    print(f"[MEMORY] Delivery success! store_conversations={store_conversations}")
                    if store_conversations:
                        print(f"[MEMORY] Storing conversation to bank...")
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
                        print(f"[MEMORY] Stored successfully in {store_timing:.2f}s to bank: {get_bank_id()}")
                        await websocket.send_json(event(EventType.MEMORY_STORED, {"timing": store_timing}))

                    # Record delivery and check if mental model refresh is needed
                    should_refresh = record_delivery()
                    if should_refresh:
                        # Send event that models are refreshing
                        await websocket.send_json(event(EventType.MODELS_REFRESHING, {}))

                        async def refresh_with_notification():
                            try:
                                await refresh_mental_models_async()
                                await websocket.send_json(event(EventType.MODELS_REFRESHED, {"success": True}))
                            except Exception as e:
                                print(f"[MEMORY] Mental models refresh failed: {e}")
                                await websocket.send_json(event(EventType.MODELS_REFRESHED, {"success": False, "error": str(e)}))

                        asyncio.create_task(refresh_with_notification())
                        reset_delivery_count()
                        print(f"[MEMORY] Mental models refresh triggered (interval reached)")

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

        # Record delivery (even failures count) and check if mental model refresh is needed
        should_refresh = record_delivery()
        if should_refresh:
            # Send event that models are refreshing
            await websocket.send_json(event(EventType.MODELS_REFRESHING, {}))

            async def refresh_with_notification():
                try:
                    await refresh_mental_models_async()
                    await websocket.send_json(event(EventType.MODELS_REFRESHED, {"success": True}))
                except Exception as e:
                    print(f"[MEMORY] Mental models refresh failed: {e}")
                    await websocket.send_json(event(EventType.MODELS_REFRESHED, {"success": False, "error": str(e)}))

            asyncio.create_task(refresh_with_notification())
            reset_delivery_count()
            print(f"[MEMORY] Mental models refresh triggered (interval reached)")

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
    mode: str = "recall",  # no_memory, filesystem, recall, reflect, hindsight_mm, hindsight_mm_nowait
    memory_query_mode: str = "inject_once",  # 'inject_once', 'per_step', 'both'
    wait_for_consolidation: bool = True,
    preseed_coverage: float = 0.0,  # 0.0-1.0, fraction of building knowledge to pre-seed
    mm_query_type: str = "recall",  # 'recall' or 'reflect' for MM modes
) -> dict:
    """Run a delivery without WebSocket streaming (fast-forward mode).

    Args:
        building: The building to navigate
        package: The package to deliver
        max_steps: Maximum steps allowed
        model: LLM model to use (None = use default from config)
        hindsight: Hindsight settings (inject, reflect, store, query, mission)
        delivery_id: Unique ID for this delivery (for memory grouping)
        mode: Agent mode - determines tools and memory behavior
        memory_query_mode: When to inject memory - 'inject_once' (start only),
                          'per_step' (every step), or 'both'
        wait_for_consolidation: Whether to wait after storing for consolidation
        preseed_coverage: Fraction of building knowledge to pre-seed into memory (0.0-1.0)
        mm_query_type: Query method for MM modes - 'recall' (raw facts) or 'reflect' (LLM synthesis)

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
    custom_mission = hindsight.get("mission") if hindsight else None

    # For MM modes, override use_reflect based on mm_query_type
    # This allows MM modes to use either recall or reflect for querying
    if mm_query_type == "reflect":
        use_reflect = True

    # Update hindsight defaults if custom bank_id provided
    if custom_bank_id:
        set_bank_id(custom_bank_id, set_background=False)

    # Only set bank mission for mental model modes (hindsight_mm, hindsight_mm_nowait)
    # Recall and reflect modes should NOT have mission (matches eval framework behavior)
    is_mm_mode = mode in ("hindsight_mm", "hindsight_mm_nowait")
    if is_mm_mode and (inject_memories or store_conversations):
        mission_to_set = custom_mission or custom_background or BANK_MISSION
        print(f"[AGENT] Setting bank mission for MM mode: {mission_to_set[:50]}...", flush=True)
        await set_bank_mission_async(custom_bank_id, mission_to_set)

    # Pre-seed building knowledge if coverage > 0
    if preseed_coverage > 0 and inject_memories:
        preseed_facts = generate_preseed_facts(building, coverage=preseed_coverage)
        if preseed_facts:
            await preseed_memory(preseed_facts, delivery_id)
            print(f"[MEMORY] Pre-seeded {len(preseed_facts)} facts ({preseed_coverage*100:.0f}% coverage)")
            # For MM modes with wait_for_consolidation, wait for preseed to consolidate
            # This ensures mental models are built from preseed data before delivery starts
            if is_mm_mode and wait_for_consolidation:
                print(f"[MEMORY] Waiting for preseed consolidation...")
                await wait_for_pending_consolidation_async(timeout=120.0)
                print(f"[MEMORY] Preseed consolidation complete")

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

    # Helper function to fetch memory context
    async def fetch_memory_context(step_context: str = None):
        """Fetch memory context using recall or reflect.

        Args:
            step_context: Optional context for per-step queries (e.g., current position)
        """
        try:
            memory_query = get_hindsight_query(package.recipient_name, custom_query)
            if use_reflect:
                # Pass context to reflect for better situational awareness
                result = await reflect_async(query=memory_query, budget="high", context=step_context)
                if result and hasattr(result, 'text') and result.text:
                    return result.text
            else:
                result = await recall_async(query=memory_query, budget="high")
                if result and len(result) > 0:
                    return format_recall_as_context(result)
        except Exception as e:
            print(f"[MEMORY] Error during {memory_method}: {e}")
        return None

    # Determine if we should inject at start based on mode
    inject_at_start = memory_query_mode in ("inject_once", "both")
    inject_per_step = memory_query_mode in ("per_step", "both")

    # MEMORY INJECTION: Call recall or reflect at start if enabled
    if inject_memories and inject_at_start:
        memory_context = await fetch_memory_context()
        if memory_context:
            system_prompt = f"{base_system_prompt}\n\n# Relevant Memory\n{memory_context}"

    # Set up filesystem mode if needed
    is_filesystem_mode = mode == "filesystem"
    memory_tool_handler = None
    if is_filesystem_mode:
        # Use filesystem-specific system prompt
        system_prompt = """You are a delivery agent navigating a building to deliver packages.

Your goal is to find the target office and deliver the package as efficiently as possible.

IMPORTANT: You have a NOTES FILE to track what you learn!
- Use read_notes() at the START of each delivery to check what you know
- Use write_notes(content) AFTER learning something to save it
- Notes persist between deliveries - use them to build a map!

Strategy:
1. First read_notes() to check if you know where the target office is.
2. If found in notes, navigate directly there.
3. If not in notes, explore systematically.
4. After finding the office, write_notes() to save what you learned!"""
        # Create memory tool handler for filesystem
        notes_key = hindsight.get("bankId") if hindsight else f"filesystem-{delivery_id}"
        memory_tool_handler = MemoryToolHandler(recall_fn=None, notes_key=notes_key)

    # Initial messages with (possibly augmented) system prompt
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": f"Please deliver this package: {package}"}
    ]

    # Get tools based on mode
    include_filesystem = is_filesystem_mode
    include_memory = is_mm_mode and memory_query_mode in ("per_step", "both")
    tool_definitions = get_tool_definitions_with_memory(
        difficulty=building.difficulty,
        include_memory=include_memory,
        include_filesystem=include_filesystem,
    )

    tools = AgentTools(building, agent_state)
    success = False
    actions = []

    # Track total metrics
    total_prompt_tokens = 0
    total_completion_tokens = 0
    total_latency_ms = 0
    delivery_start_time = time.time()

    # Track additional metrics for eval parity
    api_calls = 0
    wrong_turns = 0
    errors = 0  # Non-optimal moves
    path = [agent_state.position_str()]  # Track positions visited
    previous_positions = {agent_state.position_str()}  # Set for backtrack detection

    # Compute optimal steps for this delivery
    optimal_steps = compute_optimal_steps(building, package.recipient_name)
    if optimal_steps < 0:
        optimal_steps = 3  # Fallback default

    # Get target position for error tracking
    target_floor, target_side, target_building_name = 1, Side.FRONT, None
    if package.recipient_name in building.all_employees:
        target_business, _ = building.all_employees[package.recipient_name]
        target_floor = target_business.floor
        target_side = target_business.side
        if building.is_city_grid and hasattr(target_business, 'building_name'):
            target_building_name = target_business.building_name

    try:
        while agent_state.steps_taken < max_steps:
            # Per-step memory injection if enabled
            if inject_memories and inject_per_step and agent_state.steps_taken > 0:
                # Build context from recent conversation (last few tool results)
                recent_context = []
                for msg in messages[-6:]:  # Last 3 exchanges
                    if msg.get("role") == "tool" and msg.get("content"):
                        recent_context.append(msg["content"])
                step_context = f"Delivering to {package.recipient_name}. Current position: {agent_state.position_str()}. Recent actions: {' | '.join(recent_context[-3:]) if recent_context else 'None'}"
                step_memory = await fetch_memory_context(step_context)
                if step_memory:
                    # Update the system message with fresh memory
                    messages[0]["content"] = f"{base_system_prompt}\n\n# Relevant Memory (Step {agent_state.steps_taken})\n{step_memory}"

            # Call LLM
            t0 = time.time()
            response = await completion(
                model=llm_model,
                messages=messages,
                tools=tool_definitions,
                tool_choice="required",
                timeout=30,
            )
            timing = time.time() - t0
            total_latency_ms += timing * 1000
            api_calls += 1  # Track API calls

            # Track token usage from response
            if hasattr(response, 'usage') and response.usage:
                total_prompt_tokens += getattr(response.usage, 'prompt_tokens', 0)
                total_completion_tokens += getattr(response.usage, 'completion_tokens', 0)

            # Track memory count for first action only
            memory_count = 1 if agent_state.steps_taken == 1 and memory_context else 0

            message = response.choices[0].message

            if message.tool_calls:
                tool_results = []

                for tool_call in message.tool_calls:
                    tool_name = tool_call.function.name
                    arguments = json.loads(tool_call.function.arguments) if tool_call.function.arguments else {}

                    # Handle filesystem/memory tools (don't count against step limit)
                    is_memory_tool = tool_name in ("read_notes", "write_notes", "remember")
                    if is_memory_tool and memory_tool_handler:
                        result, handled = await memory_tool_handler.execute(tool_name, arguments)
                        if handled:
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
                                "timing": 0,
                                "memoryCount": 0,
                            })
                            continue  # Skip normal tool execution

                    # Store position before tool execution to detect movement
                    prev_position = agent_state.position_str()

                    # Calculate remaining steps before tool execution (for error tracking)
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

                    result = execute_tool(tools, tool_name, arguments)

                    # Track path and detect wrong turns (backtracking)
                    new_position = agent_state.position_str()
                    if new_position != prev_position:
                        # Agent moved - track the path
                        path.append(new_position)
                        if new_position in previous_positions:
                            # Backtracking to a previously visited position
                            wrong_turns += 1
                        previous_positions.add(new_position)

                        # Error tracking: calculate remaining steps after move
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
                        # If remaining steps didn't decrease, it was a non-optimal move
                        if remaining_after >= remaining_before:
                            errors += 1

                    # Detect failed moves (trying to go somewhere invalid)
                    if tool_name in ("go_up", "go_down", "go_to_front", "go_to_back", "move_north", "move_south", "move_east", "move_west"):
                        if "Cannot" in result or "can't" in result.lower() or "already" in result.lower():
                            wrong_turns += 1

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
                        # For MM modes with wait_for_consolidation, wait for pending_consolidation to reach 0
                        # This matches eval framework behavior: wait after EVERY retain
                        if is_mm_mode and wait_for_consolidation:
                            print(f"[MEMORY] Waiting for consolidation after retain...")
                            await wait_for_pending_consolidation_async(timeout=120.0)
                            print(f"[MEMORY] Consolidation complete")
                    # Record delivery and check if mental model refresh is needed
                    should_refresh = record_delivery()
                    if should_refresh:
                        if wait_for_consolidation:
                            await refresh_mental_models_async()  # Wait for completion
                        else:
                            asyncio.create_task(refresh_mental_models_async())  # Fire-and-forget
                        reset_delivery_count()
                    break

            else:
                # No tool calls - nudge to use tools
                messages.append({"role": "assistant", "content": message.content})
                messages.append({"role": "user", "content": "Use the available tools to complete the delivery."})

        # If we exit the loop without success, store the failed delivery
        if not success:
            if store_conversations:
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
                # For MM modes with wait_for_consolidation, wait for pending_consolidation to reach 0
                if is_mm_mode and wait_for_consolidation:
                    print(f"[MEMORY] Waiting for consolidation after retain (failed delivery)...")
                    await wait_for_pending_consolidation_async(timeout=120.0)
                    print(f"[MEMORY] Consolidation complete")
            # Record delivery (even failures count) and check if mental model refresh is needed
            should_refresh = record_delivery()
            if should_refresh:
                if wait_for_consolidation:
                    await refresh_mental_models_async()  # Wait for completion
                else:
                    asyncio.create_task(refresh_mental_models_async())  # Fire-and-forget
                reset_delivery_count()

        # Compute path efficiency
        path_efficiency = compute_path_efficiency(agent_state.steps_taken, optimal_steps)

        # Get mental model stats
        mental_model_count = 0
        mental_model_observations = 0
        building_coverage = 0.0
        try:
            bank_stats = await get_bank_stats_async()
            mental_model_count = bank_stats.get("total_mental_models", 0)
            # Get observation count from mental models if available
            mental_models = await get_mental_models_async()
            if mental_models:
                mental_model_observations = sum(
                    len(mm.get("observations", [])) for mm in mental_models
                )
                # Estimate building coverage based on mental models
                # (number of unique locations/entities mentioned)
                building_coverage = min(1.0, mental_model_count / 10.0)  # Rough estimate
        except Exception as e:
            print(f"[MEMORY] Error getting mental model stats: {e}")

        return {
            "success": success,
            "steps": agent_state.steps_taken,
            "optimalSteps": optimal_steps,
            "pathEfficiency": path_efficiency,
            "actions": actions,
            "floor": agent_state.floor,
            "side": agent_state.side.value,
            "memoryInjected": memory_context is not None,
            "tokens": {
                "prompt": total_prompt_tokens,
                "completion": total_completion_tokens,
                "total": total_prompt_tokens + total_completion_tokens,
            },
            "latencyMs": total_latency_ms,
            "totalTimeMs": (time.time() - delivery_start_time) * 1000,
            # New fields for eval parity
            "apiCalls": api_calls,
            "wrongTurns": wrong_turns,
            "errors": errors,
            "errorRate": errors / max(agent_state.steps_taken, 1),  # Non-optimal moves / total moves
            "path": path,
            "mentalModelCount": mental_model_count,
            "mentalModelObservations": mental_model_observations,
            "buildingCoverage": building_coverage,
        }

    except Exception as e:
        import traceback
        return {
            "success": False,
            "steps": agent_state.steps_taken,
            "optimalSteps": optimal_steps,
            "pathEfficiency": 0.0,
            "actions": actions,
            "error": str(e),
            "traceback": traceback.format_exc(),
            "tokens": {
                "prompt": total_prompt_tokens,
                "completion": total_completion_tokens,
                "total": total_prompt_tokens + total_completion_tokens,
            },
            "latencyMs": total_latency_ms,
            "totalTimeMs": (time.time() - delivery_start_time) * 1000,
            # New fields for eval parity (with defaults for errors)
            "apiCalls": api_calls,
            "wrongTurns": wrong_turns,
            "errors": errors,
            "errorRate": errors / max(agent_state.steps_taken, 1),
            "path": path,
            "mentalModelCount": 0,
            "mentalModelObservations": 0,
            "buildingCoverage": 0.0,
        }
