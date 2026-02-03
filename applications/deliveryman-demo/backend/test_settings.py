#!/usr/bin/env python3
"""Unit tests for benchmark settings - no external services required."""

import sys
sys.path.insert(0, str(__file__).rsplit("/", 1)[0])

from building import get_building, set_difficulty, compute_optimal_steps
from app.services.benchmark_types import generate_delivery_queue, DeliveryQueue
from app.services.agent_service import generate_preseed_facts


def test_repeat_ratio_distribution():
    """Test that repeat ratio produces correct distribution of repeats."""
    print("\n" + "=" * 60)
    print("TEST: Repeat Ratio Distribution")
    print("=" * 60)

    set_difficulty("easy")
    building = get_building()

    # Test with 40% repeat ratio
    queue = generate_delivery_queue(
        building=building,
        num_deliveries=20,
        repeat_ratio=0.4,
        paired_mode=False,
        include_business="random",
        seed=42,  # For reproducibility
    )

    print(f"  Generated {len(queue)} deliveries")

    # Count repeats
    seen = set()
    first_visit_count = 0
    repeat_count = 0

    for i, (recipient, business, is_repeat) in enumerate(queue):
        was_visited = recipient in seen
        seen.add(recipient)
        if is_repeat:
            repeat_count += 1
        else:
            first_visit_count += 1
        print(f"    {i+1}. {recipient[:20]:20} business={str(business)[:15]:15} is_repeat={is_repeat} was_visited={was_visited}")

    actual_repeat_ratio = repeat_count / len(queue)
    print(f"\n  First visits: {first_visit_count}")
    print(f"  Repeats: {repeat_count}")
    print(f"  Actual repeat ratio: {actual_repeat_ratio:.2f}")

    # Check that repeat ratio is roughly correct (allow some variance due to randomness)
    expected_ratio = 0.4
    tolerance = 0.2  # Allow 20% tolerance
    passed = abs(actual_repeat_ratio - expected_ratio) <= tolerance
    status = "✓ PASS" if passed else "✗ FAIL"
    print(f"\n  {status}: Repeat ratio {actual_repeat_ratio:.2f} vs expected {expected_ratio} (tolerance {tolerance})")

    return passed


def test_repeat_ratio_interleaving():
    """Test that repeats are properly interleaved (more repeats in second half)."""
    print("\n" + "=" * 60)
    print("TEST: Repeat Ratio Interleaving")
    print("=" * 60)

    set_difficulty("easy")
    building = get_building()

    queue = generate_delivery_queue(
        building=building,
        num_deliveries=20,
        repeat_ratio=0.4,
        paired_mode=False,
        include_business="random",
        seed=42,
    )

    # Split into first and second half
    first_half = list(queue)[:10]
    second_half = list(queue)[10:]

    first_half_repeats = sum(1 for _, _, is_repeat in first_half if is_repeat)
    second_half_repeats = sum(1 for _, _, is_repeat in second_half if is_repeat)

    print(f"  First half repeats: {first_half_repeats}/10")
    print(f"  Second half repeats: {second_half_repeats}/10")

    # Second half should have more or equal repeats (due to interleaving strategy)
    passed = second_half_repeats >= first_half_repeats
    status = "✓ PASS" if passed else "✗ FAIL"
    print(f"\n  {status}: Second half has {'more/equal' if passed else 'fewer'} repeats than first half")

    return passed


def test_paired_mode():
    """Test that paired mode visits each employee exactly twice."""
    print("\n" + "=" * 60)
    print("TEST: Paired Mode")
    print("=" * 60)

    set_difficulty("easy")
    building = get_building()

    queue = generate_delivery_queue(
        building=building,
        num_deliveries=10,
        repeat_ratio=0.4,  # Ignored in paired mode
        paired_mode=True,
        include_business="random",
        seed=42,
    )

    # Count visits per employee
    visit_counts = {}
    for recipient, business, is_repeat in queue:
        visit_counts[recipient] = visit_counts.get(recipient, 0) + 1

    print(f"  Generated {len(queue)} deliveries for paired mode")
    print(f"  Unique employees: {len(visit_counts)}")

    all_two_visits = all(count == 2 for count in visit_counts.values())

    for emp, count in visit_counts.items():
        status = "✓" if count == 2 else "✗"
        print(f"    {status} {emp[:30]:30} visited {count} times")

    passed = all_two_visits and len(queue) > 0
    status = "✓ PASS" if passed else "✗ FAIL"
    print(f"\n  {status}: All employees visited exactly twice")

    return passed


def test_step_limits():
    """Test step limit calculation."""
    print("\n" + "=" * 60)
    print("TEST: Step Limit Calculation")
    print("=" * 60)

    set_difficulty("easy")
    building = get_building()

    # Get an employee
    employees = list(building.all_employees.keys())
    if not employees:
        print("  No employees found!")
        return False

    test_employee = employees[0]
    optimal = compute_optimal_steps(building, test_employee)

    print(f"  Test employee: {test_employee}")
    print(f"  Optimal steps: {optimal}")

    test_cases = [
        # (step_mult, min_steps, max_steps_cap, expected_formula)
        (5.0, 15, None, lambda opt: max(15, int(opt * 5.0))),
        (3.0, 10, None, lambda opt: max(10, int(opt * 3.0))),
        (5.0, 15, 10, lambda opt: min(10, max(15, int(opt * 5.0)))),  # Hard cap
        (2.0, 5, 8, lambda opt: min(8, max(5, int(opt * 2.0)))),
    ]

    all_passed = True
    for step_mult, min_steps, max_cap, expected_fn in test_cases:
        expected = expected_fn(optimal)

        # Replicate the calculation from main.py
        calculated_max = max(min_steps, int(optimal * step_mult))
        if max_cap is not None:
            actual = min(calculated_max, max_cap)
        else:
            actual = calculated_max

        passed = actual == expected
        status = "✓" if passed else "✗"
        print(f"  {status} mult={step_mult}, min={min_steps}, cap={max_cap}: expected={expected}, actual={actual}")
        if not passed:
            all_passed = False

    status = "✓ PASS" if all_passed else "✗ FAIL"
    print(f"\n  {status}: Step limit calculation")

    return all_passed


def test_business_mode():
    """Test business name inclusion modes."""
    print("\n" + "=" * 60)
    print("TEST: Business Mode")
    print("=" * 60)

    set_difficulty("easy")
    building = get_building()

    # Test "always" mode
    queue_always = generate_delivery_queue(
        building=building,
        num_deliveries=10,
        repeat_ratio=0.0,
        paired_mode=False,
        include_business="always",
        seed=42,
    )
    always_has_business = [b is not None for _, b, _ in queue_always]
    always_passed = all(always_has_business)
    status = "✓" if always_passed else "✗"
    print(f"  {status} 'always' mode: {sum(always_has_business)}/10 have business name")

    # Test "never" mode
    queue_never = generate_delivery_queue(
        building=building,
        num_deliveries=10,
        repeat_ratio=0.0,
        paired_mode=False,
        include_business="never",
        seed=42,
    )
    never_has_business = [b is None for _, b, _ in queue_never]
    never_passed = all(never_has_business)
    status = "✓" if never_passed else "✗"
    print(f"  {status} 'never' mode: {sum(never_has_business)}/10 have no business name")

    # Test "random" mode - should have some with and some without
    queue_random = generate_delivery_queue(
        building=building,
        num_deliveries=20,
        repeat_ratio=0.0,
        paired_mode=False,
        include_business="random",
        seed=42,
    )
    random_has_business = sum(1 for _, b, _ in queue_random if b is not None)
    random_no_business = sum(1 for _, b, _ in queue_random if b is None)
    random_passed = random_has_business > 0 and random_no_business > 0
    status = "✓" if random_passed else "✗"
    print(f"  {status} 'random' mode: {random_has_business} with, {random_no_business} without business name")

    all_passed = always_passed and never_passed and random_passed
    status = "✓ PASS" if all_passed else "✗ FAIL"
    print(f"\n  {status}: Business mode")

    return all_passed


def test_preseed_coverage():
    """Test preseed fact generation with different coverage levels."""
    print("\n" + "=" * 60)
    print("TEST: Preseed Coverage")
    print("=" * 60)

    set_difficulty("easy")
    building = get_building()

    num_employees = len(building.all_employees)
    print(f"  Building has {num_employees} employees")

    # Test 100% coverage
    facts_100 = generate_preseed_facts(building, coverage=1.0)
    print(f"  100% coverage: {len(facts_100)} facts generated")

    # Test 50% coverage
    facts_50 = generate_preseed_facts(building, coverage=0.5)
    print(f"  50% coverage: {len(facts_50)} facts generated")

    # Test 0% coverage
    facts_0 = generate_preseed_facts(building, coverage=0.0)
    print(f"  0% coverage: {len(facts_0)} facts generated")

    # 100% should have most facts
    # 50% should have fewer employee facts but still have building facts
    # 0% should only have building structure facts (no employee facts)

    # Check that facts contain expected content
    has_employee_facts_100 = any("works at" in f for f in facts_100)
    has_building_facts_100 = any("floor" in f.lower() for f in facts_100)

    passed_100 = has_employee_facts_100 and has_building_facts_100
    status = "✓" if passed_100 else "✗"
    print(f"  {status} 100% has employee facts: {has_employee_facts_100}, building facts: {has_building_facts_100}")

    # 50% should have fewer but still some
    passed_50 = len(facts_50) < len(facts_100) and len(facts_50) > len(facts_0)
    status = "✓" if passed_50 else "✗"
    print(f"  {status} 50% has intermediate facts: {len(facts_50)} (between {len(facts_0)} and {len(facts_100)})")

    all_passed = passed_100 and passed_50
    status = "✓ PASS" if all_passed else "✗ FAIL"
    print(f"\n  {status}: Preseed coverage")

    return all_passed


def test_queue_generation_endpoint():
    """Test the generate_delivery_queue function with multiple configs."""
    print("\n" + "=" * 60)
    print("TEST: Queue Generation (Multiple Configs)")
    print("=" * 60)

    set_difficulty("easy")
    building = get_building()

    # Simulate what the endpoint does
    configs = [
        {"configId": "config-1", "numDeliveries": 5, "repeatRatio": 0.4, "pairedMode": False, "includeBusiness": "always"},
        {"configId": "config-2", "numDeliveries": 5, "repeatRatio": 0.0, "pairedMode": False, "includeBusiness": "never"},
        {"configId": "config-3", "numDeliveries": 6, "repeatRatio": 0.4, "pairedMode": True, "includeBusiness": "random"},
    ]

    queues = {}
    for config in configs:
        queue = generate_delivery_queue(
            building=building,
            num_deliveries=config["numDeliveries"],
            repeat_ratio=config["repeatRatio"],
            paired_mode=config["pairedMode"],
            include_business=config["includeBusiness"],
            seed=None,
        )
        queues[config["configId"]] = {
            "recipients": queue.recipients,
            "businesses": queue.businesses,
            "isRepeat": queue.is_repeat,
            "totalDeliveries": len(queue),
        }

    all_passed = True
    for config_id, queue_data in queues.items():
        config = next(c for c in configs if c["configId"] == config_id)

        # Verify length
        expected_len = config["numDeliveries"]
        actual_len = queue_data["totalDeliveries"]
        len_ok = actual_len == expected_len or (config["pairedMode"] and actual_len <= expected_len)

        # Verify business mode
        if config["includeBusiness"] == "always":
            biz_ok = all(b is not None for b in queue_data["businesses"])
        elif config["includeBusiness"] == "never":
            biz_ok = all(b is None for b in queue_data["businesses"])
        else:
            biz_ok = True  # Random is always ok

        passed = len_ok and biz_ok
        status = "✓" if passed else "✗"
        print(f"  {status} {config_id}: len={actual_len}, businesses={'ok' if biz_ok else 'fail'}")

        if not passed:
            all_passed = False

    status = "✓ PASS" if all_passed else "✗ FAIL"
    print(f"\n  {status}: Queue generation for multiple configs")

    return all_passed


def main():
    """Run all unit tests."""
    print("=" * 60)
    print("BENCHMARK SETTINGS UNIT TESTS")
    print("=" * 60)
    print("These tests verify settings logic without external services")

    results = []

    tests = [
        ("Repeat Ratio Distribution", test_repeat_ratio_distribution),
        ("Repeat Ratio Interleaving", test_repeat_ratio_interleaving),
        ("Paired Mode", test_paired_mode),
        ("Step Limits", test_step_limits),
        ("Business Mode", test_business_mode),
        ("Preseed Coverage", test_preseed_coverage),
        ("Queue Generation (Multiple)", test_queue_generation_endpoint),
    ]

    for name, test_fn in tests:
        try:
            passed = test_fn()
            results.append((name, passed))
        except Exception as e:
            print(f"\n  EXCEPTION: {e}")
            import traceback
            traceback.print_exc()
            results.append((name, False))

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
        return 0
    else:
        print("\n⚠️  Some tests failed - review output above")
        return 1


if __name__ == "__main__":
    exit(main())
