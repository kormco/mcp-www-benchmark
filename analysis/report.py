"""Generate a markdown report from experiment results."""

import json
import os
from typing import List

from config import REPORT_DIR, RESULTS_DIR, METHOD_LABELS
from src.models import QueryResult
from analysis.stats import load_all_results, analyze_all
from analysis.plots import generate_all_plots


def generate_report():
    """Run analysis, generate plots, and write the markdown report."""
    os.makedirs(REPORT_DIR, exist_ok=True)

    # Load results
    print("Loading results...")
    results = load_all_results()
    if not results:
        print("No results found. Run the experiment first.")
        return

    # Filter out warmup
    results = [r for r in results if r.cache_state != "warmup"]
    print(f"Loaded {len(results)} results")

    # Run analysis
    print("Running statistical analysis...")
    analysis = analyze_all(results)

    # Save raw analysis
    with open(os.path.join(REPORT_DIR, "analysis.json"), "w") as f:
        json.dump(analysis, f, indent=2, default=str)

    # Generate plots
    print("Generating charts...")
    plot_paths = generate_all_plots(results)
    print(f"Generated {len(plot_paths)} charts")

    # Load metadata if available
    metadata = {}
    meta_path = os.path.join(RESULTS_DIR, "metadata.json")
    if os.path.exists(meta_path):
        with open(meta_path) as f:
            metadata = json.load(f)

    # Build report
    report = []
    report.append("# MCP Discovery Benchmark Report\n")
    report.append("## Abstract\n")
    report.append(
        "This experiment compares three approaches to discovering MCP (Model Context Protocol) "
        "servers across a set of domains: (1) DNS TXT record lookup via the mcp-www standard, "
        "(2) HTTP-based discovery via `/.well-known/mcp`, and (3) full website scraping with "
        "HTML pattern matching. We measure latency, throughput, bandwidth, and success rates "
        "across varying concurrency levels to determine which method scales best for large-scale "
        "MCP server indexing.\n"
    )

    # Methodology
    report.append("## Methodology\n")
    if metadata:
        report.append(f"- **Platform:** {metadata.get('platform', 'unknown')}\n")
        report.append(f"- **Python:** {metadata.get('python_version', 'unknown').split()[0]}\n")
        report.append(f"- **Domains tested:** {metadata.get('domain_count', 'unknown')}\n")
        report.append(f"- **Total queries:** {metadata.get('total_queries', 'unknown')}\n")
        report.append(f"- **Total runtime:** {metadata.get('elapsed_seconds', 0):.1f}s\n")
    report.append("")

    # Summary table
    report.append("## Results Summary\n")
    report.append("### Latency by Method and Concurrency\n")
    report.append("| Method | Concurrency | Cache | Median (ms) | P95 (ms) | P99 (ms) | Success % | Throughput (q/s) |")
    report.append("|--------|-------------|-------|-------------|----------|----------|-----------|------------------|")

    for key in sorted(analysis["summary"].keys()):
        s = analysis["summary"][key]
        parts = key.rsplit("_", 2)
        # Parse method_cN_cache format
        method = "_".join(parts[:-2]) if len(parts) > 2 else parts[0]
        label = METHOD_LABELS.get(method, method)
        concurrency = parts[-2] if len(parts) > 1 else "?"
        cache = parts[-1] if len(parts) > 1 else "?"

        report.append(
            f"| {label} | {concurrency} | {cache} | "
            f"{s['median']:.1f} | {s['p95']:.1f} | {s['p99']:.1f} | "
            f"{s['success_rate']*100:.1f} | {s.get('throughput_qps', 0):.1f} |"
        )
    report.append("")

    # Statistical comparisons
    report.append("### Statistical Comparisons\n")
    report.append("| Comparison | Concurrency | Cache | Median A (ms) | Median B (ms) | Speedup | p-value | Significant | Effect Size |")
    report.append("|------------|-------------|-------|---------------|---------------|---------|---------|-------------|-------------|")

    for comp in analysis["comparisons"]:
        sig = "Yes" if comp["significant"] else "No"
        report.append(
            f"| {comp['comparison']} | {comp['concurrency']} | {comp['cache_state']} | "
            f"{comp['median_a']:.1f} | {comp['median_b']:.1f} | "
            f"{comp['speedup']:.2f}x | {comp['p_value']:.2e} | {sig} | "
            f"{comp['cohens_d']:.3f} |"
        )
    report.append("")

    # Charts
    report.append("## Charts\n")
    for path in plot_paths:
        filename = os.path.basename(path)
        title = filename.replace("_", " ").replace(".png", "").title()
        report.append(f"### {title}\n")
        report.append(f"![{title}]({filename})\n")

    # Discussion
    report.append("## Discussion\n")
    report.append(
        "The results should be interpreted considering:\n"
        "- DNS queries use UDP (connectionless) while HTTP requires TCP+TLS setup\n"
        "- Most domains do NOT have `_mcp` TXT records or `/.well-known/mcp` endpoints, "
        "so 'miss' latency dominates\n"
        "- Website scraping downloads entire HTML pages, consuming significantly more bandwidth\n"
        "- DNS resolver caching and HTTP connection pooling affect warm-cache performance\n"
        "- Windows asyncio uses ProactorEventLoop which may affect UDP performance\n"
    )

    report.append("## Reproducibility\n")
    report.append(
        "Raw results are stored as JSONL files in `results/raw/`. "
        "System metrics are in `results/system_metrics/`. "
        "Re-run analysis with: `python scripts/analyze_results.py`\n"
    )

    # Write report
    report_path = os.path.join(REPORT_DIR, "report.md")
    with open(report_path, "w") as f:
        f.write("\n".join(report))

    print(f"Report written to {report_path}")
    return report_path


if __name__ == "__main__":
    generate_report()
