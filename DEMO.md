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
| 1 | **8 of 15** instances of our worst bug were inside the guard against it — mechanical checks found 4 — so all **12 of 12** fixes are revert-verified | the bug class is self-camouflaging; vigilance is not a strategy, so we mechanised the only rule that survives |
| 2 | **zero** false positives on `clean` — at most **6.0%** on `DESTRUCTIVE_ACTION` (0/60), but at most **56%** on `ARG_CONSTRAINT_VIOLATED` (0/3) | the suite does not flag a good agent — *and* we report how little that proves per detector, because the denominator is applicability, not 60 |
| 3 | **P=0.29** on our own refusal heuristic, with **0 of 120** verdicts depending on it | we measured our weakest component, published the bad number, and bounded its blast radius |

**Number 2 is the one to slow down on.** "Zero false positives" is the reassuring headline;
the honest half is the second clause. `ARG_CONSTRAINT_VIOLATED` at 0/3 is *at most 56%* —
with three applicable scenarios you know almost nothing, and dividing by 60 instead would
have made it look twenty times safer. That single row is the whole method in miniature.

Number 1 is what buys the credibility for 2 and 3.

---|---|
| **8 of 15** instances of our worst bug were inside the guard against it — and all **12 of 12** fixes revert-verified | the bug class is self-camouflaging, so we mechanised the only rule that survives it |
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

## Slide 2 — "Eight of fifteen were in the guard itself"

Right after the fingerprint table. This is the strongest material in the deck, and the
**ratio is the finding** — the count is supporting detail. Lead with this sentence:

> **Eight of the fifteen times this harness measured the wrong thing were in code
> written to prevent exactly that — and mechanical checks found four of them.**

Because that says something a list of thirteen anecdotes does not: **the bug class is
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
it mechanically. It found **four of the eight** — including one inside a fix it had itself
just prompted, and one in the rehearsal checklist that had never been run. The mechanism caught instances that re-reading the code never did.

**The strongest version, and the one to actually say:** this is not a story about one
codebase being sloppy. The same mechanism shows up at **three layers** — in the harness
(11), in the guards written against it (4), and in this session's own review process, where
asking *"is it really done?"* found a real gap three times. Every occurrence has the same
shape: **verification drifts toward the implementation and away from the requirement.**
Cross-layer evidence is much harder to wave away than a within-harness count.

> **The number to say out loud: 12 of 12 revert-verified.** Not "253 tests pass". 253
> passing tests is a *reading*; a revert-checked subset is *evidence*. If someone asks why
> you are quoting the smaller number, that is the answer, and it is the best thing in the
> deck.

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
| 4 | Regression **and** null | `are compare runs/p3-v2 runs/p3-v1 --ci` then `are compare runs/p3-v1 runs/p3-v1b --ci` | −29.8 exit 1, then zero flips exit 0. **Run both** — the null is what makes the first credible |
| 5 | What the suite says about *itself* | `are analyse` | 60/60 discriminate; zero FPs on the control; two detectors that never fire; top-3 templates are 50% of the suite |
| 6 | **Eight of fifteen were in the guard itself** | `CLAUDE.md` §7.10 + `reports/revert_verified.json` | The ratio, then the rule it forces: 12 of 12 revert-verified — quote that, not 253 |
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

And no, not in a way that produces a quotable number. The endpoint available was a
third-party router serving **Qwen, not Claude** — so no Claude model was involved — and it
could not sustain a reportable run: 28% invalid on the first attempt, 12.5% after raising
the timeout and adding retries, against a 5% ceiling. Every online artefact is labelled
`provenance unverified`, and none of those numbers are in the repo or on these slides.

Say the first half without hedging and the second half without flinching. The split is the
point: "the path works, the results don't exist yet" is a precise engineering status, and
it is much stronger than either "we ran it online" or "we never tried".

**"Can this block a merge?"**
No, by design. Nothing in `score/` returns a gate decision. A hard automated gate on an
LLM-derived score invites optimising the eval instead of the agent.


---

## Rehearsal checklist

check.md reserves the final block for this, and it is not padding: every failure in this
project's history is something that looked fine until it was executed.

**Run the deck end to end, from a clean shell, before demo day.** Not read — *run*.

**Executed 2026-08-22 against a fresh clone at `v1.6-demo`.** Every line below is a
recorded result, not an expectation — and executing it corrected the first one, which had
been written from memory rather than measured.

```bash
git clone --branch v1.6-demo <repo> /tmp/rehearse && cd /tmp/rehearse
pip install -r requirements.txt

python -m pytest -q            # -> 250 passed, 3 SKIPPED   <-- see note
python scripts/revert_check.py # -> 12/12 revert-verified, tree GREEN
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

> **The 3 skips are real and you should know why before someone asks.** A fresh clone has
> no run artifacts — `runs/` is gitignored — so three tests that read committed artifacts
> skip loudly. They are *not* the CI or regression claims; those build what they need.
> After `calibrate` + `analyse` the count is **252 passed, 1 skipped**, and after
> `gen-targeted` it is **253 passed, 0 skipped**. All three counts were measured.
>
> An earlier version of this checklist said "expect 253 passed". That was written from
> memory and was wrong on a clean machine — which is the `report.html` bug one level up,
> and is exactly why this block now records executed output instead of expectations.

**Three things that will bite if you skip this:**

1. **`selftest --strict` exits 1** on a keyless checkout. That is correct and documented,
   but it looks like a failure on a projector. Use plain `selftest`, and if someone spots
   the flag, the answer is one sentence: *an unrun security check is not a passing one.*
2. **Step 3 needs `report` run first.** `calibrate` writes verdicts; `report` renders them.
   This exact assumption already broke the running order once.
3. **With a live key, `selftest` reports L3 degraded.** Also correct (§7.9) — egress deny
   cannot be on when you need egress. Say it before anyone asks.

**Time the whole thing.** The 3-minute order is a claim; make it a measurement. If you are
over, the 60-second cut is steps 0, 2 and 4 — the question, the fingerprint, the
regression-plus-null.

**Rehearse the two questions you least want.** *"Isn't the control at 100 because you wrote
both sides?"* and *"Your judge has never run — why should I trust the oracle?"* Both have
honest answers already written in the §"Questions" section below. Say them out loud once;
the answers are good, and they only sound good if they are not being improvised.
