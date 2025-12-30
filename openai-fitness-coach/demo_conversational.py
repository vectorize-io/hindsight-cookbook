#!/usr/bin/env python3
"""
Conversational Goal Tracking Demo

Demonstrates:
- Natural language workout logging with dates
- Different run types (easy, tempo, intervals, recovery runs)
- Preference learning:
  * User says: "I don't enjoy tempo runs - too monotonous"
  * User says: "I prefer interval workouts - variety keeps me engaged"
  * Coach should: Recommend MORE intervals, AVOID tempo runs
  * This tests if the coach respects preferences when giving advice
- Bidirectional memory storage:
  * User -> Memory: Workouts, preferences, goals stored as world/agent
  * Coach -> Memory: Advice, observations stored as opinion
  * Coach can reference past advice: "Last time I suggested..."
- Goal setting, progress tracking, and achievement recognition
- Temporal memory with specific dates (Feb 5-17, 2025)

Uses a separate demo agent (fitness-coach-demo) to avoid mixing with real data.
"""
import os
import sys
import requests

# Demo-specific memory bank
DEMO_BANK_ID = "fitness-coach-demo"
API_URL = "http://localhost:8888"


def setup_demo_agent():
    """Create demo memory bank."""
    disposition = {
        "skepticism": 3,
        "literalism": 3,
        "empathy": 4
    }

    payload = {
        "name": DEMO_BANK_ID,
        "disposition": disposition,
        "background": "You are an experienced fitness coach specializing in running."
    }

    try:
        requests.put(f"{API_URL}/v1/default/banks/{DEMO_BANK_ID}", json=payload, timeout=30)
        print(f"Demo agent '{DEMO_BANK_ID}' ready")
    except:
        pass


def clear_demo_data():
    """Clear old demo data."""
    try:
        requests.delete(f"{API_URL}/v1/default/banks/{DEMO_BANK_ID}/memories", timeout=30)
        print("Cleared old demo data")
    except:
        pass


def tell_coach(assistant, thread, message, pause=True, stream=False):
    """Tell coach something."""
    from openai_coach import chat

    print(f"\n{'=' * 70}")
    print(f"YOU: {message}")
    print("=" * 70)

    if stream:
        print(f"\nCOACH:")
        print('-' * 70)
        response = chat(assistant, thread.id, message, stream=True)
        print('-' * 70)
    else:
        response = chat(assistant, thread.id, message, stream=False)
        if response:
            print(f"\nCOACH:\n{'-' * 70}\n{response}\n{'-' * 70}")

    if pause:
        input("\nPress Enter to continue...")

    return response


def main():
    if not os.getenv("OPENAI_API_KEY"):
        print("OPENAI_API_KEY not set")
        sys.exit(1)

    # Check if streaming should be enabled (default: True)
    enable_streaming = os.getenv("STREAM_RESPONSES", "true").lower() in ["true", "1", "yes"]

    print("\n" + "=" * 70)
    print("CONVERSATIONAL GOAL TRACKING")
    print("=" * 70)
    input("\nPress Enter to setup...")

    # Setup
    setup_demo_agent()
    clear_demo_data()

    # Override bank ID for demo
    import memory_tools
    original_bank_id = memory_tools.BANK_ID
    memory_tools.BANK_ID = DEMO_BANK_ID

    try:
        from openai_coach import get_or_create_assistant, create_thread

        assistant = get_or_create_assistant()
        thread = create_thread()

        # PHASE 1: Set goal
        print("\n" + "=" * 70)
        print("PHASE 1: Setting Your Goal")
        print("=" * 70)

        tell_coach(assistant, thread,
            "My goal is to run 5K in under 25 minutes by March 1st. Can you help me achieve this?",
            stream=enable_streaming)

        # PHASE 2: Week 1
        print("\n" + "=" * 70)
        print("PHASE 2: Week 1 Training (Feb 5-10)")
        print("=" * 70)

        tell_coach(assistant, thread,
            """I've been training this week. Here are my runs from February 5-10:

Monday Feb 5: 5K easy run in 27:30 - Nice comfortable pace
Tuesday Feb 6: 5K tempo run in 26:45 - I really don't enjoy tempo runs let's avoid them completely.
Thursday Feb 8: Easy recovery run - 5K in 28:00
Saturday Feb 10: 5K interval training in 28:20 - I prefer interval workouts. The variety keeps me engaged.

What do you think of my progress?""",
            stream=enable_streaming)

        # PHASE 3: Advice
        print("\n" + "=" * 70)
        print("PHASE 3: Getting Advice")
        print("=" * 70)

        tell_coach(assistant, thread,
            "I'm getting closer. What should my runs look like this week to break 25 minutes?",
            stream=enable_streaming)

        # PHASE 4: Breakthrough
        print("\n" + "=" * 70)
        print("PHASE 4: Week 2 - Breakthrough! (Feb 12-17)")
        print("=" * 70)

        tell_coach(assistant, thread,
            """I followed your advice! Here are my runs from February 12-17:

Monday Feb 12: 5K with 400m intervals in 27:30 - Feeling fast, great workout!
Wednesday Feb 14: 8K in 41:10 - Longer run to build endurance.
Saturday Feb 17: 5K race pace run in 24:30 - Sub-25 minutes!

Finally broke through 25 minutes!""",
            stream=enable_streaming)

        # PHASE 5: Recognition
        print("\n" + "=" * 70)
        print("PHASE 5: Achievement Recognition")
        print("=" * 70)

        tell_coach(assistant, thread, "Have I achieved my 5K goal?",
            stream=enable_streaming)

        # PHASE 6: New goal
        print("\n" + "=" * 70)
        print("PHASE 6: New Challenge")
        print("=" * 70)

        tell_coach(assistant, thread,
            "New goal: run 5K in under 23 minutes by May 1st. Based on your previous coaching, what should I focus on?",
            stream=enable_streaming)

        # PHASE 7: Memory test
        print("\n" + "=" * 70)
        print("PHASE 7: Memory Test")
        print("=" * 70)

        tell_coach(assistant, thread,
            "What's my current 5K goal and what have I achieved?",
            pause=False, stream=enable_streaming)

        # Summary
        print("\n" + "=" * 70)
        print("DEMO COMPLETE!")

    finally:
        memory_tools.BANK_ID = original_bank_id


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\nConversation ended.")
    except Exception as e:
        print(f"\nError: {e}")
        import traceback
        traceback.print_exc()
