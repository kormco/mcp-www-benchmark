"""HTTP-based MCP discovery prober.

Method: Hit https://{domain}/.well-known/mcp via HTTPS.
This simulates a hypothetical HTTP-based MCP discovery standard.
"""

import time
from typing import Optional

import httpx

from config import QUERY_TIMEOUT, HTTP_WELL_KNOWN_PATH
from src.models import QueryResult


async def probe_http_well_known(
    domain: str,
    category: str,
    concurrency_level: int,
    cache_state: str,
    run_id: int,
    client: Optional[httpx.AsyncClient] = None,
) -> QueryResult:
    """Perform an HTTPS GET to {domain}/.well-known/mcp.

    If client is None, creates a throwaway client (no connection pooling).
    If client is provided, reuses connections (pooled mode).
    """
    url = f"https://{domain}{HTTP_WELL_KNOWN_PATH}"
    own_client = client is None

    if own_client:
        client = httpx.AsyncClient(
            timeout=QUERY_TIMEOUT,
            follow_redirects=True,
            max_redirects=3,
        )

    t_start = time.perf_counter()

    try:
        response = await client.get(url)
        t_end = time.perf_counter()

        body = response.content
        content_type = response.headers.get("content-type", "")

        # Validate that the response is actually MCP content, not a catch-all
        # HTML page. A real .well-known/mcp response should be JSON.
        mcp_found = False
        if response.status_code == 200 and len(body) > 0:
            if "json" in content_type:
                try:
                    import json
                    data = json.loads(body)
                    # Must be a dict/object with at least one MCP-relevant key
                    mcp_found = isinstance(data, dict) and bool(
                        set(data.keys()) & {"capabilities", "serverInfo", "tools", "resources", "prompts", "protocolVersion"}
                    )
                except (json.JSONDecodeError, UnicodeDecodeError):
                    pass

        # Approximate bytes: request line + headers
        request_size = len(f"GET {HTTP_WELL_KNOWN_PATH} HTTP/2\r\nHost: {domain}\r\n\r\n")

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
            extra={"status_code": response.status_code, "redirect_count": len(response.history)},
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
        result_code=result_code,
        bytes_sent=0,
        bytes_received=0,
        mcp_server_found=False,
        error_detail=error_detail,
    )
