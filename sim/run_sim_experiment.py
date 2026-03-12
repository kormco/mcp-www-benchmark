"""Run the 50% MCP adoption simulation experiment.

Starts simulated DNS and HTTP servers, then runs the experiment matrix
using mcp-www (browse_discover) pointed at the sim DNS server, and
direct HTTP pointed at the sim HTTP server.

Results are saved to results/sim_50pct/.
"""

import asyncio
import json
import os
import sys
import time
from pathlib import Path
from typing import List, Tuple

# Add project root to path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

import httpx

from sim.sim_config import (
    SimConfig,
    SIM_DNS_HOST,
    SIM_DNS_PORT,
    SIM_HTTP_HOST,
    SIM_HTTP_PORT,
    SIM_RESULTS_DIR,
    CONCURRENCY_LEVELS,
    RUNS_PER_CONFIG,
)
from sim.dns_server import start_dns_server
from sim.http_server import start_http_server
from src.models import QueryResult, RunConfig
from src.mcpwww_prober import McpWwwClient, probe_mcp_www
from config import QUERY_TIMEOUT


async def probe_sim_http(
    domain: str,
    category: str,
    concurrency_level: int,
    cache_state: str,
    run_id: int,
    client: httpx.AsyncClient = None,
) -> QueryResult:
    """Probe the simulated HTTP server for a domain.

    Instead of hitting the real domain over HTTPS, we query the local
    sim HTTP server on port 8080 with the domain in the Host header.
    """
    url = f"http://{SIM_HTTP_HOST}:{SIM_HTTP_PORT}/.well-known/mcp"
    own_client = client is None

    if own_client:
        client = httpx.AsyncClient(
            timeout=QUERY_TIMEOUT,
            follow_redirects=True,
            max_redirects=3,
        )

    t_start = time.perf_counter()

    try:
        response = await client.get(url, headers={"Host": domain})
        t_end = time.perf_counter()

        body = response.content
        mcp_found = response.status_code == 200 and len(body) > 0

        request_size = len(f"GET /.well-known/mcp HTTP/1.1\r\nHost: {domain}\r\n\r\n")

        return QueryResult(
            method="http_well_known",
            domain=domain,
            category=category,
            concurrency_level=concurrency_level,
            cache_state=cache_state,
            run_id=run_id,
            timestamp_start=t_start,
            timestamp_end=t_end,
            latency_ms=(t_end - t_start) * 1000,
            success=True,
            result_code=str(response.status_code),
            bytes_sent=request_size,
            bytes_received=len(body) + len(str(response.headers)),
            mcp_server_found=mcp_found,
            extra={"status_code": response.status_code, "simulated": True},
        )

    except Exception as e:
        t_end = time.perf_counter()
        return QueryResult(
            method="http_well_known",
            domain=domain,
            category=category,
            concurrency_level=concurrency_level,
            cache_state=cache_state,
            run_id=run_id,
            timestamp_start=t_start,
            timestamp_end=t_end,
            latency_ms=(t_end - t_start) * 1000,
            success=False,
            result_code="ERROR",
            bytes_sent=0,
            bytes_received=0,
            mcp_server_found=False,
            error_detail=f"{type(e).__name__}: {e}",
        )

    finally:
        if own_client:
            await client.aclose()


async def run_sim_batch(
    config: RunConfig,
    mcpwww_client: McpWwwClient = None,
    http_client: httpx.AsyncClient = None,
) -> List[QueryResult]:
    """Run a single batch against simulated servers."""
    semaphore = asyncio.Semaphore(config.concurrency_level)
    own_client = False

    if config.method == "http_well_known" and http_client is None:
        http_client = httpx.AsyncClient(
            timeout=QUERY_TIMEOUT,
            follow_redirects=True,
            max_redirects=3,
            limits=httpx.Limits(
                max_connections=config.concurrency_level + 50,
                max_keepalive_connections=config.concurrency_level + 50,
            ),
        )
        own_client = True

    async def probe_one(domain: str, category: str) -> QueryResult:
        async with semaphore:
            if config.method == "mcp_www":
                return await probe_mcp_www(
                    domain, category, config.concurrency_level,
                    config.cache_state, config.run_id, mcpwww_client,
                )
            elif config.method == "http_well_known":
                return await probe_sim_http(
                    domain, category, config.concurrency_level,
                    config.cache_state, config.run_id, http_client,
                )

    tasks = [probe_one(domain, cat) for domain, cat in config.domains]
    results = await asyncio.gather(*tasks)

    if own_client and http_client:
        await http_client.aclose()

    return list(results)


def save_sim_results(results: List[QueryResult], config: RunConfig):
    """Save results to the sim_50pct results directory."""
    os.makedirs(SIM_RESULTS_DIR, exist_ok=True)
    filepath = SIM_RESULTS_DIR / f"{config.label}.jsonl"
    with open(filepath, "w") as f:
        for r in results:
            f.write(r.to_json() + "\n")


async def run_sim_experiment():
    """Run the full simulation experiment."""
    print("=" * 60)
    print("50% MCP Adoption Simulation Experiment")
    print("=" * 60)

    # Load config (extracts real latency distributions)
    config = SimConfig()
    print(config.summary())
    print()

    # Start sim servers
    dns_transport = await start_dns_server(config)
    http_runner = await start_http_server(config)

    # Give servers a moment to be ready
    await asyncio.sleep(0.5)

    # Start mcp-www client pointed at sim DNS server
    dns_server = f"{SIM_DNS_HOST}:{SIM_DNS_PORT}"
    mcpwww_client = McpWwwClient(dns_server=dns_server)
    await mcpwww_client.start()
    print(f"[sim] mcp-www started with DNS resolver {dns_server}")

    domains = [(d["domain"], d["category"]) for d in config.domains]
    methods = ["mcp_www", "http_well_known"]
    cache_states = ["cold"]  # Only cold — we inject cold latency

    os.makedirs(SIM_RESULTS_DIR, exist_ok=True)

    total_batches = len(methods) * len(CONCURRENCY_LEVELS) * RUNS_PER_CONFIG
    completed = 0

    try:
        for concurrency in CONCURRENCY_LEVELS:
            for run_id in range(RUNS_PER_CONFIG):
                # Alternate method order
                method_order = methods if run_id % 2 == 0 else list(reversed(methods))

                for method in method_order:
                    run_config = RunConfig(
                        method=method,
                        concurrency_level=concurrency,
                        cache_state="cold",
                        run_id=run_id,
                        domains=domains,
                    )

                    t_start = time.perf_counter()
                    results = await run_sim_batch(run_config, mcpwww_client)
                    t_end = time.perf_counter()

                    save_sim_results(results, run_config)

                    batch_time = t_end - t_start
                    qps = len(results) / batch_time if batch_time > 0 else 0

                    # Count MCP found
                    mcp_count = sum(1 for r in results if r.mcp_server_found)

                    completed += 1
                    print(
                        f"[{completed}/{total_batches}] {run_config.label}: "
                        f"{len(results)} queries in {batch_time:.2f}s "
                        f"({qps:.1f} q/s, {mcp_count} MCP found)"
                    )

    finally:
        # Shutdown
        print("\n[sim] Shutting down...")
        await mcpwww_client.stop()
        dns_transport.close()
        await http_runner.cleanup()

    print(f"\n[sim] Results saved to {SIM_RESULTS_DIR}")
    print("[sim] Experiment complete.")


if __name__ == "__main__":
    asyncio.run(run_sim_experiment())
