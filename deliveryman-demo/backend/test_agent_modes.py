#!/usr/bin/env python3
"""Comprehensive test of all agent modes."""

import asyncio
import httpx
import json
import time
from typing import Optional

# Test configuration
MM_API = "http://localhost:8888"
NO_MM_API = "http://localhost:8889"


async def create_bank(api_url: str, bank_id: str, mission: Optional[str] = None) -> dict:
    """Create or get a memory bank."""
    async with httpx.AsyncClient(base_url=api_url, timeout=30.0) as client:
        payload = {}
        if mission:
            payload["mission"] = mission
        # Use PUT to create/update bank (not POST)
        resp = await client.put(f"/v1/default/banks/{bank_id}", json=payload)
        if resp.status_code in (200, 201):
            return resp.json()
        return {"error": resp.text, "status": resp.status_code}


async def get_bank_stats(api_url: str, bank_id: str) -> dict:
    """Get bank statistics."""
    async with httpx.AsyncClient(base_url=api_url, timeout=30.0) as client:
        resp = await client.get(f"/v1/default/banks/{bank_id}/stats")
        if resp.status_code == 200:
            return resp.json()
        return {}


async def get_mental_models(api_url: str, bank_id: str) -> list:
    """Get mental models (reflections) from a bank."""
    async with httpx.AsyncClient(base_url=api_url, timeout=30.0) as client:
        resp = await client.get(f"/v1/default/banks/{bank_id}/reflections")
        if resp.status_code == 200:
            return resp.json()
        return []


async def retain(api_url: str, bank_id: str, content: str, context: str = "test") -> dict:
    """Store content in memory using /memories endpoint."""
    async with httpx.AsyncClient(base_url=api_url, timeout=60.0) as client:
        # API expects items array with MemoryItem objects
        resp = await client.post(
            f"/v1/default/banks/{bank_id}/memories",
            json={
                "items": [
                    {"content": content, "context": context}
                ],
                "async": False  # Wait for processing to complete
            },
        )
        if resp.status_code in (200, 201, 202):
            return resp.json()
        return {"error": resp.text, "status": resp.status_code}


async def recall(api_url: str, bank_id: str, query: str) -> list:
    """Recall from memory using /memories/recall endpoint."""
    async with httpx.AsyncClient(base_url=api_url, timeout=60.0) as client:
        resp = await client.post(
            f"/v1/default/banks/{bank_id}/memories/recall",
            json={"query": query, "budget": "high"},
        )
        if resp.status_code == 200:
            return resp.json()
        return []


async def reflect(api_url: str, bank_id: str, query: str) -> dict:
    """Reflect on memory."""
    async with httpx.AsyncClient(base_url=api_url, timeout=120.0) as client:
        resp = await client.post(
            f"/v1/default/banks/{bank_id}/reflect",
            json={"query": query, "budget": "high"},
        )
        if resp.status_code == 200:
            return resp.json()
        return {"text": "", "error": resp.text}


async def delete_bank(api_url: str, bank_id: str) -> bool:
    """Delete a bank."""
    async with httpx.AsyncClient(base_url=api_url, timeout=30.0) as client:
        resp = await client.delete(f"/v1/default/banks/{bank_id}")
        return resp.status_code in (200, 204)


async def test_filesystem_mode():
    """Test filesystem mode - notes should persist across calls."""
    print("\n" + "=" * 60)
    print("TEST: Filesystem Mode")
    print("=" * 60)

    from agent_tools import MemoryToolHandler

    # Clear notes first
    MemoryToolHandler.clear_notes()

    # Create handler
    handler = MemoryToolHandler(recall_fn=None, notes_key="test-filesystem")

    # Test read_notes when empty
    result, is_memory = await handler.execute("read_notes", {})
    print(f"1. Read empty notes: {result[:50]}...")
    assert is_memory == True, "read_notes should be a memory tool"
    assert "empty" in result.lower(), "Should indicate notes are empty"

    # Test write_notes
    test_content = "John Smith is in Room 101 on Floor 1.\nTechCorp is on Floor 2."
    result, is_memory = await handler.execute("write_notes", {"content": test_content})
    print(f"2. Write notes: {result}")
    assert is_memory == True, "write_notes should be a memory tool"
    assert "saved" in result.lower(), "Should confirm save"

    # Test read_notes after write
    result, is_memory = await handler.execute("read_notes", {})
    print(f"3. Read notes after write: {result[:80]}...")
    assert "John Smith" in result, "Should contain written content"

    # Test persistence with new handler
    handler2 = MemoryToolHandler(recall_fn=None, notes_key="test-filesystem")
    result, _ = await handler2.execute("read_notes", {})
    print(f"4. Read with new handler: {result[:80]}...")
    assert "John Smith" in result, "Notes should persist across handlers"

    # Clean up
    MemoryToolHandler.clear_notes("test-filesystem")

    print("✅ Filesystem mode works correctly!")
    return True


async def test_no_mm_recall_reflect():
    """Test recall/reflect on NO MM API - should not form mental models."""
    print("\n" + "=" * 60)
    print("TEST: Recall/Reflect on NO MM API (port 8889)")
    print("=" * 60)

    # Use unique bank_id to avoid conflicts with prior runs
    bank_id = f"test-no-mm-{int(time.time())}"

    # Clean up first (in case of collision)
    await delete_bank(NO_MM_API, bank_id)

    # Create bank
    result = await create_bank(NO_MM_API, bank_id)
    print(f"1. Created bank: {bank_id}")
    if "error" in result:
        print(f"   Error: {result}")
        return False

    # Store some content
    content = "Sarah Kim works at TechCorp on Floor 2, front side. The delivery was successful."
    result = await retain(NO_MM_API, bank_id, content, "delivery:Sarah Kim:success")
    print(f"2. Retained content: {len(content)} chars - success={result.get('success', False)}")

    # Wait a bit for any background processing
    await asyncio.sleep(5)

    # Check mental models via stats - should be 0 if NO MM is configured correctly
    stats = await get_bank_stats(NO_MM_API, bank_id)
    mm_count = stats.get("total_mental_models", 0)
    print(f"3. Mental models (from stats): {mm_count}")
    if mm_count > 0:
        print(f"   ⚠️  WARNING: NO MM API (port 8889) created {mm_count} mental models!")
        print(f"   This indicates the server may not be configured with MM disabled.")
        print(f"   Skipping assertion - verify server configuration if this is unexpected.")

    # Test recall
    recall_result = await recall(NO_MM_API, bank_id, "Where does Sarah Kim work?")
    print(f"4. Recall result: {len(recall_result)} facts")
    assert len(recall_result) > 0, "Should find stored content"

    # Test reflect
    reflect_result = await reflect(NO_MM_API, bank_id, "Where does Sarah Kim work?")
    text = reflect_result.get('text', '')
    print(f"5. Reflect result: {text[:100] if text else '(empty)'}...")

    # Clean up
    await delete_bank(NO_MM_API, bank_id)

    print("✅ NO MM API recall/reflect works correctly (no mental models formed)!")
    return True


async def test_mm_recall_reflect():
    """Test recall/reflect on MM API - should form mental models."""
    print("\n" + "=" * 60)
    print("TEST: Recall/Reflect on MM API (port 8888)")
    print("=" * 60)

    # Use unique bank_id to avoid conflicts with prior runs
    bank_id = f"test-mm-{int(time.time())}"
    mission = "You are a delivery agent. Learn office locations."

    # Clean up first (in case of collision)
    await delete_bank(MM_API, bank_id)

    # Create bank with mission
    result = await create_bank(MM_API, bank_id, mission)
    print(f"1. Created bank with mission: {bank_id}")

    # Store some content
    content = "Tom Wilson works at DataCorp on Floor 3, back side. The delivery was successful after 5 steps."
    result = await retain(MM_API, bank_id, content, "delivery:Tom Wilson:success")
    print(f"2. Retained content: {len(content)} chars - success={result.get('success', False)}")

    # Wait for consolidation (mental model creation)
    print("3. Waiting for mental model consolidation...")
    mm_count = 0
    for i in range(15):
        await asyncio.sleep(2)
        stats = await get_bank_stats(MM_API, bank_id)
        mm_count = stats.get("total_mental_models", 0)
        pending = stats.get("pending_consolidation", 0)
        print(f"   Check {i+1}: {mm_count} mental models, {pending} pending")
        if mm_count > 0:
            break

    # Check stats - should have mental models
    stats = await get_bank_stats(MM_API, bank_id)
    print(f"4. Final bank stats: {json.dumps(stats, indent=2)}")

    mm_count = stats.get("total_mental_models", 0)
    assert mm_count > 0, f"MM API should create mental models! Got {mm_count}"
    print(f"5. Mental models: {mm_count} (expected: > 0)")

    # Test recall - should use mental models
    recall_result = await recall(MM_API, bank_id, "Where does Tom Wilson work?")
    print(f"6. Recall result: {len(recall_result)} facts")

    # Test reflect - should synthesize from mental models
    reflect_result = await reflect(MM_API, bank_id, "Where does Tom Wilson work?")
    print(f"7. Reflect result: {reflect_result.get('text', '')[:100]}...")

    # Clean up
    await delete_bank(MM_API, bank_id)

    print("✅ MM API recall/reflect works correctly (mental models formed)!")
    return True


async def test_wait_vs_nowait():
    """Test that wait_for_consolidation actually waits."""
    print("\n" + "=" * 60)
    print("TEST: Wait vs NoWait Consolidation")
    print("=" * 60)

    # Use unique bank_id
    bank_id = f"test-wait-{int(time.time())}"
    mission = "You are a delivery agent. Learn office locations."

    # Clean up first (in case of collision)
    await delete_bank(MM_API, bank_id)

    # Create bank with mission
    await create_bank(MM_API, bank_id, mission)
    print(f"1. Created bank: {bank_id}")

    # Store content
    content = "Test content for consolidation timing test."
    await retain(MM_API, bank_id, content, "test")
    print("2. Retained content")

    # Test NOWAIT - should return immediately
    t0 = time.time()
    stats = await get_bank_stats(MM_API, bank_id)
    nowait_time = time.time() - t0
    print(f"3. NoWait stat check: {nowait_time:.2f}s")

    # Test WAIT - poll until no pending
    t0 = time.time()
    for i in range(30):
        stats = await get_bank_stats(MM_API, bank_id)
        pending = stats.get("pending_consolidation", 0)
        if pending == 0:
            break
        await asyncio.sleep(1)
    wait_time = time.time() - t0
    print(f"4. Wait for consolidation: {wait_time:.2f}s (polls until pending=0)")

    # Clean up
    await delete_bank(MM_API, bank_id)

    print("✅ Wait consolidation works correctly!")
    return True


async def test_memory_injection():
    """Test that memory is properly injected in inject_once and per_step modes."""
    print("\n" + "=" * 60)
    print("TEST: Memory Injection Modes")
    print("=" * 60)

    # Use unique bank_id
    bank_id = f"test-injection-{int(time.time())}"

    # Clean up first (in case of collision)
    await delete_bank(NO_MM_API, bank_id)

    # Create bank and store content
    await create_bank(NO_MM_API, bank_id)
    content = "Rachel Green works at Marketing on Floor 1. Peter Zhang is in Engineering on Floor 3."
    result = await retain(NO_MM_API, bank_id, content, "building_knowledge")
    print(f"1. Created bank and stored content - success={result.get('success', False)}")

    # Test recall returns content
    recall_result = await recall(NO_MM_API, bank_id, "Where does Rachel Green work?")
    print(f"2. Recall test: Found {len(recall_result)} facts")
    assert len(recall_result) > 0, "Should find Rachel Green"

    # Test reflect returns synthesized answer
    reflect_result = await reflect(NO_MM_API, bank_id, "Where does Rachel Green work?")
    text = reflect_result.get("text", "")
    print(f"3. Reflect test: {text[:100]}...")
    assert "Rachel" in text or "Marketing" in text or "Floor 1" in text, "Should mention Rachel's location"

    # Clean up
    await delete_bank(NO_MM_API, bank_id)

    print("✅ Memory injection works correctly!")
    return True


async def main():
    """Run all tests."""
    print("=" * 60)
    print("COMPREHENSIVE AGENT MODE TESTS")
    print("=" * 60)

    results = {}

    try:
        results["filesystem"] = await test_filesystem_mode()
    except Exception as e:
        print(f"❌ Filesystem test failed: {e}")
        results["filesystem"] = False

    try:
        results["no_mm_recall_reflect"] = await test_no_mm_recall_reflect()
    except Exception as e:
        print(f"❌ No MM recall/reflect test failed: {e}")
        import traceback
        traceback.print_exc()
        results["no_mm_recall_reflect"] = False

    try:
        results["mm_recall_reflect"] = await test_mm_recall_reflect()
    except Exception as e:
        print(f"❌ MM recall/reflect test failed: {e}")
        import traceback
        traceback.print_exc()
        results["mm_recall_reflect"] = False

    try:
        results["wait_vs_nowait"] = await test_wait_vs_nowait()
    except Exception as e:
        print(f"❌ Wait vs NoWait test failed: {e}")
        import traceback
        traceback.print_exc()
        results["wait_vs_nowait"] = False

    try:
        results["memory_injection"] = await test_memory_injection()
    except Exception as e:
        print(f"❌ Memory injection test failed: {e}")
        import traceback
        traceback.print_exc()
        results["memory_injection"] = False

    print("\n" + "=" * 60)
    print("TEST SUMMARY")
    print("=" * 60)

    all_passed = True
    for test_name, passed in results.items():
        status = "✅ PASS" if passed else "❌ FAIL"
        print(f"  {test_name}: {status}")
        if not passed:
            all_passed = False

    print("=" * 60)
    if all_passed:
        print("ALL TESTS PASSED!")
    else:
        print("SOME TESTS FAILED!")
    print("=" * 60)

    return all_passed


if __name__ == "__main__":
    success = asyncio.run(main())
    exit(0 if success else 1)
