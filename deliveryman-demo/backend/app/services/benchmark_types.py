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

    # Delivery settings
    num_deliveries: int = 10
    repeat_ratio: float = 0.4  # 40% of deliveries revisit previous offices
    paired_mode: bool = False  # Each office visited exactly 2x
    include_business: str = "random"  # "always", "never", or "random"

    # Step limits
    step_multiplier: float = 5.0  # max_steps = optimal * multiplier
    min_steps: int = 15  # Minimum step limit per delivery

    # Memory settings
    memory_query_mode: str = "inject_once"  # "inject_once", "per_step", "both"
    wait_for_consolidation: bool = True  # Wait after store operations
    refresh_interval: int = 5  # Refresh mental models every N deliveries (0=disabled)

    # Building settings
    difficulty: str = "easy"
    use_procedural: bool = False  # Use procedural generation vs hardcoded
    num_floors: int = 3  # Only for procedural
    offices_per_floor: int = 2  # Only for procedural
    seed: Optional[int] = None  # For reproducible runs


@dataclass
class TokenUsage:
    """Token usage for a single LLM call."""

    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0

    def add(self, other: "TokenUsage"):
        """Add another TokenUsage to this one."""
        self.prompt_tokens += other.prompt_tokens
        self.completion_tokens += other.completion_tokens
        self.total_tokens += other.total_tokens


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

    # Token usage
    tokens: TokenUsage = field(default_factory=TokenUsage)

    # Timing
    start_time: float = 0.0
    end_time: float = 0.0
    latency_ms: float = 0.0

    # Memory
    memory_injected: bool = False
    memory_query_count: int = 0
    consolidation_triggered: bool = False

    # Is this a repeat visit?
    is_repeat: bool = False

    def compute_derived(self):
        """Compute derived metrics."""
        if self.end_time > 0 and self.start_time > 0:
            self.latency_ms = (self.end_time - self.start_time) * 1000
        if self.optimal_steps > 0 and self.steps_taken > 0:
            self.path_efficiency = min(1.0, self.optimal_steps / self.steps_taken)

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "deliveryId": self.delivery_id,
            "recipient": self.recipient,
            "business": self.business,
            "success": self.success,
            "stepsTaken": self.steps_taken,
            "optimalSteps": self.optimal_steps,
            "pathEfficiency": self.path_efficiency,
            "tokens": {
                "prompt": self.tokens.prompt_tokens,
                "completion": self.tokens.completion_tokens,
                "total": self.tokens.total_tokens,
            },
            "latencyMs": self.latency_ms,
            "memoryInjected": self.memory_injected,
            "memoryQueryCount": self.memory_query_count,
            "consolidationTriggered": self.consolidation_triggered,
            "isRepeat": self.is_repeat,
        }


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

    total_tokens: TokenUsage = field(default_factory=TokenUsage)
    total_latency_ms: float = 0.0

    # Learning metrics
    convergence_episode: int = 0  # First episode with efficiency >= 90%
    first_half_efficiency: float = 0.0
    second_half_efficiency: float = 0.0
    improvement: float = 0.0  # second_half - first_half

    # Efficiency over time
    efficiency_by_episode: list[float] = field(default_factory=list)
    tokens_by_episode: list[int] = field(default_factory=list)

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
        self.total_tokens.add(metrics.tokens)
        self.total_latency_ms += metrics.latency_ms

        self.efficiency_by_episode.append(metrics.path_efficiency)
        self.tokens_by_episode.append(metrics.tokens.total_tokens)

    def compute_final_metrics(self):
        """Compute final aggregate metrics after all deliveries."""
        if self.total_deliveries == 0:
            return

        # Average efficiency
        if self.efficiency_by_episode:
            self.avg_path_efficiency = sum(self.efficiency_by_episode) / len(self.efficiency_by_episode)

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
                "mode": self.config.mode.value,
                "model": self.config.model,
                "numDeliveries": self.config.num_deliveries,
                "repeatRatio": self.config.repeat_ratio,
                "pairedMode": self.config.paired_mode,
                "difficulty": self.config.difficulty,
                "refreshInterval": self.config.refresh_interval,
            },
            "summary": {
                "totalDeliveries": self.total_deliveries,
                "successfulDeliveries": self.successful_deliveries,
                "failedDeliveries": self.failed_deliveries,
                "successRate": self.successful_deliveries / self.total_deliveries if self.total_deliveries > 0 else 0,
                "totalSteps": self.total_steps,
                "totalOptimalSteps": self.total_optimal_steps,
                "avgPathEfficiency": self.avg_path_efficiency,
                "totalTokens": {
                    "prompt": self.total_tokens.prompt_tokens,
                    "completion": self.total_tokens.completion_tokens,
                    "total": self.total_tokens.total_tokens,
                },
                "totalLatencyMs": self.total_latency_ms,
                "avgLatencyMs": self.total_latency_ms / self.total_deliveries if self.total_deliveries > 0 else 0,
            },
            "learning": {
                "convergenceEpisode": self.convergence_episode,
                "firstHalfEfficiency": self.first_half_efficiency,
                "secondHalfEfficiency": self.second_half_efficiency,
                "improvement": self.improvement,
            },
            "timeSeries": {
                "efficiencyByEpisode": self.efficiency_by_episode,
                "tokensByEpisode": self.tokens_by_episode,
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

    Args:
        building: The building to generate deliveries for
        num_deliveries: Total number of deliveries
        repeat_ratio: Fraction of deliveries that revisit previous offices (0.0-1.0)
        paired_mode: If True, each office is visited exactly 2x
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
    visited = set()  # Track visited employees for repeat detection

    if paired_mode:
        # Each employee is visited exactly 2x
        # Shuffle employees and assign 2 deliveries each
        selected = all_employees.copy()
        random.shuffle(selected)

        # Limit to half of num_deliveries (since each gets 2 visits)
        selected = selected[: num_deliveries // 2]

        # Create pairs
        deliveries = []
        for emp_name in selected:
            business, employee = building.all_employees[emp_name]
            biz_name = business.name if include_business == "always" or (include_business == "random" and random.random() > 0.5) else None

            # First visit (not a repeat)
            deliveries.append((emp_name, biz_name, False))
            # Second visit (repeat)
            deliveries.append((emp_name, biz_name, True))

        # Shuffle to interleave
        random.shuffle(deliveries)

        for emp_name, biz_name, is_repeat in deliveries:
            queue.recipients.append(emp_name)
            queue.businesses.append(biz_name)
            queue.is_repeat.append(is_repeat)

    else:
        # Standard mode with configurable repeat ratio
        for i in range(num_deliveries):
            # Decide if this should be a repeat
            if visited and random.random() < repeat_ratio:
                # Pick from visited employees
                emp_name = random.choice(list(visited))
                is_repeat = True
            else:
                # Pick any employee (may be visited or new)
                emp_name = random.choice(all_employees)
                is_repeat = emp_name in visited

            business, employee = building.all_employees[emp_name]

            # Determine business name inclusion
            if include_business == "always":
                biz_name = business.name
            elif include_business == "never":
                biz_name = None
            else:  # random
                biz_name = business.name if random.random() > 0.5 else None

            queue.recipients.append(emp_name)
            queue.businesses.append(biz_name)
            queue.is_repeat.append(is_repeat)

            visited.add(emp_name)

    return queue
