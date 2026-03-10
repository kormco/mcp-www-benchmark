"""CLI entry point for running the experiment."""

import argparse
import asyncio
import json
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config import (
    DOMAINS_FILE, CONCURRENCY_LEVELS, CACHE_STATES,
    RUNS_PER_CONFIG, METHODS, RESULTS_DIR,
)
from src.runner import run_experiment


def main():
    parser = argparse.ArgumentParser(description="MCP Discovery Benchmark")
    parser.add_argument(
        "--domains", default=DOMAINS_FILE,
        help="Path to domains.json",
    )
    parser.add_argument(
        "--methods", nargs="+", default=METHODS,
        choices=METHODS,
        help="Discovery methods to test",
    )
    parser.add_argument(
        "--concurrency", nargs="+", type=int, default=CONCURRENCY_LEVELS,
        help="Concurrency levels to test",
    )
    parser.add_argument(
        "--cache-states", nargs="+", default=CACHE_STATES,
        choices=CACHE_STATES,
        help="Cache states to test",
    )
    parser.add_argument(
        "--runs", type=int, default=RUNS_PER_CONFIG,
        help="Number of runs per configuration",
    )
    parser.add_argument(
        "--quick", action="store_true",
        help="Quick mode: 1 run, concurrency=[1,10,50], cold only",
    )
    args = parser.parse_args()

    if args.quick:
        args.runs = 1
        args.concurrency = [1, 10, 50]
        args.cache_states = ["cold"]

    if not os.path.exists(args.domains):
        print(f"Error: {args.domains} not found. Run build_domain_list.py first.")
        sys.exit(1)

    # Print experiment configuration
    with open(args.domains) as f:
        domain_data = json.load(f)

    print("=" * 60)
    print("MCP Discovery Benchmark")
    print("=" * 60)
    print(f"Domains:      {domain_data['total']}")
    print(f"Methods:      {', '.join(args.methods)}")
    print(f"Concurrency:  {args.concurrency}")
    print(f"Cache states: {args.cache_states}")
    print(f"Runs/config:  {args.runs}")

    total_batches = (
        len(args.cache_states)
        * len(args.concurrency)
        * args.runs
        * len(args.methods)
    )
    total_queries = total_batches * domain_data["total"]
    print(f"Total batches: {total_batches}")
    print(f"Total queries: {total_queries}")
    print("=" * 60)

    # Save experiment metadata
    os.makedirs(RESULTS_DIR, exist_ok=True)
    metadata = {
        "start_time": time.time(),
        "domains_file": args.domains,
        "domain_count": domain_data["total"],
        "methods": args.methods,
        "concurrency_levels": args.concurrency,
        "cache_states": args.cache_states,
        "runs_per_config": args.runs,
        "total_batches": total_batches,
        "total_queries": total_queries,
        "platform": sys.platform,
        "python_version": sys.version,
    }
    with open(os.path.join(RESULTS_DIR, "metadata.json"), "w") as f:
        json.dump(metadata, f, indent=2)

    # Run the experiment
    t_start = time.time()

    asyncio.run(run_experiment(
        domains_path=args.domains,
        methods=args.methods,
        concurrency_levels=args.concurrency,
        cache_states=args.cache_states,
        runs_per_config=args.runs,
    ))

    elapsed = time.time() - t_start
    print(f"\nExperiment complete in {elapsed:.1f}s")

    # Update metadata with end time
    metadata["end_time"] = time.time()
    metadata["elapsed_seconds"] = elapsed
    with open(os.path.join(RESULTS_DIR, "metadata.json"), "w") as f:
        json.dump(metadata, f, indent=2)


if __name__ == "__main__":
    main()
