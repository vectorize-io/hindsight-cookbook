"""Building API endpoints."""

from fastapi import APIRouter
import sys
sys.path.insert(0, str(__file__).rsplit("/app/", 1)[0])

from building import get_building, Side

router = APIRouter(prefix="/api/building", tags=["building"])


@router.get("")
async def get_building_info():
    """Get building information."""
    building = get_building()
    businesses = []

    # Hard mode: return city grid data
    if building.is_city_grid and building.city_grid:
        city_buildings = []
        for building_name, city_building in building.city_grid.buildings.items():
            floors_data = []
            for floor_num in sorted(city_building.floors.keys()):
                biz = city_building.floors[floor_num]
                floors_data.append({
                    "floor": floor_num,
                    "name": biz.name,
                    "employees": [{"name": e.name, "role": e.role} for e in biz.employees]
                })
            city_buildings.append({
                "name": building_name,
                "row": city_building.row,
                "col": city_building.col,
                "floors": floors_data
            })
        # Sort by row then col for consistent display
        city_buildings.sort(key=lambda b: (b["row"], b["col"]))

        return {
            "floors": 4,  # All city buildings have 4 floors
            "businesses": [],  # Empty for hard mode
            "isMultiBuilding": False,
            "isCityGrid": True,
            "difficulty": building.difficulty,
            "cityBuildings": city_buildings,
            "gridRows": building.city_grid.rows,
            "gridCols": building.city_grid.cols,
        }

    # Easy/Medium mode
    for floor_num in sorted(building.floors.keys()):
        for side in building.available_positions:
            biz = building.get_business(floor_num, side)
            if biz:
                businesses.append({
                    "name": biz.name,
                    "floor": biz.floor,
                    "side": biz.side.value,
                    "employees": [{"name": e.name, "role": e.role} for e in biz.employees]
                })

    return {
        "floors": building.num_floors,
        "businesses": businesses,
        "isMultiBuilding": building.is_multi_building,
        "difficulty": building.difficulty,
    }


@router.get("/employees")
async def get_employees():
    """Get all employees for recipient selection."""
    building = get_building()
    employees = []

    # For hard mode (city grid), include building name
    if building.is_city_grid and building.city_grid:
        for emp_name, (building_name, business, employee) in building.city_grid.all_employees.items():
            # Hard mode: agent starts on street, no starting location to exclude
            employees.append({
                "name": employee.name,
                "role": employee.role,
                "business": business.name,
                "floor": business.floor,
                "side": business.side.value,
                "building": building_name
            })
        # Sort by building then floor (desc) then business name
        employees.sort(key=lambda e: (e["building"], -e["floor"], e["business"], e["name"]))
    else:
        for emp_name, (business, employee) in building.all_employees.items():
            employees.append({
                "name": employee.name,
                "role": employee.role,
                "business": business.name,
                "floor": business.floor,
                "side": business.side.value,
                "building": None
            })
        # Sort by floor (desc) then business name
        employees.sort(key=lambda e: (-e["floor"], e["business"], e["name"]))

    return {"employees": employees}
