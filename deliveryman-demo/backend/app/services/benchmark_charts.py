"""Chart generation for benchmark results using matplotlib."""

import io
from pathlib import Path
from typing import Optional
import matplotlib
matplotlib.use('Agg')  # Non-interactive backend for server use
import matplotlib.pyplot as plt
import numpy as np


def generate_dashboard_chart(
    results: dict,
    output_path: Optional[Path] = None,
) -> bytes:
    """Generate a dashboard chart with multiple metrics.

    Args:
        results: Benchmark results dictionary (from BenchmarkResults.to_dict())
        output_path: Optional path to save the SVG file

    Returns:
        SVG content as bytes
    """
    config = results["config"]
    summary = results["summary"]
    learning = results["learning"]
    time_series = results["timeSeries"]
    deliveries = results["deliveries"]

    # Create figure with 3x2 grid
    fig, axes = plt.subplots(2, 3, figsize=(15, 10))
    fig.suptitle(
        f'Benchmark Dashboard - {config["mode"]} ({config["difficulty"]})',
        fontsize=14,
        fontweight='bold'
    )

    # Color scheme
    primary_color = '#3b82f6'
    success_color = '#22c55e'
    warning_color = '#f59e0b'

    episodes = list(range(1, len(time_series["efficiencyByEpisode"]) + 1))

    # 1. Path Efficiency over time
    ax1 = axes[0, 0]
    efficiencies = [e * 100 for e in time_series["efficiencyByEpisode"]]
    colors = [warning_color if d.get("isRepeat") else primary_color for d in deliveries]
    ax1.bar(episodes, efficiencies, color=colors, alpha=0.7)
    ax1.axhline(y=90, color=success_color, linestyle='--', label='90% Target')
    ax1.set_xlabel('Delivery')
    ax1.set_ylabel('Efficiency (%)')
    ax1.set_title('Path Efficiency')
    ax1.set_ylim(0, 105)
    ax1.legend(loc='lower right', fontsize=8)

    # 2. Steps per delivery
    ax2 = axes[0, 1]
    steps = [d["stepsTaken"] for d in deliveries]
    optimal = [d["optimalSteps"] for d in deliveries]
    x = np.arange(len(episodes))
    width = 0.35
    ax2.bar(x - width/2, steps, width, label='Actual', color=primary_color, alpha=0.7)
    ax2.bar(x + width/2, optimal, width, label='Optimal', color=success_color, alpha=0.7)
    ax2.set_xlabel('Delivery')
    ax2.set_ylabel('Steps')
    ax2.set_title('Steps Per Delivery')
    ax2.legend(loc='upper right', fontsize=8)
    ax2.set_xticks(x)
    ax2.set_xticklabels(episodes)

    # 3. Cumulative steps
    ax3 = axes[0, 2]
    cum_steps = np.cumsum(steps)
    cum_optimal = np.cumsum(optimal)
    ax3.plot(episodes, cum_steps, color=primary_color, linewidth=2, label='Actual')
    ax3.plot(episodes, cum_optimal, color=success_color, linewidth=2, linestyle='--', label='Optimal')
    ax3.fill_between(episodes, cum_optimal, cum_steps, alpha=0.2, color='red')
    ax3.set_xlabel('Delivery')
    ax3.set_ylabel('Cumulative Steps')
    ax3.set_title('Cumulative Steps')
    ax3.legend(loc='upper left', fontsize=8)

    # 4. Latency per delivery
    ax4 = axes[1, 0]
    latencies = [d["latencyMs"] / 1000 for d in deliveries]  # Convert to seconds
    ax4.bar(episodes, latencies, color=primary_color, alpha=0.7)
    avg_latency = sum(latencies) / len(latencies) if latencies else 0
    ax4.axhline(y=avg_latency, color=warning_color, linestyle='--', label=f'Avg: {avg_latency:.1f}s')
    ax4.set_xlabel('Delivery')
    ax4.set_ylabel('Latency (s)')
    ax4.set_title('Latency Per Delivery')
    ax4.legend(loc='upper right', fontsize=8)

    # 5. Tokens per delivery
    ax5 = axes[1, 1]
    tokens = time_series["tokensByEpisode"]
    ax5.bar(episodes, tokens, color=primary_color, alpha=0.7)
    avg_tokens = sum(tokens) / len(tokens) if tokens else 0
    ax5.axhline(y=avg_tokens, color=warning_color, linestyle='--', label=f'Avg: {avg_tokens:.0f}')
    ax5.set_xlabel('Delivery')
    ax5.set_ylabel('Tokens')
    ax5.set_title('Tokens Per Delivery')
    ax5.legend(loc='upper right', fontsize=8)

    # 6. Summary stats
    ax6 = axes[1, 2]
    ax6.axis('off')

    stats_text = f"""
    Summary Statistics
    ──────────────────
    Mode: {config['mode']}
    Difficulty: {config['difficulty']}
    Deliveries: {summary['totalDeliveries']}

    Success Rate: {summary['successRate']*100:.1f}%
    Avg Efficiency: {summary['avgPathEfficiency']*100:.1f}%

    Total Steps: {summary['totalSteps']}
    Optimal Steps: {summary['totalOptimalSteps']}

    Total Tokens: {summary['totalTokens']['total']:,}
    Avg Latency: {summary['avgLatencyMs']/1000:.1f}s

    Learning Metrics
    ──────────────────
    Convergence: Episode {learning['convergenceEpisode'] or 'N/A'}
    1st Half Eff: {learning['firstHalfEfficiency']*100:.1f}%
    2nd Half Eff: {learning['secondHalfEfficiency']*100:.1f}%
    Improvement: {learning['improvement']*100:+.1f}%
    """

    ax6.text(0.1, 0.9, stats_text, transform=ax6.transAxes, fontsize=10,
             verticalalignment='top', fontfamily='monospace',
             bbox=dict(boxstyle='round', facecolor='#f8fafc', edgecolor='#e2e8f0'))

    plt.tight_layout()

    # Save to bytes
    buf = io.BytesIO()
    plt.savefig(buf, format='svg', dpi=150, bbox_inches='tight')
    plt.close(fig)
    buf.seek(0)
    svg_content = buf.read()

    # Optionally save to file
    if output_path:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_bytes(svg_content)

    return svg_content


def generate_comparison_chart(
    results_list: list[dict],
    output_path: Optional[Path] = None,
) -> bytes:
    """Generate a comparison chart for multiple benchmark runs.

    Args:
        results_list: List of benchmark results dictionaries
        output_path: Optional path to save the SVG file

    Returns:
        SVG content as bytes
    """
    if not results_list:
        return b''

    # Create figure with 2x3 grid
    fig, axes = plt.subplots(2, 3, figsize=(15, 10))
    fig.suptitle('Benchmark Comparison Summary', fontsize=14, fontweight='bold')

    # Extract data
    modes = [r["config"]["mode"] for r in results_list]
    colors = plt.cm.Set2(np.linspace(0, 1, len(results_list)))

    # 1. Average Path Efficiency
    ax1 = axes[0, 0]
    efficiencies = [r["summary"]["avgPathEfficiency"] * 100 for r in results_list]
    bars = ax1.bar(modes, efficiencies, color=colors)
    ax1.axhline(y=90, color='green', linestyle='--', alpha=0.5)
    ax1.set_ylabel('Efficiency (%)')
    ax1.set_title('Average Path Efficiency')
    ax1.set_ylim(0, 105)
    for bar, eff in zip(bars, efficiencies):
        ax1.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 1,
                f'{eff:.1f}%', ha='center', va='bottom', fontsize=9)

    # 2. Success Rate
    ax2 = axes[0, 1]
    success_rates = [r["summary"]["successRate"] * 100 for r in results_list]
    bars = ax2.bar(modes, success_rates, color=colors)
    ax2.set_ylabel('Success Rate (%)')
    ax2.set_title('Success Rate')
    ax2.set_ylim(0, 105)
    for bar, rate in zip(bars, success_rates):
        ax2.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 1,
                f'{rate:.1f}%', ha='center', va='bottom', fontsize=9)

    # 3. Average Steps
    ax3 = axes[0, 2]
    avg_steps = [r["summary"]["totalSteps"] / r["summary"]["totalDeliveries"]
                 for r in results_list if r["summary"]["totalDeliveries"] > 0]
    bars = ax3.bar(modes[:len(avg_steps)], avg_steps, color=colors[:len(avg_steps)])
    ax3.set_ylabel('Avg Steps')
    ax3.set_title('Average Steps Per Delivery')
    for bar, steps in zip(bars, avg_steps):
        ax3.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 0.1,
                f'{steps:.1f}', ha='center', va='bottom', fontsize=9)

    # 4. Total Tokens
    ax4 = axes[1, 0]
    total_tokens = [r["summary"]["totalTokens"]["total"] for r in results_list]
    bars = ax4.bar(modes, total_tokens, color=colors)
    ax4.set_ylabel('Total Tokens')
    ax4.set_title('Total Token Usage')
    for bar, tokens in zip(bars, total_tokens):
        ax4.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 100,
                f'{tokens:,}', ha='center', va='bottom', fontsize=8)

    # 5. Average Latency
    ax5 = axes[1, 1]
    avg_latencies = [r["summary"]["avgLatencyMs"] / 1000 for r in results_list]
    bars = ax5.bar(modes, avg_latencies, color=colors)
    ax5.set_ylabel('Avg Latency (s)')
    ax5.set_title('Average Latency')
    for bar, lat in zip(bars, avg_latencies):
        ax5.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 0.1,
                f'{lat:.1f}s', ha='center', va='bottom', fontsize=9)

    # 6. Learning Improvement
    ax6 = axes[1, 2]
    improvements = [r["learning"]["improvement"] * 100 for r in results_list]
    bar_colors = ['green' if imp > 0 else 'red' for imp in improvements]
    bars = ax6.bar(modes, improvements, color=bar_colors, alpha=0.7)
    ax6.axhline(y=0, color='gray', linestyle='-', alpha=0.5)
    ax6.set_ylabel('Improvement (%)')
    ax6.set_title('Learning Improvement (2nd vs 1st Half)')
    for bar, imp in zip(bars, improvements):
        ax6.text(bar.get_x() + bar.get_width()/2,
                bar.get_height() + (1 if imp >= 0 else -3),
                f'{imp:+.1f}%', ha='center', va='bottom', fontsize=9)

    # Rotate x-axis labels for readability
    for ax in axes.flat:
        plt.setp(ax.xaxis.get_majorticklabels(), rotation=45, ha='right')

    plt.tight_layout()

    # Save to bytes
    buf = io.BytesIO()
    plt.savefig(buf, format='svg', dpi=150, bbox_inches='tight')
    plt.close(fig)
    buf.seek(0)
    svg_content = buf.read()

    # Optionally save to file
    if output_path:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_bytes(svg_content)

    return svg_content
