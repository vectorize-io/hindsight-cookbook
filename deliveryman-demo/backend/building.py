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
    """Which side of the floor a business is on, or middle (elevator area).

    For easy mode: FRONT/BACK sides of a single building
    For medium mode: BUILDING_A/BUILDING_B/BUILDING_C (3 separate buildings)
    """
    FRONT = "front"
    BACK = "back"
    MIDDLE = "middle"  # Elevator/hallway - no business here
    # Medium difficulty: 3 buildings
    BUILDING_A = "building_a"
    BUILDING_B = "building_b"
    BUILDING_C = "building_c"


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

    def __init__(self, difficulty: str = "easy"):
        self.difficulty = difficulty
        self.floors: dict[int, dict[Side, Business]] = {}
        self.all_employees: dict[str, tuple[Business, Employee]] = {}
        self._setup_building()

    def _setup_building(self):
        """Initialize the building with businesses and employees."""
        building_data = BUILDING_DATA.get(self.difficulty, BUILDING_DATA["easy"])

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

    @property
    def is_multi_building(self) -> bool:
        """Check if this is a multi-building layout (medium difficulty)."""
        return self.difficulty == "medium"

    @property
    def available_positions(self) -> list[Side]:
        """Get the available side/building positions for this difficulty."""
        if self.is_multi_building:
            return [Side.BUILDING_A, Side.BUILDING_B, Side.BUILDING_C]
        return [Side.FRONT, Side.BACK]

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
            if self.is_multi_building:
                floor_data = {
                    "floor": floor_num,
                    "building_a": self.floors[floor_num].get(Side.BUILDING_A),
                    "building_b": self.floors[floor_num].get(Side.BUILDING_B),
                    "building_c": self.floors[floor_num].get(Side.BUILDING_C),
                }
            else:
                floor_data = {
                    "floor": floor_num,
                    "front": self.floors[floor_num].get(Side.FRONT),
                    "back": self.floors[floor_num].get(Side.BACK),
                }
            display_data.append(floor_data)
        return display_data

    def get_businesses_for_renderer(self) -> dict:
        """Get businesses dict formatted for game renderer.

        Returns dict mapping (floor, side) tuples to business names.
        Cached after first call to avoid recreation on every render.
        """
        if not hasattr(self, '_renderer_businesses'):
            businesses = {}
            if self.is_multi_building:
                for floor_num in range(1, self.num_floors + 1):
                    floor_data = self.floors.get(floor_num, {})
                    for side in [Side.BUILDING_A, Side.BUILDING_B, Side.BUILDING_C]:
                        biz = floor_data.get(side)
                        businesses[(floor_num, side.value)] = biz.name if biz else "Office"
            else:
                for floor_num in range(1, self.num_floors + 1):
                    floor_data = self.floors.get(floor_num, {})
                    front_biz = floor_data.get(Side.FRONT)
                    back_biz = floor_data.get(Side.BACK)
                    businesses[(floor_num, "front")] = front_biz.name if front_biz else "Office"
                    businesses[(floor_num, "back")] = back_biz.name if back_biz else "Office"
            self._renderer_businesses = businesses
        return self._renderer_businesses


# Building data for different difficulties
BUILDING_DATA = {
    "easy": [
        # Floor 1 (Ground floor) - Reception and Mail Room
        (1, Side.FRONT, "Reception", [
            ("Maria Santos", "Receptionist"),
            ("Tom Wilson", "Security Guard"),
        ]),
        (1, Side.BACK, "Mail Room", [
            ("Jake Morrison", "Mail Clerk"),
            ("Lisa Park", "Package Handler"),
        ]),
        # Floor 2 - Accounting and Game Studio
        (2, Side.FRONT, "Accounting", [
            ("Jennifer Walsh", "Senior Accountant"),
            ("Marcus Brown", "Tax Specialist"),
        ]),
        (2, Side.BACK, "Game Studio", [
            ("Alex Chen", "Game Developer"),
            ("Sarah Kim", "Level Designer"),
        ]),
        # Floor 3 (Top floor) - Tech Lab and Cafe
        (3, Side.FRONT, "Tech Lab", [
            ("John Smith", "CTO"),
            ("Rachel Green", "Software Engineer"),
        ]),
        (3, Side.BACK, "Cafe", [
            ("Peter Zhang", "Barista"),
            ("Laura Martinez", "Pastry Chef"),
        ]),
    ],
    "medium": [
        # 3 Buildings (A, B, C) with 4 floors each
        # Bridge connects all buildings at Floor 3
        # Ground passage connects all buildings at Floor 1

        # Building A - Floor 1: Lobby
        (1, Side.BUILDING_A, "Lobby", [
            ("Carlos Mendez", "Concierge"),
            ("Nina Patel", "Building Manager"),
        ]),
        # Building A - Floor 2: Game Studio
        (2, Side.BUILDING_A, "Game Studio", [
            ("Alex Chen", "Game Developer"),
            ("Sarah Kim", "Level Designer"),
        ]),
        # Building A - Floor 3: Exec Suite (BRIDGE LEVEL)
        (3, Side.BUILDING_A, "Exec Suite", [
            ("William Sterling", "CEO"),
            ("Elizabeth Hart", "COO"),
        ]),
        # Building A - Floor 4: Reception
        (4, Side.BUILDING_A, "Reception", [
            ("Maria Santos", "Receptionist"),
            ("Tom Wilson", "Security Guard"),
        ]),

        # Building B - Floor 1: Storage
        (1, Side.BUILDING_B, "Storage", [
            ("Jake Morrison", "Warehouse Manager"),
            ("Lisa Park", "Inventory Clerk"),
        ]),
        # Building B - Floor 2: Archives
        (2, Side.BUILDING_B, "Archives", [
            ("Robert Blake", "Records Manager"),
            ("Sandra Wells", "Archivist"),
        ]),
        # Building B - Floor 3: Marketing (BRIDGE LEVEL)
        (3, Side.BUILDING_B, "Marketing", [
            ("Diana Cross", "Marketing Director"),
            ("Tyler Ross", "Social Media Manager"),
        ]),
        # Building B - Floor 4: Cafe
        (4, Side.BUILDING_B, "Cafe", [
            ("Peter Zhang", "Barista"),
            ("Laura Martinez", "Pastry Chef"),
        ]),

        # Building C - Floor 1: IT Support
        (1, Side.BUILDING_C, "IT Support", [
            ("Brandon Lee", "IT Manager"),
            ("Zoe Anderson", "Help Desk Lead"),
        ]),
        # Building C - Floor 2: Accounting
        (2, Side.BUILDING_C, "Accounting", [
            ("Jennifer Walsh", "Senior Accountant"),
            ("Marcus Brown", "Tax Specialist"),
        ]),
        # Building C - Floor 3: Sales (BRIDGE LEVEL)
        (3, Side.BUILDING_C, "Sales", [
            ("Victor Huang", "Sales VP"),
            ("Olivia Moore", "Account Executive"),
        ]),
        # Building C - Floor 4: HR Dept
        (4, Side.BUILDING_C, "HR Dept", [
            ("Patricia Hughes", "HR Director"),
            ("Kevin O'Brien", "Recruiter"),
        ]),
    ],
    "hard": [
        # Floor 1 - Main Entrance
        (1, Side.FRONT, "Reception Hall", [
            ("Jorge Ramirez", "Head Receptionist"),
            ("Priya Sharma", "Guest Services"),
            ("Michael Okonkwo", "Doorman"),
        ]),
        (1, Side.BACK, "Package Center", [
            ("Hannah Schmidt", "Logistics Coordinator"),
            ("Darius Jackson", "Package Clerk"),
            ("Yuki Tanaka", "Inventory Manager"),
        ]),
        # Floor 2 - Administrative
        (2, Side.FRONT, "Administration", [
            ("Catherine Bell", "Admin Director"),
            ("Ryan Murphy", "Office Manager"),
            ("Fatima Al-Hassan", "Executive Secretary"),
            ("Sean O'Connor", "Facilities Coordinator"),
        ]),
        (2, Side.BACK, "IT Support", [
            ("Brandon Lee", "IT Manager"),
            ("Zoe Anderson", "Help Desk Lead"),
            ("Raj Gupta", "System Administrator"),
        ]),
        # Floor 3 - Creative
        (3, Side.FRONT, "Advertising Agency", [
            ("Monica Reyes", "Creative Director"),
            ("Jason Park", "Art Director"),
            ("Stephanie Collins", "Copywriter"),
            ("Andre Williams", "Media Buyer"),
        ]),
        (3, Side.BACK, "Photography Studio", [
            ("Natasha Volkov", "Lead Photographer"),
            ("Marcus Thompson", "Photo Editor"),
            ("Chelsea Green", "Studio Assistant"),
        ]),
        # Floor 4 - Professional Services
        (4, Side.FRONT, "Law Firm", [
            ("Richard Goldstein", "Senior Partner"),
            ("Victoria Chang", "Associate Attorney"),
            ("Daniel Martinez", "Paralegal"),
            ("Rebecca Hughes", "Legal Secretary"),
        ]),
        (4, Side.BACK, "Consulting Group", [
            ("Alexandra Foster", "Managing Consultant"),
            ("Thomas Wright", "Strategy Analyst"),
            ("Jennifer Liu", "Business Analyst"),
        ]),
        # Floor 5 - Technology
        (5, Side.FRONT, "Software Company", [
            ("David Kim", "CTO"),
            ("Emily Watson", "Product Manager"),
            ("Christopher Lee", "Senior Developer"),
            ("Amanda Brown", "QA Lead"),
            ("Nicholas Chen", "Junior Developer"),
        ]),
        (5, Side.BACK, "Data Science Lab", [
            ("Sarah Johnson", "Data Science Director"),
            ("Kevin Patel", "Machine Learning Engineer"),
            ("Laura Garcia", "Data Analyst"),
        ]),
        # Floor 6 - Media
        (6, Side.FRONT, "News Station", [
            ("James Morrison", "News Director"),
            ("Angela Davis", "Anchor"),
            ("Robert Taylor", "Producer"),
            ("Michelle Wong", "Reporter"),
        ]),
        (6, Side.BACK, "Podcast Studio", [
            ("Brian O'Neill", "Studio Manager"),
            ("Jessica Kim", "Audio Engineer"),
            ("Mark Stevens", "Host"),
        ]),
        # Floor 7 - Executive
        (7, Side.FRONT, "Corporate Headquarters", [
            ("Elizabeth Blackwell", "CEO"),
            ("Jonathan Pierce", "President"),
            ("Margaret Chen", "Board Secretary"),
            ("Douglas Hamilton", "Chief of Staff"),
        ]),
        (7, Side.BACK, "Investor Relations", [
            ("Katherine Ross", "IR Director"),
            ("Paul Anderson", "Financial Analyst"),
            ("Linda Martinez", "Communications Manager"),
        ]),
    ],
}

# Difficulty type
Difficulty = str  # "easy" | "medium" | "hard"

# Singleton building instances per difficulty
_building_instances: dict[str, Building] = {}
_current_difficulty: str = "easy"


def get_building(difficulty: str = None) -> Building:
    """Get the building instance for a difficulty level."""
    global _building_instances, _current_difficulty
    if difficulty is None:
        difficulty = _current_difficulty
    if difficulty not in _building_instances:
        _building_instances[difficulty] = Building(difficulty)
    return _building_instances[difficulty]


def set_difficulty(difficulty: str) -> Building:
    """Set the current difficulty and return the building."""
    global _current_difficulty
    if difficulty not in BUILDING_DATA:
        raise ValueError(f"Invalid difficulty: {difficulty}. Must be one of: {list(BUILDING_DATA.keys())}")
    _current_difficulty = difficulty
    return get_building(difficulty)


def get_current_difficulty() -> str:
    """Get the current difficulty level."""
    return _current_difficulty


def reset_building(difficulty: str = None):
    """Reset the building instance (useful for testing)."""
    global _building_instances
    if difficulty:
        if difficulty in _building_instances:
            del _building_instances[difficulty]
    else:
        _building_instances = {}
