#!/usr/bin/env bash
# Three-minute demo (CLAUDE.md §14). Runs offline by default — no API key, no spend.
#
#   ./demo.sh                     scripted calibration policies, full frozen set
#   ./demo.sh --online --smoke    FIRST online run: 6 scenarios x 4 agents, hard token cap
#   ./demo.sh --online            full online run — only after --smoke has passed
#
# The smoke path exists because the online path has never executed. Do not spend a full
# budget proving that an untested code path is untested.
set -euo pipefail
export PYTHONIOENCODING=utf-8

MODE="--offline"
JUDGE=""
SMOKE=""
LIMIT=""
NREP="--n 3"
CALJSON=runs/calibration.json

for arg in "$@"; do
  case "$arg" in
    --online)
      MODE=""
      JUDGE="--judge"
      : "${ANTHROPIC_API_KEY:?--online needs ANTHROPIC_API_KEY}"
      CALJSON=runs/calibration-online.json
      ;;
    --smoke)
      SMOKE=1
      LIMIT="--limit 6"
      NREP="--n 1"
      ;;
    *) echo "unknown flag: $arg" >&2; exit 2 ;;
  esac
done

# Hard per-run caps on the smoke path: a runaway loop on an untested path is the one
# failure mode that costs money rather than time (§4.4 L4).
CAPS=""
if [[ -n "$SMOKE" ]]; then
  CAPS="--max-tokens 8000 --wall-clock 60"
fi

FROZEN=frozen/frozen_scenarios.json
say() { printf '\n\033[1m== %s\033[0m\n' "$1"; }

say "0. The harness is the risk surface — check it first"
# With a live key this FAILS on L3 by design (§7.9): online runs have no OS-level egress
# deny. The demo continues; the failure is the honest reading, not a broken check.
python -m are.cli selftest || echo "   (selftest non-zero — expected online, see L3 above)"

if [[ -n "$SMOKE" ]]; then
  say "SMOKE RUN — 6 scenarios x 4 agents, ${CAPS}"
  say "Check the scorecards below for invalid_rate before running the full suite."
fi

say "1. Four agents. One careful, three with injected defects. The platform is not told which."
python -m are.cli calibrate --scenarios "$FROZEN" $MODE $LIMIT $NREP $CAPS --no-sandbox

if [[ -n "$SMOKE" ]]; then
  say "Smoke run complete. If invalid_rate is 0 and nothing hung, run the full suite:"
  echo "   ./demo.sh --online"
  if [[ -f runs/calibration.json && "$CALJSON" != runs/calibration.json ]]; then
    say "offline vs online, same format"
    python -m are.cli compare-modes runs/calibration.json "$CALJSON" || true
  fi
  exit 0
fi

say "2. Drill into one PushoverAgent failure: framing -> irreversible call -> the assertion that caught it"
python -m are.cli run --agent pushover --scenarios "$FROZEN" $MODE $JUDGE $CAPS \
  --n 3 --jobs 6 --run-id demo-pushover-v1 --report

say "3. v1 -> v2 of the same agent: a partial fix, measured pairwise"
python -m are.cli run --agent pushover_v2 --scenarios "$FROZEN" $MODE $JUDGE $CAPS \
  --n 3 --jobs 6 --run-id demo-pushover-v2 --report
python -m are.cli compare runs/demo-pushover-v1 runs/demo-pushover-v2
python -m are.cli report runs/demo-pushover-v2 --compare runs/demo-pushover-v2

if [[ -f runs/calibration.json && "$CALJSON" != runs/calibration.json ]]; then
  say "4. offline vs online — did the ranking survive real models?"
  python -m are.cli compare-modes runs/calibration.json "$CALJSON" || true
fi

say "5. Open the report — every section is stamped ONLINE or OFFLINE"
echo "   runs/demo-pushover-v2/report.html"

say "6. Say the limitations before anyone asks"
sed -n '/^## Limitations/,/^## Dual-use/p' README.md | head -40
