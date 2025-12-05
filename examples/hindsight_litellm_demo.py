"""
Hindsight Memory Demo with LiteLLM - Automatic Integration

This example demonstrates how to add persistent memory to any LLM app using
the hindsight-litellm package. Memory storage and injection happen automatically
via LiteLLM callbacks - no manual memory management needed!

Key features demonstrated:
1. configure() + enable() - Set up automatic memory integration
2. Automatic storage - Conversations are stored after each LLM call
3. Automatic injection - Relevant memories are injected into prompts

The hindsight-litellm package hooks into LiteLLM's callback system to:
- Store each conversation after successful LLM responses
- Inject relevant memories into the system prompt before LLM calls

Prerequisites:
- Hindsight server running at http://localhost:8888
- pip install hindsight-litellm litellm requests
- OPENAI_API_KEY environment variable set
"""

import os
import uuid
import time
import logging

# Configure logging:
# - Set hindsight_litellm to INFO to see memory operations
# - Set LiteLLM to WARNING to suppress its verbose INFO logs
logging.basicConfig(level=logging.INFO)
logging.getLogger("LiteLLM").setLevel(logging.WARNING)
logging.getLogger("LiteLLM Router").setLevel(logging.WARNING)
logging.getLogger("LiteLLM Proxy").setLevel(logging.WARNING)

# Import hindsight_litellm - no need to import litellm separately!
import hindsight_litellm


def main():
    if not os.getenv("OPENAI_API_KEY"):
        print("Error: OPENAI_API_KEY not set")
        return

    # Generate a unique bank_id for this demo session
    bank_id = f"demo-{uuid.uuid4().hex[:8]}"

    print(f"Starting Hindsight memory demo with bank_id: {bank_id}\n")

    # =========================================================================
    # STEP 1: Configure and enable automatic memory integration
    # =========================================================================
    # This is all you need! After this, all LiteLLM calls will automatically:
    # - Have relevant memories injected into the prompt
    # - Store conversations to Hindsight after the response
    hindsight_litellm.configure(
        hindsight_api_url="http://localhost:8888",
        bank_id=bank_id,
        store_conversations=True,  # Automatically store conversations
        inject_memories=True,       # Automatically inject relevant memories
        verbose=True,               # Enable logging to debug memory operations
    )
    hindsight_litellm.enable()

    print("Hindsight memory integration enabled!\n")

    # =========================================================================
    # CONVERSATION 1: User introduces themselves
    # =========================================================================
    print("=" * 60)
    print("CONVERSATION 1: User introduces themselves")
    print("=" * 60)

    user_message_1 = "Hi! I'm Alex and I work at Google as a software engineer. I love Python and machine learning."
    print(f"\nUser: {user_message_1}\n")

    # Use hindsight_litellm.completion() directly - no separate litellm import needed!
    response_1 = hindsight_litellm.completion(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": "You are a helpful assistant."},
            {"role": "user", "content": user_message_1}
        ],
    )
    assistant_response_1 = response_1.choices[0].message.content
    print(f"Assistant: {assistant_response_1}\n")

    print("(Conversation automatically stored to Hindsight)")

    # Wait for Hindsight to process and extract facts (10 seconds to ensure processing completes)
    print("(Waiting 10 seconds for memory processing...)\n")
    time.sleep(10)

    # =========================================================================
    # CONVERSATION 2: Ask what the assistant remembers
    # =========================================================================
    print("=" * 60)
    print("CONVERSATION 2: Testing memory-augmented response")
    print("=" * 60)

    user_message_2 = "What do you know about me? What programming language should I use for my next project?"
    print(f"\nUser: {user_message_2}\n")

    # Memories are automatically injected before this call!
    response_2 = hindsight_litellm.completion(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": "You are a helpful assistant."},
            {"role": "user", "content": user_message_2}
        ],
    )

    print(f"Assistant: {response_2.choices[0].message.content}\n")

    # =========================================================================
    # DONE
    # =========================================================================
    print("=" * 60)
    print("Demo complete!")
    print("=" * 60)
    print(f"\nThe assistant should have remembered that Alex:")
    print("  - Works at Google as a software engineer")
    print("  - Loves Python and machine learning")
    print(f"\nMemories stored in bank: {bank_id}")

    # Clean up
    hindsight_litellm.cleanup()


if __name__ == "__main__":
    main()
