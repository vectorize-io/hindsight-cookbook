"""
Hindsight Configuration Experiments for Delivery Agent

This script tests different Hindsight configurations to find the optimal setup
for a delivery agent learning building layouts.

Experiments:
1. No memory (baseline)
2. Recall once at start (agent uses memories to decide)
3. Reflect every step (synthesized guidance per decision)
4. With/without background
5. Different query formulations
"""

import os
import json
import time
import random
from datetime import datetime
from dataclasses import dataclass, asdict
from typing import Optional, List, Dict, Any
from dotenv import load_dotenv

import litellm
from litellm import completion

# Local imports
from building import (
    Side, get_random_employee, get_employee_location,
    BUILDING_LAYOUT, get_business_at, calculate_optimal_steps
)
from agent import AgentState, AgentTools, Package, TOOL_DEFINITIONS

# Load environment
load_dotenv()

# Hindsight API - use requests directly to avoid async issues
import requests
HINDSIGHT_URL = os.getenv("HINDSIGHT_API_URL", "http://localhost:8888")


# Configuration
LLM_MODEL = os.getenv("LLM_MODEL", "gpt-4o")  # Fast and smart
MAX_STEPS = 25  # Prevent infinite loops
RUNS_PER_CONFIG = 8  # More runs for statistical significance and repeat deliveries


@dataclass
class ExperimentConfig:
    """Configuration for a single experiment."""
    name: str
    use_memory: bool = False
    memory_mode: str = "none"  # "none", "recall_start", "reflect_start", "reflect_per_step"
    background: Optional[str] = None
    query_template: str = "{recipient_name}"  # How to query Hindsight
    reflect_context_template: Optional[str] = None  # Context for reflect
    budget: str = "high"
    store_mode: str = "full_conversation"  # "full_conversation", "location_summary", "learnings"


@dataclass
class DeliveryResult:
    """Result of a single delivery attempt."""
    config_name: str
    recipient: str
    target_location: str
    start_location: str
    steps_taken: int
    optimal_steps: int
    success: bool
    action_history: List[Dict]
    memory_used: Optional[str] = None
    duration_ms: int = 0


@dataclass
class ExperimentResults:
    """Aggregated results for an experiment configuration."""
    config_name: str
    total_runs: int
    successful_runs: int
    avg_steps: float
    min_steps: int
    max_steps: int
    avg_optimal_steps: float
    efficiency_ratio: float  # avg_steps / avg_optimal_steps (lower is better)
    individual_results: List[DeliveryResult]


# Experiment Configurations to Test
EXPERIMENTS = [
    # Baseline - no memory
    ExperimentConfig(
        name="baseline_no_memory",
        use_memory=False,
    ),

    # Recall once at start - just recipient name
    ExperimentConfig(
        name="recall_start_name_only",
        use_memory=True,
        memory_mode="recall_start",
        query_template="{recipient_name}",
        budget="high",
    ),

    # Recall once at start - location question
    ExperimentConfig(
        name="recall_start_location_query",
        use_memory=True,
        memory_mode="recall_start",
        query_template="Where does {recipient_name} work? What floor and side?",
        budget="high",
    ),

    # Reflect per step - with current position context
    ExperimentConfig(
        name="reflect_per_step_with_context",
        use_memory=True,
        memory_mode="reflect_per_step",
        query_template="How do I reach {recipient_name}?",
        reflect_context_template="I am a delivery agent at {current_location}. I need to deliver to {recipient_name}. What should I do next?",
        budget="high",
    ),

    # Recall with background
    ExperimentConfig(
        name="recall_with_background",
        use_memory=True,
        memory_mode="recall_start",
        background="This is a delivery agent learning building layouts. Remember: employee locations (which floor and side they work on), business names, and efficient navigation paths.",
        query_template="Where does {recipient_name} work?",
        budget="high",
    ),

    # Reflect with background
    ExperimentConfig(
        name="reflect_with_background",
        use_memory=True,
        memory_mode="reflect_per_step",
        background="This is a delivery agent learning building layouts. Remember: employee locations (which floor and side they work on), business names, and efficient navigation paths.",
        query_template="Where is {recipient_name} located?",
        reflect_context_template="I am at {current_location}. Guide me to {recipient_name}.",
        budget="high",
    ),

    # Store learnings summary instead of full conversation
    ExperimentConfig(
        name="recall_learnings_summary",
        use_memory=True,
        memory_mode="recall_start",
        query_template="{recipient_name}",
        budget="high",
        store_mode="learnings",
    ),

    # ============ Additional Experiments ============

    # Reflect ONCE at start (not every step) - compare with recall_start
    ExperimentConfig(
        name="reflect_start_once",
        use_memory=True,
        memory_mode="reflect_start",
        query_template="Where does {recipient_name} work and how do I get there?",
        reflect_context_template="I am a delivery agent starting at {current_location}. I need to deliver to {recipient_name}. Give me directions.",
        budget="high",
    ),

    # Reflect once at start with background
    ExperimentConfig(
        name="reflect_start_with_background",
        use_memory=True,
        memory_mode="reflect_start",
        background="This is a delivery agent learning building layouts. Remember employee locations (floor and side) and optimal routes.",
        query_template="How do I reach {recipient_name}?",
        reflect_context_template="I'm at {current_location}. Direct me to {recipient_name}.",
        budget="high",
    ),

    # Recall with learnings storage + background
    ExperimentConfig(
        name="recall_learnings_with_background",
        use_memory=True,
        memory_mode="recall_start",
        background="Remember where each employee works: their floor number and whether they are on the FRONT or BACK side.",
        query_template="{recipient_name} location",
        budget="high",
        store_mode="learnings",
    ),

    # Reflect per step with learnings storage
    ExperimentConfig(
        name="reflect_per_step_learnings",
        use_memory=True,
        memory_mode="reflect_per_step",
        query_template="Where is {recipient_name}?",
        reflect_context_template="At {current_location}, delivering to {recipient_name}. Next action?",
        budget="high",
        store_mode="learnings",
    ),

    # Mid budget comparison - recall
    ExperimentConfig(
        name="recall_mid_budget",
        use_memory=True,
        memory_mode="recall_start",
        query_template="Where does {recipient_name} work?",
        budget="mid",
        store_mode="learnings",
    ),

    # Location summary storage (just "X works at Y")
    ExperimentConfig(
        name="recall_location_summary",
        use_memory=True,
        memory_mode="recall_start",
        query_template="{recipient_name}",
        budget="high",
        store_mode="location_summary",
    ),
]


API_PREFIX = "/v1/default"


def get_or_create_bank(bank_id: str, background: Optional[str] = None) -> str:
    """Ensure bank exists with optional background."""
    try:
        payload = {
            "bank_id": bank_id,
            "name": f"Experiment Bank: {bank_id}",
        }
        if background:
            payload["background"] = background

        resp = requests.post(f"{HINDSIGHT_URL}{API_PREFIX}/banks", json=payload, timeout=10)
        # 200 = created, 409 = already exists (both OK)
    except Exception as e:
        print(f"Create bank error: {e}")

    return bank_id


def clear_bank(bank_id: str):
    """Clear all memories from a bank for fresh experiments."""
    try:
        requests.delete(f"{HINDSIGHT_URL}{API_PREFIX}/banks/{bank_id}", timeout=10)
    except:
        pass


def recall_memories(bank_id: str, query: str, budget: str = "high") -> Optional[str]:
    """Recall memories from Hindsight using direct HTTP."""
    try:
        payload = {
            "query": query,
            "budget": budget,
            "max_tokens": 4096,
        }
        resp = requests.post(
            f"{HINDSIGHT_URL}{API_PREFIX}/banks/{bank_id}/memories/recall",
            json=payload,
            timeout=30
        )
        if resp.status_code == 200:
            data = resp.json()
            results = data.get("results", [])
            if results:
                return "\n".join([f"- {r.get('text', '')}" for r in results])
        return None
    except Exception as e:
        print(f"Recall error: {e}")
        return None


def reflect_memories(bank_id: str, query: str, context: Optional[str] = None, budget: str = "high") -> Optional[str]:
    """Get synthesized reflection from Hindsight using direct HTTP."""
    try:
        payload = {
            "query": query,
            "budget": budget,
        }
        if context:
            payload["context"] = context

        resp = requests.post(
            f"{HINDSIGHT_URL}{API_PREFIX}/banks/{bank_id}/reflect",
            json=payload,
            timeout=60  # Reflect can take longer
        )
        if resp.status_code == 200:
            data = resp.json()
            return data.get("text")
        return None
    except Exception as e:
        print(f"Reflect error: {e}")
        return None


def store_delivery_result(bank_id: str, result: DeliveryResult, store_mode: str):
    """Store delivery result to Hindsight using direct HTTP."""
    try:
        if store_mode == "full_conversation":
            # Store full action history
            content = f"Delivery to {result.recipient} at {result.target_location}.\n"
            content += f"Started at: {result.start_location}\n"
            content += f"Steps taken: {result.steps_taken}\n"
            content += f"Outcome: {'SUCCESS' if result.success else 'FAILED'}\n\n"
            content += "Action history:\n"
            for action in result.action_history:
                content += f"- {action['action']}: {action['result']}\n"

        elif store_mode == "learnings":
            # Store concise learnings
            loc = get_employee_location(result.recipient)
            if loc:
                floor, side, business = loc
                content = f"LEARNED: {result.recipient} works at {business} on Floor {floor} {side.value} side."
                if result.success:
                    # Add efficient path info
                    content += f" Delivery from {result.start_location} took {result.steps_taken} steps."
            else:
                content = f"Delivery to {result.recipient}: {'SUCCESS' if result.success else 'FAILED'}"

        else:  # location_summary
            loc = get_employee_location(result.recipient)
            if loc:
                floor, side, business = loc
                content = f"{result.recipient} works at {business}, Floor {floor}, {side.value} side."
            else:
                content = f"Attempted delivery to {result.recipient}"

        payload = {
            "items": [{
                "content": content,
                "context": "delivery",
            }],
            "async": False,
        }
        resp = requests.post(
            f"{HINDSIGHT_URL}{API_PREFIX}/banks/{bank_id}/memories",
            json=payload,
            timeout=60  # Give time for sync processing
        )
        if resp.status_code != 200:
            print(f"Store warning: {resp.status_code} - {resp.text[:100]}")
    except Exception as e:
        print(f"Store error: {e}")


def run_delivery(
    config: ExperimentConfig,
    bank_id: str,
    recipient_name: str,
    start_floor: int,
    start_side: Side,
) -> DeliveryResult:
    """Run a single delivery with the given configuration."""

    # Setup
    state = AgentState(floor=start_floor, side=start_side)
    state.current_package = Package(recipient_name=recipient_name)
    tools = AgentTools(state)

    target_loc = get_employee_location(recipient_name)
    target_floor, target_side, target_business = target_loc
    optimal = calculate_optimal_steps(start_floor, start_side, target_floor, target_side)

    start_time = time.time()

    # Build system prompt
    system_prompt = "You are a delivery agent in a building. Use the tools to navigate and deliver the package efficiently."

    # Get initial memory if using recall_start or reflect_start
    memory_context = None
    if config.use_memory and config.memory_mode == "recall_start":
        query = config.query_template.format(recipient_name=recipient_name)
        memory_context = recall_memories(bank_id, query, config.budget)
        if memory_context:
            system_prompt += f"\n\nRelevant memories:\n{memory_context}"

    elif config.use_memory and config.memory_mode == "reflect_start":
        # Reflect once at start with initial context
        query = config.query_template.format(recipient_name=recipient_name)
        context = None
        if config.reflect_context_template:
            context = config.reflect_context_template.format(
                current_location=state.location_str(),
                recipient_name=recipient_name,
            )
        memory_context = reflect_memories(bank_id, query, context, config.budget)
        if memory_context:
            system_prompt += f"\n\nMemory guidance:\n{memory_context}"

    # Initial message
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": f"Deliver this package to {recipient_name}. You are currently at {state.location_str()}."},
    ]

    # Run agent loop
    while not state.delivered and state.steps_taken < MAX_STEPS:
        # Get reflection if using reflect_per_step
        if config.use_memory and config.memory_mode == "reflect_per_step":
            query = config.query_template.format(recipient_name=recipient_name)
            context = None
            if config.reflect_context_template:
                context = config.reflect_context_template.format(
                    current_location=state.location_str(),
                    recipient_name=recipient_name,
                )
            reflection = reflect_memories(bank_id, query, context, config.budget)
            if reflection:
                messages.append({
                    "role": "system",
                    "content": f"Memory guidance: {reflection}"
                })

        # Get LLM decision
        try:
            response = completion(
                model=LLM_MODEL,
                messages=messages,
                tools=TOOL_DEFINITIONS,
                tool_choice="required",
                timeout=30,
            )
        except Exception as e:
            print(f"LLM error: {e}")
            break

        # Process tool calls
        message = response.choices[0].message
        if message.tool_calls:
            # Build assistant message with tool calls
            assistant_msg = {
                "role": "assistant",
                "content": message.content or "",
                "tool_calls": [
                    {
                        "id": tc.id,
                        "type": "function",
                        "function": {
                            "name": tc.function.name,
                            "arguments": tc.function.arguments or "{}"
                        }
                    }
                    for tc in message.tool_calls
                ]
            }
            messages.append(assistant_msg)

            # Process ALL tool calls and add responses
            success_found = False
            for tool_call in message.tool_calls:
                tool_name = tool_call.function.name
                try:
                    args = json.loads(tool_call.function.arguments) if tool_call.function.arguments else {}
                except:
                    args = {}

                # Execute tool
                result = tools.execute(tool_name, args)

                # Add tool response
                messages.append({
                    "role": "tool",
                    "tool_call_id": tool_call.id,
                    "content": result,
                })

                # Check for success
                if "SUCCESS" in result:
                    success_found = True

            if success_found:
                break
        else:
            # No tool call, try to continue
            if message.content:
                messages.append({"role": "assistant", "content": message.content})

    duration_ms = int((time.time() - start_time) * 1000)

    return DeliveryResult(
        config_name=config.name,
        recipient=recipient_name,
        target_location=f"Floor {target_floor} {target_side.value} ({target_business})",
        start_location=f"Floor {start_floor} {start_side.value}",
        steps_taken=state.steps_taken,
        optimal_steps=optimal,
        success=state.delivered,
        action_history=state.action_history,
        memory_used=memory_context,
        duration_ms=duration_ms,
    )


def run_experiment(config: ExperimentConfig, num_runs: int = RUNS_PER_CONFIG) -> ExperimentResults:
    """Run multiple deliveries with a configuration and aggregate results."""

    print(f"\n{'='*60}")
    print(f"Running experiment: {config.name}")
    print(f"{'='*60}")

    # Setup bank
    bank_id = f"experiment_{config.name}"
    if config.use_memory:
        clear_bank(bank_id)
        get_or_create_bank(bank_id, config.background)

    results = []

    # Get all employees for testing
    from building import get_all_employees
    all_employees = get_all_employees()

    for run in range(num_runs):
        # Pick random recipient and start
        recipient_name, target_floor, target_side, target_business = random.choice(all_employees)

        # Random start (but not at target location)
        start_floor = random.randint(1, 3)
        start_side = random.choice([Side.FRONT, Side.BACK, Side.MIDDLE])

        # Avoid starting at the exact target
        while start_floor == target_floor and start_side == target_side:
            start_floor = random.randint(1, 3)
            start_side = random.choice([Side.FRONT, Side.BACK, Side.MIDDLE])

        print(f"\nRun {run + 1}/{num_runs}: Deliver to {recipient_name}")
        print(f"  Start: Floor {start_floor} {start_side.value}")
        print(f"  Target: Floor {target_floor} {target_side.value} ({target_business})")

        result = run_delivery(config, bank_id, recipient_name, start_floor, start_side)
        results.append(result)

        print(f"  Steps: {result.steps_taken} (optimal: {result.optimal_steps})")
        print(f"  Success: {result.success}")

        # Store result for learning (if enabled and successful)
        if config.use_memory and result.success:
            store_delivery_result(bank_id, result, config.store_mode)

    # Aggregate
    successful = [r for r in results if r.success]
    all_steps = [r.steps_taken for r in results]
    all_optimal = [r.optimal_steps for r in results]

    avg_steps = sum(all_steps) / len(all_steps) if all_steps else 0
    avg_optimal = sum(all_optimal) / len(all_optimal) if all_optimal else 1

    return ExperimentResults(
        config_name=config.name,
        total_runs=num_runs,
        successful_runs=len(successful),
        avg_steps=round(avg_steps, 2),
        min_steps=min(all_steps) if all_steps else 0,
        max_steps=max(all_steps) if all_steps else 0,
        avg_optimal_steps=round(avg_optimal, 2),
        efficiency_ratio=round(avg_steps / avg_optimal, 2) if avg_optimal > 0 else 0,
        individual_results=results,
    )


def save_results(all_results: List[ExperimentResults], filename: str = "experiment_results.md"):
    """Save experiment results to a markdown file."""

    filepath = os.path.join(os.path.dirname(__file__), filename)

    with open(filepath, "w") as f:
        f.write("# Hindsight Configuration Experiments\n\n")
        f.write(f"**Date:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        f.write(f"**Model:** {LLM_MODEL}\n")
        f.write(f"**Runs per config:** {RUNS_PER_CONFIG}\n\n")

        # Summary table
        f.write("## Summary\n\n")
        f.write("| Config | Success Rate | Avg Steps | Optimal | Efficiency |\n")
        f.write("|--------|--------------|-----------|---------|------------|\n")

        for result in all_results:
            success_rate = f"{result.successful_runs}/{result.total_runs}"
            f.write(f"| {result.config_name} | {success_rate} | {result.avg_steps} | {result.avg_optimal_steps} | {result.efficiency_ratio}x |\n")

        f.write("\n")

        # Detailed results
        f.write("## Detailed Results\n\n")

        for result in all_results:
            f.write(f"### {result.config_name}\n\n")
            f.write(f"- **Total runs:** {result.total_runs}\n")
            f.write(f"- **Successful:** {result.successful_runs}\n")
            f.write(f"- **Average steps:** {result.avg_steps}\n")
            f.write(f"- **Step range:** {result.min_steps} - {result.max_steps}\n")
            f.write(f"- **Efficiency ratio:** {result.efficiency_ratio}x optimal\n\n")

            # Individual runs
            f.write("**Individual runs:**\n\n")
            for i, r in enumerate(result.individual_results):
                status = "✓" if r.success else "✗"
                f.write(f"{i+1}. {status} {r.recipient}: {r.steps_taken} steps (optimal: {r.optimal_steps})\n")
                if r.memory_used:
                    f.write(f"   Memory: {r.memory_used[:100]}...\n")
            f.write("\n")

        # Observations
        f.write("## Observations\n\n")
        f.write("<!-- Add observations after running experiments -->\n\n")

        # Recommendations
        f.write("## Recommendations\n\n")
        f.write("<!-- Add recommendations based on findings -->\n\n")

    print(f"\nResults saved to: {filepath}")
    return filepath


def main():
    """Run all experiments."""

    print("="*60)
    print("HINDSIGHT CONFIGURATION EXPERIMENTS")
    print("="*60)
    print(f"Model: {LLM_MODEL}")
    print(f"Runs per config: {RUNS_PER_CONFIG}")
    print(f"Hindsight URL: {HINDSIGHT_URL}")

    all_results = []

    for config in EXPERIMENTS:
        try:
            result = run_experiment(config)
            all_results.append(result)
        except Exception as e:
            print(f"Error running {config.name}: {e}")
            import traceback
            traceback.print_exc()

    # Save results
    filepath = save_results(all_results)

    # Print summary
    print("\n" + "="*60)
    print("SUMMARY")
    print("="*60)
    print(f"{'Config':<35} {'Success':<10} {'Avg Steps':<12} {'Efficiency'}")
    print("-"*60)

    for result in all_results:
        success = f"{result.successful_runs}/{result.total_runs}"
        print(f"{result.config_name:<35} {success:<10} {result.avg_steps:<12} {result.efficiency_ratio}x")

    return all_results


if __name__ == "__main__":
    main()
