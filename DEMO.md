# Demo running order

Written before demo day, on purpose. The framing decision below is not a slide-ordering
preference — it decides which conversation you have afterwards.

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

## Slide 2 — "Five times this harness measured the wrong thing"

Right after the fingerprint table. This is the strongest material in the deck, and it is
strongest told as a pattern rather than as four anecdotes.

The one-line version: **attribution, green tests, and tight confidence intervals each failed
to catch at least one of these.** What caught them was changing the denominator or the unit,
not looking harder at the same number.

| # | The number said | The truth | Caught by |
|---|---|---|---|
| 1 | confabulator 95.3 [91.8, 98.2], attribution 100% | defect fired on the wrong trigger (`total_cents` in any response) | denominator split: only 5/60 scenarios could exercise it |
| 2 | attribution 100%, tests green | fabricated on clean read-only scenarios | declared-trigger assertion |
| 3 | attribution 100%, tests green | marked the agent's one *correct* behaviour as its defect | declared-trigger assertion |
| 4 | "4 paraphrase-sensitive groups" | siblings differ in world state, seed, faults, assertions, payload id | field-by-field sibling audit |
| 5 | every safety number | tier system failed OPEN — `IRREVERSABLE` typo left `is_irreversible()` False, downgrading CRITICAL to MAJOR | testing a day-one invariant that had never been run |

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

#5 is the cheap one, and the one to say out loud: two safety invariants had been stated in
the design document since day one and neither had a test. One was false. That is the base
rate to assume for any untested claim in a design doc — including the ones on this slide.

If asked "why are you showing me your bugs": because a harness that has never caught itself
being wrong has not been tested, it has been run. The four above are the reason to believe
the fifth result.

---

## Running order (3 minutes)

| # | Beat | Command | The point |
|---|---|---|---|
| 0 | Framing | — | Offline/online status, up front (see above) |
| 1 | The harness is the risk surface | `python -m are.cli selftest` | L1–L4, world isolation, judge-attack corpus fired at our own judge, secret scrubbing |
| 2 | Four agents, defects not disclosed | `python -m are.cli calibrate --scenarios frozen/frozen_scenarios.json --offline --no-sandbox` | Ranking recovered; 100% attribution; CI disjointness checked, not eyeballed |
| 3 | One failure, end to end | open `runs/demo-pushover-v1/report.html` | Framing → `issue_refund` → the assertion that caught it, with the payload referenced by id only |
| 4 | v1 → v2, measured pairwise | `python -m are.cli compare runs/demo-pushover-v1 runs/demo-pushover-v2` | McNemar + BH + minimum meaningful effect; the P3-only delta shows *where* the fix landed |
| 5 | Four self-measurement failures | `README.md` § "Four times…" | Attribution, green tests and tight CIs each missed one; the untargeted fifth defect was still caught 14/14 |
| 6 | Limitations | `README.md` | Judge uncalibrated and never run; online never run; L3 degraded online; co-design caveat |

Steps 5 and 6 are the ones people remember. Step 0 is the one that decides whether they
believe steps 2–4 at all.

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

**"Can this block a merge?"**
No, by design. Nothing in `score/` returns a gate decision. A hard automated gate on an
LLM-derived score invites optimising the eval instead of the agent.
