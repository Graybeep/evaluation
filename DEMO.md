# Demo running order

Written before demo day, on purpose. The framing decision below is not a slide-ordering
preference — it decides which conversation you have afterwards.

---

## The opening line — use the brief's own number

The brief cites roughly **70% of agent deployments failing in the real world**. That is a
free opening, because it invites exactly one question and we have the answer:

> **"Which 70%? And how would you know?"**

That is not rhetorical. "70% fail" is a rate; it tells you nothing about *what* failed, so
it cannot tell you what to fix. The whole platform is an answer to the second half of the
question, and the defect fingerprint table is the answer in one screen: it does not say
*that* an agent failed, it says **which failure mode**, on how many scenarios, and — the
part almost nothing else does — **which modes it could not check at all**.

Say it in this order:

1. *"The brief says ~70% fail. The useful question isn't the rate, it's which ones and how
   you'd know."*
2. *"Here are five agents. Four have a defect I chose; the platform isn't told which."*
   → run `calibrate`
3. *"It recovers the ranking, names each defect, and where it couldn't check something it
   says so instead of showing a clean row."*

Point at `confabulator` when you say the last part: one third of its declared fingerprint
is `UNGROUNDED_CLAIM`, a judge mode, and with the judge off that row reads **NOT
APPLICABLE**, not a pass. That single row is the difference between a dashboard and a
measurement, and it is worth more airtime than any score on the screen.

### The three hard numbers to land

A short demo is won on narrative and three numbers, not on item count. These three, in
this order:

| # | number | what it settles |
|---|---|---|
| 1 | **14 of 20** instances of our worst bug were inside the guard against it, not the harness — so every shipped fix is revert-checked (count PENDING a clean sweep; see note) | the bug class is self-camouflaging; vigilance is not a strategy, so we mechanised the only rule that survives |
| 2 | **zero** false positives on `clean` — at most **6.0%** on `DESTRUCTIVE_ACTION` (0/60), but at most **56%** on `ARG_CONSTRAINT_VIOLATED` (0/3) | the suite does not flag a good agent — *and* we report how little that proves per detector, because the denominator is applicability, not 60 |
| 3 | **P=0.29** on our own refusal heuristic, with **0 of 120** verdicts depending on it | we measured our weakest component, published the bad number, and bounded its blast radius |

**Number 2 is the one to slow down on.** "Zero false positives" is the reassuring headline;
the honest half is the second clause. `ARG_CONSTRAINT_VIOLATED` at 0/3 is *at most 56%* —
with three applicable scenarios you know almost nothing, and dividing by 60 instead would
have made it look twenty times safer. That single row is the whole method in miniature.

Number 1 is what buys the credibility for 2 and 3.

---|---|
| **14 of 20** instances of our worst bug were inside the guard against it — and every fix is revert-checked (count PENDING a clean sweep) | the bug class is self-camouflaging, so we mechanised the only rule that survives it |
| **−29.8, p<0.0001, exit 1** on a real regression — and **zero flips** on the A/A null | the tracker fires on a real change *and* stays silent on no change |
| **P=0.29** on our own refusal heuristic — with **0 of 120** verdicts depending on it | we measured our weakest component, published the bad number, and bounded its blast radius |

(`60 of 60` scenarios discriminate with zero false positives on the control is the fourth,
if you have room — but three is the budget.)

The first is the one that buys credibility for the other two.

---

## If there is no API key by demo day

**The offline framing goes on the FIRST slide, not the limitations slide.**

Say this, in these words, before showing a single number:

> These numbers prove the harness recovers a ranking it was not told. They prove nothing
> about real model behaviour. Here is the one command that would.

Then show the command:

```bash
./demo.sh --online --smoke      # 6 scenarios x 4 agents, hard token cap
```

Why the order matters: presenting the calibration table as a result and *then* being asked
"is that a real model?" is the losing version of this conversation. You lose the room's
trust in every other number on the slide, including the ones that deserve it. Volunteering
it first costs one sentence and converts the same fact into evidence that you know what
your own measurement does and does not cover.

The offline result is genuinely worth showing — it is an end-to-end demonstration that the
generator, simulator, fault injection, verifier, scorecard, statistics and regression
tracker all work and recover a known ranking from agents the platform was not told about.
It is just not a claim about models, and the slide must not imply that it is.

---

## Slide 2 — "Fourteen of twenty were in the guard itself"

Right after the fingerprint table. This is the strongest material in the deck, and the
**ratio is the finding** — the count is supporting detail. Lead with this sentence:

> **Fourteen of the twenty times this harness measured the wrong thing, the defect was
> not in the harness — it was in a check, a guard, or a rehearsal written to prevent
> exactly that.**

That is 70%. Nine were found by *running* something, never by re-reading.

Because that says something a list of twenty anecdotes does not: **the bug class is
self-camouflaging.** A guard against *measuring the wrong thing* fails by measuring the
wrong thing —

* two tests **re-implemented their subject**, so reverting the fix changed nothing;
* one **regenerated the files it was checking**, then compared them to themselves;
* one **counted receipts** without checking any of them said anything;
* one asserted a **tautology** — a partition that could never fail to sum;
* one tested the **helper** while the artifact everyone reads went unchecked;
* and one was **a tautology test written to replace a tautology** — found only by running
  a coverage sweep over the tests the revert-check had just produced.

The guard adopts the failure mode of the thing it guards. So vigilance is not a strategy,
and "we were careful" is not evidence. The only rule that survives is **revert-checking**:
revert the fix, confirm the suite goes red, restore.

**And that is now an empirical result, not a preference.** `scripts/revert_check.py` does
it mechanically, and it found **three of the twenty** — rows 12, 13 and 14 — including one
inside a fix it had itself just prompted. Widen it from that mechanism to *running
something at all* and the count is **nine of the twenty**: add a rehearsal checklist that
had never been executed, the analysis of the judge result that proves the tool works, and a
rehearsal that recorded a crash as a pass. Running things caught instances that re-reading
the code never did. Keep the two numbers apart on stage — three is what the revert-check
itself found; nine is what execution found.

**The strongest version, and the one to actually say:** this is not a story about one
codebase being sloppy. The same mechanism shows up at **four layers** — in the harness's own logic
(5), in the checks written against it (12), in the demo process (2), and in the analysis of
the results (1) — twenty in total, and the buckets are disjoint. Where
asking *"is it really done?"* found a real gap three times. Every occurrence has the same
shape: **verification drifts toward the implementation and away from the requirement.**
Cross-layer evidence is much harder to wave away than a within-harness count.

> **Say the revert-verified count out loud — but only once a clean sweep has produced
> it.** Not "290 tests pass". A passing suite is a *reading*; a revert-checked fix is
> *evidence*. If someone asks why you are quoting the smaller number, that is the answer,
> and it is the best thing in the deck.
>
> **As of 2026-08-23 14:40 that count is PENDING**: two sweeps overlapped, and the surviving
> `revert_verified.json` reports `tree_restored_and_green: False`. Run one locked sweep on a
> clean tree on the morning of the demo and read the number off the artifact.
>
> This slide has now carried three wrong values for one quantity — `23 of 23` while the
> script held 25 mutations and the report recorded 21, then `25 of 25` from a raced run.
> Each was written by reading *a* number rather than checking what produced it. That is the
> slide's own subject, which is why the failure is left on the slide instead of tidied
> away.

If asked what the gaps in the old numbering were: the table is now sequential 1–14, and
ids 1–4 predate the build log kept in this repo. They are marked **not recoverable** rather
than back-filled, because inventing them would be its own instance.

---

## Running order (3 minutes)

| # | Beat | Command | The point |
|---|---|---|---|
| 0 | **"Which 70%?"** | — | The brief's own number, turned into the question this platform answers. Offline/online status up front (see above) |
| 1 | The harness is the risk surface | `are selftest` | L1–L4, world isolation, our own injection corpus fired at our own judge, secret scrubbing. Judge probes report **SKIPPED**, not passed |
| 2 | Five agents, defects not disclosed | `are calibrate --scenarios frozen/frozen_scenarios.json --offline --no-sandbox` | Ranking recovered; the **three-state fingerprint**; point at `confabulator`'s NOT APPLICABLE row |
| 3 | One failure, end to end | `are report runs/calib-pushover` then open its `report.html` | Framing → `issue_refund` → the assertion that caught it, payload by id only. **Generate it first** — `calibrate` writes verdicts, `report` renders them |
| 4 | Regression **and** null | **first** `bash scripts/demo_runs.sh` (builds the three runs), then `are compare runs/p3-v2 runs/p3-v1 --ci` and `are compare runs/p3-v1 runs/p3-v1b --ci` | −29.8 exit 1, then zero flips exit 0. **Run both** — the null is what makes the first credible. `runs/` is gitignored, so a fresh clone has nothing to compare until you build it |
| 5 | What the suite says about *itself* | `are analyse` | 60/60 discriminate; zero FPs on the control; **two detectors that never fire on the frozen set — a gap in the SUITE, not the detectors; both have revert-verified positive controls outside it**; top-3 templates are 50% of the suite |
| 6 | **Fourteen of twenty were in the guard itself** | `CLAUDE.md` §7.10 + `reports/revert_verified.json` | The ratio, then the rule it forces. Quote the revert-verified count, not the test total — **and only if the artifact also says `tree_restored_and_green: true`** |
| 7 | Limitations | `README.md` | 1a/1b split: the online *path* works; model-attributed *results* do not exist. Judge uncalibrated. Refusal lexicon P=0.29, and 0 of 120 verdicts rest on it |

Steps 6 and 7 are the ones people remember. Step 0 decides whether they believe 2–5 at all.

**If you have 60 seconds, not 3:** step 0, step 2, step 4. The question, the fingerprint,
the regression-plus-null. Everything else is supporting evidence.

---

## Questions that will be asked, and the honest answer

**"Is the control agent at 100.0 because it's good, or because you wrote both sides?"**
Partly the latter, and it is in the README as a limitation. The scripted policies and the
scenario templates were authored in the same repo. That is exactly why the online run
matters, and why the ranking — not the absolute score — is the claim.

**"A 0% feasibility discard rate means the gate does nothing."**
It means the authored scenarios are feasible. The gate's power is measured separately:
`python -m are.cli gate-audit` injects known defects and reports the catch rate (100% over
six mutation classes, n=40). It also caught two real authoring bugs the day the fault rate
changed. The `--solver llm` path is untested and is listed as future work.

**"Your detection rate is 100%."**
On 17 scenarios, with a 95% Wilson interval of [0.82, 1.00] — the scorecard prints the
interval, not the bare rate. A further 25 scenarios never exercise that defect at all
because the agent's own safety gates fire first; that is a coverage limit of the frozen
set, and it is reported as its own bucket rather than folded into the denominator.

**"Why should I trust the attribution number?"**
You shouldn't, on its own — attribution says failures trace to the injected defect, not
that the defect fired for the intended reason. Those came apart here: a bug made one agent
fabricate on fault-free scenarios while attribution still read 100%.
`tests/test_defect_opportunity.py` asserts every firing occurs under its declared trigger.
That is the check that catches it; the scorecard number never will.

**"Isn't a [65.0, 65.0] interval suspiciously confident?"**
It is degenerate by construction, and the scorecard says so on the card. Every one of that
agent's 60 scenarios carries the same penalty value, so a bootstrap over them has zero
variance. It means "this failure is deterministic", not "this estimate is precise". The two
agents with genuine spread produce 125 and 25 distinct bootstrap values on the same code
path — that is how the resampling was checked rather than assumed.

**"Isn't this an LLM grading an LLM?"** — *this is the one to be ready for; it is what
people pattern-match to, and it is the project's headline claim, so expect it probed.*

No, and the artifacts prove it rather than asserting it. Every headline number in this
submission was produced with the judge **off**: the four calibration runs, both arms of the
v1/v2 comparison and the `quitter` external check all record `"judge_used": false` and
`"judge_version": null` in their `scorecard.json`. (One scratch run, `judge-probe`, has the
flag set — it was a test of the `--judge` path with no API key, produced zero judge findings,
and backs no number here.) The verdicts come
from assertions authored in the templates and evaluated against the trace, the mutation log
and the final world state: `no_call`, `must_call`, `call_args_match`, `mutations_subset_of`,
`state_equals`, `max_tool_calls`, plus standing detectors for kill-switch trips, identical
call loops and injection-following. Those are computed, not inferred.

The judge exists, and it is scoped to 2 of the 13 failure modes — `UNGROUNDED_CLAIM` and
`OVERCONFIDENT_SUMMARY`, the two that genuinely are subjective. It is opt-in (`--judge`),
abstains below 0.7 confidence into INVALID rather than guessing, and every finding it
produces is stamped *LLM-judged, unvalidated* in the report. It is also uncalibrated — no
human-labelled agreement study, so no kappa is reported, and cutting it entirely is a
supported and more defensible configuration.

Do not get defensive here. The honest version is stronger: "correct, which is why it is off
by default, why it can only produce 2 of 13 modes, and why none of the numbers you are
looking at used it."

**"Did you ever run it against a real model?"** — *answer both halves, in this order.*
Yes, and the execution path is validated: live multi-turn tool calls, kill switches firing,
provider faults correctly classified INVALID rather than blamed on agents, retries counted
and surfaced. The plumbing demonstrably works.

No — it was attempted on 2026-08-23 and the endpoint stopped it. Say that plainly; the
failure is more interesting than a shrug.

**Two runs, both unreportable, both for endpoint reasons.** Preflight: 25% invalid on
`502`s from the gateway CDN. Full run: **100% invalid on `429 rate_limited`**, a per-minute
cap. Against §6.1's 5% ceiling neither is reportable, and **no composite from either
appears anywhere in the repo** — the reporting rules were fixed in advance in
`reports/ONLINE_SUITE_RUN_COMMITMENT.md`.

**What the failure demonstrated is the part worth saying.** The harness classified every
one of those failures correctly: provider faults recorded as **INVALID**, never charged to
the agent, and `calibrate` exited **2** (harness/endpoint) rather than **1** (agent
regressed). The three-way outcome and the CI exit codes did their job under real adverse
conditions instead of in a unit test. A tool that reported 100% agent failure there would
have been lying, and this one said "not reportable, and not the agent's fault".

**And the run found a live defect.** The retry policy read *"a 429 from this gateway means
insufficient credits, which retrying cannot fix"* — an assumption never checked against a
real response body. The real error was `type: rate_limited`, the retryable kind, and that
one assumption discarded **359 of 360 runs**. Fixed, with credit exhaustion still fatal and
both branches asserted. Same reasoning error as §7.10 rows 17 and 20: a rule written from a
picture of the input rather than the input.

**What is unaffected, and worth showing instead:** the MCP transport. There ARE is the
*server* — the external agent brings its own model and key, and `runner/mcp_server.py`
makes no LLM calls at all. Demonstrated end-to-end with `ANTHROPIC_API_KEY` unset:
`initialize`, `tools/list` (12 tools), `tools/call`, `submit_answer`, and a real
`MISSING_CLARIFICATION` verdict. **Pointing an agent at this harness never depended on the
router.**

The caveat that survives regardless: a router decides what actually serves a request, so
model identity rests on its own echo. That matters only for a claim attributed to a *named
model* — which this project does not make. Artefacts say `provenance unverified`.

Say it as: **"we ran it, the endpoint rate-limited us, and the harness correctly refused to
turn that into an agent result."** That is a precise engineering status, and it is stronger
than either "we ran it online" or "we never tried".

**"Can this block a merge?"**
No, by design. Nothing in `score/` returns a gate decision. A hard automated gate on an
LLM-derived score invites optimising the eval instead of the agent.


---

## Rehearsal checklist

check.md reserves the final block for this, and it is not padding: every failure in this
project's history is something that looked fine until it was executed.

**Run the deck end to end, from a clean shell, before demo day.** Not read — *run*.

**Executed three times, most recently 2026-08-23 against a fresh clone.** Every line below
is a recorded result, not an expectation. Executing it has now caught three defects the
written version could not: a wrong test count, a step that needed `report` run first, and
a beat that crashed because `runs/` is gitignored — the last of which **exited 1, the same
code that beat expects**, so the first rehearsal passed it for the wrong reason.

**Measured timings.** Cold, in a fresh clone including building the comparison runs:
**14s**. Warm: **7s**. `demo.sh` end to end: **50s**. The three-minute budget is not tight —
it is almost entirely narration, which is where the attention should go.

```bash
git clone --branch v1.6-demo <repo> /tmp/rehearse && cd /tmp/rehearse
pip install -r requirements.txt

python -m pytest -q            # -> RE-MEASURE, see note (was 282 passed + 3 skipped
                               #    when the suite held 285; it now holds 290)
python scripts/revert_check.py # -> RE-MEASURE: needs one locked sweep on a clean
                               #    tree; last artifact ended tree_restored_and_green=False
python -m are.cli selftest              # -> exit 0 (3 judge probes SKIPPED)
python -m are.cli selftest --strict     # -> exit 1, BY DESIGN
python -m are.cli calibrate --scenarios frozen/frozen_scenarios.json --offline --no-sandbox
                                        # -> exit 0, ACCEPTANCE: PASS
python -m are.cli analyse               # -> exit 0
python -m are.cli report runs/calib-pushover        # -> exit 0, writes report.html
python -m are.cli compare runs/p3-v2 runs/p3-v1 --ci   # -> exit 1  (regression)
python -m are.cli compare runs/p3-v1 runs/p3-v1b --ci  # -> exit 0  (A/A null)
bash demo.sh                            # -> exit 0 in 50s
```

> **A fresh clone gives `282 passed, 3 skipped`. The skips are real and you should know
> why before someone asks.** A fresh clone has
> no run artifacts — `runs/` is gitignored — so three tests that read committed artifacts
> skip loudly. They are *not* the CI or regression claims; those build what they need.
> After `calibrate` + `analyse` the count is **284 passed, 1 skipped**, and after
> `gen-targeted` it is **285 passed, 0 skipped**. All three counts were measured on
> 2026-08-23 in a fresh clone of `main`.
>
> **These three counts are STALE and must be re-measured before the demo.** They were
> executed on 2026-08-23 against a suite of 285 tests; `reports/revert_verified.json` now
> records **290 passed** after its restore, so five tests have landed since. The numbers
> are left visible with their date rather than quietly updated to an inferred 287/3,
> because inferring them is the error this note exists to record.
>
> An earlier version of this checklist said "expect 253 passed". That was written from
> memory and was wrong on a clean machine — which is the `report.html` bug one level up,
> and is exactly why this block records executed output instead of expectations. The fix
> for that bug then left `256 passed` in the command line above it, three lines from a
> note saying 282 — the same error surviving inside its own correction.
>
> **Re-running this is not ceremony.** The 2026-08-23 pass of exactly this sequence is
> what surfaced §7.10 row 19: `calibrate` on its *default* path returned
> `ACCEPTANCE: FAIL` with `looper`'s defect invisible, while every reported field said
> the run was healthy. `demo.sh` passes `--no-sandbox`, so nothing else in this
> checklist could have found it.

**Three things that will bite if you skip this:**

1. **`selftest --strict` exits 1** on a keyless checkout. That is correct and documented,
   but it looks like a failure on a projector. Use plain `selftest`, and if someone spots
   the flag, the answer is one sentence: *an unrun security check is not a passing one.*
2. **Steps 3 and 4 need their artifacts built first.** `calibrate` writes verdicts,
   `report` renders them; and `runs/` is gitignored, so the p3 comparison runs do not
   exist in a fresh clone. Both assumptions broke the running order — the second was
   worse, because `compare` crashed and exited **1**, which is also the expected code for
   that beat. A rehearsal can pass for the wrong reason.
3. **With a live key, `selftest` reports L3 degraded.** Also correct (§7.9) — egress deny
   cannot be on when you need egress. Say it before anyone asks.

**Time the whole thing.** The 3-minute order is a claim; make it a measurement. If you are
over, the 60-second cut is steps 0, 2 and 4 — the question, the fingerprint, the
regression-plus-null.

**Rehearse the two questions you least want.** *"Isn't the control at 100 because you wrote
both sides?"* and *"Your judge is uncalibrated — why should I trust the oracle?"* Both have
honest answers already written in the §"Questions" section below. Say them out loud once;
the answers are good, and they only sound good if they are not being improvised.
