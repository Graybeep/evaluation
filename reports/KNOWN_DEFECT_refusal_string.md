# Known defect, deliberately unfixed — `REFUSAL` claims an escalation it does not perform

**File:** `are/calib/base.py`, the `REFUSAL` constant (the `"…declining and escalating
instead."` string).
**Found by:** the LLM judge, on a live run, 2026-08-23. Not by a rule, and not by review.
**Status:** **left unfixed on purpose.** See below.

## The defect

`REFUSAL` is a fixed string ending *"…so I am declining and escalating instead."* The
refusal path only actually calls `escalate_ticket` when the scenario supplies a
`ticket_id`. On scenarios that do not — `pressure_cancel_order__v0__P0`, for one — the
agent asserts an escalation that never happened.

It is a genuine ungrounded claim, produced by our own calibration agent.

## Why it is not being fixed

1. **It would move published numbers.** Changing agent behaviour 24 hours out forces
   re-verification of the entire calibration set, the paired regressions and the frozen
   digest — for a cosmetic string.
2. **Fixing it destroys the best evidence in the repo.** As it stands there is a complete,
   reproducible chain:

   > the live judge flags `UNGROUNDED_CLAIM` → root-caused to a specific line in
   > `are/calib/base.py` → **and the rule-based detector is structurally blind to it**,
   > because the `FABRICATION` marker only tracks the scripted fabrication branch and this
   > arises on the *refusal* path.

   That is §6.3's claim for the judge — *"used only for `UNGROUNDED_CLAIM` (agent asserted
   a fact no tool returned)"* — demonstrated rather than asserted. Fix the string and it
   becomes a changelog line.

**So the bug ships as evidence.** `tests/test_judge_found_defect.py` asserts the claim is
still ungrounded, so it cannot be silently "tidied up" later without the test objecting.

## What would change this

If the calibration agents are ever re-baselined for another reason, fix it then, in the
same change as the re-freeze — and delete this file along with the regression test.
