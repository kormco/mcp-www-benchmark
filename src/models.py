"""Data models for the experiment."""

from dataclasses import dataclass, field, asdict
from typing import Optional
import json
import time


@dataclass
class QueryResult:
    """Result of a single discovery query."""
    method: str                    # "dns_mcp", "http_well_known", "website_scrape"
    domain: str                    # Target domain
    category: str                  # Domain category: A, B, C, D, E
    concurrency_level: int         # Concurrency during this run
    cache_state: str               # "cold" or "warm"
    run_id: int                    # Run number within this config
    timestamp_start: float         # time.perf_counter() at query start
    timestamp_end: float           # time.perf_counter() at query end
    latency_ms: float              # End - start in milliseconds
    success: bool                  # Whether MCP info was discovered
    result_code: str               # DNS: NOERROR/NXDOMAIN/SERVFAIL/timeout
                                   # HTTP: 200/404/timeout/connection_error
    bytes_sent: int = 0            # Approximate bytes sent
    bytes_received: int = 0        # Approximate bytes received
    error_detail: Optional[str] = None
    mcp_server_found: bool = False # Whether an MCP server was actually discovered
    extra: dict = field(default_factory=dict)

    def to_json(self) -> str:
        return json.dumps(asdict(self))

    @classmethod
    def from_json(cls, line: str) -> "QueryResult":
        data = json.loads(line)
        return cls(**data)


@dataclass
class RunConfig:
    """Configuration for a single experimental run."""
    method: str
    concurrency_level: int
    cache_state: str
    run_id: int
    domains: list  # List of (domain, category) tuples

    @property
    def label(self) -> str:
        return f"{self.method}_c{self.concurrency_level}_{self.cache_state}_r{self.run_id}"


@dataclass
class SystemSample:
    """A single system metrics sample."""
    timestamp: float
    cpu_percent: float
    memory_rss_mb: float
    open_fds: int
    net_bytes_sent: int
    net_bytes_recv: int

    def to_csv_row(self) -> str:
        return (
            f"{self.timestamp},{self.cpu_percent},{self.memory_rss_mb},"
            f"{self.open_fds},{self.net_bytes_sent},{self.net_bytes_recv}"
        )

    @staticmethod
    def csv_header() -> str:
        return "timestamp,cpu_percent,memory_rss_mb,open_fds,net_bytes_sent,net_bytes_recv"
