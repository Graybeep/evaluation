# Commitment — full online calibration pass

**Written 2026-08-23, before the run.** Same discipline as
`JUDGE_LIVE_RUN_COMMITMENT.md`: the reporting rules are fixed while the outcome is still
unknown, because a commitment written afterwards is a description of what happened.

## What this run is

Every headline number in this repo comes from **offline scripted policies**. That is
disclosed (README 1b), but it means the §5 acceptance criterion — the load-bearing result —
has only ever been checked against agents whose defects are *implemented in Python*.

This run checks it against agents whose defects are **a rigged system prompt driving a real
model**. `are/calib/base.py` says the two paths share the adapter, the kill switches and the
verifier; only the policy differs. This is the first test of that claim at suite scale.

```bash
export ANTHROPIC_BASE_URL=https://router.bynara.id
export ANTHROPIC_API_KEY=<key>          # NOT the key exposed on 08-23; rotate first
export ARE_AGENT_MODEL=qwen-3.8-max-free
python -m are.cli calibrate --scenarios frozen/frozen_scenarios.json --n 3
```

## What is being predicted, in advance

The offline result is `clean 100.0 > confabulator 92.2 > looper 65.0 > pushover 31.7`, six
checks passing, zero control false positives, 60/60 discriminating.

**The prediction is the ORDERING, not the numbers.** §5 requires
`clean > {looper, confabulator} > pushover` and ≥70% correct attribution. Absolute composites
are expected to move — a real model is not a scripted policy, and §11.5 already says absolute
scores are not comparable across toolsets. Any of these is a legitimate outcome:

| outcome | what it means | how it gets reported |
|---|---|---|
| ordering holds | the criterion survives contact with a real model | headline gains an online column |
| ordering holds, composites shift a lot | expected; scripted policies are caricatures | reported as-is, both columns shown |
| **ordering breaks** | the rigged prompts do not reproduce their defects | **reported as the primary finding.** The offline numbers stay; a note says the criterion is offline-only |
| `invalid_rate > 5%` | §6.1: not reportable | reported as a harness/endpoint result, and **no composite is quoted from it** |

## What will not happen

- **The prompts will not be tuned to recover the ordering.** That is §13.7 (tuning after
  seeing scores) and it would make the frozen set meaningless.
- **The frozen set will not be touched.** Not regenerated, not filtered, not re-frozen.
- **A partial run will not be quoted as a full one.** If it dies at scenario 40, the artefact
  says 40 and no composite is reported against a 60-scenario denominator.
- **`--offline` numbers will not be silently swapped in** if the online run disappoints.
  The mode is recorded in `meta.json` and in every rendered report.
- **A failed run will not be re-run until it looks better.** The first completed pass is the
  reported one; any subsequent run is reported alongside it, not instead of it.

## The §7.10 trap specific to THIS run

An online run that errors out early can produce a scorecard with a **high composite and a
tiny n** — few runs completed, so few failures found. That reads like a good agent and is
actually a broken run. `n_scenarios`, `n_runs` and `invalid_rate` are quoted with every
number from this run, and a pass is only a pass if `n_scenarios == 60`.

The mirrored trap: `pushover` scoring *well* online would most likely mean the rigged prompt
failed to make it compliant — a **defect-not-reproduced** result, not a safe agent. It is
checked against the defect markers, not inferred from the score.

## Cost and stopping rule

~720 agent runs (60 × 3 × 4 agents), several thousand calls. Prior online agent evidence is
a **single scenario at 20.5s**, so the extrapolation is weak by three orders of magnitude.
Hard stop if `invalid_rate` exceeds 25% at the first agent boundary — that is an endpoint
result, and burning the remaining spend to confirm it is waste.
