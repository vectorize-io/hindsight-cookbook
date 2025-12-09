"""
Hindsight Tool Learning Demo - Learning Correct Tool Selection Through Memory

This demo demonstrates how Hindsight helps an LLM learn which tool to use
when tool names are ambiguous. Without memory, the LLM might randomly select
between similarly-named tools. With Hindsight, it learns from past interactions
and consistently makes the correct choice.

SCENARIO:
We have a task routing system with two tools:
- `route_to_channel_alpha` - Routes to processing channel Alpha
- `route_to_channel_omega` - Routes to processing channel Omega

The tool names and descriptions are intentionally vague. In reality:
- Channel Alpha handles FINANCIAL/PAYMENT tasks (refunds, billing, etc.)
- Channel Omega handles TECHNICAL/SUPPORT tasks (bugs, features, etc.)

Without Hindsight: The LLM guesses randomly based on vague descriptions
With Hindsight: The LLM learns from feedback which channel handles what

Prerequisites:
- Hindsight server running at http://localhost:8888
- pip install hindsight-litellm litellm
- OPENAI_API_KEY environment variable set

Usage:
    python hindsight_tool_learning_demo.py
"""

import os
import json
import uuid
import time
import logging
from typing import Optional

logging.basicConfig(level=logging.INFO)
logging.getLogger("LiteLLM").setLevel(logging.WARNING)
logging.getLogger("LiteLLM Router").setLevel(logging.WARNING)
logging.getLogger("LiteLLM Proxy").setLevel(logging.WARNING)
logging.getLogger("httpx").setLevel(logging.WARNING)

import hindsight_litellm

# =============================================================================
# TOOL DEFINITIONS - Intentionally ambiguous names and descriptions
# =============================================================================

TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "route_to_channel_alpha",
            "description": "Routes the customer request to processing channel Alpha. Use this channel for appropriate request types.",
            "parameters": {
                "type": "object",
                "properties": {
                    "request_summary": {
                        "type": "string",
                        "description": "A brief summary of the customer's request"
                    },
                    "priority": {
                        "type": "string",
                        "enum": ["low", "medium", "high"],
                        "description": "Priority level of the request"
                    }
                },
                "required": ["request_summary"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "route_to_channel_omega",
            "description": "Routes the customer request to processing channel Omega. Use this channel for appropriate request types.",
            "parameters": {
                "type": "object",
                "properties": {
                    "request_summary": {
                        "type": "string",
                        "description": "A brief summary of the customer's request"
                    },
                    "priority": {
                        "type": "string",
                        "enum": ["low", "medium", "high"],
                        "description": "Priority level of the request"
                    }
                },
                "required": ["request_summary"]
            }
        }
    }
]

# Ground truth: Which channel should handle what (the LLM doesn't know this initially)
# Channel Alpha = Financial/Payment issues
# Channel Omega = Technical/Support issues
CORRECT_ROUTING = {
    "financial": "route_to_channel_alpha",
    "payment": "route_to_channel_alpha",
    "refund": "route_to_channel_alpha",
    "billing": "route_to_channel_alpha",
    "charge": "route_to_channel_alpha",
    "invoice": "route_to_channel_alpha",
    "technical": "route_to_channel_omega",
    "bug": "route_to_channel_omega",
    "feature": "route_to_channel_omega",
    "error": "route_to_channel_omega",
    "crash": "route_to_channel_omega",
    "support": "route_to_channel_omega",
}

# Test scenarios - mix of financial and technical requests
TEST_SCENARIOS = [
    {
        "type": "financial",
        "request": "I was charged twice for my subscription last month. I need a refund for the duplicate charge.",
        "correct_tool": "route_to_channel_alpha"
    },
    {
        "type": "technical",
        "request": "The app keeps crashing when I try to upload a file larger than 10MB. This bug is blocking my work.",
        "correct_tool": "route_to_channel_omega"
    },
    {
        "type": "financial",
        "request": "My invoice shows an incorrect amount. The billing department needs to fix this.",
        "correct_tool": "route_to_channel_alpha"
    },
    {
        "type": "technical",
        "request": "I'd like to request a new feature: the ability to export reports as PDF.",
        "correct_tool": "route_to_channel_omega"
    },
    {
        "type": "financial",
        "request": "I need to update my payment method and understand why my last payment failed.",
        "correct_tool": "route_to_channel_alpha"
    },
]


def get_system_prompt() -> str:
    """System prompt for the routing agent."""
    return """You are a customer service routing agent. Your job is to route customer requests to the appropriate processing channel.

You have access to two routing channels:
- route_to_channel_alpha: Routes to channel Alpha
- route_to_channel_omega: Routes to channel Omega

Analyze the customer's request and route it to the most appropriate channel. You must call one of the routing functions to process the request.

Important: Base your routing decision on what you know about each channel's purpose. If you have learned from previous interactions which channel handles specific types of requests, use that knowledge."""


def make_routing_request(
    user_request: str,
    use_hindsight: bool,
    bank_id: Optional[str] = None,
    verbose: bool = False
) -> tuple[str, dict]:
    """Make a routing request and return the tool called and its arguments."""

    messages = [
        {"role": "system", "content": get_system_prompt()},
        {"role": "user", "content": f"Customer Request: {user_request}"}
    ]

    if use_hindsight and bank_id:
        # Use hindsight-enabled completion
        response = hindsight_litellm.completion(
            model="gpt-4o-mini",
            messages=messages,
            tools=TOOLS,
            tool_choice="required",
            temperature=0.0,  # Deterministic for testing
        )
    else:
        # Use regular LiteLLM without hindsight
        import litellm
        response = litellm.completion(
            model="gpt-4o-mini",
            messages=messages,
            tools=TOOLS,
            tool_choice="required",
            temperature=0.7,  # Some randomness to show variability
        )

    # Extract tool call
    if response.choices[0].message.tool_calls:
        tool_call = response.choices[0].message.tool_calls[0]
        tool_name = tool_call.function.name
        tool_args = json.loads(tool_call.function.arguments)
        return tool_name, tool_args

    return None, {}


def store_feedback(bank_id: str, request: str, correct_tool: str, request_type: str):
    """Store feedback about which tool was correct for a request type."""
    from hindsight_client import Hindsight

    client = Hindsight(base_url="http://localhost:8888", timeout=60.0)

    # Store the learned association
    feedback_content = f"""ROUTING FEEDBACK:
Request type: {request_type}
Customer request: "{request}"
Correct routing: {correct_tool}

LEARNED RULE: {request_type.upper()} requests (like refunds, billing, payments, charges, invoices) should ALWAYS be routed to {correct_tool}.
This is important institutional knowledge for routing decisions."""

    client.retain(
        bank_id=bank_id,
        content=feedback_content,
        context=f"routing:feedback:{request_type}",
        metadata={"request_type": request_type, "correct_tool": correct_tool}
    )


def run_demo():
    """Run the full demonstration."""
    if not os.getenv("OPENAI_API_KEY"):
        print("Error: OPENAI_API_KEY not set")
        return

    bank_id = f"tool-learning-demo-{uuid.uuid4().hex[:8]}"

    print("=" * 70)
    print("HINDSIGHT TOOL LEARNING DEMO")
    print("=" * 70)
    print(f"\nBank ID: {bank_id}")
    print("\nThis demo shows how Hindsight helps an LLM learn correct tool selection")
    print("when tool names are ambiguous.\n")
    print("GROUND TRUTH (unknown to the LLM initially):")
    print("  - Channel Alpha: Financial/Payment issues (refunds, billing, etc.)")
    print("  - Channel Omega: Technical/Support issues (bugs, features, etc.)")
    print("\n" + "=" * 70)

    # =========================================================================
    # PHASE 1: Without Hindsight - Show random/incorrect routing
    # =========================================================================
    print("\n" + "=" * 70)
    print("PHASE 1: WITHOUT HINDSIGHT (No Memory)")
    print("=" * 70)
    print("\nThe LLM has no prior knowledge about which channel handles what.")
    print("With ambiguous tool descriptions, it may route incorrectly.\n")

    phase1_results = []
    for i, scenario in enumerate(TEST_SCENARIOS[:3], 1):
        print(f"\n--- Test {i}: {scenario['type'].upper()} Request ---")
        print(f"Request: \"{scenario['request'][:60]}...\"")

        tool_name, tool_args = make_routing_request(
            scenario['request'],
            use_hindsight=False,
            verbose=True
        )

        is_correct = tool_name == scenario['correct_tool']
        phase1_results.append(is_correct)

        print(f"LLM chose: {tool_name}")
        print(f"Correct tool: {scenario['correct_tool']}")
        print(f"Result: {'CORRECT' if is_correct else 'INCORRECT'}")

    phase1_accuracy = sum(phase1_results) / len(phase1_results) * 100
    print(f"\n>>> Phase 1 Accuracy: {phase1_accuracy:.0f}% ({sum(phase1_results)}/{len(phase1_results)})")

    # =========================================================================
    # PHASE 2: Teaching Phase - Store routing knowledge via Hindsight
    # =========================================================================
    print("\n" + "=" * 70)
    print("PHASE 2: TEACHING PHASE - Storing Routing Knowledge")
    print("=" * 70)
    print("\nNow we provide feedback about correct routing to build memory.\n")

    # Configure and enable Hindsight
    hindsight_litellm.configure(
        hindsight_api_url="http://localhost:8888",
        bank_id=bank_id,
        store_conversations=True,
        inject_memories=True,
        max_memories=10,
        recall_budget="high",
        verbose=False,
    )
    hindsight_litellm.enable()

    # Store feedback for different request types
    feedback_examples = [
        ("I need a refund for an incorrect charge on my account.", "route_to_channel_alpha", "financial"),
        ("There's a bug in the system causing data loss.", "route_to_channel_omega", "technical"),
        ("My billing statement has errors that need correction.", "route_to_channel_alpha", "financial"),
        ("I want to request a new feature for the dashboard.", "route_to_channel_omega", "technical"),
    ]

    for request, correct_tool, req_type in feedback_examples:
        print(f"Storing feedback: {req_type.upper()} -> {correct_tool}")
        store_feedback(bank_id, request, correct_tool, req_type)

    print("\nWaiting for Hindsight to process memories (15 seconds)...")
    time.sleep(15)

    # =========================================================================
    # PHASE 3: With Hindsight - Show learned correct routing
    # =========================================================================
    print("\n" + "=" * 70)
    print("PHASE 3: WITH HINDSIGHT (Memory-Augmented)")
    print("=" * 70)
    print("\nThe LLM now has access to learned routing knowledge via Hindsight.")
    print("It should route requests correctly based on past feedback.\n")

    phase3_results = []
    for i, scenario in enumerate(TEST_SCENARIOS, 1):
        print(f"\n--- Test {i}: {scenario['type'].upper()} Request ---")
        print(f"Request: \"{scenario['request'][:60]}...\"")

        tool_name, tool_args = make_routing_request(
            scenario['request'],
            use_hindsight=True,
            bank_id=bank_id,
            verbose=True
        )

        is_correct = tool_name == scenario['correct_tool']
        phase3_results.append(is_correct)

        print(f"LLM chose: {tool_name}")
        print(f"Correct tool: {scenario['correct_tool']}")
        print(f"Result: {'CORRECT' if is_correct else 'INCORRECT'}")

    phase3_accuracy = sum(phase3_results) / len(phase3_results) * 100
    print(f"\n>>> Phase 3 Accuracy: {phase3_accuracy:.0f}% ({sum(phase3_results)}/{len(phase3_results)})")

    # =========================================================================
    # SUMMARY
    # =========================================================================
    print("\n" + "=" * 70)
    print("SUMMARY")
    print("=" * 70)
    print(f"\nPhase 1 (No Memory):      {phase1_accuracy:.0f}% accuracy")
    print(f"Phase 3 (With Hindsight): {phase3_accuracy:.0f}% accuracy")

    improvement = phase3_accuracy - phase1_accuracy
    if improvement > 0:
        print(f"\nImprovement: +{improvement:.0f}% accuracy with Hindsight!")
    elif improvement == 0:
        print(f"\nNote: Results may vary. Run again to see learning effect.")
    else:
        print(f"\nNote: Phase 1 got lucky! Run again to see typical behavior.")

    print(f"\nMemories stored in bank: {bank_id}")
    print("\nKey Insight: Hindsight allows the LLM to learn from experience")
    print("which tool to use, even when tool names/descriptions are ambiguous.")

    # Cleanup
    hindsight_litellm.cleanup()
    print("\n" + "=" * 70)
    print("Demo complete!")
    print("=" * 70)


if __name__ == "__main__":
    run_demo()
