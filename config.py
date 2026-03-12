"""Experiment configuration constants."""

# DNS resolver to use (pinned for consistency)
# Previous run used "8.8.8.8" port 53 (Google Public DNS)
# Now using local Unbound recursive resolver on Synology NAS
DNS_RESOLVER = "192.168.68.133"
DNS_RESOLVER_PORT = 5335

# Query timeout in seconds
QUERY_TIMEOUT = 5.0

# Concurrency levels to test
CONCURRENCY_LEVELS = [1, 10, 50, 100, 500]

# Number of runs per configuration
RUNS_PER_CONFIG = 3

# Cache states to test
CACHE_STATES = ["cold", "warm"]

# Discovery methods to compare
METHODS = ["mcp_www", "http_well_known"]
METHOD_LABELS = {
    "mcp_www": "mcp-www (browse_discover)",
    "http_well_known": "HTTP (/.well-known/mcp)",
}

# Path to locally-built mcp-www
MCP_WWW_NODE_PATH = "/home/kormco/mcp-www/dist/index.js"

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
