"""Seed sample developer facts into Hindsight for the Cursor memory demo.

Usage:
    python seed_memory.py
    python seed_memory.py --reset
"""

import asyncio
import os
import sys

from hindsight_client import Hindsight

BANK_ID = os.environ.get("BANK_ID", "cursor")
HINDSIGHT_URL = os.environ.get("HINDSIGHT_URL", "http://localhost:8888")
HINDSIGHT_API_KEY = os.environ.get("HINDSIGHT_API_KEY")

SAMPLE_FACTS = [
    "User prefers pytest for Python testing and Vitest for TypeScript projects",
    "Current project stack: FastAPI backend, React frontend, PostgreSQL database",
    "User prefers TypeScript over JavaScript for new frontend work",
    "Team convention: snake_case in the database, camelCase in the API layer",
    "User prefers functional patterns over class-heavy designs when practical",
    "The team uses GitHub Actions for CI and requires tests before merging",
    "Cursor should keep edits minimal and avoid unnecessary file churn",
    "When debugging, the user prefers reproducing the bug first and then adding targeted tests",
]


async def reset_bank(client: Hindsight) -> None:
    try:
        await client.adelete_bank(bank_id=BANK_ID)
        print(f"Cleared memory bank '{BANK_ID}'")
    except Exception:
        pass


async def main() -> None:
    client_kwargs = {"base_url": HINDSIGHT_URL, "timeout": 30.0}
    if HINDSIGHT_API_KEY:
        client_kwargs["api_key"] = HINDSIGHT_API_KEY

    client = Hindsight(**client_kwargs)
    try:
        if "--reset" in sys.argv:
            await reset_bank(client)

        content = "\n".join(f"- {fact}" for fact in SAMPLE_FACTS)
        await client.aretain(
            bank_id=BANK_ID,
            content=content,
            document_id="cursor-seed-demo",
            context="cursor-demo",
        )

        print(f"Seeded {len(SAMPLE_FACTS)} developer facts into bank '{BANK_ID}'")
        print("Next: run `python verify_memory.py` or open Cursor and ask about your preferences.")
    finally:
        await client.aclose()


if __name__ == "__main__":
    asyncio.run(main())
