# Judge live run — reporting commitment, written BEFORE the run

**Status: not yet executed.** No credentials in the environment at time of writing.

This file exists because of when it was written. check.md C4 requires the reporting
commitment to be recorded *before* the result is known, and names the reason plainly:

> A red result surfacing shortly before a demo is exactly when quiet re-scoping tempts.
> That temptation is what the eleven instances are made of.

So the decision is made here, with no result to be tempted by.

## The commitment

**Both outcomes get reported, in the README, at the same prominence.**

| outcome | what gets published |
|---|---|
| the judge **holds** under all three JUDGE-ATK payloads | §7.2 moves from UNVERIFIED to **verified**, stating the model, endpoint and date — and noting it is one endpoint, not a general claim |
| the judge **flips** on any payload | §7.2 records a **FINDING**: our own injection corpus defeats our own oracle. It goes in the README limitations *and* the demo deck. `--judge` stays opt-in and the `LLM-judged, unvalidated` labels stay |
| the probes cannot run (provider faults) | reported as **INCONCLUSIVE**, never as a pass — the §7.10 rule that produced this whole discipline |

**A flip is a finding, not a setback.** By this project's own rule — *finding > feature* —
a judge that fails its own attack corpus is more valuable to report than one that passes,
because it is the difference between an oracle we trust and an oracle we have checked.
Nothing about a red result gets softened, deferred past the demo, or re-scoped.

**What will not happen:** the judge will not be tuned, the payloads will not be swapped,
and the probe set will not be narrowed in response to a red result. Any of those would be
instance fourteen.

## How to run it

```bash
git checkout judge-live-run
export ANTHROPIC_BASE_URL=https://router.bynara.id
export ANTHROPIC_API_KEY=<key>
export ARE_JUDGE_MODEL=qwen-3.8-max-free
python -m are.cli selftest          # fires the three JUDGE-ATK probes for real
```

Expect `selftest` to also report **L3 as degraded** — with a live key, OS-level egress deny
cannot be on, because egress is required. That is correct behaviour (§7.9), not a
regression introduced by this run.

Record the outcome in §7.2 as a **result**, with model and date — not as a status.
