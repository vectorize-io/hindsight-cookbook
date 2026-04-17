"""Seed sample user facts into Hindsight for the Pipecat memory demo.

Run this once before starting your Pipecat pipeline to pre-populate your
memory bank. Then start a conversation and ask something like "what's my
preferred response style?" to see Hindsight recall the right context.

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

BANK_ID = os.environ.get("BANK_ID", "pipecat")
HINDSIGHT_URL = os.environ.get("HINDSIGHT_URL", "http://localhost:8888")
HINDSIGHT_API_KEY = os.environ.get("HINDSIGHT_API_KEY")

SAMPLE_FACTS = [
    "User's name is Alex and they prefer concise responses",
    "User is a software engineer working on a home automation system",
    "User prefers metric units (Celsius, kilometers) over imperial",
    "User's home assistant should address them by first name",
    "User has a morning routine starting at 7am with news briefing",
    "User's preferred wake-up alarm style is gradual, not abrupt",
    "User has asked the assistant to remember grocery items when mentioned",
    "User prefers voice responses to be under 30 seconds when possible",
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

    print(f"Seeded {len(SAMPLE_FACTS)} user facts into bank '{BANK_ID}'")
    print()
    print("Now start your Pipecat pipeline and try asking:")
    print("  - 'what's my name?'")
    print("  - 'what time do I wake up?'")
    print("  - 'what units do I prefer?'")
    print()
    print("HindsightMemoryService will recall the relevant context before each LLM call.")


if __name__ == "__main__":
    asyncio.run(main())
