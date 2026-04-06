"""Verify the Cursor memory demo by recalling a known preference from Hindsight.

Retries automatically if memories are not yet available (retain may still be
processing after seeding).
"""

import asyncio
import os

from hindsight_client import Hindsight

BANK_ID = os.environ.get("BANK_ID", "cursor")
HINDSIGHT_URL = os.environ.get("HINDSIGHT_URL", "http://localhost:8888")
HINDSIGHT_API_KEY = os.environ.get("HINDSIGHT_API_KEY")

MAX_RETRIES = 5
RETRY_DELAY_SECS = 3


async def main() -> None:
    client_kwargs = {"base_url": HINDSIGHT_URL, "timeout": 30.0}
    if HINDSIGHT_API_KEY:
        client_kwargs["api_key"] = HINDSIGHT_API_KEY

    client = Hindsight(**client_kwargs)
    try:
        items = []
        for attempt in range(1, MAX_RETRIES + 1):
            result = await client.arecall(
                bank_id=BANK_ID,
                query="What testing frameworks and coding preferences does the user have?",
                max_tokens=512,
                budget="mid",
            )
            items = result.results
            if items:
                break
            if attempt < MAX_RETRIES:
                print(f"No memories yet (attempt {attempt}/{MAX_RETRIES}), retrying in {RETRY_DELAY_SECS}s...")
                await asyncio.sleep(RETRY_DELAY_SECS)

        print(f"Recalled {len(items)} memories from '{BANK_ID}'")
        for item in items[:5]:
            text = item.text.strip()
            memory_type = item.type or "unknown"
            print(f"- [{memory_type}] {text}")
    finally:
        await client.aclose()


if __name__ == "__main__":
    asyncio.run(main())
