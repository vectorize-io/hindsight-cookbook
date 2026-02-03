"""
Agent Tools Module

Defines the tools available to the delivery agent for navigating
the building and gathering information.
"""

from typing import Callable
from building import (
    Building, Side, AgentState, get_building,
    CITY_GRID, CITY_GRID_ROWS, CITY_GRID_COLS,
    is_road_cell, is_building_cell, is_intersection, get_adjacent_buildings, get_cell_description
)


class AgentTools:
    """
    Tools available to the delivery agent.
    Each tool returns a string describing the result.
    """

    def __init__(self, building: Building, state: AgentState, on_action: Callable[[str, str], None] = None):
        """
        Initialize agent tools.

        Args:
            building: The building to navigate
            state: The agent's current state
            on_action: Callback function called with (action_name, result) for each action
        """
        self.building = building
        self.state = state
        self.on_action = on_action or (lambda a, r: None)

    def _record_action(self, action: str, result: str) -> str:
        """Record an action and return the result."""
        self.state.steps_taken += 1
        self.on_action(action, result)
        return result

    def go_up(self) -> str:
        """Move up one floor via the elevator."""
        # Hard mode: city grid - must be inside a building
        if self.building.is_city_grid:
            if not self.state.current_building:
                result = "Cannot use elevator on the street. Enter a building first."
                return self._record_action("go_up", result)

            city_building = self.building.city_grid.get_building_by_name(self.state.current_building)
            if not city_building:
                result = "Building not found."
                return self._record_action("go_up", result)

            if self.state.floor >= city_building.max_floor:
                result = f"Cannot go up. Already at the top floor (Floor {self.state.floor})."
                return self._record_action("go_up", result)

            self.state.floor += 1
            floors_remaining = city_building.max_floor - self.state.floor
            business = city_building.get_business(self.state.floor)
            dept_name = business.name if business else "unknown"
            if floors_remaining > 0:
                result = f"Took elevator up to Floor {self.state.floor} in {self.state.current_building}. Now at {dept_name}. You can go up {floors_remaining} more floor(s)."
            else:
                result = f"Took elevator up to Floor {self.state.floor} in {self.state.current_building}. Now at {dept_name}. This is the top floor."
            return self._record_action("go_up", result)

        # Easy/Medium mode
        if self.state.floor >= self.building.max_floor:
            result = f"Cannot go up. Already at the top floor (Floor {self.state.floor})."
            return self._record_action("go_up", result)

        self.state.floor += 1
        floors_remaining_up = self.building.max_floor - self.state.floor
        if self.building.is_multi_building:
            # Multi-building: stay in current building, just change floor
            building_letter = self.state.side.value.replace("building_", "").upper()
            business = self.building.get_business(self.state.floor, self.state.side)
            biz_name = business.name if business else "unknown"
            if floors_remaining_up > 0:
                result = f"Took elevator up to Floor {self.state.floor} in Building {building_letter}. Now at {biz_name}. You can go up {floors_remaining_up} more floor(s)."
            else:
                result = f"Took elevator up to Floor {self.state.floor} in Building {building_letter}. Now at {biz_name}. This is the top floor."
        else:
            self.state.side = Side.MIDDLE  # Elevator deposits in the middle
            if floors_remaining_up > 0:
                result = f"Took elevator up to Floor {self.state.floor}. Now in the middle hallway. You can go up {floors_remaining_up} more floor(s)."
            else:
                result = f"Took elevator up to Floor {self.state.floor}. Now in the middle hallway. This is the top floor."
        return self._record_action("go_up", result)

    def go_down(self) -> str:
        """Move down one floor via the elevator."""
        # Hard mode: city grid - must be inside a building
        if self.building.is_city_grid:
            if not self.state.current_building:
                result = "Cannot use elevator on the street. Enter a building first."
                return self._record_action("go_down", result)

            city_building = self.building.city_grid.get_building_by_name(self.state.current_building)
            if not city_building:
                result = "Building not found."
                return self._record_action("go_down", result)

            if self.state.floor <= city_building.min_floor:
                result = f"Cannot go down. Already at the ground floor (Floor {self.state.floor})."
                return self._record_action("go_down", result)

            self.state.floor -= 1
            floors_remaining = self.state.floor - city_building.min_floor
            business = city_building.get_business(self.state.floor)
            dept_name = business.name if business else "unknown"
            if floors_remaining > 0:
                result = f"Took elevator down to Floor {self.state.floor} in {self.state.current_building}. Now at {dept_name}. You can go down {floors_remaining} more floor(s)."
            else:
                result = f"Took elevator down to Floor {self.state.floor} in {self.state.current_building}. Now at {dept_name}. This is the ground floor."
            return self._record_action("go_down", result)

        # Easy/Medium mode
        if self.state.floor <= self.building.min_floor:
            result = f"Cannot go down. Already at the bottom floor (Floor {self.state.floor})."
            return self._record_action("go_down", result)

        self.state.floor -= 1
        floors_remaining_down = self.state.floor - self.building.min_floor
        if self.building.is_multi_building:
            # Multi-building: stay in current building, just change floor
            building_letter = self.state.side.value.replace("building_", "").upper()
            business = self.building.get_business(self.state.floor, self.state.side)
            biz_name = business.name if business else "unknown"
            if floors_remaining_down > 0:
                result = f"Took elevator down to Floor {self.state.floor} in Building {building_letter}. Now at {biz_name}. You can go down {floors_remaining_down} more floor(s)."
            else:
                result = f"Took elevator down to Floor {self.state.floor} in Building {building_letter}. Now at {biz_name}. This is the ground floor."
        else:
            self.state.side = Side.MIDDLE  # Elevator deposits in the middle
            if floors_remaining_down > 0:
                result = f"Took elevator down to Floor {self.state.floor}. Now in the middle hallway. You can go down {floors_remaining_down} more floor(s)."
            else:
                result = f"Took elevator down to Floor {self.state.floor}. Now in the middle hallway. This is the ground floor."
        return self._record_action("go_down", result)

    def go_to_front(self) -> str:
        """Walk to the front side of the current floor to reach the front business."""
        if self.state.side == Side.FRONT:
            result = "Already at the front side of this floor."
            return self._record_action("go_to_front", result)

        self.state.side = Side.FRONT
        business = self.building.get_business(self.state.floor, Side.FRONT)
        if not business:
            # This should never happen - every floor has front/back businesses
            raise ValueError(f"No business found at Floor {self.state.floor}, Front. Building floors: {list(self.building.floors.keys())}")
        result = f"Walked to the front side of Floor {self.state.floor}. Now at {business.name}."
        return self._record_action("go_to_front", result)

    def go_to_back(self) -> str:
        """Walk to the back side of the current floor to reach the back business."""
        if self.state.side == Side.BACK:
            result = "Already at the back side of this floor."
            return self._record_action("go_to_back", result)

        self.state.side = Side.BACK
        business = self.building.get_business(self.state.floor, Side.BACK)
        if not business:
            # This should never happen - every floor has front/back businesses
            raise ValueError(f"No business found at Floor {self.state.floor}, Back. Building floors: {list(self.building.floors.keys())}")
        result = f"Walked to the back side of Floor {self.state.floor}. Now at {business.name}."
        return self._record_action("go_to_back", result)

    # Medium difficulty tools - 3 building navigation

    def cross_bridge(self, target_building: str) -> str:
        """Cross the bridge to another building. Only works on Floor 3."""
        if self.state.floor != 3:
            result = f"Cannot cross bridge. The bridge is only on Floor 3. You are on Floor {self.state.floor}."
            return self._record_action("cross_bridge", result)

        target_map = {
            "a": Side.BUILDING_A,
            "b": Side.BUILDING_B,
            "c": Side.BUILDING_C,
            "building_a": Side.BUILDING_A,
            "building_b": Side.BUILDING_B,
            "building_c": Side.BUILDING_C,
        }
        target_side = target_map.get(target_building.lower())
        if not target_side:
            result = f"Invalid building: {target_building}. Choose A, B, or C."
            return self._record_action("cross_bridge", result)

        if self.state.side == target_side:
            result = f"Already in Building {target_building.upper()}."
            return self._record_action("cross_bridge", result)

        self.state.side = target_side
        business = self.building.get_business(self.state.floor, target_side)
        biz_name = business.name if business else "unknown"
        result = f"Crossed the bridge to Building {target_building.upper()}. Now at {biz_name} on Floor 3."
        return self._record_action("cross_bridge", result)

    def go_to_building(self, target_building: str) -> str:
        """Walk through the ground passage to another building. Only works on Floor 1."""
        if self.state.floor != 1:
            result = f"Cannot use ground passage. The passage is only on Floor 1 (ground floor). You are on Floor {self.state.floor}."
            return self._record_action("go_to_building", result)

        target_map = {
            "a": Side.BUILDING_A,
            "b": Side.BUILDING_B,
            "c": Side.BUILDING_C,
            "building_a": Side.BUILDING_A,
            "building_b": Side.BUILDING_B,
            "building_c": Side.BUILDING_C,
        }
        target_side = target_map.get(target_building.lower())
        if not target_side:
            result = f"Invalid building: {target_building}. Choose A, B, or C."
            return self._record_action("go_to_building", result)

        if self.state.side == target_side:
            result = f"Already in Building {target_building.upper()}."
            return self._record_action("go_to_building", result)

        self.state.side = target_side
        business = self.building.get_business(self.state.floor, target_side)
        biz_name = business.name if business else "unknown"
        result = f"Walked through ground passage to Building {target_building.upper()}. Now at {biz_name} on Floor 1."
        return self._record_action("go_to_building", result)

    # Hard mode tools - road-based city grid navigation
    # Agent moves on roads between buildings, not directly to buildings

    def _get_surroundings(self) -> str:
        """Get a description of what's in each direction from current position."""
        row, col = self.state.grid_row, self.state.grid_col
        directions = []

        # North
        if row > 0:
            directions.append(f"North: {get_cell_description(row - 1, col)}")
        else:
            directions.append("North: edge")

        # South
        if row < CITY_GRID_ROWS - 1:
            directions.append(f"South: {get_cell_description(row + 1, col)}")
        else:
            directions.append("South: edge")

        # East
        if col < CITY_GRID_COLS - 1:
            directions.append(f"East: {get_cell_description(row, col + 1)}")
        else:
            directions.append("East: edge")

        # West
        if col > 0:
            directions.append(f"West: {get_cell_description(row, col - 1)}")
        else:
            directions.append("West: edge")

        return " | ".join(directions)

    def _get_current_location_desc(self) -> str:
        """Get description of current location."""
        row, col = self.state.grid_row, self.state.grid_col
        if is_building_cell(row, col):
            building_name = CITY_GRID.get((row, col), "Unknown")
            return f"in front of {building_name}"
        else:
            return "on road"

    def move_north(self) -> str:
        """Move north on the city grid (toward row 0). Only works from road positions."""
        if self.state.current_building:
            result = f"Cannot move while inside {self.state.current_building}. Exit the building first."
            return self._record_action("move_north", result)

        # Can only move north/south from road positions (odd columns)
        if is_building_cell(self.state.grid_row, self.state.grid_col):
            building_name = CITY_GRID.get((self.state.grid_row, self.state.grid_col), "building")
            result = f"Cannot move north from {building_name}. Move east or west to the road first."
            return self._record_action("move_north", result)

        if self.state.grid_row <= 0:
            result = "Cannot move north. Already at the northern edge of the city."
            return self._record_action("move_north", result)

        self.state.grid_row -= 1
        result = f"Moved north. Now {self._get_current_location_desc()} at ({self.state.grid_row}, {self.state.grid_col}). {self._get_surroundings()}"
        return self._record_action("move_north", result)

    def move_south(self) -> str:
        """Move south on the city grid (toward higher rows). Only works from road positions."""
        if self.state.current_building:
            result = f"Cannot move while inside {self.state.current_building}. Exit the building first."
            return self._record_action("move_south", result)

        # Can only move north/south from road positions (odd columns)
        if is_building_cell(self.state.grid_row, self.state.grid_col):
            building_name = CITY_GRID.get((self.state.grid_row, self.state.grid_col), "building")
            result = f"Cannot move south from {building_name}. Move east or west to the road first."
            return self._record_action("move_south", result)

        if self.state.grid_row >= CITY_GRID_ROWS - 1:
            result = "Cannot move south. Already at the southern edge of the city."
            return self._record_action("move_south", result)

        self.state.grid_row += 1
        result = f"Moved south. Now {self._get_current_location_desc()} at ({self.state.grid_row}, {self.state.grid_col}). {self._get_surroundings()}"
        return self._record_action("move_south", result)

    def move_east(self) -> str:
        """Move east on the city grid (toward higher columns)."""
        if self.state.current_building:
            result = f"Cannot move while inside {self.state.current_building}. Exit the building first."
            return self._record_action("move_east", result)

        if self.state.grid_col >= CITY_GRID_COLS - 1:
            result = "Cannot move east. Already at the eastern edge of the city."
            return self._record_action("move_east", result)

        self.state.grid_col += 1
        result = f"Moved east. Now {self._get_current_location_desc()} at ({self.state.grid_row}, {self.state.grid_col}). {self._get_surroundings()}"
        return self._record_action("move_east", result)

    def move_west(self) -> str:
        """Move west on the city grid (toward column 0)."""
        if self.state.current_building:
            result = f"Cannot move while inside {self.state.current_building}. Exit the building first."
            return self._record_action("move_west", result)

        if self.state.grid_col <= 0:
            result = "Cannot move west. Already at the western edge of the city."
            return self._record_action("move_west", result)

        self.state.grid_col -= 1
        result = f"Moved west. Now {self._get_current_location_desc()} at ({self.state.grid_row}, {self.state.grid_col}). {self._get_surroundings()}"
        return self._record_action("move_west", result)

    def enter_building(self) -> str:
        """Enter the building you are standing in front of."""
        if self.state.current_building:
            result = f"Already inside {self.state.current_building}. Exit first to enter a different building."
            return self._record_action("enter_building", result)

        row, col = self.state.grid_row, self.state.grid_col

        # Must be at a building position (even column) to enter
        if not is_building_cell(row, col):
            result = f"Not in front of a building. Move to a building first (even column positions). {self._get_surroundings()}"
            return self._record_action("enter_building", result)

        building_name = CITY_GRID.get((row, col))
        if not building_name:
            result = "No building found at this position."
            return self._record_action("enter_building", result)

        self.state.current_building = building_name
        self.state.floor = 1
        self.state.side = Side.INSIDE

        # Get the business on floor 1
        city_building = self.building.city_grid.get_building_by_name(building_name)
        if city_building:
            business = city_building.get_business(1)
            dept_name = business.name if business else "Lobby"
        else:
            dept_name = "Lobby"

        result = f"Entered {building_name}. Now on Floor 1 at {dept_name}. This building has 4 floors."
        return self._record_action("enter_building", result)

    def exit_building(self) -> str:
        """Exit the current building back to the street."""
        if not self.state.current_building:
            result = "Not inside any building. Already on the street."
            return self._record_action("exit_building", result)

        building_name = self.state.current_building
        self.state.current_building = None
        self.state.floor = 1
        self.state.side = Side.STREET

        result = f"Exited {building_name}. Now {self._get_current_location_desc()} at ({self.state.grid_row}, {self.state.grid_col}). {self._get_surroundings()}"
        return self._record_action("exit_building", result)

    def get_employee_list(self) -> str:
        """Get the list of employees at the current business."""
        # Hard mode: city grid
        if self.building.is_city_grid:
            if not self.state.current_building:
                result = "You're on the street. Enter a building to see employees."
                return self._record_action("get_employee_list", result)

            city_building = self.building.city_grid.get_building_by_name(self.state.current_building)
            if not city_building:
                result = "Building not found."
                return self._record_action("get_employee_list", result)

            business = city_building.get_business(self.state.floor)
            if not business or not business.employees:
                result = f"No employees listed on Floor {self.state.floor}."
                return self._record_action("get_employee_list", result)

            employee_list = "\n".join([
                f"  - {emp.name} ({emp.role})"
                for emp in business.employees
            ])
            result = f"Employees at {business.name} (Floor {self.state.floor}, {self.state.current_building}):\n{employee_list}"
            return self._record_action("get_employee_list", result)

        # Easy/Medium mode
        if self.state.side == Side.MIDDLE:
            if self.building.is_multi_building:
                result = "You're in the elevator area. Go to a building to see employees."
            else:
                result = "You're in the middle hallway. Go to the front or back side to see employees."
            return self._record_action("get_employee_list", result)

        business = self.building.get_business(self.state.floor, self.state.side)
        if not business:
            result = "No business at this location."
            return self._record_action("get_employee_list", result)

        if not business.employees:
            result = f"{business.name} has no employees listed."
            return self._record_action("get_employee_list", result)

        employee_list = "\n".join([
            f"  - {emp.name} ({emp.role})"
            for emp in business.employees
        ])
        result = f"Employees at {business.name}:\n{employee_list}"
        return self._record_action("get_employee_list", result)

    def deliver_package(self, recipient_name: str) -> str:
        """
        Attempt to deliver the package to the recipient at the current location.

        Args:
            recipient_name: Name of the person to deliver to
        """
        if not self.state.current_package:
            result = "No package to deliver."
            return self._record_action("deliver_package", result)

        pkg = self.state.current_package

        # Verify the agent is delivering to the correct recipient (the one on the package)
        if recipient_name.lower() != pkg.recipient_name.lower():
            result = f"FAILED: Package is addressed to {pkg.recipient_name}, not {recipient_name}. Check the package details."
            return self._record_action("deliver_package", result)

        # Hard mode: city grid
        if self.building.is_city_grid:
            if not self.state.current_building:
                result = "FAILED: You're on the street. Enter a building to deliver."
                return self._record_action("deliver_package", result)

            city_building = self.building.city_grid.get_building_by_name(self.state.current_building)
            if not city_building:
                result = "FAILED: Building not found."
                return self._record_action("deliver_package", result)

            business = city_building.get_business(self.state.floor)
            if not business:
                result = "FAILED: No business at this location to deliver to."
                return self._record_action("deliver_package", result)

            recipient_found = any(
                emp.name.lower() == recipient_name.lower()
                for emp in business.employees
            )

            if recipient_found:
                self.state.packages_delivered += 1
                self.state.current_package = None
                result = f"SUCCESS! Package #{pkg.id} delivered to {recipient_name} at {business.name} in {self.state.current_building}!"
                return self._record_action("deliver_package", result)
            else:
                result = f"FAILED: {recipient_name} does not work at {business.name}. Try another floor or building."
                return self._record_action("deliver_package", result)

        # Easy/Medium mode
        if self.state.side == Side.MIDDLE:
            if self.building.is_multi_building:
                result = "FAILED: You're in the elevator area. Go to a building to deliver."
            else:
                result = "FAILED: You're in the middle hallway. Go to the front or back side to deliver."
            return self._record_action("deliver_package", result)

        business = self.building.get_business(self.state.floor, self.state.side)
        if not business:
            result = "No business at this location to deliver to."
            return self._record_action("deliver_package", result)

        # Check if the correct recipient works here
        recipient_found = any(
            emp.name.lower() == recipient_name.lower()
            for emp in business.employees
        )

        if recipient_found:
            self.state.packages_delivered += 1
            self.state.current_package = None
            result = f"SUCCESS! Package #{pkg.id} delivered to {recipient_name} at {business.name}!"
            return self._record_action("deliver_package", result)
        else:
            result = f"FAILED: {recipient_name} does not work at {business.name}. Try another location."
            return self._record_action("deliver_package", result)

    def check_current_location(self) -> str:
        """Check the agent's current location in the building."""
        # Hard mode: city grid
        if self.building.is_city_grid:
            if self.state.current_building:
                city_building = self.building.city_grid.get_building_by_name(self.state.current_building)
                if city_building:
                    business = city_building.get_business(self.state.floor)
                    dept_name = business.name if business else "unknown"
                    floors_up = city_building.max_floor - self.state.floor
                    floors_down = self.state.floor - city_building.min_floor
                    result = f"Current location: Inside {self.state.current_building}, Floor {self.state.floor}, at {dept_name}. Can go up {floors_up} floor(s), down {floors_down} floor(s)."
                else:
                    result = f"Current location: Inside {self.state.current_building}, Floor {self.state.floor}"
            else:
                result = f"Current location: {self._get_current_location_desc()} at ({self.state.grid_row}, {self.state.grid_col}). {self._get_surroundings()}"
            return self._record_action("check_current_location", result)

        # Easy/Medium mode
        if self.state.side == Side.MIDDLE:
            if self.building.is_multi_building:
                result = f"Current location: Floor {self.state.floor}, elevator area."
            else:
                result = f"Current location: Floor {self.state.floor}, middle hallway."
        elif self.building.is_multi_building:
            # Multi-building mode - show building name
            building_name = {
                Side.BUILDING_A: "Building A",
                Side.BUILDING_B: "Building B",
                Side.BUILDING_C: "Building C",
            }.get(self.state.side, "Unknown Building")
            business = self.building.get_business(self.state.floor, self.state.side)
            biz_name = business.name if business else "unknown"
            result = f"Current location: {building_name}, Floor {self.state.floor}, at {biz_name}"
        else:
            business = self.building.get_business(self.state.floor, self.state.side)
            biz_name = business.name if business else "unknown"
            result = f"Current location: Floor {self.state.floor} on the {self.state.side.value} side at business: {biz_name}"
        return self._record_action("check_current_location", result)


# Common tool definitions (used by all difficulties)
_COMMON_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "go_up",
            "description": "Move up one floor in the building.",
            "parameters": {"type": "object", "properties": {}, "required": []}
        }
    },
    {
        "type": "function",
        "function": {
            "name": "go_down",
            "description": "Move down one floor in the building.",
            "parameters": {"type": "object", "properties": {}, "required": []}
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_employee_list",
            "description": "Get the list of employees at your current location.",
            "parameters": {"type": "object", "properties": {}, "required": []}
        }
    },
    {
        "type": "function",
        "function": {
            "name": "deliver_package",
            "description": "Attempt to deliver the package to the specified recipient at your current location.",
            "parameters": {
                "type": "object",
                "properties": {
                    "recipient_name": {
                        "type": "string",
                        "description": "The name of the person to deliver the package to"
                    }
                },
                "required": ["recipient_name"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "check_current_location",
            "description": "Check your current location in the building.",
            "parameters": {"type": "object", "properties": {}, "required": []}
        }
    }
]

# Easy mode tools - front/back navigation
_EASY_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "go_to_front",
            "description": "Go to the front side of the current floor.",
            "parameters": {"type": "object", "properties": {}, "required": []}
        }
    },
    {
        "type": "function",
        "function": {
            "name": "go_to_back",
            "description": "Go to the back side of the current floor.",
            "parameters": {"type": "object", "properties": {}, "required": []}
        }
    },
]

# Medium mode tools - 3 building navigation with bridge and ground passage
_MEDIUM_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "cross_bridge",
            "description": "Cross the bridge to another building. Only works on Floor 3.",
            "parameters": {
                "type": "object",
                "properties": {
                    "target_building": {
                        "type": "string",
                        "description": "The building to go to: A, B, or C"
                    }
                },
                "required": ["target_building"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "go_to_building",
            "description": "Walk through the ground passage to another building. Only works on Floor 1 (ground floor).",
            "parameters": {
                "type": "object",
                "properties": {
                    "target_building": {
                        "type": "string",
                        "description": "The building to go to: A, B, or C"
                    }
                },
                "required": ["target_building"]
            }
        }
    },
]

# Hard mode tools - city grid navigation
_HARD_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "move_north",
            "description": "Move north to the adjacent row (toward row 0).",
            "parameters": {"type": "object", "properties": {}, "required": []}
        }
    },
    {
        "type": "function",
        "function": {
            "name": "move_south",
            "description": "Move south to the adjacent row (toward row 2).",
            "parameters": {"type": "object", "properties": {}, "required": []}
        }
    },
    {
        "type": "function",
        "function": {
            "name": "move_east",
            "description": "Move east to the adjacent column. Buildings at even columns, roads at odd columns.",
            "parameters": {"type": "object", "properties": {}, "required": []}
        }
    },
    {
        "type": "function",
        "function": {
            "name": "move_west",
            "description": "Move west to the adjacent column. Buildings at even columns, roads at odd columns.",
            "parameters": {"type": "object", "properties": {}, "required": []}
        }
    },
    {
        "type": "function",
        "function": {
            "name": "enter_building",
            "description": "Enter the building you are standing in front of. Must be at a building position (even column).",
            "parameters": {"type": "object", "properties": {}, "required": []}
        }
    },
    {
        "type": "function",
        "function": {
            "name": "exit_building",
            "description": "Exit the current building and return to the street.",
            "parameters": {"type": "object", "properties": {}, "required": []}
        }
    },
]

# Tool definitions for LLM function calling - legacy (easy mode)
TOOL_DEFINITIONS = _COMMON_TOOLS + _EASY_TOOLS


def get_tool_definitions(difficulty: str = "easy") -> list:
    """Get the tool definitions for a specific difficulty level."""
    if difficulty == "medium":
        return _COMMON_TOOLS + _MEDIUM_TOOLS
    if difficulty == "hard":
        return _COMMON_TOOLS + _HARD_TOOLS
    # Easy uses front/back navigation
    return _COMMON_TOOLS + _EASY_TOOLS


def execute_tool(tools: AgentTools, tool_name: str, arguments: dict) -> str:
    """Execute a tool by name with the given arguments."""
    # Direct dispatch - faster than dict creation on every call
    if tool_name == "go_up":
        return tools.go_up()
    elif tool_name == "go_down":
        return tools.go_down()
    elif tool_name == "go_to_front":
        return tools.go_to_front()
    elif tool_name == "go_to_back":
        return tools.go_to_back()
    elif tool_name == "cross_bridge":
        return tools.cross_bridge(arguments.get("target_building", ""))
    elif tool_name == "go_to_building":
        return tools.go_to_building(arguments.get("target_building", ""))
    elif tool_name == "get_employee_list":
        return tools.get_employee_list()
    elif tool_name == "deliver_package":
        return tools.deliver_package(arguments.get("recipient_name", ""))
    elif tool_name == "check_current_location":
        return tools.check_current_location()
    # Hard mode tools
    elif tool_name == "move_north":
        return tools.move_north()
    elif tool_name == "move_south":
        return tools.move_south()
    elif tool_name == "move_east":
        return tools.move_east()
    elif tool_name == "move_west":
        return tools.move_west()
    elif tool_name == "enter_building":
        return tools.enter_building()
    elif tool_name == "exit_building":
        return tools.exit_building()
    else:
        return f"Unknown tool: {tool_name}"


# =============================================================================
# Benchmark Mode Tools (memory and filesystem)
# =============================================================================

# Memory tools - for per-step memory queries (Hindsight modes)
_MEMORY_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "remember",
            "description": "Query your memory for relevant information about the building, employees, or past deliveries. "
                          "Use this to recall where employees work, building layout, or lessons from previous deliveries. "
                          "This does NOT count against your step limit.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "What to search for in memory (e.g., 'Where does Alice work?', 'What is on floor 3?')"
                    }
                },
                "required": ["query"]
            }
        }
    },
]

# Filesystem tools - for filesystem agent mode (read only, writing is controlled by the system)
_FILESYSTEM_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "read_notes",
            "description": "Read your personal notes file to recall information from previous deliveries. "
                          "Returns the full contents of your notes. This does NOT count against your step limit.",
            "parameters": {"type": "object", "properties": {}, "required": []}
        }
    },
]


def get_tool_definitions_with_memory(
    difficulty: str = "easy",
    include_memory: bool = False,
    include_filesystem: bool = False,
) -> list:
    """Get tool definitions with optional memory/filesystem tools.

    Args:
        difficulty: Building difficulty level
        include_memory: Include 'remember' tool for per-step memory queries
        include_filesystem: Include 'read_notes' tool for filesystem mode

    Returns:
        List of tool definitions
    """
    base_tools = get_tool_definitions(difficulty)

    if include_memory:
        base_tools = base_tools + _MEMORY_TOOLS

    if include_filesystem:
        base_tools = base_tools + _FILESYSTEM_TOOLS

    return base_tools


class MemoryToolHandler:
    """Handles memory tool calls (remember, read_notes).

    These tools don't count against the step limit and are executed
    outside the normal tool execution flow. Note: write_notes is controlled
    by the system, not the agent.
    """

    # Class-level storage for filesystem mode notes (keyed by bank_id or session)
    _notes_storage: dict[str, str] = {}

    def __init__(self, recall_fn=None, notes_key: str = "default"):
        """Initialize the memory tool handler.

        Args:
            recall_fn: Async function to call for memory recall (takes query string, returns context)
            notes_key: Key for filesystem notes storage (e.g., bank_id)
        """
        self.recall_fn = recall_fn
        self.notes_key = notes_key
        self.query_count = 0

    async def execute(self, tool_name: str, arguments: dict) -> tuple[str, bool]:
        """Execute a memory tool.

        Args:
            tool_name: Name of the tool
            arguments: Tool arguments

        Returns:
            Tuple of (result string, is_memory_tool)
            - result: Tool execution result
            - is_memory_tool: True if this was a memory tool (doesn't count as step)
        """
        if tool_name == "remember":
            query = arguments.get("query", "")
            if not query:
                return "Please provide a query to search memory.", True

            self.query_count += 1

            if self.recall_fn:
                try:
                    result = await self.recall_fn(query)
                    if result:
                        return f"Memory recall:\n{result}", True
                    else:
                        return "No relevant memories found.", True
                except Exception as e:
                    return f"Error querying memory: {e}", True
            else:
                return "Memory not available in this mode.", True

        elif tool_name == "read_notes":
            notes = self._notes_storage.get(self.notes_key, "")
            if notes:
                return f"Your notes:\n{notes}", True
            else:
                return "Your notes file is empty. Use write_notes to save information.", True

        elif tool_name == "write_notes":
            content = arguments.get("content", "")
            self._notes_storage[self.notes_key] = content
            return f"Notes saved ({len(content)} characters).", True

        return "", False  # Not a memory tool

    @classmethod
    def clear_notes(cls, notes_key: str = None):
        """Clear notes storage.

        Args:
            notes_key: Specific key to clear, or None to clear all
        """
        if notes_key:
            cls._notes_storage.pop(notes_key, None)
        else:
            cls._notes_storage.clear()

    @classmethod
    def get_notes(cls, notes_key: str) -> str:
        """Get notes for a key."""
        return cls._notes_storage.get(notes_key, "")
