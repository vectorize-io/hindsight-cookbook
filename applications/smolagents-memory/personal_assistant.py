"""
Personal assistant with persistent memory via Hindsight + SmolAgents.

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

from hindsight_client import Hindsight
from hindsight_smolagents import create_hindsight_tools, memory_instructions
from smolagents import LiteLLMModel, ToolCallingAgent

BANK_ID = os.environ.get("BANK_ID", "personal-assistant")
HINDSIGHT_URL = os.environ.get("HINDSIGHT_URL", "http://localhost:8888")
HINDSIGHT_API_KEY = os.environ.get("HINDSIGHT_API_KEY")
MODEL = os.environ.get("MODEL", "gpt-4o-mini")


PERSONA = (
    "You are a helpful personal assistant with long-term memory. "
    "When the user tells you something about themselves, store it "
    "using hindsight_retain. When they ask a question, first check "
    "your memory with hindsight_recall or hindsight_reflect. Always "
    "be upfront about what you remember vs what you don't."
)


def build_agent() -> ToolCallingAgent:
    """Build a SmolAgents agent with Hindsight memory tools."""
    tools = create_hindsight_tools(
        bank_id=BANK_ID,
        hindsight_api_url=HINDSIGHT_URL,
        api_key=HINDSIGHT_API_KEY,
    )

    model = LiteLLMModel(model_id=MODEL)

    return ToolCallingAgent(tools=tools, model=model)


def make_task(user_query: str) -> str:
    """Inject persona + recalled memories into the task sent to the agent."""
    prior_memories = memory_instructions(
        bank_id=BANK_ID,
        hindsight_api_url=HINDSIGHT_URL,
        api_key=HINDSIGHT_API_KEY,
        query=user_query,
        max_results=5,
    )

    parts = [PERSONA]
    if prior_memories:
        parts.append(prior_memories)
    parts.append(f"User: {user_query}")
    return "\n\n".join(parts)


def reset_memory() -> None:
    """Delete the memory bank."""
    kwargs: dict = {"base_url": HINDSIGHT_URL, "timeout": 30.0}
    if HINDSIGHT_API_KEY:
        kwargs["api_key"] = HINDSIGHT_API_KEY
    client = Hindsight(**kwargs)
    client.delete_bank(bank_id=BANK_ID)
    print(f"Memory bank '{BANK_ID}' has been reset.")


def single_query(query: str) -> None:
    """Run a single query and print the result."""
    agent = build_agent()
    print(str(agent.run(make_task(query))))


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

        response = agent.run(make_task(user_input), reset=False)
        print(f"Assistant: {response}\n")


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
