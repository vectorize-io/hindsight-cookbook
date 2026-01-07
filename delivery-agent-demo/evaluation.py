"""
Evaluation Framework for Hindsight Memory System

This module provides tools for running systematic evaluations of the delivery agent
with different Hindsight memory configurations.
"""

import json
import os
import time
from dataclasses import dataclass, field, asdict
from datetime import datetime
from typing import Optional, Any
from enum import Enum

from building import Building, Side, Package


class EvalConfig(Enum):
    """Evaluation configurations for Hindsight settings."""
    BASELINE = "baseline"           # No memory injection
    RECALL_LOW = "recall-low"       # Recall with low budget
    RECALL_MID = "recall-mid"       # Recall with mid budget (default)
    RECALL_HIGH = "recall-high"     # Recall with high budget
    REFLECT_LOW = "reflect-low"     # Reflect with low budget
    REFLECT_MID = "reflect-mid"     # Reflect with mid budget
    REFLECT_HIGH = "reflect-high"   # Reflect with high budget


# Map config to hindsight settings
EVAL_CONFIG_SETTINGS = {
    EvalConfig.BASELINE: {
        "inject_memories": False,
        "use_reflect": False,
        "recall_budget": "mid",
    },
    EvalConfig.RECALL_LOW: {
        "inject_memories": True,
        "use_reflect": False,
        "recall_budget": "low",
    },
    EvalConfig.RECALL_MID: {
        "inject_memories": True,
        "use_reflect": False,
        "recall_budget": "mid",
    },
    EvalConfig.RECALL_HIGH: {
        "inject_memories": True,
        "use_reflect": False,
        "recall_budget": "high",
    },
    EvalConfig.REFLECT_LOW: {
        "inject_memories": True,
        "use_reflect": True,
        "recall_budget": "low",
    },
    EvalConfig.REFLECT_MID: {
        "inject_memories": True,
        "use_reflect": True,
        "recall_budget": "mid",
    },
    EvalConfig.REFLECT_HIGH: {
        "inject_memories": True,
        "use_reflect": True,
        "recall_budget": "high",
    },
}


@dataclass
class StepData:
    """Data captured for a single step in a delivery."""
    step_number: int
    tool_calls: list[dict]  # [{name, args, result}]
    llm_time_ms: float
    memory_injection: Optional[dict] = None  # {mode, count, memories, relevant}
    llm_response_content: Optional[str] = None
    action_correct: Optional[bool] = None
    error_type: Optional[str] = None  # wrong_direction, wrong_side, unnecessary_step, etc.


@dataclass
class DeliveryData:
    """Data captured for a single delivery attempt."""
    delivery_id: int
    package: dict  # {recipient, business, floor, side}
    optimal_steps: int
    success: bool
    actual_steps: int
    total_time_ms: float
    llm_time_ms: float
    steps: list[StepData] = field(default_factory=list)
    failure_reason: Optional[str] = None
    memories_injected_total: int = 0
    relevant_memories_count: int = 0


@dataclass
class EvalRunSummary:
    """Summary statistics for an evaluation run."""
    config_name: str
    total_deliveries: int
    successful_deliveries: int
    success_rate: float
    avg_steps: float
    avg_optimal_steps: float
    step_efficiency: float  # optimal / actual
    avg_llm_time_ms: float
    total_time_seconds: float

    # Error breakdown
    error_counts: dict = field(default_factory=dict)

    # Memory effectiveness
    memory_stats: dict = field(default_factory=dict)

    # Learning curve (success rate in batches)
    learning_curve: list[dict] = field(default_factory=list)


def compute_optimal_path(building: Building, package: Package, start_floor: int = 1, start_side: Side = Side.FRONT) -> dict:
    """
    Compute the optimal path to deliver a package.

    Returns dict with:
        - target_floor: int
        - target_side: Side
        - optimal_steps: int (number of tool calls needed)
        - optimal_actions: list of action names
    """
    # Find the employee's location
    emp_info = building.find_employee(package.recipient_name)
    if not emp_info:
        return {"error": f"Employee {package.recipient_name} not found"}

    business, employee = emp_info
    target_floor = business.floor
    target_side = business.side

    actions = []
    current_floor = start_floor
    current_side = start_side

    # First, go to correct floor
    while current_floor != target_floor:
        if current_floor < target_floor:
            actions.append("go_up")
            current_floor += 1
        else:
            actions.append("go_down")
            current_floor -= 1

    # Then, go to correct side if needed
    if current_side != target_side:
        if target_side == Side.FRONT:
            actions.append("go_front")
        else:
            actions.append("go_back")
        current_side = target_side

    # Finally, deliver
    actions.append("deliver_package")

    return {
        "target_floor": target_floor,
        "target_side": target_side,
        "optimal_steps": len(actions),
        "optimal_actions": actions,
    }


def categorize_error(
    action: str,
    current_floor: int,
    current_side: Side,
    target_floor: int,
    target_side: Side,
    delivery_success: bool,
) -> Optional[str]:
    """
    Categorize an error based on the action taken vs optimal action.

    Returns error type string or None if action was correct.
    """
    # Check if going wrong vertical direction
    if action == "go_up":
        if current_floor >= target_floor:
            return "wrong_direction_up"
        return None  # Correct

    if action == "go_down":
        if current_floor <= target_floor:
            return "wrong_direction_down"
        return None  # Correct

    # Check if going wrong horizontal direction
    if action == "go_front":
        if current_side == Side.FRONT:
            return "unnecessary_move"
        if target_side != Side.FRONT and current_floor == target_floor:
            return "wrong_side"
        return None

    if action == "go_back":
        if current_side == Side.BACK:
            return "unnecessary_move"
        if target_side != Side.BACK and current_floor == target_floor:
            return "wrong_side"
        return None

    # Delivery attempt
    if action == "deliver_package":
        if not delivery_success:
            if current_floor != target_floor:
                return "deliver_wrong_floor"
            if current_side != target_side:
                return "deliver_wrong_side"
            return "deliver_failed_other"
        return None  # Success

    # Info gathering actions (not errors, but track if excessive)
    if action in ["check_current_location", "get_employee_list", "get_nearby_businesses"]:
        return None  # These are informational, not errors per se

    return "unknown_action"


def check_memory_relevance(
    memories: list[str],
    target_employee: str,
    target_floor: int,
    target_side: Side,
    target_business: Optional[str] = None,
) -> dict:
    """
    Check if injected memories are relevant to the current delivery.

    Returns dict with:
        - relevant_count: number of relevant memories
        - relevant_memories: list of relevant memory texts
        - relevance_types: what info was relevant (employee, floor, side, business)
    """
    relevant = []
    relevance_types = set()

    target_employee_lower = target_employee.lower()
    target_business_lower = target_business.lower() if target_business else ""
    target_side_str = target_side.value.lower()

    for mem in memories:
        mem_lower = mem.lower()
        is_relevant = False

        # Check if memory mentions the target employee
        if target_employee_lower in mem_lower:
            is_relevant = True
            relevance_types.add("employee")

        # Check if memory mentions the target floor
        if f"floor {target_floor}" in mem_lower:
            is_relevant = True
            relevance_types.add("floor")

        # Check if memory mentions the target side
        if target_side_str in mem_lower:
            is_relevant = True
            relevance_types.add("side")

        # Check if memory mentions the business
        if target_business_lower and target_business_lower in mem_lower:
            is_relevant = True
            relevance_types.add("business")

        if is_relevant:
            relevant.append(mem)

    return {
        "relevant_count": len(relevant),
        "relevant_memories": relevant,
        "relevance_types": list(relevance_types),
    }


def compute_learning_curve(deliveries: list[DeliveryData], batch_size: int = 100) -> list[dict]:
    """
    Compute learning curve as success rate over batches of deliveries.

    Returns list of dicts with batch stats.
    """
    curve = []
    for i in range(0, len(deliveries), batch_size):
        batch = deliveries[i:i + batch_size]
        successes = sum(1 for d in batch if d.success)
        total_steps = sum(d.actual_steps for d in batch)
        optimal_steps = sum(d.optimal_steps for d in batch)

        curve.append({
            "batch_start": i + 1,
            "batch_end": min(i + batch_size, len(deliveries)),
            "deliveries": len(batch),
            "successes": successes,
            "success_rate": successes / len(batch) if batch else 0,
            "avg_steps": total_steps / len(batch) if batch else 0,
            "step_efficiency": optimal_steps / total_steps if total_steps > 0 else 0,
        })

    return curve


def compute_memory_effectiveness(deliveries: list[DeliveryData]) -> dict:
    """
    Compute memory effectiveness metrics.

    Returns dict with correlation analysis between memory presence and success.
    """
    with_relevant_memory = [d for d in deliveries if d.relevant_memories_count > 0]
    without_relevant_memory = [d for d in deliveries if d.relevant_memories_count == 0]

    with_any_memory = [d for d in deliveries if d.memories_injected_total > 0]
    without_any_memory = [d for d in deliveries if d.memories_injected_total == 0]

    def success_rate(ds):
        return sum(1 for d in ds if d.success) / len(ds) if ds else 0

    def avg_steps(ds):
        return sum(d.actual_steps for d in ds) / len(ds) if ds else 0

    return {
        "total_deliveries": len(deliveries),

        # Any memory
        "with_any_memory_count": len(with_any_memory),
        "with_any_memory_success_rate": success_rate(with_any_memory),
        "with_any_memory_avg_steps": avg_steps(with_any_memory),

        "without_any_memory_count": len(without_any_memory),
        "without_any_memory_success_rate": success_rate(without_any_memory),
        "without_any_memory_avg_steps": avg_steps(without_any_memory),

        # Relevant memory
        "with_relevant_memory_count": len(with_relevant_memory),
        "with_relevant_memory_success_rate": success_rate(with_relevant_memory),
        "with_relevant_memory_avg_steps": avg_steps(with_relevant_memory),

        "without_relevant_memory_count": len(without_relevant_memory),
        "without_relevant_memory_success_rate": success_rate(without_relevant_memory),
        "without_relevant_memory_avg_steps": avg_steps(without_relevant_memory),

        # Lift (improvement from memory)
        "relevant_memory_success_lift": (
            success_rate(with_relevant_memory) - success_rate(without_relevant_memory)
            if with_relevant_memory and without_relevant_memory else None
        ),
        "relevant_memory_steps_reduction": (
            avg_steps(without_relevant_memory) - avg_steps(with_relevant_memory)
            if with_relevant_memory and without_relevant_memory else None
        ),
    }


def generate_summary(
    config: EvalConfig,
    deliveries: list[DeliveryData],
    total_time_seconds: float,
    building: Building,
) -> EvalRunSummary:
    """Generate summary statistics for an evaluation run."""

    successful = [d for d in deliveries if d.success]

    # Aggregate error counts
    error_counts = {}
    for d in deliveries:
        for step in d.steps:
            if step.error_type:
                error_counts[step.error_type] = error_counts.get(step.error_type, 0) + 1

    total_steps = sum(d.actual_steps for d in deliveries)
    total_optimal = sum(d.optimal_steps for d in deliveries)
    total_llm_time = sum(d.llm_time_ms for d in deliveries)

    return EvalRunSummary(
        config_name=config.value,
        total_deliveries=len(deliveries),
        successful_deliveries=len(successful),
        success_rate=len(successful) / len(deliveries) if deliveries else 0,
        avg_steps=total_steps / len(deliveries) if deliveries else 0,
        avg_optimal_steps=total_optimal / len(deliveries) if deliveries else 0,
        step_efficiency=total_optimal / total_steps if total_steps > 0 else 0,
        avg_llm_time_ms=total_llm_time / len(deliveries) if deliveries else 0,
        total_time_seconds=total_time_seconds,
        error_counts=error_counts,
        memory_stats=compute_memory_effectiveness(deliveries),
        learning_curve=compute_learning_curve(deliveries),
    )


def get_building_layout_dict(building: Building) -> dict:
    """Export building layout as a dictionary for storage."""
    layout = {
        "num_floors": building.num_floors,
        "floors": {}
    }

    for floor_num in sorted(building.floors.keys()):
        floor_data = {}
        for side in [Side.FRONT, Side.BACK]:
            business = building.get_business(floor_num, side)
            if business:
                floor_data[side.value] = {
                    "business_name": business.name,
                    "employees": [
                        {"name": emp.name, "role": emp.role}
                        for emp in business.employees
                    ]
                }
        layout["floors"][floor_num] = floor_data

    return layout


def generate_report_markdown(
    config: EvalConfig,
    summary: EvalRunSummary,
    building: Building,
    settings: dict,
    run_timestamp: str,
) -> str:
    """Generate a human-readable markdown report."""

    report = f"""# Evaluation Report: {config.value}

**Run Timestamp:** {run_timestamp}

## Configuration

| Setting | Value |
|---------|-------|
| Memory Injection | {settings.get('inject_memories', 'N/A')} |
| Mode | {'reflect' if settings.get('use_reflect') else 'recall'} |
| Budget | {settings.get('recall_budget', 'N/A')} |

## Summary Statistics

| Metric | Value |
|--------|-------|
| Total Deliveries | {summary.total_deliveries} |
| Successful Deliveries | {summary.successful_deliveries} |
| **Success Rate** | **{summary.success_rate:.1%}** |
| Average Steps | {summary.avg_steps:.2f} |
| Average Optimal Steps | {summary.avg_optimal_steps:.2f} |
| **Step Efficiency** | **{summary.step_efficiency:.1%}** |
| Average LLM Time | {summary.avg_llm_time_ms:.0f} ms |
| Total Run Time | {summary.total_time_seconds:.1f} seconds |

## Error Breakdown

| Error Type | Count |
|------------|-------|
"""

    for error_type, count in sorted(summary.error_counts.items(), key=lambda x: -x[1]):
        report += f"| {error_type} | {count} |\n"

    if not summary.error_counts:
        report += "| No errors recorded | - |\n"

    report += """
## Memory Effectiveness

"""

    mem = summary.memory_stats
    is_baseline = not settings.get('inject_memories', True)

    if is_baseline:
        report += "*No memory injection in this configuration (baseline).*\n\n"
    elif mem.get('with_any_memory_count', 0) > 0:
        report += f"""| Metric | With Memory | Without Memory |
|--------|-------------|----------------|
| Deliveries | {mem.get('with_any_memory_count', 0)} | {mem.get('without_any_memory_count', 0)} |
| Success Rate | {mem.get('with_any_memory_success_rate', 0):.1%} | {mem.get('without_any_memory_success_rate', 0):.1%} |
| Avg Steps | {mem.get('with_any_memory_avg_steps', 0):.2f} | {mem.get('without_any_memory_avg_steps', 0):.2f} |

### Relevant Memory Analysis

| Metric | With Relevant Memory | Without Relevant Memory |
|--------|---------------------|------------------------|
| Deliveries | {mem.get('with_relevant_memory_count', 0)} | {mem.get('without_relevant_memory_count', 0)} |
| Success Rate | {mem.get('with_relevant_memory_success_rate', 0):.1%} | {mem.get('without_relevant_memory_success_rate', 0):.1%} |
| Avg Steps | {mem.get('with_relevant_memory_avg_steps', 0):.2f} | {mem.get('without_relevant_memory_avg_steps', 0):.2f} |

"""
        if mem.get('relevant_memory_success_lift') is not None:
            report += f"""**Success Rate Lift from Relevant Memory:** {mem['relevant_memory_success_lift']:+.1%}

**Steps Reduction from Relevant Memory:** {mem.get('relevant_memory_steps_reduction', 0):+.2f} steps

"""
    else:
        report += "*Memory injection enabled but no memories were detected in deliveries. Early deliveries may not have accumulated memories yet.*\n\n"

    report += """## Learning Curve

| Batch | Deliveries | Success Rate | Avg Steps | Efficiency |
|-------|------------|--------------|-----------|------------|
"""

    for batch in summary.learning_curve:
        report += f"| {batch['batch_start']}-{batch['batch_end']} | {batch['deliveries']} | {batch['success_rate']:.1%} | {batch['avg_steps']:.2f} | {batch['step_efficiency']:.1%} |\n"

    report += """
## Building Layout

"""

    for floor_num in sorted(building.floors.keys(), reverse=True):
        report += f"### Floor {floor_num}\n\n"
        for side in [Side.FRONT, Side.BACK]:
            business = building.get_business(floor_num, side)
            if business:
                report += f"**{side.value.title()} Side:** {business.name}\n"
                report += f"- Employees: {', '.join(emp.name for emp in business.employees)}\n\n"

    report += """
---
*Generated by Hindsight Evaluation Framework*
"""

    return report


class EvaluationRunner:
    """Manages evaluation runs with data collection and persistence."""

    def __init__(self, output_dir: str = "evaluation_runs"):
        self.output_dir = output_dir
        os.makedirs(output_dir, exist_ok=True)

    def create_run_directory(self, config: EvalConfig) -> str:
        """Create a directory for a new evaluation run."""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        run_dir = os.path.join(self.output_dir, f"run_{timestamp}_{config.value}")
        os.makedirs(run_dir, exist_ok=True)
        os.makedirs(os.path.join(run_dir, "deliveries"), exist_ok=True)
        return run_dir

    def save_delivery(self, run_dir: str, delivery: DeliveryData):
        """Save a single delivery's data to disk."""
        filepath = os.path.join(run_dir, "deliveries", f"{delivery.delivery_id:04d}.json")
        with open(filepath, 'w') as f:
            # Convert dataclass to dict, handling nested dataclasses
            data = asdict(delivery)
            json.dump(data, f, indent=2, default=str)

    def save_config(self, run_dir: str, config: EvalConfig, settings: dict, building: Building, num_deliveries: int):
        """Save the run configuration."""
        config_data = {
            "config_name": config.value,
            "hindsight_settings": settings,
            "num_deliveries": num_deliveries,
            "building_layout": get_building_layout_dict(building),
            "timestamp": datetime.now().isoformat(),
        }
        filepath = os.path.join(run_dir, "config.json")
        with open(filepath, 'w') as f:
            json.dump(config_data, f, indent=2)

    def save_summary(self, run_dir: str, summary: EvalRunSummary):
        """Save the run summary."""
        filepath = os.path.join(run_dir, "summary.json")
        with open(filepath, 'w') as f:
            json.dump(asdict(summary), f, indent=2)

    def save_report(self, run_dir: str, report: str):
        """Save the markdown report."""
        filepath = os.path.join(run_dir, "report.md")
        with open(filepath, 'w') as f:
            f.write(report)

    def get_all_runs(self) -> list[dict]:
        """Get list of all evaluation runs with their summaries."""
        runs = []
        if not os.path.exists(self.output_dir):
            return runs

        for run_name in sorted(os.listdir(self.output_dir), reverse=True):
            run_dir = os.path.join(self.output_dir, run_name)
            if os.path.isdir(run_dir):
                summary_path = os.path.join(run_dir, "summary.json")
                config_path = os.path.join(run_dir, "config.json")

                run_info = {"name": run_name, "path": run_dir}

                if os.path.exists(summary_path):
                    with open(summary_path) as f:
                        run_info["summary"] = json.load(f)

                if os.path.exists(config_path):
                    with open(config_path) as f:
                        run_info["config"] = json.load(f)

                runs.append(run_info)

        return runs
