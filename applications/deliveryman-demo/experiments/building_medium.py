"""Medium difficulty building model with fire escape shortcut."""

from dataclasses import dataclass
from enum import Enum
from typing import Dict, List, Optional, Tuple


class Side(str, Enum):
    FRONT = "FRONT"
    BACK = "BACK"
    MIDDLE = "MIDDLE"


@dataclass
class Employee:
    name: str
    role: str


@dataclass
class Business:
    name: str
    employees: List[Employee]


# Building layout - 3 floors, 2 businesses per floor
# Same as easy building but with fire escape shortcut
BUILDING_LAYOUT: Dict[int, Dict[Side, Business]] = {
    1: {
        Side.FRONT: Business("Reception", [
            Employee("Maria Santos", "Receptionist"),
            Employee("Tom Wilson", "Security Guard"),
        ]),
        Side.BACK: Business("Mail Room", [
            Employee("Jake Morrison", "Mail Clerk"),
            Employee("Lisa Park", "Package Handler"),
        ]),
    },
    2: {
        Side.FRONT: Business("Accounting", [
            Employee("Jennifer Walsh", "Senior Accountant"),
            Employee("Marcus Brown", "Tax Specialist"),
        ]),
        Side.BACK: Business("Game Studio", [
            Employee("Alex Chen", "Game Developer"),
            Employee("Sarah Kim", "Level Designer"),
        ]),
    },
    3: {
        Side.FRONT: Business("Tech Lab", [
            Employee("John Smith", "CTO"),
            Employee("Rachel Green", "Software Engineer"),
        ]),
        Side.BACK: Business("Cafe", [
            Employee("Peter Zhang", "Barista"),
            Employee("Laura Martinez", "Pastry Chef"),
        ]),
    },
}

# Fire escape connects Floor 1 FRONT <-> Floor 3 FRONT (shortcut!)
FIRE_ESCAPE = {
    (1, Side.FRONT): (3, Side.FRONT),
    (3, Side.FRONT): (1, Side.FRONT),
}


def get_all_employees() -> List[Tuple[str, int, Side, str]]:
    """Returns list of (name, floor, side, business_name) for all employees."""
    employees = []
    for floor, sides in BUILDING_LAYOUT.items():
        for side, business in sides.items():
            for emp in business.employees:
                employees.append((emp.name, floor, side, business.name))
    return employees


def get_employee_location(name: str) -> Optional[Tuple[int, Side, str]]:
    """Get (floor, side, business_name) for an employee."""
    for floor, sides in BUILDING_LAYOUT.items():
        for side, business in sides.items():
            for emp in business.employees:
                if emp.name.lower() == name.lower():
                    return (floor, side, business.name)
    return None


def get_business_at(floor: int, side: Side) -> Optional[Business]:
    """Get business at a specific location."""
    if side == Side.MIDDLE:
        return None
    return BUILDING_LAYOUT.get(floor, {}).get(side)


def get_employees_at(floor: int, side: Side) -> List[Employee]:
    """Get employees at a specific location."""
    business = get_business_at(floor, side)
    return business.employees if business else []


def can_use_fire_escape(floor: int, side: Side) -> bool:
    """Check if fire escape is accessible from current position."""
    return (floor, side) in FIRE_ESCAPE


def get_fire_escape_destination(floor: int, side: Side) -> Optional[Tuple[int, Side]]:
    """Get destination when using fire escape."""
    return FIRE_ESCAPE.get((floor, side))


def calculate_optimal_steps(
    start_floor: int,
    start_side: Side,
    target_floor: int,
    target_side: Side
) -> Tuple[int, List[str]]:
    """Calculate minimum steps and optimal path to reach target.

    Returns (steps, path) where path is list of tool names.

    Rules:
    - go_up/go_down: Changes floor, lands in MIDDLE
    - go_to_front/go_to_back: Changes side
    - use_fire_escape: Floor 1 FRONT <-> Floor 3 FRONT (1 step!)
    - deliver_package: Final step
    """
    steps = []
    current_floor = start_floor
    current_side = start_side

    # Check if fire escape is optimal
    # Fire escape is good when: going to Floor 3 FRONT from Floor 1 area, or vice versa
    use_fire_escape_path = False

    if target_floor == 3 and target_side == Side.FRONT:
        # Going to Floor 3 FRONT - fire escape might help
        if current_floor == 1 and current_side == Side.FRONT:
            # Perfect - direct fire escape
            use_fire_escape_path = True
        elif current_floor == 1 and current_side != Side.FRONT:
            # Need to get to FRONT first, then fire escape
            # Compare: go_to_front + fire_escape (2) vs go_up + go_up + go_to_front (3)
            use_fire_escape_path = True
        elif current_floor == 2:
            # From floor 2: go_up + go_to_front (2) vs go_down + go_to_front + fire_escape (3)
            use_fire_escape_path = False

    elif target_floor == 1 and target_side == Side.FRONT:
        # Going to Floor 1 FRONT from Floor 3 FRONT area
        if current_floor == 3 and current_side == Side.FRONT:
            use_fire_escape_path = True
        elif current_floor == 3 and current_side != Side.FRONT:
            # go_to_front + fire_escape (2) vs go_down + go_down + go_to_front (3)
            use_fire_escape_path = True

    if use_fire_escape_path and target_side == Side.FRONT:
        # Use fire escape strategy
        if target_floor == 3:
            # Going UP to Floor 3 FRONT
            if current_side != Side.FRONT:
                if current_floor != 1:
                    # Need to go down to floor 1 first
                    while current_floor > 1:
                        steps.append("go_down")
                        current_floor -= 1
                        current_side = Side.MIDDLE
                steps.append("go_to_front")
                current_side = Side.FRONT
            elif current_floor != 1:
                # At FRONT but not floor 1
                while current_floor > 1:
                    steps.append("go_down")
                    current_floor -= 1
                    current_side = Side.MIDDLE
                steps.append("go_to_front")
                current_side = Side.FRONT

            if current_floor == 1 and current_side == Side.FRONT:
                steps.append("use_fire_escape")
                current_floor = 3
                current_side = Side.FRONT
        else:
            # Going DOWN to Floor 1 FRONT
            if current_side != Side.FRONT:
                steps.append("go_to_front")
                current_side = Side.FRONT
            if current_floor == 3 and current_side == Side.FRONT:
                steps.append("use_fire_escape")
                current_floor = 1
                current_side = Side.FRONT
    else:
        # Normal elevator strategy
        # First, handle floor changes
        while current_floor != target_floor:
            if current_floor < target_floor:
                steps.append("go_up")
                current_floor += 1
            else:
                steps.append("go_down")
                current_floor -= 1
            current_side = Side.MIDDLE

        # Then, handle side changes
        if current_side != target_side:
            if target_side == Side.FRONT:
                steps.append("go_to_front")
            elif target_side == Side.BACK:
                steps.append("go_to_back")
            current_side = target_side

    # Final delivery
    steps.append("deliver_package")

    return len(steps), steps


def format_location(floor: int, side: Side) -> str:
    """Format location as readable string."""
    business = get_business_at(floor, side)
    if business:
        return f"Floor {floor} {side.value} ({business.name})"
    return f"Floor {floor} {side.value}"


# All available tools
TOOLS = [
    "go_up",
    "go_down",
    "go_to_front",
    "go_to_back",
    "use_fire_escape",
    "check_current_location",
    "get_employee_list",
    "deliver_package",
]


if __name__ == "__main__":
    # Test optimal path calculations
    print("=== Testing Optimal Paths ===\n")

    test_cases = [
        # (start_floor, start_side, target_floor, target_side, description)
        (1, Side.FRONT, 3, Side.FRONT, "Fire escape: F1 FRONT → F3 FRONT"),
        (1, Side.MIDDLE, 3, Side.FRONT, "F1 MIDDLE → F3 FRONT (should use fire escape)"),
        (1, Side.BACK, 3, Side.FRONT, "F1 BACK → F3 FRONT (fire escape after go_to_front)"),
        (2, Side.MIDDLE, 3, Side.FRONT, "F2 MIDDLE → F3 FRONT (elevator faster)"),
        (1, Side.FRONT, 3, Side.BACK, "F1 FRONT → F3 BACK (no fire escape - wrong side)"),
        (3, Side.FRONT, 1, Side.FRONT, "Fire escape down: F3 FRONT → F1 FRONT"),
        (1, Side.FRONT, 2, Side.BACK, "Normal: F1 FRONT → F2 BACK"),
    ]

    for start_floor, start_side, target_floor, target_side, desc in test_cases:
        steps, path = calculate_optimal_steps(start_floor, start_side, target_floor, target_side)
        print(f"{desc}")
        print(f"  Steps: {steps}")
        print(f"  Path: {' → '.join(path)}")
        print()
