"""
AgentCore Runtime support agent with persistent memory via Hindsight.

Simulates an Amazon Bedrock AgentCore Runtime handler. Each call to
handler() represents one Runtime invocation — the agent starts cold,
but memory persists across calls via Hindsight.

Usage:
    # Run a multi-turn conversation (simulates multiple Runtime invocations)
    python support_agent.py

    # Single query
    python support_agent.py "What are my open tickets?"

    # Reset memory and start fresh
    python support_agent.py --reset

Prerequisites:
    - Hindsight running on localhost:8888 (see README)
    - OpenAI key: export OPENAI_API_KEY=sk-...
    - pip install -r requirements.txt
"""

import asyncio
import os
import sys

from hindsight_agentcore import HindsightRuntimeAdapter, TurnContext, configure
from openai import AsyncOpenAI

# --- Configuration ---------------------------------------------------------

HINDSIGHT_URL = os.environ.get("HINDSIGHT_URL", "http://localhost:8888")
HINDSIGHT_API_KEY = os.environ.get("HINDSIGHT_API_KEY")
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY")
MODEL = os.environ.get("MODEL", "gpt-4o-mini")

# Stable identity — in production these come from validated JWT/OAuth context.
# Never use the runtimeSessionId as the user_id; sessions are ephemeral.
USER_ID = os.environ.get("USER_ID", "demo-user")
TENANT_ID = os.environ.get("TENANT_ID", "demo-tenant")
AGENT_NAME = "support-agent"

# ---------------------------------------------------------------------------

configure(
    hindsight_api_url=HINDSIGHT_URL,
    api_key=HINDSIGHT_API_KEY,
    verbose=True,
)

adapter = HindsightRuntimeAdapter(agent_name=AGENT_NAME)
openai_client = AsyncOpenAI(api_key=OPENAI_API_KEY)

# Simulate a monotonically increasing session counter (in production each
# Runtime invocation gets a fresh runtimeSessionId from AWS).
_session_counter = 0


def _new_session_id() -> str:
    global _session_counter
    _session_counter += 1
    return f"runtime-session-{_session_counter:04d}"


async def call_llm(prompt: str, memory_context: str) -> str:
    """Call the LLM with memory context injected into the system prompt."""
    system = (
        "You are a helpful customer support agent. "
        "Answer questions accurately and concisely. "
        "When the user shares information, remember it will be stored for future sessions."
    )
    if memory_context:
        system += f"\n\n## Relevant memory from past sessions\n{memory_context}"

    response = await openai_client.chat.completions.create(
        model=MODEL,
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": prompt},
        ],
    )
    return response.choices[0].message.content or ""


async def run_my_agent(payload: dict, memory_context: str) -> dict:
    """Async agent callable: receives payload + recalled memories, returns output dict."""
    prompt = payload.get("prompt", "")
    output = await call_llm(prompt, memory_context)
    return {"output": output}


async def handler(user_prompt: str, user_id: str = USER_ID) -> str:
    """
    Simulated AgentCore Runtime handler.

    In production, event fields (sessionId, userId, tenantId) come from
    the Runtime invocation context — not from the client.
    """
    context = TurnContext(
        runtime_session_id=_new_session_id(),   # fresh each invocation
        user_id=user_id,                         # stable across invocations
        agent_name=AGENT_NAME,
        tenant_id=TENANT_ID,
        request_id=f"req-{_session_counter:04d}",
    )

    result = await adapter.run_turn(
        context=context,
        payload={"prompt": user_prompt},
        agent_callable=run_my_agent,
    )
    return result.get("output", "")


async def reset_memory() -> None:
    """Delete the memory bank for this user."""
    from hindsight_client import Hindsight  # type: ignore[import]

    kwargs: dict = {"base_url": HINDSIGHT_URL, "timeout": 30.0}
    if HINDSIGHT_API_KEY:
        kwargs["api_key"] = HINDSIGHT_API_KEY
    client = Hindsight(**kwargs)

    bank_id = f"tenant:{TENANT_ID}:user:{USER_ID}:agent:{AGENT_NAME}"
    client.delete_bank(bank_id=bank_id)
    print(f"Memory bank '{bank_id}' has been reset.")


async def single_query(query: str) -> None:
    output = await handler(query)
    print(output)


async def interactive() -> None:
    """
    Simulate multiple Runtime invocations by running the handler in a loop.

    Each iteration represents a fresh AgentCore Runtime session (new
    runtimeSessionId). Memory persists because Hindsight is keyed to the
    stable user_id, not the session ID.
    """
    print(f"Support agent ready (user: {USER_ID}, agent: {AGENT_NAME})")
    print("Each message = one Runtime invocation (new session ID, same memory).")
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

        response = await handler(user_input)
        print(f"Agent: {response}\n")


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
