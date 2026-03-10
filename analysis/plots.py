"""Chart generation for experiment results."""

import os
from typing import Dict, List

import numpy as np
import matplotlib.pyplot as plt
import matplotlib

matplotlib.use("Agg")  # Non-interactive backend

from config import REPORT_DIR, METHOD_LABELS
from src.models import QueryResult
from analysis.stats import group_results

COLORS = {
    "dns_mcp": "#2196F3",
    "http_well_known": "#FF9800",
    "website_scrape": "#F44336",
}


def _ensure_dir():
    os.makedirs(REPORT_DIR, exist_ok=True)


def plot_latency_cdf(results: List[QueryResult], cache_state: str = "cold"):
    """CDF of latency per method, one subplot per concurrency level."""
    _ensure_dir()
    groups = group_results(results)

    concurrency_levels = sorted(set(k[1] for k in groups if k[2] == cache_state))
    methods = sorted(set(k[0] for k in groups))

    fig, axes = plt.subplots(1, len(concurrency_levels), figsize=(5 * len(concurrency_levels), 5))
    if len(concurrency_levels) == 1:
        axes = [axes]

    for ax, concurrency in zip(axes, concurrency_levels):
        for method in methods:
            key = (method, concurrency, cache_state)
            if key not in groups:
                continue
            latencies = sorted([r.latency_ms for r in groups[key]])
            cdf = np.arange(1, len(latencies) + 1) / len(latencies)
            label = METHOD_LABELS.get(method, method)
            ax.plot(latencies, cdf, label=label, color=COLORS.get(method, "gray"), linewidth=2)

        ax.set_title(f"Concurrency = {concurrency}")
        ax.set_xlabel("Latency (ms)")
        ax.set_ylabel("CDF")
        ax.set_xscale("log")
        ax.legend(fontsize=8)
        ax.grid(True, alpha=0.3)

    fig.suptitle(f"Latency CDF by Discovery Method ({cache_state} cache)", fontsize=14)
    plt.tight_layout()
    path = os.path.join(REPORT_DIR, f"latency_cdf_{cache_state}.png")
    fig.savefig(path, dpi=150, bbox_inches="tight")
    plt.close(fig)
    return path


def plot_throughput_vs_concurrency(results: List[QueryResult], cache_state: str = "cold"):
    """Line chart: throughput (q/s) vs concurrency level."""
    _ensure_dir()
    groups = group_results(results)

    methods = sorted(set(k[0] for k in groups))
    concurrency_levels = sorted(set(k[1] for k in groups if k[2] == cache_state))

    fig, ax = plt.subplots(figsize=(10, 6))

    for method in methods:
        throughputs = []
        for concurrency in concurrency_levels:
            key = (method, concurrency, cache_state)
            if key not in groups:
                throughputs.append(0)
                continue
            group = groups[key]
            total_time_s = sum(r.latency_ms for r in group) / 1000
            # Effective throughput: queries / wall clock (approximated by max latency in batch)
            latencies = [r.latency_ms for r in group]
            if latencies:
                # Wall clock ~ max(latency) when running concurrently
                wall_clock = max(r.timestamp_end for r in group) - min(r.timestamp_start for r in group)
                if wall_clock > 0:
                    throughputs.append(len(group) / wall_clock)
                else:
                    throughputs.append(0)
            else:
                throughputs.append(0)

        label = METHOD_LABELS.get(method, method)
        ax.plot(
            concurrency_levels, throughputs,
            marker="o", label=label, color=COLORS.get(method, "gray"), linewidth=2,
        )

    ax.set_xlabel("Concurrency Level")
    ax.set_ylabel("Throughput (queries/sec)")
    ax.set_title(f"Throughput vs Concurrency ({cache_state} cache)")
    ax.legend()
    ax.grid(True, alpha=0.3)

    path = os.path.join(REPORT_DIR, f"throughput_vs_concurrency_{cache_state}.png")
    fig.savefig(path, dpi=150, bbox_inches="tight")
    plt.close(fig)
    return path


def plot_latency_boxplots(results: List[QueryResult], concurrency: int = 50, cache_state: str = "cold"):
    """Box plots of latency by domain category for each method."""
    _ensure_dir()
    groups = group_results(results)
    methods = sorted(set(k[0] for k in groups))
    categories = sorted(set(r.category for r in results))

    fig, axes = plt.subplots(1, len(methods), figsize=(6 * len(methods), 6), sharey=True)
    if len(methods) == 1:
        axes = [axes]

    for ax, method in zip(axes, methods):
        key = (method, concurrency, cache_state)
        if key not in groups:
            continue

        data_by_cat = {}
        for r in groups[key]:
            data_by_cat.setdefault(r.category, []).append(r.latency_ms)

        cats = sorted(data_by_cat.keys())
        data = [data_by_cat[c] for c in cats]

        bp = ax.boxplot(data, labels=cats, patch_artist=True, showfliers=False)
        for patch in bp["boxes"]:
            patch.set_facecolor(COLORS.get(method, "gray"))
            patch.set_alpha(0.6)

        label = METHOD_LABELS.get(method, method)
        ax.set_title(label, fontsize=11)
        ax.set_xlabel("Domain Category")
        ax.set_ylabel("Latency (ms)")
        ax.grid(True, alpha=0.3, axis="y")

    fig.suptitle(f"Latency by Domain Category (concurrency={concurrency}, {cache_state})", fontsize=14)
    plt.tight_layout()
    path = os.path.join(REPORT_DIR, f"latency_by_category_c{concurrency}_{cache_state}.png")
    fig.savefig(path, dpi=150, bbox_inches="tight")
    plt.close(fig)
    return path


def plot_bandwidth_comparison(results: List[QueryResult], cache_state: str = "cold"):
    """Bar chart comparing bandwidth consumed per method."""
    _ensure_dir()
    groups = group_results(results)
    methods = sorted(set(k[0] for k in groups))

    # Aggregate bandwidth across all concurrency levels
    bandwidth = {}
    query_count = {}
    for method in methods:
        total_recv = 0
        total_sent = 0
        count = 0
        for key, group in groups.items():
            if key[0] == method and key[2] == cache_state:
                total_recv += sum(r.bytes_received for r in group)
                total_sent += sum(r.bytes_sent for r in group)
                count += len(group)
        if count > 0:
            bandwidth[method] = {
                "avg_recv": total_recv / count,
                "avg_sent": total_sent / count,
                "avg_total": (total_recv + total_sent) / count,
            }

    fig, ax = plt.subplots(figsize=(8, 5))
    x = np.arange(len(bandwidth))
    width = 0.35

    methods_sorted = sorted(bandwidth.keys())
    sent = [bandwidth[m]["avg_sent"] for m in methods_sorted]
    recv = [bandwidth[m]["avg_recv"] for m in methods_sorted]
    labels = [METHOD_LABELS.get(m, m) for m in methods_sorted]
    colors = [COLORS.get(m, "gray") for m in methods_sorted]

    ax.bar(x - width / 2, sent, width, label="Bytes Sent", alpha=0.7, color=colors)
    ax.bar(x + width / 2, recv, width, label="Bytes Received", alpha=0.7,
           color=[c + "88" for c in colors] if all(len(c) == 7 for c in colors) else colors)

    ax.set_xlabel("Discovery Method")
    ax.set_ylabel("Avg Bytes per Query")
    ax.set_title(f"Bandwidth per Query ({cache_state} cache)")
    ax.set_xticks(x)
    ax.set_xticklabels(labels, rotation=15, ha="right")
    ax.legend()
    ax.grid(True, alpha=0.3, axis="y")

    path = os.path.join(REPORT_DIR, f"bandwidth_{cache_state}.png")
    fig.savefig(path, dpi=150, bbox_inches="tight")
    plt.close(fig)
    return path


def generate_all_plots(results: List[QueryResult]) -> List[str]:
    """Generate all charts and return list of file paths."""
    paths = []
    cache_states = sorted(set(r.cache_state for r in results if r.cache_state not in ("warmup",)))
    concurrency_levels = sorted(set(r.concurrency_level for r in results))

    for cache in cache_states:
        paths.append(plot_latency_cdf(results, cache))
        paths.append(plot_throughput_vs_concurrency(results, cache))
        paths.append(plot_bandwidth_comparison(results, cache))
        # Box plot at middle concurrency
        mid_c = concurrency_levels[len(concurrency_levels) // 2] if concurrency_levels else 50
        paths.append(plot_latency_boxplots(results, mid_c, cache))

    return paths
