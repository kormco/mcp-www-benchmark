"""Experiment orchestrator.

Runs the full test matrix: 2 methods x 5 concurrency levels x 2 cache states x N runs.
"""

import asyncio
import json
import os
import time
from pathlib import Path
from typing import List, Tuple

import httpx

from config import (
    CONCURRENCY_LEVELS, CACHE_STATES, RUNS_PER_CONFIG,
    RAW_RESULTS_DIR, SYSTEM_METRICS_DIR, QUERY_TIMEOUT,
)
from src.models import QueryResult, RunConfig
from src.dns_prober import probe_dns, _make_resolver
from src.http_prober import probe_http_well_known
from src.cache_control import flush_dns_cache
from src.metrics import MetricsCollector


def load_domains(path: str) -> List[Tuple[str, str]]:
    """Load domain list from JSON. Returns list of (domain, category) tuples."""
    with open(path) as f:
        data = json.load(f)
    return [(d["domain"], d["category"]) for d in data["domains"]]


async def run_batch(
    config: RunConfig,
    progress_callback=None,
) -> List[QueryResult]:
    """Run a single batch: one method, one concurrency level, all domains."""

    semaphore = asyncio.Semaphore(config.concurrency_level)
    results: List[QueryResult] = []

    # Set up shared resources based on method
    resolver = None
    client = None

    if config.method == "dns_mcp":
        resolver = _make_resolver()
    elif config.method == "http_well_known":
        client = httpx.AsyncClient(
            timeout=QUERY_TIMEOUT,
            follow_redirects=True,
            max_redirects=3,
        )

    async def probe_one(domain: str, category: str) -> QueryResult:
        async with semaphore:
            if config.method == "dns_mcp":
                return await probe_dns(
                    domain, category, config.concurrency_level,
                    config.cache_state, config.run_id, resolver,
                )
            elif config.method == "http_well_known":
                return await probe_http_well_known(
                    domain, category, config.concurrency_level,
                    config.cache_state, config.run_id, client,
                )

    tasks = [probe_one(domain, cat) for domain, cat in config.domains]
    results = await asyncio.gather(*tasks)

    if client:
        await client.aclose()

    if progress_callback:
        progress_callback(config.label, len(results))

    return list(results)


def save_results(results: List[QueryResult], config: RunConfig):
    """Save results to a JSONL file."""
    os.makedirs(RAW_RESULTS_DIR, exist_ok=True)
    filepath = os.path.join(RAW_RESULTS_DIR, f"{config.label}.jsonl")
    with open(filepath, "w") as f:
        for r in results:
            f.write(r.to_json() + "\n")


async def run_experiment(
    domains_path: str,
    methods: List[str] = None,
    concurrency_levels: List[int] = None,
    cache_states: List[str] = None,
    runs_per_config: int = None,
    progress_callback=None,
):
    """Run the full experiment matrix."""

    methods = methods or ["dns_mcp", "http_well_known"]
    concurrency_levels = concurrency_levels or CONCURRENCY_LEVELS
    cache_states = cache_states or CACHE_STATES
    runs_per_config = runs_per_config or RUNS_PER_CONFIG

    domains = load_domains(domains_path)
    total_configs = len(cache_states) * len(concurrency_levels) * runs_per_config
    completed = 0

    os.makedirs(RAW_RESULTS_DIR, exist_ok=True)
    os.makedirs(SYSTEM_METRICS_DIR, exist_ok=True)

    for cache_state in cache_states:
        for concurrency in concurrency_levels:
            for run_id in range(runs_per_config):
                # Alternate method order to control for temporal effects
                if run_id % 2 == 0:
                    method_order = methods
                else:
                    method_order = list(reversed(methods))

                for method in method_order:
                    config = RunConfig(
                        method=method,
                        concurrency_level=concurrency,
                        cache_state=cache_state,
                        run_id=run_id,
                        domains=domains,
                    )

                    # Flush DNS cache for cold runs
                    if cache_state == "cold":
                        flush_dns_cache()
                        await asyncio.sleep(0.5)  # let flush settle

                    # Warm-up pass for warm cache state (first run only)
                    if cache_state == "warm" and run_id == 0:
                        warmup_config = RunConfig(
                            method=method,
                            concurrency_level=concurrency,
                            cache_state="warmup",
                            run_id=-1,
                            domains=domains,
                        )
                        await run_batch(warmup_config)

                    # Collect system metrics
                    collector = MetricsCollector()
                    collector.start()

                    # Run the actual batch
                    t_batch_start = time.perf_counter()
                    results = await run_batch(config, progress_callback)
                    t_batch_end = time.perf_counter()

                    # Stop metrics collection
                    system_samples = collector.stop()
                    metrics_path = os.path.join(SYSTEM_METRICS_DIR, f"{config.label}.csv")
                    collector.save_csv(metrics_path)

                    # Save results
                    save_results(results, config)

                    batch_time = t_batch_end - t_batch_start
                    qps = len(results) / batch_time if batch_time > 0 else 0

                    completed += 1
                    print(
                        f"[{completed}/{total_configs * len(methods)}] "
                        f"{config.label}: {len(results)} queries in "
                        f"{batch_time:.2f}s ({qps:.1f} q/s)"
                    )
