"""
Personal assistant with persistent memory via Hindsight + Hermes Agent.

Registers Hindsight memory tools into Hermes's tool registry, then
starts an interactive chat. The agent stores what you tell it and
recalls relevant context in future sessions.

Usage:
    # Start interactive chat
    python personal_assistant.py

    # Single query
    python personal_assistant.py "What do you know about me?"

    # Reset memory and start fresh
    python personal_assistant.py --reset

Prerequisites:
    - Hindsight running on localhost:8888 (see README)
    - OpenAI key: export OPENAI_API_KEY=sk-...
    - pip install -r requirements.txt
    - hermes tools disable memory  (disable built-in memory)
"""

import json
import os
import sys

from hindsight_client import Hindsight

BANK_ID = os.environ.get("HINDSIGHT_BANK_ID", "hermes-assistant")
HINDSIGHT_URL = os.environ.get("HINDSIGHT_API_URL", "http://localhost:8888")
HINDSIGHT_API_KEY = os.environ.get("HINDSIGHT_API_KEY")


def get_client() -> Hindsight:
    """Create a Hindsight client."""
    kwargs = {"base_url": HINDSIGHT_URL, "timeout": 30.0}
    if HINDSIGHT_API_KEY:
        kwargs["api_key"] = HINDSIGHT_API_KEY
    return kwargs


def build_client() -> Hindsight:
    """Build and return a configured Hindsight client."""
    kwargs = {"base_url": HINDSIGHT_URL, "timeout": 30.0}
    if HINDSIGHT_API_KEY:
        kwargs["api_key"] = HINDSIGHT_API_KEY
    return Hindsight(**kwargs)


def ensure_bank(client: Hindsight) -> None:
    """Create the memory bank if it doesn't exist."""
    try:
        client.create_bank(
            bank_id=BANK_ID,
            name="Hermes Personal Assistant",
        )
    except Exception:
        pass  # Bank may already exist


def retain(client: Hindsight, content: str) -> str:
    """Store a memory."""
    client.retain(bank_id=BANK_ID, content=content)
    return json.dumps({"result": "Memory stored successfully."})


def recall(client: Hindsight, query: str, budget: str = "mid") -> str:
    """Search memories."""
    response = client.recall(bank_id=BANK_ID, query=query, budget=budget)
    if not response.results:
        return json.dumps({"result": "No relevant memories found."})
    lines = [f"{i}. {r.text}" for i, r in enumerate(response.results, 1)]
    return json.dumps({"result": "\n".join(lines)})


def reflect(client: Hindsight, query: str, budget: str = "mid") -> str:
    """Synthesize an answer from memories."""
    response = client.reflect(bank_id=BANK_ID, query=query, budget=budget)
    return json.dumps({"result": response.text or "No relevant memories found."})


def reset_memory() -> None:
    """Delete and recreate the memory bank."""
    client = build_client()
    try:
        client.delete_bank(bank_id=BANK_ID)
    except Exception:
        pass
    print(f"Memory bank '{BANK_ID}' has been reset.")


def demo_standalone() -> None:
    """Demonstrate memory operations without Hermes (standalone mode).

    This shows the core retain/recall/reflect pattern that the Hermes
    plugin uses under the hood.
    """
    client = build_client()
    ensure_bank(client)

    print(f"Hindsight memory demo (bank: {BANK_ID})")
    print(f"Connected to: {HINDSIGHT_URL}")
    print("=" * 50)

    # Store some memories
    print("\n--- Storing memories ---")
    memories = [
        "User's favourite programming language is Rust.",
        "User prefers dark mode in all editors.",
        "User works on CLI tools and systems programming.",
    ]
    for memory in memories:
        retain(client, memory)
        print(f"  Stored: {memory}")

    # Recall
    print("\n--- Recalling memories ---")
    query = "programming preferences"
    result = json.loads(recall(client, query))
    print(f"  Query: {query}")
    print(f"  Result:\n  {result['result']}")

    # Reflect
    print("\n--- Reflecting on memories ---")
    query = "Based on what you know, suggest a tech stack for a new project"
    result = json.loads(reflect(client, query))
    print(f"  Query: {query}")
    print(f"  Result:\n  {result['result']}")

    print("\n" + "=" * 50)
    print("These are the same operations that hindsight-hermes registers")
    print("as Hermes tools: hindsight_retain, hindsight_recall, hindsight_reflect")


def interactive() -> None:
    """Run an interactive loop using the Hindsight client directly."""
    client = build_client()
    ensure_bank(client)

    print(f"Personal assistant ready (bank: {BANK_ID})")
    print("Commands: /store <text>, /recall <query>, /reflect <query>, /reset, /quit")
    print()

    while True:
        try:
            user_input = input("You: ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nGoodbye!")
            break

        if not user_input:
            continue
        if user_input.lower() in ("quit", "exit", "/quit"):
            print("Goodbye!")
            break

        if user_input.startswith("/store "):
            content = user_input[7:]
            result = json.loads(retain(client, content))
            print(f"Assistant: {result['result']}\n")
        elif user_input.startswith("/recall "):
            query = user_input[8:]
            result = json.loads(recall(client, query))
            print(f"Assistant: {result['result']}\n")
        elif user_input.startswith("/reflect "):
            query = user_input[9:]
            result = json.loads(reflect(client, query))
            print(f"Assistant: {result['result']}\n")
        elif user_input == "/reset":
            reset_memory()
            ensure_bank(client)
            print("Assistant: Memory has been reset.\n")
        else:
            # Default: store as a memory
            result = json.loads(retain(client, user_input))
            print(f"Assistant: Stored to memory. {result['result']}\n")


def main() -> None:
    if "--reset" in sys.argv:
        reset_memory()
        return

    if "--demo" in sys.argv:
        demo_standalone()
        return

    args = [arg for arg in sys.argv[1:] if not arg.startswith("--")]
    if args:
        # Single query mode: recall
        client = build_client()
        ensure_bank(client)
        result = json.loads(recall(client, " ".join(args)))
        print(result["result"])
    else:
        interactive()


if __name__ == "__main__":
    main()
