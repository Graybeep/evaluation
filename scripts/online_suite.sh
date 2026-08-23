#!/usr/bin/env bash
# Full online calibration pass, IN SANDBOX.
#
# Reporting rules were fixed in advance: reports/ONLINE_SUITE_RUN_COMMITMENT.md.
# Read it before quoting any number produced here.
#
# The key is read from .env.local (gitignored) so it never enters a transcript, a
# shell history, or a commit. §7.1: the runner holds exactly one secret.
#
#   scripts/online_suite.sh preflight   # 2 scenarios x 1 repeat, ~2 min, checks the path
#   scripts/online_suite.sh full        # 60 x 3 x 4 agents
set -euo pipefail
cd "$(dirname "$0")/.."

MODE="${1:-preflight}"

[ -f .env.local ] || { echo "FATAL: .env.local missing. See the header of this script."; exit 2; }
set -a; . ./.env.local; set +a
: "${ANTHROPIC_API_KEY:?not set in .env.local}"
: "${ANTHROPIC_BASE_URL:?not set in .env.local}"
export ARE_AGENT_MODEL="${ARE_AGENT_MODEL:-qwen-3.8-max-free}"

# Online turns are model round-trips, so the INNER wall clock has to cover a 25-call
# agent. The outer sandbox cap derives from this (are/runner/sandbox.py) and stays
# above it, so a slow-but-legal run is the agent's TIMEOUT, never a harness INVALID.
CAPS="--wall-clock 240 --max-tokens 30000"

echo "endpoint : $ANTHROPIC_BASE_URL"
echo "model    : $ARE_AGENT_MODEL"
echo "key      : sha256:$(printf %s "$ANTHROPIC_API_KEY" | sha256sum | cut -c1-12) (len ${#ANTHROPIC_API_KEY})"
echo "sandbox  : ON  (L1 mocking + L2 process/fs + L3 process-level allowlist + L4 budgets)"
echo "           L3 is process-level, not OS-level: a live key requires egress (§7.9)."
echo "caps     : $CAPS"

if [ "$MODE" = "preflight" ]; then
  echo "mode     : PREFLIGHT — 2 scenarios x 1 repeat x 4 agents"
  echo
  # The sandboxed ONLINE path has never been run. Row 19 was a sandbox defect that
  # scaled with trace size and reported invalid_rate 0.0% while observing nothing, so
  # this path gets checked small before ~720 runs are spent on it.
  python -m are.cli calibrate --scenarios frozen/frozen_scenarios.json \
      --agents clean confabulator looper pushover \
      --n 1 --limit 2 --jobs 2 $CAPS --out runs/online-preflight
  echo
  echo "Check BEFORE running full:"
  echo "  * invalid_rate must be 0 — an outer-cap trip now means the harness, not the agent"
  echo "  * looper must show BUDGET_EXCEEDED or TIMEOUT, and a NON-ZERO tool_call_count"
  echo "  * model_version must name the gateway, not 'unknown' (that is a killed skeleton)"
  exit 0
fi

if [ "$MODE" != "full" ]; then echo "usage: $0 [preflight|full]"; exit 2; fi

echo "mode     : FULL — 60 scenarios x 3 repeats x 4 agents (~720 runs)"
echo
exec python -m are.cli calibrate --scenarios frozen/frozen_scenarios.json \
    --agents clean confabulator looper pushover \
    --n 3 --jobs 4 $CAPS --out runs/online-suite
