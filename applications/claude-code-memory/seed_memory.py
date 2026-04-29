"""Seed sample developer facts into Hindsight for the Claude Code memory demo.

Run this once before starting Claude Code to pre-populate your memory bank.
Then ask Claude Code questions like "what testing framework do I prefer?"
to see Hindsight recall the right context automatically via the
hindsight-memory plugin's UserPromptSubmit hook.

Usage:
    python seed_memory.py           # seed default facts
    python seed_memory.py --reset   # clear the bank first, then seed

Prerequisites:
    - pip install -r requirements.txt
    - Hindsight running locally, or set HINDSIGHT_URL to your cloud endpoint
    - Set HINDSIGHT_API_KEY if using Hindsight Cloud
"""

import asyncio
import os
import sys

from hindsight_client import Hindsight

# Default bank ID matches DEFAULT_BANK_NAME in the Claude Code plugin
# (hindsight-integrations/claude-code/scripts/lib/bank.py).
BANK_ID = os.environ.get("BANK_ID", "claude-code")
HINDSIGHT_URL = os.environ.get("HINDSIGHT_URL", "http://localhost:8888")
HINDSIGHT_API_KEY = os.environ.get("HINDSIGHT_API_KEY")

SAMPLE_FACTS = [
    "User prefers Python for scripting and TypeScript for web applications",
    "User is currently migrating a monolith to microservices using Docker and Kubernetes",
    "User's primary editor is VS Code with Vim keybindings enabled",
    "User always writes tests before submitting PRs (test-driven development)",
    "Preferred testing frameworks: pytest for Python, Jest for TypeScript/JavaScript",
    "User's team uses GitHub Actions for CI/CD pipelines",
    "User prefers functional programming patterns over object-oriented where possible",
    "Current project stack: FastAPI backend, React frontend, PostgreSQL database",
]


async def reset_bank(client: Hindsight) -> None:
    try:
        await client.adelete_bank(bank_id=BANK_ID)
        print(f"Cleared memory bank '{BANK_ID}'")
    except Exception:
        pass  # Bank may not exist yet


async def main() -> None:
    client_kwargs: dict = {"base_url": HINDSIGHT_URL, "timeout": 30.0}
    if HINDSIGHT_API_KEY:
        client_kwargs["api_key"] = HINDSIGHT_API_KEY

    client = Hindsight(**client_kwargs)

    if "--reset" in sys.argv:
        await reset_bank(client)

    content = "\n".join(f"- {fact}" for fact in SAMPLE_FACTS)
    await client.aretain(
        bank_id=BANK_ID,
        content=content,
        document_id="seed-demo",
    )

    print(f"Seeded {len(SAMPLE_FACTS)} developer facts into bank '{BANK_ID}'")
    print()
    print("Now start Claude Code and try asking:")
    print("  - 'what testing framework do I prefer?'")
    print("  - 'what's my current project stack?'")
    print("  - 'how does my team handle CI/CD?'")
    print()
    print("Hindsight will inject the relevant context before each prompt")
    print("via the hindsight-memory plugin's UserPromptSubmit hook.")


if __name__ == "__main__":
    asyncio.run(main())
