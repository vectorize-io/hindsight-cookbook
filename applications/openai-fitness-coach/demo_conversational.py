#!/usr/bin/env python3
"""
Interactive Fitness Coach Demo

An interactive demo where you can have a free-form conversation with
a fitness coach powered by OpenAI + Hindsight memory.

Features:
- Natural language workout logging
- Goal setting and progress tracking
- Preference learning (the coach remembers what you like/dislike)
- Persistent memory across the conversation

Try things like:
- "My goal is to run 5K in under 25 minutes"
- "I ran 5K today in 27 minutes"
- "I don't like tempo runs, I prefer intervals"
- "What workouts should I do this week?"
- "What do you remember about my training?"

Commands:
- Type 'quit' or 'exit' to end the conversation
- Type 'clear' to clear memory and start fresh
- Type 'scripted' to run the original scripted demo

Uses a separate demo bank (fitness-coach-demo) to avoid mixing with real data.
"""
import os
import sys
import requests

# Demo-specific memory bank
DEMO_BANK_ID = "fitness-coach-demo"
API_URL = "http://localhost:8888"


def setup_demo_bank():
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
        return True
    except Exception as e:
        print(f"Warning: Could not setup demo bank: {e}")
        return False


def clear_demo_data():
    """Clear old demo data."""
    try:
        requests.delete(f"{API_URL}/v1/default/banks/{DEMO_BANK_ID}/memories", timeout=30)
        print("Memory cleared - starting fresh!")
        return True
    except Exception as e:
        print(f"Warning: Could not clear demo data: {e}")
        return False


def check_hindsight():
    """Check if Hindsight API is running."""
    try:
        response = requests.get(f"{API_URL}/health", timeout=5)
        return response.status_code == 200
    except:
        return False


def interactive_chat(assistant, thread, stream=True):
    """Run interactive chat loop."""
    from openai_coach import chat

    print("\n" + "=" * 70)
    print("INTERACTIVE FITNESS COACH")
    print("=" * 70)
    print("\nTalk to your fitness coach! Try:")
    print("  - Setting goals: 'I want to run a 5K in under 25 minutes'")
    print("  - Logging workouts: 'I ran 5K today in 27:30'")
    print("  - Asking for advice: 'What should I focus on this week?'")
    print("  - Testing memory: 'What do you know about my training?'")
    print("\nCommands: 'clear' to reset memory, 'quit' to exit")
    print("=" * 70)

    while True:
        try:
            print()
            user_input = input("You: ").strip()

            if not user_input:
                continue

            # Handle commands
            if user_input.lower() in ['quit', 'exit', 'q']:
                print("\nGoodbye! Keep up the great training!")
                break

            if user_input.lower() == 'clear':
                clear_demo_data()
                continue

            if user_input.lower() == 'scripted':
                run_scripted_demo(assistant, thread, stream)
                continue

            # Chat with coach
            print("\nCoach: ", end="", flush=True)
            if stream:
                response = chat(assistant, thread.id, user_input, stream=True)
            else:
                response = chat(assistant, thread.id, user_input, stream=False)
                if response:
                    print(response)

        except EOFError:
            print("\n\nGoodbye!")
            break


def run_scripted_demo(assistant, thread, stream=True):
    """Run the original scripted demo for showcasing features."""
    from openai_coach import chat

    print("\n" + "=" * 70)
    print("RUNNING SCRIPTED DEMO")
    print("=" * 70)

    scripted_messages = [
        ("Setting Goal",
         "My goal is to run 5K in under 25 minutes by March 1st. Can you help me achieve this?"),

        ("Week 1 Training",
         """I've been training this week. Here are my runs from February 5-10:

Monday Feb 5: 5K easy run in 27:30 - Nice comfortable pace
Tuesday Feb 6: 5K tempo run in 26:45 - I really don't enjoy tempo runs, let's avoid them completely.
Thursday Feb 8: Easy recovery run - 5K in 28:00
Saturday Feb 10: 5K interval training in 28:20 - I prefer interval workouts. The variety keeps me engaged.

What do you think of my progress?"""),

        ("Getting Advice",
         "I'm getting closer. What should my runs look like this week to break 25 minutes?"),

        ("Breakthrough Week",
         """I followed your advice! Here are my runs from February 12-17:

Monday Feb 12: 5K with 400m intervals in 27:30 - Feeling fast, great workout!
Wednesday Feb 14: 8K in 41:10 - Longer run to build endurance.
Saturday Feb 17: 5K race pace run in 24:30 - Sub-25 minutes!

Finally broke through 25 minutes!"""),

        ("Achievement Check",
         "Have I achieved my 5K goal?"),

        ("Memory Test",
         "What's my current 5K goal and what have I achieved?"),
    ]

    for phase_name, message in scripted_messages:
        print(f"\n--- {phase_name} ---")
        print(f"You: {message[:100]}..." if len(message) > 100 else f"You: {message}")
        print("\nCoach: ", end="", flush=True)

        if stream:
            chat(assistant, thread.id, message, stream=True)
        else:
            response = chat(assistant, thread.id, message, stream=False)
            if response:
                print(response)

        print()
        input("Press Enter to continue...")

    print("\n" + "=" * 70)
    print("SCRIPTED DEMO COMPLETE!")
    print("=" * 70)
    print("\nYou can now continue chatting interactively...")


def main():
    if not os.getenv("OPENAI_API_KEY"):
        print("Error: OPENAI_API_KEY not set")
        print("Run: export OPENAI_API_KEY=your_key_here")
        sys.exit(1)

    # Check Hindsight
    if not check_hindsight():
        print("Error: Hindsight API not running at", API_URL)
        print("\nStart it with:")
        print("  docker run --rm -p 8888:8888 -p 9999:9999 \\")
        print("    -e HINDSIGHT_API_LLM_API_KEY=$OPENAI_API_KEY \\")
        print("    -e HINDSIGHT_API_LLM_MODEL=o3-mini \\")
        print("    ghcr.io/vectorize-io/hindsight:latest")
        sys.exit(1)

    # Check if streaming should be enabled (default: True)
    enable_streaming = os.getenv("STREAM_RESPONSES", "true").lower() in ["true", "1", "yes"]

    # Setup
    print("Setting up demo...")
    setup_demo_bank()

    # Override bank ID for demo
    import memory_tools
    original_bank_id = memory_tools.BANK_ID
    memory_tools.BANK_ID = DEMO_BANK_ID

    try:
        from openai_coach import get_or_create_assistant, create_thread

        assistant = get_or_create_assistant()
        thread = create_thread()

        # Run interactive chat
        interactive_chat(assistant, thread, stream=enable_streaming)

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
