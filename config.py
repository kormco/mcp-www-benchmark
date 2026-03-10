"""Experiment configuration constants."""

# DNS resolver to use (pinned for consistency)
DNS_RESOLVER = "8.8.8.8"
DNS_RESOLVER_PORT = 53

# Query timeout in seconds
QUERY_TIMEOUT = 5.0

# Concurrency levels to test
CONCURRENCY_LEVELS = [1, 10, 50, 100, 500]

# Number of runs per configuration
RUNS_PER_CONFIG = 10

# Cache states to test
CACHE_STATES = ["cold", "warm"]

# Discovery methods to compare
METHODS = ["dns_mcp", "http_well_known", "website_scrape"]
METHOD_LABELS = {
    "dns_mcp": "DNS-based (mcp-www)",
    "http_well_known": "HTTP MCP Discovery (/.well-known/mcp)",
    "website_scrape": "Website Scraping (HTML parse)",
}

# HTTP discovery path
HTTP_WELL_KNOWN_PATH = "/.well-known/mcp"

# System metrics sampling interval (seconds)
METRICS_SAMPLE_INTERVAL = 0.1

# Paths
DOMAINS_FILE = "domains.json"
RESULTS_DIR = "results"
RAW_RESULTS_DIR = "results/raw"
SYSTEM_METRICS_DIR = "results/system_metrics"
REPORT_DIR = "results/report"

# Statistical analysis
BOOTSTRAP_SAMPLES = 10_000
CONFIDENCE_LEVEL = 0.95
ALPHA = 0.05  # before Bonferroni correction
