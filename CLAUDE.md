# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Scientific benchmark comparing two approaches for discovering MCP (Model Context Protocol) servers at scale:
- **DNS-based** (`_mcp.{domain}` TXT records) — the mcp-www standard
- **HTTP-based** (`https://{domain}/.well-known/mcp`) — hypothetical standard

Measures latency, throughput, bandwidth, and success rates across concurrency levels (1, 10, 50, 100, 500) and cache states (cold, warm).

## Commands

```bash
# Setup
pip install -r requirements.txt

# Generate domain list (must run first)
python scripts/build_domain_list.py

# Run full experiment (300 configs × 201 domains = 60,300 queries)
python scripts/run_experiment.py

# Run quick experiment (for development/testing)
python scripts/run_experiment.py --quick

# Custom run
python scripts/run_experiment.py --methods dns_mcp http_well_known --concurrency 1 10 50 --runs 3

# Analyze results and generate report
python scripts/analyze_results.py
```

No linting, tests, or type checking configured.

## Architecture

**Three-layer design:**

1. **Probers** (`src/dns_prober.py`, `src/http_prober.py`) — async functions that execute a single query and return a `QueryResult`. Each uses `asyncio` with either `dnspython` or `httpx.AsyncClient`.

2. **Orchestrator** (`src/runner.py`) — `run_batch()` runs all 201 domain queries at a given concurrency using `asyncio.Semaphore`. `run_experiment()` loops through the full test matrix, alternating method order between runs to control temporal effects. `src/metrics.py::MetricsCollector` samples system resources (CPU, memory, FDs, network) in a background thread during runs.

3. **Analysis** (`analysis/stats.py`, `analysis/plots.py`, `analysis/report.py`) — loads JSONL results, computes descriptive stats, runs Mann-Whitney U tests with Bonferroni correction, generates bootstrap CIs (10,000 resamples), and outputs a markdown report with PNG charts.

**Data models** (`src/models.py`): `QueryResult` (single query outcome), `RunConfig` (batch configuration), `SystemSample` (resource snapshot).

**Config** (`config.py`): Experiment constants — DNS resolver pinned to `8.8.8.8`, 5-second query timeout, concurrency levels, run count.

## Data Flow

1. `scripts/build_domain_list.py` → `domains.json` (201 domains across 5 categories)
2. `scripts/run_experiment.py` → `results/raw/{method}_c{concurrency}_{cache}_r{run}.jsonl` + `results/system_metrics/{label}.csv`
3. `scripts/analyze_results.py` → `results/report/report.md` + PNG charts

## Conventions

- `probe_*()` for individual query functions, `analyze_*()` for stats, `plot_*()` for charts
- Result file labels: `{method}_c{concurrency}_{cache}_r{run_id}`
- Timeouts are data points (included in distributions, not removed)
- Fixed seed (42) for reproducibility
- Probers return structured `QueryResult` with `success=False` on errors rather than raising exceptions
