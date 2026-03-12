"""mcp-www browse_discover prober.

Spawns the mcp-www MCP server as a subprocess and calls browse_discover
over stdio JSON-RPC. This benchmarks the full discovery flow: DNS TXT
lookup + server manifest fetch (when an MCP server is found).
"""

import asyncio
import json
import os
import time
from typing import Optional, Dict

from config import QUERY_TIMEOUT, MCP_WWW_NODE_PATH
from src.models import QueryResult


class McpWwwClient:
    """Manages a mcp-www subprocess for async browse_discover calls."""

    def __init__(self, dns_server: Optional[str] = None):
        self.dns_server = dns_server
        self.process = None
        self._id_counter = 0
        self._pending: Dict[int, asyncio.Future] = {}
        self._reader_task = None

    async def start(self):
        """Spawn the mcp-www process and perform the initialize handshake."""
        env = dict(os.environ)
        if self.dns_server:
            env["MCP_DNS_SERVER"] = self.dns_server

        self.process = await asyncio.create_subprocess_exec(
            "node", MCP_WWW_NODE_PATH,
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.DEVNULL,
            env=env,
        )

        # Start reading responses
        self._reader_task = asyncio.create_task(self._read_responses())

        # Initialize handshake
        await self._send_request("initialize", {
            "protocolVersion": "2024-11-05",
            "capabilities": {},
            "clientInfo": {"name": "benchmark", "version": "1.0"},
        })

    async def stop(self):
        """Shut down the subprocess."""
        if self._reader_task:
            self._reader_task.cancel()
            try:
                await self._reader_task
            except asyncio.CancelledError:
                pass
        if self.process and self.process.returncode is None:
            self.process.stdin.close()
            try:
                await asyncio.wait_for(self.process.wait(), timeout=5)
            except asyncio.TimeoutError:
                self.process.kill()

    def _next_id(self) -> int:
        self._id_counter += 1
        return self._id_counter

    async def _send_request(self, method: str, params: dict, timeout: float = 30.0) -> dict:
        """Send a JSON-RPC request and wait for the matching response."""
        req_id = self._next_id()
        msg = json.dumps({"jsonrpc": "2.0", "id": req_id, "method": method, "params": params})

        future = asyncio.get_event_loop().create_future()
        self._pending[req_id] = future

        self.process.stdin.write((msg + "\n").encode())
        await self.process.stdin.drain()

        try:
            return await asyncio.wait_for(future, timeout=timeout)
        except asyncio.TimeoutError:
            self._pending.pop(req_id, None)
            raise

    async def _read_responses(self):
        """Background task: read stdout lines and resolve pending futures."""
        try:
            while True:
                line = await self.process.stdout.readline()
                if not line:
                    break
                try:
                    msg = json.loads(line)
                    req_id = msg.get("id")
                    if req_id is not None and req_id in self._pending:
                        self._pending.pop(req_id).set_result(msg)
                except json.JSONDecodeError:
                    pass
        except asyncio.CancelledError:
            pass
        finally:
            # Resolve any remaining pending futures with an error
            for fut in self._pending.values():
                if not fut.done():
                    fut.set_exception(ConnectionError("mcp-www process exited"))
            self._pending.clear()

    async def browse_discover(self, domain: str, timeout: float = QUERY_TIMEOUT) -> dict:
        """Call browse_discover and return the raw JSON-RPC response."""
        return await self._send_request(
            "tools/call",
            {"name": "browse_discover", "arguments": {"domain": domain}},
            timeout=timeout,
        )


async def probe_mcp_www(
    domain: str,
    category: str,
    concurrency_level: int,
    cache_state: str,
    run_id: int,
    client: McpWwwClient = None,
) -> QueryResult:
    """Probe a domain using mcp-www browse_discover.

    Measures the full discovery flow: DNS TXT lookup + manifest fetch.
    """
    t_start = time.perf_counter()

    try:
        response = await client.browse_discover(domain, timeout=QUERY_TIMEOUT)
        t_end = time.perf_counter()

        result_data = response.get("result", {})
        content_blocks = result_data.get("content", [])
        is_error = result_data.get("isError", False)

        # Extract text content for byte counting
        raw_text = ""
        for block in content_blocks:
            if block.get("type") == "text":
                raw_text += block.get("text", "")

        # Determine if an MCP server was actually found
        # browse_discover either prefixes with "Discovered MCP server for" (when
        # server has instructions) or returns JSON with "found": true + "server"
        mcp_found = (
            "Discovered MCP server for" in raw_text
            or ('"found": true' in raw_text and '"serverInfo"' in raw_text)
        )

        # Approximate bytes: request JSON + response JSON
        request_json = json.dumps({
            "jsonrpc": "2.0", "id": 0, "method": "tools/call",
            "params": {"name": "browse_discover", "arguments": {"domain": domain}},
        })

        return QueryResult(
            method="mcp_www",
            domain=domain,
            category=category,
            concurrency_level=concurrency_level,
            cache_state=cache_state,
            run_id=run_id,
            timestamp_start=t_start,
            timestamp_end=t_end,
            latency_ms=(t_end - t_start) * 1000,
            success=not is_error,
            result_code="found" if mcp_found else "not_found" if not is_error else "error",
            bytes_sent=len(request_json),
            bytes_received=len(raw_text),
            mcp_server_found=mcp_found,
            extra={"via": "mcp-www/browse_discover"},
        )

    except asyncio.TimeoutError:
        t_end = time.perf_counter()
        return QueryResult(
            method="mcp_www",
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
            bytes_sent=0,
            bytes_received=0,
            mcp_server_found=False,
            error_detail="browse_discover timed out",
        )

    except Exception as e:
        t_end = time.perf_counter()
        return QueryResult(
            method="mcp_www",
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
            error_detail=str(e),
        )
