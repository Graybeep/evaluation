#!/usr/bin/env bash
# Build the three runs the demo's regression beat compares.
#
# runs/ is gitignored, so a fresh clone has nothing to compare. Without this the
# demo's beat 4 crashed — and exited 1, which is ALSO the expected code for that
# beat, so a rehearsal could pass for the wrong reason. Takes ~15s, offline.
set -euo pipefail
PY="${PYTHON:-python}"
S="frozen/frozen_scenarios.json"
for spec in "looper:p3-v1" "looper_v2:p3-v2" "looper:p3-v1b"; do
  agent="${spec%%:*}"; out="${spec##*:}"
  if [ ! -f "runs/$out/verdicts.json" ]; then
    echo "  building runs/$out ($agent) ..."
    "$PY" -m are.cli run --agent "$agent" --scenarios "$S" \
        --offline --n 3 --out "runs/$out" --no-sandbox >/dev/null
  else
    echo "  runs/$out already present"
  fi
done
echo "  ready: p3-v1 (looper@v1), p3-v2 (looper@v2 partial fix), p3-v1b (A/A null)"
