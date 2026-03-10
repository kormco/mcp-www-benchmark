# MCP Discovery Benchmark: DNS vs HTTP

A scientific experiment comparing DNS TXT record lookups vs HTTP-based discovery
for indexing MCP (Model Context Protocol) servers at scale.

## Hypothesis

**H1 (Primary):** DNS TXT record lookups (`_mcp.{domain}`) achieve significantly
higher throughput and lower median latency than HTTP-based discovery
(`https://{domain}/.well-known/mcp`) at scale, because DNS uses UDP with small
payloads while HTTP requires TCP + TLS negotiation.

**H2 (Secondary):** The DNS throughput advantage diminishes at very high concurrency
levels due to resolver bottlenecks, while HTTP benefits from connection pooling.

**H0 (Null):** No statistically significant difference exists between DNS and HTTP
discovery at any tested concurrency level.

## Methodology

### Variables

| Type | Variable | Values |
|------|----------|--------|
| Independent | Discovery method | DNS (mcp-www), HTTP (/.well-known/mcp), Website scraping |
| Independent | Concurrency level | 1, 10, 50, 100, 500 |
| Independent | Cache state | Cold, Warm |
| Dependent | Latency (p50, p95, p99) | ms |
| Dependent | Throughput | queries/sec |
| Dependent | Success/failure rate | % |
| Dependent | Bandwidth | bytes sent + received |
| Controlled | Timeout | 5s per query |
| Controlled | Domain list | Same 1,000 domains per trial |
| Controlled | DNS resolver | Pinned (8.8.8.8) |
| Controlled | Machine/network | Same host, same session |

### Domain Categories (200 each, 1,000 total)

| Category | Description | Purpose |
|----------|-------------|---------|
| A | MCP-enabled domains | Happy path for both methods |
| B | Popular domains (Tranco top list) | "Miss" performance — NXDOMAIN vs 404 |
| C | Nonexistent domains | Failure-path latency |
| D | Slow/unreliable domains | Timeout and tail latency behavior |
| E | HTTPS-only, no .well-known | Key asymmetry: fast DNS NXDOMAIN vs full TLS then 404 |

### Test Matrix

- 5 concurrency levels x 3 methods x 2 cache states = 30 configurations
- 10 runs per configuration = 300 total runs
- 1,000 domains per run = 300,000 individual measurements
- Method order alternated between runs to control for temporal effects

### Statistical Analysis

- Mann-Whitney U test (non-parametric) with Bonferroni correction
- Bootstrap 95% CI on medians (10,000 resamples)
- Cohen's d / rank-biserial effect size
- Outliers (timeouts) included in distributions, not removed

## Quick Start

```bash
pip install -r requirements.txt
python scripts/build_domain_list.py
python scripts/run_experiment.py
python scripts/analyze_results.py
```

## Project Structure

```
├── README.md
├── requirements.txt
├── config.py
├── domains.json
├── src/
│   ├── dns_prober.py       # Async DNS TXT lookup
│   ├── http_prober.py      # Async HTTP GET
│   ├── runner.py           # Experiment orchestrator
│   ├── metrics.py          # System resource monitoring
│   ├── models.py           # Data models
│   └── cache_control.py    # DNS cache flush, client lifecycle
├── analysis/
│   ├── stats.py            # Statistical analysis
│   ├── plots.py            # Chart generation
│   └── report.py           # Markdown report generator
├── scripts/
│   ├── build_domain_list.py
│   ├── run_experiment.py
│   └── analyze_results.py
├── results/
│   ├── raw/                # JSONL per run
│   ├── system_metrics/     # CSV timeseries
│   └── report/             # Generated report + charts
└── tests/
```
