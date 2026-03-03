"""Agent service — copilot loop that pauses for CSR approval on action tools."""

import json
import time
import asyncio
from fastapi import WebSocket

import sys
sys.path.insert(0, str(__file__).rsplit("/app/", 1)[0])

from telecom_data import Scenario, get_account, PLANS
from agent_tools import (
    execute_lookup, execute_action, execute_terminal,
    get_tool_definitions, get_rejection_hint,
    LOOKUP_TOOLS, ACTION_TOOLS, TERMINAL_TOOLS,
)
from .memory_service import (
    completion,
    retain_async,
    recall_async,
    format_recall_as_context,
    get_mental_models,
    refresh_mental_models_async,
    record_scenario,
    reset_scenario_count,
)
from ..config import LLM_MODEL


CUSTOMER_SIM_PROMPT = (
    "You are simulating a customer in a cable/internet company support conversation. "
    "Stay in character. Respond naturally and briefly (1-3 sentences). "
    "If the CSR has addressed your concern, acknowledge it but you may have follow-up questions. "
    "If your issue is fully resolved, thank them and say goodbye. "
    "Do NOT be overly polite or formal — be a normal person."
)


SYSTEM_PROMPT = (
    "You are an AI copilot assisting a customer service representative (CSR) at CableConnect, "
    "a cable and internet provider. A customer has contacted support. "
    "You can see the customer's messages.\n\n"
    "Your job is to:\n"
    "1. Look up relevant account information using lookup tools\n"
    "2. Suggest a response to send to the customer using suggest_response\n"
    "3. Suggest system actions when needed (credits, dispatches, service orders, etc.)\n"
    "4. The CSR will approve or reject your suggestions with feedback\n"
    "5. The CSR may also send you direct feedback at any time — pay close attention\n"
    "6. If rejected or corrected, learn from the feedback and try again\n"
    "7. Continue the conversation until the customer is satisfied\n\n"
    "IMPORTANT RULES:\n"
    "- Always suggest a customer response using suggest_response. Never skip this.\n"
    "- After each response is sent, WAIT for the customer to reply before taking further action.\n"
    "- Do NOT call resolve_interaction until the customer has explicitly confirmed they are "
    "satisfied, said goodbye, or the CSR tells you to wrap up. A customer asking a follow-up "
    "question means the conversation is NOT over.\n"
    "- The CSR sees both the customer chat and your suggestions side by side.\n"
    "- If the CSR gives you feedback, pay close attention and adjust your approach."
)


def _get_memory_query(scenario: Scenario) -> str:
    """Generate a memory query for the scenario category."""
    # Always recall communication style + conversation flow lessons,
    # plus category-specific policy and investigation lessons.
    base = (
        "How should I communicate with customers? What tone should I use? "
        "What jargon should I avoid? How concise should I be? "
        "When should I resolve an interaction? What must I do before ending a conversation? "
    )
    category_queries = {
        "billing": (
            "How should I investigate billing inquiries? Should I compare past bills? "
            "What are the rules for billing adjustments and credits?"
        ),
        "credit": (
            "What are the billing adjustment limits? What are the rules for outage credits? "
            "What mistakes should I avoid when posting adjustments?"
        ),
        "technical": (
            "What should I do before scheduling a technician dispatch? "
            "Should I run diagnostics first? What troubleshooting steps are required?"
        ),
        "retention": (
            "What are the retention offer eligibility requirements? "
            "What tenure is required? What mistakes should I avoid with retention?"
        ),
        "outage": (
            "What are the rules for outage credits? Should I check outage status first? "
            "What should I do during active outages?"
        ),
    }
    return base + category_queries.get(scenario.category, (
        f"What have I learned about handling {scenario.category} requests? "
        f"What mistakes should I avoid?"
    ))


def _format_retain_content(
    scenario: Scenario,
    actions_log: list[dict],
    csr_feedback: list[str],
    customer_chat: list[dict] | None = None,
) -> str:
    """Format the full interaction for Hindsight retention."""
    lines = []

    # Conversation
    lines.append("The conversation between the Customer and the Customer Service Rep was:")
    if customer_chat:
        for msg in customer_chat:
            role = "Customer" if msg["role"] == "customer" else "CSR"
            lines.append(f"  {role}: {msg['content']}")
    else:
        lines.append("  (no conversation recorded)")
    lines.append("")

    # Tool calls (lookups)
    lookups = [a for a in actions_log if a.get("isLookup")]
    if lookups:
        lines.append("The assistant performed these tool calls:")
        for a in lookups:
            lines.append(f"  {a.get('toolName', 'unknown')}({json.dumps(a.get('toolArgs', {}))}) -> {a.get('toolResult', '')[:200]}")
        lines.append("")

    # Suggestions and outcomes
    suggestions = [a for a in actions_log if a.get("isAction")]
    if suggestions:
        for a in suggestions:
            tool_name = a.get("toolName", "unknown")
            lines.append(f"The assistant made this suggestion:")
            lines.append(f"  {tool_name}({json.dumps(a.get('toolArgs', {}))})")
            if a.get("rejected"):
                lines.append(f"The CSR rejected the suggestion with the following feedback:")
                lines.append(f"  {a.get('rejectionFeedback', '')}")
            else:
                lines.append(f"The CSR approved the suggestion. Result:")
                lines.append(f"  {a.get('toolResult', '')}")
            lines.append("")

    # Direct CSR feedback
    if csr_feedback:
        lines.append("The CSR also provided this direct feedback:")
        for msg in csr_feedback:
            lines.append(f"  {msg}")
        lines.append("")

    return "\n".join(lines)


async def _simulate_customer_reply(
    llm_model: str,
    scenario: Scenario,
    customer_chat: list[dict],
) -> str | None:
    """Use LLM to simulate a customer reply based on conversation so far."""
    try:
        sim_messages = [
            {"role": "system", "content": CUSTOMER_SIM_PROMPT},
            {"role": "user", "content": (
                f"You are {get_account(scenario.account_id).name if get_account(scenario.account_id) else 'a customer'}. "
                f"You originally called because: \"{scenario.customer_message}\"\n\n"
                f"Here is the conversation so far:\n"
                + "\n".join(
                    f"{'You' if m['role'] == 'customer' else 'CSR'}: {m['content']}"
                    for m in customer_chat
                )
                + "\n\nWhat do you say next? Just the dialogue, nothing else."
            )},
        ]
        response = await completion(
            model=llm_model,
            messages=sim_messages,
            timeout=15,
        )
        reply = response.choices[0].message.content
        if reply:
            return reply.strip().strip('"')
    except Exception as e:
        print(f"[CUSTOMER SIM] Error: {e}")
    return None


async def _drain_csr_messages(websocket: WebSocket, timeout: float = 0.05) -> tuple[list[str], bool]:
    """Non-blocking drain of any pending csr_message events from the WebSocket.
    Returns (messages, cancelled)."""
    messages = []
    cancelled = False
    try:
        while True:
            data = await asyncio.wait_for(websocket.receive_json(), timeout=timeout)
            evt_type = data.get("type", "")
            if evt_type == "csr_message":
                msg = data.get("payload", {}).get("message", "")
                if msg:
                    messages.append(msg)
            elif evt_type == "cancel":
                cancelled = True
                break
    except asyncio.TimeoutError:
        pass
    return messages, cancelled


async def _wait_for_csr_response(
    websocket: WebSocket,
    suggestion_id: str,
    csr_message_queue: list[str],
    cancelled: asyncio.Event = None,
) -> dict:
    """Wait for the CSR to approve or reject a suggestion via WebSocket.
    Also collects any csr_message events that arrive during the wait."""
    while True:
        if cancelled and cancelled.is_set():
            return {"approved": False, "feedback": "Cancelled"}

        data = await websocket.receive_json()
        evt_type = data.get("type", "")

        if evt_type == "csr_respond":
            payload = data.get("payload", {})
            if payload.get("suggestionId") == suggestion_id:
                return payload

        if evt_type == "csr_message":
            msg = data.get("payload", {}).get("message", "")
            if msg:
                csr_message_queue.append(msg)

        if evt_type == "cancel":
            if cancelled:
                cancelled.set()
            return {"approved": False, "feedback": "Cancelled"}


async def process_scenario(
    websocket: WebSocket,
    scenario: Scenario,
    mode: str = "no_memory",
    max_steps: int = 25,
    model: str = None,
    cancelled: asyncio.Event = None,
):
    """Process a customer scenario. Agent suggests actions, pauses for CSR input."""
    llm_model = model or LLM_MODEL
    use_memory = mode == "memory_on"

    print(f"=== SCENARIO {scenario.scenario_index}: {scenario.account_id} ({scenario.category}) mode={mode} ===", flush=True)

    acct = get_account(scenario.account_id)
    plan = PLANS.get(acct.plan_id) if acct else None

    # Send scenario loaded
    await websocket.send_json({
        "type": "SCENARIO_LOADED",
        "payload": {
            "scenarioIndex": scenario.scenario_index,
            "accountId": scenario.account_id,
            "customerMessage": scenario.customer_message,
            "category": scenario.category,
            "customerName": acct.name if acct else "Unknown",
            "planName": plan.name if plan else "Unknown",
            "tenure": acct.tenure_months if acct else 0,
            "contractMonths": acct.contract_months if acct else 0,
            "area": acct.area if acct else "Unknown",
            "learningPairId": scenario.learning_pair_id,
            "isLearningTest": scenario.is_learning_test,
        },
    })

    # Build system prompt
    system_prompt = SYSTEM_PROMPT

    # Always inject mental models into the system prompt (regardless of mode)
    try:
        mental_models = get_mental_models()
        if mental_models:
            mm_lines = []
            for mm in mental_models:
                name = mm.get("name", "Unknown")
                content = mm.get("content") or mm.get("text") or ""
                if content:
                    mm_lines.append(f"## {name}\n{content}")
            if mm_lines:
                system_prompt += (
                    "\n\n# My Knowledge (Mental Models)\n"
                    "These are consolidated insights I've built from past interactions. "
                    "I must follow these guidelines:\n\n"
                    + "\n\n".join(mm_lines)
                )
                print(f"[MEMORY] Injected {len(mm_lines)} mental models into system prompt")
    except Exception as e:
        print(f"[MEMORY] Failed to fetch mental models: {e}")

    # Memory injection — when memory is on, recall past feedback
    memory_context = None

    if use_memory:
        try:
            await websocket.send_json({"type": "AGENT_THINKING", "payload": {"step": 0}})
            memory_query = _get_memory_query(scenario)
            t_mem = time.time()

            result = await recall_async(query=memory_query, budget="high")
            mem_timing = time.time() - t_mem
            if result and len(result) > 0:
                memory_context = format_recall_as_context(result)

            if memory_context:
                system_prompt += (
                    "\n\n# What I Remember From Past Interactions\n"
                    "The following is what I've learned from previous CSR feedback. "
                    "I must follow these lessons to avoid repeating mistakes:\n\n"
                    f"{memory_context}"
                )

            await websocket.send_json({
                "type": "MEMORY_RECALLED",
                "payload": {
                    "method": "recall",
                    "query": memory_query,
                    "text": memory_context,
                    "count": len(result) if result else 0,
                    "timing": mem_timing,
                },
            })
        except Exception as e:
            print(f"[MEMORY] Error during recall: {e}")
            import traceback
            traceback.print_exc()

    # Initial messages
    user_message = (
        f"A customer has called in. Here are the details:\n\n"
        f"Account ID: {scenario.account_id}\n"
        f"Customer: {acct.name if acct else 'Unknown'}\n"
        f"Plan: {plan.name if plan else 'Unknown'} (${plan.monthly_rate:.2f}/mo)\n"
        f"Tenure: {acct.tenure_months if acct else 0} months\n"
        f"Area: {acct.area if acct else 'Unknown'}\n\n"
        f"Customer says: \"{scenario.customer_message}\"\n\n"
        f"Look up relevant account information and suggest a response to the customer. "
        f"After the customer replies, continue helping until they are satisfied."
    )

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_message},
    ]

    tool_defs = get_tool_definitions()
    actions_log: list[dict] = []
    all_csr_feedback: list[str] = []
    step = 0
    suggestion_counter = 0
    resolved = False
    csr_message_queue: list[str] = []
    # Track customer ↔ CSR chat for customer simulation
    customer_chat: list[dict] = [
        {"role": "customer", "content": scenario.customer_message},
    ]

    try:
        while step < max_steps and not resolved:
            if cancelled and cancelled.is_set():
                await websocket.send_json({"type": "ERROR", "payload": {"message": "Cancelled"}})
                return

            # Drain any CSR messages that arrived while we were processing
            drained, was_cancelled = await _drain_csr_messages(websocket)
            if was_cancelled:
                if cancelled:
                    cancelled.set()
                return
            csr_message_queue.extend(drained)

            # Inject queued CSR messages into conversation
            if csr_message_queue:
                for msg in csr_message_queue:
                    messages.append({"role": "user", "content": f"CSR feedback: {msg}"})
                    all_csr_feedback.append(msg)
                    await websocket.send_json({
                        "type": "KNOWLEDGE_UPDATED",
                        "payload": {"tool": "_csr_feedback", "feedback": msg, "step": step},
                    })
                    # Store CSR feedback to Hindsight immediately
                    try:
                        conversation_so_far = "\n".join(
                            f"  {'Customer' if m['role'] == 'customer' else 'CSR'}: {m['content']}"
                            for m in customer_chat
                        )
                        retain_text = (
                            f"The conversation between the Customer and the Customer Service Rep was:\n"
                            f"{conversation_so_far}\n\n"
                            f"The CSR sent the assistant this direct feedback:\n"
                            f"  {msg}"
                        )
                        await retain_async(
                            content=retain_text,
                            context=f"csr_feedback:{scenario.category}",
                            tags=["feedback"],
                        )
                        print(f"[MEMORY] Stored CSR feedback immediately")
                    except Exception as e:
                        print(f"[MEMORY] Failed to store CSR feedback: {e}")
                csr_message_queue.clear()

            step += 1
            await websocket.send_json({"type": "AGENT_THINKING", "payload": {"step": step}})

            t0 = time.time()
            response = await completion(
                model=llm_model,
                messages=messages,
                tools=tool_defs,
                tool_choice="auto",
                timeout=30,
            )
            timing = time.time() - t0
            message = response.choices[0].message

            if not message.tool_calls:
                # Agent produced text without tool calls — nudge it
                if message.content:
                    messages.append({"role": "assistant", "content": message.content})
                    messages.append({"role": "user", "content": "Please use the available tools to help the customer."})
                continue

            tool_results = []

            for tool_call in message.tool_calls:
                tool_name = tool_call.function.name
                arguments = json.loads(tool_call.function.arguments) if tool_call.function.arguments else {}

                if tool_name in LOOKUP_TOOLS:
                    # Auto-execute lookups
                    result_text = execute_lookup(tool_name, arguments)
                    tool_results.append({
                        "tool_call_id": tool_call.id,
                        "role": "tool",
                        "content": result_text,
                    })
                    action_entry = {
                        "step": step,
                        "toolName": tool_name,
                        "toolArgs": arguments,
                        "toolResult": result_text,
                        "timing": timing,
                        "isAction": False,
                        "isLookup": True,
                        "rejected": False,
                        "rejectionFeedback": None,
                    }
                    actions_log.append(action_entry)
                    await websocket.send_json({"type": "AGENT_LOOKUP", "payload": action_entry})
                    await asyncio.sleep(0.05)

                elif tool_name in ACTION_TOOLS:
                    # === CSR GATE: pause and wait for human approval ===
                    suggestion_counter += 1
                    suggestion_id = f"sug-{scenario.scenario_index}-{suggestion_counter}"
                    hint = get_rejection_hint(tool_name, arguments)

                    # Send suggestion to frontend
                    await websocket.send_json({
                        "type": "AGENT_SUGGESTION",
                        "payload": {
                            "suggestionId": suggestion_id,
                            "step": step,
                            "toolName": tool_name,
                            "toolArgs": arguments,
                            "reasoning": message.content or "",
                            "rejectionHint": hint,
                        },
                    })

                    # Wait for CSR response (also collects csr_message events)
                    csr_response = await _wait_for_csr_response(
                        websocket, suggestion_id, csr_message_queue, cancelled,
                    )

                    if cancelled and cancelled.is_set():
                        return

                    approved = csr_response.get("approved", False)
                    feedback = csr_response.get("feedback", "")

                    if approved:
                        result_text = execute_action(tool_name, arguments)
                        tool_results.append({
                            "tool_call_id": tool_call.id,
                            "role": "tool",
                            "content": f"CSR APPROVED. {result_text}",
                        })
                        action_entry = {
                            "step": step,
                            "toolName": tool_name,
                            "toolArgs": arguments,
                            "toolResult": result_text,
                            "timing": timing,
                            "isAction": True,
                            "isLookup": False,
                            "rejected": False,
                            "rejectionFeedback": None,
                        }
                        actions_log.append(action_entry)
                        await websocket.send_json({
                            "type": "CSR_APPROVED",
                            "payload": {
                                "suggestionId": suggestion_id,
                                "step": step,
                                "tool": tool_name,
                                "result": result_text,
                            },
                        })
                        # If resolve_interaction was approved, end the loop
                        if tool_name == "resolve_interaction":
                            resolved = True

                        # If suggest_response was approved, send to customer chat and simulate reply
                        elif tool_name == "suggest_response":
                            csr_msg = arguments.get("message", "")
                            await websocket.send_json({
                                "type": "RESPONSE_SENT",
                                "payload": {
                                    "message": csr_msg,
                                    "accountId": arguments.get("account_id", ""),
                                },
                            })
                            customer_chat.append({"role": "csr", "content": csr_msg})

                            # Simulate customer reply
                            customer_reply = await _simulate_customer_reply(
                                llm_model, scenario, customer_chat,
                            )
                            if customer_reply:
                                customer_chat.append({"role": "customer", "content": customer_reply})
                                await websocket.send_json({
                                    "type": "CUSTOMER_REPLY",
                                    "payload": {"message": customer_reply},
                                })
                                # Inject customer reply into agent conversation
                                messages.append({
                                    "role": "user",
                                    "content": f"The customer responds: \"{customer_reply}\"",
                                })
                    else:
                        result_text = f"CSR REJECTED your suggestion. CSR feedback: {feedback}"
                        tool_results.append({
                            "tool_call_id": tool_call.id,
                            "role": "tool",
                            "content": result_text,
                        })
                        action_entry = {
                            "step": step,
                            "toolName": tool_name,
                            "toolArgs": arguments,
                            "toolResult": result_text,
                            "timing": timing,
                            "isAction": True,
                            "isLookup": False,
                            "rejected": True,
                            "rejectionFeedback": feedback,
                        }
                        actions_log.append(action_entry)
                        all_csr_feedback.append(feedback)
                        await websocket.send_json({
                            "type": "CSR_REJECTED",
                            "payload": {
                                "suggestionId": suggestion_id,
                                "step": step,
                                "tool": tool_name,
                                "feedback": feedback,
                            },
                        })
                        await websocket.send_json({
                            "type": "KNOWLEDGE_UPDATED",
                            "payload": {
                                "tool": tool_name,
                                "feedback": feedback,
                                "step": step,
                            },
                        })
                        # Store rejection feedback to Hindsight immediately
                        try:
                            conversation_so_far = "\n".join(
                                f"  {'Customer' if m['role'] == 'customer' else 'CSR'}: {m['content']}"
                                for m in customer_chat
                            )
                            lookups_so_far = "\n".join(
                                f"  {a['toolName']}({json.dumps(a.get('toolArgs', {}))}) -> {a.get('toolResult', '')[:200]}"
                                for a in actions_log if a.get("isLookup")
                            )
                            retain_text = (
                                f"The conversation between the Customer and the Customer Service Rep was:\n"
                                f"{conversation_so_far}\n\n"
                                f"The assistant performed these tool calls:\n"
                                f"{lookups_so_far or '  (none yet)'}\n\n"
                                f"The assistant made this suggestion:\n"
                                f"  {tool_name}({json.dumps(arguments)})\n\n"
                                f"The CSR rejected the suggestion with the following feedback:\n"
                                f"  {feedback}"
                            )
                            await retain_async(
                                content=retain_text,
                                context=f"csr_rejection:{scenario.category}",
                                tags=["feedback"],
                            )
                            print(f"[MEMORY] Stored rejection feedback immediately")
                        except Exception as e:
                            print(f"[MEMORY] Failed to store rejection feedback: {e}")

                elif tool_name in TERMINAL_TOOLS:
                    result_text = execute_terminal(tool_name, arguments)
                    tool_results.append({
                        "tool_call_id": tool_call.id,
                        "role": "tool",
                        "content": result_text,
                    })
                    action_entry = {
                        "step": step,
                        "toolName": tool_name,
                        "toolArgs": arguments,
                        "toolResult": result_text,
                        "timing": timing,
                        "isAction": False,
                        "isLookup": False,
                        "rejected": False,
                        "rejectionFeedback": None,
                    }
                    actions_log.append(action_entry)
                    resolved = True
                    await websocket.send_json({
                        "type": "SCENARIO_RESOLVED_PREVIEW",
                        "payload": action_entry,
                    })

                else:
                    tool_results.append({
                        "tool_call_id": tool_call.id,
                        "role": "tool",
                        "content": f"Unknown tool: {tool_name}",
                    })

            # Update conversation
            serialized_tc = [
                {"id": tc.id, "type": "function", "function": {"name": tc.function.name, "arguments": tc.function.arguments}}
                for tc in message.tool_calls
            ] if message.tool_calls else []
            messages.append({"role": "assistant", "content": message.content, "tool_calls": serialized_tc})
            messages.extend(tool_results)

        # --- Post-processing: ALWAYS store memory ---
        # Retain happens regardless of mode — the mode only controls recall/reflect.
        # CSR feedback and interaction data should always be persisted so it's
        # available when the user switches to a memory-enabled mode.
        rejections = [a for a in actions_log if a.get("rejected")]

        if actions_log or all_csr_feedback:
            retain_content = _format_retain_content(scenario, actions_log, all_csr_feedback, customer_chat)
            await websocket.send_json({"type": "MEMORY_STORING", "payload": {}})
            t_store = time.time()
            try:
                await retain_async(
                    retain_content,
                    context=f"customer_service:{scenario.category}",
                    session_id=f"scenario-{scenario.scenario_index}",
                )
                store_timing = time.time() - t_store
                await websocket.send_json({"type": "MEMORY_STORED", "payload": {"timing": store_timing}})
            except Exception as e:
                print(f"[MEMORY] Retain failed: {e}")
                import traceback
                traceback.print_exc()
                await websocket.send_json({"type": "MEMORY_STORED", "payload": {}})

            should_refresh = record_scenario()
            if should_refresh:
                await websocket.send_json({"type": "MODELS_REFRESHING", "payload": {}})
                try:
                    await refresh_mental_models_async()
                    await websocket.send_json({"type": "MODELS_REFRESHED", "payload": {"timing": 0}})
                except Exception as e:
                    print(f"[MEMORY] Refresh failed: {e}")
                reset_scenario_count()

        # Send final resolved event
        await websocket.send_json({
            "type": "SCENARIO_RESOLVED",
            "payload": {
                "scenarioIndex": scenario.scenario_index,
                "accountId": scenario.account_id,
                "category": scenario.category,
                "steps": step,
                "rejections": [
                    {"step": r["step"], "tool": r["toolName"], "feedback": r.get("rejectionFeedback", "")}
                    for r in rejections
                ],
                "rejectionCount": len(rejections),
                "learningPairId": scenario.learning_pair_id,
                "isLearningTest": scenario.is_learning_test,
            },
        })

    except asyncio.CancelledError:
        await websocket.send_json({"type": "ERROR", "payload": {"message": "Cancelled"}})
        raise
    except Exception as e:
        import traceback
        print(f"[AGENT] Error: {e}")
        traceback.print_exc()
        await websocket.send_json({"type": "ERROR", "payload": {"message": str(e)}})
