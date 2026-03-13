# MCP Discovery Benchmark: DNS vs HTTP

How should AI agents discover MCP servers? This benchmark tests two candidates head-to-head across 201 domains and 5 concurrency levels to find out.

## Hypothesis

DNS-based MCP discovery (`_mcp.{domain}` TXT records, as implemented by [mcp-www](https://github.com/kormco/mcp-www)) will be significantly faster and more reliable than HTTP-based discovery (`/.well-known/mcp`) for detecting whether a domain advertises an MCP server, because:

1. **DNS responses are small and cacheable.** A TXT lookup returns ~100 bytes and is served from recursive resolver caches after the first query. HTTP requires a full TLS handshake, TCP connection, and application-layer response for every domain.
2. **DNS fails fast.** NXDOMAIN for a non-MCP domain returns in a single round-trip. HTTP must wait for a TCP timeout, TLS failure, or application-level 404/error from each origin server.
3. **DNS scales through the resolver.** Recursive resolvers are designed to handle thousands of concurrent lookups. HTTP discovery puts the concurrency burden on the client and the diverse set of origin servers being queried.

We test this with the real `mcp-www` npm package (not raw DNS), so latencies include the full tool invocation: subprocess communication, DNS lookup, TXT record parsing, and (when found) manifest fetch from the advertised server URL. This is an apples-to-apples comparison of the complete discovery flow.

## Experiment Design

### Methods Under Test

| Method | What it does | Implementation |
|--------|-------------|----------------|
| **mcp-www** (`browse_discover`) | DNS TXT lookup for `_mcp.{domain}`, parse the record, fetch the manifest from the advertised server URL via JSON-RPC | `kormco/mcp-www` npm package running as a subprocess, called over stdio JSON-RPC |
| **HTTP** (`/.well-known/mcp`) | Direct HTTPS GET to `https://{domain}/.well-known/mcp` | `httpx.AsyncClient` with 5s timeout, follow redirects |

### Test Matrix

| Parameter | Value |
|-----------|-------|
| **Platform** | Linux (Ubuntu) |
| **DNS Resolver** | Unbound (local recursive, `192.168.68.133:5335`) |
| **Concurrency levels** | 1, 10, 50, 100, 500 |
| **Cache states** | Cold (resolver cache flushed), Warm (pre-populated) |
| **Domains** | 201 across 5 categories |
| **Runs per config** | 3 (alternating method order) |
| **Total queries** | 12,060 |

### Domain Categories

| Category | Count | Description |
|----------|-------|-------------|
| A | 1 | MCP-enabled (known `_mcp` TXT record) |
| B | 50 | Popular domains (Tranco-style top list) |
| C | 50 | Nonexistent domains (randomly generated) |
| D | 50 | Slow/unreliable domains (uncommon TLDs) |
| E | 50 | HTTPS-only sites (no MCP expected) |

Only 1 of 201 domains (0.5%) has an MCP server. This reflects current real-world adoption and tests the dominant case: quickly determining that a domain does *not* offer MCP.

## Results

**mcp-www is 919x faster at low concurrency and 106x faster at high concurrency, with 100% success vs ~55% for HTTP.**

### Latency Comparison

| Method | Concurrency | Cache | Median (ms) | P95 (ms) | P99 (ms) | Success % | MCP Found % | Throughput (q/s) |
|--------|-------------|-------|-------------|----------|----------|-----------|-------------|------------------|
| HTTP (/.well-known/mcp) | c1 | cold | 476.9 | 3627.9 | 5363.1 | 55.1 | 0.0 | 1.1 |
| HTTP (/.well-known/mcp) | c1 | warm | 445.1 | 3059.9 | 5373.3 | 55.4 | 0.0 | 1.2 |
| HTTP (/.well-known/mcp) | c10 | cold | 479.8 | 3011.4 | 5336.1 | 55.2 | 0.0 | 1.2 |
| HTTP (/.well-known/mcp) | c10 | warm | 497.1 | 3663.7 | 5333.5 | 54.9 | 0.0 | 1.2 |
| HTTP (/.well-known/mcp) | c50 | cold | 552.1 | 3420.1 | 5387.7 | 55.2 | 0.0 | 1.1 |
| HTTP (/.well-known/mcp) | c50 | warm | 535.6 | 3632.6 | 5384.2 | 55.4 | 0.0 | 1.1 |
| HTTP (/.well-known/mcp) | c100 | cold | 1081.9 | 3917.3 | 6127.5 | 55.4 | 0.0 | 0.7 |
| HTTP (/.well-known/mcp) | c100 | warm | 1197.1 | 4595.2 | 6364.0 | 55.2 | 0.0 | 0.7 |
| HTTP (/.well-known/mcp) | c500 | cold | 1874.9 | 4060.0 | 7001.2 | 55.2 | 0.0 | 0.5 |
| HTTP (/.well-known/mcp) | c500 | warm | 1797.9 | 4149.5 | 7063.5 | 54.9 | 0.0 | 0.5 |
| mcp-www (browse_discover) | c1 | cold | 0.5 | 1.2 | 5.8 | 100.0 | 0.5 | 376.9 |
| mcp-www (browse_discover) | c1 | warm | 0.5 | 0.9 | 6.1 | 100.0 | 0.5 | 505.5 |
| mcp-www (browse_discover) | c10 | cold | 1.2 | 3.4 | 6.9 | 100.0 | 0.5 | 292.9 |
| mcp-www (browse_discover) | c10 | warm | 0.9 | 1.6 | 1.9 | 100.0 | 0.5 | 430.0 |
| mcp-www (browse_discover) | c50 | cold | 5.1 | 7.5 | 7.9 | 100.0 | 0.5 | 144.5 |
| mcp-www (browse_discover) | c50 | warm | 4.3 | 5.9 | 6.0 | 100.0 | 0.5 | 177.7 |
| mcp-www (browse_discover) | c100 | cold | 8.3 | 12.5 | 12.9 | 100.0 | 0.5 | 94.8 |
| mcp-www (browse_discover) | c100 | warm | 7.2 | 11.6 | 12.3 | 100.0 | 0.5 | 114.9 |
| mcp-www (browse_discover) | c500 | cold | 17.7 | 18.4 | 19.5 | 100.0 | 0.5 | 54.5 |
| mcp-www (browse_discover) | c500 | warm | 13.5 | 17.0 | 17.1 | 100.0 | 0.5 | 70.7 |

## Analysis

### 1. Latency: Orders-of-magnitude difference

At c=1 with a cold cache, mcp-www returns a median response in **0.5ms** vs **476.9ms** for HTTP (919x faster). The gap persists at scale: at c=500, mcp-www stays at **17.7ms** median while HTTP degrades to **1874.9ms**.

The CDF plots show the distributions barely overlap. HTTP latency has a long tail extending past 5 seconds (the timeout), while mcp-www latency is tightly clustered in the single-digit millisecond range.

![Latency Cdf Cold](latency_cdf_cold.png)

![Latency Cdf Warm](latency_cdf_warm.png)

### 2. Reliability: DNS fails gracefully, HTTP doesn't

mcp-www achieves **100% success** across all concurrency levels. HTTP only reaches **55%** even at c=500, meaning ~45% of HTTP probes fail due to connection timeouts, TLS errors, or servers rejecting the request.

This is the critical difference for an indexer use case. A discovery system that fails on 45% of domains will either miss MCP servers or require expensive retries. DNS returns a definitive NXDOMAIN for non-MCP domains without hitting the origin server at all.

### 3. Throughput: DNS scales, HTTP degrades

At c=1, mcp-www sustains **377 q/s** vs HTTP's **1.1 q/s** — a **344x** difference. As concurrency increases, HTTP throughput remains flat or *decreases* (to 0.5 q/s at c=500) because timeouts and connection failures consume more wall-clock time. mcp-www throughput also decreases with concurrency (55 q/s at c=500) due to the single-process architecture, but remains dramatically higher throughout.

![Throughput Cold](throughput_cold.png)

![Throughput Warm](throughput_warm.png)

### 4. Cache effects: Minimal for DNS, marginal for HTTP

Warming the DNS resolver cache provides a modest 1.1x improvement for mcp-www (0.5ms -> 0.5ms at c=1). HTTP sees a similar marginal gain (1.1x). This suggests DNS latency is already dominated by local resolver performance rather than upstream lookups, while HTTP latency is dominated by the TLS/TCP overhead to each origin server, which caching doesn't help.

### 5. Statistical significance

All comparisons are statistically significant (p < 0.001 after Bonferroni correction) with large effect sizes (Cohen's d > 1.0). The Mann-Whitney U test was chosen because latency distributions are heavily skewed and non-normal.

| Comparison | Concurrency | Cache | Median A (ms) | Median B (ms) | Speedup | p-value | Significant | Effect Size |
|------------|-------------|-------|---------------|---------------|---------|---------|-------------|-------------|
| http_well_known vs mcp_www | 1 | cold | 476.9 | 0.5 | 0.00x | 3.92e-197 | Yes | 1.131 |
| http_well_known vs mcp_www | 1 | warm | 445.1 | 0.5 | 0.00x | 1.04e-197 | Yes | 1.091 |
| http_well_known vs mcp_www | 10 | cold | 479.8 | 1.2 | 0.00x | 4.05e-197 | Yes | 1.070 |
| http_well_known vs mcp_www | 10 | warm | 497.1 | 0.9 | 0.00x | 8.53e-198 | Yes | 1.065 |
| http_well_known vs mcp_www | 50 | cold | 552.1 | 5.1 | 0.01x | 2.61e-197 | Yes | 1.111 |
| http_well_known vs mcp_www | 50 | warm | 535.6 | 4.3 | 0.01x | 6.15e-198 | Yes | 1.123 |
| http_well_known vs mcp_www | 100 | cold | 1081.9 | 8.3 | 0.01x | 4.47e-198 | Yes | 1.623 |
| http_well_known vs mcp_www | 100 | warm | 1197.1 | 7.2 | 0.01x | 1.98e-198 | Yes | 1.670 |
| http_well_known vs mcp_www | 500 | cold | 1874.9 | 17.7 | 0.01x | 2.25e-198 | Yes | 2.009 |
| http_well_known vs mcp_www | 500 | warm | 1797.9 | 13.5 | 0.01x | 1.73e-198 | Yes | 2.024 |

## What if 50% of domains had MCP servers?

The real-world experiment above tests today's reality: almost no domains have MCP servers. But what happens when adoption grows? We simulated a scenario where 100 of 201 domains (50%) advertise MCP servers, using local DNS and HTTP sim servers with latency sampled from the real cold-cache distributions.

This changes the workload significantly: instead of mostly returning "not found," both methods now need to complete the full discovery flow for half of all queries. For mcp-www, that means DNS lookup + manifest fetch via JSON-RPC. For HTTP, that means receiving and parsing the `.well-known/mcp` response body.

### Simulation Results

| Method | Concurrency | Cache | Median (ms) | P95 (ms) | P99 (ms) | Success % | MCP Found % | Throughput (q/s) |
|--------|-------------|-------|-------------|----------|----------|-----------|-------------|------------------|
| HTTP (/.well-known/mcp) | c1 | cold | 672.5 | 5006.2 | 5009.1 | 94.5 | 46.6 | 0.9 |
| HTTP (/.well-known/mcp) | c10 | cold | 680.5 | 3935.4 | 5004.7 | 95.9 | 47.9 | 0.9 |
| HTTP (/.well-known/mcp) | c50 | cold | 731.9 | 3406.2 | 5013.3 | 96.5 | 48.6 | 0.9 |
| HTTP (/.well-known/mcp) | c100 | cold | 735.0 | 4008.4 | 5095.7 | 95.5 | 47.4 | 0.8 |
| HTTP (/.well-known/mcp) | c500 | cold | 1446.9 | 4111.4 | 6115.8 | 96.2 | 47.8 | 0.6 |
| mcp-www (browse_discover) | c1 | cold | 10.1 | 28.0 | 33.7 | 100.0 | 50.2 | 77.8 |
| mcp-www (browse_discover) | c10 | cold | 8.5 | 21.6 | 26.7 | 100.0 | 50.2 | 79.6 |
| mcp-www (browse_discover) | c50 | cold | 29.2 | 63.3 | 74.7 | 100.0 | 50.2 | 30.5 |
| mcp-www (browse_discover) | c100 | cold | 51.0 | 109.9 | 122.8 | 100.0 | 50.2 | 17.8 |
| mcp-www (browse_discover) | c500 | cold | 74.0 | 150.3 | 166.5 | 100.0 | 50.2 | 13.2 |

### Simulation Analysis

Even with 50% adoption, mcp-www remains **67x faster** at c=1 (10.1ms vs 672.5ms) and **20x faster** at c=500 (74.0ms vs 1446.9ms).

mcp-www latency increases from 0.5ms (real) to 10.1ms (sim) at c=1 because half the queries now require a manifest fetch in addition to the DNS lookup. Despite the extra work, mcp-www still completes with **100% success** vs **96%** for HTTP at c=500.

The MCP Found rate converges to the expected ~50% for both methods, confirming the simulation is working correctly.

### Simulation Statistical Comparisons

| Comparison | Concurrency | Cache | Median A (ms) | Median B (ms) | Speedup | p-value | Significant | Effect Size |
|------------|-------------|-------|---------------|---------------|---------|---------|-------------|-------------|
| http_well_known vs mcp_www | 1 | cold | 672.5 | 10.1 | 0.02x | 1.49e-197 | Yes | 1.332 |
| http_well_known vs mcp_www | 10 | cold | 680.5 | 8.5 | 0.01x | 2.73e-197 | Yes | 1.375 |
| http_well_known vs mcp_www | 50 | cold | 731.9 | 29.2 | 0.04x | 1.25e-197 | Yes | 1.438 |
| http_well_known vs mcp_www | 100 | cold | 735.0 | 51.0 | 0.07x | 1.60e-197 | Yes | 1.386 |
| http_well_known vs mcp_www | 500 | cold | 1446.9 | 74.0 | 0.05x | 4.23e-198 | Yes | 1.794 |

![Latency Cdf Cold 50Pct Adoption Sim](latency_cdf_cold_50pct_adoption_sim.png)

![Throughput Cold 50Pct Adoption Sim](throughput_cold_50pct_adoption_sim.png)

## Discussion

### Why is DNS so much faster?

The speed difference comes from what each method avoids:

- **No TLS handshake.** DNS operates over UDP (or TCP for large responses). HTTP discovery requires a TLS handshake with *each* origin server, which alone accounts for 100-300ms on a typical connection.
- **No origin server dependency.** DNS queries go through a recursive resolver, which caches results and handles failures. HTTP discovery depends on 201 different origin servers, each with different response times, availability, and error modes.
- **NXDOMAIN is instant.** When a domain doesn't have MCP, the DNS resolver returns NXDOMAIN in a single packet. HTTP must wait for TCP connect + TLS + HTTP response or timeout.

### Why does HTTP have ~45% failure rate?

The 201 domain list includes nonexistent domains, slow TLDs, and sites that don't serve `/.well-known/mcp`. These are realistic: an indexer scanning arbitrary domains will encounter all of these. Failures include:

- Connection timeouts (5s limit) for unreachable hosts
- TLS handshake failures for domains with misconfigured or missing certificates
- Connection refused for domains not running a web server
- HTTP errors (404, 403, 500) from servers that don't support the endpoint

DNS handles all of these cases with NXDOMAIN or SERVFAIL, which are fast, definitive responses rather than timeouts.

### Limitations

- **Single MCP-enabled domain.** Only `korm.co` has a real `_mcp` TXT record, so MCP Found rates (0.5%) reflect current adoption, not detection accuracy. The 50% simulation addresses this.
- **Local resolver.** DNS latency depends on the resolver. A remote resolver (e.g. Google Public DNS) would add network RTT. However, production indexers would typically run their own recursive resolver.
- **mcp-www overhead.** The mcp-www prober includes subprocess stdio overhead that a native integration would avoid. Real-world latency could be even lower.
- **No CDN effects.** Some well-known endpoints might be served from CDN edge caches in production, reducing HTTP latency for popular domains.
- **Single machine.** Both probers run on the same machine, so network conditions are identical. A distributed benchmark might show different scaling characteristics.

## Conclusion

DNS-based discovery via mcp-www is **919x faster** (median) and **100% reliable** compared to HTTP-based discovery at `/.well-known/mcp`, which achieves only ~55% success. The advantage holds across all concurrency levels (1 to 500), both cache states, and in a simulated 50% adoption scenario.

For an MCP indexer scanning thousands of domains, DNS-based discovery is not just faster — it's a fundamentally different reliability profile. DNS provides a definitive answer (record exists or NXDOMAIN) without depending on the target's web server availability, TLS configuration, or endpoint support. HTTP discovery inherits all the fragility of making HTTPS connections to arbitrary domains across the internet.

The hypothesis is confirmed: DNS-based MCP discovery is significantly faster and more reliable than HTTP-based discovery for the indexer use case.

## Methodology

### Probers

- **mcp-www:** Spawns `node dist/index.js` as a subprocess. Sends `browse_discover` calls via JSON-RPC over stdio. A single Node.js process handles all concurrent requests asynchronously, with request/response multiplexing by JSON-RPC ID.
- **HTTP:** `httpx.AsyncClient` with `asyncio.Semaphore` for concurrency control. Direct HTTPS GET to `https://{domain}/.well-known/mcp` with 5s timeout and redirect following.

### Statistical Methods

- **Comparison test:** Mann-Whitney U (non-parametric, appropriate for skewed latency distributions)
- **Correction:** Bonferroni (10 comparisons)
- **Effect sizes:** Cohen's d
- **Confidence intervals:** Bootstrap, 10,000 resamples on medians
- **Reproducibility seed:** 42

### Simulation

The 50% adoption simulation runs local servers:
- **Sim DNS server** (UDP, dnslib): Returns TXT records for MCP-enabled domains, NXDOMAIN for others. Injects latency sampled from real cold-cache distributions.
- **Sim HTTP server** (aiohttp): Responds to `/.well-known/mcp` with MCP manifests for enabled domains, 404 for others. Same latency injection.
- **Sim MCP server** (aiohttp): Minimal JSON-RPC server that responds to `initialize`, `tools/list`, `resources/list`, `prompts/list` so mcp-www can complete the manifest fetch.

## Reproducibility

```bash
pip install -r requirements.txt
cd ../mcp-www && npm install && npm run build  # build mcp-www locally
cd ../mcp-www-benchmark
python scripts/run_experiment.py
python scripts/analyze_results.py
python scripts/generate_combined_report.py
```
