"""
Personal assistant with persistent memory via Hindsight + Agno.

A conversational agent that remembers what you tell it across sessions.
Run it multiple times — the agent builds on what it learned before.

Usage:
    # Chat with the assistant (interactive mode)
    python personal_assistant.py

    # Single query
    python personal_assistant.py "What do you know about me?"

    # Reset memory and start fresh
    python personal_assistant.py --reset

Prerequisites:
    - Hindsight running on localhost:8888 (see README)
    - OpenAI key: export OPENAI_API_KEY=sk-...
    - pip install -r requirements.txt
"""

import os
import sys

from agno.agent import Agent
from agno.models.openai import OpenAIChat
from hindsight_agno import HindsightTools, memory_instructions
from hindsight_client import Hindsight

BANK_ID = os.environ.get("BANK_ID", "personal-assistant")
HINDSIGHT_URL = os.environ.get("HINDSIGHT_URL", "http://localhost:8888")
MODEL = os.environ.get("MODEL", "gpt-4o-mini")


def build_agent() -> Agent:
    """Build an Agno agent with Hindsight memory tools."""
    agent = Agent(
        model=OpenAIChat(id=MODEL),
        description=(
            "You are a helpful personal assistant with long-term memory. "
            "When the user tells you something about themselves, store it "
            "using retain_memory. When they ask you a question, first "
            "check your memory with recall_memory or reflect_on_memory. "
            "Always be upfront about what you remember vs what you don't."
        ),
        tools=[
            HindsightTools(
                bank_id=BANK_ID,
                hindsight_api_url=HINDSIGHT_URL,
            ),
        ],
        instructions=[
            memory_instructions(
                bank_id=BANK_ID,
                hindsight_api_url=HINDSIGHT_URL,
                query="important context about the user",
                max_results=5,
            ),
        ],
        markdown=True,
    )

    return agent


def reset_memory() -> None:
    """Delete and recreate the memory bank."""
    client = Hindsight(base_url=HINDSIGHT_URL, timeout=30.0)
    client.delete_bank(bank_id=BANK_ID)
    print(f"Memory bank '{BANK_ID}' has been reset.")


def single_query(query: str) -> None:
    """Run a single query and print the result."""
    agent = build_agent()
    agent.print_response(query)


def interactive() -> None:
    """Run an interactive chat loop."""
    agent = build_agent()

    print(f"Personal assistant ready (bank: {BANK_ID})")
    print("Type 'quit' or 'exit' to stop.\n")

    while True:
        try:
            user_input = input("You: ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nGoodbye!")
            break

        if not user_input:
            continue
        if user_input.lower() in ("quit", "exit"):
            print("Goodbye!")
            break

        agent.print_response(user_input)
        print()


def main() -> None:
    args = [arg for arg in sys.argv[1:] if not arg.startswith("--")]

    if "--reset" in sys.argv:
        reset_memory()
        return

    if args:
        single_query(" ".join(args))
    else:
        interactive()


if __name__ == "__main__":
    main()
