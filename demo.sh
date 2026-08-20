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

# Resolve a Python 3 interpreter. `python` is not reliably on PATH in Git Bash on Windows
# (the Store alias lives in WindowsApps, which PowerShell exposes and bash often does not),
# and an alias that exists but does not run is worse than one that is missing.
find_python() {
  local c
  for c in "${PYTHON:-}" python3 python py; do
    [ -z "$c" ] && continue
    if command -v "$c" >/dev/null 2>&1; then
      if "$c" -c "import sys; sys.exit(0 if sys.version_info[0]==3 else 1)" >/dev/null 2>&1; then
        printf '%s' "$c"; return 0
      fi
    fi
  done
  # ${VAR:-} throughout: `set -u` turns an unset LOCALAPPDATA (any non-Windows shell) into
  # a spurious "unbound variable" line before the real diagnostic gets printed.
  for c in "${LOCALAPPDATA:-}/Microsoft/WindowsApps/python3.exe" \
           "${LOCALAPPDATA:-}/Microsoft/WindowsApps/python.exe"; do
    if [ -x "$c" ] && "$c" -c "import sys; sys.exit(0)" >/dev/null 2>&1; then
      printf '%s' "$c"; return 0
    fi
  done
  return 1
}

if ! PY="$(find_python)"; then
  cat >&2 <<'MSG'
ERROR: no working Python 3 interpreter found on PATH.

  Tried: $PYTHON, python3, python, py, and the Windows Store aliases.

  Fixes, quickest first:
    PYTHON=/c/Path/to/python.exe bash demo.sh     # point at it explicitly
    py -3 -m are.cli selftest                     # or run the CLI directly
    winget install Python.Python.3.11             # if Python is genuinely absent

  On Windows, `python` frequently resolves in PowerShell but not in Git Bash.
MSG
  exit 127
fi
echo "using interpreter: $PY ($("$PY" --version 2>&1))"

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
# deny. That specific failure is expected and the demo continues. Anything else — a crash,
# a missing dependency, an L1 breach — must STOP the demo rather than be dressed up as the
# expected one. An `|| echo` here previously swallowed "python: command not found" and
# printed the L3 caveat instead, which is precisely the wrong thing to do in front of a room.
set +e
"$PY" -m are.cli selftest
SELFTEST_RC=$?
set -e
if [ "$SELFTEST_RC" -eq 0 ]; then
  :
elif [ "$SELFTEST_RC" -eq 1 ] && [ -n "${ANTHROPIC_API_KEY:-}" ]; then
  echo "   (selftest exit 1 with a live key — expected: L3 is degraded online, see above)"
else
  echo "" >&2
  echo "ERROR: selftest exited $SELFTEST_RC, and that is NOT the expected online-L3" >&2
  echo "       failure. Stopping: do not demo a harness that fails its own checks." >&2
  exit "$SELFTEST_RC"
fi

if [[ -n "$SMOKE" ]]; then
  say "SMOKE RUN — 6 scenarios x 4 agents, ${CAPS}"
  say "Check the scorecards below for invalid_rate before running the full suite."
fi

say "1. Four agents. One careful, three with injected defects. The platform is not told which."
"$PY" -m are.cli calibrate --scenarios "$FROZEN" $MODE $LIMIT $NREP $CAPS --no-sandbox

if [[ -n "$SMOKE" ]]; then
  say "Smoke run complete. If invalid_rate is 0 and nothing hung, run the full suite:"
  echo "   ./demo.sh --online"
  if [[ -f runs/calibration.json && "$CALJSON" != runs/calibration.json ]]; then
    say "offline vs online, same format"
    "$PY" -m are.cli compare-modes runs/calibration.json "$CALJSON" || true
  fi
  exit 0
fi

say "2. Drill into one PushoverAgent failure: framing -> irreversible call -> the assertion that caught it"
"$PY" -m are.cli run --agent pushover --scenarios "$FROZEN" $MODE $JUDGE $CAPS \
  --n 3 --jobs 6 --run-id demo-pushover-v1 --report

say "3. v1 -> v2 of the same agent: a partial fix, measured pairwise"
"$PY" -m are.cli run --agent pushover_v2 --scenarios "$FROZEN" $MODE $JUDGE $CAPS \
  --n 3 --jobs 6 --run-id demo-pushover-v2 --report
"$PY" -m are.cli compare runs/demo-pushover-v1 runs/demo-pushover-v2
"$PY" -m are.cli report runs/demo-pushover-v2 --compare runs/demo-pushover-v2

if [[ -f runs/calibration.json && "$CALJSON" != runs/calibration.json ]]; then
  say "4. offline vs online — did the ranking survive real models?"
  "$PY" -m are.cli compare-modes runs/calibration.json "$CALJSON" || true
fi

say "5. Open the report — every section is stamped ONLINE or OFFLINE"
echo "   runs/demo-pushover-v2/report.html"

say "6. Say the limitations before anyone asks"
sed -n '/^## Limitations/,/^## Dual-use/p' README.md | head -40
