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
    For hard mode: STREET (on city grid) or INSIDE (inside a building)
    """
    FRONT = "front"
    BACK = "back"
    MIDDLE = "middle"  # Elevator/hallway - no business here
    # Medium difficulty: 3 buildings
    BUILDING_A = "building_a"
    BUILDING_B = "building_b"
    BUILDING_C = "building_c"
    # Hard difficulty: city grid
    STREET = "street"  # On the street, not inside a building
    INSIDE = "inside"  # Inside a building


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
    # Hard mode: city grid position
    grid_row: int = 0  # Row in city grid (0 = top)
    grid_col: int = 0  # Column in city grid (0 = left)
    current_building: Optional[str] = None  # Name of building agent is inside (None if on street)

    def position_str(self) -> str:
        if self.current_building:
            return f"Inside {self.current_building}, Floor {self.floor}"
        elif self.side == Side.STREET:
            return f"On street at ({self.grid_row}, {self.grid_col})"
        return f"Floor {self.floor}, {self.side.value} side"


class CityBuilding:
    """A single building in the city grid (for hard mode)."""

    def __init__(self, name: str, row: int, col: int, floors_data: list):
        self.name = name
        self.row = row
        self.col = col
        self.floors: dict[int, Business] = {}
        self.all_employees: dict[str, tuple[Business, Employee]] = {}

        # Build floors from data: [(floor_num, dept_name, [(emp_name, role), ...]), ...]
        for floor_num, dept_name, employees_data in floors_data:
            employees = [Employee(name=name, role=role) for name, role in employees_data]
            business = Business(
                name=dept_name,
                floor=floor_num,
                side=Side.INSIDE,
                employees=employees
            )
            self.floors[floor_num] = business
            for emp in employees:
                self.all_employees[emp.name] = (business, emp)

    @property
    def num_floors(self) -> int:
        return len(self.floors)

    @property
    def min_floor(self) -> int:
        return min(self.floors.keys()) if self.floors else 1

    @property
    def max_floor(self) -> int:
        return max(self.floors.keys()) if self.floors else 1

    def get_business(self, floor: int) -> Optional[Business]:
        return self.floors.get(floor)

    def find_employee(self, name: str) -> Optional[tuple[Business, Employee]]:
        return self.all_employees.get(name)


class CityGrid:
    """City grid for hard mode - contains multiple buildings."""

    def __init__(self):
        self.rows = CITY_GRID_ROWS
        self.cols = CITY_GRID_COLS
        self.buildings: dict[str, CityBuilding] = {}
        self.grid: dict[tuple[int, int], CityBuilding] = {}
        self.all_employees: dict[str, tuple[str, Business, Employee]] = {}  # emp_name -> (building_name, business, emp)
        self._setup_city()

    def _setup_city(self):
        """Initialize the city with buildings."""
        for (row, col), building_name in CITY_GRID.items():
            floors_data = CITY_BUILDINGS_DATA.get(building_name, [])
            building = CityBuilding(building_name, row, col, floors_data)
            self.buildings[building_name] = building
            self.grid[(row, col)] = building
            # Index all employees with building reference
            for emp_name, (business, emp) in building.all_employees.items():
                self.all_employees[emp_name] = (building_name, business, emp)

    def get_building_at(self, row: int, col: int) -> Optional[CityBuilding]:
        """Get the building at a grid position."""
        return self.grid.get((row, col))

    def get_building_by_name(self, name: str) -> Optional[CityBuilding]:
        """Get a building by name."""
        return self.buildings.get(name)

    def find_employee(self, name: str) -> Optional[tuple[str, Business, Employee]]:
        """Find an employee anywhere in the city. Returns (building_name, business, employee)."""
        return self.all_employees.get(name)

    def get_adjacent_buildings(self, row: int, col: int) -> dict[str, Optional[str]]:
        """Get building names in adjacent directions."""
        adjacent = {}
        if row > 0:
            b = self.get_building_at(row - 1, col)
            adjacent["north"] = b.name if b else None
        else:
            adjacent["north"] = None
        if row < self.rows - 1:
            b = self.get_building_at(row + 1, col)
            adjacent["south"] = b.name if b else None
        else:
            adjacent["south"] = None
        if col > 0:
            b = self.get_building_at(row, col - 1)
            adjacent["west"] = b.name if b else None
        else:
            adjacent["west"] = None
        if col < self.cols - 1:
            b = self.get_building_at(row, col + 1)
            adjacent["east"] = b.name if b else None
        else:
            adjacent["east"] = None
        return adjacent

    def generate_package(self, include_business: bool = None) -> Package:
        """Generate a random package for delivery."""
        emp_name = random.choice(list(self.all_employees.keys()))
        building_name, business, employee = self.all_employees[emp_name]

        if include_business is None:
            include_business = random.choice([True, False])

        package_id = f"{random.randint(1000, 9999)}"
        # For hard mode, business_name includes the building
        if include_business:
            business_str = f"{business.name} at {building_name}"
        else:
            business_str = None

        return Package(
            id=package_id,
            recipient_name=employee.name,
            business_name=business_str
        )


class Building:
    """
    A building with multiple floors, each with two businesses (front and back).
    For hard mode, this wraps a CityGrid instead.
    """

    def __init__(self, difficulty: str = "easy"):
        self.difficulty = difficulty
        self.floors: dict[int, dict[Side, Business]] = {}
        self.all_employees: dict[str, tuple[Business, Employee]] = {}
        self.city_grid: Optional[CityGrid] = None  # Only for hard mode
        self._setup_building()

    def _setup_building(self):
        """Initialize the building with businesses and employees."""
        # Hard mode uses city grid instead
        if self.difficulty == "hard":
            self.city_grid = CityGrid()
            # Copy all employees to building-level for compatibility
            for emp_name, (building_name, business, emp) in self.city_grid.all_employees.items():
                self.all_employees[emp_name] = (business, emp)
            return

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
        if self.is_city_grid:
            return 5  # All city buildings have 5 floors
        return len(self.floors)

    @property
    def min_floor(self) -> int:
        if self.is_city_grid:
            return 1
        return min(self.floors.keys()) if self.floors else 1

    @property
    def max_floor(self) -> int:
        if self.is_city_grid:
            return 5
        return max(self.floors.keys()) if self.floors else 1

    @property
    def is_multi_building(self) -> bool:
        """Check if this is a multi-building layout (medium difficulty)."""
        return self.difficulty == "medium"

    @property
    def is_city_grid(self) -> bool:
        """Check if this is a city grid layout (hard difficulty)."""
        return self.difficulty == "hard" and self.city_grid is not None

    @property
    def available_positions(self) -> list[Side]:
        """Get the available side/building positions for this difficulty."""
        if self.is_city_grid:
            return [Side.STREET, Side.INSIDE]
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

    def _is_starting_location(self, business: 'Business') -> bool:
        """Check if a business is at the agent's starting location."""
        if self.difficulty == "easy":
            return business.floor == 1 and business.side == Side.FRONT
        elif self.difficulty == "medium":
            return business.floor == 1 and business.side == Side.BUILDING_A
        return False

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
        # Hard mode uses city_grid to generate packages
        if self.is_city_grid:
            return self.city_grid.generate_package(include_business)

        # Pick a random employee, excluding those at the starting location
        eligible = [
            name for name, (biz, _) in self.all_employees.items()
            if not self._is_starting_location(biz)
        ]
        emp_name = random.choice(eligible if eligible else list(self.all_employees.keys()))
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
    # Hard mode uses CITY_GRID_DATA instead (see below)
    "hard": [],
}

# Hard mode: City grid with 12 buildings, each with 5 floors
# Grid layout (4 columns x 3 rows):
#   Row 0: Tech Corp, City Bank, Law Office, Medical
#   Row 1: Real Estate, News Studio, Accounting, Insurance Co
#   Row 2: Marketing, Consulting, Engineering, Data Center

# Simple grid: 3 rows x 7 cols
# Buildings at EVEN columns (0, 2, 4, 6) - agent stands "in front of door"
# Roads at ODD columns (1, 3, 5) - vertical roads between buildings
#
# Grid layout:
# Col:  0          1      2          3      4           5      6
# Row 0: Tech Corp  road   City Bank  road   Law Office  road   Medical
# Row 1: Real Est   road   News Std   road   Accounting  road   Ins Co
# Row 2: Marketing  road   Consulting road   Engineering road   Data Ctr

CITY_GRID = {
    # (row, col): building_name - buildings at EVEN columns
    (0, 0): "Tech Corp",
    (0, 2): "City Bank",
    (0, 4): "Law Office",
    (0, 6): "Medical",
    (1, 0): "Real Estate",
    (1, 2): "News Studio",
    (1, 4): "Accounting",
    (1, 6): "Insurance Co",
    (2, 0): "Marketing",
    (2, 2): "Consulting",
    (2, 4): "Engineering",
    (2, 6): "Data Center",
}

CITY_GRID_ROWS = 3
CITY_GRID_COLS = 7

def is_road_cell(row: int, col: int) -> bool:
    """Check if a grid position is a road (odd column)."""
    return col % 2 == 1

def is_building_cell(row: int, col: int) -> bool:
    """Check if a grid position is a building (even column)."""
    return col % 2 == 0

def is_intersection(row: int, col: int) -> bool:
    """Check if a grid position is a road (roads are at odd columns)."""
    return col % 2 == 1

def get_adjacent_buildings(row: int, col: int) -> dict:
    """Get buildings adjacent to a road position."""
    adjacent = {}
    directions = [("north", -1, 0), ("south", 1, 0), ("east", 0, 1), ("west", 0, -1)]
    for direction, dr, dc in directions:
        nr, nc = row + dr, col + dc
        if (nr, nc) in CITY_GRID:
            adjacent[direction] = CITY_GRID[(nr, nc)]
    return adjacent

def get_cell_description(row: int, col: int) -> str:
    """Get a description of what's at a grid position."""
    if (row, col) in CITY_GRID:
        return CITY_GRID[(row, col)]
    elif is_intersection(row, col):
        return "intersection"
    else:
        return "road"

# Each building has 4 floors with employees
# Format: building_name -> [(floor, department_name, [(employee_name, role), ...]), ...]
CITY_BUILDINGS_DATA = {
    "Tech Corp": [
        (1, "Lobby", [("Amy Chen", "Receptionist"), ("Mike Ross", "Security")]),
        (2, "Engineering", [("David Kim", "CTO"), ("Sarah Lee", "Senior Engineer")]),
        (3, "Product", [("Emily Watson", "Product Manager"), ("Chris Park", "Designer")]),
        (4, "Executive", [("James Wilson", "CEO"), ("Lisa Wang", "CFO")]),
    ],
    "City Bank": [
        (1, "Teller Hall", [("Maria Garcia", "Head Teller"), ("John Smith", "Teller")]),
        (2, "Loans", [("Robert Johnson", "Loan Officer"), ("Patricia White", "Analyst")]),
        (3, "Investments", [("Michael Brown", "Investment Advisor"), ("Jennifer Lee", "Trader")]),
        (4, "Management", [("Richard Taylor", "Branch Manager"), ("Susan Anderson", "VP Operations")]),
    ],
    "Law Office": [
        (1, "Reception", [("Nancy Drew", "Legal Secretary"), ("Frank Hardy", "Paralegal")]),
        (2, "Family Law", [("Victoria Chang", "Family Attorney"), ("Daniel Martinez", "Associate")]),
        (3, "Corporate", [("Richard Goldstein", "Corporate Partner"), ("Rachel Green", "Associate")]),
        (4, "Partners", [("Jessica Pearson", "Managing Partner"), ("Louis Litt", "Senior Partner")]),
    ],
    "Medical": [
        (1, "Admissions", [("Grace Kim", "Admin Coordinator"), ("Henry Park", "Records Clerk")]),
        (2, "General Practice", [("Dr. Sarah Chen", "GP"), ("Nurse Betty", "RN")]),
        (3, "Specialists", [("Dr. James House", "Diagnostician"), ("Dr. Lisa Cuddy", "Administrator")]),
        (4, "Surgery", [("Dr. Derek Shepherd", "Surgeon"), ("Dr. Meredith Grey", "Resident")]),
    ],
    "Real Estate": [
        (1, "Welcome Center", [("Phil Dunphy", "Agent"), ("Claire Dunphy", "Manager")]),
        (2, "Residential", [("Gloria Pritchett", "Luxury Agent"), ("Jay Pritchett", "Commercial")]),
        (3, "Commercial", [("Mitchell Pritchett", "Office Leasing"), ("Cameron Tucker", "Retail")]),
        (4, "Executive", [("Haley Dunphy", "Marketing Director"), ("Dylan Marshall", "Tech Lead")]),
    ],
    "News Studio": [
        (1, "Lobby", [("Kent Brockman", "Anchor"), ("Robin Scherbatsky", "Reporter")]),
        (2, "Newsroom", [("Ted Mosby", "Editor"), ("Marshall Eriksen", "Writer")]),
        (3, "Production", [("Barney Stinson", "Producer"), ("Lily Aldrin", "Director")]),
        (4, "Management", [("James Morrison", "News Director"), ("Angela Davis", "VP Content")]),
    ],
    "Accounting": [
        (1, "Reception", [("Oscar Martinez", "Receptionist"), ("Kevin Malone", "Greeter")]),
        (2, "Tax Services", [("Angela Martin", "Tax Manager"), ("Stanley Hudson", "Tax Prep")]),
        (3, "Audit", [("Dwight Schrute", "Audit Manager"), ("Jim Halpert", "Senior Auditor")]),
        (4, "Partners", [("Michael Scott", "Regional Manager"), ("Toby Flenderson", "HR")]),
    ],
    "Insurance Co": [
        (1, "Claims", [("Flo", "Claims Agent"), ("Jake", "Senior Agent")]),
        (2, "Underwriting", [("Dennis Nedry", "Underwriter"), ("Ray Arnold", "Analyst")]),
        (3, "Sales", [("Gil Gunderson", "Sales Rep"), ("Lionel Hutz", "Agent")]),
        (4, "Executive", [("Mr. Burns", "CEO"), ("Waylon Smithers", "Executive Assistant")]),
    ],
    "Marketing": [
        (1, "Creative Hub", [("Don Draper", "Creative Director"), ("Peggy Olson", "Copywriter")]),
        (2, "Digital", [("Pete Campbell", "Digital Lead"), ("Ken Cosgrove", "Accounts")]),
        (3, "Strategy", [("Joan Holloway", "Strategy Director"), ("Lane Pryce", "Planning")]),
        (4, "Executive", [("Diana Cross", "CMO"), ("Tyler Ross", "VP Marketing")]),
    ],
    "Consulting": [
        (1, "Reception", [("Donna Paulsen", "Executive Assistant"), ("Harold Gunderson", "Concierge")]),
        (2, "Strategy", [("Alexandra Foster", "Strategy Lead"), ("Thomas Wright", "Analyst")]),
        (3, "Operations", [("Jennifer Liu", "Ops Consultant"), ("Brian Kim", "Process Expert")]),
        (4, "Partners", [("Sheldon Cooper", "Senior Partner"), ("Leonard Hofstadter", "Partner")]),
    ],
    "Engineering": [
        (1, "Workshop", [("Tony Stark", "Chief Engineer"), ("Bruce Banner", "R&D Lead")]),
        (2, "Mechanical", [("Hank Pym", "Mechanical Eng"), ("Janet Van Dyne", "Design Eng")]),
        (3, "Electrical", [("Reed Richards", "Electrical Lead"), ("Sue Storm", "Systems Eng")]),
        (4, "Management", [("Nick Fury", "Director"), ("Maria Hill", "Deputy Director")]),
    ],
    "Data Center": [
        (1, "Operations", [("Neo Anderson", "Ops Manager"), ("Trinity", "Senior Ops")]),
        (2, "Infrastructure", [("Morpheus", "Infrastructure Lead"), ("Tank", "Systems Admin")]),
        (3, "Security", [("Agent Smith", "Security Lead"), ("Agent Brown", "Analyst")]),
        (4, "Management", [("The Oracle", "Director"), ("The Architect", "Chief Architect")]),
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


# =============================================================================
# Optimal Path Calculation (for benchmarking efficiency)
# =============================================================================

def compute_optimal_steps_easy(target_floor: int, target_side: Side) -> int:
    """Compute optimal steps for easy mode (single building with front/back).

    Starting position: Floor 1, Front side.

    Actions and their costs:
    - go_up/go_down: 1 step (ends in middle)
    - go_to_front/go_to_back: 1 step
    - deliver_package: 1 step

    Args:
        target_floor: Target floor number (1-3)
        target_side: Target side (FRONT or BACK)

    Returns:
        Minimum number of steps to reach target and deliver
    """
    steps = 0

    # Starting: Floor 1, Front
    current_floor = 1
    current_side = Side.FRONT

    # Move to target floor
    floor_diff = abs(target_floor - current_floor)
    if floor_diff > 0:
        # Each floor change costs 1 step and ends in middle
        steps += floor_diff
        current_side = Side.MIDDLE

    # Move to target side if needed
    if current_side != target_side:
        steps += 1

    # Deliver package
    steps += 1

    return steps


def compute_optimal_steps_medium(target_floor: int, target_building: Side) -> int:
    """Compute optimal steps for medium mode (3 buildings with bridge at floor 3).

    Starting position: Building A, Floor 1.

    Actions and their costs:
    - go_up/go_down: 1 step
    - cross_bridge: 1 step (only on floor 3)
    - go_to_building: 1 step (only on floor 1)
    - deliver_package: 1 step

    Args:
        target_floor: Target floor number (1-4)
        target_building: Target building (BUILDING_A, BUILDING_B, or BUILDING_C)

    Returns:
        Minimum number of steps to reach target and deliver
    """
    steps = 0

    # Starting: Building A, Floor 1
    current_floor = 1
    current_building = Side.BUILDING_A

    # If we need to change buildings, consider two strategies:
    # 1. Go to floor 1 and use ground passage
    # 2. Go to floor 3 and use bridge

    if current_building != target_building:
        # Strategy 1: Ground passage (floor 1)
        steps_ground = abs(current_floor - 1) + 1  # Go to floor 1 + cross ground passage

        # Strategy 2: Bridge (floor 3)
        steps_bridge = abs(current_floor - 3) + 1  # Go to floor 3 + cross bridge

        # Choose the better strategy
        if steps_ground <= steps_bridge:
            # Use ground passage
            steps += abs(current_floor - 1)  # Go to floor 1
            steps += 1  # Cross ground passage
            current_floor = 1
        else:
            # Use bridge
            steps += abs(current_floor - 3)  # Go to floor 3
            steps += 1  # Cross bridge
            current_floor = 3

        current_building = target_building

    # Move to target floor
    steps += abs(target_floor - current_floor)

    # Deliver package
    steps += 1

    return steps


def compute_optimal_steps_hard(target_row: int, target_col: int, target_floor: int) -> int:
    """Compute optimal steps for hard mode (city grid with buildings).

    Starting position: Grid (0, 0), on street in front of Tech Corp.

    Navigation rules:
    - Can only move north/south on roads (odd columns)
    - Can move east/west from any position
    - Buildings are at even columns
    - Must enter building to access floors

    Actions and their costs:
    - move_north/south/east/west: 1 step each
    - enter_building: 1 step (enters at floor 1)
    - go_up/go_down: 1 step
    - deliver_package: 1 step

    Args:
        target_row: Target grid row (0-2)
        target_col: Target grid column (0, 2, 4, or 6 for buildings)
        target_floor: Target floor within the building (1-4)

    Returns:
        Minimum number of steps to reach target and deliver
    """
    steps = 0

    # Starting: Grid (0, 0), on street (in front of Tech Corp at even column 0)
    current_row = 0
    current_col = 0

    # Navigate to target building position
    # Buildings are at even columns: 0, 2, 4, 6
    # Roads are at odd columns: 1, 3, 5

    # Horizontal movement (east/west)
    col_diff = abs(target_col - current_col)
    steps += col_diff
    current_col = target_col

    # Vertical movement (north/south) - must be on a road
    if current_row != target_row:
        # If at a building, move to adjacent road first
        if current_col % 2 == 0:  # At building
            steps += 1  # Move east to road
            current_col += 1

        # Move north/south
        row_diff = abs(target_row - current_row)
        steps += row_diff
        current_row = target_row

        # Move back to building column
        steps += 1  # Move west to building
        current_col = target_col

    # Enter building
    steps += 1

    # Move to target floor (entering puts us at floor 1)
    steps += abs(target_floor - 1)

    # Deliver package
    steps += 1

    return steps


def compute_optimal_steps(building: Building, recipient_name: str) -> int:
    """Compute the optimal number of steps to deliver to a recipient.

    Args:
        building: The building to navigate
        recipient_name: Name of the recipient

    Returns:
        Optimal number of steps, or -1 if recipient not found
    """
    # Find the recipient
    found = building.find_employee(recipient_name)
    if not found:
        return -1

    business, employee = found

    if building.is_city_grid:
        # Hard mode: find building location on grid
        for emp_name, (building_name, biz, emp) in building.city_grid.all_employees.items():
            if emp_name.lower() == recipient_name.lower():
                city_building = building.city_grid.get_building_by_name(building_name)
                if city_building:
                    return compute_optimal_steps_hard(
                        city_building.row,
                        city_building.col,
                        biz.floor
                    )
        return -1

    elif building.is_multi_building:
        # Medium mode
        return compute_optimal_steps_medium(business.floor, business.side)

    else:
        # Easy mode
        return compute_optimal_steps_easy(business.floor, business.side)


def compute_path_efficiency(actual_steps: int, optimal_steps: int) -> float:
    """Compute path efficiency as a ratio.

    Args:
        actual_steps: Number of steps actually taken
        optimal_steps: Optimal number of steps

    Returns:
        Efficiency ratio (1.0 = optimal, lower = worse)
        Returns 0.0 if optimal_steps is 0 or negative
    """
    if optimal_steps <= 0 or actual_steps <= 0:
        return 0.0
    return min(1.0, optimal_steps / actual_steps)


def compute_remaining_steps(
    current_floor: int,
    current_side: Side,
    target_floor: int,
    target_side: Side,
    building: "Building" = None,
    current_building: str = None,
    target_building_name: str = None,
    grid_row: int = 0,
    grid_col: int = 0,
) -> int:
    """Compute optimal remaining steps from current position to target.

    Works for all difficulty modes (easy, medium, hard).

    Returns:
        Minimum steps remaining to reach target and deliver (excluding deliver action)
    """
    # Hard mode (city grid)
    if building and building.is_city_grid and building.city_grid:
        if current_building is None:
            # On street - need to enter building first
            target_bldg = building.city_grid.get_building_by_name(target_building_name)
            if not target_bldg:
                return 999  # Can't find building
            # Manhattan distance to building + enter + floors + side + deliver
            street_dist = abs(grid_row - target_bldg.row) + abs(grid_col - target_bldg.col)
            floor_dist = abs(target_floor - 1)  # Enter at floor 1
            side_dist = 1 if target_side != Side.MIDDLE else 0
            return street_dist + 1 + floor_dist + side_dist  # +1 for enter
        elif current_building != target_building_name:
            # In wrong building - need to exit and navigate
            return 999  # Simplified - would need full pathfinding
        else:
            # In correct building
            floor_dist = abs(target_floor - current_floor)
            side_dist = 0 if current_side == target_side else 1
            if floor_dist > 0 and current_side != Side.MIDDLE:
                side_dist = 1  # Will end in middle after elevator
            return floor_dist + side_dist

    # Medium mode (3 buildings with bridge)
    if building and building.is_multi_building:
        # Simplified - just track floor and side distance
        floor_dist = abs(target_floor - current_floor)
        if current_side != target_side:
            # Need to cross bridge (at floor 3)
            if current_floor != 3:
                floor_dist = abs(3 - current_floor) + abs(target_floor - 3)
            return floor_dist + 1  # +1 for bridge
        return floor_dist

    # Easy mode (single building)
    floor_dist = abs(target_floor - current_floor)
    if floor_dist > 0:
        # After elevator, we're in middle
        side_dist = 0 if target_side == Side.MIDDLE else 1
    else:
        # Same floor - just need to change side if different
        side_dist = 0 if current_side == target_side else 1
    return floor_dist + side_dist
