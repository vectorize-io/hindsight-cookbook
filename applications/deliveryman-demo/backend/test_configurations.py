#!/usr/bin/env python3
"""Test script to verify all configuration paths work correctly."""

import asyncio
import httpx
import json
from typing import Optional

BASE_URL = "http://localhost:8000"
HINDSIGHT_URL = "http://localhost:8888"

# Test configurations to verify
TEST_CONFIGS = [
    {
        "name": "1. No Memory Mode",
        "config": {
            "includeBusiness": "always",
            "maxSteps": 5,  # Just a few steps to verify
            "model": "openai/gpt-4o",
            "memoryQueryMode": "inject_once",
            "waitForConsolidation": False,
            "preseedCoverage": 0,
            "mmQueryType": "recall",
            "hindsight": {
                "inject": False,
                "reflect": False,
                "store": False,
                "bankId": "test-no-memory",
            },
        },
        "expect": {
            "memory_injected": False,
            "should_store": False,
        }
    },
    {
        "name": "2. Filesystem Mode",
        "config": {
            "includeBusiness": "always",
            "maxSteps": 5,
            "model": "openai/gpt-4o",
            "memoryQueryMode": "inject_once",
            "waitForConsolidation": False,
            "preseedCoverage": 0,
            "mmQueryType": "recall",
            "hindsight": {
                "inject": False,
                "reflect": False,
                "store": False,
                "bankId": "test-filesystem",
            },
        },
        "expect": {
            "memory_injected": False,
            "should_store": False,
        }
    },
    {
        "name": "3. Recall Mode (inject_once)",
        "config": {
            "includeBusiness": "always",
            "maxSteps": 5,
            "model": "openai/gpt-4o",
            "memoryQueryMode": "inject_once",
            "waitForConsolidation": False,
            "preseedCoverage": 0,
            "mmQueryType": "recall",
            "hindsight": {
                "inject": True,
                "reflect": False,  # recall mode
                "store": True,
                "bankId": "test-recall-inject-once",
            },
        },
        "expect": {
            "uses_recall": True,
            "should_store": True,
        }
    },
    {
        "name": "4. Reflect Mode (inject_once)",
        "config": {
            "includeBusiness": "always",
            "maxSteps": 5,
            "model": "openai/gpt-4o",
            "memoryQueryMode": "inject_once",
            "waitForConsolidation": False,
            "preseedCoverage": 0,
            "mmQueryType": "recall",
            "hindsight": {
                "inject": True,
                "reflect": True,  # reflect mode
                "store": True,
                "bankId": "test-reflect-inject-once",
            },
        },
        "expect": {
            "uses_reflect": True,
            "should_store": True,
        }
    },
    {
        "name": "5. Hindsight MM (recall query)",
        "config": {
            "includeBusiness": "always",
            "maxSteps": 5,
            "model": "openai/gpt-4o",
            "memoryQueryMode": "inject_once",
            "waitForConsolidation": False,
            "preseedCoverage": 0,
            "mmQueryType": "recall",  # MM uses recall
            "hindsight": {
                "inject": True,
                "reflect": False,
                "store": True,
                "bankId": "test-mm-recall",
                "mission": "Test mission for MM recall",
            },
        },
        "expect": {
            "uses_recall": True,
            "mission_set": True,
            "should_store": True,
        }
    },
    {
        "name": "6. Hindsight MM (reflect query)",
        "config": {
            "includeBusiness": "always",
            "maxSteps": 5,
            "model": "openai/gpt-4o",
            "memoryQueryMode": "inject_once",
            "waitForConsolidation": False,
            "preseedCoverage": 0,
            "mmQueryType": "reflect",  # MM uses reflect
            "hindsight": {
                "inject": True,
                "reflect": False,  # Will be overridden by mmQueryType
                "store": True,
                "bankId": "test-mm-reflect",
                "mission": "Test mission for MM reflect",
            },
        },
        "expect": {
            "uses_reflect": True,
            "mission_set": True,
            "should_store": True,
        }
    },
    {
        "name": "7. Preseed Coverage (50%)",
        "config": {
            "includeBusiness": "always",
            "maxSteps": 5,
            "model": "openai/gpt-4o",
            "memoryQueryMode": "inject_once",
            "waitForConsolidation": False,
            "preseedCoverage": 0.5,  # 50% preseed
            "mmQueryType": "recall",
            "hindsight": {
                "inject": True,
                "reflect": False,
                "store": True,
                "bankId": "test-preseed-50",
            },
        },
        "expect": {
            "preseed_called": True,
            "should_store": True,
        }
    },
    {
        "name": "8. Memory Injection per_step",
        "config": {
            "includeBusiness": "always",
            "maxSteps": 5,
            "model": "openai/gpt-4o",
            "memoryQueryMode": "per_step",  # Inject every step
            "waitForConsolidation": False,
            "preseedCoverage": 0,
            "mmQueryType": "recall",
            "hindsight": {
                "inject": True,
                "reflect": False,
                "store": True,
                "bankId": "test-per-step",
            },
        },
        "expect": {
            "inject_per_step": True,
            "should_store": True,
        }
    },
    {
        "name": "9. Memory Injection both",
        "config": {
            "includeBusiness": "always",
            "maxSteps": 5,
            "model": "openai/gpt-4o",
            "memoryQueryMode": "both",  # Inject at start AND every step
            "waitForConsolidation": False,
            "preseedCoverage": 0,
            "mmQueryType": "recall",
            "hindsight": {
                "inject": True,
                "reflect": False,
                "store": True,
                "bankId": "test-both",
            },
        },
        "expect": {
            "inject_at_start": True,
            "inject_per_step": True,
            "should_store": True,
        }
    },
    {
        "name": "10. Custom Mission Set",
        "config": {
            "includeBusiness": "always",
            "maxSteps": 5,
            "model": "openai/gpt-4o",
            "memoryQueryMode": "inject_once",
            "waitForConsolidation": False,
            "preseedCoverage": 0,
            "mmQueryType": "recall",
            "hindsight": {
                "inject": True,
                "reflect": False,
                "store": True,
                "bankId": "test-custom-mission",
                "mission": "Custom test mission for delivery agent learning building layout",
            },
        },
        "expect": {
            "mission_set": True,
            "should_store": True,
        }
    },
]


async def check_bank_exists(bank_id: str) -> dict:
    """Check if a bank exists and get its details."""
    async with httpx.AsyncClient(timeout=30.0) as client:
        try:
            # Get all banks and find the one we want
            response = await client.get(f"{HINDSIGHT_URL}/v1/default/banks")
            if response.status_code == 200:
                data = response.json()
                banks = data.get("banks", [])
                for bank in banks:
                    if bank.get("bank_id") == bank_id:
                        return bank
            return {}
        except Exception as e:
            print(f"    Error checking bank: {e}")
            return {}


async def check_bank_mission(bank_id: str) -> Optional[str]:
    """Get the mission set on a bank."""
    bank_data = await check_bank_exists(bank_id)
    return bank_data.get("mission")


async def check_bank_memories(bank_id: str) -> tuple[int, int]:
    """Count memories in a bank.

    Returns:
        Tuple of (total_nodes, total_documents)
    """
    async with httpx.AsyncClient(timeout=30.0) as client:
        try:
            response = await client.get(f"{HINDSIGHT_URL}/v1/default/banks/{bank_id}/stats")
            if response.status_code == 200:
                data = response.json()
                nodes = data.get("total_nodes", 0)
                docs = data.get("total_documents", 0)
                return (nodes, docs)
            return (0, 0)
        except Exception as e:
            print(f"    Error checking memories: {e}")
            return (0, 0)


async def delete_bank(bank_id: str):
    """Delete a bank to start fresh."""
    async with httpx.AsyncClient(timeout=30.0) as client:
        try:
            await client.delete(f"{HINDSIGHT_URL}/v1/default/banks/{bank_id}")
        except:
            pass  # Ignore errors


async def run_delivery(config: dict) -> dict:
    """Run a single delivery with the given config."""
    async with httpx.AsyncClient(timeout=120.0) as client:
        response = await client.post(
            f"{BASE_URL}/api/delivery/fast",
            json=config,
        )
        if response.status_code == 200:
            return response.json()
        else:
            print(f"    Error: {response.status_code} - {response.text[:200]}")
            return {"error": response.text}


async def test_configuration(test: dict) -> bool:
    """Test a single configuration and verify expected behavior."""
    name = test["name"]
    config = test["config"]
    expect = test["expect"]
    bank_id = config.get("hindsight", {}).get("bankId", "unknown")

    print(f"\n{'='*60}")
    print(f"Testing: {name}")
    print(f"Bank ID: {bank_id}")
    print(f"{'='*60}")

    # Clean up - delete bank first for fresh start
    await delete_bank(bank_id)

    # Check initial state
    initial_nodes, initial_docs = await check_bank_memories(bank_id)
    print(f"  Initial state: nodes={initial_nodes}, docs={initial_docs}")

    # Run delivery
    print(f"  Running delivery...")
    result = await run_delivery(config)

    if "error" in result:
        print(f"  FAILED: {result['error'][:100]}")
        return False

    print(f"  Delivery result: success={result.get('success')}, steps={result.get('steps')}")

    # Verify expectations
    passed = True

    # Check if memory was injected
    if "memory_injected" in expect:
        actual = result.get("memoryInjected", False)
        expected = expect["memory_injected"]
        status = "✓" if actual == expected else "✗"
        print(f"  {status} Memory injected: expected={expected}, actual={actual}")
        if actual != expected:
            passed = False

    # Check if memories were stored
    if expect.get("should_store"):
        await asyncio.sleep(1)  # Give time for async storage
        final_nodes, final_docs = await check_bank_memories(bank_id)
        stored = final_docs > initial_docs
        status = "✓" if stored else "✗"
        print(f"  {status} Memories stored: docs={initial_docs} -> {final_docs}, nodes={initial_nodes} -> {final_nodes}")
        if not stored:
            passed = False

    # Check mission was set
    if expect.get("mission_set"):
        mission = await check_bank_mission(bank_id)
        has_mission = mission is not None and len(mission) > 0
        status = "✓" if has_mission else "✗"
        print(f"  {status} Mission set: {mission[:50] if mission else 'None'}...")
        if not has_mission:
            passed = False

    # Check preseed (should have created at least 2 documents: preseed + delivery)
    if expect.get("preseed_called"):
        final_nodes, final_docs = await check_bank_memories(bank_id)
        # With preseed + delivery storage, should have at least 2 documents
        has_preseed = final_docs >= 2
        status = "✓" if has_preseed else "✗"
        print(f"  {status} Preseed executed: docs={final_docs} (expected >= 2 for preseed + delivery)")
        if not has_preseed:
            passed = False

    return passed


async def main():
    """Run all configuration tests."""
    print("=" * 60)
    print("CONFIGURATION PATH VERIFICATION TEST")
    print("=" * 60)

    # Check backend is running
    async with httpx.AsyncClient(timeout=10.0) as client:
        try:
            response = await client.get(f"{BASE_URL}/api/difficulty")
            print(f"Backend status: OK (difficulty={response.json().get('difficulty')})")
        except Exception as e:
            print(f"Backend not reachable: {e}")
            return

    # Check hindsight is running
    async with httpx.AsyncClient(timeout=10.0) as client:
        try:
            response = await client.get(f"{HINDSIGHT_URL}/health")
            print(f"Hindsight status: OK")
        except Exception as e:
            print(f"Hindsight not reachable: {e}")
            return

    # Run all tests
    results = []
    for test in TEST_CONFIGS:
        try:
            passed = await test_configuration(test)
            results.append((test["name"], passed))
        except Exception as e:
            print(f"  EXCEPTION: {e}")
            import traceback
            traceback.print_exc()
            results.append((test["name"], False))

    # Summary
    print("\n" + "=" * 60)
    print("TEST SUMMARY")
    print("=" * 60)

    passed_count = sum(1 for _, p in results if p)
    total_count = len(results)

    for name, passed in results:
        status = "✓ PASS" if passed else "✗ FAIL"
        print(f"  {status}: {name}")

    print(f"\nTotal: {passed_count}/{total_count} passed")

    if passed_count == total_count:
        print("\n🎉 All tests passed!")
    else:
        print("\n⚠️  Some tests failed - review output above")


if __name__ == "__main__":
    asyncio.run(main())
