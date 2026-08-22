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

A short demo is won on narrative and three numbers, not on item count. These three:

| number | what it settles |
|---|---|
| **60 of 60** scenarios separate at least one agent pair, and **zero** false positives on the control | the suite can actually tell agents apart, and does not cry wolf on a good one |
| **−29.8, p<0.0001, exit 1** on a real regression — and **zero flips** on the A/A null | the tracker fires on a real change *and* stays silent on no change |
| **P=0.29** on our own refusal heuristic — with **0 of 120** verdicts depending on it | we measured our weakest component, published the bad number, and bounded its blast radius |

The third is the one that buys credibility for the first two.

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

## Slide 2 — "Eleven times this harness measured the wrong thing"

Right after the fingerprint table. This is the strongest material in the deck, and it is
strongest told as a pattern rather than as eleven anecdotes.

The one-line version: **attribution, green tests, and tight confidence intervals each failed
to catch at least one of these.** What caught them was changing the denominator or the unit,
not looking harder at the same number.

**The line that lands hardest, and it is new:** *four of the eleven are in tests written to
prevent exactly this bug.* Two tests re-implemented the thing they were meant to guard, so
reverting the fix left the suite green. One regenerated the files it was checking and then
compared them to themselves. One counted receipts without checking any of them said
anything. The reflex to check a negative survives even while you are writing the guard
against it — which is why the standing rule here is now **mutation**: revert the fix, watch
the suite go red, or the test is not evidence.

The full table is CLAUDE.md §7.10, numbered 1–11. Ids 1–4 predate the log kept in this repo
and are marked NOT RECOVERABLE rather than back-filled — if someone asks, that is the
answer, and inventing them would be its own instance.

| # | The number said | The truth | Caught by |
|---|---|---|---|
| 1 | confabulator 95.3 [91.8, 98.2], attribution 100% | defect fired on the wrong trigger (`total_cents` in any response) | denominator split: only 5/60 scenarios could exercise it |
| 2 | attribution 100%, tests green | fabricated on clean read-only scenarios | declared-trigger assertion |
| 3 | attribution 100%, tests green | marked the agent's one *correct* behaviour as its defect | declared-trigger assertion |
| 4 | "4 paraphrase-sensitive groups" | siblings differ in world state, seed, faults, assertions, payload id | field-by-field sibling audit |
| 5 | every safety number | tier system failed OPEN — `IRREVERSABLE` typo left `is_irreversible()` False, downgrading CRITICAL to MAJOR | testing a day-one invariant that had never been run |
| 6 | "bit-identical replay" | a replay miss fell through to a **live API call**, blending recorded and fresh responses | testing the replay guarantee, also never run |
| 7 | "ACCEPTANCE: FAIL — fix the platform" | rendered twice from runs its own scorecards had marked `reportable=False` (12.5–28% invalid) | reading the scorecards the gate had just written |
| 8 | "feasibility discard rate 0.0%" | 0.0 returned when **nothing was evaluated** — 25/25 provider faults printed as a clean rate | running `--solver llm` for real |
| 9 | "JUDGE-ATK-01 PASS" | the injection test was **structurally incapable of failing** — its flip criterion needed a control finding it never had | running the judge-attack corpus for the first time |

Then the payoff, which is the reason to show this at all:

> A fifth defect was chosen **after** the taxonomy was frozen — an agent that announces
> completion and never performs the change — with **no detector added for it**. It
> partitions the frozen set cleanly, all 60 scenarios, no residue: 14 requiring a mutation
> caught on `TASK_INCOMPLETE` + `WRONG_FINAL_STATE`, 30 requiring a refusal on
> `REFUSAL_EXPECTED`, 9 requiring a question on `MISSING_CLARIFICATION`, and 7 read-only
> scenarios that correctly pass. No coincidental passes, no partial detections. That is the
> evidence the taxonomy generalises past what it was authored against.

And the shape of that partition is a second finding: **one defect, three signatures** —
the classifier labels by the requirement violated, not by root cause. That is the same
lossiness as `looper`'s nine mode signatures collapsing to one composite value, reached from
the opposite direction. Both the scoring and the classifier trade *why* for *whether*. If
you have one spare sentence on this slide, it is this one — two independent validity checks
converging on the same structural property is worth more than either alone.

**The line to lead with on this slide:** #5, #6, #7, #8 and #9 are the same bug five times —
a guard returning a confident value instead of refusing to answer. Malformed tier → "not
irreversible". Replay miss → live API call. Unreportable data → PASS/FAIL. Nothing
evaluated → 0%. Undiscriminating test → PASS. For an evaluation harness the dangerous
default is not a crash, it is a plausible number. Every one of these looked like health.

#5 and #6 are the cheap ones, and the line to say out loud: a sweep of every
stated-but-untested invariant found **five claims, two of them false**. The three that held
are now tested rather than asserted. 40% is the base rate to assume for any untested claim
in a design doc — including the remaining ones on this slide.

If asked "why are you showing me your bugs": because a harness that has never caught itself
being wrong has not been tested, it has been run. The four above are the reason to believe
the fifth result.

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
| 6 | Eleven times we measured the wrong thing | `CLAUDE.md` §7.10 | Four of the eleven are in tests written to prevent it |
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
