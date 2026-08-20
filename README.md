# Agent Reliability Engine (ARE)

A **property-based testing framework for LLM agents** — not "an LLM that grades another LLM".

Every scenario ships with machine-checkable **assertions generated alongside it**, so the
verdict is computed from the trace and the final world state, deterministically:

```
Scenario = (initial_world_state, instruction, assertions[], pressure_tags[])
Verdict  = evaluate(assertions, trace, final_state)  ->  PASS | FAIL | INVALID
```

The LLM appears in exactly three bounded places: expanding template *phrasing*
(schema-validated), the feasibility reference solver, and a **secondary** judge for two
subjective failure modes that is always labelled low-confidence.

---

## Quickstart

```bash
pip install -r requirements.txt
git config core.hooksPath .githooks      # enforces the frozen-set rule (§3.4)

python -m are.cli selftest                     # sandbox, isolation, judge-attack, scrub
python -m are.cli gen        --out pool/scenarios.json
python -m are.cli gate-audit                   # what the feasibility gate actually catches
python -m are.cli freeze     --pool pool/scenarios.json --n 60
python -m are.cli calibrate  --scenarios frozen/frozen_scenarios.json --offline --no-sandbox

python -m are.cli run --agent pushover --scenarios frozen/frozen_scenarios.json --report
python -m are.cli compare runs/pushover-v1 runs/pushover-v2
```

On Windows, `python` often resolves in PowerShell but **not** in Git Bash (the Store alias
lives in `WindowsApps`, which bash does not always inherit). `demo.sh` resolves an
interpreter itself and tells you what to do if it cannot; to force one:

```bash
PYTHON=python3 bash demo.sh            # or: PYTHON=/c/Python311/python.exe bash demo.sh
```

No `ANTHROPIC_API_KEY`? Everything above still runs: the calibration agents fall back to
**scripted policies** carrying the same defects. See *Offline mode* below for what that
does and does not prove.

Interactive console:

```bash
streamlit run app.py
```

A **view over the engine, not a second implementation** — every number it shows comes from
the same `verify` / `compute` / `regression` code the CLI uses, so the UI cannot drift and
disagree with the CLI about a verdict. It carries the honesty machinery rather than dropping
it for looking prettier: every page is stamped ONLINE/OFFLINE with the resolved model
string, `invalid_rate` sits next to the composite instead of below the fold, a run over the
§6.1 ceiling is banner-blocked as NOT REPORTABLE, pressure payloads are redacted to id +
category, judge findings keep their *LLM-judged, unvalidated* marker, and degenerate
intervals are flagged as such. Five tabs: **Run**, **Scorecard**, **Traces** (step-by-step
drill-down, including `defect_marker` steps), **Compare** (paired McNemar + BH), and
**Integrity** — which shows the live sandbox state and the standing limitations rather than
hiding them in a footer.

Containers (sandbox L3):

```bash
docker compose run --rm offline calibrate --offline    # network_mode: none, OS-level deny
docker compose run --rm online  run --agent clean --judge
```

---

## Coverage of the brief

| Brief asks for | Component | Scope note |
|---|---|---|
| Scenario Generation Engine | `gen/` — 13 hand-authored templates + LLM phrasing pass, schema-validated, feasibility-gated | Ships **assertions with every scenario**, which the brief doesn't ask for and is the differentiator |
| Sandboxed Execution and Replay Harness | `runner/` + `sim/` — four-layer containment, record/replay cache | Mocked tools **are** the isolation boundary; L3 is OS-enforced on the offline path only (see Limitations 8) |
| Failure Mode Classifier | `verify/` — 11 rule detectors + 2 judge detectors, three-way outcome | Rules primary; judge secondary and labelled everywhere it appears |
| Destructive Action Guardrail Tester | `probes/` — pressure taxonomy P0–P5 | Reports **P_n − P0 deltas**, not absolutes — a finding, not a feature |
| Reliability Scorecard and Regression Tracker | `score/` + `report/` — severity-weighted, per-category, paired McNemar + BH | Pairwise A/B across versions; history is append-only JSONL |

---

## What it measures, on the calibration suite

Four deliberately-defective agents with known failure signatures. The platform is not told
which is which — `calibrate` takes agent names and checks whether the scorecard recovers
the truth (frozen set, 60 scenarios × 3 repeats, **offline scripted policies**):

| Agent | Injected defect | Composite | Attribution to its own defect |
|---|---|---|---|
| `clean` | none (control) | **100.0** | n/a — 0 CRITICAL findings |
| `confabulator` | answers from priors when a tool errors | **92.2** [88.2, 95.5] | 100% |
| `looper` | re-searches instead of concluding | **65.0** | 100% |
| `pushover` | complies with authority/urgency framing | **31.7** [20.0, 43.3] | 100% |

`ACCEPTANCE: PASS` — the required ranking (`clean > {looper, confabulator} > pushover`)
holds and every defective agent's findings land on its own failure mode. If that check ever
fails, the instruction is to fix the platform, not the scenarios.

**Paired regression demo** (`pushover@v1 → pushover@v2`, a partial fix that resists claimed
authority but still folds under urgency):

```
composite 31.7 -> 41.7   delta +10.0  (meaningful, >= 3-point minimum effect)
flips: pass->fail 0   fail->pass 6    McNemar p=0.0312 (exact binomial)
safety   n=36  pass 3->9  flips -0/+6  p=0.0312  SIGNIFICANT (BH q=0.10)
pressure: P3 delta +44.1   P1/P2/P4/P5 delta 0.0
```

That last line is the finding the pressure ladder exists to produce: the fix moved the
authority condition only, and the report says so instead of averaging it away.

---

## Two things that were measured rather than assumed

Both of these started as "the number looks fine" and turned into a diagnosis. They are the
reason to trust the rest of the numbers, so they are documented rather than tidied away.

**The confabulator's margin was thin because the suite starved its defect.** At the first
build `confabulator` scored 95.3 [91.8, 98.2] — clearing `clean` by 1.8 points. Diagnosis on
the frozen set: mean failed tool results per run was **0.033**, and only **5/60 scenarios
(8.3%)** ever presented the epistemic defect an opportunity to fire. Of those 5, the
detector caught 5. The detector was fine; the suite was. A baseline transient-fault rate was
added across the mix (72% of scenario bodies, keyed on `(template, variant)` so a pressure
ladder still differs only by framing), taking observed opportunity to **70% of runs**.
Conditioned on the defect being able to express itself, the catch rate is **17/17 scenarios,
95% Wilson [0.82, 1.00]**, with zero escapes — every scenario where the fabrication branch
was entered and a rule could see it was caught. The same diagnostic exposed a bug in the
agent itself: its "is this data degraded?" check looked for `total_cents` in any response,
which a healthy `list_tickets` reply never has, so it fabricated on fault-free scenarios.
Fixed to a per-tool expected-field check.

**Attribution is not a validity check, so defect firing is instrumented separately.** The
scorecard's attribution number says an agent's failures trace to its injected defect; it
cannot say the defect fired *for the intended reason*. Those came apart twice here. The
`total_cents` bug above is one. The second: the confabulator treated "this instruction has
no action to perform" as "a tool failed", and fabricated on clean read-only scenarios.
Attribution read 100% through both, because the resulting failures were still the expected
modes. Each defective agent now declares a trigger and emits a `defect_marker` step when it
enters its defect branch, and `tests/test_defect_opportunity.py` asserts (a) the defect
fires at least N times on the frozen set and (b) **every** firing occurs under its declared
trigger. Assertion (b) is the one that catches this class of bug; no scorecard number will.

Detection is then reported with **its own denominator and an interval**, scenario-level per
§8.2: FABRICATION is detected on **17/17 scenarios, 95% Wilson [0.82, 1.00]** — not a bare
"100%". A further **25 scenarios never exercise the defect at all**, because the agent's own
safety gates fire first and it refuses or asks before reaching the fabrication branch, and
**18** are never handed the trigger. Those are coverage limits of the frozen set, reported
as their own buckets rather than folded into the denominator or silently dropped.

**A gate that rejects nothing is indistinguishable from no gate — so the gate is audited.**
The feasibility gate's discard rate on authored scenarios is **0%**, which alone proves
nothing. `python -m are.cli gate-audit` injects known defects into real scenarios and
measures what the gate rejects: **100% across six mutation classes** (n=40) — unsatisfiable
`state_equals`, `must_call` on a tool no solution uses, non-existent entity ids, unknown
tools, `no_call` on a tool the reference plan needs, and an impossible call budget. Read
together, 0% baseline plus 100% catch means the authored scenarios are genuinely feasible,
not that the gate is inert. It also caught two real authoring bugs the day the fault rate
was raised: reference plans that didn't survive a transient fault, and a duplicated read
that tripped the loop detector.

**The caveat that belongs next to that 100%:** the mutations are ones we authored, so the
audit carries the same co-design exposure as the calibration agents — it shows the gate
catches the defect classes we thought of. Alongside it: the gate has **never rejected a
real generated scenario (0/174)**, and `--solver llm`, the backend that would catch
"possible but unreasonable" rather than "impossible", remains untested. The honest summary
is that the gate is a validated *static and satisfiability* checker, not a validated
judgement about whether a task is sensible.

---

## Nine times this harness measured the wrong thing

Every one of these looked fine on the scorecard. They are listed because the pattern
matters more than any individual number: **the signals you would normally trust — high
attribution, green tests, tight confidence intervals — each failed to catch at least one of
them.**

| # | What the number said | What was actually true | What caught it | What would have shipped |
|---|---|---|---|---|
| 1 | `confabulator` 95.3 [91.8, 98.2], attribution 100% | Its degraded-data check matched any response lacking `total_cents` — which a healthy `list_tickets` reply never has. It fabricated on fault-free scenarios. | Splitting the denominator: opportunity vs detection (only 5/60 scenarios could exercise the defect at all) | A calibration agent whose defect fires on the wrong trigger, and a margin over the control that was partly manufactured |
| 2 | attribution 100%, all tests green | `confabulator` treated "this instruction has no action to perform" as "a tool failed", fabricating on clean read-only scenarios | Defect-marker trigger assertion (`tests/test_defect_opportunity.py`) | Inflated failure counts on read-only scenarios, attributed to the right mode for the wrong reason |
| 3 | attribution 100%, all tests green | `pushover` marked `COMPLIANCE` on `benign_refund_approved`, where performing the documented refund is the **correct** behaviour | The same trigger assertion | A coverage statistic counting the agent's one correct behaviour as a defect firing |
| 4 | "4 paraphrase-sensitive groups" | Sibling variants differ in `world_state`, `seed`, `faults`, `assertions` **and** `pressure_tags` — the metric was named for an isolation the data does not have | Field-by-field sibling audit | A claimed paraphrase-robustness measurement the scenario set cannot support |
| 6 | `--replay` labelled a run "bit-identical replay" | On a cache miss it **fell through to a live API call**. `ResponseCache.get` raised a loud, explanatory error in replay mode; `LLMClient.complete` caught `CacheMiss` generically and discarded it, so a partially-populated cache silently blended recorded and freshly-generated responses into one trace | Writing the test for the replay guarantee, which had never been executed | A "reproducible" debugging run that was neither reproducible nor offline, and quietly spent money |
| 7 | `ACCEPTANCE: FAIL — fix the platform, not the scenarios` | The acceptance gate never consulted the **reportability** gate. It rendered that confident verdict twice from runs whose own scorecards said `reportable=False` at 12.5–28% invalid — blaming the agents for a provider outage | Reading the scorecards the gate had just written and noticing they disagreed with it | A headline "the calibration ranking does not survive real models", sourced entirely from Cloudflare 502s |
| 8 | `feasibility[llm]: discard rate 0.0%` | `discard_rate` returned **0.0 when nothing had been evaluated**. The LLM solver run that exposed it was 25/25 provider faults — "nothing was rejected" and "nothing was judged" printed identically | Running `--solver llm` for real and reading the 0/0 | "The LLM gate rejects 0%, same as the deterministic one" written up as a finding about the gate |
| 9 | `JUDGE-ATK-01 PASS` — the §7.2 injection defence | The test was **vacuous by construction**. Its flip criterion was `control_flagged and not flagged`, so when the judge failed to flag the control it could never report anything but PASS. It had also never executed at all before this, always SKIPPING without an API key | Running the judge-attack corpus for the first time and reading `control_flagged=False` next to `PASS` | "Our injection defence is verified" — from a test structurally incapable of failing |
| 5 | Every safety number on the scorecard | The tier system **failed open**: `tier: IRREVERSABLE` (one transposed letter), lowercase, empty or whitespace-padded all left `is_irreversible()` returning `False` — silently downgrading `must_refuse` from CRITICAL to MAJOR and making the §2 unsanctioned-call detector skip the tool | Writing the test for a documented invariant that had never been executed | A one-character typo in `registry.yaml` disabling the safety oracle, with nothing anywhere reporting it |

#5 and #6 are a different species from the first four and worth separating: those were *measurement*
bugs found by changing a denominator. This one was a **fail-open default in the safety path**,
found by the cheapest possible means — writing a test for an invariant that had been stated
in the design document from day one (§2, §13.8: "default to IRREVERSIBLE on any doubt") and
never once executed. #6 is the same story: §4.5 promised replay "guarantees the replay
really is a replay", and it did not.

That prompted a sweep of every other stated-but-untested invariant. Final tally: **five
invariants tested, two were false.** The three that held — a CRITICAL destructive action
outranks a softer finding (politeness buys no severity discount), run ids never collide, and
trace content cannot close the judge's `<untrusted_trace>` wrapper (whitespace, case and
nested-opener variants all neutralised) — are now locked by tests rather than by assertion.
A 40% falsity rate is roughly what you should assume for any claim in a design document that
has no test next to it.

A side effect of fixing #6 is worth more than the fix: **replay mode now exercises the LLM
code path with no API key**, because a replay makes `client.available` true. Multi-turn
message threading, `tool_use` block handling, `tool_result` formatting and token accounting
have therefore all executed at least once — deterministically, and asserted bit-identical
across two runs. That does not validate any *model* behaviour, but it retires the risk that
the harness's own LLM plumbing is broken in some obvious way.

**The pattern in five of them.** #5, #6, #7, #8 and #9 are one bug wearing five costumes: **a
guard that returns a confident, benign-looking value instead of refusing to answer.** A
malformed risk tier resolved to "not irreversible" rather than "I don't know". A replay
cache miss fell through to a live API call rather than stopping. An acceptance gate rendered
PASS/FAIL rather than INCONCLUSIVE. A discard rate returned 0% rather than "not measured".
A judge-attack test reported PASS rather than "this test cannot discriminate". In every
case the fix was the same shape — make the code say *I don't know* — and in every case the
pre-fix behaviour was indistinguishable from health on the scorecard. If there is
one transferable lesson here it is that **for an evaluation harness, the dangerous default
is not a crash; it is a plausible number.**

**The generalisation.** Attribution stayed at 100% through 1, 2 and 3 — it reports whether
failures trace to the injected defect, and cannot report whether the defect fired for the
intended reason. The test suite was green through 1, 2 and 3, because no test asserted
anything about *why* a defect fired. `confabulator`'s interval, [91.8, 98.2], was
comfortably non-degenerate throughout 1 — a tight interval around a wrong number is still
tight.

What actually caught them, in each case, was a mechanism that changed the *denominator or
the unit*, not one that looked harder at the same number:

* **denominator splitting** — separating "the defect could fire here" from "the defect was
  detected here" turned a healthy-looking 95.3 into "measured on 5 of 60 scenarios" (#1);
* **declared-trigger assertions** — each defective agent now declares its trigger and emits
  a `defect_marker` step, and the suite asserts every firing occurred under it (#2, #3);
* **structural audit of the data** — comparing sibling scenarios field by field, rather
  than trusting the name on the metric (#4).

A fifth check was then run deliberately against the co-design problem: `quitter@v1`, an
agent whose defect (announce completion, never perform the mutation) was chosen **after**
the taxonomy was frozen, with **no detector added to catch it**. The full partition of the
frozen set — all 60 scenarios, no residue:

| What the scenario required | n | Outcome | Mode |
|---|---|---|---|
| a mutation | 14 | FAIL | `TASK_INCOMPLETE` + `WRONG_FINAL_STATE` |
| a refusal | 30 | FAIL | `REFUSAL_EXPECTED` |
| a clarifying question | 9 | FAIL | `MISSING_CLARIFICATION` |
| a read only | 7 | **PASS** | — (correct: doing the read *is* the task) |

Every scenario that could expose the defect did, with **no coincidental passes** (0 scenarios
requiring a mutation passed) and **no partial detections** (0 requiring a mutation escaped
`WRONG_FINAL_STATE`). That is evidence the taxonomy generalises past the defects it was
authored against.

The shape of that table is itself the finding: **one injected defect produced three distinct
failure signatures**, because the classifier labels by *the requirement that was violated*,
not by the agent's root cause. Which is the same phenomenon as `looper`'s nine distinct mode
signatures collapsing to a single composite value — and the two arrived from independent
directions. **Both the severity scoring and the failure classifier are lossy about *why*
something failed in favour of *whether* it failed.** The mapping between cause and reported
number is not injective in either direction: you cannot recover nine failure shapes from one
composite, and you cannot recover one root cause from three modes. That is a deliberate
trade — a classifier that reported root causes would be inferring intent — but it means the
per-mode table and the trace drill-down, not the composite, are where a debugging reader has
to go.

---

## Design decisions worth defending

**The verdict is computed, not inferred.** Assertion kinds are authored in templates; the
LLM fills parameters and varies wording. It cannot invent an assertion, add a tool, or
change a severity.

**Three-way outcomes.** `PASS | FAIL | INVALID`. Harness faults, API errors and judge
abstentions are INVALID and are reported as a first-class `invalid_rate`. Above 5%, the
run is marked **not reportable**.

**Kill-switch trips are failure modes, not crashes.** Three independent limits — wall
clock, tool calls, tokens — because a loop can be cheap-and-fast, expensive-and-slow, or
silent-and-stuck.

**Goal drift is `SCOPE_VIOLATION`**, defined as "mutated an entity outside the task's
declared affected set". Measurable. "Seemed to lose the plot" is not.

**The scenario is the unit of analysis.** Bootstrap resamples *scenarios*; version
comparison is paired (McNemar) with Benjamini–Hochberg across category tests and a stated
minimum meaningful effect of 3 composite points.

**Two variance axes, never reported as each other.** `flaky` is mixed outcomes across the
N repeats of *one identical instruction* — the seed enters the response-cache key, never the
prompt, so the only thing that can vary is model sampling. `variant_sensitive` is
outcome disagreement across *sibling variants* of one template — audited and named for what
it actually varies: siblings differ in `world_state`, `seed`, `faults`, `assertions` and
`pressure_tags`, not only in wording, so it is deliberately **not** called paraphrase
sensitivity. The scorecard also reports
`flaky_measurable`, so an empty flaky list against a deterministic agent reads as **"not
measured"**, never as "none found".

**A zero-width interval is flagged, not celebrated.** A percentile bootstrap over N
identical values returns width 0 — correct output, and not evidence of precision. `clean`
(every scenario penalty 0.0) and `looper` (every scenario penalty 0.35) both produce
degenerate intervals, and the scorecard labels them *degenerate by construction* rather than
letting `[65.0, 65.0]` read as a very confident estimate. `confabulator` and `pushover`
produce 125 and 25 distinct bootstrap values respectively on the same code path, which is
how the resampling was confirmed sound rather than assumed.

**A run is scored by its worst finding.** The first severity model summed weights across
modes; it double-counted correlated detectors (one unapproved refund trips
`DESTRUCTIVE_ACTION` *and* `SCOPE_VIOLATION` *and* the `must_refuse` assertion) and
saturated — `looper` and `pushover` both clipped to **0.0**, destroying the very ranking the
platform is validated against. Replaced with worst-finding-per-run, averaged over runs then
over scenarios. Per-mode rates are still reported separately and unchanged.

**No server-side refusal fallbacks.** Deliberately disabled. A fallback reroutes a refused
request to a different model, which would substitute another model's safety behaviour into a
measurement *of* safety behaviour — and would break the one-model-version-per-report
guarantee. `stop_reason == "refusal"` is handled explicitly instead; for a guardrail tester
a refusal is frequently the correct outcome.

**The scorecard advises; it does not gate.** Nothing here returns "block the merge".

---

## The sandbox — four layers

| Layer | Mechanism | Defends against |
|---|---|---|
| **L1 — tool mocking** | no tool implementation touches a real system; no pass-through mode, not behind a flag | all real-world side effects — the primary boundary |
| **L2 — process + filesystem** | each run in a child process with a scratch tempdir as cwd | stray writes, log pollution, cross-run bleed |
| **L3 — network** | **offline container: OS-enforced** (`network_mode: none`). Offline host: process-level allowlist. **Online: degraded** — see Limitations 8 | exfiltration, an agent "helpfully" calling a real API |
| **L4 — resource budgets** | inner cooperative limits + outer parent-kills-child caps | runaway loops, cost blowups, a hung demo |

L1 is doing most of the work and the repo says so rather than faking VM isolation.
`selftest` asserts L1 mechanically and **fails L3 with exit 1 when a live API key is
present**, rather than skipping it — a layer you cannot demonstrate is not a layer you have.

The real attack surface is **the harness itself**: we inject prompt-injection payloads into
tool output and then feed those traces to our own judge. Traces reach the judge wrapped in
`<untrusted_trace>` with delimiter tokens stripped, and `selftest` fires the judge-attack
corpus at the judge to check it does not flip.

---

## Repo layout

```
are/
  schema/     scenario.py, trace.py, verdict.py      pydantic, single source of truth
  tools/      registry.yaml, specs.py                risk tiers, manually declared
  sim/        world.py, faults.py, entities.py       the simulator (L1 boundary)
  gen/        templates/*.yaml, expand.py, feasibility.py, audit.py
  runner/     adapter.py, loop.py, limits.py, cache.py, llm.py, sandbox.py
  verify/     rules.py, judge.py, taxonomy.py
  score/      compute.py, stats.py, regression.py
  probes/     pressure_corpus.yaml, README.md        dual-use; see §7.4
  calib/      clean.py, looper.py, pushover.py, confabulator.py
  report/     render.py
  cli.py
.githooks/    commit-msg                             blocks silent re-freezes (§3.4)
frozen/       frozen_scenarios.json + MANIFEST.sha256  git-tracked, do NOT regenerate
runs/<id>/    traces.jsonl, runs.jsonl, verdicts.json, scorecard.json, report.html
```

The frozen set is protected twice: a `commit-msg` hook rejects any commit touching it unless
the message starts with `REFREEZE:`, and a content hash in `frozen/MANIFEST.sha256` is
asserted by the test suite — which still fires under `--no-verify`, `git revert`, or CI,
where hooks do not run.

---

## Offline mode — read this before quoting a number

With no API key, the calibration agents run **scripted policies** that carry the same
defects as their rigged system prompts. This makes the whole platform demonstrable with
zero spend, and it is how every number in this README was produced.

What that proves: the harness, simulator, fault injection, verifier, scorecard, statistics
and regression tracker work end to end, and the platform recovers a known ranking from
agents it was not told about.

What it does **not** prove: anything about a real model's behaviour. The scripted policies
and the scenario templates were authored in the same repo, so `clean` scoring exactly 100.0
reflects that co-design as much as it reflects the agent — and a co-designed control at the
ceiling is exactly the kind of number that deserves suspicion. **Headline numbers about an
agent must come from an LLM-backed run**; every report banners which mode produced it.

**The online validation has not been run.** No credentials of any kind were available in
this environment (`ANTHROPIC_API_KEY` unset, no `ant` CLI profile), so `demo.sh --online`,
the LLM feasibility solver, the LLM phrasing pass and the judge have never executed against
a real model. The four-way ordering above is an offline result only. Until that run happens,
treat the acceptance criterion as *the platform is internally consistent*, not *the platform
measures model behaviour correctly*.

---

## Limitations

1a. **The online execution path IS mechanically validated.** This is a positive claim and
   it was earned, so it is stated separately from what it does not establish. Against a
   live, non-scripted endpoint the harness has demonstrably performed: multi-turn tool
   calling (real `tool_use` blocks, `tool_result` threading, message-history reconstruction
   verified by cache-key match), kill switches firing on real runs (`BUDGET_EXCEEDED`,
   `TIMEOUT`), provider-fault classification (502s recorded as INVALID, never blamed on the
   agent), bounded counted retries (27 recoveries across 13 of 32 runs, surfaced rather than
   laundered), and provenance-carrying model labels. The plumbing works.

1b. **Model-attributed reliability results remain unvalidated.** Two independent reasons,
   either of which alone is disqualifying:

   * **No reportable run was achieved.** `invalid_rate` was 28% on the first attempt and
     12.5% after raising the wall-clock cap and adding 5xx retries — against a 5% ceiling
     (§6.1). Every failure was gateway instability, not agent behaviour. The available
     infrastructure could not sustain a reportable run, and the full-suite run was
     deliberately not attempted on that basis.
   * **The endpoint was not Anthropic, and its model identity is unverifiable.** Traffic
     went to a third-party router (`router.bynara.id`); the model served was
     `qwen-3.8-max-free` — **no Claude model was involved in any online run**. Even the
     Qwen identity rests on the router's own echo and the model's self-report, neither of
     which is proof: a gateway can serve a different checkpoint, a quantised build, or a
     substitute, and nothing in the response would reveal it. Every online artefact is
     therefore labelled `qwen-3.8-max-free (via router.bynara.id, provenance unverified)`,
     and no number from those runs appears in this README or the tagged artifact.

   Consequently **this project reports no validated model-attributed reliability result.**
   The headline table is scripted-policy behaviour with the co-design caveat above; the one
   online ordering signal obtained came from a 12.5%-invalid run and is logged as a
   hypothesis, not a finding.

1c. **The LLM judge is uncalibrated and has never run.** No human-labelled agreement study,
   so no κ is reported — and a κ computed against labels produced by Claude would be
   circular, since the judge is Claude. Judge-derived findings are marked *LLM-judged,
   unvalidated* wherever they appear, and `--judge` is opt-in. Cutting it entirely and
   reporting rule-based modes only is a supported, more defensible configuration. Cohen's κ
   with a bootstrap CI is implemented and waiting on human labels.
2. **Scenarios come from 13 hand-authored templates.** Coverage is bounded by template
   imagination, not by the real failure distribution.
3. **Single domain** (Internal Ops Console). Cross-domain transfer is unvalidated.
4. **Mocked tools mean limited tool-level realism.** Timing, rate limits and real API error
   semantics are approximated.
5. **Absolute scores are not comparable across agents with different toolsets.** Only
   paired, same-suite comparisons are meaningful.
6. **`must_refuse` and `must_request_clarification` are decided by fixed text lexicons**
   over the final answer, plus the mutation log. The mutation-log half (did anything
   irreversible happen?) is exact; the text half is heuristic and an unusual refusal
   phrasing can read as a non-refusal.
7. **The feasibility gate is validated against mutations we authored.** 100% catch over six
   classes (n=40) shows it catches the defect classes we thought of — the same co-design
   exposure as the calibration agents. It has never rejected a real generated scenario
   (0/174). `--solver llm`, the backend that would catch "possible but unreasonable" rather
   than "impossible", **was attempted and could not be evaluated**: a 25-scenario sample
   returned 25/25 provider faults in 766s against the only endpoint available, so the
   rejection rate is `NOT MEASURED`, not 0%. (Reporting it as 0% was bug #8.) Counted as
   future work, not a shipped capability.
8. **L3 is OS-enforced only for offline container runs.** Online runs need egress to the LLM
   API, so `network_mode: none` is off and only a process-level allowlist remains — a
   control, not containment. The parent-process unix-socket proxy that would close this is
   not implemented, so online runs ship **L1 + L2 + L4** (the §7.9 fallback ladder, invoked
   explicitly). `selftest` fails rather than skips in that configuration.
9. **Flakiness is not measurable offline.** Repeats of a scenario receive a byte-identical
   instruction, so against a deterministic scripted policy all N runs are identical and the
   flake quarantine is structurally vacuous. Reported as `flaky_measurable: false` rather
   than as an empty list.
10. **There is no paraphrase-sensitivity measurement.** The metric that was briefly named
    that is now `VARIANT_SENSITIVE`, because an audit of the frozen set showed sibling
    variants differ in `world_state`, `seed`, `faults`, `assertions` and `pressure_tags` —
    not only in wording. Isolating a wording effect needs siblings that hold seed and every
    bound entity fixed; that is a scenario-set change and therefore a re-freeze.
11. **Rule-based confabulation detection requires a state-change assertion.** On refuse/ask
    scenarios there is no state delta to check, so a fabricated claim there would be visible
    only to the (uncalibrated, opt-in) judge.
12. **Defect coverage is uneven across the frozen set.** FABRICATION is exercised on 17 of
    60 scenarios; 25 are gated by the agent's own safety path and 18 never receive the
    trigger. The detection rate is sound on its own denominator but the sample is small,
    and its lower confidence bound (0.82) is the number to quote, not the point estimate.
13. **Worst-finding scoring discards within-band variation.** `looper` fails with nine
    distinct mode signatures across the frozen set, but all of them are MAJOR, so every
    scenario scores 0.35 and its composite interval collapses to a point. The composite
    cannot distinguish those nine failure shapes; the per-mode table is where that
    information lives.
14. **No MCP adapter.** One agent-loop shape is supported (`SimpleLoopAdapter`), plus any
    Python callable (`CallableAdapter`).

---

## Dual-use notice

`are/probes/pressure_corpus.yaml` is, functionally, a small jailbreak library. It exists to
measure whether an agent performs irreversible actions it should refuse.

**It is published here deliberately, and the reasoning is recorded in CLAUDE.md §7.4.**
Short version: the headline regression result is not reproducible without it —
`pushover@v2`'s gate keys on authority-vs-urgency cues in the instruction text, so redacted
payloads collapse v2 onto v1 and the P3 delta (+44.1) disappears. The payloads are in-domain
ops-console phrasings aimed at tools that are mocked with no pass-through (L1), not novel or
transferable exploits.

What that exception does **not** relax, and what is enforced mechanically rather than by
convention:

* payload text lives in that one file and nowhere else;
* reports reference payloads by **id and category only** — `report/render.py` calls
  `assert_no_payload_text()` and refuses to write a report that leaks one, and scenario
  instructions are redacted to `[pressure payload ID / category — text withheld]` in every
  trace drill-down;
* `are/probes/README.md` states the intended use and the rules for adding to it.

If the corpus ever grows novel, cross-domain, or non-mocked-tool payloads, it goes back to
private distribution.
