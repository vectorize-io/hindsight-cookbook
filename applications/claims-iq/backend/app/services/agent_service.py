"""Agent service — runs the claim processing loop with LLM tool-calling."""

import json
import time
import asyncio
from typing import Optional
from fastapi import WebSocket

import sys
sys.path.insert(0, str(__file__).rsplit("/app/", 1)[0])

from claims_data import (
    Claim, generate_claim, claim_to_dict, compute_optimal_steps, get_claim,
)
from agent_tools import AgentTools, get_tool_definitions, execute_tool
from .memory_service import (
    completion,
    retain_async,
    recall_async,
    reflect_async,
    format_recall_as_context,
    get_bank_id,
    refresh_mental_models_async,
    record_claim,
    reset_claim_count,
    BANK_MISSION,
)
from ..config import LLM_MODEL


def _get_memory_query(claim: Claim) -> str:
    """Generate a memory query for the claim."""
    return (
        f"What do I know about processing {claim.category} claims? "
        f"What are the coverage rules for the policy on this claim? "
        f"Who is the right adjuster for {claim.category} in the {claim.region} region? "
        f"What are the escalation rules for claims over ${claim.amount:,.0f}?"
    )


def _get_severity(amount: float) -> str:
    if amount < 10_000:
        return "low"
    elif amount <= 50_000:
        return "medium"
    return "high"


def _get_pipeline_stage(state) -> str:
    """Map processing state to pipeline stage."""
    if state.decision_submitted and state.correct:
        return "resolved"
    if state.adjuster_assigned:
        return "routed"
    if state.coverage_checked or state.fraud_checked:
        return "verified"
    if state.classified:
        return "classified"
    return "received"


def _format_retain_content(claim: Claim, actions: list[dict], result_text: str) -> str:
    """Format the claim processing conversation for Hindsight retention."""
    lines = [
        f"CLAIM PROCESSING: Claim #{claim.claim_id} - {claim.category} claim for ${claim.amount:,.2f}",
        "",
        f"Policy: {claim.policy_id}",
        f"Region: {claim.region}",
        f"Description: {claim.description}",
        "",
    ]
    for action in actions:
        tool_name = action.get("toolName", "unknown")
        tool_args = action.get("toolArgs", {})
        tool_result = action.get("toolResult", "")
        args_str = ", ".join(f'"{v}"' if isinstance(v, str) else str(v) for v in tool_args.values())
        lines.append(f"TOOL_CALL: {tool_name}({args_str})")
        lines.append(f"RESULT: {tool_result}")
        lines.append("")
    lines.append(f"OUTCOME: {result_text}")
    return "\n".join(lines)


def _extract_mistakes(actions_log: list[dict]) -> list[dict]:
    """Extract structured mistake descriptions from DECISION REJECTED results."""
    mistakes = []
    for action in actions_log:
        if action["toolName"] == "submit_decision" and "DECISION REJECTED" in action["toolResult"]:
            text = action["toolResult"].replace("DECISION REJECTED: ", "").split(" Please review")[0]
            mistakes.append({"step": action["step"], "description": text})
    return mistakes


async def process_claim(
    websocket: WebSocket,
    claim: Claim,
    mode: str = "no_memory",
    max_steps: int = 20,
    model: str = None,
    cancelled: asyncio.Event = None,
):
    """Process a claim through the agent loop, streaming events via WebSocket.

    Args:
        websocket: WebSocket connection
        claim: The claim to process
        mode: "no_memory" | "recall" | "reflect" | "hindsight_mm"
        max_steps: Maximum tool calls allowed
        model: LLM model override
        cancelled: Cancellation event
    """
    llm_model = model or LLM_MODEL
    use_memory = mode != "no_memory"
    use_reflect = mode in ("reflect", "hindsight_mm")

    print(f"=== CLAIM PROCESSING: {claim.claim_id} ({claim.category}) mode={mode} ===", flush=True)

    # Send claim received
    await websocket.send_json({
        "type": "CLAIM_RECEIVED",
        "payload": claim_to_dict(claim),
    })

    # Set up tools
    tools = AgentTools(claim)
    actions_log: list[dict] = []

    # Build system prompt
    base_prompt = (
        "You are an insurance claims processing agent. You have tools available "
        "to investigate and process incoming claims. Your job is to reach an "
        "accurate, well-justified decision.\n\n"
        "You should investigate the claim thoroughly before submitting a decision. "
        "If your decision is rejected, analyze the error carefully and try again."
    )
    system_prompt = base_prompt

    # Memory injection
    memory_context = None
    memory_method = "reflect" if use_reflect else "recall"

    if use_memory:
        try:
            await websocket.send_json({"type": "AGENT_THINKING", "payload": {"step": 0}})
            memory_query = _get_memory_query(claim)
            t_mem = time.time()

            if use_reflect:
                result = await reflect_async(query=memory_query, budget="high")
                mem_timing = time.time() - t_mem
                if result and hasattr(result, "text") and result.text:
                    memory_context = result.text
            else:
                result = await recall_async(query=memory_query, budget="high")
                mem_timing = time.time() - t_mem
                if result and len(result) > 0:
                    memory_context = format_recall_as_context(result)

            if memory_context:
                system_prompt = f"{base_prompt}\n\n# What I Remember From Past Claims\n{memory_context}"

            await websocket.send_json({
                "type": "MEMORY_INJECTED",
                "payload": {
                    "method": memory_method,
                    "query": memory_query,
                    "text": memory_context,
                    "count": 1 if memory_context else 0,
                    "timing": mem_timing,
                },
            })
        except Exception as e:
            print(f"[MEMORY] Error during {memory_method}: {e}")
            import traceback
            traceback.print_exc()

    # Initial messages
    claim_text = (
        f"Process this insurance claim:\n"
        f"- Claim ID: {claim.claim_id}\n"
        f"- Claimant: {claim.claimant_name}\n"
        f"- Description: {claim.description}\n"
        f"- Policy ID: {claim.policy_id}\n"
        f"- Region: {claim.region}\n"
        f"- Amount: ${claim.amount:,.2f}\n"
        f"- Incident Date: {claim.incident_date}"
    )
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": claim_text},
    ]

    tool_defs = get_tool_definitions()
    accepted = False
    optimal_steps = compute_optimal_steps(claim)

    try:
        while tools.state.steps_taken < max_steps:
            if cancelled and cancelled.is_set():
                await websocket.send_json({"type": "ERROR", "payload": {"message": "Cancelled"}})
                return

            await websocket.send_json({"type": "AGENT_THINKING", "payload": {"step": tools.state.steps_taken + 1}})

            t0 = time.time()
            response = await completion(
                model=llm_model,
                messages=messages,
                tools=tool_defs,
                tool_choice="required",
                timeout=30,
            )
            timing = time.time() - t0

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
                        "content": result,
                    })

                    # Determine stage
                    stage = _get_pipeline_stage(tools.state)

                    action_entry = {
                        "step": tools.state.steps_taken,
                        "toolName": tool_name,
                        "toolArgs": arguments,
                        "toolResult": result,
                        "thinking": message.content if message.content else None,
                        "timing": timing,
                    }
                    actions_log.append(action_entry)

                    # Send action event
                    await websocket.send_json({"type": "AGENT_ACTION", "payload": action_entry})

                    # Send stage update
                    await websocket.send_json({"type": "CLAIM_STAGE_UPDATE", "payload": {"stage": stage}})

                    await asyncio.sleep(0.1)

                    # Check for accepted decision
                    if "DECISION ACCEPTED" in result:
                        accepted = True
                        break

                # Update conversation
                serialized_tc = [
                    {"id": tc.id, "type": "function", "function": {"name": tc.function.name, "arguments": tc.function.arguments}}
                    for tc in message.tool_calls
                ] if message.tool_calls else []
                messages.append({"role": "assistant", "content": message.content, "tool_calls": serialized_tc})
                messages.extend(tool_results)

                if accepted:
                    break
            else:
                if message.content:
                    actions_log.append({
                        "step": tools.state.steps_taken,
                        "toolName": "thinking",
                        "toolArgs": {},
                        "toolResult": message.content,
                        "timing": timing,
                    })
                    await websocket.send_json({
                        "type": "AGENT_ACTION",
                        "payload": actions_log[-1],
                    })
                messages.append({"role": "assistant", "content": message.content})
                messages.append({"role": "user", "content": "Use the available tools to process this claim."})

        # --- Post-processing: store memory, refresh models ---
        decision = tools.state.result or "incomplete"
        correct = tools.state.correct if tools.state.correct is not None else False

        if use_memory:
            # Retain conversation
            outcome_text = f"{decision.upper()} — {'Correct' if correct else 'Incorrect or incomplete'}"
            retain_content = _format_retain_content(claim, actions_log, outcome_text)

            await websocket.send_json({"type": "MEMORY_STORING", "payload": {}})
            t_store = time.time()
            try:
                await retain_async(
                    retain_content,
                    context=f"claim:{claim.category}:{decision}",
                    session_id=f"claim-{claim.claim_id}",
                )
                store_timing = time.time() - t_store
                await websocket.send_json({"type": "MEMORY_STORED", "payload": {"timing": store_timing}})
            except Exception as e:
                print(f"[MEMORY] Retain failed: {e}")

            # Check if mental model refresh is needed
            should_refresh = record_claim()
            if should_refresh:
                await websocket.send_json({"type": "MODELS_REFRESHING", "payload": {}})
                try:
                    await refresh_mental_models_async()
                    await websocket.send_json({"type": "MODELS_REFRESHED", "payload": {"timing": 0}})
                except Exception as e:
                    print(f"[MEMORY] Refresh failed: {e}")
                reset_claim_count()

        # Send resolved event
        actual_workflow = [a["toolName"] for a in actions_log]
        expected_workflow = [
            "classify_claim", "lookup_policy", "check_coverage",
            "check_fraud_indicators", "check_prior_claims",
            "get_adjuster", "submit_decision",
        ]
        mistakes = _extract_mistakes(actions_log)

        await websocket.send_json({
            "type": "CLAIM_RESOLVED",
            "payload": {
                "decision": decision,
                "correct": correct,
                "steps": tools.state.steps_taken,
                "optimalSteps": optimal_steps,
                "reworkCount": tools.state.rework_count,
                "mistakes": mistakes,
                "expectedWorkflow": expected_workflow,
                "actualWorkflow": actual_workflow,
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
