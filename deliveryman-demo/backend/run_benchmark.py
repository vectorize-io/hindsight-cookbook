#!/usr/bin/env python3
"""CLI to run benchmarks from a JSON config file.

All configs run in PARALLEL with separate memory banks for faster execution.
Each config gets a unique bank_id auto-generated to avoid conflicts.

Usage:
    python run_benchmark.py configs/all_memory_modes.json
    python run_benchmark.py configs/all_memory_modes.json --hindsight-url http://localhost:8888

CI Usage:
    # Run benchmarks and fail if success rate < 80%
    python run_benchmark.py configs/ci.json --min-success-rate 0.8

Config file format:
    {
      "runName": "my_benchmark",       // Optional, defaults to config filename
      "generateCharts": true,          // Generate SVG charts
      "saveDetailedLogs": false,       // Save per-delivery action logs
      "configs": [
        { "mode": "recall", "num_deliveries": 5, ... },
        { "mode": "hindsight_mm", "num_deliveries": 5, ... }
      ]
    }

    Or legacy format (array of configs):
    [
      { "mode": "recall", "num_deliveries": 5, ... }
    ]
"""

import argparse
import asyncio
import json
import sys
from datetime import datetime
from pathlib import Path
from dataclasses import dataclass
from typing import Optional

# Add parent to path for imports
sys.path.insert(0, str(Path(__file__).parent))

from app.services.benchmark_types import BenchmarkConfig, AgentMode
from app.services.benchmark_service import run_benchmark
from app.services.benchmark_charts import generate_dashboard_chart, generate_comparison_chart
from app.services.memory_service import initialize_memory

# Results directory (same as UI)
RESULTS_DIR = Path(__file__).parent / "results"


@dataclass
class BenchmarkRunConfig:
    """Top-level config for a benchmark run."""
    run_name: str
    generate_charts: bool
    save_detailed_logs: bool
    configs: list[BenchmarkConfig]


# Global config keys that apply to all configs if not specified per-config
GLOBAL_CONFIG_KEYS = [
    "num_deliveries",
    "model",
    "difficulty",
    "repeat_ratio",
    "step_multiplier",
    "min_steps",
    "max_steps",
    "memory_query_mode",
    "wait_for_consolidation",
    "refresh_interval",
    "preseed_coverage",
    "mm_query_type",
    "hindsight_url",
    "bank_id",
    "mission",
    "query",
    # Delivery queue settings
    "paired_mode",
    "include_business",
    "seed",
]


def load_config(config_path: str, overrides: dict = None) -> BenchmarkRunConfig:
    """Load benchmark run config from JSON file.

    Supports two formats:
    1. New format: { "runName": "...", "generateCharts": true, "configs": [...] }
    2. Legacy format: [...] (array of configs)

    Global config keys (num_deliveries, model, etc.) can be set at top level
    and will apply to all configs unless overridden per-config.
    """
    with open(config_path) as f:
        data = json.load(f)

    # Determine format
    if isinstance(data, list):
        # Legacy format: array of configs
        config_list = data
        run_name = Path(config_path).stem
        generate_charts = False
        save_detailed_logs = False
        global_defaults = {}
    else:
        # New format: object with metadata
        config_list = data.get("configs", [data])  # Support single config object
        run_name = data.get("runName", Path(config_path).stem)
        generate_charts = data.get("generateCharts", False)
        save_detailed_logs = data.get("saveDetailedLogs", False)
        # Extract global defaults
        global_defaults = {k: data[k] for k in GLOBAL_CONFIG_KEYS if k in data}

    # Auto-generate seed if not specified (ensures all configs get same deliveries)
    import random
    import uuid
    if "seed" not in global_defaults:
        global_defaults["seed"] = random.randint(1, 1000000)

    # Parse configs
    configs = []
    for i, cfg in enumerate(config_list):
        # Apply global defaults first (per-config values override)
        merged_cfg = {**global_defaults, **cfg}
        # Convert mode string to enum
        if "mode" in merged_cfg and isinstance(merged_cfg["mode"], str):
            merged_cfg["mode"] = AgentMode(merged_cfg["mode"])
        # Apply CLI overrides last (highest priority)
        if overrides:
            for key, value in overrides.items():
                if value is not None:
                    merged_cfg[key] = value
        # Auto-generate unique bank_id for parallel execution (if not specified)
        if "bank_id" not in merged_cfg or not merged_cfg["bank_id"]:
            mode_name = merged_cfg.get("mode", AgentMode.RECALL)
            if isinstance(mode_name, AgentMode):
                mode_name = mode_name.value
            config_name = merged_cfg.get("name", f"config{i}")
            # Sanitize name for bank_id
            safe_name = "".join(c if c.isalnum() else "_" for c in config_name).lower()
            merged_cfg["bank_id"] = f"bench-{safe_name}-{uuid.uuid4().hex[:8]}"
        configs.append(BenchmarkConfig(**merged_cfg))

    return BenchmarkRunConfig(
        run_name=run_name,
        generate_charts=generate_charts,
        save_detailed_logs=save_detailed_logs,
        configs=configs,
    )


def generate_charts(all_results: list[dict], run_dir: Path, quiet: bool = False) -> list[str]:
    """Generate dashboard and comparison charts.

    Args:
        all_results: List of benchmark result dicts
        run_dir: Directory to save charts
        quiet: Suppress output

    Returns:
        List of generated chart file paths
    """
    chart_paths = []

    # Generate dashboard chart for each config
    for i, result in enumerate(all_results):
        config_name = result.get("config", {}).get("name") or result.get("config", {}).get("mode", f"config{i}")
        # Sanitize for filename
        mode_safe = "".join(c if c.isalnum() or c in "-_" else "_" for c in config_name)
        chart_path = run_dir / f"{mode_safe}_dashboard.svg"
        try:
            generate_dashboard_chart(result, chart_path)
            chart_paths.append(str(chart_path))
            if not quiet:
                print(f"  Generated: {chart_path.name}")
        except Exception as e:
            print(f"  Warning: Failed to generate dashboard for {config_name}: {e}", file=sys.stderr)

    # Generate comparison chart if multiple configs
    if len(all_results) > 1:
        comparison_path = run_dir / "comparison.svg"
        try:
            generate_comparison_chart(all_results, comparison_path)
            chart_paths.append(str(comparison_path))
            if not quiet:
                print(f"  Generated: {comparison_path.name}")
        except Exception as e:
            print(f"  Warning: Failed to generate comparison chart: {e}", file=sys.stderr)

    return chart_paths


def save_detailed_logs(all_results: list[dict], run_dir: Path, quiet: bool = False) -> list[str]:
    """Save per-delivery action logs to subdirectories.

    Args:
        all_results: List of benchmark result dicts
        run_dir: Base directory for the run
        quiet: Suppress output

    Returns:
        List of saved file paths
    """
    saved_files = []

    for result in all_results:
        config = result.get("config", {})
        config_name = config.get("name") or config.get("mode", "unknown")
        mode_safe = "".join(c if c.isalnum() or c in "-_" else "_" for c in config_name)

        # Create config subdirectory
        config_dir = run_dir / mode_safe
        config_dir.mkdir(parents=True, exist_ok=True)

        # Save each delivery's detailed log
        for i, delivery in enumerate(result.get("deliveries", []), start=1):
            if delivery.get("actions"):
                delivery_log = {
                    "deliveryId": delivery.get("deliveryId", i),
                    "recipient": delivery.get("recipient"),
                    "business": delivery.get("business"),
                    "success": delivery.get("success"),
                    "stepsTaken": delivery.get("stepsTaken"),
                    "optimalSteps": delivery.get("optimalSteps"),
                    "pathEfficiency": delivery.get("pathEfficiency"),
                    "errors": delivery.get("errors"),
                    "errorRate": delivery.get("errorRate"),
                    "path": delivery.get("path"),
                    "actions": delivery.get("actions"),
                }
                log_path = config_dir / f"delivery_{i:03d}.json"
                with open(log_path, "w") as f:
                    json.dump(delivery_log, f, indent=2)
                saved_files.append(str(log_path))

        # Also save config summary in the config directory
        config_summary = {
            "config": config,
            "summary": result.get("summary", {}),
            "learning": result.get("learning", {}),
        }
        summary_path = config_dir / "summary.json"
        with open(summary_path, "w") as f:
            json.dump(config_summary, f, indent=2)
        saved_files.append(str(summary_path))

        if not quiet:
            print(f"  Saved detailed logs for {config_name}: {len(result.get('deliveries', []))} deliveries")

    return saved_files


def save_configurations_doc(configs: list[BenchmarkConfig], run_dir: Path, seed: int = None, quiet: bool = False) -> str:
    """Save a markdown document showing all configuration settings.

    Args:
        configs: List of BenchmarkConfig objects
        run_dir: Directory to save the doc
        seed: Random seed used for delivery queue generation
        quiet: Suppress output

    Returns:
        Path to saved file
    """
    lines = [
        "# Benchmark Configurations",
        "",
        f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        "",
        f"Total configs: {len(configs)}",
        f"Seed: {seed} (ensures all configs get same delivery queue)",
        "",
    ]

    for i, config in enumerate(configs, 1):
        lines.extend([
            f"## {i}. {config.display_name}",
            "",
            "| Setting | Value |",
            "|---------|-------|",
            f"| Mode | `{config.mode.value}` |",
            f"| Model | `{config.model}` |",
            f"| Difficulty | `{config.difficulty}` |",
            f"| Num Deliveries | {config.num_deliveries} |",
            f"| Paired Mode | {config.paired_mode} |",
            f"| Repeat Ratio | {config.repeat_ratio} |",
            f"| Include Business | `{config.include_business}` |",
            "",
            "### Step Limits",
            "",
            "| Setting | Value |",
            "|---------|-------|",
            f"| Step Multiplier | {config.step_multiplier} |",
            f"| Min Steps | {config.min_steps} |",
            f"| Max Steps | {config.max_steps or 'None (no cap)'} |",
            "",
            "### Memory Settings",
            "",
            "| Setting | Value |",
            "|---------|-------|",
            f"| Memory Query Mode | `{config.memory_query_mode}` |",
            f"| MM Query Type | `{config.mm_query_type}` |",
            f"| Wait for Consolidation | {config.wait_for_consolidation} |",
            f"| Refresh Interval | {config.refresh_interval} |",
            f"| Preseed Coverage | {config.preseed_coverage} |",
            "",
            "### Hindsight Settings",
            "",
            "| Setting | Value |",
            "|---------|-------|",
            f"| Hindsight URL | `{config.hindsight_url or 'default'}` |",
            f"| Bank ID | `{config.bank_id or 'auto-generated'}` |",
            f"| Custom Mission | {'Yes' if config.mission else 'No (default)'} |",
            f"| Custom Query | {'Yes' if config.query else 'No (default)'} |",
            "",
        ])

    doc_path = run_dir / "configurations.md"
    with open(doc_path, "w") as f:
        f.write("\n".join(lines))

    if not quiet:
        print(f"  Saved: {doc_path.name}")

    return str(doc_path)


def save_summary_of_findings(all_results: list[dict], run_dir: Path, quiet: bool = False) -> str:
    """Save a markdown summary of benchmark findings.

    Args:
        all_results: List of benchmark result dicts
        run_dir: Directory to save the doc
        quiet: Suppress output

    Returns:
        Path to saved file
    """
    lines = [
        "# Benchmark Summary of Findings",
        "",
        f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        "",
    ]

    # Overview table
    lines.extend([
        "## Overview",
        "",
        "| Config | Success Rate | Path Efficiency | Error Rate | Total Steps | Optimal Steps |",
        "|--------|--------------|-----------------|------------|-------------|---------------|",
    ])

    for result in all_results:
        config = result.get("config", {})
        name = config.get("name") or config.get("mode", "unknown")
        summary = result.get("summary", {})

        total = summary.get("totalDeliveries", 1)
        successful = summary.get("successfulDeliveries", 0)
        success_rate = successful / max(total, 1)
        efficiency = summary.get("avgPathEfficiency", 0)
        error_rate = summary.get("avgErrorRate", 0)
        total_steps = summary.get("totalSteps", 0)
        optimal_steps = summary.get("totalOptimalSteps", 0)

        lines.append(
            f"| {name} | {success_rate:.1%} | {efficiency:.1%} | {error_rate:.1%} | {total_steps} | {optimal_steps} |"
        )

    lines.append("")

    # Detailed findings per config
    lines.extend([
        "## Detailed Results",
        "",
    ])

    for result in all_results:
        config = result.get("config", {})
        name = config.get("name") or config.get("mode", "unknown")
        summary = result.get("summary", {})
        learning = result.get("learning", {})

        total = summary.get("totalDeliveries", 0)
        successful = summary.get("successfulDeliveries", 0)
        failed = summary.get("failedDeliveries", 0)

        lines.extend([
            f"### {name}",
            "",
            f"**Deliveries:** {successful}/{total} successful ({failed} failed)",
            "",
            "#### Performance Metrics",
            "",
            f"- **Path Efficiency:** {summary.get('avgPathEfficiency', 0):.1%}",
            f"- **Error Rate:** {summary.get('avgErrorRate', 0):.1%} ({summary.get('totalErrors', 0)} total errors)",
            f"- **Total Steps:** {summary.get('totalSteps', 0)} (optimal: {summary.get('totalOptimalSteps', 0)})",
            "",
            "#### Learning Metrics",
            "",
            f"- **Convergence Episode:** {learning.get('convergenceEpisode', 'N/A')}",
            f"- **First Half Efficiency:** {learning.get('firstHalfEfficiency', 0):.1%}",
            f"- **Second Half Efficiency:** {learning.get('secondHalfEfficiency', 0):.1%}",
            f"- **Improvement:** {learning.get('improvement', 0):+.1%}",
            "",
        ])

        # Per-delivery breakdown
        deliveries = result.get("deliveries", [])
        if deliveries:
            lines.extend([
                "#### Delivery Breakdown",
                "",
                "| # | Recipient | Success | Steps | Optimal | Efficiency | Errors |",
                "|---|-----------|---------|-------|---------|------------|--------|",
            ])
            for d in deliveries:
                lines.append(
                    f"| {d.get('deliveryId', '?')} | {d.get('recipient', '?')} | "
                    f"{'Yes' if d.get('success') else 'No'} | {d.get('stepsTaken', 0)} | "
                    f"{d.get('optimalSteps', 0)} | {d.get('pathEfficiency', 0):.1%} | "
                    f"{d.get('errors', 0)} |"
                )
            lines.append("")

    # Comparative analysis
    if len(all_results) > 1:
        lines.extend([
            "## Comparative Analysis",
            "",
        ])

        # Find best/worst performers by efficiency
        sorted_by_efficiency = sorted(
            all_results,
            key=lambda r: r.get("summary", {}).get("avgPathEfficiency", 0),
            reverse=True
        )
        best = sorted_by_efficiency[0]
        worst = sorted_by_efficiency[-1]

        best_name = best.get("config", {}).get("name") or best.get("config", {}).get("mode", "unknown")
        worst_name = worst.get("config", {}).get("name") or worst.get("config", {}).get("mode", "unknown")

        lines.extend([
            f"**Best Path Efficiency:** {best_name} ({best.get('summary', {}).get('avgPathEfficiency', 0):.1%})",
            "",
            f"**Worst Path Efficiency:** {worst_name} ({worst.get('summary', {}).get('avgPathEfficiency', 0):.1%})",
            "",
        ])

        # Find best/worst by error rate
        sorted_by_errors = sorted(
            all_results,
            key=lambda r: r.get("summary", {}).get("avgErrorRate", 0)
        )
        lowest_errors = sorted_by_errors[0]
        highest_errors = sorted_by_errors[-1]

        le_name = lowest_errors.get("config", {}).get("name") or lowest_errors.get("config", {}).get("mode", "unknown")
        he_name = highest_errors.get("config", {}).get("name") or highest_errors.get("config", {}).get("mode", "unknown")

        lines.extend([
            f"**Lowest Error Rate:** {le_name} ({lowest_errors.get('summary', {}).get('avgErrorRate', 0):.1%})",
            "",
            f"**Highest Error Rate:** {he_name} ({highest_errors.get('summary', {}).get('avgErrorRate', 0):.1%})",
            "",
        ])

    doc_path = run_dir / "summary_of_findings.md"
    with open(doc_path, "w") as f:
        f.write("\n".join(lines))

    if not quiet:
        print(f"  Saved: {doc_path.name}")

    return str(doc_path)


def print_summary(all_results: list[dict], min_success_rate: float, max_error_rate: float) -> bool:
    """Print summary and return True if all thresholds passed."""
    print("\n" + "=" * 60)
    print("BENCHMARK SUMMARY")
    print("=" * 60)

    all_passed = True

    for result in all_results:
        # Name is nested in config, but summary fields are at top level
        config = result.get("config", {})
        mode = config.get("name") or config.get("mode", result.get("mode", "unknown"))
        summary = result.get("summary", result)
        success_rate = summary.get("successfulDeliveries", summary.get("successful_deliveries", 0)) / max(summary.get("totalDeliveries", summary.get("total_deliveries", 1)), 1)
        avg_error_rate = summary.get("avgErrorRate", summary.get("avg_error_rate", 0))
        avg_efficiency = summary.get("avgPathEfficiency", summary.get("avg_path_efficiency", 0))

        # Check thresholds
        success_ok = success_rate >= min_success_rate
        error_ok = max_error_rate is None or avg_error_rate <= max_error_rate

        status = "PASS" if (success_ok and error_ok) else "FAIL"
        if not (success_ok and error_ok):
            all_passed = False

        print(f"\n{mode}:")
        print(f"  Success Rate:    {success_rate:.1%} {'✓' if success_ok else '✗'} (min: {min_success_rate:.1%})")
        if max_error_rate is not None:
            print(f"  Avg Error Rate:  {avg_error_rate:.1%} {'✓' if error_ok else '✗'} (max: {max_error_rate:.1%})")
        print(f"  Path Efficiency: {avg_efficiency:.1%}")
        print(f"  Status: {status}")

    print("\n" + "=" * 60)
    overall = "ALL PASSED" if all_passed else "SOME FAILED"
    print(f"OVERALL: {overall}")
    print("=" * 60)

    return all_passed


async def main() -> int:
    """Run benchmarks and return exit code (0 = success, 1 = failure)."""
    parser = argparse.ArgumentParser(
        description="Run delivery benchmarks from JSON config",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Basic run (charts/logs controlled by JSON config)
  python run_benchmark.py configs/all_memory_modes.json

  # CI run with thresholds
  python run_benchmark.py configs/ci.json --min-success-rate 0.8 --max-error-rate 0.3

  # Override model for all configs
  python run_benchmark.py configs/all_memory_modes.json --model openai/gpt-4o
        """
    )
    parser.add_argument("config", help="Path to JSON config file")
    parser.add_argument("--hindsight-url", default="http://localhost:8888", help="Hindsight API URL")

    # CI threshold options
    parser.add_argument("--min-success-rate", type=float, default=0.0,
                        help="Minimum success rate to pass (0.0-1.0, default: 0.0)")
    parser.add_argument("--max-error-rate", type=float, default=None,
                        help="Maximum error rate to pass (0.0-1.0, default: no limit)")

    # Override options
    parser.add_argument("--model", help="Override model for all configs")
    parser.add_argument("--num-deliveries", type=int, help="Override number of deliveries")
    parser.add_argument("--difficulty", choices=["easy", "medium", "hard"],
                        help="Override difficulty for all configs")

    # Output options
    parser.add_argument("--quiet", "-q", action="store_true", help="Minimal output (CI friendly)")
    parser.add_argument("--json-summary", action="store_true",
                        help="Print JSON summary to stdout (for CI parsing)")

    args = parser.parse_args()

    # Build overrides dict
    overrides = {}
    if args.model:
        overrides["model"] = args.model
    if args.num_deliveries:
        overrides["num_deliveries"] = args.num_deliveries
    if args.difficulty:
        overrides["difficulty"] = args.difficulty

    # Load config
    try:
        run_config = load_config(args.config, overrides if overrides else None)
    except FileNotFoundError:
        print(f"Error: Config file not found: {args.config}", file=sys.stderr)
        return 1
    except json.JSONDecodeError as e:
        print(f"Error: Invalid JSON in config file: {e}", file=sys.stderr)
        return 1

    # Determine hindsight URL: CLI arg takes priority, then first config's hindsight_url, then default
    hindsight_url = args.hindsight_url
    if hindsight_url == "http://localhost:8888" and run_config.configs:
        # CLI arg is default, check if config specifies a URL
        first_config_url = run_config.configs[0].hindsight_url
        if first_config_url:
            hindsight_url = first_config_url

    # Get the seed (same for all configs)
    seed_used = run_config.configs[0].seed if run_config.configs else None

    if not args.quiet:
        print(f"Loaded {len(run_config.configs)} config(s) from {args.config}")
        print(f"Run name: {run_config.run_name}")
        print(f"Seed: {seed_used}")
        print(f"Hindsight URL: {hindsight_url}")
        print(f"Charts: {'enabled' if run_config.generate_charts else 'disabled'}")
        print(f"Detailed logs: {'enabled' if run_config.save_detailed_logs else 'disabled'}")

    # Initialize memory service with default URL (per-config URLs handled in benchmark_service)
    initialize_memory(hindsight_url)

    # Create output directory with timestamp
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    run_dir_name = f"{run_config.run_name}_{timestamp}"
    run_dir = RESULTS_DIR / run_dir_name
    run_dir.mkdir(parents=True, exist_ok=True)

    if not args.quiet:
        print(f"Output directory: {run_dir}")

    # Run all configs in parallel
    if not args.quiet:
        print(f"\nRunning {len(run_config.configs)} configs in parallel...")
        for i, config in enumerate(run_config.configs, 1):
            print(f"  {i}. {config.display_name} (mode: {config.mode.value}, bank: {config.bank_id})")
        print()

    async def run_single_config(config: BenchmarkConfig, index: int):
        """Run a single config and return results with index for ordering."""
        if not args.quiet:
            print(f"[{index}] Starting: {config.display_name}")
        result = await run_benchmark(config)
        if not args.quiet:
            print(f"[{index}] Completed: {config.display_name} - "
                  f"{result.successful_deliveries}/{result.total_deliveries} success, "
                  f"{result.avg_path_efficiency:.1%} efficiency")
        return index, result

    # Run all configs concurrently
    tasks = [
        run_single_config(config, i)
        for i, config in enumerate(run_config.configs, 1)
    ]
    results_with_indices = await asyncio.gather(*tasks)

    # Sort by original index to maintain config order
    results_with_indices.sort(key=lambda x: x[0])
    all_results = [result.to_dict() for _, result in results_with_indices]

    if not args.quiet:
        print(f"\n{'='*50}")
        print("ALL CONFIGS COMPLETED")
        print(f"{'='*50}")
        for i, (_, result) in enumerate(results_with_indices, 1):
            config = run_config.configs[i-1]
            print(f"\n{i}. {config.display_name}:")
            print(f"   Success rate: {result.successful_deliveries}/{result.total_deliveries}")
            print(f"   Avg efficiency: {result.avg_path_efficiency:.1%}")
            print(f"   Avg error rate: {result.avg_error_rate:.1%}")
            print(f"   Total steps: {result.total_steps} (optimal: {result.total_optimal_steps})")

    # Save results (main JSON file)
    if not args.quiet:
        print(f"\nSaving results...")

    # Create summary results (strip action logs from main file)
    summary_results = []
    for result in all_results:
        summary_result = {
            "config": result["config"],
            "summary": result["summary"],
            "learning": result["learning"],
            "timeSeries": result["timeSeries"],
            # Strip actions from deliveries for summary
            "deliveries": [
                {k: v for k, v in d.items() if k != "actions"}
                for d in result.get("deliveries", [])
            ],
        }
        summary_results.append(summary_result)

    # Save main results file
    results_path = run_dir / "results.json"
    results_data = {
        "savedAt": datetime.now().isoformat(),
        "runName": run_config.run_name,
        "numConfigs": len(summary_results),
        "results": summary_results,
    }
    with open(results_path, "w") as f:
        json.dump(results_data, f, indent=2, default=str)

    if not args.quiet:
        print(f"  Saved: {results_path.name}")

    # Save configurations document
    if not args.quiet:
        print("\nSaving configurations document...")
    save_configurations_doc(run_config.configs, run_dir, seed=seed_used, quiet=args.quiet)

    # Save detailed logs if enabled
    if run_config.save_detailed_logs:
        if not args.quiet:
            print("\nSaving detailed logs...")
        save_detailed_logs(all_results, run_dir, args.quiet)

    # Generate charts if enabled
    if run_config.generate_charts:
        if not args.quiet:
            print("\nGenerating charts...")
        generate_charts(all_results, run_dir, args.quiet)

    # Save summary of findings
    if not args.quiet:
        print("\nSaving summary of findings...")
    save_summary_of_findings(all_results, run_dir, args.quiet)

    if not args.quiet:
        print(f"\nAll files saved to: {run_dir}")

    # Print summary and check thresholds
    passed = print_summary(all_results, args.min_success_rate, args.max_error_rate)

    # JSON summary for CI parsing
    if args.json_summary:
        def extract_summary(r):
            s = r.get("summary", r)
            cfg = r.get("config", {})
            return {
                "name": cfg.get("name") or cfg.get("mode", r.get("mode")),
                "success_rate": s.get("successfulDeliveries", s.get("successful_deliveries", 0)) / max(s.get("totalDeliveries", s.get("total_deliveries", 1)), 1),
                "avg_error_rate": s.get("avgErrorRate", s.get("avg_error_rate", 0)),
                "avg_path_efficiency": s.get("avgPathEfficiency", s.get("avg_path_efficiency", 0)),
            }

        summary = {
            "passed": passed,
            "results": [extract_summary(r) for r in all_results],
            "output_dir": str(run_dir),
        }
        print("\n--- JSON SUMMARY ---")
        print(json.dumps(summary, indent=2))

    return 0 if passed else 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
