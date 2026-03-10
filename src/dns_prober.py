"""DNS-based MCP discovery prober.

Method: Look up _mcp.{domain} TXT record via DNS.
This is the mcp-www approach — lightweight UDP query to find the MCP server URL.
"""

import asyncio
import time
from typing import Optional

import dns.asyncresolver
import dns.resolver
import dns.rdatatype
import dns.name

from config import DNS_RESOLVER, QUERY_TIMEOUT
from src.models import QueryResult


def _make_resolver() -> dns.asyncresolver.Resolver:
    """Create a DNS resolver pinned to our configured nameserver."""
    resolver = dns.asyncresolver.Resolver()
    resolver.nameservers = [DNS_RESOLVER]
    resolver.lifetime = QUERY_TIMEOUT
    resolver.timeout = QUERY_TIMEOUT
    return resolver


async def probe_dns(
    domain: str,
    category: str,
    concurrency_level: int,
    cache_state: str,
    run_id: int,
    resolver: Optional[dns.asyncresolver.Resolver] = None,
) -> QueryResult:
    """Perform a DNS TXT lookup for _mcp.{domain}.

    Returns a QueryResult with timing and outcome data.
    """
    if resolver is None:
        resolver = _make_resolver()

    qname = f"_mcp.{domain}"
    t_start = time.perf_counter()

    try:
        answer = await resolver.resolve(qname, rdtype=dns.rdatatype.TXT)
        t_end = time.perf_counter()

        # Extract TXT record content
        txt_records = []
        bytes_received = 0
        for rdata in answer:
            txt_value = b"".join(rdata.strings).decode("utf-8", errors="replace")
            txt_records.append(txt_value)
            bytes_received += len(txt_value)

        # Check if any TXT record looks like an MCP server URL
        mcp_found = any("mcp" in t.lower() or "http" in t.lower() for t in txt_records)

        return QueryResult(
            method="dns_mcp",
            domain=domain,
            category=category,
            concurrency_level=concurrency_level,
            cache_state=cache_state,
            run_id=run_id,
            timestamp_start=t_start,
            timestamp_end=t_end,
            latency_ms=(t_end - t_start) * 1000,
            success=True,
            result_code="NOERROR",
            bytes_sent=len(qname) + 12,  # approximate DNS query size
            bytes_received=bytes_received,
            mcp_server_found=mcp_found,
            extra={"txt_records": txt_records},
        )

    except dns.resolver.NXDOMAIN:
        t_end = time.perf_counter()
        return QueryResult(
            method="dns_mcp",
            domain=domain,
            category=category,
            concurrency_level=concurrency_level,
            cache_state=cache_state,
            run_id=run_id,
            timestamp_start=t_start,
            timestamp_end=t_end,
            latency_ms=(t_end - t_start) * 1000,
            success=True,  # query succeeded, just no record
            result_code="NXDOMAIN",
            bytes_sent=len(qname) + 12,
            bytes_received=0,
            mcp_server_found=False,
        )

    except dns.resolver.NoAnswer:
        t_end = time.perf_counter()
        return QueryResult(
            method="dns_mcp",
            domain=domain,
            category=category,
            concurrency_level=concurrency_level,
            cache_state=cache_state,
            run_id=run_id,
            timestamp_start=t_start,
            timestamp_end=t_end,
            latency_ms=(t_end - t_start) * 1000,
            success=True,
            result_code="NOANSWER",
            bytes_sent=len(qname) + 12,
            bytes_received=0,
            mcp_server_found=False,
        )

    except dns.resolver.LifetimeTimeout:
        t_end = time.perf_counter()
        return QueryResult(
            method="dns_mcp",
            domain=domain,
            category=category,
            concurrency_level=concurrency_level,
            cache_state=cache_state,
            run_id=run_id,
            timestamp_start=t_start,
            timestamp_end=t_end,
            latency_ms=(t_end - t_start) * 1000,
            success=False,
            result_code="TIMEOUT",
            bytes_sent=len(qname) + 12,
            bytes_received=0,
            mcp_server_found=False,
            error_detail="DNS query timed out",
        )

    except Exception as e:
        t_end = time.perf_counter()
        return QueryResult(
            method="dns_mcp",
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
            bytes_sent=len(qname) + 12,
            bytes_received=0,
            mcp_server_found=False,
            error_detail=str(e),
        )
