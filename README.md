# Agent Reliability Engine (ARE)

A property-based testing framework for LLM agents. It does not use one model to grade
another. Every scenario ships with machine-checkable assertions, so a verdict is computed
from the execution trace and the final world state, deterministically.

```
Scenario = (initial_world_state, instruction, assertions[], pressure_tags[])
Verdict  = evaluate(assertions, trace, final_state)  ->  PASS | FAIL | INVALID
```

## Table of Contents

- [Features](#features)
- [Results](#results)
- [Prerequisites](#prerequisites)
- [Installation](#installation)
- [Usage](#usage)
- [Architecture](#architecture)
- [Limitations](#limitations)
- [Contributing](#contributing)
- [License](#license)
- [Contact](#contact)

## Features

- **Deterministic verdicts.** 11 rule based detectors read the trace, the mutation log and
  the final state. No model opinion is involved.
- **Assertions ship with the scenario.** The oracle is generated alongside the task, which
  is what makes a verdict checkable rather than inferred.
- **Three way outcomes.** PASS, FAIL, INVALID. Harness faults and provider errors are never
  charged to the agent. A run above 5 percent `invalid_rate` is declared not reportable.
- **Calibration agents with known defects.** Four agents, three deliberately broken, and the
  platform is never told which. If it cannot recover the ranking, its numbers are noise.
- **Four layer sandbox.** Tool mocking with no pass through, process and filesystem
  isolation, network allowlisting, independent resource budgets.
- **MCP server mode.** Point your own agent at it. Your agent brings its own model and key;
  ARE makes no LLM calls in this mode.
- **Paired regression tracking.** Identical scenarios and seeds across versions, McNemar's
  test on pass/fail flips, Benjamini Hochberg correction, minimum meaningful effect.
- **Optional LLM judge**, off by default, covering 2 subjective failure modes. Every finding
  is labelled "LLM-judged, unvalidated" and no kappa is reported.

## Results

Frozen 60 scenario set, offline scripted policies, sandboxed path, 2026-08-23.

| Agent | Injected defect | Composite |
|---|---|---|
| `clean` | none (control) | **100.0** |
| `confabulator` | answers from priors when a tool errors | **92.2** |
| `looper` | re-queries instead of concluding | **65.0** |
| `pushover` | complies with authority framing | **31.7** |

**Acceptance criterion: PASS, 6 of 6 checks.** Required ordering is
`clean > {looper, confabulator} > pushover`, with at least 70 percent of each defective
agent's findings attributed to its injected defect.

60 of 60 scenarios discriminate. Zero false positives on the control. 294 tests passing,
25 of 25 fixes revert verified.

## Prerequisites

- Python 3.11 or higher (measured on 3.11.9)
- Git
- No API key required; everything runs offline using scripted calibration policies
- Optional: `ANTHROPIC_API_KEY`, and `ANTHROPIC_BASE_URL` for a compatible gateway

Dependencies are pinned, not floated. A floating dependency has the same failure mode as a
floating model string: a fresh clone resolves a version the frozen numbers were never
measured against, and the difference is misattributed to the agent.

## Installation

```bash
git clone https://github.com/Graybeep/evaluation.git
cd evaluation
pip install -r requirements.txt
git config core.hooksPath .githooks    # enforces the frozen set rule
python -m pytest -q                    # expect 294 passed
```

On a fresh clone 3 tests skip, because they read run artifacts that do not exist yet.

Windows note: `python` often resolves in PowerShell but not in Git Bash. All commands below
use `python -m are.cli`, which needs nothing on PATH.

## Usage

### The acceptance check

```bash
python -m are.cli calibrate --scenarios frozen/frozen_scenarios.json --offline
```

Runs four agents over 60 scenarios and reports whether the ranking was recovered.

### Safety layers

```bash
python -m are.cli selftest
```

Reports the four sandbox layers, world isolation, our own injection payloads fired at our
own judge, and secret scrubbing. Checks that cannot run report SKIPPED, never a pass.

### Evaluate one agent

```bash
python -m are.cli run --agent pushover --scenarios frozen/frozen_scenarios.json
python -m are.cli report runs/pushover
```

Renders HTML with the full trace and the assertion that caught each failure.

### Regression comparison

```bash
python -m are.cli compare runs/v2 runs/v1 --ci
```

Gating is opt in. Without `--ci` every command exits 0, because a scorecard advises and a
human decides.

| exit | meaning | whose problem |
|---|---|---|
| `0` | no meaningful regression | nobody |
| `1` | regression detected | the **agent** |
| `2` | not reportable, invalid rate over ceiling | the **harness** |

**A job that treats exit 1 and exit 2 alike is misconfigured.** Exit 2 means the run failed
for our reasons, so it supports no claim about the agent in either direction.

```yaml
# .github/workflows/agent-reliability.yml
name: agent reliability
on: [pull_request]
jobs:
  evaluate:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - run: pip install -r requirements.txt
      - run: python -m are.cli run --agent clean --scenarios frozen/frozen_scenarios.json --offline --out runs/candidate
      - run: python -m are.cli compare runs/baseline runs/candidate --ci
        # exit 1 -> the agent regressed, block the PR
        # exit 2 -> the evaluation is unreportable, fix the harness first
```

### Audit the suite itself

```bash
python -m are.cli analyse
```

Detector co-firing, discrimination, false positives on the control, template concentration.

### Point your own agent at it

```bash
python -m are.cli mcp-serve --scenario-id <id> --out runs/my-agent
```

ARE becomes the MCP server and exposes the toolset over stdio. Agent-internal messages are
not observable over this transport, so token budgets are not enforceable; that is recorded
in `provenance.json` on every such run.

### Static site

```bash
python landing/build.py && python -m http.server 8080 --directory landing
```

Views over the same artifacts, never a second implementation, so they cannot disagree with
the CLI.

## Architecture

```
are/
  schema/     scenario, trace, verdict (pydantic, single source of truth)
  tools/      registry.yaml, risk tiers declared not inferred
  sim/        stateful world, fault injection
  gen/        templates, expansion, feasibility gate
  runner/     adapters, execution loop, limits, sandbox, MCP server
  verify/     rule detectors, judge, taxonomy
  score/      composite, statistics, regression
  report/     HTML rendering
frozen/       the benchmark set, git tracked, never regenerated
```

Every fix is revert verified: remove the fix, run the suite, confirm it goes red, restore.

```bash
python scripts/revert_check.py    # writes reports/revert_verified.json
```

Read the count from that artifact, not from this file. `CLAUDE.md` section 7.10 records why
this is mechanised rather than recommended: of 20 occasions where this project measured the
wrong thing, **14 were inside a check written to prevent exactly that bug**, and 9 were
found by running something rather than re-reading it.

## Limitations

1. **No online agent result exists.** The full suite was attempted on 2026-08-23 against a
   third party gateway: 25 percent invalid on 502 errors at preflight, 100 percent invalid
   on 429 rate limiting at full scale. Neither is reportable, and no composite from either
   appears in this repository. Every headline number here is offline behaviour.
2. **The judge is uncalibrated.** No human labelled agreement study was run. What was
   verified is narrower: 3 of 3 injection probes held on one endpoint, each with a flagged
   control so the pass could not be vacuous. That is resistance to attack, not agreement
   with human judgement.
3. **The 429 retry fix is not validated against a live rate limit.** Unit tested and revert
   verified, but no 429 was ever observed retrying and recovering.
4. **13 hand authored templates.** Coverage is bounded by template imagination, and the top
   3 templates are 50 percent of the suite.
5. **Single domain.** One internal operations console. Cross domain transfer is unvalidated.
6. **Mocked tools.** Timing, rate limits and real API error semantics are approximated.
7. **Absolute scores are not comparable across toolsets.** Only paired, same suite
   comparisons are meaningful.
8. **Text based checks are blunt.** The refusal lexicon measures 0.29 precision, 0.57
   recall. No published verdict rests on it alone.
9. **Network isolation is degraded online.** OS level egress deny is enforced only on the
   offline Docker path. With a live key `selftest --strict` exits 1 rather than skipping,
   because a layer you cannot demonstrate is not a layer you have.
10. **Flakiness is unmeasurable offline.** Scripted policies produce identical repeats, so
    the scorecard reports `flaky_measurable: false` rather than an empty list.
11. **Two detectors never fire on the frozen set.** A coverage gap in the scenario set, not
    a defect in the detectors. Both have revert verified controls outside the frozen set.
12. **One deliberately unfixed defect**, documented in
    `reports/KNOWN_DEFECT_refusal_string.md`, kept so the judge's catch stays reproducible.

Full evidence for each item is preserved in `README_FULL.md`.

## Contributing

1. Add a test that fails without your change.
2. Add a mutation to `scripts/revert_check.py` that removes your fix, and confirm the suite
   goes red. A fix without a mutation is not verified.
3. Run `python -m pytest -q` and `python scripts/revert_check.py` on a clean tree. Both
   refuse to run over uncommitted changes on purpose.
4. Do not regenerate `frozen/frozen_scenarios.json`. Tuning scenarios after seeing scores is
   the failure mode the frozen set exists to prevent.

## License

No license file is present. Until one is added, all rights are reserved by the author.
Please make contact before reuse.

## Contact

Repository: https://github.com/Graybeep/evaluation

Dual use notice: `are/probes/pressure_corpus.yaml` contains authority, urgency and
injection payloads, published deliberately for reproducibility of the regression result
(reasoning in `CLAUDE.md` section 7.4). Payload text appears only in that file; rendered
reports reference payloads by id and category, enforced by an assertion in
`report/render.py` that runs before any report is written.
