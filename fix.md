# ARE — Gap & Limitation Remediation Spec

Input for Claude Code. Derived from `PROJECT_CONTEXT.md` §8–§11. **Every status claim in
that doc is self-reported and unverified — verify before acting on any item below.**

## Ground rules (violating these costs more than the fix is worth)

- `frozen/frozen_scenarios.json` does NOT change. No item here requires a re-freeze. If a
  fix seems to need one, stop and report instead.
- Tags immutable. Verify at tag, not HEAD.
- Never tune detectors to restore an expected ranking.
- Every fix ships with a regression test that **fails on revert**. Absence of a failing
  test = fix not landed.
- Finding > feature. If an item grows into new surface area, cut it.
- Apply §6's rule to every fix: assert the positive condition; route "not measured" to an
  explicit non-success state that never renders as clean.

---

## TIER 0 — free, from existing artifacts, no new runs

### G3 — Detector correlation known but never reported
- **Claim:** 8 independent rule detectors.
- **Risk:** §3 chose worst-finding scoring *because* detectors correlate. Structure never
  published. If two co-fire ~always they are one detector; "8 detectors" overstates coverage.
- **Fix:** pairwise co-fire matrix over all existing run artifacts. Emit
  `reports/detector_cofire.json` + rendered table.
- **Verify:** 8×8, diagonal = raw fire counts. Flag any pair with Jaccard > 0.9. Test
  asserts matrix is fully populated (no `null` cells silently read as "uncorrelated").
- **Effort:** 30m.

### G4 — No discrimination check on the frozen suite
- **Risk:** a scenario every agent passes contributes zero information. Effective suite
  size may be well under 60.
- **Fix:** per scenario, count agent pairs it separates. Emit `reports/suite_discrimination.json`.
  Report: N scenarios separating ≥1 pair, N separating 0.
- **Verify:** counts sum to 60 exactly. Do not accept a partition that doesn't sum (see
  §6, `quitter`/MISSING_CLARIFICATION precedent).
- **Effort:** 45m.

### G2 — No published false-positive rate on `clean`
- **Risk:** most important single number the platform has. A suite that flags the clean
  agent is worthless. Absent from §8 entirely.
- **Fix:** per-detector FP rate on `clean` across all 60 scenarios, with Wilson **upper**
  bound (upper, not lower — you are bounding a bad thing).
- **Verify:** denominator per detector = scenarios where that detector was *applicable*,
  not 60 by default. Emit applicability count alongside.
- **Effort:** 45m.

### L13 — Worst-finding scoring discards within-band mode variation
- **Fix:** emit `distinct_modes` alongside severity band. `looper: HIGH, distinct_modes: 9`.
- **Verify:** score values unchanged (assert byte-identical composite scores pre/post).
  Purely additive field. No re-freeze.
- **Effort:** 30m.

### L12 + L11 — Fabrication coverage stated as one number
- **Fix:** collapse two bullets into one published figure: rule-based fabrication
  detection is validated on **17/60 = 28% of the suite**; the other 43 are refuse/ask-only
  where the rule is structurally blind and only the (unvalidated) judge would apply.
- **Verify:** `0.82` Wilson LB confirmed correct for 17/17 — keep quoting the bound, not
  the point estimate. Assert the 17/43 split sums to 60.
- **Effort:** 15m, docs only.

### G6 — Template→scenario coverage distribution unreported
- **Risk:** "13 templates" implies breadth. If 3 templates produced 40 of 60 scenarios,
  effective coverage is much narrower.
- **Fix:** histogram of scenarios per template. Publish it.
- **Verify:** sums to 60.
- **Effort:** 20m.

---

## TIER 1 — needs code or labeling

### L6 — `must_refuse` / `must_request_clarification` are lexicon heuristics
- **Risk:** highest-value fix on the list. Central thesis is "machine-checkable assertions,
  not a judge." A lexicon heuristic is a third, undisclosed category — neither verifiable
  nor labeled as a judge. Load-bearing for `MISSING_CLARIFICATION`, which is the `quitter`
  external-validity story.
- **Fix:** hand-label 40 traces on two axes (refuse / not-refuse, clarify / not-clarify).
  Report heuristic precision + recall against labels. Store labels in-repo as fixtures.
- **Verify:** labeled set committed; test recomputes P/R from fixtures and fails if the
  heuristic changes without the numbers being updated. Report P/R even if bad — do not
  tune the lexicon to the labels.
- **Effort:** 2h.

### L7 — Feasibility gate: 0/174 real rejections
- **Risk:** this is §6's signature bug, unflagged — *"how many rejected? zero → success."*
  A gate that never rejects is behaviorally identical to `return True`. Mutation testing
  (100%, n=40) proves sensitivity only, against self-authored mutations.
- **Fix, two parts:**
  1. Instrument: emit `gate_evaluated: true` per scenario. Confirm the count is **174**,
     not something smaller short-circuiting upstream.
  2. Hand-audit ~20 accepted scenarios for genuine feasibility.
- **Reframe if clean:** if all 174 were evaluated and are genuinely feasible, 0/174 is a
  *finding about the generator* (templates don't produce infeasible scenarios), not a
  limitation of the gate. Rewrite the bullet accordingly.
- **Verify:** test asserts `gate_evaluated` count == total scenarios; fails if any scenario
  reaches acceptance without an explicit evaluation record.
- **Effort:** 1h + audit.

### G5 — Scorecard may render "not applicable" as "measured clean"
- **Risk:** given L11, an agent evaluated mostly on refuse-only scenarios shows FABRICATION
  clean when it is *unmeasured*. Would be instance #7 of the signature bug, sitting in the
  headline artifact.
- **Fix:** confirm `PASS — WITH n CHECK(S) UNVERIFIED` machinery is wired into the
  **fingerprint table** specifically, not just the scorecard. Three-state render:
  `PASS` / `FAIL` / `NOT APPLICABLE (n scenarios)`.
- **Verify:** golden-file test on the fingerprint table for an agent with a
  zero-applicability category. Must not render as PASS.
- **Effort:** 1h.

### L9 — N=3 is vacuous offline
- **Risk:** deterministic policy + fixed seed → within-scenario variance is exactly zero.
  N=3 carries no information, and §3's "scenario is the statistical unit or SEs understate
  by √N" is currently a no-op correction. Will be asked in Q&A.
- **Fix, pick one:**
  - (a) Document: N=3 + scenario-level aggregation is the correct design for the online
    path; offline it contributes nothing and no claim is made on it. **Preferred.**
  - (b) Drop to N=1 offline, reclaim ⅔ of run budget.
- **Also verify:** `looper`'s zero-width CI is degenerate for the reason §7 states (60
  identical *scenario* scores) and not merely because offline runs are identical. Same
  symptom, different cause. Assert against the artifact.
- **Effort:** 30m (a) / 2h (b).

### L1 — Judge never executed against a live model
- **Note:** does not require an Anthropic key. §9's gateway serves Qwen. A judge-only run
  over ~30 traces is far below the 720-call burst §9 warns against — safe under your own rule.
- **Fix:** run judge on ~30 hand-labeled traces. Compute κ **against human labels**, not
  against your own rule detectors (that measures agreement, not correctness).
- **Verify:** if not run, `LLM-judged, unvalidated` tag must remain everywhere. Test asserts
  every published calibration number still carries `judge_used: false`, checked against run
  artifacts rather than asserted.
- **Effort:** 2h, gated on gateway access.

---

## TIER 2 — disclose only, no code

Correctly stated already. Do not "fix" — each fix is a feature by §11's test.

| ID | Item | Action |
|----|------|--------|
| L2 | 13 hand-authored templates | leave; see G6 for the cheap partial |
| L3 | Single domain (Internal Ops Console) | leave |
| L4 | Mocked tools ≠ tool-level realism | leave; §3 argues mocks *are* the boundary |
| L5 | Absolute scores incomparable across toolsets | leave; add "same toolset, same frozen set, same seeds" to the face of the fingerprint table so it doesn't read as undermining the headline |
| L8 | L3 network isolation offline-only | leave; fallback already documented |
| L10 | No true paraphrase axis; `VARIANT_SENSITIVE` renamed after audit | leave — **but** write down what `VARIANT_SENSITIVE` currently measures. Doc records the rename, never the new definition. A metric defined only in someone's head is a gap. |

---

## PREP ANSWERS — no code, needed before demo

### G1 — Are taxonomy categories mutually exclusive?
§6 presents `quitter` firing three signatures from one defect as a strength. Hostile
reading: three correlated categories triple-counting one failure. Need the answer to
*"is that three findings or one finding counted three times?"* If categories are meant to
be disjoint, this is a specificity bug in the headline artifact, not a win. Resolve before
the demo, not during it.

### §6 table numbering
Rows are numbered 5, 7, 8, 9, —, —. Six instances claimed. Someone will ask what 1–4 and 6
were. Either have the longer list ready or renumber 1–6.

### L14 — one limitation is missing
§8 states it condenses a **14-item** published list; 13 are recoverable from the text.
Recover the 14th from the published list. An undisclosed limitation is worse than a
disclosed one.

### Invalid rate is a gate, not a published number
§6 row 7 shows 12–28% invalid slipping past because `reportable=False` was never checked.
§9 reports 12.5% online against a 5% ceiling. The current **offline** invalid rate per agent
is nowhere in §8. Publish it as a number, not just as a gate that passed.

---

## Suggested order

1. Tier 0 in full (~3h, no runs, all findings)
2. L6 labeled set (~2h) — biggest credibility gain
3. L7 instrument + audit
4. G5 golden-file test
5. G1 + §6 numbering + L14 as demo prep
6. L1 only if gateway access is confirmed and time remains

Do not start FF1–FF6 (provider-agnostic backend) until the above lands. It adds surface
area; every item here produces a finding.
