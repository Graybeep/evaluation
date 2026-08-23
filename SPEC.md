# ARE — Build & Remediation Spec (brief-aligned)

Input for Claude Code. Supersedes `ARE_REMEDIATION_SPEC.md`. Derived from
`PROJECT_CONTEXT.md` §5–§11, re-prioritised against the hackathon brief.

**Every status claim in `PROJECT_CONTEXT.md` is self-reported and unverified.** Phase 0
exists to establish which of it is true. Do not build on §5's claims until Phase 0 passes.

## Ground rules

- `frozen/frozen_scenarios.json` does NOT change. No item here requires a re-freeze. If
  one seems to, stop and report instead.
- Tags immutable. Verify at tag, not HEAD.
- Never tune detectors to restore an expected ranking. A collapsed ranking is a finding.
- Every fix ships a regression test that **fails on revert**. No failing test = not landed.
- Finding > feature. If an item grows surface area, cut it.
- Apply §6's rule to every fix: assert the positive condition, enumerate states, route
  "not measured" to an explicit non-success state that never renders as clean.

## Brief coverage (state this on slide 1 — it is true and it is checkable)

| Brief direction | Built | Weakness to disclose |
|---|---|---|
| Scenario Generation Engine | 13 templates → LLM expansion → feasibility gate | conditions on tools + domain, not agent prompt (P5) |
| Sandboxed Execution & Replay | 4-layer sandbox, record/replay cache | L3 offline-only |
| Failure Mode Classifier | 8 rule detectors + 2 opt-in judge, PASS/FAIL/INVALID | judge unvalidated, off by default |
| Destructive Action Guardrail Tester | P0–P5 pressure taxonomy, irreversible tagging | — |
| Reliability Scorecard & Regression Tracker | worst-finding composite, bootstrap CIs, McNemar+BH | weakest coverage — see P3 |

| Brief failure mode | Detector | Positive control |
|---|---|---|
| tool-call loops | loop detector | `looper` |
| hallucinated confidence | fabrication detector | `confabulator` |
| unsafe destructive actions | irreversible-tier + P0–P5 | `pushover` |
| silent goal drift | `mutations_subset_of` | **NONE — see P2** |

---

# PHASE 0 — verify before building (do first, blocking)

### V1 — GG1–GG6 cross-check
Fresh clone **at the tag**, not HEAD. `pytest -q`, `python -m are.cli selftest --strict`,
`bash demo.sh`. Confirm every §5 claim has a corresponding test that fails on revert.
Confirm the calibration fingerprint table reproduces.
**Blocking:** §12 leads with that table and §11 records a tag already found stale. If it
doesn't reproduce, nothing below matters. Report divergences; do not silently fix them.

### V2 — Regression result still exists
§11 records a refreeze that silently invalidated a previously-reported regression result.
Confirm the current tag still has a valid one. If not, P3 becomes mandatory, not optional.

---

# PHASE 1 — Tier 0: free findings, existing artifacts, no new runs (~3h)

### G3 — Detector correlation known but never reported
- **Risk:** §3 chose worst-finding scoring *because* detectors correlate; structure never
  published. Two detectors co-firing ~always are one detector — "8 detectors" overstates coverage.
- **Fix:** pairwise co-fire matrix over existing run artifacts → `reports/detector_cofire.json` + table.
- **Verify:** 8×8, diagonal = raw fire counts, flag Jaccard > 0.9. Test asserts no `null`
  cells (a null must not read as "uncorrelated").
- **30m.**

### G4 — No discrimination check on the frozen suite
- **Risk:** a scenario every agent passes carries zero information. Effective suite size
  may be well under 60.
- **Fix:** per scenario, count agent pairs separated → `reports/suite_discrimination.json`.
- **Verify:** counts sum to exactly 60. Do not accept a partition that doesn't sum
  (§6 `quitter`/MISSING_CLARIFICATION precedent).
- **45m.**

### G2 — No published false-positive rate on `clean`
- **Risk:** the single most important number the platform has. A suite that flags the clean
  agent is worthless. Absent from §8 entirely.
- **Fix:** per-detector FP rate on `clean`, Wilson **upper** bound (upper — bounding a bad thing).
- **Verify:** denominator per detector = scenarios where that detector was *applicable*,
  not 60 by default. Emit applicability count alongside.
- **45m.**

### L13 — Worst-finding scoring hides within-band mode variation
- **Fix:** emit `distinct_modes` next to severity band. `looper: HIGH, distinct_modes: 9`.
- **Verify:** composite scores byte-identical pre/post. Additive field only, no re-freeze.
- **30m.**

### L11+L12 — Fabrication coverage as one published number
- **Fix:** rule-based fabrication detection is validated on **17/60 = 28% of the suite**;
  the other 43 are refuse/ask-only where the rule is structurally blind and only the
  unvalidated judge applies. One figure, not two scattered bullets.
- **Verify:** 17/17 Wilson LB = 0.816 — confirmed correct, quote **0.82**, never the point
  estimate. Assert 17 + 43 = 60.
- **15m, docs only.**

### G6 — Template→scenario coverage distribution unreported
- **Risk:** "13 templates" implies breadth. If 3 templates produced 40 of 60, coverage is narrower.
- **Fix:** histogram of scenarios per template, published.
- **Verify:** sums to 60.
- **20m.**

---

# PHASE 2 — brief-driven additions (ranked)

### P1 — Make the CI metaphor literal  *(highest value / cost ratio)*
- **Why:** the brief's headline is "continuous integration for autonomous agents." You have
  `demo.sh` and a CLI. Instantiate the framing rather than gesturing at it.
- **Fix:** (a) nonzero exit code on regression **or** on `reportable=False`; (b) machine-readable
  report artifact; (c) ~15-line GitHub Actions snippet in README showing a build failing on
  an agent regression.
- **Verify:** exit code 0 vs nonzero asserted in tests for both trigger conditions
  separately. `reportable=False` must fail the build on its own — that is §6 row 7 exactly.
- **30m.**

### P2 — `drifter` calibration agent  *(closes a real brief gap)*
- **Why:** the brief names silent goal drift. `mutations_subset_of` is your detector for it
  and **has never fired against a known positive**. [CLOSED — T1, 2026-08-23: synthetic
  positive controls in `tests/fixtures/`, revert-verified; the count lives in
  `reports/revert_verified.json`, not here.] Same shape as §6: the check reports no
  violations, but nothing was ever in a position to violate it (cf. the judge positive
  control and the `call_args_match` row). Six instances documented; this would be the seventh.
- **Fix:** scripted agent that writes outside `mutations_subset_of` while completing the
  nominal task. Run against the frozen set.
- **Verify:** detector fires; confirm it fires *for the drift*, not incidentally via another
  detector — check the co-fire matrix from G3.
- **Note:** this is a **targeted** positive control, not a replication of `quitter`'s
  external-validity result. Do not conflate them in the writeup.
- **1–2h.**

### P3 — One demonstrated version regression + one A/A null
- **Why:** direction 5 is the weakest coverage. McNemar+BH machinery exists; the artifact
  may not (see V2).
- **Fix:** `looper-v1` vs `looper-v2` with a known partial fix → detected regression. Plus
  an A/A comparison (same agent, same seeds) → no alarm.
- **Verify:** the A/A null is the more persuasive half. Assert BH correction is applied
  across categories; assert A/A produces zero flagged regressions.
- **1–2h.**

### P4 — L6: `must_refuse` / `must_request_clarification` are lexicon heuristics
- **Why:** central thesis is "machine-checkable assertions, not a judge." A lexicon heuristic
  is a third, undisclosed category — neither verifiable nor labeled as a judge. Load-bearing
  for `MISSING_CLARIFICATION`, which is the `quitter` story.
- **Fix:** hand-label 40 traces on two axes; report precision + recall; commit labels as fixtures.
- **Verify:** test recomputes P/R from fixtures, fails if the heuristic changes without the
  numbers updating. **Report P/R even if bad. Do not tune the lexicon to the labels.**
- **2h.**

### P5 — Prompt conditioning in the generator  *(only literal gap vs brief text)*
- **Why:** brief says generator reads "tools, prompt and task domain." Yours reads tools + domain.
- **Fix:** thread the agent's system prompt into the existing LLM expansion context.
- **HARD CONSTRAINT:** **do not regenerate the frozen set.** Demonstrate on a separate
  non-frozen sample. Report as "capability shown; frozen set intentionally not regenerated
  per §11." Regenerating triggers the full re-verification cycle that burned you before.
- **Fallback:** if short on time, the existing disclosed-scope-cut framing is defensible.
- **1–2h.**

### L7 — Feasibility gate: 0/174 real rejections
- **Risk:** §6's signature bug, unflagged. *"How many rejected? Zero → success."* A gate that
  never rejects is behaviorally identical to `return True`. Mutation testing (100%, n=40)
  proves sensitivity only, against self-authored mutations.
- **Fix:** (1) emit `gate_evaluated: true` per scenario; confirm count is **174**, not
  something smaller short-circuiting upstream. (2) Hand-audit ~20 accepted scenarios.
- **Reframe if clean:** if all 174 were evaluated and are genuinely feasible, 0/174 is a
  *finding about the generator*, not a limitation of the gate. Rewrite the bullet.
- **Verify:** test asserts `gate_evaluated` count == total scenarios; fails if any scenario
  reaches acceptance without an explicit evaluation record.
- **1h + audit.**

### G5 — Scorecard may render "not applicable" as "measured clean"
- **Risk:** given L11, an agent evaluated mostly on refuse-only scenarios shows FABRICATION
  clean when it is *unmeasured*. Would be instance #7, in the headline artifact.
- **Fix:** confirm `PASS — WITH n CHECK(S) UNVERIFIED` is wired into the **fingerprint table**
  specifically. Three-state render: `PASS` / `FAIL` / `NOT APPLICABLE (n scenarios)`.
- **Verify:** golden-file test for an agent with a zero-applicability category. Must not render PASS.
- **1h.**

---

# PHASE 3 — disclose only, no code

Correctly stated already. Each "fix" is a feature by §11's test. Leave them.

| ID | Item | Action |
|----|------|--------|
| L2 | 13 hand-authored templates | leave; G6 is the cheap partial |
| L3 | Single domain (Internal Ops Console) | leave |
| L4 | Mocked tools ≠ tool-level realism | leave; §3 argues mocks *are* the boundary |
| L5 | Absolute scores incomparable across toolsets | leave; put "same toolset, same frozen set, same seeds" on the face of the fingerprint table |
| L8 | L3 network isolation offline-only | leave; fallback documented |
| L9 | Flakiness structurally unmeasurable offline | **document**: N=3 + scenario-level aggregation is correct design for the online path; offline within-scenario variance is exactly zero, so §3's √N correction is a no-op and no claim rests on it. Will be asked. Also confirm `looper`'s zero-width CI is degenerate for §7's stated reason (60 identical *scenario* scores), not merely because offline runs are identical — same symptom, different cause |
| L10 | No true paraphrase axis; `VARIANT_SENSITIVE` renamed | leave — **but write down what it currently measures**. Doc records the rename, never the new definition |
| L1 | Judge never run live | **demoted to optional.** Brief never asks for an LLM judge; yours is opt-in, off by default, ~2 of 8+ modes. κ buys nothing against the brief. Keep `unvalidated` tags. Test asserts every published number carries `judge_used: false` **checked against run artifacts**, not asserted |
| — | MCP adapter | keep, don't invest. Outside the brief, costs a kill switch (2/3). Bonus slide with caveat, not the lead |
| — | FF1–FF6 provider-agnostic backend | **CUT.** Not in the brief. ~1 day of a 3–4 day window. Feature, not finding. §9's accidental Qwen run already delivers the cross-model result without the build |

---

# PHASE 4 — demo prep, no code

### G1 — Are taxonomy categories mutually exclusive?
§6 presents `quitter` firing three signatures from one defect as a strength. Hostile reading:
three correlated categories triple-counting one failure. Have the answer to *"is that three
findings or one finding counted three times?"* If categories are meant to be disjoint, this is
a specificity bug in the headline artifact, not a win. Resolve before the demo, not during it.
G3's co-fire matrix is direct evidence either way.

### §6 table numbering
Rows numbered 5, 7, 8, 9, —, —. Six instances claimed. Someone will ask what 1–4 and 6 were.
Have the longer list ready or renumber 1–6.

### L14 — one limitation is missing
§8 says it condenses a **14-item** published list; 13 are recoverable. Recover the 14th.
An undisclosed limitation is worse than a disclosed one.

### Invalid rate is a gate, not a published number
§6 row 7: 12–28% invalid slipped past because `reportable=False` was never checked. §9 reports
12.5% online against a 5% ceiling. Current **offline** invalid rate per agent is nowhere in §8.
Publish it as a number, not as a gate that passed.

### "At scale" framing
60 scenarios from 13 templates reads thin against the brief's "at scale." Don't build more —
report throughput (scenarios/min, cost each) and frame 60 as a *frozen evaluation set* sized
for statistical discipline, not a ceiling.

### The 70% anchor
The brief's cited ~70% real-world failure rate is a free opening. The calibration fingerprint
table is a direct answer to "how would you know *which* 70%."

---

# Execution order

1. **V1, V2** — Phase 0 audit (blocking)
2. **Phase 1** — Tier 0, ~3h, all findings, no runs
3. **P1** — CI exit codes, 30m
4. **P2** — `drifter`, closes the goal-drift control gap
5. **P3** — regression A/B + A/A null
6. **P4** — lexicon labeled set
7. **L7, G5** — if time
8. **P5** — prompt conditioning, if time
9. **Phase 4 + rehearsal** — reserve the final block. A short demo is won on narrative and
   three hard numbers, not on item count.

## Structural note

Nearly every validation in this project is self-authored: self-written mutations, self-built
calibration agents, self-designed taxonomy, self-reported status. `quitter` and the accidental
Qwen run are the only two things outside that loop — and they are the two strongest assets.
That is not a coincidence. Prefer external checks over internal ones wherever time is contested.
