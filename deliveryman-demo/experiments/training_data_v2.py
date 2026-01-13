"""Generate training delivery histories for Hindsight experiments - V2.

Uses the actual demo format:
- ASSISTANT_TOOL_CALLS: tool_name({args})
- TOOL_RESULT: result text

All deliveries start from Floor 1 MIDDLE (elevator lobby) for consistency.
Includes realistic exploration patterns, not just optimal paths.
"""

import os
import httpx
from typing import Optional

# Tools available to the delivery agent
AVAILABLE_TOOLS = [
    "check_current_location()",
    "go_up()",
    "go_down()",
    "go_to_front()",
    "go_to_back()",
    "get_employee_list()",
    "deliver_package(recipient_name)",
    "use_fire_escape()",
]

TOOLS_DESCRIPTION = "\n".join(f"- {tool}" for tool in AVAILABLE_TOOLS)

# Summarization prompts - from minimal to detailed
SUMMARIZATION_PROMPTS = {
    # Minimal - just summarize to help with deliveries
    "S1_minimal": f"""Summarize this delivery data to help a delivery agent make optimal deliveries in the future.

Available tools:
{TOOLS_DESCRIPTION}""",

    # Short - bit more guidance
    "S2_short": f"""Summarize this delivery data to help a delivery agent with these tools make optimal deliveries:

{TOOLS_DESCRIPTION}

Focus on what would help the agent deliver faster next time.""",

    # Detailed - specific instructions about locations and paths
    "S3_detailed": f"""Summarize this delivery data to help a delivery agent make optimal deliveries.

Available tools:
{TOOLS_DESCRIPTION}

Include:
- Where people work (locations discovered)
- Optimal paths to reach different areas
- Any shortcuts or limitations discovered""",

    # Most detailed - explicit about learning
    "S4_comprehensive": f"""Summarize this delivery data for a delivery agent to learn from.

Available tools:
{TOOLS_DESCRIPTION}

Extract:
- Employee locations: who works where
- Navigation paths: how to get to different areas from the starting point
- Shortcuts: any faster routes discovered
- Limitations: any tool restrictions or failed attempts that reveal rules"""
}


def generate_delivery_1_rachel_green() -> str:
    """Delivery to Rachel Green - discovers fire escape, explores, finds her at Tech Lab.

    Shows: fire escape discovery, employee list checks, successful delivery.
    """
    return """USER: Please deliver this package: Package #1001: To Rachel Green

ASSISTANT_TOOL_CALLS: check_current_location({})

TOOL_RESULT: Current location: Floor 1 in the middle hallway (elevator lobby).

ASSISTANT_TOOL_CALLS: go_to_front({})

TOOL_RESULT: Walked to the front side of Floor 1. Now at Lobby & Reception. You notice a fire escape here that connects to Floor 3 front side.

ASSISTANT_TOOL_CALLS: get_employee_list({})

TOOL_RESULT: Employees at Lobby & Reception:
  - Maria Santos (Receptionist)
  - Tom Wilson (Security Guard)

ASSISTANT_TOOL_CALLS: deliver_package({"recipient_name": "Rachel Green"})

TOOL_RESULT: FAILED: Rachel Green does not work at Lobby & Reception. Try another location.

ASSISTANT_TOOL_CALLS: use_fire_escape({})

TOOL_RESULT: Took the fire escape! Now at Floor 3 front side at Tech Lab.

ASSISTANT_TOOL_CALLS: get_employee_list({})

TOOL_RESULT: Employees at Tech Lab:
  - John Smith (CTO)
  - Rachel Green (Software Engineer)

ASSISTANT_TOOL_CALLS: deliver_package({"recipient_name": "Rachel Green"})

TOOL_RESULT: SUCCESS! Package #1001 delivered to Rachel Green at Tech Lab!"""


def generate_delivery_2_jake_morrison() -> str:
    """Delivery to Jake Morrison - learns fire escape limitations, explores building.

    Shows: fire escape only works from specific locations, exploration pattern,
    discovers employees at multiple locations including Sarah Kim at Byte Size Games.
    """
    return """USER: Please deliver this package: Package #1002: To Jake Morrison

ASSISTANT_TOOL_CALLS: check_current_location({})

TOOL_RESULT: Current location: Floor 1 in the middle hallway (elevator lobby).

ASSISTANT_TOOL_CALLS: use_fire_escape({})

TOOL_RESULT: FAILED: Fire escape is only accessible from Floor 1 front side or Floor 3 front side. You are currently in the middle hallway.

ASSISTANT_TOOL_CALLS: go_to_front({})

TOOL_RESULT: Walked to the front side of Floor 1. Now at Lobby & Reception. You notice a fire escape here that connects to Floor 3 front side.

ASSISTANT_TOOL_CALLS: use_fire_escape({})

TOOL_RESULT: Took the fire escape! Now at Floor 3 front side at Tech Lab.

ASSISTANT_TOOL_CALLS: go_to_back({})

TOOL_RESULT: Walked to the back side of Floor 3. Now at Rooftop Cafe.

ASSISTANT_TOOL_CALLS: get_employee_list({})

TOOL_RESULT: Employees at Rooftop Cafe:
  - Peter Zhang (Barista)
  - Laura Martinez (Pastry Chef)

ASSISTANT_TOOL_CALLS: deliver_package({"recipient_name": "Jake Morrison"})

TOOL_RESULT: FAILED: Jake Morrison does not work at Rooftop Cafe. Try another location.

ASSISTANT_TOOL_CALLS: go_down({})

TOOL_RESULT: Took elevator down to Floor 2. Now in the middle hallway.

ASSISTANT_TOOL_CALLS: go_to_back({})

TOOL_RESULT: Walked to the back side of Floor 2. Now at Byte Size Games.

ASSISTANT_TOOL_CALLS: get_employee_list({})

TOOL_RESULT: Employees at Byte Size Games:
  - Alex Chen (Game Developer)
  - Sarah Kim (Level Designer)

ASSISTANT_TOOL_CALLS: deliver_package({"recipient_name": "Jake Morrison"})

TOOL_RESULT: FAILED: Jake Morrison does not work at Byte Size Games. Try another location.

ASSISTANT_TOOL_CALLS: go_down({})

TOOL_RESULT: Took elevator down to Floor 1. Now in the middle hallway.

ASSISTANT_TOOL_CALLS: go_to_back({})

TOOL_RESULT: Walked to the back side of Floor 1. Now at Mail Room.

ASSISTANT_TOOL_CALLS: get_employee_list({})

TOOL_RESULT: Employees at Mail Room:
  - Jake Morrison (Mail Clerk)
  - Lisa Park (Package Handler)

ASSISTANT_TOOL_CALLS: deliver_package({"recipient_name": "Jake Morrison"})

TOOL_RESULT: SUCCESS! Package #1002 delivered to Jake Morrison at Mail Room!"""


def generate_delivery_3_sarah_kim() -> str:
    """Delivery to Sarah Kim - uses knowledge from previous delivery.

    Shows: agent already knows Sarah is at Byte Size Games from delivery #2,
    takes direct path without exploration.
    """
    return """USER: Please deliver this package: Package #1003: To Sarah Kim

ASSISTANT_TOOL_CALLS: check_current_location({})

TOOL_RESULT: Current location: Floor 1 in the middle hallway (elevator lobby).

ASSISTANT_TOOL_CALLS: go_up({})

TOOL_RESULT: Took elevator up to Floor 2. Now in the middle hallway.

ASSISTANT_TOOL_CALLS: go_to_back({})

TOOL_RESULT: Walked to the back side of Floor 2. Now at Byte Size Games.

ASSISTANT_TOOL_CALLS: deliver_package({"recipient_name": "Sarah Kim"})

TOOL_RESULT: SUCCESS! Package #1003 delivered to Sarah Kim at Byte Size Games!"""


def get_all_training_deliveries() -> list[str]:
    """Get all 3 training delivery histories in demo format."""
    return [
        generate_delivery_1_rachel_green(),
        generate_delivery_2_jake_morrison(),
        generate_delivery_3_sarah_kim(),
    ]


def summarize_with_llm(
    delivery_history: str,
    prompt_style: str,
    model: str = "gpt-4o-mini",
    api_key: Optional[str] = None
) -> str:
    """Actually run the delivery history through an LLM to generate summary.

    Args:
        delivery_history: The full delivery conversation
        prompt_style: Key from SUMMARIZATION_PROMPTS
        model: OpenAI model to use
        api_key: OpenAI API key (defaults to env var)

    Returns:
        LLM-generated summary
    """
    api_key = api_key or os.environ.get("OPENAI_API_KEY")
    if not api_key:
        raise ValueError("OPENAI_API_KEY not set")

    prompt = SUMMARIZATION_PROMPTS.get(prompt_style)
    if not prompt:
        raise ValueError(f"Unknown prompt style: {prompt_style}")

    messages = [
        {
            "role": "system",
            "content": "You are a helpful assistant that summarizes delivery agent logs. Be concise and focus on actionable information."
        },
        {
            "role": "user",
            "content": f"{prompt}\n\n---\n\nDelivery Log:\n{delivery_history}"
        }
    ]

    response = httpx.post(
        "https://api.openai.com/v1/chat/completions",
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        },
        json={
            "model": model,
            "messages": messages,
            "temperature": 0.3,
            "max_tokens": 500
        },
        timeout=30
    )

    if response.status_code != 200:
        raise Exception(f"OpenAI API error: {response.status_code} - {response.text}")

    return response.json()["choices"][0]["message"]["content"]


def get_training_data_summarized(prompt_style: str, api_key: Optional[str] = None) -> list[str]:
    """Get LLM-summarized versions of all training deliveries.

    Args:
        prompt_style: Key from SUMMARIZATION_PROMPTS (S1_basic, S2_generic, etc.)
        api_key: OpenAI API key

    Returns:
        List of summarized delivery learnings
    """
    deliveries = get_all_training_deliveries()
    summaries = []

    for delivery in deliveries:
        summary = summarize_with_llm(delivery, prompt_style, api_key=api_key)
        summaries.append(summary)

    return summaries


if __name__ == "__main__":
    print("=== Training Delivery Histories (Demo Format) ===")
    print("All deliveries start from Floor 1 MIDDLE (elevator lobby)\n")

    deliveries = get_all_training_deliveries()
    for i, d in enumerate(deliveries, 1):
        print(f"\n{'='*60}")
        print(f"DELIVERY {i}")
        print('='*60)
        print(d)

    print(f"\n\n{'='*60}")
    print("=== What Each Delivery Teaches ===\n")
    print("Delivery 1 (Rachel Green):")
    print("  - Fire escape exists at Floor 1 front, connects to Floor 3 front")
    print("  - Rachel Green works at Tech Lab (Floor 3 front)")
    print("  - John Smith also at Tech Lab")
    print("  - Maria Santos, Tom Wilson at Lobby & Reception (Floor 1 front)")

    print("\nDelivery 2 (Jake Morrison):")
    print("  - Fire escape ONLY works from Floor 1 front or Floor 3 front (not middle)")
    print("  - Jake Morrison works at Mail Room (Floor 1 back)")
    print("  - Lisa Park also at Mail Room")
    print("  - Peter Zhang, Laura Martinez at Rooftop Cafe (Floor 3 back)")
    print("  - Alex Chen, Sarah Kim at Byte Size Games (Floor 2 back)")

    print("\nDelivery 3 (Sarah Kim):")
    print("  - Direct path: go_up -> go_to_back -> deliver")
    print("  - Shows learning from delivery 2 (already knew Sarah's location)")
