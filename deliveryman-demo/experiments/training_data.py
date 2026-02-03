"""Generate training delivery histories for Hindsight experiments.

Creates 3 delivery histories with different scenarios:
1. Rachel Green (Floor 3 FRONT) - uses fire escape from Floor 1
2. Jake Morrison (Floor 1 BACK) - simple delivery
3. Sarah Kim (Floor 2 BACK) - standard elevator path

Each history includes the full agent-tool conversation that would occur.
"""

from building_medium import (
    BUILDING_LAYOUT,
    Side,
    get_employee_location,
    get_business_at,
    get_all_employees,
    can_use_fire_escape,
    get_fire_escape_destination,
)


def generate_delivery_1_rachel_green():
    """Delivery to Rachel Green at Tech Lab (Floor 3 FRONT).

    Agent starts at Floor 1 MIDDLE, discovers fire escape shortcut.
    Optimal path: go_to_front -> use_fire_escape -> deliver_package (3 steps)
    Actual path shown: explores a bit first, then finds optimal route.
    """
    return {
        "recipient": "Rachel Green",
        "location": {"floor": 3, "side": "FRONT", "business": "Tech Lab"},
        "start": {"floor": 1, "side": "MIDDLE"},
        "optimal_steps": 3,
        "actual_steps": 7,
        "used_fire_escape": True,
        "conversation": [
            {
                "role": "user",
                "content": "Deliver a package to Rachel Green. You are currently at Floor 1 MIDDLE (elevator lobby)."
            },
            {
                "role": "assistant",
                "content": "I need to find Rachel Green. Let me check who's on this floor first.",
                "tool_calls": [{"name": "check_current_location", "args": {}}]
            },
            {
                "role": "tool",
                "name": "check_current_location",
                "content": "You are at Floor 1 MIDDLE (elevator lobby). You can go to FRONT or BACK side, or use elevator to go up/down."
            },
            {
                "role": "assistant",
                "content": "Let me check the front side of Floor 1.",
                "tool_calls": [{"name": "go_to_front", "args": {}}]
            },
            {
                "role": "tool",
                "name": "go_to_front",
                "content": "You are now at Floor 1 FRONT. Business: Reception. Employees: Maria Santos (Receptionist), Tom Wilson (Security Guard). You notice a fire escape that goes to Floor 3 FRONT."
            },
            {
                "role": "assistant",
                "content": "Rachel Green isn't here. I see there's a fire escape to Floor 3 FRONT. Let me get the employee list to find Rachel.",
                "tool_calls": [{"name": "get_employee_list", "args": {}}]
            },
            {
                "role": "tool",
                "name": "get_employee_list",
                "content": "Employees in building:\n- Floor 1 FRONT (Reception): Maria Santos, Tom Wilson\n- Floor 1 BACK (Mail Room): Jake Morrison, Lisa Park\n- Floor 2 FRONT (Accounting): Jennifer Walsh, Marcus Brown\n- Floor 2 BACK (Game Studio): Alex Chen, Sarah Kim\n- Floor 3 FRONT (Tech Lab): John Smith, Rachel Green\n- Floor 3 BACK (Cafe): Peter Zhang, Laura Martinez"
            },
            {
                "role": "assistant",
                "content": "Rachel Green is at Floor 3 FRONT (Tech Lab). I'm at Floor 1 FRONT and there's a fire escape that goes directly to Floor 3 FRONT. This is a shortcut!",
                "tool_calls": [{"name": "use_fire_escape", "args": {}}]
            },
            {
                "role": "tool",
                "name": "use_fire_escape",
                "content": "You used the fire escape! You are now at Floor 3 FRONT. Business: Tech Lab. Employees: John Smith (CTO), Rachel Green (Software Engineer)."
            },
            {
                "role": "assistant",
                "content": "I found Rachel Green at the Tech Lab. Delivering the package now.",
                "tool_calls": [{"name": "deliver_package", "args": {"recipient": "Rachel Green"}}]
            },
            {
                "role": "tool",
                "name": "deliver_package",
                "content": "Package successfully delivered to Rachel Green at Tech Lab (Floor 3 FRONT). Delivery complete!"
            },
            {
                "role": "assistant",
                "content": "Package delivered to Rachel Green at the Tech Lab on Floor 3 FRONT. I used the fire escape shortcut from Floor 1 FRONT to get there quickly."
            }
        ]
    }


def generate_delivery_2_jake_morrison():
    """Delivery to Jake Morrison at Mail Room (Floor 1 BACK).

    Agent starts at Floor 2 FRONT (after previous delivery).
    Optimal path: go_down -> go_to_back -> deliver_package (3 steps)
    """
    return {
        "recipient": "Jake Morrison",
        "location": {"floor": 1, "side": "BACK", "business": "Mail Room"},
        "start": {"floor": 2, "side": "FRONT"},
        "optimal_steps": 3,
        "actual_steps": 5,
        "used_fire_escape": False,
        "conversation": [
            {
                "role": "user",
                "content": "Deliver a package to Jake Morrison. You are currently at Floor 2 FRONT (Accounting)."
            },
            {
                "role": "assistant",
                "content": "I need to find Jake Morrison. Let me check the employee list.",
                "tool_calls": [{"name": "get_employee_list", "args": {}}]
            },
            {
                "role": "tool",
                "name": "get_employee_list",
                "content": "Employees in building:\n- Floor 1 FRONT (Reception): Maria Santos, Tom Wilson\n- Floor 1 BACK (Mail Room): Jake Morrison, Lisa Park\n- Floor 2 FRONT (Accounting): Jennifer Walsh, Marcus Brown\n- Floor 2 BACK (Game Studio): Alex Chen, Sarah Kim\n- Floor 3 FRONT (Tech Lab): John Smith, Rachel Green\n- Floor 3 BACK (Cafe): Peter Zhang, Laura Martinez"
            },
            {
                "role": "assistant",
                "content": "Jake Morrison is at Floor 1 BACK (Mail Room). I need to go down one floor and to the back side.",
                "tool_calls": [{"name": "go_down", "args": {}}]
            },
            {
                "role": "tool",
                "name": "go_down",
                "content": "You went down one floor. You are now at Floor 1 MIDDLE (elevator lobby)."
            },
            {
                "role": "assistant",
                "content": "Now I need to go to the back side to reach the Mail Room.",
                "tool_calls": [{"name": "go_to_back", "args": {}}]
            },
            {
                "role": "tool",
                "name": "go_to_back",
                "content": "You are now at Floor 1 BACK. Business: Mail Room. Employees: Jake Morrison (Mail Clerk), Lisa Park (Package Handler)."
            },
            {
                "role": "assistant",
                "content": "Found Jake Morrison. Delivering the package.",
                "tool_calls": [{"name": "deliver_package", "args": {"recipient": "Jake Morrison"}}]
            },
            {
                "role": "tool",
                "name": "deliver_package",
                "content": "Package successfully delivered to Jake Morrison at Mail Room (Floor 1 BACK). Delivery complete!"
            },
            {
                "role": "assistant",
                "content": "Package delivered to Jake Morrison at the Mail Room on Floor 1 BACK."
            }
        ]
    }


def generate_delivery_3_sarah_kim():
    """Delivery to Sarah Kim at Game Studio (Floor 2 BACK).

    Agent starts at Floor 3 FRONT (Tech Lab, after a fire escape delivery).
    Could use fire escape down then go up, but elevator is faster.
    Optimal path: go_down -> go_to_back -> deliver_package (3 steps)
    """
    return {
        "recipient": "Sarah Kim",
        "location": {"floor": 2, "side": "BACK", "business": "Game Studio"},
        "start": {"floor": 3, "side": "FRONT"},
        "optimal_steps": 3,
        "actual_steps": 4,
        "used_fire_escape": False,
        "conversation": [
            {
                "role": "user",
                "content": "Deliver a package to Sarah Kim. You are currently at Floor 3 FRONT (Tech Lab)."
            },
            {
                "role": "assistant",
                "content": "I need to find Sarah Kim. I remember the employee list from before - Sarah Kim works at the Game Studio on Floor 2 BACK.",
                "tool_calls": [{"name": "go_down", "args": {}}]
            },
            {
                "role": "tool",
                "name": "go_down",
                "content": "You went down one floor. You are now at Floor 2 MIDDLE (elevator lobby)."
            },
            {
                "role": "assistant",
                "content": "Now going to the back side where the Game Studio is.",
                "tool_calls": [{"name": "go_to_back", "args": {}}]
            },
            {
                "role": "tool",
                "name": "go_to_back",
                "content": "You are now at Floor 2 BACK. Business: Game Studio. Employees: Alex Chen (Game Developer), Sarah Kim (Level Designer)."
            },
            {
                "role": "assistant",
                "content": "Found Sarah Kim at the Game Studio. Delivering the package.",
                "tool_calls": [{"name": "deliver_package", "args": {"recipient": "Sarah Kim"}}]
            },
            {
                "role": "tool",
                "name": "deliver_package",
                "content": "Package successfully delivered to Sarah Kim at Game Studio (Floor 2 BACK). Delivery complete!"
            },
            {
                "role": "assistant",
                "content": "Package delivered to Sarah Kim at the Game Studio on Floor 2 BACK."
            }
        ]
    }


def format_as_full_history(delivery: dict) -> str:
    """Format delivery as full conversation history for Hindsight storage."""
    lines = [f"=== Delivery to {delivery['recipient']} ==="]
    lines.append(f"Start: Floor {delivery['start']['floor']} {delivery['start']['side']}")
    lines.append(f"Target: {delivery['location']['business']} (Floor {delivery['location']['floor']} {delivery['location']['side']})")
    lines.append(f"Steps taken: {delivery['actual_steps']}")
    if delivery['used_fire_escape']:
        lines.append("Used fire escape shortcut: Yes")
    lines.append("")
    lines.append("Conversation:")

    for msg in delivery['conversation']:
        role = msg['role'].upper()
        if role == "USER":
            lines.append(f"\n[USER]: {msg['content']}")
        elif role == "ASSISTANT":
            lines.append(f"\n[AGENT]: {msg['content']}")
            if 'tool_calls' in msg:
                for tc in msg['tool_calls']:
                    lines.append(f"  -> Called: {tc['name']}")
        elif role == "TOOL":
            lines.append(f"  [TOOL {msg['name']}]: {msg['content']}")

    return "\n".join(lines)


# Pre-defined summarized learnings for different prompts
SUMMARIZATION_PROMPTS = {
    "S1_basic": "Summarize what was learned from this delivery.",
    "S2_location_focus": "Extract key facts about employee locations learned during this delivery.",
    "S3_path_focus": "Extract key facts about locations AND any shortcuts or optimal paths discovered.",
    "S4_structured": """Extract learnings in this format:
- EMPLOYEE: [name] works at [business] on Floor [N] [SIDE] side
- PATH: [any shortcuts or optimal routes discovered]
- TIP: [any useful navigation tips]"""
}

# Example of what good summarized learnings should look like
EXPECTED_SUMMARIES = {
    "rachel_green": {
        "S1_basic": "Delivered to Rachel Green at Tech Lab. She works on Floor 3 FRONT.",
        "S2_location_focus": "Rachel Green works at Tech Lab on Floor 3 FRONT side.",
        "S3_path_focus": "Rachel Green works at Tech Lab on Floor 3 FRONT side. There is a fire escape shortcut from Floor 1 FRONT to Floor 3 FRONT.",
        "S4_structured": """- EMPLOYEE: Rachel Green works at Tech Lab on Floor 3 FRONT side
- PATH: Fire escape connects Floor 1 FRONT directly to Floor 3 FRONT (shortcut!)
- TIP: When delivering to Floor 3 FRONT from lower floors, check if fire escape from Floor 1 FRONT is faster than elevator"""
    },
    "jake_morrison": {
        "S1_basic": "Delivered to Jake Morrison at Mail Room. He works on Floor 1 BACK.",
        "S2_location_focus": "Jake Morrison works at Mail Room on Floor 1 BACK side.",
        "S3_path_focus": "Jake Morrison works at Mail Room on Floor 1 BACK side. Standard elevator route is optimal.",
        "S4_structured": """- EMPLOYEE: Jake Morrison works at Mail Room on Floor 1 BACK side
- PATH: Standard elevator route from upper floors
- TIP: Mail Room is on first floor back side"""
    },
    "sarah_kim": {
        "S1_basic": "Delivered to Sarah Kim at Game Studio. She works on Floor 2 BACK.",
        "S2_location_focus": "Sarah Kim works at Game Studio on Floor 2 BACK side.",
        "S3_path_focus": "Sarah Kim works at Game Studio on Floor 2 BACK side. From Floor 3, elevator down one floor then back side.",
        "S4_structured": """- EMPLOYEE: Sarah Kim works at Game Studio on Floor 2 BACK side
- PATH: Standard elevator to Floor 2, then to BACK side
- TIP: Game Studio is on Floor 2 back side, same floor as Accounting (front)"""
    }
}


def get_all_training_deliveries():
    """Get all 3 training delivery histories."""
    return [
        generate_delivery_1_rachel_green(),
        generate_delivery_2_jake_morrison(),
        generate_delivery_3_sarah_kim(),
    ]


def get_training_data_full():
    """Get full conversation histories for all training deliveries."""
    deliveries = get_all_training_deliveries()
    return [format_as_full_history(d) for d in deliveries]


def get_training_data_summarized(style: str = "S3_path_focus"):
    """Get pre-summarized learnings for training.

    Args:
        style: One of S1_basic, S2_location_focus, S3_path_focus, S4_structured
    """
    return [
        EXPECTED_SUMMARIES["rachel_green"][style],
        EXPECTED_SUMMARIES["jake_morrison"][style],
        EXPECTED_SUMMARIES["sarah_kim"][style],
    ]


if __name__ == "__main__":
    print("=== Training Delivery Histories ===\n")

    deliveries = get_all_training_deliveries()
    for d in deliveries:
        print(f"\n{'='*60}")
        print(format_as_full_history(d))

    print(f"\n\n{'='*60}")
    print("=== Summarization Styles ===\n")

    for style, prompt in SUMMARIZATION_PROMPTS.items():
        print(f"\n{style}: {prompt}")
        print("-" * 40)
        summaries = get_training_data_summarized(style)
        for i, s in enumerate(summaries):
            print(f"  Delivery {i+1}: {s[:80]}...")
