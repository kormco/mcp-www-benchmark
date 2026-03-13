"""Simulated HTTP server for the 50% MCP adoption scenario.

Listens on port 8080 and responds to /.well-known/mcp requests:
- MCP-enabled domains (determined by Host header): returns 200 with JSON body
- Other domains: returns 404
- All responses are delayed by a random sample from the real cold-cache
  HTTP latency distribution.

Uses aiohttp for the HTTP server.
"""

import asyncio
import json
import random
import sys
from pathlib import Path

from aiohttp import web

# Add project root to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from sim.sim_config import SimConfig, SIM_HTTP_HOST, SIM_HTTP_PORT


class SimHTTPServer:
    """Simulated HTTP server with delay injection."""

    def __init__(self, config: SimConfig):
        self.config = config
        self.rng = random.Random(42)
        self.request_count = 0

    async def handle_well_known_mcp(self, request: web.Request) -> web.Response:
        self.request_count += 1

        # Determine domain from Host header
        host = request.host
        # Strip port if present
        if ":" in host:
            host = host.split(":")[0]

        # Sample delay from real distribution
        delay_ms = self.rng.choice(self.config.http_latencies)
        delay_s = delay_ms / 1000.0
        await asyncio.sleep(delay_s)

        if host in self.config.mcp_enabled:
            body = {
                "protocolVersion": "2024-11-05",
                "capabilities": {"tools": {}, "resources": {}},
                "serverInfo": {"name": f"mcp-{host}", "version": "1.0.0"},
            }
            return web.json_response(body, status=200)
        else:
            return web.Response(status=404, text="Not Found")

    async def handle_catch_all(self, request: web.Request) -> web.Response:
        """Handle any path that is not /.well-known/mcp."""
        return web.Response(status=404, text="Not Found")

    def create_app(self) -> web.Application:
        app = web.Application()
        app.router.add_get("/.well-known/mcp", self.handle_well_known_mcp)
        app.router.add_route("*", "/{path:.*}", self.handle_catch_all)
        return app


async def start_http_server(config: SimConfig) -> web.AppRunner:
    """Start the simulated HTTP server. Returns the runner for shutdown."""
    server = SimHTTPServer(config)
    app = server.create_app()
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, SIM_HTTP_HOST, SIM_HTTP_PORT)
    await site.start()
    print(f"[sim] HTTP server listening on {SIM_HTTP_HOST}:{SIM_HTTP_PORT}")
    return runner


async def main():
    """Run the HTTP server standalone for testing."""
    config = SimConfig()
    print(config.summary())
    print()

    runner = await start_http_server(config)

    print("[sim] HTTP server running. Press Ctrl+C to stop.")
    try:
        while True:
            await asyncio.sleep(3600)
    except asyncio.CancelledError:
        pass
    finally:
        await runner.cleanup()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n[sim] HTTP server stopped.")
