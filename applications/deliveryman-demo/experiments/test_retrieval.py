"""Test Hindsight retrieval quality independently of agent behavior.

This experiment tests:
1. One-shot retrieval: Given a name, what does Hindsight return?
2. Step-by-step guidance: Given current state, what guidance does Hindsight provide?

Test categories:
- KNOWN: People we have training data for (Rachel Green, Jake Morrison, Sarah Kim)
- ADJACENT: People at same location as KNOWN (John Smith - same as Rachel, Lisa Park - same as Jake)
- UNKNOWN: People with no training data (Maria Santos, Alex Chen, Peter Zhang)
"""

import os
import json
import httpx
from datetime import datetime
from typing import Optional
from dataclasses import dataclass

from training_data import (
    get_training_data_full,
    get_training_data_summarized,
    get_all_training_deliveries,
    SUMMARIZATION_PROMPTS,
)
from building_medium import (
    Side,
    get_employee_location,
    calculate_optimal_steps,
    FIRE_ESCAPE,
)

# API Configuration
HINDSIGHT_BASE = os.environ.get("HINDSIGHT_BASE_URL", "http://localhost:8888")
API_PREFIX = "/v1/default"
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY", "")

# Test configuration
TEST_PEOPLE = {
    "known": ["Rachel Green", "Jake Morrison", "Sarah Kim"],
    "adjacent": ["John Smith", "Lisa Park", "Alex Chen"],  # Same location as known people
    "unknown": ["Maria Santos", "Peter Zhang", "Laura Martinez", "Tom Wilson"],
}

# Expected outcomes for evaluation
EXPECTED_LOCATIONS = {
    "Rachel Green": (3, Side.FRONT, "Tech Lab"),
    "Jake Morrison": (1, Side.BACK, "Mail Room"),
    "Sarah Kim": (2, Side.BACK, "Game Studio"),
    "John Smith": (3, Side.FRONT, "Tech Lab"),
    "Lisa Park": (1, Side.BACK, "Mail Room"),
    "Alex Chen": (2, Side.BACK, "Game Studio"),
    "Maria Santos": (1, Side.FRONT, "Reception"),
    "Peter Zhang": (3, Side.BACK, "Cafe"),
    "Laura Martinez": (3, Side.BACK, "Cafe"),
    "Tom Wilson": (1, Side.FRONT, "Reception"),
}

EXPECTED_FIRE_ESCAPE_KNOWLEDGE = {
    "from_floor_1": "fire escape from Floor 1 FRONT to Floor 3 FRONT",
    "from_floor_3": "fire escape from Floor 3 FRONT to Floor 1 FRONT",
}


@dataclass
class BankConfig:
    """Configuration for a Hindsight bank."""
    name: str
    background: str
    training_style: str  # "full" or summarization style like "S3_path_focus"


# Different bank configurations to test
BANK_CONFIGS = [
    BankConfig(
        name="full_history",
        background="This is a delivery agent navigating a building. Remember employee locations and any shortcuts discovered.",
        training_style="full"
    ),
    BankConfig(
        name="full_history_location_bg",
        background="Remember where each employee works: floor number (1-3) and side (FRONT or BACK).",
        training_style="full"
    ),
    BankConfig(
        name="summarized_basic",
        background="Remember employee locations and delivery tips.",
        training_style="S1_basic"
    ),
    BankConfig(
        name="summarized_location",
        background="Remember where each employee works: floor number (1-3) and side (FRONT or BACK).",
        training_style="S2_location_focus"
    ),
    BankConfig(
        name="summarized_path",
        background="Remember employee locations and optimal navigation paths including shortcuts.",
        training_style="S3_path_focus"
    ),
    BankConfig(
        name="summarized_structured",
        background="Remember employee locations, navigation paths, and delivery tips.",
        training_style="S4_structured"
    ),
]


def create_bank(bank_id: str, background: str) -> bool:
    """Create a Hindsight bank."""
    try:
        # First try to delete if exists
        httpx.delete(f"{HINDSIGHT_BASE}{API_PREFIX}/banks/{bank_id}", timeout=10)
    except:
        pass

    try:
        # Bank creation is PUT to /banks/{bank_id}
        response = httpx.put(
            f"{HINDSIGHT_BASE}{API_PREFIX}/banks/{bank_id}",
            json={"background": background},
            timeout=10
        )
        return response.status_code in [200, 201]
    except Exception as e:
        print(f"Error creating bank {bank_id}: {e}")
        return False


def retain_memories(bank_id: str, memories: list[str]) -> bool:
    """Store memories in a bank synchronously."""
    try:
        items = [{"content": m, "context": "delivery training"} for m in memories]
        response = httpx.post(
            f"{HINDSIGHT_BASE}{API_PREFIX}/banks/{bank_id}/memories",
            json={"items": items, "async": False},
            timeout=120  # Sync retain can take a while
        )
        if response.status_code != 200:
            print(f"  Retain failed: {response.status_code} - {response.text[:200]}")
        return response.status_code == 200
    except Exception as e:
        print(f"Error retaining to {bank_id}: {e}")
        return False


def recall_memories(bank_id: str, query: str, budget: str = "high") -> dict:
    """Recall memories from a bank."""
    try:
        response = httpx.post(
            f"{HINDSIGHT_BASE}{API_PREFIX}/banks/{bank_id}/memories/recall",
            json={"query": query, "budget": budget},
            timeout=30
        )
        if response.status_code == 200:
            return response.json()
        return {"error": f"Status {response.status_code}"}
    except Exception as e:
        return {"error": str(e)}


def reflect_memories(bank_id: str, query: str, context: str = "", budget: str = "high") -> dict:
    """Reflect on memories from a bank."""
    try:
        payload = {"query": query, "budget": budget}
        if context:
            payload["context"] = context
        response = httpx.post(
            f"{HINDSIGHT_BASE}{API_PREFIX}/banks/{bank_id}/reflect",
            json=payload,
            timeout=30
        )
        if response.status_code == 200:
            return response.json()
        return {"error": f"Status {response.status_code}"}
    except Exception as e:
        return {"error": str(e)}


def setup_bank(config: BankConfig) -> bool:
    """Set up a bank with training data."""
    print(f"\nSetting up bank: {config.name}")

    # Create bank
    if not create_bank(config.name, config.background):
        print(f"  Failed to create bank")
        return False

    # Get training data
    if config.training_style == "full":
        memories = get_training_data_full()
    else:
        memories = get_training_data_summarized(config.training_style)

    # Store memories
    if not retain_memories(config.name, memories):
        print(f"  Failed to retain memories")
        return False

    print(f"  Stored {len(memories)} memories")
    return True


def evaluate_location_extraction(response: dict, person: str) -> dict:
    """Evaluate if the response correctly identifies the person's location."""
    expected = EXPECTED_LOCATIONS.get(person)
    if not expected:
        return {"score": 0, "reason": "Unknown person"}

    floor, side, business = expected
    response_text = str(response).lower()

    # Check for floor
    has_floor = str(floor) in response_text or f"floor {floor}" in response_text

    # Check for side
    has_side = side.value.lower() in response_text

    # Check for business
    has_business = business.lower() in response_text

    score = sum([has_floor, has_side, has_business]) / 3.0

    return {
        "score": score,
        "has_floor": has_floor,
        "has_side": has_side,
        "has_business": has_business,
        "expected": f"Floor {floor} {side.value} ({business})"
    }


def evaluate_fire_escape_knowledge(response: dict, current_floor: int) -> dict:
    """Evaluate if the response mentions fire escape when relevant."""
    response_text = str(response).lower()

    mentions_fire_escape = "fire escape" in response_text or "fire_escape" in response_text

    # Check if it mentions the correct connection
    if current_floor == 1:
        mentions_correct = "floor 3" in response_text or "3 front" in response_text
    elif current_floor == 3:
        mentions_correct = "floor 1" in response_text or "1 front" in response_text
    else:
        mentions_correct = False  # Fire escape not directly accessible from floor 2

    return {
        "mentions_fire_escape": mentions_fire_escape,
        "mentions_correct_destination": mentions_correct,
        "score": 1.0 if (mentions_fire_escape and mentions_correct) else (0.5 if mentions_fire_escape else 0.0)
    }


def run_one_shot_retrieval_test(bank_id: str, method: str = "recall") -> list[dict]:
    """Test one-shot retrieval for all test people.

    Args:
        bank_id: The bank to query
        method: "recall" or "reflect"
    """
    results = []

    for category, people in TEST_PEOPLE.items():
        for person in people:
            # Query for this person
            query = person

            if method == "recall":
                response = recall_memories(bank_id, query)
            else:
                response = reflect_memories(
                    bank_id,
                    query=f"Where does {person} work?",
                    context=f"I need to deliver a package to {person}."
                )

            # Evaluate
            location_eval = evaluate_location_extraction(response, person)

            results.append({
                "bank_id": bank_id,
                "method": method,
                "category": category,
                "person": person,
                "query": query,
                "response": response,
                "location_score": location_eval["score"],
                "location_details": location_eval
            })

    return results


def run_step_by_step_guidance_test(bank_id: str) -> list[dict]:
    """Test step-by-step guidance for delivery to known people.

    Simulates: Agent at Floor 1 FRONT, needs to deliver to Rachel Green (Floor 3 FRONT).
    Optimal path uses fire escape (2 steps: use_fire_escape + deliver).
    Test if Hindsight suggests the fire escape.
    """
    results = []

    # Scenario: Deliver to Rachel Green from Floor 1 FRONT
    # Optimal: use_fire_escape -> deliver_package (2 tool calls)
    scenarios = [
        {
            "name": "rachel_from_f1_front",
            "recipient": "Rachel Green",
            "current_floor": 1,
            "current_side": Side.FRONT,
            "target_floor": 3,
            "target_side": Side.FRONT,
            "fire_escape_optimal": True,
            "context": "I am at Floor 1 FRONT (Reception). I need to deliver to Rachel Green. There is a fire escape here that goes to Floor 3 FRONT.",
        },
        {
            "name": "rachel_from_f1_middle",
            "recipient": "Rachel Green",
            "current_floor": 1,
            "current_side": Side.MIDDLE,
            "target_floor": 3,
            "target_side": Side.FRONT,
            "fire_escape_optimal": True,  # go_to_front + fire_escape is 2, vs go_up + go_up + go_to_front is 3
            "context": "I am at Floor 1 MIDDLE (elevator lobby). I need to deliver to Rachel Green at Floor 3 FRONT.",
        },
        {
            "name": "rachel_from_f2_middle",
            "recipient": "Rachel Green",
            "current_floor": 2,
            "current_side": Side.MIDDLE,
            "target_floor": 3,
            "target_side": Side.FRONT,
            "fire_escape_optimal": False,  # go_up + go_to_front is 2 steps, fire escape would be 3
            "context": "I am at Floor 2 MIDDLE (elevator lobby). I need to deliver to Rachel Green at Floor 3 FRONT.",
        },
        {
            "name": "jake_from_f3_front",
            "recipient": "Jake Morrison",
            "current_floor": 3,
            "current_side": Side.FRONT,
            "target_floor": 1,
            "target_side": Side.BACK,
            "fire_escape_optimal": False,  # Fire escape goes to 1 FRONT, still need to go to BACK
            "context": "I am at Floor 3 FRONT (Tech Lab). I need to deliver to Jake Morrison at Floor 1 BACK (Mail Room).",
        },
    ]

    for scenario in scenarios:
        # Calculate optimal path
        optimal_steps, optimal_path = calculate_optimal_steps(
            scenario["current_floor"],
            scenario["current_side"],
            scenario["target_floor"],
            scenario["target_side"]
        )

        # Query Hindsight
        query = f"How should I get to {scenario['recipient']} from my current location?"
        response = reflect_memories(
            bank_id,
            query=query,
            context=scenario["context"]
        )

        # Evaluate fire escape knowledge
        fire_escape_eval = evaluate_fire_escape_knowledge(
            response,
            scenario["current_floor"]
        )

        # Check if response suggests fire escape when optimal
        response_text = str(response).lower()
        suggests_fire_escape = "fire escape" in response_text or "fire_escape" in response_text

        results.append({
            "bank_id": bank_id,
            "scenario": scenario["name"],
            "recipient": scenario["recipient"],
            "current_location": f"Floor {scenario['current_floor']} {scenario['current_side'].value}",
            "target_location": f"Floor {scenario['target_floor']} {scenario['target_side'].value}",
            "optimal_steps": optimal_steps,
            "optimal_path": optimal_path,
            "fire_escape_optimal": scenario["fire_escape_optimal"],
            "suggests_fire_escape": suggests_fire_escape,
            "correct_suggestion": suggests_fire_escape == scenario["fire_escape_optimal"],
            "fire_escape_eval": fire_escape_eval,
            "response": response
        })

    return results


def run_all_tests():
    """Run all retrieval quality tests."""
    print("=" * 60)
    print("HINDSIGHT RETRIEVAL QUALITY TESTS")
    print(f"Date: {datetime.now().isoformat()}")
    print("=" * 60)

    # Set up all banks
    print("\n## Setting Up Banks\n")
    active_banks = []
    for config in BANK_CONFIGS:
        if setup_bank(config):
            active_banks.append(config.name)
        else:
            print(f"  Skipping {config.name}")

    print(f"\nActive banks: {len(active_banks)}/{len(BANK_CONFIGS)}")

    all_results = {
        "one_shot_recall": [],
        "one_shot_reflect": [],
        "step_by_step": [],
    }

    # Run one-shot tests
    print("\n## One-Shot Retrieval Tests\n")
    for bank_id in active_banks:
        print(f"\nTesting bank: {bank_id}")

        # Test recall
        recall_results = run_one_shot_retrieval_test(bank_id, "recall")
        all_results["one_shot_recall"].extend(recall_results)

        # Test reflect
        reflect_results = run_one_shot_retrieval_test(bank_id, "reflect")
        all_results["one_shot_reflect"].extend(reflect_results)

        # Summarize
        recall_avg = sum(r["location_score"] for r in recall_results) / len(recall_results)
        reflect_avg = sum(r["location_score"] for r in reflect_results) / len(reflect_results)
        print(f"  Recall avg location score: {recall_avg:.2f}")
        print(f"  Reflect avg location score: {reflect_avg:.2f}")

    # Run step-by-step tests
    print("\n## Step-by-Step Guidance Tests\n")
    for bank_id in active_banks:
        print(f"\nTesting bank: {bank_id}")
        step_results = run_step_by_step_guidance_test(bank_id)
        all_results["step_by_step"].extend(step_results)

        correct = sum(1 for r in step_results if r["correct_suggestion"])
        print(f"  Correct fire escape suggestions: {correct}/{len(step_results)}")

    # Generate summary report
    print("\n" + "=" * 60)
    print("SUMMARY REPORT")
    print("=" * 60)

    # One-shot recall summary by bank and category
    print("\n### One-Shot Recall - Location Scores by Bank and Category\n")
    print("| Bank | Known | Adjacent | Unknown | Avg |")
    print("|------|-------|----------|---------|-----|")
    for bank_id in active_banks:
        bank_results = [r for r in all_results["one_shot_recall"] if r["bank_id"] == bank_id]
        scores = {}
        for cat in ["known", "adjacent", "unknown"]:
            cat_results = [r for r in bank_results if r["category"] == cat]
            scores[cat] = sum(r["location_score"] for r in cat_results) / len(cat_results) if cat_results else 0
        avg = sum(scores.values()) / len(scores)
        print(f"| {bank_id} | {scores['known']:.2f} | {scores['adjacent']:.2f} | {scores['unknown']:.2f} | {avg:.2f} |")

    # One-shot reflect summary
    print("\n### One-Shot Reflect - Location Scores by Bank and Category\n")
    print("| Bank | Known | Adjacent | Unknown | Avg |")
    print("|------|-------|----------|---------|-----|")
    for bank_id in active_banks:
        bank_results = [r for r in all_results["one_shot_reflect"] if r["bank_id"] == bank_id]
        scores = {}
        for cat in ["known", "adjacent", "unknown"]:
            cat_results = [r for r in bank_results if r["category"] == cat]
            scores[cat] = sum(r["location_score"] for r in cat_results) / len(cat_results) if cat_results else 0
        avg = sum(scores.values()) / len(scores)
        print(f"| {bank_id} | {scores['known']:.2f} | {scores['adjacent']:.2f} | {scores['unknown']:.2f} | {avg:.2f} |")

    # Step-by-step summary
    print("\n### Step-by-Step Guidance - Fire Escape Suggestion Accuracy\n")
    print("| Bank | Correct | Total | Accuracy |")
    print("|------|---------|-------|----------|")
    for bank_id in active_banks:
        bank_results = [r for r in all_results["step_by_step"] if r["bank_id"] == bank_id]
        correct = sum(1 for r in bank_results if r["correct_suggestion"])
        total = len(bank_results)
        acc = correct / total if total > 0 else 0
        print(f"| {bank_id} | {correct} | {total} | {acc:.0%} |")

    # Save detailed results
    output_file = "retrieval_test_results.json"
    with open(output_file, "w") as f:
        json.dump(all_results, f, indent=2, default=str)
    print(f"\nDetailed results saved to: {output_file}")

    return all_results


if __name__ == "__main__":
    results = run_all_tests()
