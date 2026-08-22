# ARE — Final Checks

Input for Claude Code. Repo state at time of writing: 247 tests, selftest exit 0,
demo.sh exit 0, ACCEPTANCE PASS, fresh-clone verified. fix.md complete except L1's
live-model half. SPEC.md Phases 0–4 complete.

Four items. Nothing here adds surface area.

---

## C1 — Revert-check the Phase 1/2 tests  **(blocking, do first)**

**Why:** `247 tests · exit 0 · ACCEPTANCE: PASS` is a green reading reported as success —
the exact shape the harness has now caught eleven times. The standing rule this session
settled on (*revert the fix, watch the suite go red, or the test isn't evidence*) applies
to the harness's own final state. Untested, this is instance twelve waiting.

**Do:** for each test below, revert the fix, run the suite, confirm RED, restore.

| Test | Revert what | Must go red because |
|---|---|---|
| G3 co-fire matrix | null-cell assertion | a `null` cell must not read as "uncorrelated" |
| G4 discrimination | sum-to-60 assertion | partition that doesn't sum must fail |
| G2 clean FP rate | per-detector applicability denominator | denominator 60-by-default must fail |
| L13 distinct_modes | the field | composite scores must stay byte-identical; absence must fail |
| P1 CI exit codes | regression trigger **and** `reportable=False` trigger, **separately** | each must fail the build alone |
| P2 drifter | the planted drift | `mutations_subset_of` must fire, and fire *for the drift* — cross-check G3's co-fire matrix that it isn't firing incidentally via another detector |
| P3 A/A null | — | assert A/A produces **zero** flagged regressions; the null is the persuasive half |
| L7 gate_evaluated | the emit | count must equal total scenarios; any scenario accepted without an explicit evaluation record must fail |
| G5 not-applicable | three-state render | zero-applicability category must not render PASS |

**Output:** `reports/revert_verified.json` — per test: reverted, went red, restored.
**Report the revert-verified count on the slide, not 247.** A revert-checked subset is
evidence; a total is a reading.

---

## C2 — Reframe the finding: 4-of-11, not 9→11

**Why:** nine→eleven is an increment. *Four of the eleven were in tests written to prevent
that exact bug* is a different and stronger claim: **the bug class is self-camouflaging.**
A guard against "measuring the wrong thing" fails by measuring the wrong thing —
two re-implemented the target, one regenerated the files it checked then compared them to
themselves, one counted receipts without checking any said anything. The guard adopts the
failure mode of the thing it guards. That is *why* revert-checking is the only rule that
survives — now an empirical result, not an assertion.

**Do:** lead §6 and the deck with the ratio. Keep the count as supporting detail.

---

## C3 — Two open questions on §6 (answer before demo, not during)

1. **Table numbering.** Rows were 5, 7, 8, 9, —, — at six instances. At eleven, confirm it
   was fixed and not made worse. Someone will ask what the gaps were.
2. **Is the `report.html` dry-run catch a twelfth?** Same signature — assumed artifact
   presence read as success — but in the demo script, not the harness. (Step 3 pointed at
   `runs/calib-pushover/report.html`, which `calibrate` doesn't produce; `calibrate` writes
   verdicts, `report` renders them.) Either bucket is defensible. Being asked without
   having decided is not. Pick one and write the rationale into §6.

---

## C4 — Judge live run: branch, pre-committed outcome

**Why:** SPEC's demotion to optional still holds — the brief doesn't ask for an LLM judge.
Run it anyway: if the three JUDGE-ATK probes fail against a live model, that's a **finding**,
and finding > feature by the project's own rule. Three probes is far below §9's burst
threshold. Turns §7.2 from UNVERIFIED into a result either way. ~5 min.

**Do:**
1. Branch. Do not run on the demo tag.
2. **Write the reporting commitment into the branch commit message before running.**
   Both outcomes get reported. Decide this before seeing the result.
3. Export router key, `selftest` fires the three JUDGE-ATK probes.
4. Record outcome in §7.2 as a result, not as a status.

**Guard:** a red result surfacing shortly before a demo is exactly when quiet re-scoping
tempts. That temptation is what the eleven instances are made of. If it fails, it ships
as a finding.

**If credentials never arrive:** L1 stays optional and correctly disclosed. Assert every
published number carries `judge_used: false` checked **against run artifacts**, not asserted.

---

## Order

C1 (blocking) → C4 (5 min, unblocks the last item) → C2 → C3 → rehearsal.

Reserve the final block for rehearsal. A short demo is won on narrative and three hard
numbers — best candidates: 4-of-11, the revert-verified count from C1, and the `clean`
false-positive rate.
