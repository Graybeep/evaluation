# Agent Reliability Engine (ARE)

A property-based testing framework for LLM agents. It does not use one model to grade
another. Every scenario ships with machine-checkable assertions written alongside it, so a
verdict is computed from the execution trace and the final world state, deterministically.

```
Scenario = (initial_world_state, instruction, assertions[], pressure_tags[])
Verdict  = evaluate(assertions, trace, final_state)  ->  PASS | FAIL | INVALID
```

Built for anyone who needs to answer "which tasks does my agent fail, and how badly" with
a number they can defend.

## Table of Contents

- [Features](#features)
- [Results](#results)
- [Prerequisites](#prerequisites)
- [Installation](#installation)
- [Usage](#usage)
- [How This Is Verified](#how-this-is-verified)
- [Limitations](#limitations)
- [Contributing](#contributing)
- [License](#license)
- [Contact](#contact)

## Features

- **Deterministic verdicts, not model opinions.** 11 rule based detectors read the trace,
  the mutation log and the final state. An LLM judge exists for 2 subjective failure modes
  only, is off by default, and every finding it produces is labelled "LLM-judged,
  unvalidated".
- **Assertions ship with the scenario.** The brief asks for scenario generation; this
  generates the oracle at the same time, which is what makes a verdict checkable.
- **Three way outcomes.** PASS, FAIL, and INVALID. Harness faults and provider errors are
  never charged to the agent. `invalid_rate` is a first class metric, and a run above 5
  percent is declared not reportable.
- **Calibration agents with known defects.** Four agents, three deliberately broken. The
  platform is never told which. If it cannot recover the ranking, its numbers are noise.
- **Sandboxed execution, four layers.** Tool mocking with no pass through, process and
  filesystem isolation, network allowlisting, and independent resource budgets.
- **Point your own agent at it over MCP.** ARE runs as an MCP server and exposes the
  toolset. Your agent brings its own model and key. ARE makes no LLM calls in this mode.
- **Paired regression tracking.** Identical scenarios and seeds across versions, McNemar's
  test on pass/fail flips, Benjamini Hochberg correction, and a minimum meaningful effect.
- **Mechanised self checking.** Every shipped fix is revert verified: remove the fix,
  confirm the suite goes red, restore. A test that passes without its fix is not evidence.

## Results

Measured on the frozen 60 scenario set, offline scripted policies, sandboxed path,
2026-08-23.

| Agent | Injected defect | Composite |
|---|---|---|
| `clean` | none (control) | **100.0** |
| `confabulator` | answers from priors when a tool errors | **92.2** |
| `looper` | re-queries instead of concluding | **65.0** |
| `pushover` | complies with authority framing | **31.7** |

Acceptance criterion: **PASS, 6 of 6 checks.** The required ordering is
`clean > {looper, confabulator} > pushover`, with at least 70 percent of each defective
agent's findings attributed to its injected defect.

Other measured properties: 60 of 60 scenarios discriminate between a good and a bad agent,
zero false positives on the control, 13 templates expanding to 60 scenarios, 294 tests
passing, and 25 of 25 fixes revert verified.

## Prerequisites

- Python 3.11 or higher (measured on 3.11.9)
- Git
- No API key required. Everything below runs offline using scripted calibration policies.
- Optional: an Anthropic API key, or a compatible gateway, to run agents against a live
  model. Set `ANTHROPIC_API_KEY` and optionally `ANTHROPIC_BASE_URL`.

Dependencies are pinned rather than floated, because a floating dependency produces the
same failure mode as a floating model string: a fresh clone resolves a version the frozen
numbers were never measured against, and the difference is misattributed to the agent.

## Installation

1. Clone the repository:
   ```bash
   git clone https://github.com/Graybeep/evaluation.git
   cd evaluation
   ```

2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

3. Enable the repository hooks, which enforce the frozen scenario set rule:
   ```bash
   git config core.hooksPath .githooks
   ```

4. Verify the installation:
   ```bash
   python -m pytest -q
   ```
   Expect 294 passing. On a fresh clone 3 tests skip, because they read run artifacts that
   do not exist yet. Those are not the correctness claims.

Windows note: `python` often resolves in PowerShell but not in Git Bash. Use
`PYTHON=python3 bash demo.sh` to force an interpreter. The commands below use
`python -m are.cli`, which needs nothing on PATH.

## Usage

### Run the acceptance check

The single command that demonstrates the platform measures anything at all:

```bash
python -m are.cli calibrate --scenarios frozen/frozen_scenarios.json --offline
```

Four agents, 60 scenarios, ranking recovered without being told which agent is defective.

### Check the safety layers

```bash
python -m are.cli selftest
```

Reports the four sandbox layers, world isolation, our own injection payloads fired at our
own judge, and secret scrubbing. Checks that cannot run report SKIPPED rather than passing.

### Evaluate one agent and render a report

```bash
python -m are.cli run --agent pushover --scenarios frozen/frozen_scenarios.json
python -m are.cli report runs/pushover
```

Opens as HTML with the full trace, the tool calls, and the assertion that caught each
failure.

### Compare two versions for regressions

```bash
python -m are.cli compare runs/v2 runs/v1 --ci
```

Gating is opt in. Without `--ci` every command exits 0, because a scorecard should advise
and a human should decide. With `--ci` the codes keep the three way distinction rather than
collapsing to pass/fail:

| exit | meaning | whose problem |
|---|---|---|
| `0` | no meaningful regression | nobody |
| `1` | regression detected | the **agent** |
| `2` | not reportable, invalid rate over the 5 percent ceiling | the **harness**, never an agent finding |

**A job that treats exit 1 and exit 2 alike is misconfigured.** Exit 2 means the run failed
for our reasons, so it supports no claim about the agent in either direction. Blaming a
developer's agent for our outage is the failure this project keeps finding, and the codes
exist so CI cannot do it by accident.

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
      - name: Score the candidate against the frozen set
        run: python -m are.cli run --agent clean --scenarios frozen/frozen_scenarios.json --offline --out runs/candidate
      - name: Fail the build on a regression, but not on our own bad data
        run: python -m are.cli compare runs/baseline runs/candidate --ci
        # exit 1 -> the agent regressed, block the PR
        # exit 2 -> the evaluation itself is unreportable, fix the harness first
      - uses: actions/upload-artifact@v4
        if: always()
        with: { name: comparison, path: runs/candidate/comparison.json }
```

### Audit the test suite itself

```bash
python -m are.cli analyse
```

Reports detector co-firing, discrimination, false positives on the control, and template
concentration.

### Point your own agent at it over MCP

```bash
python -m are.cli mcp-serve --scenario-id <id> --out runs/my-agent
```

ARE becomes the MCP server and exposes the toolset over stdio. Your agent is the host and
brings its own model. Verified end to end with no API key present. The harness cannot
observe agent-internal messages over this transport, so token budgets are not enforceable,
and that is recorded in `provenance.json` on every such run.

### Build the static site

```bash
python landing/build.py
python -m http.server 8080 --directory landing
```

A homepage, an MCP walkthrough, and a plain language report card. These are views over the
same artifacts, never a second implementation, so they cannot disagree with the CLI.

## How This Is Verified

Every fix in this repository is revert verified. The fix is removed, the suite is run, the
failure is recorded, and the fix is restored. A test that stays green with its subject
removed is not evidence.

```bash
python scripts/revert_check.py
```

This writes `reports/revert_verified.json`. Read the number from that artifact, not from
this file.

The reason it is mechanised rather than recommended: `CLAUDE.md` section 7.10 logs 20
occasions where this project measured the wrong thing. **Fourteen of those twenty were
inside a check written to prevent exactly that bug.** Nine were found by running something
rather than by re-reading it. The recurring error was never a subsystem. It was one
reasoning mistake about what a passing check proves, and it is self camouflaging enough to
survive inside its own guard.

## Limitations

Stated plainly, because naming the weaknesses first is worth more than an extra feature.

1. **No online agent result exists.** The full suite was attempted on 2026-08-23 against a
   third party gateway. Preflight returned 25 percent invalid on 502 errors; the full run
   returned 100 percent invalid on 429 rate limiting. Against the 5 percent ceiling neither
   is reportable, and no composite from either appears anywhere in this repository. Every
   headline number here is offline scripted policy behaviour.
2. **The LLM judge is uncalibrated.** No human labelled agreement study was run, and
   therefore no kappa is reported. `cohens_kappa` exists and raises by default rather than returning a
   number no human labelled. Judge findings are advisory and labelled everywhere they
   appear. What was verified is narrower: 3 of 3 injection probes held on one endpoint,
   each with a flagged control so the pass could not be vacuous. That is resistance to
   attack, not agreement with human judgement.
3. **The 429 retry fix is not validated against a live rate limit.** It is unit tested
   across both branches and revert verified, but no 429 was ever observed retrying and
   recovering. Absence of a rate limit is not evidence the rate limit path works.
4. **Scenarios come from 13 hand authored templates.** Coverage is bounded by template
   imagination, not by the real failure distribution. The top 3 templates are 50 percent of
   the suite.
5. **Single domain.** One internal operations console. Cross domain transfer is unvalidated.
6. **Mocked tools.** Timing, rate limits and real API error semantics are approximated.
7. **Absolute scores are not comparable across agents on different toolsets.** Only paired,
   same suite comparisons are meaningful.
8. **Text based checks are blunt.** The refusal lexicon measures at 0.29 precision and 0.57
   recall. No published verdict rests on it alone.
9. **Network isolation is degraded on online runs.** OS level egress deny is enforced only
   on the offline Docker path. With a live key, `selftest --strict` exits 1 rather than
   skipping the check, because a layer you cannot demonstrate is not a layer you have.
10. **Flakiness is unmeasurable offline.** Scripted policies produce byte identical repeats.
    The scorecard reports `flaky_measurable: false` rather than an empty list that would
    read as "none found".
11. **Two detectors never fire on the frozen set.** That is a coverage gap in the scenario
    set, not a defect in the detectors. Both have revert verified positive controls outside
    the frozen set, and the coverage gap is still reported as zero.
12. **One deliberately unfixed defect.** A refusal string in `are/calib/base.py` overstates
    what the agent did. It is left in place so the judge's catch stays reproducible, and it
    is documented in `reports/KNOWN_DEFECT_refusal_string.md`.

The full limitations text, with the evidence behind each item, is preserved in
`README_FULL.md`.

## Contributing

1. Fork the repository and create a branch.
2. Add a test that fails without your change.
3. Add a mutation to `scripts/revert_check.py` that removes your fix, and confirm the suite
   goes red. A fix without a mutation is not verified, and the artifact count will say so.
4. Run `python -m pytest -q` and `python scripts/revert_check.py` on a clean tree. Both
   refuse to run over uncommitted changes on purpose.
5. Do not regenerate `frozen/frozen_scenarios.json`. Tuning scenarios after seeing scores is
   the failure mode the frozen set exists to prevent.

## License

No license file is currently present in this repository. Until one is added, all rights are
reserved by the author. Please make contact before reuse.

## Contact

Repository: https://github.com/Graybeep/evaluation

Dual use notice: `are/probes/pressure_corpus.yaml` contains authority, urgency and
injection payloads. It is published deliberately, for reproducibility of the regression
result, and the reasoning is recorded in `CLAUDE.md` section 7.4. Payload text appears only
in that file. Rendered reports reference payloads by id and category, enforced by an
assertion in `report/render.py` that runs before any report is written.
