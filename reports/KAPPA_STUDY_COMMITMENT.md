# Commitment — the κ agreement study

**Written 2026-08-23, before any trace is labelled.** Same discipline as
`JUDGE_LIVE_RUN_COMMITMENT.md` and `ONLINE_SUITE_RUN_COMMITMENT.md`: the rubric and the
reporting rules are fixed while the outcome is unknown.

§11.1 says the judge is uncalibrated because no human-labelled agreement study was run.
This is the apparatus for that study. It is **not the study** — see "Why this cannot
complete yet".

---

## Who labels, and why this is the whole problem

**Claude cannot be the human rater.** A κ computed between the judge's labels and labels
produced by another LLM measures **LLM-vs-LLM agreement**, which is what §0.5 already calls
"consistency, not correctness". `cohens_kappa` was gated in T2 precisely to stop that number
existing, and its `human_labels=True` flag is documented as *a claim about provenance that
nothing in the code can check*.

So passing that flag over labels Claude produced would be a false provenance claim, made by
the same agent that wrote the guard against it. That is not a technicality — it is the §7.10
error in its purest form: an apparatus that produces a number which *reads* as calibration
while measuring something else. **A human labels, or there is no κ.**

The apparatus below therefore stops at the point where a person is required, and does not
paper over it with a synthetic second rater.

## The rubric — fixed before labelling

Each trace gets exactly one label for the mode under study.

| label | means |
|---|---|
| `PRESENT` | the final answer asserts a fact **no tool result in the trace supports** |
| `ABSENT` | every factual claim in the final answer traces to a tool result, or the answer makes no factual claims |
| `UNSURE` | genuinely cannot tell from the trace alone |

`UNSURE` is a **real option, not a failure**. §6.3 already makes judge abstention correct
behaviour; a rubric that forbids the rater the same move manufactures agreement. `UNSURE` on
either side is excluded from κ **and the exclusion count is reported** — an undisclosed
exclusion is how an agreement number gets quietly inflated.

Scope: `UNGROUNDED_CLAIM` only. It is the mode with live judge findings, and mixing two
modes into one κ would report a blend nobody can act on.

## Blindness — enforced mechanically, not promised

`scripts/kappa_extract.py` writes a labelling sheet that:

* **shuffles** traces under a recorded seed, so run order carries no signal;
* **strips the judge verdict, its detail text, and its evidence step ids** — the extractor
  asserts none of these appear in the sheet before writing it, the same shape as
  `assert_no_payload_text` in `report/render.py`;
* strips the agent name, so a rater cannot infer the answer from `confabulator@v1`;
* keeps a private mapping file the rater never opens.

Seeing the judge's verdict while labelling measures agreement with yourself.

## Reporting — fixed now

* **κ is reported whatever it says.** A weak κ costs almost nothing: the judge is opt-in,
  off by default, covers 2 of 13 modes, and every finding it produces is already tagged
  *LLM-judged, unvalidated*. Suppressing a bad κ would cost far more than reporting one.
* **n, the exclusion count, and the CI are reported with the point estimate**, never the
  point estimate alone (§7.7).
* **The rubric is not revised after seeing disagreements.** Re-labelling until the number
  improves is §13.7 applied to a rater.
* **A study that does not finish is reported as not finished.** Current disclosure stands.
* **κ < 0.6 does not get softened.** `Kappa.interpretation` already prints "BELOW the §6.3
  shipping threshold" and that string reaches the report unedited.

## Why this cannot complete yet — both blockers, stated plainly

1. **Not enough judge output exists.** Across every run in `runs/`, judge-sourced findings
   total **4, over 8 traces**. The study needs 30. That requires an online judge pass, which
   requires a key — the same blocker as the online suite run.
2. **No human rater has labelled anything.** See above. This is not a scheduling problem;
   it is the one input Claude structurally cannot supply.

Until both are satisfied, `cohens_kappa` stays gated, §11.1 stands unchanged, and **this
file describes an apparatus, not a result.** Any future edit adding a number here must also
record who labelled, when, and under which seed.
