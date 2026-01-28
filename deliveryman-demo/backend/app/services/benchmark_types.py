"""Benchmark types and configuration for delivery agent evaluation."""

from dataclasses import dataclass, field
from enum import Enum
from typing import Optional
import time


class AgentMode(str, Enum):
    """Available agent modes for benchmarking."""

    NO_MEMORY = "no_memory"  # Stateless baseline - no memory injection or storage
    FILESYSTEM = "filesystem"  # Agent manages own notes (read_notes/write_notes tools)
    RECALL = "recall"  # Hindsight recall - raw fact retrieval
    REFLECT = "reflect"  # Hindsight reflect - LLM-synthesized answers
    HINDSIGHT_MM = "hindsight_mm"  # Hindsight with mental models (wait for consolidation)
    HINDSIGHT_MM_NOWAIT = "hindsight_mm_nowait"  # Mental models without waiting


@dataclass
class BenchmarkConfig:
    """Configuration for a benchmark run."""

    # Agent settings
    mode: AgentMode = AgentMode.RECALL
    model: str = "openai/gpt-4o"
    name: Optional[str] = None  # Custom name for this config (defaults to mode)

    # Delivery settings
    num_deliveries: int = 10
    repeat_ratio: float = 0.4  # 40% of deliveries revisit previous offices
    paired_mode: bool = False  # Each office visited exactly 2x
    include_business: str = "random"  # "always", "never", or "random"

    # Step limits
    step_multiplier: float = 5.0  # max_steps = optimal * multiplier
    min_steps: int = 15  # Minimum step limit per delivery
    max_steps: Optional[int] = None  # Hard cap on steps (optional)

    # Memory settings
    memory_query_mode: str = "inject_once"  # "inject_once", "per_step", "both"
    wait_for_consolidation: bool = True  # Wait after store operations
    refresh_interval: int = 5  # Refresh mental models every N deliveries (0=disabled)
    preseed_coverage: float = 0.0  # Pre-seed building knowledge (0.0-1.0)
    mm_query_type: str = "recall"  # "recall" or "reflect" for MM modes

    # Hindsight settings
    hindsight_url: Optional[str] = None  # Override hindsight API URL
    bank_id: Optional[str] = None  # Custom bank ID (None = auto-generated)
    mission: Optional[str] = None  # Custom bank mission for mental models
    query: Optional[str] = None  # Custom memory query template ({recipient} placeholder)

    # Building settings
    difficulty: str = "easy"
    use_procedural: bool = False  # Use procedural generation vs hardcoded
    num_floors: int = 3  # Only for procedural
    offices_per_floor: int = 2  # Only for procedural
    seed: Optional[int] = None  # For reproducible runs

    @property
    def display_name(self) -> str:
        """Get display name (custom name or mode)."""
        return self.name or self.mode.value


@dataclass
class DeliveryMetrics:
    """Metrics for a single delivery."""

    delivery_id: int
    recipient: str
    business: Optional[str] = None

    # Outcome
    success: bool = False
    steps_taken: int = 0
    optimal_steps: int = 0
    path_efficiency: float = 0.0
    errors: int = 0  # Non-optimal moves (wrong direction OR failed tool calls)
    error_rate: float = 0.0  # errors / steps_taken

    # Memory
    memory_injected: bool = False
    memory_query_count: int = 0
    consolidation_triggered: bool = False

    # Timing (seconds)
    total_time_s: float = 0.0  # Total wall-clock time for this delivery
    llm_time_s: float = 0.0  # Time spent in LLM calls
    memory_time_s: float = 0.0  # Time spent in memory operations (recall/reflect/retain)
    consolidation_time_s: float = 0.0  # Time waiting for consolidation

    # Is this a repeat visit?
    is_repeat: bool = False

    # Detailed logs (for saveDetailedLogs option)
    path: list[str] = field(default_factory=list)  # Sequence of locations visited
    actions: list[dict] = field(default_factory=list)  # Tool calls and responses

    def compute_derived(self):
        """Compute derived metrics."""
        if self.optimal_steps > 0 and self.steps_taken > 0:
            self.path_efficiency = min(1.0, self.optimal_steps / self.steps_taken)

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        result = {
            "deliveryId": self.delivery_id,
            "recipient": self.recipient,
            "business": self.business,
            "success": self.success,
            "stepsTaken": self.steps_taken,
            "optimalSteps": self.optimal_steps,
            "pathEfficiency": self.path_efficiency,
            "errors": self.errors,
            "errorRate": self.error_rate,
            "memoryInjected": self.memory_injected,
            "memoryQueryCount": self.memory_query_count,
            "consolidationTriggered": self.consolidation_triggered,
            "totalTimeS": round(self.total_time_s, 2),
            "llmTimeS": round(self.llm_time_s, 2),
            "memoryTimeS": round(self.memory_time_s, 2),
            "consolidationTimeS": round(self.consolidation_time_s, 2),
            "isRepeat": self.is_repeat,
        }
        # Only include path/actions if they have data (to keep results.json smaller)
        if self.path:
            result["path"] = self.path
        if self.actions:
            result["actions"] = self.actions
        return result


@dataclass
class BenchmarkResults:
    """Aggregate results for a benchmark run."""

    config: BenchmarkConfig

    # Per-delivery metrics
    deliveries: list[DeliveryMetrics] = field(default_factory=list)

    # Aggregate metrics
    total_deliveries: int = 0
    successful_deliveries: int = 0
    failed_deliveries: int = 0

    total_steps: int = 0
    total_optimal_steps: int = 0
    avg_path_efficiency: float = 0.0
    total_errors: int = 0
    avg_error_rate: float = 0.0

    # Timing aggregates (seconds)
    total_time_s: float = 0.0
    avg_delivery_time_s: float = 0.0
    total_llm_time_s: float = 0.0
    total_memory_time_s: float = 0.0
    total_consolidation_time_s: float = 0.0

    # Learning metrics
    convergence_episode: int = 0  # First episode with efficiency >= 90%
    first_half_efficiency: float = 0.0
    second_half_efficiency: float = 0.0
    improvement: float = 0.0  # second_half - first_half

    # Efficiency over time
    efficiency_by_episode: list[float] = field(default_factory=list)

    def add_delivery(self, metrics: DeliveryMetrics):
        """Add a delivery result and update aggregates."""
        metrics.compute_derived()
        self.deliveries.append(metrics)

        self.total_deliveries += 1
        if metrics.success:
            self.successful_deliveries += 1
        else:
            self.failed_deliveries += 1

        self.total_steps += metrics.steps_taken
        self.total_optimal_steps += metrics.optimal_steps
        self.total_errors += metrics.errors

        self.total_time_s += metrics.total_time_s
        self.total_llm_time_s += metrics.llm_time_s
        self.total_memory_time_s += metrics.memory_time_s
        self.total_consolidation_time_s += metrics.consolidation_time_s

        self.efficiency_by_episode.append(metrics.path_efficiency)

    def compute_final_metrics(self):
        """Compute final aggregate metrics after all deliveries."""
        if self.total_deliveries == 0:
            return

        # Average efficiency
        if self.efficiency_by_episode:
            self.avg_path_efficiency = sum(self.efficiency_by_episode) / len(self.efficiency_by_episode)

        # Average error rate
        if self.total_steps > 0:
            self.avg_error_rate = self.total_errors / self.total_steps

        # Average delivery time
        self.avg_delivery_time_s = self.total_time_s / self.total_deliveries

        # Convergence episode (first with efficiency >= 90%)
        for i, eff in enumerate(self.efficiency_by_episode):
            if eff >= 0.9:
                self.convergence_episode = i + 1
                break

        # Learning improvement (second half vs first half)
        if len(self.efficiency_by_episode) >= 2:
            mid = len(self.efficiency_by_episode) // 2
            self.first_half_efficiency = sum(self.efficiency_by_episode[:mid]) / mid
            self.second_half_efficiency = sum(self.efficiency_by_episode[mid:]) / (len(self.efficiency_by_episode) - mid)
            self.improvement = self.second_half_efficiency - self.first_half_efficiency

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return {
            "config": {
                "name": self.config.display_name,
                "mode": self.config.mode.value,
                "model": self.config.model,
                "numDeliveries": self.config.num_deliveries,
                "repeatRatio": self.config.repeat_ratio,
                "pairedMode": self.config.paired_mode,
                "difficulty": self.config.difficulty,
                "refreshInterval": self.config.refresh_interval,
                "mmQueryType": self.config.mm_query_type,
                "memoryQueryMode": self.config.memory_query_mode,
                "waitForConsolidation": self.config.wait_for_consolidation,
                "hindsightUrl": self.config.hindsight_url,
                "bankId": self.config.bank_id,
            },
            "summary": {
                "totalDeliveries": self.total_deliveries,
                "successfulDeliveries": self.successful_deliveries,
                "failedDeliveries": self.failed_deliveries,
                "successRate": self.successful_deliveries / self.total_deliveries if self.total_deliveries > 0 else 0,
                "totalSteps": self.total_steps,
                "totalOptimalSteps": self.total_optimal_steps,
                "avgPathEfficiency": self.avg_path_efficiency,
                "totalErrors": self.total_errors,
                "avgErrorRate": self.avg_error_rate,
                "totalTimeS": round(self.total_time_s, 2),
                "avgDeliveryTimeS": round(self.avg_delivery_time_s, 2),
                "totalLlmTimeS": round(self.total_llm_time_s, 2),
                "totalMemoryTimeS": round(self.total_memory_time_s, 2),
                "totalConsolidationTimeS": round(self.total_consolidation_time_s, 2),
            },
            "learning": {
                "convergenceEpisode": self.convergence_episode,
                "firstHalfEfficiency": self.first_half_efficiency,
                "secondHalfEfficiency": self.second_half_efficiency,
                "improvement": self.improvement,
            },
            "timeSeries": {
                "efficiencyByEpisode": self.efficiency_by_episode,
            },
            "deliveries": [d.to_dict() for d in self.deliveries],
        }


@dataclass
class DeliveryQueue:
    """Queue of deliveries to run with repeat/paired mode support."""

    recipients: list[str] = field(default_factory=list)
    businesses: list[Optional[str]] = field(default_factory=list)
    is_repeat: list[bool] = field(default_factory=list)
    current_index: int = 0

    def __len__(self) -> int:
        return len(self.recipients)

    def __iter__(self):
        return iter(zip(self.recipients, self.businesses, self.is_repeat))

    def get_next(self) -> Optional[tuple[str, Optional[str], bool]]:
        """Get the next delivery."""
        if self.current_index >= len(self.recipients):
            return None
        result = (
            self.recipients[self.current_index],
            self.businesses[self.current_index],
            self.is_repeat[self.current_index],
        )
        self.current_index += 1
        return result

    def reset(self):
        """Reset to start."""
        self.current_index = 0


def generate_delivery_queue(
    building,
    num_deliveries: int,
    repeat_ratio: float = 0.4,
    paired_mode: bool = False,
    include_business: str = "random",
    seed: Optional[int] = None,
) -> DeliveryQueue:
    """Generate a queue of deliveries with configurable repeat ratio.

    Matches eval framework behavior:
    - Pre-calculates unique visits and repeat visits
    - First 60% of deliveries favor unique visits (tests new exploration)
    - Remaining 40% has more repeats (tests learning/memory)
    - Creates "frequent employees" that get majority of repeat visits

    Args:
        building: The building to generate deliveries for
        num_deliveries: Total number of deliveries
        repeat_ratio: Fraction of deliveries that are repeats (0.0-1.0)
        paired_mode: If True, each employee is visited exactly 2x
        include_business: "always", "never", or "random"
        seed: Random seed for reproducibility

    Returns:
        DeliveryQueue with recipients, businesses, and is_repeat flags
    """
    import random

    if seed is not None:
        random.seed(seed)

    # Get all employees
    all_employees = list(building.all_employees.keys())
    if not all_employees:
        return DeliveryQueue()

    queue = DeliveryQueue()

    def get_business_name(emp_name: str) -> Optional[str]:
        """Determine business name based on include_business setting."""
        business, _ = building.all_employees[emp_name]
        if include_business == "always":
            return business.name
        elif include_business == "never":
            return None
        else:  # random
            return business.name if random.random() > 0.5 else None

    if paired_mode:
        # Each employee is visited exactly 2x (matches eval framework's generate_paired_deliveries)
        selected = all_employees.copy()
        random.shuffle(selected)

        # Limit to half of num_deliveries (since each gets 2 visits)
        num_employees = min(len(selected), num_deliveries // 2)
        selected = selected[:num_employees]

        # Track which employees have been visited once
        first_visits = selected.copy()
        second_visits = selected.copy()
        random.shuffle(second_visits)

        # Interleave: put most first visits early, second visits later (but not strictly)
        visit_order = []
        first_queue = first_visits.copy()
        second_queue = second_visits.copy()
        visited_once = set()

        # First 60% of deliveries - mostly first visits
        first_portion = int(num_employees * 1.2)  # ~60% of 2*num_employees
        for _ in range(first_portion):
            if first_queue:
                emp = first_queue.pop(0)
                visit_order.append((emp, False))  # First visit
                visited_once.add(emp)
            elif second_queue:
                # Find an employee that's been visited
                for i, emp in enumerate(second_queue):
                    if emp in visited_once:
                        visit_order.append((emp, True))  # Second visit
                        second_queue.pop(i)
                        break

        # Remaining deliveries - mix of remaining first visits and second visits
        remaining = [(emp, False) for emp in first_queue] + [(emp, True) for emp in second_queue]
        random.shuffle(remaining)
        visit_order.extend(remaining)

        # Build the queue
        for emp_name, is_repeat in visit_order:
            queue.recipients.append(emp_name)
            queue.businesses.append(get_business_name(emp_name))
            queue.is_repeat.append(is_repeat)

    else:
        # Standard mode with sophisticated repeat ratio (matches eval framework)
        # Split deliveries: unique visits + repeat visits
        num_repeats = int(num_deliveries * repeat_ratio)
        num_unique = num_deliveries - num_repeats

        # Ensure we don't request more unique visits than employees exist
        num_unique = min(num_unique, len(all_employees))
        num_repeats = num_deliveries - num_unique

        # Select employees for unique visits
        shuffled_employees = all_employees.copy()
        random.shuffle(shuffled_employees)
        unique_visits = shuffled_employees[:num_unique]

        # Select employees for repeat visits (favor some employees more than others)
        # This simulates "frequent customers" that a delivery person would remember
        frequent_employees = unique_visits[:max(1, len(unique_visits) // 3)]
        repeat_visits = []
        for _ in range(num_repeats):
            # 70% chance to pick from frequent employees, 30% from all unique
            if random.random() < 0.7 and frequent_employees:
                repeat_visits.append(random.choice(frequent_employees))
            else:
                repeat_visits.append(random.choice(unique_visits))

        # Build delivery sequence: spread repeats throughout
        # First 60% - favor unique visits (tests exploration)
        # Remaining 40% - more repeats (tests if agent learned)
        visit_order = []
        unique_queue = list(unique_visits)
        repeat_queue = list(repeat_visits)
        random.shuffle(unique_queue)
        random.shuffle(repeat_queue)
        visited = set()

        # First 60% - favor unique visits (80% unique, 20% repeat)
        first_portion = int(num_deliveries * 0.6)
        for _ in range(first_portion):
            if unique_queue and (not repeat_queue or random.random() < 0.8):
                emp = unique_queue.pop()
                is_repeat = emp in visited
                visit_order.append((emp, is_repeat))
                visited.add(emp)
            elif repeat_queue:
                emp = repeat_queue.pop()
                is_repeat = emp in visited
                visit_order.append((emp, is_repeat))
                visited.add(emp)

        # Remaining 40% - use what's left (more repeats)
        remaining_emps = unique_queue + repeat_queue
        random.shuffle(remaining_emps)
        for emp in remaining_emps:
            is_repeat = emp in visited
            visit_order.append((emp, is_repeat))
            visited.add(emp)

        # Build the queue
        for emp_name, is_repeat in visit_order:
            queue.recipients.append(emp_name)
            queue.businesses.append(get_business_name(emp_name))
            queue.is_repeat.append(is_repeat)

    return queue
