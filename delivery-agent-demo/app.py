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

    if "total_steps" not in st.session_state:
        st.session_state.total_steps = 0

    if "delivery_history" not in st.session_state:
        st.session_state.delivery_history = []

    if "current_actions" not in st.session_state:
        st.session_state.current_actions = []

    if "agent_floor" not in st.session_state:
        st.session_state.agent_floor = 1

    if "agent_side" not in st.session_state:
        st.session_state.agent_side = "front"

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

    # Layout: Building and Action Log side by side at top
    col_building, col_log = st.columns([1, 1])

    with col_building:
        # Building visualization
        st.markdown("### 🏢 Building View")

        # Render building as HTML component
        building_html = render_building_html(
            building,
            st.session_state.agent_floor,
            st.session_state.agent_side,
            st.session_state.has_package,
            st.session_state.current_action
        )
        components.html(building_html, height=650, scrolling=False)

    with col_log:
        # Action log (newest at top)
        st.markdown("### 📝 Action Log")

        # Track action count for scroll position maintenance
        action_count = len(st.session_state.current_actions)
        prev_count = st.session_state.get('prev_action_count', 0)

        if st.session_state.current_actions:
            log_container = st.container(height=600)
            with log_container:
                # Group: each tool action with status/memory before AND after it
                groups = []
                pending_status = []  # Status messages waiting for their action

                for action, result in st.session_state.current_actions:
                    if action in ["🧠 memory", "⏳ status", "💬 response"]:
                        if groups and groups[-1]["action"]:
                            # Attach to previous action group
                            groups[-1]["after"].append((action, result))
                        else:
                            # No action yet, queue as pending
                            pending_status.append((action, result))
                    else:
                        # New tool action - create group with pending status
                        groups.append({
                            "before": pending_status.copy(),
                            "action": (action, result),
                            "after": []
                        })
                        pending_status = []

                # Handle any trailing status without action
                if pending_status:
                    groups.append({"before": pending_status, "action": None, "after": []})

                # Display in reverse order (newest first)
                for i, group in enumerate(reversed(groups)):
                    if i > 0:
                        st.divider()

                    # Show the main action first (if exists)
                    if group["action"]:
                        action, result = group["action"]
                        if "SUCCESS" in result:
                            st.success(f"**{action}**: {result}")
                        elif action in ["go_up", "go_down", "go_to_front", "go_to_back"]:
                            st.warning(f"**{action}**: {result}")
                        else:
                            st.info(f"**{action}**: {result}")

                    # Show before status (indented/smaller)
                    for action, result in group["before"]:
                        if action == "🧠 memory":
                            st.caption(f"  🧠 {result}")
                        elif action == "⏳ status":
                            st.caption(f"  ⏳ {result}")
                        elif action == "💬 response":
                            st.warning(f"💬 LLM said: {result}")

                    # Show after status (indented/smaller)
                    for action, result in group["after"]:
                        if action == "🧠 memory":
                            st.caption(f"  🧠 {result}")
                        elif action == "⏳ status":
                            st.caption(f"  ⏳ {result}")
                        elif action == "💬 response":
                            st.warning(f"💬 LLM said: {result}")
        else:
            st.markdown("*Waiting for delivery...*")

        # Maintain scroll position when new content is added at top
        if action_count > prev_count and prev_count > 0:
            # New actions added - adjust scroll to keep user at same content
            scroll_adjust_js = """
            <script>
                (function() {
                    // Find the scrollable container (Streamlit container with height)
                    const containers = window.parent.document.querySelectorAll('[data-testid="stVerticalBlockBorderWrapper"]');
                    for (const container of containers) {
                        const scrollable = container.querySelector('[style*="overflow"]');
                        if (scrollable && scrollable.scrollHeight > scrollable.clientHeight) {
                            // Estimate new content height and adjust scroll
                            const newItems = """ + str(action_count - prev_count) + """;
                            const avgItemHeight = 60; // Approximate height per action item
                            scrollable.scrollTop += (newItems * avgItemHeight);
                        }
                    }
                })();
            </script>
            """
            components.html(scroll_adjust_js, height=0)

        st.session_state.prev_action_count = action_count

    st.markdown("---")

    # Bottom section: Controls, Stats, and History
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
        if st.button("📦 New Delivery", use_container_width=True, disabled=has_pending):
            st.session_state.current_actions = []
            st.session_state.llm_messages = []  # Reset step counter for new delivery
            st.session_state.has_package = True
            st.session_state.agent_floor = 1
            st.session_state.agent_side = "front"
            st.session_state.current_action = None

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

                    memory.clear_recent_memories()

                    if agent.state.current_package is None:
                        agent.state.current_package = package
                        pending["messages"] = [
                            {"role": "system", "content": agent._build_system_prompt(package)},
                            {"role": "user", "content": f"Please deliver this package: {package}. You are at Floor 1, front side."}
                        ]

                    tools = AgentTools(agent.building, agent.state, on_action=agent._record_action)

                    try:
                        import time as timer

                        # Log to action log
                        st.session_state.current_actions.append(("⏳ status", "Starting memory recall from Hindsight..."))
                        t0 = timer.time()

                        response = memory.completion(
                            model=agent.model,
                            messages=pending["messages"],
                            tools=TOOL_DEFINITIONS,
                            tool_choice="auto",
                            timeout=30
                        )

                        t1 = timer.time()
                        st.session_state.current_actions.append(("⏳ status", f"LLM response received ({t1-t0:.2f}s)"))

                        message = response.choices[0].message
                        print(f"[DEBUG] LLM response: tool_calls={bool(message.tool_calls)}, content={bool(message.content)}", flush=True)
                        if message.tool_calls:
                            print(f"[DEBUG] Tool calls: {[tc.function.name for tc in message.tool_calls]}", flush=True)

                        import hindsight_litellm
                        debug_info = hindsight_litellm.get_last_injection_debug()
                        print(f"[DEBUG] Building raw messages from {len(pending['messages'])} messages...", flush=True)

                        # Build raw prompt - the actual messages sent to LLM
                        raw_messages = []
                        for i, msg in enumerate(pending["messages"]):
                            raw_msg = {"role": msg.get("role", "")}
                            if msg.get("content"):
                                raw_msg["content"] = msg.get("content")
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

                        # Include tools in the raw prompt
                        raw_prompt = {
                            "messages": raw_messages,
                            "tools": [{"name": t["function"]["name"], "description": t["function"]["description"]} for t in TOOL_DEFINITIONS]
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

                                # Log tool execution to action log
                                t_tool_start = timer.time()
                                result = execute_tool(tools, tool_name, arguments)
                                t_tool_end = timer.time()

                                # Check if any memories were stored (retain was called)
                                new_memories = memory.get_recent_memories()
                                if new_memories:
                                    st.session_state.current_actions.append(("⏳ status", f"Storing {len(new_memories)} memory(ies) to Hindsight..."))
                                    for mem in new_memories:
                                        st.session_state.stored_memories.append(mem)
                                        st.session_state.current_actions.append(("🧠 memory", f"Stored: {mem}"))
                                memory.clear_recent_memories()

                                tool_results.append({
                                    "tool_call_id": tool_call.id,
                                    "role": "tool",
                                    "content": result
                                })

                                st.session_state.agent_floor = agent.state.floor
                                st.session_state.agent_side = agent.state.side.value
                                st.session_state.current_actions.append((tool_name, result))

                                if "SUCCESS!" in result:
                                    pending["complete"] = True
                                    st.session_state.deliveries_completed += 1
                                    st.session_state.has_package = False
                                    st.session_state.total_steps += agent.state.steps_taken
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
                            # LLM returned text without tool calls - log it and continue
                            if message.content:
                                st.session_state.current_actions.append(("💬 response", message.content))
                            pending["messages"].append({"role": "assistant", "content": message.content})
                            # Add a nudge to use tools
                            pending["messages"].append({"role": "user", "content": "Please use one of the available tools to continue the delivery."})

                    except Exception as e:
                        import traceback
                        st.error(f"❌ Error: {e}")
                        st.code(traceback.format_exc(), language=None)
                        pending["complete"] = True
                        st.session_state.pending_delivery = None

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

        st.metric("Memories Stored", len(st.session_state.stored_memories))

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
            st.line_chart(steps_history, use_container_width=True)

    # LLM Debug Section (collapsible) - full width at bottom
    if st.session_state.llm_messages:
        with st.expander("🤖 LLM Prompt & Response", expanded=False):
            for entry in st.session_state.llm_messages[-5:]:
                step_num = entry.get("step", "?")
                with st.expander(f"**Step {step_num}**", expanded=False):
                    # Raw Prompt
                    st.markdown("**📤 Raw Prompt:**")
                    raw_prompt = entry.get("raw_prompt", "")
                    st.code(raw_prompt, language="json")

                    st.divider()

                    # Raw Response
                    st.markdown("**📥 Raw Response:**")
                    raw_response = entry.get("raw_response", "")
                    st.code(raw_response, language="json")


if __name__ == "__main__":
    main()
