"""Website scraping MCP discovery prober.

Method: Fetch the full website homepage and search for MCP references in HTML.
This simulates the worst-case discovery approach — no standard, just crawling.
"""

import re
import time
from typing import Optional

import httpx

from config import QUERY_TIMEOUT
from src.models import QueryResult

# Patterns that might indicate MCP server presence in HTML
MCP_PATTERNS = [
    re.compile(r'_mcp\b', re.IGNORECASE),
    re.compile(r'mcp\..*\.com', re.IGNORECASE),
    re.compile(r'model\s*context\s*protocol', re.IGNORECASE),
    re.compile(r'\.well-known/mcp', re.IGNORECASE),
    re.compile(r'mcp-server', re.IGNORECASE),
    re.compile(r'mcpServers', re.IGNORECASE),
]


async def probe_website(
    domain: str,
    category: str,
    concurrency_level: int,
    cache_state: str,
    run_id: int,
    client: Optional[httpx.AsyncClient] = None,
) -> QueryResult:
    """Fetch the homepage of a domain and scan for MCP references.

    This represents the heaviest discovery method: full page load + parsing.
    """
    url = f"https://{domain}"
    own_client = client is None

    if own_client:
        client = httpx.AsyncClient(
            timeout=QUERY_TIMEOUT,
            follow_redirects=True,
            max_redirects=5,
            headers={"User-Agent": "MCP-Discovery-Benchmark/1.0"},
        )

    t_start = time.perf_counter()

    try:
        response = await client.get(url)
        t_end = time.perf_counter()

        body = response.text
        body_bytes = response.content

        # Scan for MCP-related patterns
        mcp_found = any(pattern.search(body) for pattern in MCP_PATTERNS)

        request_size = len(f"GET / HTTP/2\r\nHost: {domain}\r\nUser-Agent: MCP-Discovery-Benchmark/1.0\r\n\r\n")

        return QueryResult(
            method="website_scrape",
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
            bytes_received=len(body_bytes),
            mcp_server_found=mcp_found,
            extra={
                "status_code": response.status_code,
                "content_length": len(body_bytes),
                "redirect_count": len(response.history),
            },
        )

    except httpx.ConnectTimeout:
        t_end = time.perf_counter()
        return _error_result(
            domain, category, concurrency_level, cache_state, run_id,
            t_start, t_end, "CONNECT_TIMEOUT", "Connection timed out",
        )

    except httpx.ReadTimeout:
        t_end = time.perf_counter()
        return _error_result(
            domain, category, concurrency_level, cache_state, run_id,
            t_start, t_end, "READ_TIMEOUT", "Read timed out",
        )

    except httpx.ConnectError as e:
        t_end = time.perf_counter()
        return _error_result(
            domain, category, concurrency_level, cache_state, run_id,
            t_start, t_end, "CONNECT_ERROR", str(e),
        )

    except httpx.TooManyRedirects:
        t_end = time.perf_counter()
        return _error_result(
            domain, category, concurrency_level, cache_state, run_id,
            t_start, t_end, "TOO_MANY_REDIRECTS", "Exceeded max redirects",
        )

    except Exception as e:
        t_end = time.perf_counter()
        return _error_result(
            domain, category, concurrency_level, cache_state, run_id,
            t_start, t_end, "ERROR", str(e),
        )

    finally:
        if own_client:
            await client.aclose()


def _error_result(
    domain: str,
    category: str,
    concurrency_level: int,
    cache_state: str,
    run_id: int,
    t_start: float,
    t_end: float,
    result_code: str,
    error_detail: str,
) -> QueryResult:
    return QueryResult(
        method="website_scrape",
        domain=domain,
        category=category,
        concurrency_level=concurrency_level,
        cache_state=cache_state,
        run_id=run_id,
        timestamp_start=t_start,
        timestamp_end=t_end,
        latency_ms=(t_end - t_start) * 1000,
        success=False,
        result_code=result_code,
        bytes_sent=0,
        bytes_received=0,
        mcp_server_found=False,
        error_detail=error_detail,
    )
