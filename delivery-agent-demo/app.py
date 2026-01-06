"""
Delivery Agent Demo - Streamlit App

A retro-style sprite-based demo showcasing how AI agents learn
to navigate using Hindsight memory.
"""

import streamlit as st
import streamlit.components.v1 as components
import time
import json
import os
import uuid
import random
import traceback
import threading
import queue
import pandas as pd
from dotenv import load_dotenv

# Queue storage using st.cache_resource to survive Streamlit reruns
# Regular module-level dicts get reset when Streamlit reimports the module
@st.cache_resource
def _get_queue_storage() -> dict:
    """Get the persistent queue storage dict. Survives Streamlit reruns."""
    return {}


def _get_or_create_queue(session_id: str) -> queue.Queue:
    """Get the queue for this session, creating if needed."""
    storage = _get_queue_storage()
    if session_id not in storage:
        storage[session_id] = queue.Queue()
    return storage[session_id]


def _clear_queue(session_id: str):
    """Clear and remove the queue for this session."""
    storage = _get_queue_storage()
    if session_id in storage:
        # Drain any remaining items
        q = storage[session_id]
        while True:
            try:
                q.get_nowait()
            except queue.Empty:
                break
        del storage[session_id]


import hindsight_litellm
from building import get_building, Side, reset_building, Package
from agent import DeliveryAgent, ActionEvent
from agent_tools import AgentTools, TOOL_DEFINITIONS, execute_tool
from game_renderer import generate_game_html
import memory

# Load environment variables
load_dotenv()

# Page config
st.set_page_config(
    page_title="Delivery Agent Demo",
    page_icon="📦",
    layout="wide"
)


def _format_messages_for_retain(messages: list) -> str:
    """Format conversation messages for explicit retain to Hindsight.

    This is used to store the final conversation when a delivery completes,
    since the automatic LLM callback won't capture the final tool results.
    """
    items = []
    for msg in messages:
        role = msg.get("role", "").upper()
        content = msg.get("content", "")
        tool_calls = msg.get("tool_calls", [])

        # Skip system messages
        if role == "SYSTEM":
            continue

        # Handle tool results
        if role == "TOOL":
            items.append(f"TOOL_RESULT: {content}")
            continue

        # Handle assistant with tool calls
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

        # Regular messages
        if content:
            label = "USER" if role == "USER" else "ASSISTANT"
            items.append(f"{label}: {content}")

    return "\n\n".join(items)


def _run_delivery_in_background(
    action_queue: queue.Queue,
    building,
    package: Package,
    model: str,
    max_steps: int = None,
):
    # DEBUG: Log at the very start of the function
    with open("/tmp/demo.log", "a") as f:
        f.write(f"\n\n*** BACKGROUND THREAD STARTED ***\n")
        f.write(f"Package: {package}\n")
        f.write(f"Model: {model}\n")
        f.write(f"Max steps: {max_steps}\n")
    """Run a delivery in a background thread, pushing actions to queue.

    This allows the UI to animate actions as they happen while the agent
    runs at full speed without waiting for animations.

    Args:
        action_queue: Thread-safe queue to push actions to
        building: The building to navigate
        package: The package to deliver
        model: LLM model to use
        max_steps: Maximum steps (None = no limit)

    The queue receives dicts with keys:
        - type: "action", "success", "error", "step_limit", "complete"
        - For "action": tool_name, result, floor, side, timing
        - For "success"/"error"/"step_limit": message
        - For "complete": success (bool), steps (int), messages (list)
    """
    from building import AgentState

    agent_state = AgentState()
    agent_state.current_package = package

    messages = [
        {"role": "system", "content": "You are a delivery agent. Use the tools provided to get it delivered."},
        {"role": "user", "content": f"Please deliver this package: {package}"}
    ]

    tools = AgentTools(building, agent_state)
    success = False
    error_msg = None

    try:
        while max_steps is None or agent_state.steps_taken < max_steps:
            t0 = time.time()

            # DEBUG: Log FULL prompt being sent to LLM (no truncation)
            with open("/tmp/demo.log", "a") as f:
                f.write(f"\n{'='*80}\n")
                f.write(f"[DEBUG] Step {agent_state.steps_taken + 1} - FULL PROMPT TO LLM:\n")
                f.write(f"[DEBUG] Model: {model}\n")
                f.write(f"{'='*80}\n")
                for i, msg in enumerate(messages):
                    role = msg.get("role", "?")
                    content = msg.get("content", "") or "(none)"
                    tool_calls = msg.get("tool_calls", [])
                    f.write(f"\n--- MESSAGE [{i}] role={role} ---\n")
                    if content:
                        f.write(f"{content}\n")
                    if tool_calls:
                        f.write(f"tool_calls: {json.dumps([{'name': tc.get('function', {}).get('name', '?') if isinstance(tc, dict) else tc.function.name, 'args': tc.get('function', {}).get('arguments', '') if isinstance(tc, dict) else tc.function.arguments} for tc in tool_calls], indent=2)}\n")
                f.write(f"\n--- TOOLS ---\n")
                f.write(f"{json.dumps([t['function']['name'] for t in TOOL_DEFINITIONS])}\n")
                f.write(f"{'='*80}\n")

            response = memory.completion(
                model=model,
                messages=messages,
                tools=TOOL_DEFINITIONS,
                tool_choice="required",
                timeout=30
            )

            t1 = time.time()
            llm_duration = t1 - t0

            message = response.choices[0].message

            # DEBUG: Log what we received from the LLM (write to file)
            with open("/tmp/demo.log", "a") as f:
                f.write(f"[DEBUG] Response received in {llm_duration:.2f}s:\n")
                if message.tool_calls:
                    for tc in message.tool_calls:
                        f.write(f"[DEBUG]   Tool call: {tc.function.name}({tc.function.arguments})\n")
                if message.content:
                    f.write(f"[DEBUG]   Content: {message.content[:200]}\n")
                f.write(f"{'='*60}\n\n")

            # Push LLM call info to queue for display (include tools)
            llm_call_item = {
                "type": "llm_call",
                "step": agent_state.steps_taken + 1,
                "messages": json.dumps({
                    "messages": [dict(m) if isinstance(m, dict) else {"role": m.get("role", ""), "content": m.get("content", "")} for m in messages],
                    "tools": TOOL_DEFINITIONS,
                }),
                "response": json.dumps({"content": message.content, "tool_calls": [{"name": tc.function.name, "arguments": tc.function.arguments} for tc in (message.tool_calls or [])]}),
            }
            action_queue.put(llm_call_item)
            # DEBUG: Log that we pushed llm_call to queue
            with open("/tmp/demo.log", "a") as f:
                f.write(f"[QUEUE-PUSH] Pushed llm_call for step {agent_state.steps_taken + 1} to queue\n")

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

                    # Push action to queue for UI animation
                    action_queue.put({
                        "type": "action",
                        "tool_name": tool_name,
                        "result": result,
                        "floor": agent_state.floor,
                        "side": agent_state.side.value,
                        "timing": llm_duration,
                    })

                    if "SUCCESS!" in result:
                        success = True
                        action_queue.put({
                            "type": "success",
                            "message": result,
                        })
                        break

                # Serialize tool_calls to dicts for JSON compatibility
                serialized_tool_calls = [
                    {"id": tc.id, "type": "function", "function": {"name": tc.function.name, "arguments": tc.function.arguments}}
                    for tc in message.tool_calls
                ] if message.tool_calls else []
                messages.append({"role": "assistant", "content": message.content, "tool_calls": serialized_tool_calls})
                messages.extend(tool_results)

                if success:
                    # Store to memory on success
                    final_convo = _format_messages_for_retain(messages)
                    memory.retain(final_convo)
                    break

                # Check step limit
                if max_steps is not None and agent_state.steps_taken >= max_steps:
                    action_queue.put({
                        "type": "step_limit",
                        "message": f"Exceeded {max_steps} step limit",
                    })
                    break
            else:
                # No tool calls - nudge to use tools
                if message.content:
                    action_queue.put({
                        "type": "action",
                        "tool_name": "💬 response",
                        "result": message.content,
                        "floor": agent_state.floor,
                        "side": agent_state.side.value,
                        "timing": llm_duration,
                    })
                messages.append({"role": "assistant", "content": message.content})
                messages.append({"role": "user", "content": "Use the available tools to complete the delivery."})

    except Exception as e:
        error_msg = str(e)
        action_queue.put({
            "type": "error",
            "message": error_msg,
            "traceback": traceback.format_exc(),
        })

    # Signal completion
    action_queue.put({
        "type": "complete",
        "success": success,
        "steps": agent_state.steps_taken,
        "messages": messages,
        "error": error_msg,
    })


def _run_single_delivery_ff(building, include_business: bool, delivery_counter: int, max_steps: int = None):
    """Run a single delivery to completion without Streamlit reruns.

    This is optimized for fast-forward mode - no UI updates, minimal overhead.

    Args:
        building: The building to navigate
        include_business: Whether to include business name on packages
        delivery_counter: Counter for document_id
        max_steps: Maximum steps per delivery (None = no limit)

    Returns:
        dict with keys: success, steps, llm_times, package_str, error (if any)
    """
    package = building.generate_package(include_business=include_business)
    memory.set_document_id(f"delivery-{delivery_counter}")

    agent = DeliveryAgent(building=building)
    agent.state.current_package = package

    messages = [
        {"role": "system", "content": agent._build_system_prompt(package)},
        {"role": "user", "content": f"Please deliver this package: {package}"}
    ]

    tools = AgentTools(agent.building, agent.state, on_action=agent._record_action)
    llm_times = []
    success = False
    error = None

    while max_steps is None or agent.state.steps_taken < max_steps:
        try:
            t0 = time.time()
            response = memory.completion(
                model=agent.model,
                messages=messages,
                tools=TOOL_DEFINITIONS,
                tool_choice="required",
                timeout=30
            )
            t1 = time.time()
            llm_times.append(t1 - t0)

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

                    # Check for success
                    if "SUCCESS!" in result:
                        success = True
                        break

                # Update messages (serialize tool_calls for JSON compatibility)
                serialized_tool_calls = [
                    {"id": tc.id, "type": "function", "function": {"name": tc.function.name, "arguments": tc.function.arguments}}
                    for tc in message.tool_calls
                ] if message.tool_calls else []
                messages.append({"role": "assistant", "content": message.content, "tool_calls": serialized_tool_calls})
                messages.extend(tool_results)

                if success:
                    # Store final conversation
                    final_convo = _format_messages_for_retain(messages)
                    memory.retain(final_convo)
                    break
            else:
                # No tool calls - nudge to use tools
                messages.append({"role": "assistant", "content": message.content})
                messages.append({"role": "user", "content": "Use the available tools to complete the delivery."})

        except Exception as e:
            error = str(e)
            break

    # Check for storage errors
    storage_errors = memory.get_pending_storage_errors()
    storage_error_msgs = []
    if storage_errors:
        for err in storage_errors:
            print(f"[STORAGE ERROR] {err}", flush=True)
            storage_error_msgs.append(str(err))

    # Determine if we hit the step limit
    hit_step_limit = max_steps is not None and agent.state.steps_taken >= max_steps and not success

    return {
        "success": success,
        "steps": agent.state.steps_taken,
        "llm_times": llm_times,
        "package_str": str(package),
        "error": error,
        "storage_errors": storage_error_msgs,
        "hit_step_limit": hit_step_limit,
    }


@st.dialog("Select Recipient", width="large")
def recipient_dialog(building, include_business):
    """Dialog to select a recipient from the building directory."""

    st.markdown("**Select a recipient for delivery:**")

    # Build list of all employees grouped by floor
    all_options = []
    employee_map = {}  # Maps display string to (emp_name, business_name)

    floors_data = building.get_floor_display()

    for floor_data in floors_data:
        floor_num = floor_data["floor"]
        front_biz = floor_data["front"]
        back_biz = floor_data["back"]

        if front_biz:
            for emp in front_biz.employees:
                label = f"F{floor_num} | {front_biz.name} | {emp.name}"
                all_options.append(label)
                employee_map[label] = (emp.name, front_biz.name)

        if back_biz:
            for emp in back_biz.employees:
                label = f"F{floor_num} | {back_biz.name} | {emp.name}"
                all_options.append(label)
                employee_map[label] = (emp.name, back_biz.name)

    # Selectbox for choosing recipient
    selected = st.selectbox(
        "Choose recipient:",
        options=all_options,
        index=None,
        placeholder="Select a person..."
    )

    # Confirm button
    if st.button("✅ Confirm & Start Delivery", use_container_width=True, type="primary", disabled=selected is None):
        if selected:
            emp_name, business_name = employee_map[selected]
            st.session_state.selected_recipient = emp_name
            st.session_state.selected_business = business_name if include_business else None
            st.session_state.start_delivery_now = True
            st.session_state.show_recipient_dialog = False
            st.rerun()


def main():
    # Title
    st.markdown("""
    <h1 style="text-align: center; color: #00ff00; font-family: monospace;">
        📦 DELIVERY AGENT DEMO 📦
    </h1>
    <p style="text-align: center; color: #888888;">
        Watch an AI agent learn to navigate a building using Hindsight memory
    </p>
    """, unsafe_allow_html=True)

    # Difficulty selector - single click switches and resets
    if "difficulty" not in st.session_state:
        st.session_state.difficulty = "easy"

    difficulty_options = {
        "easy": "🟢 Easy - Simple Office",
        "medium": "🟡 Medium - Industrial Building",
        "hard": "🔴 Hard - Space Station"
    }

    col_diff, col_desc = st.columns([1, 2])
    with col_diff:
        new_difficulty = st.radio(
            "Difficulty",
            options=list(difficulty_options.keys()),
            format_func=lambda x: difficulty_options[x],
            index=list(difficulty_options.keys()).index(st.session_state.difficulty),
            horizontal=True,
            label_visibility="collapsed"
        )

    # If difficulty changed, reset everything with new bank ID
    if new_difficulty != st.session_state.difficulty:
        st.session_state.difficulty = new_difficulty
        # Reset all state for fresh start
        st.session_state.current_actions = []
        st.session_state.action_queue = []
        st.session_state.displayed_actions = []
        st.session_state.last_display_time = 0
        st.session_state.delivery_complete_pending = False
        st.session_state.pending_delivery = None
        st.session_state.llm_messages = []
        st.session_state.stored_memories = []
        st.session_state.deliveries_completed = 0
        st.session_state.delivery_counter = 0
        st.session_state.loop_remaining = 0
        st.session_state.total_steps = 0
        st.session_state.delivery_history = []
        st.session_state.agent_floor = 1
        st.session_state.agent_side = "front"
        st.session_state.prev_agent_floor = 1
        st.session_state.prev_agent_side = "front"
        st.session_state.has_package = False
        st.session_state.current_action = None
        # New bank ID for this difficulty (memories don't overlap)
        st.session_state.session_id = f"{new_difficulty}-{uuid.uuid4().hex[:6]}"
        bank_id = memory.configure_memory(session_id=st.session_state.session_id)
        st.session_state.bank_id = bank_id
        st.rerun()

    with col_desc:
        desc_map = {
            "easy": "Left/right offices, single elevator",
            "medium": "Ladders skip floors (1→3, 3→5)",
            "hard": "Gravity lifts, teleporters, multiple routes"
        }
        st.caption(desc_map[st.session_state.difficulty])

    st.divider()

    # Initialize session state
    if "session_id" not in st.session_state:
        st.session_state.session_id = uuid.uuid4().hex[:8]
        # Configure memory with unique session ID
        bank_id = memory.configure_memory(session_id=st.session_state.session_id)
        st.session_state.bank_id = bank_id

    if "building" not in st.session_state:
        st.session_state.building = get_building()

    if "llm_messages" not in st.session_state:
        st.session_state.llm_messages = []  # Track LLM prompt/response for display

    if "stored_memories" not in st.session_state:
        st.session_state.stored_memories = []  # Track memories stored this session

    if "deliveries_completed" not in st.session_state:
        st.session_state.deliveries_completed = 0

    if "delivery_counter" not in st.session_state:
        st.session_state.delivery_counter = 0  # Increments at start of each delivery

    if "total_steps" not in st.session_state:
        st.session_state.total_steps = 0

    if "delivery_history" not in st.session_state:
        st.session_state.delivery_history = []

    if "current_actions" not in st.session_state:
        st.session_state.current_actions = []

    # Queue-based animation system
    if "action_queue" not in st.session_state:
        st.session_state.action_queue = []  # Actions waiting to be displayed

    if "displayed_actions" not in st.session_state:
        st.session_state.displayed_actions = []  # Actions already shown

    if "last_display_time" not in st.session_state:
        st.session_state.last_display_time = 0  # Timestamp of last displayed action

    if "animation_duration" not in st.session_state:
        st.session_state.animation_duration = 1.5  # Seconds per animation

    if "delivery_complete_pending" not in st.session_state:
        st.session_state.delivery_complete_pending = False  # Delivery done but animations pending

    if "agent_floor" not in st.session_state:
        st.session_state.agent_floor = 1

    if "agent_side" not in st.session_state:
        st.session_state.agent_side = "front"

    if "prev_agent_floor" not in st.session_state:
        st.session_state.prev_agent_floor = 1

    if "prev_agent_side" not in st.session_state:
        st.session_state.prev_agent_side = "front"

    if "has_package" not in st.session_state:
        st.session_state.has_package = False

    if "is_running" not in st.session_state:
        st.session_state.is_running = False

    if "last_package_info" not in st.session_state:
        st.session_state.last_package_info = None

    if "step_by_step" not in st.session_state:
        st.session_state.step_by_step = False

    if "pending_delivery" not in st.session_state:
        st.session_state.pending_delivery = None

    if "delivery_generator" not in st.session_state:
        st.session_state.delivery_generator = None

    if "current_result" not in st.session_state:
        st.session_state.current_result = None

    if "current_action" not in st.session_state:
        st.session_state.current_action = None

    if "show_recipient_dialog" not in st.session_state:
        st.session_state.show_recipient_dialog = False

    if "selected_recipient" not in st.session_state:
        st.session_state.selected_recipient = None

    if "selected_business" not in st.session_state:
        st.session_state.selected_business = None

    if "start_delivery_now" not in st.session_state:
        st.session_state.start_delivery_now = False

    if "include_business" not in st.session_state:
        st.session_state.include_business = False

    if "max_steps_per_delivery" not in st.session_state:
        st.session_state.max_steps_per_delivery = None  # None = no limit

    if "ff_errors" not in st.session_state:
        st.session_state.ff_errors = []  # Track errors during FF mode

    # Background thread state for UI mode streaming
    # Note: The actual queue.Queue object is stored in _GLOBAL_QUEUES, not session state
    # This is because queue.Queue objects don't survive Streamlit hot-reloads
    if "bg_queue_active" not in st.session_state:
        st.session_state.bg_queue_active = False  # Whether there's an active queue for this session

    if "bg_delivery_running" not in st.session_state:
        st.session_state.bg_delivery_running = False

    if "bg_delivery_complete_info" not in st.session_state:
        st.session_state.bg_delivery_complete_info = None  # Completion info from thread

    building = st.session_state.building

    # Auto-start delivery if recipient was selected (check this FIRST)
    if st.session_state.start_delivery_now and st.session_state.selected_recipient:
        st.session_state.start_delivery_now = False
        st.session_state.show_recipient_dialog = False  # Ensure dialog is closed
        st.session_state.current_actions = []
        st.session_state.action_queue = []  # Reset action queue
        st.session_state.displayed_actions = []
        st.session_state.llm_messages = []
        st.session_state.has_package = True
        st.session_state.agent_floor = 1
        st.session_state.agent_side = "front"
        st.session_state.prev_agent_floor = 1
        st.session_state.prev_agent_side = "front"
        st.session_state.current_action = None
        st.session_state.delivery_start_time = time.time()
        st.session_state.delivery_complete_pending = False
        st.session_state.bg_delivery_complete_info = None  # Clear any previous completion
        # Clear old queue before creating new one
        _clear_queue(st.session_state.session_id)
        st.session_state.bg_queue_active = False

        # Create package for selected recipient
        recipient_name = st.session_state.selected_recipient
        business_info = building.find_employee(recipient_name)
        business_name = business_info[0].name if business_info and st.session_state.include_business else None
        package = Package(
            id=f"{random.randint(1000, 9999)}",
            recipient_name=recipient_name,
            business_name=business_name
        )
        st.session_state.last_package_info = str(package)

        # Increment delivery counter and set document_id for memory grouping
        st.session_state.delivery_counter += 1
        memory.set_document_id(f"delivery-{st.session_state.delivery_counter}")

        # Get model from a temp agent
        model = os.environ.get("LLM_MODEL", "openai/gpt-4o-mini")

        # Start background thread for delivery using global queue storage
        action_q = _get_or_create_queue(st.session_state.session_id)
        st.session_state.bg_queue_active = True
        st.session_state.bg_delivery_running = True
        st.session_state.bg_delivery_complete_info = None

        # DEBUG: Log queue creation
        with open("/tmp/demo.log", "a") as f:
            f.write(f"\n=== STARTING THREAD from Select Recipient ===\n")
            f.write(f"[START] Session ID: {st.session_state.session_id}\n")
            f.write(f"[START] Queue from global: {action_q}, id={id(action_q)}\n")
            f.write(f"[START] bg_queue_active: {st.session_state.bg_queue_active}\n")

        thread = threading.Thread(
            target=_run_delivery_in_background,
            args=(action_q, building, package, model, st.session_state.max_steps_per_delivery),
            daemon=True
        )
        thread.start()

        # Clear selected recipient
        st.session_state.selected_recipient = None
        st.session_state.selected_business = None
        st.rerun()

    # Show recipient dialog if triggered (after checking for delivery start)
    if st.session_state.show_recipient_dialog:
        recipient_dialog(building, st.session_state.include_business)

    # Initialize timing state
    if "loop_remaining" not in st.session_state:
        st.session_state.loop_remaining = 0
    if "timing_llm_calls" not in st.session_state:
        st.session_state.timing_llm_calls = []
    if "timing_deliveries" not in st.session_state:
        st.session_state.timing_deliveries = []
    if "timing_loop_start" not in st.session_state:
        st.session_state.timing_loop_start = None
    if "delivery_start_time" not in st.session_state:
        st.session_state.delivery_start_time = None

    # Mode tabs at top
    ui_tab, ff_tab = st.tabs(["🎮 UI Mode", "⚡ Fast-Forward Mode"])

    with ff_tab:
        # Fast-forward mode - minimal UI for benchmarking
        st.markdown("### ⚡ Fast-Forward Mode")
        st.caption("Maximum speed - no animations, minimal UI")

        col_ff_controls, col_ff_stats = st.columns([1, 1])

        with col_ff_controls:
            loop_count = st.slider("Deliveries to run", min_value=1, max_value=100, value=10, key="ff_loop_count")

            # Max steps per delivery - number input, empty = no limit
            max_steps_input = st.number_input(
                "Max steps per delivery",
                min_value=1,
                max_value=500,
                value=None,
                placeholder="No limit",
                help="Leave empty for no limit. Delivery fails if it exceeds this many steps.",
                key="ff_max_steps"
            )
            st.session_state.max_steps_per_delivery = max_steps_input

            is_running = st.session_state.loop_remaining > 0
            if st.button("🚀 Run Loop", use_container_width=True, disabled=is_running, key="ff_loop_btn"):
                st.session_state.fast_forward = True
                st.session_state.loop_remaining = loop_count
                st.session_state.timing_loop_start = time.time()
                st.session_state.timing_llm_calls = []
                st.session_state.timing_deliveries = []
                st.session_state.ff_errors = []  # Clear errors for new run

            if st.button("📦 Single Delivery", use_container_width=True, disabled=is_running, key="ff_single_btn"):
                st.session_state.fast_forward = True
                st.session_state.loop_remaining = 1
                st.session_state.ff_errors = []

            if st.button("🛑 Stop", use_container_width=True, disabled=not is_running, key="ff_stop_btn"):
                st.session_state.loop_remaining = 0
                st.session_state.fast_forward = False

        with col_ff_stats:
            st.markdown("#### ⏱️ Benchmarks")
            llm_times = st.session_state.timing_llm_calls
            delivery_times = st.session_state.timing_deliveries

            col_a, col_b = st.columns(2)
            with col_a:
                st.metric("Deliveries", len(delivery_times))
                if llm_times:
                    st.metric("Avg LLM", f"{sum(llm_times)/len(llm_times):.2f}s")
            with col_b:
                st.metric("LLM Calls", len(llm_times))
                if delivery_times:
                    st.metric("Avg Delivery", f"{sum(delivery_times)/len(delivery_times):.1f}s")

            if st.session_state.timing_loop_start and delivery_times:
                total = time.time() - st.session_state.timing_loop_start
                st.metric("Total Time", f"{total:.1f}s")

        # Show errors from FF runs
        if st.session_state.ff_errors:
            with st.expander(f"⚠️ Errors ({len(st.session_state.ff_errors)})", expanded=True):
                for err in st.session_state.ff_errors[-10:]:  # Show last 10
                    st.error(err)

        # Learning curve in fast-forward
        if len(st.session_state.delivery_history) > 1:
            st.markdown("### 📈 Learning Curve")
            steps_history = [d["steps"] for d in st.session_state.delivery_history]
            df = pd.DataFrame({"Steps": steps_history}, index=range(1, len(steps_history) + 1))
            df.index.name = "Delivery"
            st.line_chart(df, use_container_width=True)

        # Fast-forward delivery loop - uses st.empty() for real-time updates
        if st.session_state.get("fast_forward", False) and st.session_state.loop_remaining > 0:
            # Create placeholders for real-time updates
            progress_placeholder = st.empty()
            status_placeholder = st.empty()

            total_to_run = st.session_state.loop_remaining
            completed_this_run = 0

            # Run ALL deliveries in a single loop without st.rerun()
            while st.session_state.loop_remaining > 0:
                st.session_state.loop_remaining -= 1
                st.session_state.delivery_counter += 1
                completed_this_run += 1

                # Update progress in real-time
                progress = completed_this_run / total_to_run
                progress_placeholder.progress(progress, text=f"Delivery {completed_this_run}/{total_to_run}")
                status_placeholder.info(f"🚀 Running delivery {completed_this_run}...")

                delivery_start = time.time()

                # Run entire delivery
                result = _run_single_delivery_ff(
                    building=building,
                    include_business=st.session_state.include_business,
                    delivery_counter=st.session_state.delivery_counter,
                    max_steps=st.session_state.max_steps_per_delivery,
                )

                delivery_time = time.time() - delivery_start

                # Update stats
                st.session_state.timing_llm_calls.extend(result["llm_times"])
                st.session_state.timing_deliveries.append(delivery_time)
                st.session_state.total_steps += result["steps"]
                if result["success"]:
                    st.session_state.deliveries_completed += 1
                st.session_state.delivery_history.append({
                    "package": result["package_str"],
                    "success": result["success"],
                    "steps": result["steps"],
                })
                st.session_state.last_package_info = result["package_str"]

                # Track errors for UI display
                if result["error"]:
                    err_msg = f"Delivery {st.session_state.delivery_counter}: {result['error']}"
                    st.session_state.ff_errors.append(err_msg)
                    print(f"[FF ERROR] {err_msg}", flush=True)

                if result["storage_errors"]:
                    for se in result["storage_errors"]:
                        err_msg = f"Delivery {st.session_state.delivery_counter} storage: {se}"
                        st.session_state.ff_errors.append(err_msg)

                if result["hit_step_limit"]:
                    err_msg = f"Delivery {st.session_state.delivery_counter}: Hit step limit ({st.session_state.max_steps_per_delivery} steps)"
                    st.session_state.ff_errors.append(err_msg)
                    print(f"[FF STEP LIMIT] {err_msg}", flush=True)

            # Clear placeholders and show completion
            progress_placeholder.empty()
            status_placeholder.success(f"✅ Completed {completed_this_run} deliveries!")

            # Clear fast_forward flag and rerun once to update all stats
            st.session_state.fast_forward = False
            time.sleep(0.5)  # Brief pause to show success message
            st.rerun()

    with ui_tab:
        # Reset fast_forward when viewing UI tab
        st.session_state.fast_forward = False

        # Poll background queue BEFORE rendering columns so both see updated state
        # Get queue from cached storage (survives hot-reloads)
        bg_queue = _get_queue_storage().get(st.session_state.session_id)

        # SAFETY: If running but queue doesn't exist, reset the running flag
        # This can happen after cache clears or hot-reloads
        if st.session_state.bg_delivery_running and bg_queue is None and not st.session_state.action_queue:
            st.session_state.bg_delivery_running = False
            st.session_state.bg_queue_active = False

        # DEBUG: Log queue polling status with more detail (only if something interesting)
        if st.session_state.bg_delivery_running or st.session_state.action_queue or st.session_state.delivery_complete_pending:
            with open("/tmp/demo.log", "a") as f:
                f.write(f"[POLL] session_id={st.session_state.session_id}, bg_queue={bg_queue is not None}, bg_queue_active={st.session_state.bg_queue_active}, running={st.session_state.bg_delivery_running}, action_queue_len={len(st.session_state.action_queue)}, pending={st.session_state.delivery_complete_pending}\n")

        if bg_queue is not None and (st.session_state.bg_delivery_running or st.session_state.action_queue or st.session_state.delivery_complete_pending):
            # Drain all available items from the thread-safe queue
            items_polled = 0
            while True:
                try:
                    item = bg_queue.get_nowait()
                    items_polled += 1
                    item_type = item.get("type")
                    # DEBUG: Log every item polled
                    with open("/tmp/demo.log", "a") as f:
                        f.write(f"[POLL] Got item #{items_polled}: type={item_type}\n")

                    if item_type == "action":
                        st.session_state.action_queue.append({
                            "tool_name": item["tool_name"],
                            "result": item["result"],
                            "floor": item["floor"],
                            "side": item["side"],
                            "timing": item["timing"],
                        })
                    elif item_type == "success":
                        st.session_state.delivery_complete_pending = True
                    elif item_type == "error":
                        st.session_state.action_queue.append({
                            "tool_name": "❌ error",
                            "result": item["message"],
                            "floor": st.session_state.agent_floor,
                            "side": st.session_state.agent_side,
                            "timing": 0,
                        })
                        st.session_state.delivery_complete_pending = True
                    elif item_type == "step_limit":
                        st.session_state.action_queue.append({
                            "tool_name": "⚠️ step_limit",
                            "result": item["message"],
                            "floor": st.session_state.agent_floor,
                            "side": st.session_state.agent_side,
                            "timing": 0,
                        })
                        st.session_state.delivery_complete_pending = True
                    elif item_type == "llm_call":
                        llm_entry = {
                            "step": item["step"],
                            "raw_prompt": item["messages"],
                            "raw_response": item["response"],
                        }
                        st.session_state.llm_messages.append(llm_entry)
                        # DEBUG: Log that we received an llm_call with details
                        with open("/tmp/demo.log", "a") as f:
                            f.write(f"[POLL] *** ADDED llm_call for step {item['step']}, total llm_messages now: {len(st.session_state.llm_messages)} ***\n")
                            f.write(f"[POLL] llm_messages IDs: {[id(m) for m in st.session_state.llm_messages]}\n")
                    elif item_type == "complete":
                        st.session_state.bg_delivery_complete_info = item
                        st.session_state.bg_delivery_running = False
                        st.session_state.total_steps += item["steps"]
                        if item["success"]:
                            st.session_state.deliveries_completed += 1
                        st.session_state.delivery_history.append({
                            "package": st.session_state.last_package_info,
                            "success": item["success"],
                            "steps": item["steps"],
                        })
                except queue.Empty:
                    # DEBUG: Log how many items were polled
                    with open("/tmp/demo.log", "a") as f:
                        f.write(f"[POLL] Queue empty after {items_polled} items, llm_messages={len(st.session_state.llm_messages)}\n")
                    break  # Queue empty
                except Exception as e:
                    # Log unexpected errors instead of silently breaking
                    with open("/tmp/demo.log", "a") as f:
                        f.write(f"[ERROR] Queue polling error: {e}\n")
                        f.write(f"{traceback.format_exc()}\n")
                    break

        # Process animation queue - advance one action per frame
        current_time = time.time()
        time_since_last = current_time - st.session_state.last_display_time
        should_advance = time_since_last >= st.session_state.animation_duration

        if st.session_state.step_by_step and st.session_state.action_queue:
            should_advance = False  # Will be set by Next Step button

        if st.session_state.action_queue and should_advance and not st.session_state.step_by_step:
            next_action = st.session_state.action_queue.pop(0)
            st.session_state.displayed_actions.append(next_action)
            st.session_state.last_display_time = current_time

            if next_action.get("floor") is not None:
                st.session_state.prev_agent_floor = st.session_state.agent_floor
                st.session_state.prev_agent_side = st.session_state.agent_side
                st.session_state.agent_floor = next_action["floor"]
                st.session_state.agent_side = next_action["side"]
                st.session_state.current_action = next_action["tool_name"]

        # Check if delivery complete and all animations done
        if st.session_state.delivery_complete_pending and not st.session_state.action_queue:
            st.session_state.delivery_complete_pending = False
            _clear_queue(st.session_state.session_id)
            st.session_state.bg_queue_active = False
            st.session_state.has_package = False
            st.balloons()

        # Layout: Building and Action Log side by side at top
        col_building, col_log = st.columns([1, 1])

        with col_building:
            # Building visualization - Game View
            st.markdown("### 🎮 Building View")

            # Show current package info prominently
            if st.session_state.last_package_info:
                st.info(f"📦 **Delivering:** {st.session_state.last_package_info}")
            elif st.session_state.bg_delivery_running:
                st.warning("📦 Package info loading...")

            # Build businesses dict from building data
            businesses = {}
            for floor_num in range(1, building.num_floors + 1):
                floor_data = building.floors.get(floor_num, {})
                front_biz = floor_data.get(Side.FRONT)
                back_biz = floor_data.get(Side.BACK)
                businesses[(floor_num, "front")] = front_biz.name if front_biz else "Office"
                businesses[(floor_num, "back")] = back_biz.name if back_biz else "Office"

            game_html = generate_game_html(
                floor=st.session_state.agent_floor,
                side=st.session_state.agent_side,
                current_action=st.session_state.current_action,
                businesses=businesses,
                prev_floor=st.session_state.prev_agent_floor,
                prev_side=st.session_state.prev_agent_side,
                difficulty=st.session_state.difficulty,
            )
            components.html(game_html, height=600, scrolling=False)

        with col_log:
            # Action log (newest at top)
            st.markdown("### 📝 Action Log")

            # Display actions
            if st.session_state.displayed_actions:
                log_container = st.container(height=600)
                with log_container:
                    # Display in reverse order (newest first)
                    for i, action_data in enumerate(reversed(st.session_state.displayed_actions)):
                        is_newest = (i == 0)
                        tool_name = action_data.get("tool_name", "unknown")
                        result = action_data.get("result", "")
                        floor = action_data.get("floor", 1)
                        side = action_data.get("side", "front")
                        timing = action_data.get("timing", 0)

                        # Determine icon and style based on result
                        if "SUCCESS" in result:
                            icon = "🎉"
                            header = f"{icon} The agent called **{tool_name}** - SUCCESS!"
                        elif "error" in tool_name.lower():
                            icon = "❌"
                            header = f"{icon} **Error**"
                        elif "step_limit" in tool_name.lower():
                            icon = "⚠️"
                            header = f"{icon} **Step Limit Reached**"
                        elif tool_name in ["go_up", "go_down", "go_to_front", "go_to_back"]:
                            icon = "🚶"
                            header = f"{icon} The agent called **{tool_name}**"
                        elif tool_name == "look_at_business":
                            icon = "👀"
                            header = f"{icon} The agent called **{tool_name}**"
                        elif tool_name == "deliver_package":
                            icon = "📦"
                            header = f"{icon} The agent called **{tool_name}**"
                        else:
                            icon = "🔧"
                            header = f"{icon} The agent called **{tool_name}**"

                        with st.expander(header, expanded=is_newest):
                            st.markdown(f"**Result:** {result}")
                            st.caption(f"📍 Floor {floor}, {side} side | ⏱️ {timing:.2f}s")
            else:
                if st.session_state.bg_delivery_running:
                    st.markdown("*Agent is working...*")
                else:
                    st.markdown("*Waiting for delivery...*")

            # Auto-refresh while delivery running or animations pending
            needs_refresh = (
                st.session_state.bg_delivery_running or
                st.session_state.action_queue or
                st.session_state.delivery_complete_pending
            )
            if needs_refresh and not st.session_state.step_by_step:
                time.sleep(0.3)  # Poll interval
                st.rerun()

        st.markdown("---")

    # Bottom section: Only show in UI mode (not fast-forward)
    if st.session_state.get("fast_forward", False):
        return  # Fast-forward mode has its own UI in ff_tab

    col_controls, col_stats, col_history = st.columns([1, 1, 1])

    with col_controls:
        # Controls
        st.markdown("### 🎮 Controls")

        # Current package info
        if st.session_state.last_package_info:
            st.markdown("**📦 Current Package:**")
            st.code(st.session_state.last_package_info, language=None)

        # Package options
        include_business = st.checkbox("Include business name", value=st.session_state.include_business,
                                       help="If checked, package will show the business name")
        st.session_state.include_business = include_business

        # Max steps per delivery
        max_steps_ui = st.number_input(
            "Max steps per delivery",
            min_value=1,
            max_value=500,
            value=st.session_state.max_steps_per_delivery,
            placeholder="No limit",
            help="Leave empty for no limit",
            key="ui_max_steps"
        )
        st.session_state.max_steps_per_delivery = max_steps_ui

        # Select Recipient button
        if st.button("👤 Select Recipient", use_container_width=True):
            st.session_state.show_recipient_dialog = True
            st.session_state.start_delivery_now = False
            st.session_state.selected_recipient = None
            st.rerun()

        # Step by step mode - controls animation speed, not agent speed
        step_by_step = st.checkbox("Step by step mode", value=st.session_state.step_by_step,
                                   help="Click 'Next Step' to advance animations one at a time")
        st.session_state.step_by_step = step_by_step

        # Check if a background delivery is running
        is_delivery_running = st.session_state.bg_delivery_running

        # Generate new package button
        start_new_delivery = st.button("📦 New Delivery", use_container_width=True, disabled=is_delivery_running)

        if start_new_delivery:
            st.session_state.current_actions = []
            st.session_state.action_queue = []
            st.session_state.displayed_actions = []
            st.session_state.last_display_time = 0
            st.session_state.delivery_complete_pending = False
            st.session_state.bg_delivery_complete_info = None  # Clear any previous completion
            # Clear old queue before creating new one
            _clear_queue(st.session_state.session_id)
            st.session_state.bg_queue_active = False
            st.session_state.llm_messages = []
            st.session_state.has_package = True
            st.session_state.agent_floor = 1
            st.session_state.agent_side = "front"
            st.session_state.prev_agent_floor = 1
            st.session_state.prev_agent_side = "front"
            st.session_state.current_action = None
            st.session_state.delivery_start_time = time.time()

            # Use selected recipient or generate random package
            if st.session_state.selected_recipient:
                recipient_name = st.session_state.selected_recipient
                business_info = building.find_employee(recipient_name)
                business_name = business_info[0].name if business_info and include_business else None
                package = Package(
                    id=f"{random.randint(1000, 9999)}",
                    recipient_name=recipient_name,
                    business_name=business_name
                )
            else:
                package = building.generate_package(include_business=include_business)
            st.session_state.last_package_info = str(package)

            # Increment delivery counter and set document_id for memory grouping
            st.session_state.delivery_counter += 1
            memory.set_document_id(f"delivery-{st.session_state.delivery_counter}")

            # Get model
            model = os.environ.get("LLM_MODEL", "openai/gpt-4o-mini")

            # Start background thread for delivery using global queue storage
            action_q = _get_or_create_queue(st.session_state.session_id)
            st.session_state.bg_queue_active = True
            st.session_state.bg_delivery_running = True
            st.session_state.bg_delivery_complete_info = None
            st.session_state.pending_delivery = None  # Clear old pending_delivery

            # DEBUG: Log that we're about to start the thread
            with open("/tmp/demo.log", "a") as f:
                f.write(f"\n=== STARTING THREAD from New Delivery button ===\n")
                f.write(f"[START] Session ID: {st.session_state.session_id}\n")
                f.write(f"Package: {package}\n")
                f.write(f"Model: {model}\n")
                f.write(f"[START] Queue from global: {action_q}, id={id(action_q)}\n")
                f.write(f"[START] bg_queue_active: {st.session_state.bg_queue_active}\n")

            thread = threading.Thread(
                target=_run_delivery_in_background,
                args=(action_q, building, package, model, st.session_state.max_steps_per_delivery),
                daemon=True
            )
            thread.start()
            st.rerun()

        # Step-by-step mode: Next Step button advances animations
        if st.session_state.step_by_step and st.session_state.action_queue:
            if st.button("▶️ Next Step", use_container_width=True, type="primary"):
                # Advance one action from the queue
                next_action = st.session_state.action_queue.pop(0)
                st.session_state.displayed_actions.append(next_action)
                st.session_state.last_display_time = time.time()

                if next_action.get("floor") is not None:
                    st.session_state.prev_agent_floor = st.session_state.agent_floor
                    st.session_state.prev_agent_side = st.session_state.agent_side
                    st.session_state.agent_floor = next_action["floor"]
                    st.session_state.agent_side = next_action["side"]
                    st.session_state.current_action = next_action["tool_name"]
                st.rerun()

        # Show status when delivery is running
        if is_delivery_running:
            st.info("🔄 Agent is working... (actions will appear as they complete)")
        elif st.session_state.bg_delivery_complete_info:
            info = st.session_state.bg_delivery_complete_info
            if info["success"]:
                st.success(f"✅ Delivery complete in {info['steps']} steps!")
            elif info["error"]:
                st.error(f"❌ Delivery failed: {info['error']}")
            else:
                st.warning(f"⚠️ Delivery ended after {info['steps']} steps")

            if st.button("🔄 Reset", use_container_width=True):
                st.session_state.bg_delivery_complete_info = None
                _clear_queue(st.session_state.session_id)
                st.session_state.bg_queue_active = False
                st.session_state.action_queue = []
                st.session_state.displayed_actions = []
                st.session_state.delivery_complete_pending = False
                st.rerun()

        # Always-visible Full Reset button - kills everything and starts completely fresh
        if st.button("🔄 Full Reset", use_container_width=True, type="secondary"):
            # Stop any running background delivery
            st.session_state.bg_delivery_running = False
            _clear_queue(st.session_state.session_id)  # Clear and remove the queue
            st.session_state.bg_queue_active = False
            st.session_state.bg_delivery_complete_info = None

            # Clear all delivery state
            st.session_state.action_queue = []
            st.session_state.displayed_actions = []
            st.session_state.delivery_complete_pending = False
            st.session_state.llm_messages = []
            st.session_state.has_package = False
            st.session_state.last_package_info = None
            st.session_state.current_action = None
            st.session_state.agent_floor = 1
            st.session_state.agent_side = "front"
            st.session_state.prev_agent_floor = 1
            st.session_state.prev_agent_side = "front"

            # CRITICAL: Reset delivery trigger flags to prevent auto-start
            st.session_state.start_delivery_now = False
            st.session_state.show_recipient_dialog = False
            st.session_state.pending_delivery = None
            st.session_state.fast_forward = False

            # Generate new session and bank ID (fresh memory)
            st.session_state.session_id = uuid.uuid4().hex[:8]
            bank_id = memory.configure_memory(session_id=st.session_state.session_id)
            st.session_state.bank_id = bank_id

            # Reset stats
            st.session_state.deliveries_completed = 0
            st.session_state.delivery_counter = 0
            st.session_state.total_steps = 0
            st.session_state.delivery_history = []
            st.session_state.current_actions = []
            st.session_state.selected_recipient = None
            st.session_state.selected_business = None
            st.session_state.stored_memories = []
            st.session_state.loop_remaining = 0
            st.session_state.is_running = False

            st.rerun()

        # Clear Memory button (keeps stats, just clears hindsight memory)
        if st.button("🧹 Clear Memory", use_container_width=True, disabled=st.session_state.is_running):
            st.session_state.session_id = uuid.uuid4().hex[:8]
            bank_id = memory.configure_memory(session_id=st.session_state.session_id)
            st.session_state.bank_id = bank_id
            st.session_state.deliveries_completed = 0
            st.session_state.delivery_counter = 0  # Reset delivery counter
            st.session_state.loop_remaining = 0  # Stop any active loop
            st.session_state.total_steps = 0
            st.session_state.delivery_history = []
            st.session_state.current_actions = []
            st.session_state.has_package = False
            st.session_state.last_package_info = None
            st.session_state.current_action = None
            st.session_state.selected_recipient = None
            st.session_state.llm_messages = []
            st.session_state.stored_memories = []
            st.rerun()

    with col_stats:
        # Stats panel
        st.markdown("### 📊 Stats")

        # Memory Bank ID with copy button
        bank_id = st.session_state.get('bank_id', 'N/A')
        st.markdown("🏦 **Memory Bank:**")
        st.code(bank_id, language=None)

        col_a, col_b = st.columns(2)
        with col_a:
            st.metric("Deliveries", st.session_state.deliveries_completed)
        with col_b:
            st.metric("Total Steps", st.session_state.total_steps)

        if st.session_state.deliveries_completed > 0:
            avg_steps = st.session_state.total_steps / st.session_state.deliveries_completed
            st.metric("Avg Steps", f"{avg_steps:.1f}")

        # Timing Benchmarks
        if st.session_state.get("timing_llm_calls") or st.session_state.get("timing_deliveries"):
            st.markdown("### ⏱️ Benchmarks")

            llm_times = st.session_state.get("timing_llm_calls", [])
            delivery_times = st.session_state.get("timing_deliveries", [])

            if llm_times:
                avg_llm = sum(llm_times) / len(llm_times)
                st.metric("Avg LLM Call", f"{avg_llm:.2f}s")

            if delivery_times:
                avg_delivery = sum(delivery_times) / len(delivery_times)
                st.metric("Avg Delivery", f"{avg_delivery:.1f}s")

            # Total loop time
            if st.session_state.get("timing_loop_start") and delivery_times:
                total_loop = time.time() - st.session_state.timing_loop_start
                st.metric("Total Loop Time", f"{total_loop:.1f}s")
                st.caption(f"{len(llm_times)} LLM calls | {len(delivery_times)} deliveries")

    with col_history:
        # Delivery history
        st.markdown("### 📜 History")
        if st.session_state.delivery_history:
            for i, delivery in enumerate(reversed(st.session_state.delivery_history[-5:]), 1):
                status = "✅" if delivery["success"] else "❌"
                st.markdown(f"{status} **{delivery['steps']} steps** 🧠")
        else:
            st.markdown("*No deliveries yet*")

        # Learning curve visualization
        if len(st.session_state.delivery_history) > 1:
            st.markdown("### 📈 Learning Curve")
            steps_history = [d["steps"] for d in st.session_state.delivery_history]
            # Create DataFrame with 1-indexed delivery numbers
            df = pd.DataFrame({
                "Steps": steps_history
            }, index=range(1, len(steps_history) + 1))
            df.index.name = "Delivery"
            st.line_chart(df, use_container_width=True)

    # LLM Debug Section - scrollable, organized display
    st.markdown("### 🤖 LLM Prompt & Response")
    # DEBUG: Log what we're about to render
    with open("/tmp/demo.log", "a") as f:
        f.write(f"[UI] Rendering LLM section, llm_messages count: {len(st.session_state.llm_messages)}\n")
    if st.session_state.llm_messages:
        # Scrollable container
        llm_container = st.container(height=500)
        with llm_container:
            for entry in reversed(st.session_state.llm_messages):  # Newest first
                step_num = entry.get("step", "?")
                is_newest = (entry == st.session_state.llm_messages[-1])

                with st.expander(f"**Step {step_num}**", expanded=is_newest):
                    raw_prompt_str = entry.get("raw_prompt", "{}")
                    raw_response_str = entry.get("raw_response", "{}")

                    try:
                        raw_prompt = json.loads(raw_prompt_str)
                        messages = raw_prompt.get("messages", [])
                        injection_info = raw_prompt.get("_hindsight_injection", {})

                        # Separate messages by type
                        system_msg = None
                        history_messages = []
                        current_message = None

                        for msg in messages:
                            role = msg.get("role", "")
                            if role == "system":
                                system_msg = msg
                            elif msg == messages[-1]:
                                current_message = msg
                            else:
                                history_messages.append(msg)

                        # 1. History (collapsed) - previous conversation turns
                        if history_messages:
                            with st.expander(f"📜 History ({len(history_messages)} messages)", expanded=False):
                                for msg in history_messages:
                                    role = msg.get("role", "").upper()
                                    content = msg.get("content", "")
                                    tool_calls = msg.get("tool_calls", [])

                                    if role == "USER":
                                        st.caption(f"**USER:** {content}")
                                    elif role == "ASSISTANT" and tool_calls:
                                        # Handle both formats: {"name": ...} or {"function": {"name": ...}}
                                        tc_names = [tc.get("function", {}).get("name", "") or tc.get("name", "") for tc in tool_calls]
                                        st.caption(f"**ASSISTANT:** called {', '.join(tc_names)}")
                                    elif role == "TOOL":
                                        st.caption(f"**TOOL:** {content[:100]}..." if len(content) > 100 else f"**TOOL:** {content}")
                                    else:
                                        st.caption(f"**{role}:** {content[:100]}..." if len(content) > 100 else f"**{role}:** {content}")

                        # 2. System Prompt (with injected memories)
                        st.markdown("**🔧 System Prompt:**")
                        if system_msg:
                            system_content = system_msg.get("content", "")
                            # Check if memories were injected
                            injected = injection_info.get("injected", False) if injection_info else False
                            memories_count = injection_info.get("memories_count", 0) if injection_info else 0

                            if injected and memories_count > 0:
                                st.success(f"🧠 {memories_count} memories injected")
                                # Show full system prompt with memories
                                with st.expander("View full system prompt with memories", expanded=False):
                                    st.code(system_content, language=None)
                            else:
                                st.caption("🧠 No memories injected")
                                st.code(system_content, language=None)
                        else:
                            st.caption("No system prompt")

                        # 3. Tools available
                        tools = raw_prompt.get("tools", [])
                        if tools:
                            with st.expander(f"🔧 Tools ({len(tools)} available)", expanded=False):
                                tool_names = [t.get("function", {}).get("name", "?") for t in tools]
                                st.write(", ".join(tool_names))

                        # 4. Current (the latest message being sent)
                        st.markdown("**📤 Current:**")
                        if current_message:
                            st.json(current_message)
                        else:
                            st.caption("No current message")

                        st.divider()

                        # 5. Response
                        st.markdown("**📥 Response:**")
                        st.code(raw_response_str, language="json")

                        st.divider()

                        # 5. Raw Prompt & Response (for debugging)
                        with st.expander("🔍 Raw Prompt & Response (Debug)", expanded=False):
                            st.markdown("**Raw Prompt (full JSON sent to LLM):**")
                            st.code(raw_prompt_str, language="json")
                            st.markdown("**Raw Response (full JSON from LLM):**")
                            st.code(raw_response_str, language="json")

                    except Exception as e:
                        st.error(f"Parse error: {e}")
                        st.code(raw_prompt_str, language="json")
    else:
        st.caption("*No LLM calls yet*")


if __name__ == "__main__":
    main()
