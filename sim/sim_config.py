"""Simulation configuration for the 50% MCP adoption scenario.

Loads real latency distributions from experiment results and selects
which domains are "MCP-enabled" for the simulation.
"""

import json
import os
import random
from pathlib import Path
from typing import Dict, List, Tuple

# Fixed seed for reproducibility
SIM_SEED = 42

# Project root
PROJECT_ROOT = Path(__file__).resolve().parent.parent

# Paths
DOMAINS_FILE = PROJECT_ROOT / "domains.json"
RAW_RESULTS_DIR = PROJECT_ROOT / "results" / "raw"
SIM_RESULTS_DIR = PROJECT_ROOT / "results" / "sim_50pct"

# Simulation server settings
SIM_DNS_HOST = "127.0.0.1"
SIM_DNS_PORT = 5354
SIM_HTTP_HOST = "127.0.0.1"
SIM_HTTP_PORT = 8080

# Concurrency levels (same as real experiment)
CONCURRENCY_LEVELS = [1, 10, 50, 100, 500]
RUNS_PER_CONFIG = 3


def load_domains() -> List[Dict]:
    """Load all domains from domains.json."""
    with open(DOMAINS_FILE) as f:
        data = json.load(f)
    return data["domains"]


def select_mcp_enabled_domains(domains: List[Dict], fraction: float = 0.5) -> set:
    """Randomly select a fraction of domains to be MCP-enabled.

    Uses a fixed seed for reproducibility. Returns set of domain names.
    """
    rng = random.Random(SIM_SEED)
    domain_names = [d["domain"] for d in domains]
    count = int(len(domain_names) * fraction)
    selected = set(rng.sample(domain_names, count))
    return selected


def extract_cold_latencies(method: str) -> List[float]:
    """Extract all cold-cache latency values for a given method from raw results.

    Reads all JSONL files matching {method}_c*_cold_r*.jsonl and collects
    the latency_ms values for successful queries.

    Args:
        method: "dns_mcp" or "http_well_known"

    Returns:
        List of latency_ms values (floats).
    """
    latencies = []
    for fname in sorted(os.listdir(RAW_RESULTS_DIR)):
        if not fname.startswith(method) or "_cold_" not in fname or not fname.endswith(".jsonl"):
            continue
        fpath = RAW_RESULTS_DIR / fname
        with open(fpath) as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                record = json.loads(line)
                if record.get("cache_state") == "cold" and record.get("method") == method:
                    latencies.append(record["latency_ms"])
    return latencies


class SimConfig:
    """Holds everything the simulation servers need."""

    def __init__(self):
        self.domains = load_domains()
        self.mcp_enabled = select_mcp_enabled_domains(self.domains, fraction=0.5)
        self.dns_latencies = extract_cold_latencies("dns_mcp")
        self.http_latencies = extract_cold_latencies("http_well_known")

        if not self.dns_latencies:
            raise RuntimeError(
                f"No DNS cold-cache latencies found in {RAW_RESULTS_DIR}. "
                "Run the real experiment first."
            )
        if not self.http_latencies:
            raise RuntimeError(
                f"No HTTP cold-cache latencies found in {RAW_RESULTS_DIR}. "
                "Run the real experiment first."
            )

    def summary(self) -> str:
        total = len(self.domains)
        enabled = len(self.mcp_enabled)
        return (
            f"SimConfig: {enabled}/{total} domains MCP-enabled ({enabled/total*100:.1f}%)\n"
            f"  DNS latency samples: {len(self.dns_latencies)} "
            f"(p50={sorted(self.dns_latencies)[len(self.dns_latencies)//2]:.1f}ms)\n"
            f"  HTTP latency samples: {len(self.http_latencies)} "
            f"(p50={sorted(self.http_latencies)[len(self.http_latencies)//2]:.1f}ms)"
        )


if __name__ == "__main__":
    cfg = SimConfig()
    print(cfg.summary())
    print(f"\nFirst 10 MCP-enabled domains: {sorted(cfg.mcp_enabled)[:10]}")
