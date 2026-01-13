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

    for emp_name, (business, employee) in building.all_employees.items():
        employees.append({
            "name": employee.name,
            "role": employee.role,
            "business": business.name,
            "floor": business.floor,
            "side": business.side.value
        })

    # Sort by floor (desc) then business name
    employees.sort(key=lambda e: (-e["floor"], e["business"], e["name"]))

    return {"employees": employees}
