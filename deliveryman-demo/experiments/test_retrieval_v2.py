"""Test Hindsight retrieval quality - V2.

Uses actual demo format and real LLM summarization.
Tests retrieval quality independently of agent behavior.
"""

import os
import json
import httpx
from datetime import datetime
from dataclasses import dataclass
from typing import Optional

from training_data_v2 import (
    get_all_training_deliveries,
    get_training_data_summarized,
    SUMMARIZATION_PROMPTS,
)

# API Configuration
HINDSIGHT_BASE = os.environ.get("HINDSIGHT_BASE_URL", "http://localhost:8888")
API_PREFIX = "/v1/default"

# Test people - based on training data
TEST_PEOPLE = {
    "known": ["Rachel Green", "Jake Morrison", "Sarah Kim"],
    "adjacent": ["John Smith", "Lisa Park", "Alex Chen"],  # Same locations as known
    "unknown": ["Maria Santos", "Peter Zhang", "Laura Martinez", "Tom Wilson"],
}

# Expected locations (for evaluation)
EXPECTED_LOCATIONS = {
    "Rachel Green": {"business": "Tech Lab", "floor": 3, "side": "front"},
    "Jake Morrison": {"business": "Mail Room", "floor": 1, "side": "back"},
    "Sarah Kim": {"business": "Byte Size Games", "floor": 2, "side": "back"},
    "John Smith": {"business": "Tech Lab", "floor": 3, "side": "front"},
    "Lisa Park": {"business": "Mail Room", "floor": 1, "side": "back"},
    "Alex Chen": {"business": "Byte Size Games", "floor": 2, "side": "back"},
    "Maria Santos": {"business": "Lobby & Reception", "floor": 1, "side": "front"},
    "Peter Zhang": {"business": "Cafe", "floor": 3, "side": "back"},
    "Laura Martinez": {"business": "Cafe", "floor": 3, "side": "back"},
    "Tom Wilson": {"business": "Lobby & Reception", "floor": 1, "side": "front"},
}


@dataclass
class BankConfig:
    """Configuration for a Hindsight bank."""
    name: str
    background: str
    training_style: str  # "full" or summarization style like "S2_generic"


# Bank configurations to test
BANK_CONFIGS = [
    # Full history variants
    BankConfig(
        name="full_history",
        background="This is a delivery agent navigating a building to deliver packages.",
        training_style="full"
    ),
    BankConfig(
        name="full_history_detailed_bg",
        background="Remember delivery locations, optimal routes, and any shortcuts that speed up future deliveries.",
        training_style="full"
    ),
    # Summarized variants - different prompt styles
    BankConfig(
        name="summarized_minimal",
        background="This is a delivery agent navigating a building.",
        training_style="S1_minimal"
    ),
    BankConfig(
        name="summarized_short",
        background="Remember delivery locations and shortcuts.",
        training_style="S2_short"
    ),
    BankConfig(
        name="summarized_detailed",
        background="Remember delivery locations, optimal routes, and shortcuts for future deliveries.",
        training_style="S3_detailed"
    ),
    BankConfig(
        name="summarized_comprehensive",
        background="Remember employee locations, navigation paths, shortcuts, and any limitations discovered.",
        training_style="S4_comprehensive"
    ),
]


def create_bank(bank_id: str, background: str) -> bool:
    """Create a Hindsight bank."""
    try:
        httpx.delete(f"{HINDSIGHT_BASE}{API_PREFIX}/banks/{bank_id}", timeout=10)
    except:
        pass

    try:
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
        items = [{"content": m, "context": "delivery history"} for m in memories]
        response = httpx.post(
            f"{HINDSIGHT_BASE}{API_PREFIX}/banks/{bank_id}/memories",
            json={"items": items, "async": False},
            timeout=120
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


def setup_bank(config: BankConfig, api_key: Optional[str] = None) -> bool:
    """Set up a bank with training data."""
    print(f"\nSetting up bank: {config.name}")

    if not create_bank(config.name, config.background):
        print(f"  Failed to create bank")
        return False

    # Get training data
    if config.training_style == "full":
        memories = get_all_training_deliveries()
        print(f"  Using full delivery histories ({len(memories)} deliveries)")
    else:
        print(f"  Generating summaries with style: {config.training_style}")
        try:
            memories = get_training_data_summarized(config.training_style, api_key=api_key)
            print(f"  Generated {len(memories)} summaries")
        except Exception as e:
            print(f"  Failed to generate summaries: {e}")
            return False

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

    # Convert response to string for searching
    response_text = json.dumps(response).lower()

    # Check for business name
    has_business = expected["business"].lower() in response_text

    # Check for floor (flexible matching)
    floor_str = str(expected["floor"])
    has_floor = (
        f"floor {floor_str}" in response_text or
        f"floor{floor_str}" in response_text or
        f"level {floor_str}" in response_text
    )

    # Check for side (flexible matching)
    side = expected["side"].lower()
    has_side = side in response_text

    score = sum([has_floor, has_side, has_business]) / 3.0

    return {
        "score": score,
        "has_floor": has_floor,
        "has_side": has_side,
        "has_business": has_business,
        "expected": expected
    }


def evaluate_fire_escape_knowledge(response: dict) -> dict:
    """Evaluate if the response mentions fire escape shortcut."""
    response_text = json.dumps(response).lower()

    mentions_fire_escape = "fire escape" in response_text or "fire_escape" in response_text
    mentions_shortcut = "shortcut" in response_text or "faster" in response_text or "quick" in response_text

    return {
        "mentions_fire_escape": mentions_fire_escape,
        "mentions_shortcut": mentions_shortcut,
        "score": 1.0 if mentions_fire_escape else (0.5 if mentions_shortcut else 0.0)
    }


def run_one_shot_retrieval_test(bank_id: str, method: str = "recall") -> list[dict]:
    """Test one-shot retrieval for all test people."""
    results = []

    for category, people in TEST_PEOPLE.items():
        for person in people:
            if method == "recall":
                response = recall_memories(bank_id, person)
            else:
                response = reflect_memories(
                    bank_id,
                    query=f"Where does {person} work? How do I deliver a package to them?",
                    context=f"I need to deliver a package to {person}."
                )

            location_eval = evaluate_location_extraction(response, person)

            results.append({
                "bank_id": bank_id,
                "method": method,
                "category": category,
                "person": person,
                "response": response,
                "location_score": location_eval["score"],
                "location_details": location_eval
            })

    return results


def run_fire_escape_knowledge_test(bank_id: str) -> dict:
    """Test if the bank knows about the fire escape shortcut."""

    # Test with recall
    recall_response = recall_memories(bank_id, "fire escape shortcut")
    recall_eval = evaluate_fire_escape_knowledge(recall_response)

    # Test with reflect
    reflect_response = reflect_memories(
        bank_id,
        query="Are there any shortcuts in this building?",
        context="I want to deliver packages as fast as possible."
    )
    reflect_eval = evaluate_fire_escape_knowledge(reflect_response)

    return {
        "bank_id": bank_id,
        "recall": {
            "response": recall_response,
            "eval": recall_eval
        },
        "reflect": {
            "response": reflect_response,
            "eval": reflect_eval
        }
    }


def run_step_guidance_test(bank_id: str) -> list[dict]:
    """Test step-by-step guidance for deliveries."""
    scenarios = [
        {
            "name": "rachel_from_f1_front",
            "query": "How do I get to Rachel Green from here?",
            "context": "I am at Floor 1 front side (Lobby & Reception). I see a fire escape here. I need to deliver to Rachel Green.",
            "fire_escape_optimal": True,
        },
        {
            "name": "rachel_from_f2",
            "query": "How do I get to Rachel Green?",
            "context": "I am at Floor 2 in the middle hallway. I need to deliver to Rachel Green.",
            "fire_escape_optimal": False,  # Elevator up is faster
        },
        {
            "name": "jake_from_f3_front",
            "query": "How do I get to Jake Morrison?",
            "context": "I am at Floor 3 front side (Tech Lab). I need to deliver to Jake Morrison.",
            "fire_escape_optimal": False,  # Jake is on back side, fire escape goes to front
        },
    ]

    results = []
    for scenario in scenarios:
        response = reflect_memories(
            bank_id,
            query=scenario["query"],
            context=scenario["context"]
        )

        fire_escape_eval = evaluate_fire_escape_knowledge(response)
        suggests_fire_escape = fire_escape_eval["mentions_fire_escape"]

        results.append({
            "bank_id": bank_id,
            "scenario": scenario["name"],
            "fire_escape_optimal": scenario["fire_escape_optimal"],
            "suggests_fire_escape": suggests_fire_escape,
            "correct_suggestion": suggests_fire_escape == scenario["fire_escape_optimal"],
            "response": response
        })

    return results


def run_all_tests(api_key: Optional[str] = None):
    """Run all retrieval quality tests."""
    print("=" * 60)
    print("HINDSIGHT RETRIEVAL QUALITY TESTS - V2")
    print(f"Date: {datetime.now().isoformat()}")
    print("=" * 60)

    # Set up all banks
    print("\n## Setting Up Banks\n")
    active_banks = []
    for config in BANK_CONFIGS:
        if setup_bank(config, api_key=api_key):
            active_banks.append(config.name)
        else:
            print(f"  Skipping {config.name}")

    print(f"\nActive banks: {len(active_banks)}/{len(BANK_CONFIGS)}")

    if not active_banks:
        print("No banks set up successfully. Exiting.")
        return None

    all_results = {
        "one_shot_recall": [],
        "one_shot_reflect": [],
        "fire_escape_knowledge": [],
        "step_guidance": [],
    }

    # Run one-shot tests
    print("\n## One-Shot Retrieval Tests\n")
    for bank_id in active_banks:
        print(f"\nTesting bank: {bank_id}")

        recall_results = run_one_shot_retrieval_test(bank_id, "recall")
        all_results["one_shot_recall"].extend(recall_results)

        reflect_results = run_one_shot_retrieval_test(bank_id, "reflect")
        all_results["one_shot_reflect"].extend(reflect_results)

        recall_avg = sum(r["location_score"] for r in recall_results) / len(recall_results)
        reflect_avg = sum(r["location_score"] for r in reflect_results) / len(reflect_results)
        print(f"  Recall avg: {recall_avg:.2f}, Reflect avg: {reflect_avg:.2f}")

    # Run fire escape knowledge tests
    print("\n## Fire Escape Knowledge Tests\n")
    for bank_id in active_banks:
        result = run_fire_escape_knowledge_test(bank_id)
        all_results["fire_escape_knowledge"].append(result)
        print(f"{bank_id}: recall={result['recall']['eval']['score']:.1f}, reflect={result['reflect']['eval']['score']:.1f}")

    # Run step guidance tests
    print("\n## Step-by-Step Guidance Tests\n")
    for bank_id in active_banks:
        results = run_step_guidance_test(bank_id)
        all_results["step_guidance"].extend(results)
        correct = sum(1 for r in results if r["correct_suggestion"])
        print(f"{bank_id}: {correct}/{len(results)} correct")

    # Generate summary
    print("\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)

    print("\n### One-Shot Location Scores\n")
    print("| Bank | Recall | Reflect |")
    print("|------|--------|---------|")
    for bank_id in active_banks:
        recall_results = [r for r in all_results["one_shot_recall"] if r["bank_id"] == bank_id]
        reflect_results = [r for r in all_results["one_shot_reflect"] if r["bank_id"] == bank_id]
        recall_avg = sum(r["location_score"] for r in recall_results) / len(recall_results)
        reflect_avg = sum(r["location_score"] for r in reflect_results) / len(reflect_results)
        print(f"| {bank_id} | {recall_avg:.2f} | {reflect_avg:.2f} |")

    print("\n### Fire Escape Knowledge\n")
    print("| Bank | Recall | Reflect |")
    print("|------|--------|---------|")
    for result in all_results["fire_escape_knowledge"]:
        bank_id = result["bank_id"]
        recall_score = result["recall"]["eval"]["score"]
        reflect_score = result["reflect"]["eval"]["score"]
        print(f"| {bank_id} | {recall_score:.1f} | {reflect_score:.1f} |")

    print("\n### Step Guidance Accuracy\n")
    print("| Bank | Correct | Total |")
    print("|------|---------|-------|")
    for bank_id in active_banks:
        results = [r for r in all_results["step_guidance"] if r["bank_id"] == bank_id]
        correct = sum(1 for r in results if r["correct_suggestion"])
        print(f"| {bank_id} | {correct} | {len(results)} |")

    # Save results
    output_file = "retrieval_test_results_v2.json"
    with open(output_file, "w") as f:
        json.dump(all_results, f, indent=2, default=str)
    print(f"\nDetailed results saved to: {output_file}")

    return all_results


if __name__ == "__main__":
    api_key = os.environ.get("OPENAI_API_KEY")
    results = run_all_tests(api_key=api_key)
