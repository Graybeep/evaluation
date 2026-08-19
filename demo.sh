#!/usr/bin/env bash
# Three-minute demo (CLAUDE.md §14). Runs offline by default — no API key, no spend.
#   ./demo.sh            scripted calibration policies
#   ./demo.sh --online   the same suite against the pinned model (needs ANTHROPIC_API_KEY)
set -euo pipefail
export PYTHONIOENCODING=utf-8

MODE="--offline"
JUDGE=""
if [[ "${1:-}" == "--online" ]]; then
  MODE=""
  JUDGE="--judge"
  : "${ANTHROPIC_API_KEY:?--online needs ANTHROPIC_API_KEY}"
fi
FROZEN=frozen/frozen_scenarios.json
say() { printf '\n\033[1m== %s\033[0m\n' "$1"; }

say "0. The harness is the risk surface — check it first"
python -m are.cli selftest

say "1. Four agents. One careful, three with injected defects. The platform is not told which."
python -m are.cli calibrate --scenarios "$FROZEN" $MODE --no-sandbox --n 3

say "2. Drill into one PushoverAgent failure: framing -> irreversible call -> the assertion that caught it"
python -m are.cli run --agent pushover --scenarios "$FROZEN" $MODE $JUDGE \
  --n 3 --jobs 6 --run-id demo-pushover-v1 --report

say "3. v1 -> v2 of the same agent: a partial fix, measured pairwise"
python -m are.cli run --agent pushover_v2 --scenarios "$FROZEN" $MODE $JUDGE \
  --n 3 --jobs 6 --run-id demo-pushover-v2 --report
python -m are.cli compare runs/demo-pushover-v1 runs/demo-pushover-v2
python -m are.cli report runs/demo-pushover-v2 --compare runs/demo-pushover-v2

say "4. Open the report — scores with intervals, per-category, pressure deltas, trace drill-down"
echo "   runs/demo-pushover-v2/report.html"

say "5. Say the limitations before anyone asks"
sed -n '/^## Limitations/,/^## Dual-use/p' README.md | head -40
