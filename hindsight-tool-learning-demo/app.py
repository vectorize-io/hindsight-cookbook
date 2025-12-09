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
from typing import Dict, Any, List

import hindsight_litellm
from hindsight_litellm import configure, recall, retain, completion, enable, disable, is_enabled

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
    "OpenAI": ["gpt-4o-mini", "gpt-4o", "gpt-4-turbo"],
    "Anthropic": ["claude-3-5-sonnet-20241022", "claude-3-5-haiku-20241022"],
    "Groq": ["groq/llama-3.1-70b-versatile", "groq/llama-3.1-8b-instant"],
}

# THREE Tool definitions - intentionally ambiguous
TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "route_to_channel_alpha",
            "description": "Routes the customer request to processing channel Alpha.",
            "parameters": {
                "type": "object",
                "properties": {
                    "reasoning": {"type": "string", "description": "Your reasoning for why this channel is appropriate for this request"},
                    "request_summary": {"type": "string", "description": "Brief summary of the customer's issue"}
                },
                "required": ["reasoning", "request_summary"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "route_to_channel_beta",
            "description": "Routes the customer request to processing channel Beta.",
            "parameters": {
                "type": "object",
                "properties": {
                    "reasoning": {"type": "string", "description": "Your reasoning for why this channel is appropriate for this request"},
                    "request_summary": {"type": "string", "description": "Brief summary of the customer's issue"}
                },
                "required": ["reasoning", "request_summary"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "route_to_channel_omega",
            "description": "Routes the customer request to processing channel Omega.",
            "parameters": {
                "type": "object",
                "properties": {
                    "reasoning": {"type": "string", "description": "Your reasoning for why this channel is appropriate for this request"},
                    "request_summary": {"type": "string", "description": "Brief summary of the customer's issue"}
                },
                "required": ["reasoning", "request_summary"]
            }
        }
    }
]

# Ground truth (hidden from LLM) - 3 categories now
CORRECT_ROUTING = {
    "financial": "route_to_channel_alpha",   # Billing, refunds, payments
    "security": "route_to_channel_beta",      # Account access, password, security
    "technical": "route_to_channel_omega",    # Bugs, features, errors
}

CHANNEL_INFO = {
    "route_to_channel_alpha": {"name": "Alpha", "handles": "💰 Financial (billing, refunds, payments)", "color": "#4CAF50"},
    "route_to_channel_beta": {"name": "Beta", "handles": "🔐 Security (account access, passwords)", "color": "#FF9800"},
    "route_to_channel_omega": {"name": "Omega", "handles": "🔧 Technical (bugs, features, errors)", "color": "#2196F3"},
}

# Customer queue - mix of financial, security, and technical issues
CUSTOMER_QUEUE = [
    {"id": 1, "type": "financial", "name": "Alice", "issue": "I was charged twice for my subscription last month. I need a refund for the duplicate payment."},
    {"id": 2, "type": "technical", "name": "Bob", "issue": "The app crashes every time I try to upload a file larger than 5MB. This is blocking my work."},
    {"id": 3, "type": "security", "name": "Carol", "issue": "I can't log into my account. It says my password is wrong but I'm sure it's correct. I think I'm locked out."},
    {"id": 4, "type": "financial", "name": "David", "issue": "My invoice shows the wrong amount. I was billed $99 but my plan is only $49/month."},
    {"id": 5, "type": "technical", "name": "Eve", "issue": "I found a bug: when I search for items with special characters, the results are completely wrong."},
    {"id": 6, "type": "security", "name": "Frank", "issue": "I received an email saying someone tried to access my account from a new device. I need to secure my account."},
    {"id": 7, "type": "financial", "name": "Grace", "issue": "I need to cancel my subscription and get a prorated refund for the remaining days."},
    {"id": 8, "type": "technical", "name": "Henry", "issue": "The mobile app isn't syncing with the web version. My changes disappear when I switch devices."},
    {"id": 9, "type": "security", "name": "Iris", "issue": "I want to enable two-factor authentication on my account. How do I set that up?"},
    {"id": 10, "type": "financial", "name": "Jack", "issue": "My payment failed but I was still charged. Please reverse the charge or apply it to my account."},
    {"id": 11, "type": "technical", "name": "Kate", "issue": "Getting error 500 when trying to access the dashboard. It's been happening for 2 days now."},
    {"id": 12, "type": "security", "name": "Leo", "issue": "I forgot my password and the reset email isn't arriving. I've checked spam too."},
]

SYSTEM_PROMPT = """You are a customer service routing agent. Route each customer request to the appropriate channel.

Available channels:
- route_to_channel_alpha: Channel Alpha
- route_to_channel_beta: Channel Beta
- route_to_channel_omega: Channel Omega

You must call exactly one routing function for each request."""

# ============================================================================
# SESSION STATE
# ============================================================================

# Default bank background - tells Hindsight what's important to remember
DEFAULT_BANK_BACKGROUND = """You are the memory system for a customer service routing assistant.

The assistant's job is to route customer requests to one of three channels: Alpha, Beta, or Omega.
The channel names don't indicate what they handle - the assistant must learn from experience.

When the assistant receives a new customer request, it will ask: "What do I know about routing this type of issue?"

Your job is to remember past routing outcomes so the assistant can make better decisions.
Focus on: what type of problem did the customer have, and which channel successfully handled it (or failed to handle it)."""


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

# ============================================================================
# HINDSIGHT LITELLM FUNCTIONS
# ============================================================================

def configure_hindsight(api_url: str, bank_id: str, store_conversations: bool = False, with_background: bool = False):
    """Configure hindsight_litellm with the given settings."""
    # Use session state background if available, otherwise use default
    background_text = st.session_state.get("bank_background", DEFAULT_BANK_BACKGROUND) if with_background else None
    configure(
        hindsight_api_url=api_url,
        bank_id=bank_id,
        store_conversations=store_conversations,
        inject_memories=True,
        max_memories=10,
        recall_budget="high",
        verbose=False,
        # Only set background on first configure to avoid repeated API calls
        background=background_text,
        bank_name="Customer Service Routing Agent" if with_background else None,
    )


def recall_memories(api_url: str, bank_id: str, query: str) -> Dict[str, Any]:
    """Recall memories using hindsight_litellm."""
    try:
        configure_hindsight(api_url, bank_id, store_conversations=False)

        results = recall(query=query, limit=10)

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

    Storage is NOT enabled here - we store after feedback is received so the
    conversation includes whether the routing was correct or not.
    """
    try:
        # Configure hindsight (storage disabled - we store after feedback)
        configure_hindsight(api_url, bank_id, store_conversations=False)

        # Retrieve learned routing knowledge
        recall_result = recall_memories(api_url, bank_id, f"routing rules channel {customer_issue}")
        memories = recall_result.get("memories", [])
        memories_text = recall_result.get("memories_text", "")
        recall_error = recall_result.get("error")

        # Build enhanced prompt with learned knowledge
        enhanced_prompt = SYSTEM_PROMPT
        if memories_text:
            enhanced_prompt += f"""

## CRITICAL: Learned Routing Knowledge
Based on past customer interactions and feedback, here's what you've learned about which channel handles what:

{memories_text}

Use this knowledge to route the current request correctly. Match the issue type to the correct channel based on past experience."""

        user_message = f"{customer_name}: {customer_issue}"

        response = completion(
            model=model,
            messages=[
                {"role": "system", "content": enhanced_prompt},
                {"role": "user", "content": user_message}
            ],
            tools=TOOLS,
            tool_choice="required",
            temperature=0.7,
        )

        if response.choices[0].message.tool_calls:
            tool_call = response.choices[0].message.tool_calls[0]
            tool_name = tool_call.function.name
            tool_args = json.loads(tool_call.function.arguments)

            return {
                "success": True,
                "tool": tool_name,
                "args": tool_args,
                "memories_used": len(memories),
                "memories": [m.text[:150] for m in memories[:5]] if memories else [],
                "system_prompt": enhanced_prompt,
                "user_message": user_message,
                "recall_error": recall_error,
            }
        return {"success": False, "tool": None, "error": "No tool called", "system_prompt": enhanced_prompt, "user_message": user_message, "recall_error": recall_error}

    except Exception as e:
        return {"success": False, "tool": None, "error": str(e)}


def store_feedback(model: str, api_url: str, bank_id: str, customer: Dict, routed_to: str, was_correct: bool) -> Dict[str, Any]:
    """Store the routing interaction with feedback to Hindsight.

    Uses hindsight_litellm.retain() to store the conversation to memory.
    """
    try:
        correct_channel = CORRECT_ROUTING[customer["type"]]
        routed_info = CHANNEL_INFO.get(routed_to, {"name": "Unknown"})
        correct_info = CHANNEL_INFO[correct_channel]

        customer_name = customer["name"]
        original_issue = customer['issue']
        issue_type = customer["type"]  # financial, security, technical

        # Build the conversation that happened - natural and sparse
        user_issue = f"{customer_name}: {original_issue}"
        routing_response = f"I'll route you to {routed_info['name']}."

        # Natural feedback - like a real customer would say
        if was_correct:
            customer_feedback = f"Thanks, {routed_info['name']} helped me with my {issue_type} issue!"
        else:
            customer_feedback = f"That was wrong - {routed_info['name']} couldn't help. Had to go to {correct_info['name']} instead."

        # Build the full conversation text
        conversation_text = f"""USER: {user_issue}

ASSISTANT: {routing_response}

USER: {customer_feedback}"""

        # Store using hindsight_litellm.retain()
        print(f"[DEBUG] Storing feedback to bank: {bank_id}")
        print(f"[DEBUG] Conversation:\n{conversation_text}")

        # Configure hindsight_litellm with the API URL and bank_id
        configure(
            hindsight_api_url=api_url,
            bank_id=bank_id,
            store_conversations=False,
            inject_memories=False,
        )

        result = retain(
            content=conversation_text,
            context="customer_service_routing_feedback",
        )

        print(f"[DEBUG] Retain result: {result}")

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


def render_channel_legend():
    """Show the hidden ground truth."""
    st.markdown("#### 🎯 Ground Truth (Hidden from LLM)")
    cols = st.columns(3)
    for i, (channel, info) in enumerate(CHANNEL_INFO.items()):
        with cols[i]:
            st.markdown(f"""
            <div style="background: {info['color']}22; border-left: 4px solid {info['color']};
                        padding: 10px; border-radius: 5px; font-size: 13px;">
                <strong>Channel {info['name']}</strong><br/>
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


def render_results(no_mem_result: Dict, with_mem_result: Dict, correct_channel: str, customer: Dict):
    """Render side-by-side routing results."""
    col1, col2 = st.columns(2)

    for col, result, title, color, is_hindsight in [
        (col1, no_mem_result, "Without Memory", "#9E9E9E", False),
        (col2, with_mem_result, "With Hindsight 🧠", "#2196F3", True)
    ]:
        with col:
            tool = result.get("tool", "None")
            is_correct = tool == correct_channel
            status = "✅ Correct!" if is_correct else "❌ Wrong channel"
            status_color = "#4CAF50" if is_correct else "#f44336"

            channel_info = CHANNEL_INFO.get(tool, {"name": "?", "color": "#999"})

            st.markdown(f"""
            <div style="border: 3px solid {color}; border-radius: 15px; padding: 20px;">
                <h3 style="color: {color}; margin-top: 0;">{title}</h3>
                <div style="background: #f8f9fa; padding: 15px; border-radius: 10px; margin: 10px 0;">
                    <p style="margin: 0 0 5px 0; font-size: 13px; color: #666;">Routed to:</p>
                    <code style="font-size: 14px; background: {channel_info['color']}22;
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
                # Show memories for Hindsight first (context)
                if is_hindsight:
                    st.markdown(f"**Memories Retrieved:** {result.get('memories_used', 0)}")
                    if result.get("memories"):
                        for i, mem in enumerate(result.get("memories", []), 1):
                            st.markdown(f"{i}. _{mem}_")
                    else:
                        st.info("No memories found (bank may be empty or memories still processing)")

                    # Show recall error if any
                    if result.get("recall_error"):
                        st.warning(f"Recall error: {result.get('recall_error')}")
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
- route_to_channel_alpha
- route_to_channel_beta
- route_to_channel_omega
(tool_choice: required)"""

                st.code(full_prompt, language=None)

                # Show tool call result
                st.markdown("---")
                st.markdown("**📥 LLM Response (Tool Call):**")
                st.json({"function": tool, "arguments": result.get("args", {})})


def render_feedback(customer: Dict, no_mem_result: Dict, with_mem_result: Dict):
    """Show simulated customer feedback."""
    correct_channel = CORRECT_ROUTING[customer["type"]]
    no_correct = no_mem_result.get("tool") == correct_channel
    with_correct = with_mem_result.get("tool") == correct_channel

    # Get channel info for feedback messages
    no_mem_routed = no_mem_result.get("tool", "unknown")
    with_mem_routed = with_mem_result.get("tool", "unknown")
    no_mem_info = CHANNEL_INFO.get(no_mem_routed, {"name": "Unknown"})
    with_mem_info = CHANNEL_INFO.get(with_mem_routed, {"name": "Unknown"})
    correct_info = CHANNEL_INFO[correct_channel]
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
    st.caption("📊 Random guessing with 3 channels = ~33% accuracy. Watch Hindsight improve!")


# ============================================================================
# MAIN
# ============================================================================

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

    # Explanation
    with st.expander("📖 How This Works", expanded=False):
        st.markdown("""
        **The Challenge:** Route customers to the correct support channel. But the LLM only sees vague channel names!

        | Channel | LLM Sees | Actually Handles |
        |---------|----------|------------------|
        | `route_to_channel_alpha` | "Channel Alpha" | 💰 Financial issues |
        | `route_to_channel_beta` | "Channel Beta" | 🔐 Security issues |
        | `route_to_channel_omega` | "Channel Omega" | 🔧 Technical issues |

        **With 3 channels, random guessing = ~33% accuracy**

        **The Flow:**
        1. Customer arrives → Both LLMs route simultaneously
        2. Customer gives feedback (simulated) → Was routing correct?
        3. Feedback stored to Hindsight via `hindsight_litellm.retain()` → **~5 second wait for indexing**
        4. Next customer → Hindsight LLM uses learned knowledge via `hindsight_litellm.recall()`

        **Watch the chart:** Hindsight should improve while no-memory stays ~33%

        > **Note:** This demo uses `hindsight_litellm` exclusively for all operations (completion, recall, retain).
        """)

    st.markdown("---")
    render_channel_legend()
    st.markdown("---")

    # Demo complete?
    if st.session_state.customer_index >= len(CUSTOMER_QUEUE):
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
        return

    # Current customer
    customer = CUSTOMER_QUEUE[st.session_state.customer_index]

    st.markdown(f"### 👥 Customer {st.session_state.customer_index + 1} of {len(CUSTOMER_QUEUE)}")
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
        correct_channel = CORRECT_ROUTING[customer["type"]]

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
            "correct_channel": correct_channel,
        }
        st.rerun()

    # Show results if we have them
    if st.session_state.last_results:
        results = st.session_state.last_results

        render_results(results["no_mem"], results["with_mem"], results["correct_channel"], results["customer"])

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
                "correct_channel": results["correct_channel"],
            })

    # Handle next customer
    if next_clicked:
        st.session_state.customer_index += 1
        st.session_state.last_results = None
        st.rerun()

    # Show history chart
    render_history()


if __name__ == "__main__":
    main()
