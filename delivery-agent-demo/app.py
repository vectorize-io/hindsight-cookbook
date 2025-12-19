"""
Delivery Agent Demo - Streamlit App

A retro-style sprite-based demo showcasing how AI agents learn
to navigate using Hindsight memory.
"""

import streamlit as st
import streamlit.components.v1 as components
import time
import os
import uuid
from dotenv import load_dotenv

from building import get_building, Side, reset_building
from agent import DeliveryAgent, ActionEvent
import memory

# Load environment variables
load_dotenv()

# Page config
st.set_page_config(
    page_title="Delivery Agent Demo",
    page_icon="📦",
    layout="wide"
)


def render_building_html(building, agent_floor: int, agent_side: str, has_package: bool = False, current_action: str = None):
    """Render the building as a retro sprite-based visualization using HTML."""
    floors_data = building.get_floor_display()

    html = """
    <!DOCTYPE html>
    <html>
    <head>
    <style>
        @import url('https://fonts.googleapis.com/css2?family=Press+Start+2P&display=swap');

        * {
            box-sizing: border-box;
            margin: 0;
            padding: 0;
        }

        body {
            background: #0f0f23;
            font-family: 'Press Start 2P', monospace;
            padding: 10px;
        }

        .building {
            background: #f5f5dc;
            border: 4px solid #000000;
            border-radius: 8px;
            padding: 15px;
            box-shadow: 0 0 20px rgba(0, 0, 0, 0.3);
        }

        .floor {
            display: flex;
            align-items: stretch;
            margin-bottom: 4px;
            position: relative;
        }

        .business {
            flex: 1;
            background: #add8e6;
            border: 3px solid #4a90a4;
            padding: 12px 8px;
            text-align: center;
            min-height: 90px;
            position: relative;
            display: flex;
            flex-direction: column;
            justify-content: center;
            align-items: center;
        }

        .business.active {
            border-color: #00aa00;
            box-shadow: 0 0 20px rgba(0, 200, 0, 0.6);
            background: #90ee90;
        }

        .business-name {
            font-size: 7px;
            color: #333333;
            margin-bottom: 8px;
            line-height: 1.4;
            font-weight: bold;
        }

        .sprites {
            font-size: 48px;
            min-height: 50px;
        }

        .agent {
            display: inline-block;
            animation: bounce 0.5s ease infinite;
            font-size: 56px;
        }

        .agent.facing-right {
            animation: bounce-right 0.5s ease infinite;
        }

        .package {
            font-size: 40px;
        }

        .magnifying-glass {
            font-size: 36px;
            animation: pulse 0.5s ease infinite;
        }

        @keyframes pulse {
            0%, 100% { transform: scale(1); }
            50% { transform: scale(1.2); }
        }

        @keyframes bounce {
            0%, 100% { transform: translateY(0); }
            50% { transform: translateY(-5px); }
        }

        @keyframes bounce-right {
            0%, 100% { transform: scaleX(-1) translateY(0); }
            50% { transform: scaleX(-1) translateY(-5px); }
        }

        .floor-center {
            width: 80px;
            display: flex;
            flex-direction: column;
            align-items: center;
            justify-content: center;
            background: #d4c4a8;
            position: relative;
        }

        .floor-num {
            color: #8b4513;
            font-size: 12px;
            font-weight: bold;
            z-index: 2;
            position: absolute;
        }

        /* F1, F3, F5: top right quadrant */
        .floor-1 .floor-num { top: 5px; right: 5px; }
        .floor-3 .floor-num { top: 5px; right: 5px; }
        .floor-5 .floor-num { top: 5px; right: 5px; }

        /* F2, F4: top left quadrant */
        .floor-2 .floor-num { top: 5px; left: 5px; }
        .floor-4 .floor-num { top: 5px; left: 5px; }

        .staircase-container {
            position: absolute;
            top: 0;
            left: 0;
            right: 0;
            bottom: 0;
        }

        .stair-segment {
            position: absolute;
            background: #1a1a1a;
        }

        /* Each floor has 4 steps: h1,v1,h2,v2,h3,v3,h4,v4 */
        /* Horizontal segments are 25% width, vertical segments are 25% height */

        /* ===== FLOOR 1: Right to Left (bottom-right of front to top-left of back) ===== */
        .floor-1 .h1 { bottom: 0; right: 0; width: 25%; height: 5px; }
        .floor-1 .v1 { bottom: 0; right: 25%; width: 5px; height: 25%; }
        .floor-1 .h2 { bottom: 25%; right: 25%; width: 25%; height: 5px; }
        .floor-1 .v2 { bottom: 25%; right: 50%; width: 5px; height: 25%; }
        .floor-1 .h3 { bottom: 50%; right: 50%; width: 25%; height: 5px; }
        .floor-1 .v3 { bottom: 50%; right: 75%; width: 5px; height: 25%; }
        .floor-1 .h4 { bottom: 75%; right: 75%; width: 25%; height: 5px; }
        .floor-1 .v4 { bottom: 75%; left: 0; width: 5px; height: 25%; }

        /* ===== FLOOR 2: Left to Right ===== */
        .floor-2 .h1 { bottom: 0; left: 0; width: 25%; height: 5px; }
        .floor-2 .v1 { bottom: 0; left: 25%; width: 5px; height: 25%; }
        .floor-2 .h2 { bottom: 25%; left: 25%; width: 25%; height: 5px; }
        .floor-2 .v2 { bottom: 25%; left: 50%; width: 5px; height: 25%; }
        .floor-2 .h3 { bottom: 50%; left: 50%; width: 25%; height: 5px; }
        .floor-2 .v3 { bottom: 50%; left: 75%; width: 5px; height: 25%; }
        .floor-2 .h4 { bottom: 75%; left: 75%; width: 25%; height: 5px; }
        .floor-2 .v4 { bottom: 75%; right: 0; width: 5px; height: 25%; }

        /* ===== FLOOR 3: Right to Left ===== */
        .floor-3 .h1 { bottom: 0; right: 0; width: 25%; height: 5px; }
        .floor-3 .v1 { bottom: 0; right: 25%; width: 5px; height: 25%; }
        .floor-3 .h2 { bottom: 25%; right: 25%; width: 25%; height: 5px; }
        .floor-3 .v2 { bottom: 25%; right: 50%; width: 5px; height: 25%; }
        .floor-3 .h3 { bottom: 50%; right: 50%; width: 25%; height: 5px; }
        .floor-3 .v3 { bottom: 50%; right: 75%; width: 5px; height: 25%; }
        .floor-3 .h4 { bottom: 75%; right: 75%; width: 25%; height: 5px; }
        .floor-3 .v4 { bottom: 75%; left: 0; width: 5px; height: 25%; }

        /* ===== FLOOR 4: Left to Right ===== */
        .floor-4 .h1 { bottom: 0; left: 0; width: 25%; height: 5px; }
        .floor-4 .v1 { bottom: 0; left: 25%; width: 5px; height: 25%; }
        .floor-4 .h2 { bottom: 25%; left: 25%; width: 25%; height: 5px; }
        .floor-4 .v2 { bottom: 25%; left: 50%; width: 5px; height: 25%; }
        .floor-4 .h3 { bottom: 50%; left: 50%; width: 25%; height: 5px; }
        .floor-4 .v3 { bottom: 50%; left: 75%; width: 5px; height: 25%; }
        .floor-4 .h4 { bottom: 75%; left: 75%; width: 25%; height: 5px; }
        .floor-4 .v4 { bottom: 75%; right: 0; width: 5px; height: 25%; }

        /* ===== FLOOR 5: Right to Left (top floor) ===== */
        .floor-5 .h1 { bottom: 0; right: 0; width: 25%; height: 5px; }
        .floor-5 .v1 { bottom: 0; right: 25%; width: 5px; height: 25%; }
        .floor-5 .h2 { bottom: 25%; right: 25%; width: 25%; height: 5px; }
        .floor-5 .v2 { bottom: 25%; right: 50%; width: 5px; height: 25%; }
        .floor-5 .h3 { bottom: 50%; right: 50%; width: 25%; height: 5px; }
        .floor-5 .v3 { bottom: 50%; right: 75%; width: 5px; height: 25%; }
        .floor-5 .h4 { bottom: 75%; right: 75%; width: 25%; height: 5px; }
        .floor-5 .v4 { bottom: 75%; left: 0; width: 5px; height: 25%; }

        .platform {
            height: 8px;
            background: linear-gradient(180deg, #8b4513 0%, #654321 100%);
            border-top: 2px solid #a0522d;
            margin-top: 2px;
        }

        .title {
            text-align: center;
            color: #8b4513;
            font-size: 10px;
            margin-bottom: 15px;
            text-shadow: 1px 1px #d4c4a8;
        }

        .ground {
            height: 15px;
            background: linear-gradient(180deg, #228b22 0%, #006400 100%);
            border-top: 3px solid #32cd32;
            margin-top: 5px;
            border-radius: 0 0 4px 4px;
        }
    </style>
    </head>
    <body>
    <div class="building">
        <div class="title">OFFICE BUILDING</div>
    """

    for floor_data in floors_data:
        floor_num = floor_data["floor"]
        front_biz = floor_data["front"]
        back_biz = floor_data["back"]

        is_agent_floor = floor_num == agent_floor
        agent_on_front = is_agent_floor and agent_side == "front"
        agent_on_back = is_agent_floor and agent_side == "back"

        front_class = "business active" if agent_on_front else "business"
        back_class = "business active" if agent_on_back else "business"

        front_sprites = ""
        back_sprites = ""

        # Check if agent is checking employees at current location
        is_checking = current_action == "get_employee_list"

        if agent_on_front:
            # Mirror the agent to face right when on front (left) side
            front_sprites = '<span class="agent facing-right">🚶</span>'
            if has_package:
                front_sprites += '<span class="package">📦</span>'
            if is_checking:
                front_sprites += '<span class="magnifying-glass">🔍</span>'

        if agent_on_back:
            back_sprites = '<span class="agent">🚶</span>'
            if has_package:
                back_sprites += '<span class="package">📦</span>'
            if is_checking:
                back_sprites += '<span class="magnifying-glass">🔍</span>'

        html += f'''
        <div class="floor">
            <div class="{front_class}">
                <div class="business-name">{front_biz.name if front_biz else "Empty"}</div>
                <div class="sprites">{front_sprites}</div>
            </div>
            <div class="floor-center floor-{floor_num}">
                <div class="staircase-container">
                    <div class="stair-segment h1"></div>
                    <div class="stair-segment v1"></div>
                    <div class="stair-segment h2"></div>
                    <div class="stair-segment v2"></div>
                    <div class="stair-segment h3"></div>
                    <div class="stair-segment v3"></div>
                    <div class="stair-segment h4"></div>
                    <div class="stair-segment v4"></div>
                </div>
                <div class="floor-num">F{floor_num}</div>
            </div>
            <div class="{back_class}">
                <div class="business-name">{back_biz.name if back_biz else "Empty"}</div>
                <div class="sprites">{back_sprites}</div>
            </div>
        </div>
        <div class="platform"></div>
        '''

    html += """
        <div class="ground"></div>
    </div>
    </body>
    </html>
    """

    return html


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

    building = st.session_state.building

    # Auto-start delivery if recipient was selected (check this FIRST)
    if st.session_state.start_delivery_now and st.session_state.selected_recipient:
        st.session_state.start_delivery_now = False
        st.session_state.show_recipient_dialog = False  # Ensure dialog is closed
        st.session_state.current_actions = []
        st.session_state.llm_messages = []  # Reset step counter for new delivery
        st.session_state.has_package = True
        st.session_state.agent_floor = 1
        st.session_state.agent_side = "front"
        st.session_state.prev_agent_floor = 1
        st.session_state.prev_agent_side = "front"
        st.session_state.current_action = None

        # Create package for selected recipient
        from building import Package
        import random
        recipient_name = st.session_state.selected_recipient
        # Find the business for this recipient
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

        # Create agent
        agent = DeliveryAgent(building=building)

        # Use step-by-step internally (for animation)
        st.session_state.pending_delivery = {
            "package": package,
            "agent": agent,
            "complete": False,
            "auto_advance": not st.session_state.step_by_step
        }
        st.session_state.current_result = None
        # Clear selected recipient after starting delivery
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
            has_pending = st.session_state.pending_delivery is not None

            loop_count = st.slider("Deliveries to run", min_value=1, max_value=100, value=10, key="ff_loop_count")

            loop_disabled = has_pending or st.session_state.loop_remaining > 0
            if st.button("🚀 Run Loop", use_container_width=True, disabled=loop_disabled, key="ff_loop_btn"):
                st.session_state.fast_forward = True
                st.session_state.loop_remaining = loop_count
                st.session_state.timing_loop_start = time.time()
                st.session_state.timing_llm_calls = []
                st.session_state.timing_deliveries = []

            if st.session_state.loop_remaining > 0:
                progress = 1 - (st.session_state.loop_remaining / loop_count) if loop_count > 0 else 0
                st.progress(progress, text=f"{st.session_state.loop_remaining} remaining")

            if st.button("📦 Single Delivery", use_container_width=True, disabled=has_pending, key="ff_single_btn"):
                st.session_state.fast_forward = True
                st.session_state.loop_remaining = 1

            if st.button("🛑 Stop", use_container_width=True, disabled=not has_pending, key="ff_stop_btn"):
                st.session_state.loop_remaining = 0
                st.session_state.pending_delivery = None

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

        # Learning curve in fast-forward
        if len(st.session_state.delivery_history) > 1:
            st.markdown("### 📈 Learning Curve")
            import pandas as pd
            steps_history = [d["steps"] for d in st.session_state.delivery_history]
            df = pd.DataFrame({"Steps": steps_history}, index=range(1, len(steps_history) + 1))
            df.index.name = "Delivery"
            st.line_chart(df, use_container_width=True)

        # Current status
        if has_pending:
            st.info(f"🔄 Running... Floor {st.session_state.agent_floor}, {st.session_state.agent_side} side | Step {st.session_state.pending_delivery['agent'].state.steps_taken if st.session_state.pending_delivery else 0}")

        # Fast-forward delivery loop (inside ff_tab)
        if st.session_state.get("fast_forward", False):
            # Auto-start if loop is active and no pending delivery
            if st.session_state.loop_remaining > 0 and st.session_state.pending_delivery is None:
                st.session_state.loop_remaining -= 1
                from building import Package
                package = building.generate_package(include_business=st.session_state.include_business)
                st.session_state.last_package_info = str(package)
                st.session_state.delivery_counter += 1
                memory.set_document_id(f"delivery-{st.session_state.delivery_counter}")
                st.session_state.delivery_start_time = time.time()

                agent = DeliveryAgent(building=building)
                st.session_state.pending_delivery = {
                    "package": package,
                    "agent": agent,
                    "complete": False,
                    "auto_advance": True
                }
                st.session_state.action_queue = []
                st.session_state.displayed_actions = []
                st.session_state.llm_messages = []
                st.rerun()

            # Run the delivery step if pending
            if st.session_state.pending_delivery and not st.session_state.pending_delivery["complete"]:
                pending = st.session_state.pending_delivery
                agent = pending["agent"]
                package = pending["package"]

                from agent_tools import AgentTools, TOOL_DEFINITIONS, execute_tool
                import json
                import time as timer

                if agent.state.current_package is None:
                    agent.state.current_package = package
                    pending["messages"] = [
                        {"role": "system", "content": agent._build_system_prompt(package)},
                        {"role": "user", "content": f"Please deliver this package: {package}"}
                    ]

                tools = AgentTools(agent.building, agent.state, on_action=agent._record_action)

                try:
                    t0 = timer.time()
                    response = memory.completion(
                        model=agent.model,
                        messages=pending["messages"],
                        tools=TOOL_DEFINITIONS,
                        tool_choice="auto",
                        timeout=30
                    )
                    t1 = timer.time()
                    st.session_state.timing_llm_calls.append(t1 - t0)

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

                            st.session_state.agent_floor = agent.state.floor
                            st.session_state.agent_side = agent.state.side.value

                            if "SUCCESS!" in result:
                                pending["complete"] = True
                                st.session_state.deliveries_completed += 1
                                st.session_state.total_steps += agent.state.steps_taken
                                if st.session_state.delivery_start_time:
                                    st.session_state.timing_deliveries.append(time.time() - st.session_state.delivery_start_time)
                                st.session_state.delivery_history.append({
                                    "package": str(package),
                                    "success": True,
                                    "steps": agent.state.steps_taken
                                })
                                st.session_state.pending_delivery = None
                                break

                        pending["messages"].append({"role": "assistant", "content": message.content, "tool_calls": message.tool_calls})
                        pending["messages"].extend(tool_results)

                        if agent.state.steps_taken >= 50:
                            pending["complete"] = True
                            st.session_state.pending_delivery = None
                    else:
                        pending["messages"].append({"role": "assistant", "content": message.content})
                        pending["messages"].append({"role": "user", "content": "Use the available tools to complete the delivery."})

                except Exception as e:
                    print(f"[FF ERROR] {e}", flush=True)
                    pending["complete"] = True
                    st.session_state.pending_delivery = None

                st.rerun()

    with ui_tab:
        # Reset fast_forward when viewing UI tab
        st.session_state.fast_forward = False

        # Layout: Building and Action Log side by side at top
        col_building, col_log = st.columns([1, 1])

        with col_building:
            # Building visualization - Game View
            st.markdown("### 🎮 Building View")

            # Use new animated game renderer
            from game_renderer import generate_game_html

            # Build businesses dict from building data
            from building import Side
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

            # Normal mode: process queue with animation timing
            import time as timer
            current_time = timer.time()
            time_since_last = current_time - st.session_state.last_display_time

            if st.session_state.action_queue and time_since_last >= st.session_state.animation_duration:
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
                st.session_state.pending_delivery = None
                st.balloons()

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
                st.markdown("*Waiting for delivery...*")

            # Auto-refresh to process queue (trigger rerun after animation duration)
            if st.session_state.action_queue or st.session_state.delivery_complete_pending:
                time.sleep(0.5)  # Small delay to allow UI to render
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

        # Select Recipient button
        if st.button("👤 Select Recipient", use_container_width=True):
            st.session_state.show_recipient_dialog = True
            st.session_state.start_delivery_now = False
            st.session_state.selected_recipient = None
            st.rerun()

        # Step by step mode
        step_by_step = st.checkbox("Step by step mode", value=st.session_state.step_by_step,
                                   help="Click 'Next Step' to advance one action at a time")
        st.session_state.step_by_step = step_by_step

        # Check if there's a pending step-by-step delivery
        has_pending = st.session_state.pending_delivery is not None

        # Generate new package button
        start_new_delivery = st.button("📦 New Delivery", use_container_width=True, disabled=has_pending)

        if start_new_delivery:
            st.session_state.current_actions = []
            st.session_state.action_queue = []  # Reset action queue
            st.session_state.displayed_actions = []  # Reset displayed actions
            st.session_state.last_display_time = 0
            st.session_state.delivery_complete_pending = False
            st.session_state.llm_messages = []  # Reset step counter for new delivery
            st.session_state.has_package = True
            st.session_state.agent_floor = 1
            st.session_state.agent_side = "front"
            st.session_state.prev_agent_floor = 1
            st.session_state.prev_agent_side = "front"
            st.session_state.current_action = None
            st.session_state.delivery_start_time = time.time()  # Track delivery start

            # Use selected recipient or generate random package
            if st.session_state.selected_recipient:
                from building import Package
                import random
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

            agent = DeliveryAgent(building=building)
            st.session_state.pending_delivery = {
                "package": package,
                "agent": agent,
                "complete": False,
                "auto_advance": not st.session_state.step_by_step
            }
            st.session_state.current_result = None
            st.rerun()

        # Next Step button for step-by-step mode
        if has_pending:
            pending = st.session_state.pending_delivery
            auto_advance = pending.get("auto_advance", False)

            if not pending["complete"]:
                should_step = False
                if auto_advance:
                    should_step = True
                else:
                    should_step = st.button("▶️ Next Step", use_container_width=True, type="primary")

                if should_step:
                    agent = pending["agent"]
                    package = pending["package"]

                    from agent_tools import AgentTools, TOOL_DEFINITIONS, execute_tool
                    import json

                    # Batch size: run 1 step at a time for real-time UI updates
                    # (LLM section shows each step immediately)
                    batch_size = 1
                    steps_this_batch = 0

                    while steps_this_batch < batch_size and not pending["complete"]:
                        steps_this_batch += 1

                        if agent.state.current_package is None:
                            agent.state.current_package = package
                            pending["messages"] = [
                                {"role": "system", "content": agent._build_system_prompt(package)},
                                {"role": "user", "content": f"Please deliver this package: {package}"}
                            ]

                        tools = AgentTools(agent.building, agent.state, on_action=agent._record_action)

                        try:
                            import time as timer
                            t0 = timer.time()

                            response = memory.completion(
                                model=agent.model,
                                messages=pending["messages"],
                                tools=TOOL_DEFINITIONS,
                                tool_choice="auto",
                                timeout=30
                            )

                            t1 = timer.time()
                            llm_duration = t1 - t0
                            st.session_state.timing_llm_calls.append(llm_duration)

                            message = response.choices[0].message
                            print(f"[DEBUG] LLM response ({llm_duration:.2f}s): tool_calls={bool(message.tool_calls)}, content={bool(message.content)}", flush=True)
                            if message.tool_calls:
                                print(f"[DEBUG] Tool calls: {[tc.function.name for tc in message.tool_calls]}", flush=True)

                            import hindsight_litellm
                            debug_info = hindsight_litellm.get_last_injection_debug()
                            print(f"[DEBUG] Building raw messages from {len(pending['messages'])} messages...", flush=True)
                            if debug_info:
                                print(f"[DEBUG] Hindsight injected: {debug_info.injected}, results_count: {debug_info.results_count}", flush=True)

                            # Build raw prompt - POST-INJECTION (what actually went to LLM)
                            raw_messages = []
                            for i, msg in enumerate(pending["messages"]):
                                raw_msg = {"role": msg.get("role", "")}
                                content = msg.get("content", "")

                                # For system message, append injected memories (what Hindsight actually did)
                                if msg.get("role") == "system" and debug_info and debug_info.injected:
                                    content = f"{content}\n\n{debug_info.memory_context}"

                                if content:
                                    raw_msg["content"] = content
                                if msg.get("tool_calls"):
                                    tc_list = []
                                    for tc in msg.get("tool_calls", []):
                                        # Handle both object (from LLM response) and dict (from stored messages) formats
                                        if hasattr(tc, 'function'):
                                            tc_list.append({"name": tc.function.name, "arguments": tc.function.arguments})
                                        elif isinstance(tc, dict):
                                            func = tc.get('function', {})
                                            tc_list.append({"name": func.get('name', ''), "arguments": func.get('arguments', '')})
                                    raw_msg["tool_calls"] = tc_list
                                if msg.get("tool_call_id"):
                                    raw_msg["tool_call_id"] = msg.get("tool_call_id")
                                raw_messages.append(raw_msg)

                            # Include tools and injection info in the raw prompt
                            raw_prompt = {
                                "messages": raw_messages,
                                "tools": [{"name": t["function"]["name"], "description": t["function"]["description"]} for t in TOOL_DEFINITIONS],
                                "_hindsight_injection": {
                                    "injected": debug_info.injected if debug_info else False,
                                    "memories_count": debug_info.results_count if debug_info else 0,
                                } if debug_info else None
                            }

                            # Build raw response
                            raw_response = {
                                "content": message.content,
                                "tool_calls": [
                                    {"name": tc.function.name, "arguments": tc.function.arguments}
                                    for tc in (message.tool_calls or [])
                                ] if message.tool_calls else None
                            }

                            tool_calls_info = []
                            if message.tool_calls:
                                for tc in message.tool_calls:
                                    tool_calls_info.append({
                                        "tool_call": tc.function.name,
                                        "arguments": tc.function.arguments,
                                        "reasoning": message.content or "No explicit reasoning provided"
                                    })

                            llm_entry = {
                                "step": len(st.session_state.llm_messages) + 1,
                                "raw_prompt": json.dumps(raw_prompt, indent=2),
                                "raw_response": json.dumps(raw_response, indent=2),
                                "tool_calls": tool_calls_info
                            }
                            st.session_state.llm_messages.append(llm_entry)

                            if message.tool_calls:
                                print(f"[DEBUG] Processing {len(message.tool_calls)} tool calls...", flush=True)
                                tool_results = []
                                for tool_call in message.tool_calls:
                                    tool_name = tool_call.function.name
                                    arguments = json.loads(tool_call.function.arguments) if tool_call.function.arguments else {}
                                    print(f"[DEBUG] Executing tool: {tool_name}({arguments})", flush=True)

                                    st.session_state.current_action = tool_name

                                    # Execute tool
                                    t_tool_start = timer.time()
                                    result = execute_tool(tools, tool_name, arguments)
                                    t_tool_end = timer.time()

                                    tool_results.append({
                                        "tool_call_id": tool_call.id,
                                        "role": "tool",
                                        "content": result
                                    })

                                    # Add to action queue (will be displayed with animation later)
                                    action_data = {
                                        "tool_name": tool_name,
                                        "result": result,
                                        "floor": agent.state.floor,
                                        "side": agent.state.side.value,
                                        "timing": t_tool_end - t_tool_start,
                                    }
                                    st.session_state.action_queue.append(action_data)

                                    if "SUCCESS!" in result:
                                        pending["complete"] = True
                                        st.session_state.deliveries_completed += 1
                                        st.session_state.has_package = False
                                        st.session_state.total_steps += agent.state.steps_taken
                                        # Track delivery duration
                                        if st.session_state.delivery_start_time:
                                            delivery_duration = time.time() - st.session_state.delivery_start_time
                                            st.session_state.timing_deliveries.append(delivery_duration)
                                        st.session_state.delivery_history.append({
                                            "package": str(package),
                                            "success": True,
                                            "steps": agent.state.steps_taken
                                        })
                                        # Mark delivery complete but wait for animations
                                        st.session_state.delivery_complete_pending = True
                                        break

                                pending["messages"].append({"role": "assistant", "content": message.content, "tool_calls": message.tool_calls})
                                pending["messages"].extend(tool_results)

                                if agent.state.steps_taken >= 50:
                                    pending["complete"] = True
                                    st.session_state.delivery_complete_pending = True
                            else:
                                # LLM returned text without tool calls - add to queue and nudge to use tools
                                if message.content:
                                    st.session_state.action_queue.append({
                                        "tool_name": "💬 response",
                                        "result": message.content,
                                        "floor": agent.state.floor,
                                        "side": agent.state.side.value,
                                        "timing": 0,
                                    })
                                pending["messages"].append({"role": "assistant", "content": message.content})
                                pending["messages"].append({"role": "user", "content": "Use the available tools to complete the delivery."})

                        except Exception as e:
                            import traceback
                            st.error(f"❌ Error: {e}")
                            st.code(traceback.format_exc(), language=None)
                            pending["complete"] = True
                            st.session_state.pending_delivery = None
                            break  # Exit the while loop on error

                    st.rerun()
            else:
                st.success("Delivery complete!")
                if st.button("🔄 Reset", use_container_width=True):
                    st.session_state.pending_delivery = None
                    st.rerun()

        # Reset memory button
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
            import pandas as pd
            steps_history = [d["steps"] for d in st.session_state.delivery_history]
            # Create DataFrame with 1-indexed delivery numbers
            df = pd.DataFrame({
                "Steps": steps_history
            }, index=range(1, len(steps_history) + 1))
            df.index.name = "Delivery"
            st.line_chart(df, use_container_width=True)

    # LLM Debug Section - scrollable, organized display
    st.markdown("### 🤖 LLM Prompt & Response")
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
                        import json
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
                                        tc_names = [tc.get("name", "") for tc in tool_calls]
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

                        # 3. Current (the latest message being sent)
                        st.markdown("**📤 Current:**")
                        if current_message:
                            st.json(current_message)
                        else:
                            st.caption("No current message")

                        st.divider()

                        # 4. Response
                        st.markdown("**📥 Response:**")
                        st.code(raw_response_str, language="json")

                    except Exception as e:
                        st.error(f"Parse error: {e}")
                        st.code(raw_prompt_str, language="json")
    else:
        st.caption("*No LLM calls yet*")


if __name__ == "__main__":
    main()
