"""Statistical analysis for experiment results."""

import json
import os
from pathlib import Path
from typing import Dict, List, Tuple

import numpy as np
from scipy import stats

from config import RAW_RESULTS_DIR, BOOTSTRAP_SAMPLES, CONFIDENCE_LEVEL, ALPHA, METHODS
from src.models import QueryResult


def load_all_results(results_dir: str = RAW_RESULTS_DIR) -> List[QueryResult]:
    """Load all JSONL result files into a flat list, filtered to configured METHODS."""
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


def group_results(
    results: List[QueryResult],
) -> Dict[Tuple[str, int, str], List[QueryResult]]:
    """Group results by (method, concurrency_level, cache_state)."""
    groups = {}
    for r in results:
        key = (r.method, r.concurrency_level, r.cache_state)
        groups.setdefault(key, []).append(r)
    return groups


def descriptive_stats(latencies: np.ndarray) -> dict:
    """Compute descriptive statistics for a latency array."""
    return {
        "count": len(latencies),
        "mean": float(np.mean(latencies)),
        "median": float(np.median(latencies)),
        "std": float(np.std(latencies)),
        "p5": float(np.percentile(latencies, 5)),
        "p25": float(np.percentile(latencies, 25)),
        "p75": float(np.percentile(latencies, 75)),
        "p95": float(np.percentile(latencies, 95)),
        "p99": float(np.percentile(latencies, 99)),
        "min": float(np.min(latencies)),
        "max": float(np.max(latencies)),
        "iqr": float(np.percentile(latencies, 75) - np.percentile(latencies, 25)),
    }


def bootstrap_ci_median(
    data: np.ndarray,
    n_bootstrap: int = BOOTSTRAP_SAMPLES,
    confidence: float = CONFIDENCE_LEVEL,
) -> Tuple[float, float]:
    """Bootstrap confidence interval for the median."""
    rng = np.random.default_rng(seed=42)
    medians = np.array([
        np.median(rng.choice(data, size=len(data), replace=True))
        for _ in range(n_bootstrap)
    ])
    alpha = (1 - confidence) / 2
    return (
        float(np.percentile(medians, alpha * 100)),
        float(np.percentile(medians, (1 - alpha) * 100)),
    )


def compare_methods(
    latencies_a: np.ndarray,
    latencies_b: np.ndarray,
    label_a: str,
    label_b: str,
    n_comparisons: int = 1,
) -> dict:
    """Compare two methods using Mann-Whitney U test with Bonferroni correction."""
    # Mann-Whitney U test (non-parametric)
    statistic, p_value = stats.mannwhitneyu(
        latencies_a, latencies_b, alternative="two-sided",
    )

    # Bonferroni-corrected alpha
    corrected_alpha = ALPHA / n_comparisons

    # Rank-biserial correlation (effect size for Mann-Whitney)
    n1, n2 = len(latencies_a), len(latencies_b)
    rank_biserial = 1 - (2 * statistic) / (n1 * n2)

    # Cohen's d (parametric effect size for reference)
    pooled_std = np.sqrt(
        (np.var(latencies_a) + np.var(latencies_b)) / 2
    )
    cohens_d = (
        (np.mean(latencies_a) - np.mean(latencies_b)) / pooled_std
        if pooled_std > 0 else 0
    )

    return {
        "comparison": f"{label_a} vs {label_b}",
        "u_statistic": float(statistic),
        "p_value": float(p_value),
        "corrected_alpha": corrected_alpha,
        "significant": p_value < corrected_alpha,
        "rank_biserial": float(rank_biserial),
        "cohens_d": float(cohens_d),
        "median_a": float(np.median(latencies_a)),
        "median_b": float(np.median(latencies_b)),
        "speedup": float(np.median(latencies_b) / np.median(latencies_a))
        if np.median(latencies_a) > 0 else float("inf"),
    }


def analyze_all(results: List[QueryResult]) -> dict:
    """Run the full analysis pipeline."""
    groups = group_results(results)

    # Filter out warmup runs
    groups = {
        k: v for k, v in groups.items()
        if k[2] not in ("warmup",)
    }

    analysis = {
        "summary": {},
        "comparisons": [],
        "by_category": {},
    }

    # Descriptive stats per group
    for key, group in groups.items():
        method, concurrency, cache = key
        latencies = np.array([r.latency_ms for r in group])
        success_rate = sum(1 for r in group if r.success) / len(group) if group else 0
        mcp_found_rate = sum(1 for r in group if r.mcp_server_found) / len(group) if group else 0
        total_bytes_recv = sum(r.bytes_received for r in group)

        desc = descriptive_stats(latencies)
        ci_low, ci_high = bootstrap_ci_median(latencies)

        group_key = f"{method}_c{concurrency}_{cache}"
        analysis["summary"][group_key] = {
            **desc,
            "success_rate": success_rate,
            "mcp_found_rate": mcp_found_rate,
            "total_bytes_received": total_bytes_recv,
            "median_ci_95": [ci_low, ci_high],
            "throughput_qps": len(group) / (sum(r.latency_ms for r in group) / 1000)
            if sum(r.latency_ms for r in group) > 0 else 0,
        }

    # Pairwise comparisons at each concurrency level
    methods_in_data = sorted(set(k[0] for k in groups))
    concurrency_levels = sorted(set(k[1] for k in groups))
    n_comparisons = len(concurrency_levels) * 3  # 3 pairwise comparisons

    for concurrency in concurrency_levels:
        for cache in sorted(set(k[2] for k in groups)):
            method_latencies = {}
            for method in methods_in_data:
                key = (method, concurrency, cache)
                if key in groups:
                    method_latencies[method] = np.array(
                        [r.latency_ms for r in groups[key]]
                    )

            # All pairwise comparisons
            method_list = sorted(method_latencies.keys())
            for i in range(len(method_list)):
                for j in range(i + 1, len(method_list)):
                    m_a, m_b = method_list[i], method_list[j]
                    comp = compare_methods(
                        method_latencies[m_a],
                        method_latencies[m_b],
                        m_a, m_b,
                        n_comparisons=n_comparisons,
                    )
                    comp["concurrency"] = concurrency
                    comp["cache_state"] = cache
                    analysis["comparisons"].append(comp)

    # Per-category analysis
    for key, group in groups.items():
        method, concurrency, cache = key
        by_cat = {}
        for r in group:
            by_cat.setdefault(r.category, []).append(r)

        for cat, cat_results in by_cat.items():
            latencies = np.array([r.latency_ms for r in cat_results])
            cat_key = f"{method}_c{concurrency}_{cache}_cat{cat}"
            analysis["by_category"][cat_key] = descriptive_stats(latencies)

    return analysis
