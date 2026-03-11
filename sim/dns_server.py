"""Simulated DNS server for the 50% MCP adoption scenario.

Listens on UDP port 5354 and responds to _mcp.{domain} TXT queries:
- MCP-enabled domains: returns a TXT record with MCP server URL
- Other domains: returns NXDOMAIN
- All responses are delayed by a random sample from the real cold-cache
  DNS latency distribution.

Uses dnslib for DNS packet parsing and asyncio for concurrency.
"""

import asyncio
import random
import struct
import sys
from pathlib import Path

from dnslib import DNSRecord, DNSHeader, RR, TXT, QTYPE, RCODE

# Add project root to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from sim.sim_config import SimConfig, SIM_DNS_HOST, SIM_DNS_PORT


class SimDNSProtocol(asyncio.DatagramProtocol):
    """Async UDP protocol handler for simulated DNS."""

    def __init__(self, config: SimConfig, loop: asyncio.AbstractEventLoop):
        self.config = config
        self.loop = loop
        self.rng = random.Random(42)
        self.request_count = 0

    def connection_made(self, transport):
        self.transport = transport

    def datagram_received(self, data, addr):
        self.request_count += 1
        # Schedule async handling
        self.loop.create_task(self._handle(data, addr))

    async def _handle(self, data: bytes, addr):
        try:
            request = DNSRecord.parse(data)
        except Exception:
            return

        qname = str(request.q.qname).rstrip(".")
        qtype = request.q.qtype

        # Sample delay from real distribution
        delay_ms = self.rng.choice(self.config.dns_latencies)
        delay_s = delay_ms / 1000.0
        await asyncio.sleep(delay_s)

        # Build response
        reply = DNSRecord(
            DNSHeader(id=request.header.id, qr=1, aa=1, ra=1),
            q=request.q,
        )

        if qtype == QTYPE.TXT and qname.startswith("_mcp."):
            domain = qname[5:]  # strip "_mcp." prefix
            if domain in self.config.mcp_enabled:
                # MCP-enabled: return TXT record
                txt_value = f"v=mcp1; src=https://mcp.{domain}; auth=none"
                reply.add_answer(
                    RR(
                        rname=request.q.qname,
                        rtype=QTYPE.TXT,
                        rdata=TXT(txt_value),
                        ttl=300,
                    )
                )
                reply.header.rcode = RCODE.NOERROR
            else:
                # Not MCP-enabled: NXDOMAIN
                reply.header.rcode = RCODE.NXDOMAIN
        else:
            # Not a _mcp TXT query: NXDOMAIN
            reply.header.rcode = RCODE.NXDOMAIN

        self.transport.sendto(reply.pack(), addr)


async def start_dns_server(config: SimConfig) -> asyncio.DatagramTransport:
    """Start the simulated DNS server. Returns the transport for shutdown."""
    loop = asyncio.get_running_loop()
    transport, protocol = await loop.create_datagram_endpoint(
        lambda: SimDNSProtocol(config, loop),
        local_addr=(SIM_DNS_HOST, SIM_DNS_PORT),
    )
    print(f"[sim] DNS server listening on {SIM_DNS_HOST}:{SIM_DNS_PORT}")
    return transport


async def main():
    """Run the DNS server standalone for testing."""
    config = SimConfig()
    print(config.summary())
    print()

    transport = await start_dns_server(config)

    print("[sim] DNS server running. Press Ctrl+C to stop.")
    try:
        while True:
            await asyncio.sleep(3600)
    except asyncio.CancelledError:
        pass
    finally:
        transport.close()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n[sim] DNS server stopped.")
