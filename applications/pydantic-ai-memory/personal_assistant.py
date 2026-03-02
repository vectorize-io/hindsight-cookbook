"""
Personal assistant with persistent memory via Hindsight + Pydantic AI.

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

import asyncio
import sys

from hindsight_client import Hindsight
from hindsight_pydantic_ai import create_hindsight_tools, memory_instructions
from pydantic_ai import Agent

BANK_ID = "personal-assistant"
HINDSIGHT_URL = "http://localhost:8888"
MODEL = "openai:gpt-4o-mini"


def build_agent() -> tuple[Agent, Hindsight]:
    """Build a Pydantic AI agent with Hindsight memory tools."""
    client = Hindsight(base_url=HINDSIGHT_URL, timeout=30.0)

    agent = Agent(
        MODEL,
        system_prompt=(
            "You are a helpful personal assistant with long-term memory. "
            "When the user tells you something about themselves, store it "
            "using hindsight_retain. When they ask you a question, first "
            "check your memory with hindsight_recall or hindsight_reflect. "
            "Always be upfront about what you remember vs what you don't."
        ),
        tools=create_hindsight_tools(client=client, bank_id=BANK_ID),
        instructions=[
            memory_instructions(
                client=client,
                bank_id=BANK_ID,
                query="important context about the user",
                max_results=5,
            ),
        ],
    )

    return agent, client


async def reset_memory() -> None:
    """Delete and recreate the memory bank."""
    client = Hindsight(base_url=HINDSIGHT_URL, timeout=30.0)
    await client.adelete_bank(bank_id=BANK_ID)
    print(f"Memory bank '{BANK_ID}' has been reset.")


async def single_query(query: str) -> None:
    """Run a single query and print the result."""
    agent, _ = build_agent()
    result = await agent.run(query)
    print(result.output)


async def interactive() -> None:
    """Run an interactive chat loop."""
    agent, _ = build_agent()
    message_history = None

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

        result = await agent.run(user_input, message_history=message_history)
        message_history = result.all_messages()

        print(f"Assistant: {result.output}\n")


async def main() -> None:
    args = [arg for arg in sys.argv[1:] if not arg.startswith("--")]

    if "--reset" in sys.argv:
        await reset_memory()
        return

    if args:
        await single_query(" ".join(args))
    else:
        await interactive()


if __name__ == "__main__":
    asyncio.run(main())
