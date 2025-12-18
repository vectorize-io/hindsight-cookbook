"""
Building Simulation Module

Defines the building structure with floors, businesses, and employees.
The delivery agent must navigate this building to deliver packages.
"""

from dataclasses import dataclass, field
from typing import Optional
from enum import Enum
import random


class Side(Enum):
    """Which side of the floor a business is on."""
    FRONT = "front"
    BACK = "back"


@dataclass
class Employee:
    """An employee working at a business."""
    name: str
    role: str


@dataclass
class Business:
    """A business located on one side of a floor."""
    name: str
    floor: int
    side: Side
    employees: list[Employee] = field(default_factory=list)

    def __str__(self):
        return f"{self.name} (Floor {self.floor}, {self.side.value})"


@dataclass
class Package:
    """A package to be delivered."""
    id: str
    recipient_name: str
    business_name: Optional[str] = None  # May or may not be included

    def __str__(self):
        if self.business_name:
            return f"Package #{self.id}: To {self.recipient_name} at {self.business_name}"
        return f"Package #{self.id}: To {self.recipient_name}"


@dataclass
class AgentState:
    """Current state of the delivery agent."""
    floor: int = 1
    side: Side = Side.FRONT
    packages_delivered: int = 0
    steps_taken: int = 0
    current_package: Optional[Package] = None

    def position_str(self) -> str:
        return f"Floor {self.floor}, {self.side.value} side"


class Building:
    """
    A building with multiple floors, each with two businesses (front and back).
    """

    def __init__(self):
        self.floors: dict[int, dict[Side, Business]] = {}
        self.all_employees: dict[str, tuple[Business, Employee]] = {}
        self._setup_building()

    def _setup_building(self):
        """Initialize the building with businesses and employees."""

        # Building layout: 5 floors, 2 businesses per floor
        building_data = [
            # Floor 1 (Ground floor)
            (1, Side.FRONT, "Lobby & Reception", [
                ("Maria Santos", "Receptionist"),
                ("Tom Wilson", "Security Guard"),
            ]),
            (1, Side.BACK, "BuildingOps Inc", [
                ("Jake Morrison", "Facilities Manager"),
                ("Lisa Park", "Maintenance Tech"),
            ]),

            # Floor 2
            (2, Side.FRONT, "TechStart Labs", [
                ("Alex Chen", "Software Engineer"),
                ("Sarah Kim", "Product Manager"),
                ("Dev Patel", "Data Scientist"),
            ]),
            (2, Side.BACK, "Legal Eagles LLP", [
                ("Jennifer Walsh", "Partner"),
                ("Marcus Brown", "Associate"),
                ("Emily Davis", "Paralegal"),
            ]),

            # Floor 3
            (3, Side.FRONT, "Acme Corporation", [
                ("John Smith", "CEO"),
                ("Rachel Green", "CFO"),
                ("Mike Ross", "Sales Director"),
            ]),
            (3, Side.BACK, "Creative Designs Co", [
                ("Nina Rodriguez", "Art Director"),
                ("Chris Taylor", "Graphic Designer"),
                ("Sam Johnson", "UX Designer"),
            ]),

            # Floor 4
            (4, Side.FRONT, "FinanceHub Capital", [
                ("David Lee", "Portfolio Manager"),
                ("Amanda Foster", "Financial Analyst"),
                ("Robert King", "Trader"),
            ]),
            (4, Side.BACK, "MedTech Solutions", [
                ("Dr. Sarah Palmer", "Research Director"),
                ("James Wilson", "Lab Technician"),
                ("Karen White", "Clinical Manager"),
            ]),

            # Floor 5 (Top floor)
            (5, Side.FRONT, "SkyView Marketing", [
                ("Michelle Adams", "Marketing Director"),
                ("Brian Cooper", "Brand Strategist"),
                ("Jessica Lee", "Social Media Manager"),
            ]),
            (5, Side.BACK, "CloudNine Consulting", [
                ("Peter Zhang", "Managing Consultant"),
                ("Laura Martinez", "Senior Consultant"),
                ("Kevin O'Brien", "Business Analyst"),
            ]),
        ]

        for floor_num, side, business_name, employees_data in building_data:
            employees = [Employee(name=name, role=role) for name, role in employees_data]
            business = Business(
                name=business_name,
                floor=floor_num,
                side=side,
                employees=employees
            )

            if floor_num not in self.floors:
                self.floors[floor_num] = {}
            self.floors[floor_num][side] = business

            # Index employees for quick lookup
            for emp in employees:
                self.all_employees[emp.name] = (business, emp)

    @property
    def num_floors(self) -> int:
        return len(self.floors)

    @property
    def min_floor(self) -> int:
        return min(self.floors.keys())

    @property
    def max_floor(self) -> int:
        return max(self.floors.keys())

    def get_business(self, floor: int, side: Side) -> Optional[Business]:
        """Get the business at a specific floor and side."""
        if floor in self.floors and side in self.floors[floor]:
            return self.floors[floor][side]
        return None

    def get_all_businesses(self) -> list[Business]:
        """Get all businesses in the building."""
        businesses = []
        for floor_businesses in self.floors.values():
            businesses.extend(floor_businesses.values())
        return businesses

    def find_employee(self, name: str) -> Optional[tuple[Business, Employee]]:
        """Find an employee by name."""
        return self.all_employees.get(name)

    def find_business_by_name(self, name: str) -> Optional[Business]:
        """Find a business by name (partial match)."""
        name_lower = name.lower()
        for business in self.get_all_businesses():
            if name_lower in business.name.lower():
                return business
        return None

    def generate_package(self, include_business: bool = None) -> Package:
        """Generate a random package for delivery."""
        # Pick a random employee
        emp_name = random.choice(list(self.all_employees.keys()))
        business, employee = self.all_employees[emp_name]

        # Decide whether to include business name
        if include_business is None:
            include_business = random.choice([True, False])

        package_id = f"{random.randint(1000, 9999)}"

        return Package(
            id=package_id,
            recipient_name=employee.name,
            business_name=business.name if include_business else None
        )

    def get_floor_display(self) -> list[dict]:
        """Get building data formatted for display."""
        display_data = []
        for floor_num in sorted(self.floors.keys(), reverse=True):
            floor_data = {
                "floor": floor_num,
                "front": self.floors[floor_num].get(Side.FRONT),
                "back": self.floors[floor_num].get(Side.BACK),
            }
            display_data.append(floor_data)
        return display_data


# Singleton building instance
_building_instance = None

def get_building() -> Building:
    """Get the singleton building instance."""
    global _building_instance
    if _building_instance is None:
        _building_instance = Building()
    return _building_instance


def reset_building():
    """Reset the building instance (useful for testing)."""
    global _building_instance
    _building_instance = None
