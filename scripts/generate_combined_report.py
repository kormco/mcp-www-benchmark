"""Generate the benchmark report.

Compares mcp-www (browse_discover) vs HTTP (/.well-known/mcp) for MCP
server discovery. Includes real-world results and 50% adoption simulation
if available.
"""

import json
import os
import sys
from pathlib import Path

import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from config import METHOD_LABELS, METHODS, REPORT_DIR
from src.models import QueryResult
from analysis.stats import load_all_results, analyze_all, group_results, descriptive_stats


SIM_RESULTS_DIR = PROJECT_ROOT / "results" / "sim_50pct"
REPORT_OUTPUT_DIR = PROJECT_ROOT / "results" / "report"
COLORS = {"mcp_www": "#2196F3", "http_well_known": "#FF9800"}


def load_jsonl_results(results_dir) -> list:
    results = []
    for filepath in Path(results_dir).glob("*.jsonl"):
        with open(filepath) as f:
            for line in f:
                line = line.strip()
                if line:
                    r = QueryResult.from_json(line)
                    if r.method in METHODS:
                        results.append(r)
    return results


def build_summary_table(results):
    """Build a markdown summary table from results."""
    groups = group_results(results)
    groups = {k: v for k, v in groups.items() if k[2] not in ("warmup",)}

    rows = []
    for key in sorted(groups.keys(), key=lambda k: (k[0], k[1], k[2])):
        method, concurrency, cache = key
        group = groups[key]
        latencies = np.array([r.latency_ms for r in group])
        success_rate = sum(1 for r in group if r.success) / len(group)
        mcp_rate = sum(1 for r in group if r.mcp_server_found) / len(group)
        desc = descriptive_stats(latencies)

        total_time = sum(r.latency_ms for r in group) / 1000
        throughput = len(group) / total_time if total_time > 0 else 0

        label = METHOD_LABELS.get(method, method)
        rows.append(
            f"| {label} | c{concurrency} | {cache} | "
            f"{desc['median']:.1f} | {desc['p95']:.1f} | {desc['p99']:.1f} | "
            f"{success_rate*100:.1f} | {mcp_rate*100:.1f} | {throughput:.1f} |"
        )

    header = (
        "| Method | Concurrency | Cache | Median (ms) | P95 (ms) | P99 (ms) | Success % | MCP Found % | Throughput (q/s) |\n"
        "|--------|-------------|-------|-------------|----------|----------|-----------|-------------|------------------|"
    )
    return header + "\n" + "\n".join(rows)


def build_comparison_table(results):
    """Build statistical comparison table."""
    analysis = analyze_all([r for r in results if r.cache_state != "warmup"])

    rows = []
    for comp in analysis["comparisons"]:
        sig = "Yes" if comp["significant"] else "No"
        rows.append(
            f"| {comp['comparison']} | {comp['concurrency']} | {comp['cache_state']} | "
            f"{comp['median_a']:.1f} | {comp['median_b']:.1f} | "
            f"{comp['speedup']:.2f}x | {comp['p_value']:.2e} | {sig} | "
            f"{comp['cohens_d']:.3f} |"
        )

    header = (
        "| Comparison | Concurrency | Cache | Median A (ms) | Median B (ms) | Speedup | p-value | Significant | Effect Size |\n"
        "|------------|-------------|-------|---------------|---------------|---------|---------|-------------|-------------|"
    )
    return header + "\n" + "\n".join(rows)


def plot_latency_cdf(results, cache_state, suffix=""):
    """Latency CDF for each concurrency level."""
    groups = group_results(results)
    methods = sorted(set(k[0] for k in groups))

    concurrencies = sorted(set(k[1] for k in groups if k[2] == cache_state))
    if not concurrencies:
        return None

    fig, axes = plt.subplots(1, len(concurrencies), figsize=(5 * len(concurrencies), 5))
    if len(concurrencies) == 1:
        axes = [axes]

    for ax, c in zip(axes, concurrencies):
        for method in methods:
            key = (method, c, cache_state)
            if key not in groups:
                continue
            latencies = sorted([r.latency_ms for r in groups[key]])
            cdf = np.arange(1, len(latencies) + 1) / len(latencies)
            ax.plot(latencies, cdf, label=METHOD_LABELS.get(method, method),
                    color=COLORS.get(method, "gray"), linewidth=2)
        ax.set_title(f"c={c}")
        ax.set_xlabel("Latency (ms)")
        ax.set_ylabel("CDF")
        ax.set_xscale("log")
        ax.legend(fontsize=7)
        ax.grid(True, alpha=0.3)

    fig.suptitle(f"Latency CDF ({cache_state} cache){suffix}", fontsize=14)
    plt.tight_layout()
    fname = f"latency_cdf_{cache_state}{suffix.replace(' ', '_').lower()}.png"
    path = os.path.join(REPORT_OUTPUT_DIR, fname)
    fig.savefig(path, dpi=150, bbox_inches="tight")
    plt.close(fig)
    return fname


def plot_throughput(results, cache_state, suffix=""):
    """Throughput vs concurrency."""
    groups = group_results(results)
    methods = sorted(set(k[0] for k in groups))
    concurrencies = sorted(set(k[1] for k in groups if k[2] == cache_state))
    if not concurrencies:
        return None

    fig, ax = plt.subplots(figsize=(10, 6))

    for method in methods:
        throughputs = []
        for c in concurrencies:
            key = (method, c, cache_state)
            if key in groups:
                group = groups[key]
                wall_clock = max(r.timestamp_end for r in group) - min(r.timestamp_start for r in group)
                throughputs.append(len(group) / wall_clock if wall_clock > 0 else 0)
            else:
                throughputs.append(0)
        ax.plot(concurrencies, throughputs, marker="o",
                label=METHOD_LABELS.get(method, method),
                color=COLORS.get(method, "gray"), linewidth=2)

    ax.set_xlabel("Concurrency Level")
    ax.set_ylabel("Throughput (q/s)")
    ax.set_title(f"Throughput vs Concurrency ({cache_state} cache){suffix}")
    ax.legend()
    ax.grid(True, alpha=0.3)

    fname = f"throughput_{cache_state}{suffix.replace(' ', '_').lower()}.png"
    path = os.path.join(REPORT_OUTPUT_DIR, fname)
    fig.savefig(path, dpi=150, bbox_inches="tight")
    plt.close(fig)
    return fname


def generate_combined_report():
    os.makedirs(REPORT_OUTPUT_DIR, exist_ok=True)

    print("Loading results...")
    current_results = load_jsonl_results(PROJECT_ROOT / "results" / "raw")
    current_results = [r for r in current_results if r.cache_state != "warmup"]

    sim_results = []
    if SIM_RESULTS_DIR.exists():
        sim_results = load_jsonl_results(SIM_RESULTS_DIR)

    print(f"  Current run:    {len(current_results)} results")
    print(f"  Simulation:     {len(sim_results)} results")

    # Generate charts
    print("Generating charts...")
    charts = []
    for cache in ["cold", "warm"]:
        c = plot_latency_cdf(current_results, cache)
        if c:
            charts.append(c)
        t = plot_throughput(current_results, cache)
        if t:
            charts.append(t)

    sim_charts = []
    if sim_results:
        c = plot_latency_cdf(sim_results, "cold", suffix=" — 50% Adoption Sim")
        if c:
            sim_charts.append(c)
        t = plot_throughput(sim_results, "cold", suffix=" — 50% Adoption Sim")
        if t:
            sim_charts.append(t)

    # Build report
    report = []
    groups = group_results(current_results)

    report.append("# MCP Discovery Benchmark Report\n")
    report.append(
        "This benchmark compares two approaches to discovering MCP (Model Context Protocol) "
        "servers at scale:\n"
        "- **mcp-www** (`browse_discover`): DNS TXT lookup for `_mcp.{domain}` + manifest "
        "fetch from the advertised server URL\n"
        "- **HTTP** (`/.well-known/mcp`): Direct HTTPS GET to a well-known endpoint\n"
    )
    report.append(
        "mcp-www is tested as the actual npm package running as a subprocess, called via "
        "JSON-RPC over stdio. This measures the real end-to-end tool invocation, not raw DNS.\n"
    )

    # ── Setup ──
    report.append("## Setup\n")
    report.append("| Parameter | Value |")
    report.append("|-----------|-------|")
    report.append("| **Platform** | Linux (Ubuntu) |")
    report.append("| **DNS Resolver** | Unbound on Synology NAS (`192.168.68.133:5335`) |")
    report.append(f"| **Methods** | {', '.join(METHOD_LABELS.values())} |")
    report.append("| **Concurrency** | 1, 10, 50, 100, 500 |")
    report.append("| **Cache States** | Cold, Warm |")
    report.append(f"| **Total Queries** | {len(current_results)} |")
    report.append("| **Domains** | 201 across 5 categories |")
    report.append("| **Runs/Config** | 3 |")
    report.append("| **mcp-www** | Local build from `kormco/mcp-www` (browse_discover tool) |")
    report.append("")

    # ── Results ──
    report.append("## Results\n")
    report.append("### Latency Summary\n")
    report.append(build_summary_table(current_results))
    report.append("")

    report.append("### Statistical Comparisons\n")
    report.append(build_comparison_table(current_results))
    report.append("")

    # Charts
    report.append("### Charts\n")
    for fname in charts:
        title = fname.replace("_", " ").replace(".png", "").title()
        report.append(f"#### {title}\n")
        report.append(f"![{title}]({fname})\n")

    # ── Key findings ──
    report.append("## Key Findings\n")

    mcp_c1 = np.median([r.latency_ms for r in groups.get(("mcp_www", 1, "cold"), [])]) if ("mcp_www", 1, "cold") in groups else 0
    http_c1 = np.median([r.latency_ms for r in groups.get(("http_well_known", 1, "cold"), [])]) if ("http_well_known", 1, "cold") in groups else 0
    mcp_c500 = np.median([r.latency_ms for r in groups.get(("mcp_www", 500, "cold"), [])]) if ("mcp_www", 500, "cold") in groups else 0
    http_c500 = np.median([r.latency_ms for r in groups.get(("http_well_known", 500, "cold"), [])]) if ("http_well_known", 500, "cold") in groups else 0

    if mcp_c1 > 0 and http_c1 > 0:
        report.append(f"- **At c=1 (cold):** mcp-www {mcp_c1:.1f}ms vs HTTP {http_c1:.1f}ms ({http_c1/mcp_c1:.0f}x)")
    if mcp_c500 > 0 and http_c500 > 0:
        report.append(f"- **At c=500 (cold):** mcp-www {mcp_c500:.1f}ms vs HTTP {http_c500:.1f}ms ({http_c500/mcp_c500:.0f}x)")

    # Success rates at high concurrency
    mcp_c500_group = groups.get(("mcp_www", 500, "cold"), [])
    http_c500_group = groups.get(("http_well_known", 500, "cold"), [])
    if mcp_c500_group and http_c500_group:
        mcp_success = sum(1 for r in mcp_c500_group if r.success) / len(mcp_c500_group)
        http_success = sum(1 for r in http_c500_group if r.success) / len(http_c500_group)
        report.append(f"- **Success at c=500 (cold):** mcp-www {mcp_success*100:.0f}% vs HTTP {http_success*100:.0f}%")
    report.append("")

    # ── Simulation ──
    if sim_results:
        report.append("## 50% Adoption Simulation\n")
        report.append(
            "Simulated 50% MCP adoption (100/201 domains have MCP servers). "
            "Uses local DNS and HTTP sim servers with latency injected from "
            "real cold-cache distributions. mcp-www runs against the sim DNS server.\n"
        )

        report.append("### Simulation Results\n")
        report.append(build_summary_table(sim_results))
        report.append("")

        report.append("### Simulation Statistical Comparisons\n")
        report.append(build_comparison_table(sim_results))
        report.append("")

        report.append("### Simulation Charts\n")
        for fname in sim_charts:
            title = fname.replace("_", " ").replace(".png", "").title()
            report.append(f"#### {title}\n")
            report.append(f"![{title}]({fname})\n")

    # ── Methodology ──
    report.append("## Methodology\n")
    report.append("- **mcp-www prober:** Spawns `node dist/index.js` subprocess, sends `browse_discover` "
                  "calls via JSON-RPC over stdio. Single process handles all concurrent requests.")
    report.append("- **HTTP prober:** Direct `httpx.AsyncClient` GET to `https://{domain}/.well-known/mcp`")
    report.append("- **Statistical tests:** Mann-Whitney U (non-parametric) with Bonferroni correction")
    report.append("- **Effect sizes:** Cohen's d and rank-biserial correlation")
    report.append("- **Confidence intervals:** Bootstrap (10,000 resamples) on medians")
    report.append("- **Domain list:** 201 domains across 5 categories (MCP-enabled, popular, nonexistent, slow, HTTPS-only)")
    report.append("- **Reproducibility seed:** 42")
    report.append("")

    report.append("## Reproducibility\n")
    report.append("```bash")
    report.append("pip install -r requirements.txt")
    report.append("cd ../mcp-www && npm install && npm run build  # build mcp-www locally")
    report.append("cd ../mcp-www-benchmark")
    report.append("python scripts/run_experiment.py")
    report.append("python scripts/analyze_results.py")
    report.append("python scripts/generate_combined_report.py")
    report.append("```\n")

    # Write report
    report_path = os.path.join(REPORT_OUTPUT_DIR, "report.md")
    with open(report_path, "w") as f:
        f.write("\n".join(report))

    print(f"\nReport written to {report_path}")
    return report_path


if __name__ == "__main__":
    generate_combined_report()
