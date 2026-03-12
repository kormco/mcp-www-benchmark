"""Simulated MCP server for the 50% adoption scenario.

Responds to JSON-RPC initialize, tools/list, resources/list, and prompts/list
so that mcp-www's browse_discover can complete the full manifest fetch.

No delay is injected here — the DNS server already injects latency.
This server just needs to respond quickly so the manifest fetch succeeds.
"""

import asyncio
import json
import sys
from pathlib import Path

from aiohttp import web

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from sim.sim_config import SimConfig, SIM_MCP_HOST, SIM_MCP_PORT


class SimMCPServer:
    """Minimal MCP JSON-RPC server for browse_discover manifest fetch."""

    def __init__(self, config: SimConfig):
        self.config = config
        self.request_count = 0

    async def handle_jsonrpc(self, request: web.Request) -> web.Response:
        self.request_count += 1

        try:
            body = await request.json()
        except Exception:
            return web.json_response(
                {"jsonrpc": "2.0", "id": None, "error": {"code": -32700, "message": "Parse error"}},
                status=200,
            )

        req_id = body.get("id")
        method = body.get("method", "")

        if method == "initialize":
            result = {
                "protocolVersion": "2024-11-05",
                "capabilities": {"tools": {}},
                "serverInfo": {"name": "sim-mcp-server", "version": "1.0.0"},
            }
        elif method == "tools/list":
            result = {"tools": []}
        elif method == "resources/list":
            result = {"resources": []}
        elif method == "prompts/list":
            result = {"prompts": []}
        else:
            result = {}

        response = {"jsonrpc": "2.0", "id": req_id, "result": result}
        resp = web.json_response(response, status=200)
        # browse_discover looks for mcp-session-id
        resp.headers["mcp-session-id"] = "sim-session"
        return resp

    def create_app(self) -> web.Application:
        app = web.Application()
        app.router.add_post("/", self.handle_jsonrpc)
        app.router.add_route("*", "/{path:.*}", self.handle_jsonrpc)
        return app


async def start_mcp_server(config: SimConfig) -> web.AppRunner:
    """Start the simulated MCP server. Returns the runner for shutdown."""
    server = SimMCPServer(config)
    app = server.create_app()
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, SIM_MCP_HOST, SIM_MCP_PORT)
    await site.start()
    print(f"[sim] MCP server listening on {SIM_MCP_HOST}:{SIM_MCP_PORT}")
    return runner
