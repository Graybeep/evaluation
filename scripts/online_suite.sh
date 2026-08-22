#!/usr/bin/env bash
# Full online calibration pass. Reporting rules are fixed in advance:
# reports/ONLINE_SUITE_RUN_COMMITMENT.md — read it before quoting any number from here.
#
# The key is read from .env.local (gitignored) so it never enters a transcript,
# a shell history, or a commit. §7.1: the runner holds exactly one secret.
set -euo pipefail
cd "$(dirname "$0")/.."

[ -f .env.local ] || { echo "FATAL: .env.local missing. See scripts/online_suite.sh header."; exit 2; }
set -a; . ./.env.local; set +a

: "${ANTHROPIC_API_KEY:?not set in .env.local}"
: "${ANTHROPIC_BASE_URL:?not set in .env.local}"
export ARE_AGENT_MODEL="${ARE_AGENT_MODEL:-qwen-3.8-max-free}"

echo "endpoint : $ANTHROPIC_BASE_URL"
echo "model    : $ARE_AGENT_MODEL"
echo "key      : sha256:$(printf %s "$ANTHROPIC_API_KEY" | sha256sum | cut -c1-12) (len ${#ANTHROPIC_API_KEY})"
echo "scope    : 60 frozen scenarios x n=3 x 4 agents"
echo

exec python -m are.cli calibrate \
  --scenarios frozen/frozen_scenarios.json \
  --agents clean confabulator looper pushover \
  --n 3 --jobs 4 --out runs --no-sandbox
