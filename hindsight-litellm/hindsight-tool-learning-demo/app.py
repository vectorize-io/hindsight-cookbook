"""
Tool Learning Demo - Incremental Learning with Hindsight

Interactive demo showing how an LLM learns correct tool selection over time.
Customers come in sequentially, both LLMs route them, and the Hindsight version
automatically learns from feedback after each interaction.

Uses hindsight_litellm exclusively for all Hindsight operations:
- LLM calls via hindsight_litellm.completion
- Memory recall via hindsight_litellm.recall
- Memory storage via hindsight_litellm.retain

Run with: streamlit run app.py
"""

import os
import json
import time
import uuid
import streamlit as st
from datetime import datetime
from typing import Dict, Any, List, Optional

import hindsight_litellm
from hindsight_litellm import configure, recall, retain, reflect, completion, enable, disable, is_enabled, get_last_injection_debug

# ============================================================================
# PAGE CONFIG
# ============================================================================

st.set_page_config(
    page_title="Tool Learning Demo - Hindsight",
    page_icon="🔧",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ============================================================================
# CONSTANTS
# ============================================================================

AVAILABLE_MODELS = {
    "OpenAI": ["gpt-4o", "gpt-4o-mini", "gpt-4-turbo"],
    "Anthropic": ["claude-3-5-sonnet-20241022", "claude-3-5-haiku-20241022"],
    "Groq": ["groq/llama-3.1-70b-versatile", "groq/llama-3.1-8b-instant"],
}

# THREE Tool definitions - regional offices with ambiguous names
TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "route_to_downtown_office",
            "description": "Routes the customer request to the Downtown Office.",
            "parameters": {
                "type": "object",
                "properties": {
                    "reasoning": {"type": "string", "description": "Your reasoning for why this office is appropriate for this request"},
                    "request_summary": {"type": "string", "description": "Brief summary of the customer's issue"}
                },
                "required": ["reasoning", "request_summary"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "route_to_riverside_branch",
            "description": "Routes the customer request to the Riverside Branch.",
            "parameters": {
                "type": "object",
                "properties": {
                    "reasoning": {"type": "string", "description": "Your reasoning for why this office is appropriate for this request"},
                    "request_summary": {"type": "string", "description": "Brief summary of the customer's issue"}
                },
                "required": ["reasoning", "request_summary"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "route_to_harbor_center",
            "description": "Routes the customer request to the Harbor Center.",
            "parameters": {
                "type": "object",
                "properties": {
                    "reasoning": {"type": "string", "description": "Your reasoning for why this office is appropriate for this request"},
                    "request_summary": {"type": "string", "description": "Brief summary of the customer's issue"}
                },
                "required": ["reasoning", "request_summary"]
            }
        }
    }
]

# Ground truth (hidden from LLM) - which office handles what
CORRECT_ROUTING = {
    "financial": "route_to_downtown_office",   # Billing, refunds, payments
    "security": "route_to_riverside_branch",   # Account access, password, security
    "technical": "route_to_harbor_center",     # Bugs, features, errors
}

OFFICE_INFO = {
    "route_to_downtown_office": {"name": "Downtown Office", "handles": "💰 Financial (billing, refunds, payments)", "color": "#4CAF50"},
    "route_to_riverside_branch": {"name": "Riverside Branch", "handles": "🔐 Security (account access, passwords)", "color": "#FF9800"},
    "route_to_harbor_center": {"name": "Harbor Center", "handles": "🔧 Technical (bugs, features, errors)", "color": "#2196F3"},
}

# Functions to load and randomize customers from JSON file
def load_customers_from_json():
    """Load customers from JSON file."""
    import os
    json_path = os.path.join(os.path.dirname(__file__), "customers.json")
    with open(json_path, "r") as f:
        data = json.load(f)
    return data["customers"]


def get_randomized_customers(count: int, seed: int = None) -> List[Dict]:
    """Get a randomized list of customers with assigned IDs.

    Args:
        count: Number of customers to return
        seed: Optional seed for reproducible randomization

    Returns:
        List of customer dicts with 'id', 'type', 'name', 'issue' keys
    """
    import random
    customers = load_customers_from_json()

    if seed is not None:
        random.seed(seed)

    # Shuffle and take the requested count (with repetition if needed)
    if count <= len(customers):
        selected = random.sample(customers, count)
    else:
        # If we need more than available, repeat with shuffling
        selected = []
        while len(selected) < count:
            shuffled = customers.copy()
            random.shuffle(shuffled)
            selected.extend(shuffled)
        selected = selected[:count]

    # Assign sequential IDs
    return [{"id": i + 1, **customer} for i, customer in enumerate(selected)]

SYSTEM_PROMPT = """You are a customer service routing agent. Based on the user's issue, route them to an office. Do your best to pick the correct office. Always route the user somewhere.

Available offices:
- route_to_downtown_office: Downtown Office
- route_to_riverside_branch: Riverside Branch
- route_to_harbor_center: Harbor Center

You must call exactly one routing function for each request."""

# ============================================================================
# SESSION STATE
# ============================================================================

# Default bank background - tells Hindsight what's important to remember
#
# SIMPLE BACKGROUND OPTIONS (uncomment one to try):
#
# Option 1: Ultra-minimal
# DEFAULT_BANK_BACKGROUND = """Remember customer feedback about routing."""
#
# Option 2: Slightly more context
# DEFAULT_BANK_BACKGROUND = """This is a customer service routing system. Remember what works and what doesn't."""
#
# Option 3: Task-focused
# DEFAULT_BANK_BACKGROUND = """Learn which office handles which type of customer issue based on feedback."""
#
# Option 4: Current (detailed/overfitted) - saved for reference
# DETAILED_BANK_BACKGROUND = """You are the memory system for a customer service routing assistant.
#
# The assistant routes customer requests to one of three regional offices:
# - Downtown Office
# - Riverside Branch
# - Harbor Center
#
# The office names don't indicate what they handle - the assistant must learn from customer feedback.
#
# When the assistant receives a new request, it asks: "What do I know about routing this type of issue?"
#
# Your job is to remember past routing outcomes so the assistant can make better decisions.
# Focus on: what type of issue did the customer have, and which office successfully handled it (or failed to handle it).
#
# IMPORTANT:
# - If you have NO memories at all, say "No relevant memories found."
# - If you have memories about similar issues, recommend accordingly.
# - If an office got NEGATIVE feedback for an issue type (customer was transferred elsewhere), do NOT recommend that office for similar issues.
# - Be concise: state which office handles which issue type based on actual feedback."""

# No bank background - let the memories speak for themselves
DEFAULT_BANK_BACKGROUND = None


def init_session_state():
    if "bank_id" not in st.session_state:
        st.session_state.bank_id = f"tool-demo-{uuid.uuid4().hex[:8]}"
        st.session_state.bank_configured = False  # Track if bank background has been set
    if "bank_background" not in st.session_state:
        st.session_state.bank_background = DEFAULT_BANK_BACKGROUND
    if "customer_index" not in st.session_state:
        st.session_state.customer_index = 0
    if "history" not in st.session_state:
        st.session_state.history = []
    if "last_results" not in st.session_state:
        st.session_state.last_results = None
    # Randomized customer queue for interactive demo (12 customers to match original)
    if "customer_queue" not in st.session_state:
        st.session_state.customer_queue = get_randomized_customers(12)
    # Looped demo state
    if "loop_results" not in st.session_state:
        st.session_state.loop_results = []
    if "loop_running" not in st.session_state:
        st.session_state.loop_running = False
    if "loop_completed" not in st.session_state:
        st.session_state.loop_completed = False
    if "loop_paused" not in st.session_state:
        st.session_state.loop_paused = False
    if "loop_customers" not in st.session_state:
        st.session_state.loop_customers = []  # The randomized customer list for current loop
    if "loop_num_customers" not in st.session_state:
        st.session_state.loop_num_customers = 0  # Target number of customers for current loop
    if "loop_should_start" not in st.session_state:
        st.session_state.loop_should_start = False  # Flag to trigger loop start after rerun

# ============================================================================
# HINDSIGHT LITELLM FUNCTIONS
# ============================================================================

def configure_hindsight(
    api_url: str,
    bank_id: str,
    store_conversations: bool = False,
    inject_memories: bool = True,
    use_reflect: bool = True,
    with_background: bool = False,
):
    """Configure hindsight_litellm with the given settings.

    Args:
        api_url: Hindsight API URL
        bank_id: Memory bank ID
        store_conversations: Whether to auto-store conversations via callbacks
        inject_memories: Whether to auto-inject memories into prompts
        use_reflect: Use reflect API (synthesized answer) instead of recall (raw facts)
        with_background: Whether to set bank background instructions
    """
    # Use session state background if available, otherwise use default
    background_text = st.session_state.get("bank_background", DEFAULT_BANK_BACKGROUND) if with_background else None
    configure(
        hindsight_api_url=api_url,
        bank_id=bank_id,
        store_conversations=store_conversations,
        inject_memories=inject_memories,
        use_reflect=use_reflect,  # NEW: Use reflect instead of recall for injection
        # max_memories not set = no limit (use all results from API)
        recall_budget="high",
        max_memory_tokens=100000,  # Allow up to 100k tokens for memory context (gpt-4o supports 128k)
        verbose=False,
        # Only set background on first configure to avoid repeated API calls
        background=background_text,
        bank_name="Customer Service Routing Agent" if with_background else None,
    )


def recall_memories(api_url: str, bank_id: str, query: str) -> Dict[str, Any]:
    """Recall memories using hindsight_litellm."""
    try:
        configure_hindsight(api_url, bank_id, store_conversations=False)

        results = recall(query=query)

        if results:
            return {
                "success": True,
                "memories": results,
                "memories_text": "\n".join([f"- {r.text}" for r in results]),
                "count": len(results),
            }
        return {"success": True, "memories": [], "memories_text": "", "count": 0}

    except Exception as e:
        return {"success": False, "error": str(e), "memories": [], "memories_text": "", "count": 0}


def route_without_memory(model: str, customer_name: str, customer_issue: str) -> Dict[str, Any]:
    """Route request WITHOUT any memory - pure LLM reasoning using hindsight_litellm.completion."""
    import random
    try:
        # Make sure hindsight is disabled for this call
        if is_enabled():
            disable()

        # Shuffle tools to remove positional bias (LLMs tend to favor tools listed earlier)
        shuffled_tools = TOOLS.copy()
        random.shuffle(shuffled_tools)

        user_message = f"{customer_name}: {customer_issue}"

        response = completion(
            model=model,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_message}
            ],
            tools=shuffled_tools,
            tool_choice="required",
            temperature=0.7,
        )

        if response.choices[0].message.tool_calls:
            tool_call = response.choices[0].message.tool_calls[0]
            return {
                "success": True,
                "tool": tool_call.function.name,
                "args": json.loads(tool_call.function.arguments),
                "system_prompt": SYSTEM_PROMPT,
                "user_message": user_message,
            }
        return {"success": False, "tool": None, "error": "No tool called", "system_prompt": SYSTEM_PROMPT, "user_message": user_message}

    except Exception as e:
        return {"success": False, "tool": None, "error": str(e)}


def route_with_hindsight(model: str, customer_name: str, customer_issue: str, api_url: str, bank_id: str) -> Dict[str, Any]:
    """Route request WITH Hindsight memory - learns from past interactions.

    Uses automatic injection via hindsight_litellm.enable() with use_reflect=False (recall mode).
    Debug info is retrieved via get_last_injection_debug() for display.

    Storage is NOT enabled here - we store after feedback is received.
    """
    try:
        # Configure hindsight with automatic injection using recall mode
        configure(
            hindsight_api_url=api_url,
            bank_id=bank_id,
            store_conversations=False,
            inject_memories=True,  # Automatic injection
            use_reflect=False,  # Use recall API for raw facts
            verbose=True,  # Enable debug info capture
            # max_memories not set = no limit (use all results from API)
            recall_budget="high",
            max_memory_tokens=100000,  # Allow up to 100k tokens for memory context
        )

        # Enable the integration for automatic injection
        enable()

        user_message = f"{customer_name}: {customer_issue}"

        # Call LLM - injection happens automatically via the wrapper
        response = completion(
            model=model,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_message}
            ],
            tools=TOOLS,
            tool_choice="required",
            temperature=0.7,
        )

        # Disable after the call
        disable()

        # Get debug info from the automatic injection
        injection_debug = get_last_injection_debug()

        # Extract debug info for display
        reflect_text = ""
        memory_context = ""
        injection_mode = "reflect"
        memories_used = 0

        if injection_debug:
            reflect_text = injection_debug.reflect_text or ""
            memory_context = injection_debug.memory_context or ""
            injection_mode = injection_debug.mode
            memories_used = 1 if injection_debug.injected else 0

        # Build the full system prompt for debug display
        # (This shows what was actually sent to the LLM)
        enhanced_prompt = SYSTEM_PROMPT
        if memory_context:
            enhanced_prompt += f"\n\n{memory_context}"

        if response.choices[0].message.tool_calls:
            tool_call = response.choices[0].message.tool_calls[0]
            tool_name = tool_call.function.name
            tool_args = json.loads(tool_call.function.arguments)

            return {
                "success": True,
                "tool": tool_name,
                "args": tool_args,
                "memories_used": memories_used,
                "reflect_text": reflect_text,
                "system_prompt": enhanced_prompt,  # Full prompt with injected context
                "user_message": user_message,
                "injection_mode": injection_mode,
                "injection_debug": injection_debug,  # Full debug info object
            }
        return {
            "success": False,
            "tool": None,
            "error": "No tool called",
            "system_prompt": enhanced_prompt,
            "user_message": user_message,
            "injection_debug": injection_debug,
        }

    except Exception as e:
        return {"success": False, "tool": None, "error": str(e)}


def store_feedback(model: str, api_url: str, bank_id: str, customer: Dict, routed_to: str, was_correct: bool) -> Dict[str, Any]:
    """Store the routing interaction with feedback to Hindsight.

    Uses hindsight_litellm.retain() to store the conversation to memory.
    """
    try:
        correct_office = CORRECT_ROUTING[customer["type"]]
        routed_info = OFFICE_INFO.get(routed_to, {"name": "Unknown"})
        correct_info = OFFICE_INFO[correct_office]

        customer_name = customer["name"]
        original_issue = customer['issue']
        issue_type = customer["type"]  # financial, security, technical

        # Build the conversation that happened - natural and sparse
        user_issue = f"{customer_name}: {original_issue}"
        routing_response = f"I'll route you to {routed_info['name']}."

        # Natural feedback - like a real customer would say (include customer name for context)
        if was_correct:
            customer_feedback = f"{customer_name}: Thanks! {routed_info['name']} was able to help me with my {issue_type} issue."
        else:
            customer_feedback = f"{customer_name}: Hey, so you sent me to {routed_info['name']} but they transferred me to {correct_info['name']} who actually handled my {issue_type} issue. Just wanted to let you know for next time!"

        # Build the full conversation text
        conversation_text = f"""USER: {user_issue}

ASSISTANT: {routing_response}

USER: {customer_feedback}"""

        # Store using hindsight_litellm.retain()
        # Configure hindsight_litellm with the API URL and bank_id
        configure(
            hindsight_api_url=api_url,
            bank_id=bank_id,
            store_conversations=False,
            inject_memories=False,
        )

        result = retain(
            content=conversation_text,
            context="customer feedback about which office handles which issue type",
        )

        agent_response = "Thank you for the feedback."

        # Build display version
        full_conversation = f"""USER: {user_issue}

A: {routing_response}

USER: {customer_feedback}

A: {agent_response}"""

        return {
            "success": result.success if result else False,
            "feedback": customer_feedback,
            "full_conversation": full_conversation,
            "response": agent_response,
        }

    except Exception as e:
        import traceback
        return {"success": False, "error": str(e), "traceback": traceback.format_exc()}


# ============================================================================
# UI
# ============================================================================

def render_sidebar():
    st.sidebar.title("⚙️ Configuration")

    provider = st.sidebar.selectbox("Provider", list(AVAILABLE_MODELS.keys()))
    model = st.sidebar.selectbox("Model", AVAILABLE_MODELS[provider])

    st.sidebar.markdown("---")
    api_url = st.sidebar.text_input("Hindsight URL", value="http://localhost:8888")
    st.sidebar.markdown("**Bank:**")
    st.sidebar.code(st.session_state.bank_id, language=None)

    # Bank Background configuration
    with st.sidebar.expander("📝 Bank Background", expanded=False):
        st.caption("Instructions that help Hindsight understand what to remember")
        new_background = st.text_area(
            "Background",
            value=st.session_state.bank_background,
            height=200,
            label_visibility="collapsed",
        )
        if new_background != st.session_state.bank_background:
            st.session_state.bank_background = new_background
            st.session_state.bank_configured = False  # Trigger reconfiguration
            st.rerun()
        if st.button("Reset to Default", use_container_width=True, type="secondary"):
            st.session_state.bank_background = DEFAULT_BANK_BACKGROUND
            st.session_state.bank_configured = False
            st.rerun()

    st.sidebar.markdown("---")
    if st.sidebar.button("🔄 Reset Demo", use_container_width=True):
        # Clear memories from Hindsight
        try:
            import requests
            requests.delete(f"{api_url}/v1/default/banks/{st.session_state.bank_id}/memories", timeout=5)
        except:
            pass
        st.session_state.bank_id = f"tool-demo-{uuid.uuid4().hex[:8]}"
        st.session_state.bank_configured = False  # Reset so new bank gets background configured
        st.session_state.customer_index = 0
        st.session_state.history = []
        st.session_state.last_results = None
        # Reset looped demo state
        st.session_state.loop_results = []
        st.session_state.loop_running = False
        st.session_state.loop_completed = False
        st.session_state.loop_paused = False
        # Re-randomize customers for both demos
        st.session_state.customer_queue = get_randomized_customers(12)
        # Clear feedback keys
        keys_to_delete = [k for k in st.session_state.keys() if k.startswith("feedback_")]
        for k in keys_to_delete:
            del st.session_state[k]
        st.rerun()

    if st.sidebar.button("🧹 Clear Hindsight Memories", use_container_width=True, type="secondary"):
        try:
            import requests
            response = requests.delete(f"{api_url}/v1/default/banks/{st.session_state.bank_id}/memories", timeout=5)
            if response.status_code == 200:
                st.sidebar.success("Memories cleared!")
            else:
                st.sidebar.warning(f"Status: {response.status_code}")
        except Exception as e:
            st.sidebar.error(f"Error: {e}")

    # Stats
    if st.session_state.history:
        st.sidebar.markdown("---")
        st.sidebar.markdown("### 📊 Running Stats")
        total = len(st.session_state.history)
        no_mem_correct = sum(1 for h in st.session_state.history if h["no_memory_correct"])
        with_mem_correct = sum(1 for h in st.session_state.history if h["with_memory_correct"])

        st.sidebar.metric("Without Memory", f"{no_mem_correct}/{total} ({100*no_mem_correct//total}%)")
        st.sidebar.metric("With Hindsight", f"{with_mem_correct}/{total} ({100*with_mem_correct//total}%)")

        if with_mem_correct > no_mem_correct:
            st.sidebar.success(f"🎯 Hindsight is +{with_mem_correct - no_mem_correct} ahead!")

    return {"model": model, "api_url": api_url}


def render_office_legend():
    """Show the hidden ground truth."""
    st.markdown("#### 🎯 Ground Truth (Hidden from LLM)")
    cols = st.columns(3)
    for i, (office, info) in enumerate(OFFICE_INFO.items()):
        with cols[i]:
            st.markdown(f"""
            <div style="background: {info['color']}22; border-left: 4px solid {info['color']};
                        padding: 10px; border-radius: 5px; font-size: 13px;">
                <strong>{info['name']}</strong><br/>
                <span style="font-size: 12px;">{info['handles']}</span>
            </div>
            """, unsafe_allow_html=True)


def render_customer_card(customer: Dict):
    """Render the current customer's issue."""
    type_emoji = {"financial": "💰", "security": "🔐", "technical": "🔧"}[customer["type"]]

    st.markdown(f"""
    <div style="background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                padding: 20px; border-radius: 15px; color: white; margin: 15px 0;">
        <div style="display: flex; align-items: center; gap: 15px;">
            <div style="font-size: 50px;">👤</div>
            <div>
                <h2 style="margin: 0; color: white;">Customer #{customer['id']}: {customer['name']}</h2>
                <p style="margin: 5px 0 0 0; opacity: 0.9;">
                    {type_emoji} <strong>{customer['type'].upper()}</strong> issue (hidden from LLM)
                </p>
            </div>
        </div>
        <div style="margin-top: 15px; padding: 15px; background: rgba(255,255,255,0.15);
                    border-radius: 10px; font-size: 16px; line-height: 1.5;">
            "{customer['issue']}"
        </div>
    </div>
    """, unsafe_allow_html=True)


def render_results(no_mem_result: Dict, with_mem_result: Dict, correct_office: str, customer: Dict):
    """Render side-by-side routing results."""
    col1, col2 = st.columns(2)

    for col, result, title, color, is_hindsight in [
        (col1, no_mem_result, "Without Memory", "#9E9E9E", False),
        (col2, with_mem_result, "With Hindsight 🧠", "#2196F3", True)
    ]:
        with col:
            tool = result.get("tool", "None")
            is_correct = tool == correct_office
            status = "✅ Correct!" if is_correct else "❌ Wrong office"
            status_color = "#4CAF50" if is_correct else "#f44336"

            office_info = OFFICE_INFO.get(tool, {"name": "?", "color": "#999"})

            st.markdown(f"""
            <div style="border: 3px solid {color}; border-radius: 15px; padding: 20px;">
                <h3 style="color: {color}; margin-top: 0;">{title}</h3>
                <div style="background: #f8f9fa; padding: 15px; border-radius: 10px; margin: 10px 0;">
                    <p style="margin: 0 0 5px 0; font-size: 13px; color: #666;">Routed to:</p>
                    <code style="font-size: 14px; background: {office_info['color']}22;
                                 padding: 5px 10px; border-radius: 5px;">{tool}</code>
                </div>
                <div style="padding: 12px; background: {status_color}15; border-left: 4px solid {status_color};
                            border-radius: 5px; margin-top: 10px;">
                    <span style="font-size: 18px;">{status}</span>
                </div>
            </div>
            """, unsafe_allow_html=True)

            # Debug expander
            with st.expander("🔍 Debug Info", expanded=False):
                # Show injection status for Hindsight
                if is_hindsight:
                    injection_debug = result.get("injection_debug")

                    if injection_debug:
                        if injection_debug.injected:
                            st.success(f"✅ Memory injected via `{injection_debug.mode}` mode")
                        elif injection_debug.error:
                            st.error(f"❌ Error: {injection_debug.error}")
                        else:
                            st.warning("⚠️ No relevant memories found (bank may be empty or query didn't match)")

                        # Show memory count for recall mode
                        if hasattr(injection_debug, 'results_count') and injection_debug.results_count:
                            st.markdown(f"**Facts retrieved:** {injection_debug.results_count}")

                        # Show reflect facts if available (collapsible)
                        if hasattr(injection_debug, 'reflect_facts') and injection_debug.reflect_facts:
                            with st.expander(f"📚 Facts Used by Reflect ({len(injection_debug.reflect_facts)} facts)", expanded=False):
                                for i, fact in enumerate(injection_debug.reflect_facts, 1):
                                    fact_text = fact.get('text', str(fact))
                                    fact_type = fact.get('type', 'unknown')
                                    st.markdown(f"{i}. **[{fact_type}]** {fact_text}")
                        elif injection_debug.mode == "reflect":
                            st.info("ℹ️ No facts returned by reflect (bank may be empty)")
                    st.markdown("---")

                # Show the FULL prompt sent to LLM - use actual values from result
                st.markdown("**📤 Full Prompt Sent to LLM:**")

                system_prompt = result.get("system_prompt", SYSTEM_PROMPT)
                user_message = result.get("user_message", customer['issue'])

                # Format as the actual messages array
                full_prompt = f"""[SYSTEM]
{system_prompt}

[USER]
{user_message}

[TOOLS]
- route_to_downtown_office
- route_to_riverside_branch
- route_to_harbor_center
(tool_choice: required)"""

                st.code(full_prompt, language=None)

                # Show tool call result
                st.markdown("---")
                st.markdown("**📥 LLM Response (Tool Call):**")
                st.json({"function": tool, "arguments": result.get("args", {})})


def render_feedback(customer: Dict, no_mem_result: Dict, with_mem_result: Dict):
    """Show simulated customer feedback."""
    correct_office = CORRECT_ROUTING[customer["type"]]
    no_correct = no_mem_result.get("tool") == correct_office
    with_correct = with_mem_result.get("tool") == correct_office

    # Get office info for feedback messages
    no_mem_routed = no_mem_result.get("tool", "unknown")
    with_mem_routed = with_mem_result.get("tool", "unknown")
    no_mem_info = OFFICE_INFO.get(no_mem_routed, {"name": "Unknown"})
    with_mem_info = OFFICE_INFO.get(with_mem_routed, {"name": "Unknown"})
    correct_info = OFFICE_INFO[correct_office]
    issue_type = customer["type"]

    st.markdown("### 💬 Customer Feedback")
    col1, col2 = st.columns(2)

    # Feedback messages that clearly state the routing rule
    with col1:
        if no_correct:
            st.success(f'**{customer["name"]}**: "Thanks! {no_mem_info["name"]} handled my {issue_type} issue."')
        else:
            st.error(f'**{customer["name"]}**: "Wrong! {no_mem_info["name"]} can\'t help with {issue_type}. Go to {correct_info["name"]}."')

    with col2:
        if with_correct:
            st.success(f'**{customer["name"]}**: "Thanks! {with_mem_info["name"]} handled my {issue_type} issue."')
        else:
            st.error(f'**{customer["name"]}**: "Wrong! {with_mem_info["name"]} can\'t help with {issue_type}. Go to {correct_info["name"]}."')

    return no_correct, with_correct


def render_history():
    """Render accuracy chart."""
    if len(st.session_state.history) < 2:
        return

    st.markdown("---")
    st.markdown("### 📈 Accuracy Over Time")

    import pandas as pd

    no_mem_running = []
    with_mem_running = []

    for i in range(1, len(st.session_state.history) + 1):
        no_mem_running.append(100 * sum(1 for h in st.session_state.history[:i] if h["no_memory_correct"]) / i)
        with_mem_running.append(100 * sum(1 for h in st.session_state.history[:i] if h["with_memory_correct"]) / i)

    df = pd.DataFrame({
        "Customer": list(range(1, len(st.session_state.history) + 1)),
        "Without Memory (%)": no_mem_running,
        "With Hindsight (%)": with_mem_running,
    }).set_index("Customer")

    st.line_chart(df, color=["#9E9E9E", "#2196F3"])

    # Reference line note
    st.caption("📊 Random guessing with 3 offices = ~33% accuracy. Watch Hindsight improve!")


# ============================================================================
# LOOPED DEMO
# ============================================================================

def run_looped_demo(
    model: str,
    api_url: str,
    bank_id: str,
    customers: List[Dict],
    start_index: int = 0,
    existing_results: Optional[List[Dict]] = None,
    clear_memories: bool = True,
):
    """Run multiple customers in a loop with Hindsight only.

    Args:
        model: Model to use for routing
        api_url: Hindsight API URL
        bank_id: Memory bank ID
        customers: List of customer dicts to process
        start_index: Index to start from (for resume support)
        existing_results: Previously collected results (for resume support)
        clear_memories: Whether to clear memories at start (False for resume)
    """
    results = list(existing_results) if existing_results else []

    # Clear memories for a fresh start (but not when resuming)
    if clear_memories:
        try:
            import requests
            requests.delete(f"{api_url}/v1/default/banks/{bank_id}/memories", timeout=5)
        except:
            pass

    # Configure bank with background (using recall mode, not reflect)
    configure_hindsight(
        api_url=api_url,
        bank_id=bank_id,
        store_conversations=False,
        with_background=True,
        use_reflect=False,  # Use recall API for raw facts like interactive demo
    )

    for i, customer in enumerate(customers[start_index:], start=start_index):
        correct_office = CORRECT_ROUTING[customer["type"]]

        # Route with Hindsight
        result = route_with_hindsight(model, customer["name"], customer["issue"], api_url, bank_id)

        routed_to = result.get("tool", "unknown")
        is_correct = routed_to == correct_office

        # Store feedback
        store_result = store_feedback(model, api_url, bank_id, customer, routed_to, is_correct)

        # Wait for indexing (shorter wait for looped demo)
        time.sleep(3)

        results.append({
            "customer": customer,
            "result": result,
            "routed_to": routed_to,
            "correct_office": correct_office,
            "is_correct": is_correct,
            "store_result": store_result,
        })

        yield results  # Yield intermediate results for live updates


def render_looped_demo(config: Dict):
    """Render the looped customer demo tab."""
    st.markdown("### 🔄 Looped Customer Demo")
    st.markdown("""
    Run 30 customers back-to-back with Hindsight learning from each interaction.
    Each customer's logs are shown in a collapsible section.
    """)

    st.markdown("---")
    render_office_legend()
    st.markdown("---")

    # Controls
    col1, col2, col3 = st.columns([2, 1, 1])
    with col1:
        num_customers = st.slider("Number of customers", min_value=5, max_value=100, value=30, step=5)
    with col2:
        # Use a session state flag to track if we need to start the loop
        # This allows us to set loop_running=True BEFORE rendering buttons
        start_clicked = st.button("🚀 Start Loop", type="primary", use_container_width=True,
                                   disabled=st.session_state.loop_running)
        if start_clicked:
            # Set loop_running immediately and rerun so buttons render correctly
            st.session_state.loop_running = True
            st.session_state.loop_results = []
            st.session_state.loop_completed = False
            st.session_state.loop_paused = False
            st.session_state.loop_num_customers = num_customers
            st.session_state.loop_customers = get_randomized_customers(num_customers)
            st.session_state.loop_should_start = True  # Flag to actually run the loop
            st.rerun()
    with col3:
        # Pause/Resume button (only enabled when loop is running)
        if st.session_state.loop_running:
            if st.session_state.loop_paused:
                if st.button("▶️ Resume", type="secondary", use_container_width=True):
                    st.session_state.loop_paused = False
                    st.rerun()
            else:
                if st.button("⏸️ Pause", type="secondary", use_container_width=True):
                    st.session_state.loop_paused = True
                    st.rerun()
        else:
            st.button("⏸️ Pause", type="secondary", use_container_width=True, disabled=True)

    # Show paused state with current results
    if st.session_state.loop_paused and st.session_state.loop_results:
        results = st.session_state.loop_results
        completed = len(results)
        total = st.session_state.loop_num_customers

        st.warning(f"⏸️ **PAUSED** after {completed}/{total} customers. Click Resume to continue.")

        # Stats
        if results:
            correct_count = sum(1 for r in results if r["is_correct"])
            st.markdown(f"### 📊 Progress: {completed}/{total} customers processed")

            col1, col2, col3 = st.columns(3)
            col1.metric("Completed", f"{completed}/{total}")
            col2.metric("Correct", f"{correct_count}/{completed}")
            col3.metric("Accuracy", f"{100*correct_count//completed}%")

            # Accuracy chart
            if completed >= 2:
                import pandas as pd
                running_accuracy = []
                for i in range(1, completed + 1):
                    acc = 100 * sum(1 for r in results[:i] if r["is_correct"]) / i
                    running_accuracy.append(acc)

                df = pd.DataFrame({
                    "Customer": list(range(1, completed + 1)),
                    "Accuracy (%)": running_accuracy,
                }).set_index("Customer")

                st.line_chart(df, color=["#2196F3"])

            st.markdown("---")
            st.markdown("### 📋 Customer Logs")

            # Render each customer result in a collapsible expander
            for i, r in enumerate(results):
                customer = r["customer"]
                is_correct = r["is_correct"]
                routed_to = r["routed_to"]
                correct_office = r["correct_office"]
                result = r["result"]

                type_emoji = {"financial": "💰", "security": "🔐", "technical": "🔧"}[customer["type"]]
                status_emoji = "✅" if is_correct else "❌"
                routed_info = OFFICE_INFO.get(routed_to, {"name": "Unknown"})
                correct_info = OFFICE_INFO[correct_office]

                expander_title = f"{status_emoji} Customer #{customer['id']}: {customer['name']} ({type_emoji} {customer['type']}) → {routed_info['name']}"

                with st.expander(expander_title, expanded=False):
                    st.markdown(f"**Issue:** {customer['issue']}")
                    st.markdown(f"**Routed to:** `{routed_to}` ({routed_info['name']})")
                    st.markdown(f"**Correct office:** `{correct_office}` ({correct_info['name']})")

                    if is_correct:
                        st.success("Correct routing!")
                    else:
                        st.error(f"Wrong! Should have been {correct_info['name']}")

    # Show completed results (only when not actively running - those are streamed)
    if st.session_state.loop_completed and not st.session_state.loop_running:
        results = st.session_state.loop_results
        total = len(results)  # Use actual count since loop is done
        completed = len(results)

        # Stats
        if results:
            correct_count = sum(1 for r in results if r["is_correct"])
            st.markdown(f"### 📊 Results: {completed} customers")

            col1, col2, col3 = st.columns(3)
            col1.metric("Completed", f"{completed}")
            col2.metric("Correct", f"{correct_count}/{completed}")
            col3.metric("Accuracy", f"{100*correct_count//completed}%")

            # Accuracy chart
            if completed >= 2:
                import pandas as pd
                running_accuracy = []
                for i in range(1, completed + 1):
                    acc = 100 * sum(1 for r in results[:i] if r["is_correct"]) / i
                    running_accuracy.append(acc)

                df = pd.DataFrame({
                    "Customer": list(range(1, completed + 1)),
                    "Accuracy (%)": running_accuracy,
                }).set_index("Customer")

                st.line_chart(df, color=["#2196F3"])
                st.caption("📈 Accuracy over time — watch Hindsight learn!")

            st.markdown("---")
            st.markdown("### 📋 Customer Logs")

            # Render each customer result in a collapsible expander
            for i, r in enumerate(results):
                customer = r["customer"]
                is_correct = r["is_correct"]
                routed_to = r["routed_to"]
                correct_office = r["correct_office"]
                result = r["result"]

                type_emoji = {"financial": "💰", "security": "🔐", "technical": "🔧"}[customer["type"]]
                status_emoji = "✅" if is_correct else "❌"
                routed_info = OFFICE_INFO.get(routed_to, {"name": "Unknown"})
                correct_info = OFFICE_INFO[correct_office]

                expander_title = f"{status_emoji} Customer #{customer['id']}: {customer['name']} ({type_emoji} {customer['type']}) → {routed_info['name']}"

                with st.expander(expander_title, expanded=False):
                    st.markdown(f"**Issue:** {customer['issue']}")
                    st.markdown(f"**Routed to:** `{routed_to}` ({routed_info['name']})")
                    st.markdown(f"**Correct office:** `{correct_office}` ({correct_info['name']})")

                    if is_correct:
                        st.success("Correct routing!")
                    else:
                        st.error(f"Wrong! Should have been {correct_info['name']}")

                    # Show injection debug info
                    injection_debug = result.get("injection_debug")
                    if injection_debug:
                        st.markdown("---")
                        st.markdown("**🧠 Memory Injection:**")
                        if injection_debug.injected:
                            st.success(f"Memory injected via `{injection_debug.mode}` mode")
                            if injection_debug.reflect_text:
                                st.markdown("**Reflect response:**")
                                st.info(injection_debug.reflect_text)
                        elif injection_debug.error:
                            st.error(f"Error: {injection_debug.error}")
                        else:
                            st.warning("No relevant memories found")

                        # Show facts used (for recall mode)
                        if hasattr(injection_debug, 'results_count') and injection_debug.results_count:
                            st.markdown(f"**Facts retrieved:** {injection_debug.results_count}")

                        # Show facts used (for reflect mode)
                        if hasattr(injection_debug, 'reflect_facts') and injection_debug.reflect_facts:
                            with st.expander(f"📚 Facts Used ({len(injection_debug.reflect_facts)} facts)", expanded=False):
                                for j, fact in enumerate(injection_debug.reflect_facts, 1):
                                    fact_text = fact.get('text', str(fact))
                                    fact_type = fact.get('type', 'unknown')
                                    st.markdown(f"{j}. **[{fact_type}]** {fact_text}")

                    # Show the FULL prompt sent to LLM
                    st.markdown("---")
                    st.markdown("**📤 Full Prompt Sent to LLM:**")

                    system_prompt = result.get("system_prompt", SYSTEM_PROMPT)
                    user_message = result.get("user_message", f"{customer['name']}: {customer['issue']}")

                    full_prompt = f"""[SYSTEM]
{system_prompt}

[USER]
{user_message}

[TOOLS]
- route_to_downtown_office
- route_to_riverside_branch
- route_to_harbor_center
(tool_choice: required)"""

                    st.code(full_prompt, language=None)

                    # Show tool call result
                    st.markdown("---")
                    st.markdown("**📥 LLM Response (Tool Call):**")
                    st.json({"function": routed_to, "arguments": result.get("args", {})})

                    # Show reasoning
                    if result.get("args", {}).get("reasoning"):
                        st.markdown("---")
                        st.markdown("**LLM Reasoning:**")
                        st.info(result["args"]["reasoning"])

    # Detect resume click (loop_paused was True, now it's False, and we have results)
    resume_clicked = (
        not st.session_state.loop_paused
        and st.session_state.loop_running
        and len(st.session_state.loop_results) > 0
        and len(st.session_state.loop_results) < st.session_state.loop_num_customers
    )

    # Check if we should start fresh (set by button click then rerun)
    should_start_fresh = st.session_state.loop_should_start
    if should_start_fresh:
        st.session_state.loop_should_start = False  # Clear the flag immediately

    # Run the loop (fresh start or resume)
    if should_start_fresh or resume_clicked:
        # Determine if this is a resume
        is_resume = resume_clicked
        start_index = len(st.session_state.loop_results) if is_resume else 0
        existing_results = st.session_state.loop_results if is_resume else None
        clear_memories = not is_resume

        progress_bar = st.progress(start_index / st.session_state.loop_num_customers if is_resume else 0)
        status_text = st.empty()
        if is_resume:
            status_text.markdown(f"**Resuming from customer #{start_index + 1}...**")

        # Containers for streaming results - use empty() for things that need to be replaced
        stats_placeholder = st.empty()
        chart_container = st.empty()
        st.markdown("---")
        st.markdown("### 📋 Customer Logs (Streaming)")
        results_container = st.container()

        # If resuming, show existing results first
        if is_resume and existing_results:
            for r in existing_results:
                customer = r["customer"]
                is_correct = r["is_correct"]
                routed_to = r["routed_to"]
                correct_office = r["correct_office"]
                type_emoji = {"financial": "💰", "security": "🔐", "technical": "🔧"}[customer["type"]]
                status_emoji = "✅" if is_correct else "❌"
                routed_info = OFFICE_INFO.get(routed_to, {"name": "Unknown"})
                expander_title = f"{status_emoji} Customer #{customer['id']}: {customer['name']} ({type_emoji} {customer['type']}) → {routed_info['name']}"
                with results_container:
                    with st.expander(expander_title, expanded=False):
                        st.markdown(f"**Issue:** {customer['issue']}")
                        st.markdown(f"**Routed to:** `{routed_to}` ({routed_info['name']})")
                        st.markdown(f"**Correct office:** `{correct_office}` ({OFFICE_INFO[correct_office]['name']})")
                        if is_correct:
                            st.success("Correct routing!")
                        else:
                            st.error(f"Wrong! Should have been {OFFICE_INFO[correct_office]['name']}")

        for results in run_looped_demo(
            config["model"],
            config["api_url"],
            st.session_state.bank_id,
            st.session_state.loop_customers,
            start_index=start_index,
            existing_results=existing_results,
            clear_memories=clear_memories,
        ):
            st.session_state.loop_results = results
            completed = len(results)
            total = st.session_state.loop_num_customers
            progress = completed / total
            progress_bar.progress(progress)

            latest = results[-1]
            status_emoji = "✅" if latest["is_correct"] else "❌"
            status_text.markdown(f"**Processing:** Customer #{latest['customer']['id']} - {latest['customer']['name']} {status_emoji}")

            # Check for pause - if paused, break out and wait for resume
            if st.session_state.loop_paused:
                status_text.markdown("**⏸️ PAUSED** - Click Resume to continue")
                st.rerun()  # Rerun to show pause state and update button

            # Update stats - use a container inside the placeholder to replace content
            correct_count = sum(1 for r in results if r["is_correct"])
            with stats_placeholder.container():
                col1, col2, col3 = st.columns(3)
                col1.metric("Completed", f"{completed}/{total}")
                col2.metric("Correct", f"{correct_count}/{completed}")
                col3.metric("Accuracy", f"{100*correct_count//completed}%")

            # Update chart
            if completed >= 2:
                import pandas as pd
                running_accuracy = []
                for i in range(1, completed + 1):
                    acc = 100 * sum(1 for r in results[:i] if r["is_correct"]) / i
                    running_accuracy.append(acc)
                df = pd.DataFrame({
                    "Customer": list(range(1, completed + 1)),
                    "Accuracy (%)": running_accuracy,
                }).set_index("Customer")
                chart_container.line_chart(df, color=["#2196F3"])

            # Render the latest result as an expander (collapsed)
            r = latest
            customer = r["customer"]
            is_correct = r["is_correct"]
            routed_to = r["routed_to"]
            correct_office = r["correct_office"]
            result = r["result"]

            type_emoji = {"financial": "💰", "security": "🔐", "technical": "🔧"}[customer["type"]]
            routed_info = OFFICE_INFO.get(routed_to, {"name": "Unknown"})
            correct_info = OFFICE_INFO[correct_office]

            expander_title = f"{status_emoji} Customer #{customer['id']}: {customer['name']} ({type_emoji} {customer['type']}) → {routed_info['name']}"

            with results_container:
                with st.expander(expander_title, expanded=False):
                    st.markdown(f"**Issue:** {customer['issue']}")
                    st.markdown(f"**Routed to:** `{routed_to}` ({routed_info['name']})")
                    st.markdown(f"**Correct office:** `{correct_office}` ({correct_info['name']})")

                    if is_correct:
                        st.success("Correct routing!")
                    else:
                        st.error(f"Wrong! Should have been {correct_info['name']}")

                    # Show injection debug info
                    injection_debug = result.get("injection_debug")
                    if injection_debug:
                        st.markdown("---")
                        st.markdown("**🧠 Memory Injection:**")
                        if injection_debug.injected:
                            st.success(f"Memory injected via `{injection_debug.mode}` mode")
                            if injection_debug.reflect_text:
                                st.markdown("**Reflect response:**")
                                st.info(injection_debug.reflect_text)
                        elif injection_debug.error:
                            st.error(f"Error: {injection_debug.error}")
                        else:
                            st.warning("No relevant memories found")

                        if hasattr(injection_debug, 'results_count') and injection_debug.results_count:
                            st.markdown(f"**Facts retrieved:** {injection_debug.results_count}")

                    # Show the FULL prompt sent to LLM
                    st.markdown("---")
                    st.markdown("**📤 Full Prompt Sent to LLM:**")
                    system_prompt = result.get("system_prompt", SYSTEM_PROMPT)
                    user_message = result.get("user_message", f"{customer['name']}: {customer['issue']}")
                    full_prompt = f"""[SYSTEM]
{system_prompt}

[USER]
{user_message}

[TOOLS]
- route_to_downtown_office
- route_to_riverside_branch
- route_to_harbor_center
(tool_choice: required)"""
                    st.code(full_prompt, language=None)

                    st.markdown("---")
                    st.markdown("**📥 LLM Response (Tool Call):**")
                    st.json({"function": routed_to, "arguments": result.get("args", {})})

                    if result.get("args", {}).get("reasoning"):
                        st.markdown("---")
                        st.markdown("**LLM Reasoning:**")
                        st.info(result["args"]["reasoning"])

        st.session_state.loop_running = False
        st.session_state.loop_completed = True
        progress_bar.empty()
        status_text.empty()
        st.balloons()
        st.rerun()


# ============================================================================
# MAIN
# ============================================================================

def render_interactive_demo(config: Dict):
    """Render the interactive (step-by-step) demo tab."""
    # Explanation
    with st.expander("📖 How This Works", expanded=False):
        st.markdown("""
        **The Challenge:** Route customers to the correct regional office. But the LLM only sees office names with no hint of what they handle!

        | Tool | LLM Sees | Actually Handles |
        |------|----------|------------------|
        | `route_to_downtown_office` | "Downtown Office" | 💰 Financial issues |
        | `route_to_riverside_branch` | "Riverside Branch" | 🔐 Security issues |
        | `route_to_harbor_center` | "Harbor Center" | 🔧 Technical issues |

        **With 3 offices, random guessing = ~33% accuracy**

        **The Flow:**
        1. Customer arrives → Both LLMs route simultaneously
        2. Customer gives feedback (simulated) → Was routing correct?
        3. Feedback stored to Hindsight via `hindsight_litellm.retain()` → **~5 second wait for indexing**
        4. Next customer → Hindsight LLM uses learned knowledge via `hindsight_litellm.recall()`

        **Watch the chart:** Hindsight should improve while no-memory stays ~33%

        > **Note:** This demo uses `hindsight_litellm` exclusively for all operations (completion, recall, retain).
        """)

    st.markdown("---")
    render_office_legend()
    st.markdown("---")


def main():
    init_session_state()

    st.markdown("""
    <h1 style="text-align: center;">🔧 Tool Learning Demo</h1>
    <p style="text-align: center; color: gray; font-size: 18px;">
        Watch Hindsight learn correct tool selection — incrementally, from feedback
    </p>
    """, unsafe_allow_html=True)

    config = render_sidebar()

    # Configure the bank with background instructions on first run
    # This tells Hindsight what's important to remember for this routing agent
    if not st.session_state.bank_configured:
        try:
            configure_hindsight(
                api_url=config["api_url"],
                bank_id=st.session_state.bank_id,
                store_conversations=False,
                with_background=True,  # Set bank background for better memory extraction
            )
            st.session_state.bank_configured = True
        except Exception as e:
            # Don't block the demo if bank configuration fails
            st.session_state.bank_configured = True  # Mark as configured to avoid retrying
            pass

    # Create tabs
    tab1, tab2 = st.tabs(["👥 Interactive Demo", "🔄 Looped Customers"])

    with tab1:
        render_interactive_demo(config)

        # Demo complete?
        if st.session_state.customer_index >= len(st.session_state.customer_queue):
            st.balloons()
            st.success("🎉 **Demo Complete!** All customers served.")

            total = len(st.session_state.history)
            no_mem = sum(1 for h in st.session_state.history if h["no_memory_correct"])
            with_mem = sum(1 for h in st.session_state.history if h["with_memory_correct"])

            col1, col2, col3 = st.columns(3)
            col1.metric("Customers", total)
            col2.metric("Without Memory", f"{100*no_mem//total}%", f"{no_mem}/{total}")
            col3.metric("With Hindsight", f"{100*with_mem//total}%", f"+{with_mem - no_mem} vs baseline", delta_color="normal")

            render_history()
        else:
            # Current customer
            customer = st.session_state.customer_queue[st.session_state.customer_index]

            st.markdown(f"### 👥 Customer {st.session_state.customer_index + 1} of {len(st.session_state.customer_queue)}")
            render_customer_card(customer)

            # Action buttons
            col_route, col_next = st.columns([3, 1])

            with col_route:
                route_clicked = st.button("🚀 Route This Customer", type="primary", use_container_width=True,
                                           disabled=st.session_state.last_results is not None)

            with col_next:
                next_disabled = st.session_state.last_results is None
                next_clicked = st.button("➡️ Next", use_container_width=True, disabled=next_disabled)

            # Handle routing
            if route_clicked:
                correct_office = CORRECT_ROUTING[customer["type"]]

                with st.spinner("🔄 Routing customer..."):
                    no_mem_result = route_without_memory(config["model"], customer["name"], customer["issue"])
                    with_mem_result = route_with_hindsight(
                        config["model"], customer["name"], customer["issue"],
                        config["api_url"], st.session_state.bank_id
                    )

                st.session_state.last_results = {
                    "no_mem": no_mem_result,
                    "with_mem": with_mem_result,
                    "customer": customer,
                    "correct_office": correct_office,
                }
                st.rerun()

            # Show results if we have them
            if st.session_state.last_results:
                results = st.session_state.last_results

                render_results(results["no_mem"], results["with_mem"], results["correct_office"], results["customer"])

                st.markdown("---")
                no_correct, with_correct = render_feedback(
                    results["customer"], results["no_mem"], results["with_mem"]
                )

                # Store feedback
                st.markdown("---")

                # Check if feedback has been stored for this customer
                feedback_key = f"feedback_stored_{customer['id']}"
                feedback_result_key = f"feedback_result_{customer['id']}"

                if feedback_key not in st.session_state:
                    with st.spinner("📝 Storing feedback to Hindsight via hindsight_litellm..."):
                        store_result = store_feedback(
                            config["model"],
                            config["api_url"], st.session_state.bank_id,
                            results["customer"], results["with_mem"].get("tool", "unknown"),
                            with_correct
                        )
                        st.session_state[feedback_key] = True
                        st.session_state[feedback_result_key] = store_result

                    if store_result.get("success"):
                        # Wait for Hindsight to process the memory
                        st.info("⏳ Waiting for Hindsight to process the feedback (memories need ~5 seconds to be indexed)...")
                        time.sleep(5)
                    else:
                        st.error(f"❌ Failed to store feedback: {store_result.get('error')}")
                        with st.expander("Error Details"):
                            st.code(store_result.get("traceback", "No traceback"))

                # Show result
                store_result = st.session_state.get(feedback_result_key, {})
                if store_result.get("success"):
                    st.success("✅ Feedback stored and processed — Hindsight will use this for future routing!")
                    with st.expander("📝 Full Conversation Stored to Hindsight"):
                        st.code(store_result.get("full_conversation", store_result.get("feedback", "N/A")))
                else:
                    st.error(f"❌ Feedback storage failed: {store_result.get('error', 'Unknown error')}")

                # Record to history (only once)
                if not st.session_state.history or st.session_state.history[-1]["customer"]["id"] != customer["id"]:
                    st.session_state.history.append({
                        "customer": results["customer"],
                        "no_memory_correct": no_correct,
                        "with_memory_correct": with_correct,
                        "no_memory_tool": results["no_mem"].get("tool"),
                        "with_memory_tool": results["with_mem"].get("tool"),
                        "correct_office": results["correct_office"],
                    })

            # Handle next customer
            if next_clicked:
                st.session_state.customer_index += 1
                st.session_state.last_results = None
                st.rerun()

            # Show history chart
            render_history()

    with tab2:
        render_looped_demo(config)


if __name__ == "__main__":
    main()
