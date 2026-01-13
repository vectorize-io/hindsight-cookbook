"""Simple building model for Hindsight experiments."""

from dataclasses import dataclass
from enum import Enum
from typing import Dict, List, Optional
import random


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


@dataclass
class Location:
    floor: int
    side: Side
    business: Optional[Business] = None

    def __str__(self):
        if self.side == Side.MIDDLE:
            return f"Floor {self.floor}, MIDDLE hallway"
        return f"Floor {self.floor}, {self.side.value} side ({self.business.name if self.business else 'unknown'})"


# Building layout - 3 floors, 2 businesses per floor
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


def get_all_employees() -> List[tuple[str, int, Side, str]]:
    """Returns list of (name, floor, side, business_name) for all employees."""
    employees = []
    for floor, sides in BUILDING_LAYOUT.items():
        for side, business in sides.items():
            for emp in business.employees:
                employees.append((emp.name, floor, side, business.name))
    return employees


def get_employee_location(name: str) -> Optional[tuple[int, Side, str]]:
    """Get (floor, side, business_name) for an employee."""
    for floor, sides in BUILDING_LAYOUT.items():
        for side, business in sides.items():
            for emp in business.employees:
                if emp.name.lower() == name.lower():
                    return (floor, side, business.name)
    return None


def get_random_employee() -> tuple[str, int, Side, str]:
    """Get a random employee for delivery."""
    employees = get_all_employees()
    return random.choice(employees)


def get_business_at(floor: int, side: Side) -> Optional[Business]:
    """Get business at a specific location."""
    if side == Side.MIDDLE:
        return None
    return BUILDING_LAYOUT.get(floor, {}).get(side)


def get_employees_at(floor: int, side: Side) -> List[Employee]:
    """Get employees at a specific location."""
    business = get_business_at(floor, side)
    return business.employees if business else []


# Starting positions for experiments
STARTING_POSITIONS = [
    (1, Side.FRONT),   # Floor 1, Reception
    (1, Side.MIDDLE),  # Floor 1, Elevator
    (2, Side.MIDDLE),  # Floor 2, Elevator
]


def get_random_start() -> tuple[int, Side]:
    """Get a random starting position."""
    return random.choice(STARTING_POSITIONS)


def calculate_optimal_steps(start_floor: int, start_side: Side, target_floor: int, target_side: Side) -> int:
    """Calculate the minimum steps needed to reach target from start.

    Rules:
    - go_up/go_down: Changes floor, always lands in MIDDLE
    - go_to_front/go_to_back: Changes side (only from MIDDLE or opposite side)
    - Must be at correct side to deliver
    """
    steps = 0
    current_floor = start_floor
    current_side = start_side

    # If not in middle and need to change floors, first go to middle
    if current_floor != target_floor and current_side != Side.MIDDLE:
        # Actually, go_up/go_down work from any position and land in MIDDLE
        pass

    # Move to correct floor
    floor_diff = abs(target_floor - current_floor)
    if floor_diff > 0:
        steps += floor_diff  # Each floor change is one step
        current_side = Side.MIDDLE  # Elevator deposits in middle

    # Move to correct side
    if current_side != target_side:
        if current_side == Side.MIDDLE:
            steps += 1  # Direct move to target side
        else:
            # Need to go through middle? No, can go directly front<->back
            steps += 1  # Direct move

    # Deliver
    steps += 1

    return steps
