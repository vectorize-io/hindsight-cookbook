"""
Memory System Comparison UI

Interactive Streamlit app to compare different memory approaches:
1. No Memory (baseline) - Each query is independent
2. Full Conversation History - Pass entire conversation (truncated to show context loss)
3. Hindsight Memory - Intelligent semantic memory retrieval

Run with: streamlit run app.py
"""

import os
import time
import threading
import streamlit as st
from datetime import datetime
from typing import Optional, List, Dict, Any
import litellm

# ============================================================================
# PAGE CONFIG
# ============================================================================

st.set_page_config(
    page_title="Memory Approaches Comparison",
    page_icon="🧠",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ============================================================================
# CONSTANTS
# ============================================================================

AVAILABLE_MODELS = {
    "OpenAI": [
        "gpt-4o",
        "gpt-4o-mini",
        "gpt-4-turbo",
        "gpt-4",
        "gpt-3.5-turbo",
    ],
    "Anthropic": [
        "claude-3-5-sonnet-20241022",
        "claude-3-5-haiku-20241022",
        "claude-3-opus-20240229",
        "claude-3-sonnet-20240229",
        "claude-3-haiku-20240307",
    ],
    "Groq": [
        "groq/llama-3.1-70b-versatile",
        "groq/llama-3.1-8b-instant",
        "groq/mixtral-8x7b-32768",
        "groq/gemma2-9b-it",
    ],
}

DEFAULT_SYSTEM_PROMPT = "You are a helpful assistant. Use any context provided to personalize your responses."

# Max messages to keep for "full conversation history" approach (to demonstrate truncation)
MAX_HISTORY_MESSAGES = 4  # Artificially low to show context loss after just 2 exchanges

# ============================================================================
# SESSION STATE
# ============================================================================

def init_session_state():
    """Initialize session state variables."""
    # No memory - each query independent
    if "no_memory_messages" not in st.session_state:
        st.session_state.no_memory_messages = []

    # Full conversation history - maintains all messages (shown truncated)
    if "full_history_messages" not in st.session_state:
        st.session_state.full_history_messages = []
    if "full_history_all" not in st.session_state:
        # Keep ALL messages for display, but only send truncated to LLM
        st.session_state.full_history_all = []

    # Hindsight memory
    if "hindsight_messages" not in st.session_state:
        st.session_state.hindsight_messages = []

    if "debug_info" not in st.session_state:
        st.session_state.debug_info = {"no_memory": None, "full_history": None, "hindsight": None}


# ============================================================================
# MEMORY SYSTEM HANDLERS
# ============================================================================

def send_without_memory(
    model: str,
    user_message: str,
    system_prompt: str,
    temperature: float = 0.7,
    max_tokens: int = 1000,
) -> Dict[str, Any]:
    """Send message without any memory system (baseline)."""

    start_time = time.time()
    debug = {
        "user_query": user_message,
        "full_prompt": f"[SYSTEM]\n{system_prompt}\n\n[USER]\n{user_message}",
        "response": None,
        "context_used": "None - each query is independent",
        "pre_processing": {
            "memories_retrieved": "N/A - No memory system",
            "memory_count": 0,
        },
        "post_processing": {
            "stored": False,
            "stored_content": "N/A - No memory system",
            "error": None,
        },
        "error": None,
    }

    try:
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_message}
        ]

        response = litellm.completion(
            model=model,
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
        )

        elapsed = time.time() - start_time
        content = response.choices[0].message.content
        debug["response"] = content

        return {
            "success": True,
            "response": content,
            "time": elapsed,
            "tokens": response.usage.total_tokens if response.usage else None,
            "debug": debug,
        }

    except Exception as e:
        debug["error"] = str(e)
        return {
            "success": False,
            "response": f"Error: {str(e)}",
            "time": time.time() - start_time,
            "tokens": None,
            "debug": debug,
        }


def send_with_full_history(
    model: str,
    user_message: str,
    system_prompt: str,
    conversation_history: List[Dict],
    max_history: int = MAX_HISTORY_MESSAGES,
    temperature: float = 0.7,
    max_tokens: int = 1000,
) -> Dict[str, Any]:
    """Send message with full conversation history (truncated to simulate context limits)."""

    start_time = time.time()

    # Truncate history to show context loss over time
    # In real apps, this happens due to token limits
    truncated_history = conversation_history[-max_history:] if len(conversation_history) > max_history else conversation_history
    messages_dropped = len(conversation_history) - len(truncated_history)

    debug = {
        "user_query": user_message,
        "full_prompt": None,
        "response": None,
        "context_used": f"Last {len(truncated_history)} messages ({messages_dropped} dropped due to limit)",
        "pre_processing": {
            "total_history": len(conversation_history),
            "messages_sent": len(truncated_history),
            "messages_dropped": messages_dropped,
            "truncation_note": f"Only last {max_history} messages sent to LLM" if messages_dropped > 0 else "All history sent",
        },
        "post_processing": {
            "stored": True,
            "stored_content": "Added to conversation history",
            "error": None,
        },
        "error": None,
    }

    try:
        # Build messages with system prompt + truncated history + new user message
        messages = [{"role": "system", "content": system_prompt}]
        messages.extend(truncated_history)
        messages.append({"role": "user", "content": user_message})

        # Format for debug display
        history_text = "\n".join([f"[{m['role'].upper()}] {m['content'][:100]}..." if len(m['content']) > 100 else f"[{m['role'].upper()}] {m['content']}" for m in truncated_history])
        if messages_dropped > 0:
            history_text = f"... ({messages_dropped} earlier messages dropped) ...\n\n{history_text}"

        debug["full_prompt"] = f"[SYSTEM]\n{system_prompt}\n\n[HISTORY - {len(truncated_history)} msgs]\n{history_text}\n\n[USER]\n{user_message}"

        response = litellm.completion(
            model=model,
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
        )

        elapsed = time.time() - start_time
        content = response.choices[0].message.content
        debug["response"] = content

        return {
            "success": True,
            "response": content,
            "time": elapsed,
            "tokens": response.usage.total_tokens if response.usage else None,
            "debug": debug,
        }

    except Exception as e:
        debug["error"] = str(e)
        return {
            "success": False,
            "response": f"Error: {str(e)}",
            "time": time.time() - start_time,
            "tokens": None,
            "debug": debug,
        }


def send_with_hindsight(
    model: str,
    user_message: str,
    system_prompt: str,
    api_url: str,
    bank_id: str,
    config: dict,
    temperature: float = 0.7,
    max_tokens: int = 1000,
) -> Dict[str, Any]:
    """Send message with Hindsight memory (semantic retrieval)."""

    start_time = time.time()
    debug = {
        "user_query": user_message,
        "full_prompt": None,
        "response": None,
        "context_used": "Semantic memory retrieval from Hindsight",
        "pre_processing": {
            "memories_retrieved": None,
            "memory_count": 0,
        },
        "post_processing": {
            "stored": False,
            "stored_content": None,
            "error": None,
        },
        "error": None,
    }

    try:
        import hindsight_litellm
        from hindsight_litellm import configure, enable, disable, recall, cleanup

        # Configure Hindsight - for multi-user support, use different bank_ids per user
        configure(
            hindsight_api_url=api_url,
            bank_id=bank_id,
            store_conversations=False,  # We store manually after
            inject_memories=config.get("inject_memories", True),
            max_memories=config.get("max_memories", 10),
            recall_budget=config.get("recall_budget", "mid"),
            verbose=False,
        )

        # PRE-PROCESSING: Retrieve memories
        memories_text = ""
        try:
            memories = recall(
                query=user_message,
            )
            if memories:
                debug["pre_processing"]["memories_retrieved"] = [
                    {"text": m.text, "type": m.fact_type, "weight": m.weight}
                    for m in memories
                ]
                debug["pre_processing"]["memory_count"] = len(memories)
                memories_text = "\n".join([f"- [{m.fact_type}] {m.text}" for m in memories])
        except Exception as e:
            debug["pre_processing"]["memories_retrieved"] = f"Error retrieving: {e}"

        # Build enhanced system prompt
        enhanced_system_prompt = system_prompt
        if memories_text:
            enhanced_system_prompt = f"{system_prompt}\n\n## Relevant memories about this user:\n{memories_text}"

        debug["full_prompt"] = f"[SYSTEM]\n{enhanced_system_prompt}\n\n[USER]\n{user_message}"

        enable()

        messages = [
            {"role": "system", "content": enhanced_system_prompt},
            {"role": "user", "content": user_message}
        ]

        response = litellm.completion(
            model=model,
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
        )

        disable()

        elapsed = time.time() - start_time
        content = response.choices[0].message.content
        debug["response"] = content

        # POST-PROCESSING: Store conversation in background thread (async)
        # This prevents blocking the UI while Hindsight processes the memory
        def store_async():
            try:
                from hindsight_client import Hindsight
                client = Hindsight(base_url=api_url, timeout=60.0)
                conversation_text = f"USER: {user_message}\n\nASSISTANT: {content}"
                client.retain(
                    bank_id=bank_id,
                    content=conversation_text,
                    context=f"conversation:litellm:{model}",
                )
            except Exception as e:
                # Log error but don't block - this is background processing
                pass

        # Launch background thread for storage
        threading.Thread(target=store_async, daemon=True).start()
        debug["post_processing"]["stored"] = "queued (async)"
        debug["post_processing"]["stored_content"] = f"USER: {user_message}\n\nASSISTANT: {content}"

        return {
            "success": True,
            "response": content,
            "time": elapsed,
            "tokens": response.usage.total_tokens if response.usage else None,
            "debug": debug,
        }

    except ImportError as e:
        debug["error"] = f"ImportError: {e}"
        return {
            "success": False,
            "response": f"hindsight-litellm import error: {e}",
            "time": time.time() - start_time,
            "tokens": None,
            "debug": debug,
        }
    except Exception as e:
        debug["error"] = str(e)
        return {
            "success": False,
            "response": f"Error: {str(e)}",
            "time": time.time() - start_time,
            "tokens": None,
            "debug": debug,
        }


# ============================================================================
# UI COMPONENTS
# ============================================================================

def render_sidebar():
    """Render the sidebar with configuration options."""

    st.sidebar.title("Configuration")
    st.sidebar.markdown("---")

    # Model Selection
    st.sidebar.subheader("Model")

    provider = st.sidebar.selectbox(
        "Provider",
        options=list(AVAILABLE_MODELS.keys()),
        index=0,
    )

    model = st.sidebar.selectbox(
        "Model",
        options=AVAILABLE_MODELS[provider],
        index=1,  # gpt-4o-mini by default
    )

    # Custom model option
    use_custom = st.sidebar.checkbox("Custom model")
    if use_custom:
        model = st.sidebar.text_input("Model ID", value=model)

    st.sidebar.markdown("---")

    # Generation Settings
    st.sidebar.subheader("Generation")
    temperature = st.sidebar.slider("Temperature", 0.0, 2.0, 0.7, 0.1)
    max_tokens = st.sidebar.slider("Max Tokens", 100, 4000, 1000, 100)

    st.sidebar.markdown("---")

    # Full History Settings
    st.sidebar.subheader("Full History Config")
    max_history = st.sidebar.slider(
        "Max Messages to Keep",
        min_value=2,
        max_value=20,
        value=MAX_HISTORY_MESSAGES,
        help="Artificially limit history to demonstrate context loss over time"
    )

    st.sidebar.markdown("---")

    # Hindsight Configuration
    st.sidebar.subheader("Hindsight Config")
    hindsight_api_url = st.sidebar.text_input(
        "API URL",
        value=os.getenv("HINDSIGHT_URL", "http://localhost:8888"),
    )
    hindsight_bank_id = st.sidebar.text_input(
        "Bank ID",
        value="demo-comparison",
        help="Memory bank ID. For multi-user support, use different bank_ids per user (e.g., 'user-123')",
    )
    hindsight_max_memories = st.sidebar.slider("Max Memories", 1, 20, 10, key="hindsight_max_memories")
    hindsight_budget = st.sidebar.selectbox("Recall Budget", ["low", "mid", "high"], index=1)

    hindsight_config = {
        "api_url": hindsight_api_url,
        "bank_id": hindsight_bank_id,
        "store_conversations": True,
        "inject_memories": True,
        "max_memories": hindsight_max_memories,
        "recall_budget": hindsight_budget,
    }

    st.sidebar.markdown("---")

    # System Prompt
    system_prompt = st.sidebar.text_area(
        "System Prompt",
        value=DEFAULT_SYSTEM_PROMPT,
        height=80,
    )

    st.sidebar.markdown("---")

    # Clear Chat button
    if st.sidebar.button("Clear Chat", use_container_width=True):
        st.session_state.no_memory_messages = []
        st.session_state.full_history_messages = []
        st.session_state.full_history_all = []
        st.session_state.hindsight_messages = []
        st.session_state.debug_info = {"no_memory": None, "full_history": None, "hindsight": None}
        st.rerun()

    # Clear Hindsight Memories button
    if st.sidebar.button("Clear Hindsight Memories", use_container_width=True, type="secondary"):
        try:
            import requests
            bank_id = hindsight_config['bank_id']
            api_url = hindsight_config["api_url"]
            response = requests.delete(f"{api_url}/v1/default/banks/{bank_id}/memories")
            if response.status_code == 200:
                st.sidebar.success(f"Cleared Hindsight bank: {bank_id}")
            else:
                st.sidebar.warning(f"API returned {response.status_code}")
        except Exception as e:
            st.sidebar.error(f"Error: {e}")

    # Status
    st.sidebar.markdown("---")
    st.sidebar.subheader("Status")

    # Check hindsight-litellm
    try:
        import hindsight_litellm
        st.sidebar.success("hindsight-litellm installed")
    except ImportError:
        st.sidebar.error("hindsight-litellm not installed")

    # Check Hindsight server
    import urllib.request
    try:
        urllib.request.urlopen(f"{hindsight_api_url}/metrics", timeout=2)
        st.sidebar.success("Hindsight server running")
    except:
        st.sidebar.warning("Hindsight server not responding")

    return {
        "model": model,
        "temperature": temperature,
        "max_tokens": max_tokens,
        "system_prompt": system_prompt,
        "max_history": max_history,
        "hindsight": hindsight_config,
    }


def render_chat_column(title: str, messages: List[Dict], color: str, debug_info: Optional[Dict] = None, description: str = ""):
    """Render a chat column with messages."""

    # Header with colored background
    st.markdown(f"""
        <div style="background-color: {color}; padding: 10px; border-radius: 5px; margin-bottom: 10px;">
            <h3 style="margin: 0; color: white;">{title}</h3>
        </div>
    """, unsafe_allow_html=True)

    if description:
        st.caption(description)

    # Chat container
    chat_container = st.container(height=350)

    with chat_container:
        if not messages:
            st.markdown("*No messages yet. Send a query below!*")
        else:
            for msg in messages:
                with st.chat_message(msg["role"]):
                    st.markdown(msg["content"])
                    if msg.get("time") or msg.get("tokens"):
                        meta = []
                        if msg.get("time"):
                            meta.append(f"{msg['time']:.2f}s")
                        if msg.get("tokens"):
                            meta.append(f"{msg['tokens']} tokens")
                        st.caption(" | ".join(meta))

    # Debug info expander
    if debug_info:
        with st.expander("Debug Info", expanded=False):
            tab_prompt, tab_pre, tab_post = st.tabs(["Full Prompt", "Pre-Processing", "Post-Processing"])

            with tab_prompt:
                if debug_info.get("context_used"):
                    st.markdown(f"**Context Strategy:** {debug_info['context_used']}")

                if debug_info.get("full_prompt"):
                    st.markdown("**Full Prompt:**")
                    st.code(debug_info["full_prompt"], language=None)

            with tab_pre:
                st.markdown("### Context Retrieved")
                pre = debug_info.get("pre_processing", {})

                # For full history
                if "total_history" in pre:
                    st.info(f"Total history: {pre['total_history']} messages")
                    st.info(f"Sent to LLM: {pre['messages_sent']} messages")
                    if pre.get("messages_dropped", 0) > 0:
                        st.warning(f"Dropped: {pre['messages_dropped']} messages (context limit)")
                    if pre.get("truncation_note"):
                        st.caption(pre["truncation_note"])

                # For Hindsight
                memories = pre.get("memories_retrieved")
                if memories and isinstance(memories, list):
                    st.success(f"Found {pre.get('memory_count', 0)} memories")
                    for m in memories:
                        weight = m.get('weight', 0)
                        weight_str = f" (relevance: {weight:.2f})" if weight else ""
                        st.markdown(f"- `[{m.get('type', '?')}]` {m.get('text', str(m))}{weight_str}")
                elif memories and isinstance(memories, str):
                    if "N/A" in memories:
                        st.info(memories)
                    else:
                        st.warning(memories)
                elif pre.get("memory_count", 0) == 0 and "memories_retrieved" in pre:
                    st.info("No memories retrieved")

            with tab_post:
                st.markdown("### Storage")
                post = debug_info.get("post_processing", {})

                if post.get("stored"):
                    st.success("Conversation stored")
                    if post.get("stored_content") and post["stored_content"] != "N/A - No memory system":
                        st.caption("Stored content:")
                        content = post["stored_content"]
                        if len(content) > 300:
                            content = content[:300] + "..."
                        st.code(content, language=None)
                else:
                    if post.get("error"):
                        st.error(f"Storage error: {post['error']}")
                    elif post.get("stored_content") == "N/A - No memory system":
                        st.info("No storage - baseline has no memory")
                    else:
                        st.warning("Not stored")

            if debug_info.get("error"):
                st.error(f"Error: {debug_info['error']}")


# ============================================================================
# MAIN APP
# ============================================================================

def main():
    """Main application entry point."""

    init_session_state()

    st.markdown("""
        <h1 style="text-align: center;">Memory Approaches Comparison</h1>
        <p style="text-align: center; color: gray;">Compare No Memory vs Full History vs Hindsight Memory</p>
    """, unsafe_allow_html=True)

    config = render_sidebar()

    st.markdown("---")
    st.markdown("### Query")

    col_input, col_button = st.columns([5, 1])

    with col_input:
        user_input = st.text_input(
            "Your message",
            placeholder="Type your message here... (e.g., 'I'm a Python developer named Alex')",
            label_visibility="collapsed",
            key="user_input"
        )

    with col_button:
        send_clicked = st.button("Send", use_container_width=True, type="primary")

    # Quick prompts
    st.markdown("**Quick prompts:**")
    quick_cols = st.columns(4)

    quick_prompts = [
        "Hi, I'm Sarah, a data scientist at Netflix",
        "I prefer Python and love machine learning",
        "What programming language should I use?",
        "What do you know about me?",
    ]

    quick_clicked = None
    for i, prompt in enumerate(quick_prompts):
        with quick_cols[i]:
            if st.button(prompt[:30] + "..." if len(prompt) > 30 else prompt, key=f"quick_{i}", use_container_width=True):
                quick_clicked = prompt

    message_to_send = quick_clicked or (user_input if send_clicked else None)

    if message_to_send:
        st.info(f"**Query:** {message_to_send}")

        # Add user message to display histories
        user_msg = {"role": "user", "content": message_to_send}
        st.session_state.no_memory_messages.append(user_msg.copy())
        st.session_state.full_history_all.append(user_msg.copy())
        st.session_state.hindsight_messages.append(user_msg.copy())

        progress_cols = st.columns(3)

        with progress_cols[0]:
            with st.spinner("No Memory thinking..."):
                no_memory_result = send_without_memory(
                    model=config["model"],
                    user_message=message_to_send,
                    system_prompt=config["system_prompt"],
                    temperature=config["temperature"],
                    max_tokens=config["max_tokens"],
                )

        with progress_cols[1]:
            with st.spinner("Full History thinking..."):
                # Get the history WITHOUT the current user message (we add it in the function)
                history_for_llm = st.session_state.full_history_messages.copy()

                full_history_result = send_with_full_history(
                    model=config["model"],
                    user_message=message_to_send,
                    system_prompt=config["system_prompt"],
                    conversation_history=history_for_llm,
                    max_history=config["max_history"],
                    temperature=config["temperature"],
                    max_tokens=config["max_tokens"],
                )

        with progress_cols[2]:
            with st.spinner("Hindsight thinking..."):
                hindsight_result = send_with_hindsight(
                    model=config["model"],
                    user_message=message_to_send,
                    system_prompt=config["system_prompt"],
                    api_url=config["hindsight"]["api_url"],
                    bank_id=config["hindsight"]["bank_id"],
                    config=config["hindsight"],
                    temperature=config["temperature"],
                    max_tokens=config["max_tokens"],
                )

        # Store debug info
        st.session_state.debug_info = {
            "no_memory": no_memory_result.get("debug"),
            "full_history": full_history_result.get("debug"),
            "hindsight": hindsight_result.get("debug"),
        }

        # Add responses to histories
        st.session_state.no_memory_messages.append({
            "role": "assistant",
            "content": no_memory_result["response"],
            "time": no_memory_result["time"],
            "tokens": no_memory_result["tokens"],
        })

        # For full history, add both user and assistant to the actual history used for LLM
        st.session_state.full_history_messages.append({"role": "user", "content": message_to_send})
        st.session_state.full_history_messages.append({"role": "assistant", "content": full_history_result["response"]})
        st.session_state.full_history_all.append({
            "role": "assistant",
            "content": full_history_result["response"],
            "time": full_history_result["time"],
            "tokens": full_history_result["tokens"],
        })

        st.session_state.hindsight_messages.append({
            "role": "assistant",
            "content": hindsight_result["response"],
            "time": hindsight_result["time"],
            "tokens": hindsight_result["tokens"],
        })

        st.rerun()

    # Create three columns for the chat interfaces
    st.markdown("---")
    st.markdown("### Responses")

    col1, col2, col3 = st.columns(3)

    with col1:
        render_chat_column(
            "No Memory (Baseline)",
            st.session_state.no_memory_messages,
            "#9E9E9E",  # Gray
            st.session_state.debug_info.get("no_memory"),
            description="Each query is independent - no context from previous messages"
        )

    with col2:
        # Show truncation warning if applicable
        total_msgs = len(st.session_state.full_history_messages)
        if total_msgs > config["max_history"]:
            desc = f"Full conversation passed to LLM (truncated to last {config['max_history']} msgs, {total_msgs - config['max_history']} dropped)"
        else:
            desc = f"Full conversation passed to LLM ({total_msgs} messages)"

        render_chat_column(
            "Full Conversation History",
            st.session_state.full_history_all,
            "#FF9800",  # Orange
            st.session_state.debug_info.get("full_history"),
            description=desc
        )

    with col3:
        render_chat_column(
            "Hindsight Memory",
            st.session_state.hindsight_messages,
            "#2196F3",  # Blue
            st.session_state.debug_info.get("hindsight"),
            description="Semantic memory retrieval - relevant facts injected based on query"
        )

    # Memory Explorer
    st.markdown("---")
    with st.expander("Memory Explorer (Hindsight)", expanded=False):
        st.markdown("""
        **Direct Memory Query** - Search stored memories using the `recall()` API.
        """)

        col_query, col_btn = st.columns([4, 1])
        with col_query:
            memory_query = st.text_input(
                "Search memories",
                placeholder="e.g., 'what do I work on?' or 'programming preferences'",
                key="memory_query",
                label_visibility="collapsed",
            )
        with col_btn:
            search_clicked = st.button("Search", key="search_memories", use_container_width=True)

        if search_clicked and memory_query:
            try:
                from hindsight_litellm import configure, recall

                configure(
                    hindsight_api_url=config["hindsight"]["api_url"],
                    bank_id=config["hindsight"]["bank_id"],
                )

                with st.spinner("Searching memories..."):
                    memories = recall(memory_query)

                if memories:
                    st.success(f"Found {len(memories)} memories")
                    for i, m in enumerate(memories, 1):
                        st.markdown(f"**{i}. [{m.fact_type.upper()}]** {m.text}")
                        if m.weight:
                            st.caption(f"Relevance: {m.weight:.3f}")
                else:
                    st.info("No memories found. Chat first to build up memories!")

            except Exception as e:
                st.error(f"Error searching memories: {e}")

    # Comparison info
    with st.expander("How to use this demo"):
        st.markdown("""
        ### Testing Memory Approaches

        1. **Introduce yourself**: Start with personal info
           - "Hi, I'm Alex, a Python developer at Google"
           - "I prefer using PyTorch for deep learning"

        2. **Have several exchanges**: Chat about different topics to build history

        3. **Test recall**: Ask what the assistant knows about you
           - "What programming language should I use?"
           - "What do you know about me?"

        ### What to observe

        | Approach | Behavior | Limitation |
        |----------|----------|------------|
        | **No Memory** | Each query independent | Forgets everything between messages |
        | **Full History** | Passes conversation to LLM | Context limit causes truncation - loses early info |
        | **Hindsight** | Semantic retrieval of relevant facts | Retrieves what's relevant to current query |

        ### Key insight

        After 5-10 messages, watch the **Full Conversation History** approach start losing
        early context due to truncation (simulated here with a low limit). Meanwhile,
        **Hindsight Memory** can still recall facts from the beginning because it uses
        semantic retrieval rather than sequential history.
        """)


if __name__ == "__main__":
    main()
