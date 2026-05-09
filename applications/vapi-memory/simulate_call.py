"""
Simulate Vapi server events for local end-to-end testing.

Without a real Vapi account or phone number, this script POSTs the same
event shapes Vapi sends to your webhook in production:

  - assistant-request: returned with assistantOverrides containing recalled
                       memories (call this on a "new" call to see recall)
  - end-of-call-report: includes a transcript that gets retained to Hindsight
                        (call this to populate memory)

Run webhook_server.py first, then in another shell:

    # Retain a transcript
    python simulate_call.py --caller "+15551234567" end-of-call-report \
        --transcript "User: My name is Alex and I prefer email."

    # Wait a few seconds for fact extraction, then trigger recall
    python simulate_call.py --caller "+15551234567" assistant-request
"""

from __future__ import annotations

import argparse
import json
import os
import uuid

import httpx

WEBHOOK_URL = os.environ.get("WEBHOOK_URL", "http://localhost:8000/webhook")


def assistant_request_event(caller: str) -> dict:
    return {
        "message": {
            "type": "assistant-request",
            "call": {
                "id": f"call-{uuid.uuid4().hex[:8]}",
                "customer": {"number": caller},
            },
        }
    }


def end_of_call_event(caller: str, transcript: str) -> dict:
    return {
        "message": {
            "type": "end-of-call-report",
            "call": {
                "id": f"call-{uuid.uuid4().hex[:8]}",
                "customer": {"number": caller},
            },
            "transcript": transcript,
            "endedReason": "customer-ended-call",
        }
    }


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("event", choices=["assistant-request", "end-of-call-report"])
    p.add_argument("--caller", required=True, help="Caller phone number, e.g. +15551234567")
    p.add_argument(
        "--transcript",
        default="User: Hello. Assistant: Hi, how can I help?",
        help="Transcript text (only used for end-of-call-report)",
    )
    p.add_argument("--url", default=WEBHOOK_URL, help="Webhook URL")
    args = p.parse_args()

    if args.event == "assistant-request":
        payload = assistant_request_event(args.caller)
    else:
        payload = end_of_call_event(args.caller, args.transcript)

    print(f"POST {args.url}")
    print(f"  event: {args.event}  caller: {args.caller}")

    response = httpx.post(args.url, json=payload, timeout=30.0)
    response.raise_for_status()
    body = response.json()

    print(f"\nResponse ({response.status_code}):")
    print(json.dumps(body, indent=2))

    overrides = body.get("assistantOverrides")
    if overrides:
        messages = (overrides.get("model") or {}).get("messages") or []
        if messages:
            print("\n--- Recalled memory injected as system prompt ---")
            print(messages[0].get("content", ""))


if __name__ == "__main__":
    main()
