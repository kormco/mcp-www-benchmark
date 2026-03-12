#!/bin/bash
# Full pipeline: experiment → analysis → commit → push
# Runs unattended.

set -e
cd /home/kormco/mcp-www-benchmark

echo "=== Starting full experiment pipeline ==="
echo "$(date)"

# Run full experiment
python3 scripts/run_experiment.py 2>&1 | tee results/experiment_log.txt

echo ""
echo "=== Experiment complete, running analysis ==="
echo "$(date)"

# Run analysis + report generation
python3 scripts/analyze_results.py 2>&1
python3 scripts/generate_combined_report.py 2>&1

echo ""
echo "=== Analysis complete, committing and pushing ==="
echo "$(date)"

# Commit everything
git add -A results/ src/mcpwww_prober.py src/runner.py src/models.py config.py analysis/ scripts/ sim/ CLAUDE.md README.md
git commit -m "Benchmark mcp-www browse_discover vs HTTP .well-known/mcp

Replace raw DNS prober with actual mcp-www npm package (browse_discover
tool over stdio JSON-RPC). This measures the real end-to-end discovery
flow: DNS TXT lookup + manifest fetch on hits.

- Add McpWwwClient: spawns mcp-www subprocess, multiplexes JSON-RPC
- Rename method dns_mcp → mcp_www throughout
- Remove prior Windows run data from combined report (not comparable)
- Update sim experiment to use mcp-www against sim DNS server
- Full experiment results included

Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>"

git push origin master

echo ""
echo "=== Pipeline complete ==="
echo "$(date)"
