#!/usr/bin/env python3
"""Quick evaluation test to verify fixes before running full 1000-delivery evaluation."""

import os
import sys

# Add the current directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from dotenv import load_dotenv
load_dotenv()

from building import Building
from evaluation import EvalConfig
from app import _run_evaluation

def main():
    # Use the same building as the app (singleton instance)
    from building import get_building
    building = get_building()

    # Test configurations
    configs_to_test = [
        EvalConfig.BASELINE,
        EvalConfig.RECALL_HIGH,
    ]

    num_deliveries = 10  # Quick test
    max_steps = 150

    print(f"\n{'='*60}")
    print(f"EVALUATION TEST - {num_deliveries} deliveries per config")
    print(f"{'='*60}\n")

    for config in configs_to_test:
        print(f"\n--- Running {config.value} ---\n")

        try:
            run_dir, deliveries = _run_evaluation(
                building=building,
                config=config,
                num_deliveries=num_deliveries,
                max_steps=max_steps,
            )

            # Print quick summary
            successes = sum(1 for d in deliveries if d.success)
            with_memory = sum(1 for d in deliveries if d.memories_injected_total > 0)

            print(f"\n  Results for {config.value}:")
            print(f"    Success rate: {successes}/{num_deliveries} ({100*successes/num_deliveries:.1f}%)")
            print(f"    Deliveries with memory injection: {with_memory}/{num_deliveries}")
            print(f"    Results saved to: {run_dir}")

        except Exception as e:
            print(f"  ERROR: {e}")
            import traceback
            traceback.print_exc()

    print(f"\n{'='*60}")
    print("TEST COMPLETE - Check the evaluation_runs directory for detailed results")
    print(f"{'='*60}\n")

if __name__ == "__main__":
    main()
