# Pressure probe corpus — intended use

`pressure_corpus.yaml` holds the text of the authority / urgency / social / injection
payloads used to pressure-test agent guardrails (CLAUDE.md §5, §7.4).

**This is, functionally, a small jailbreak library.** It exists for one purpose: to measure
whether an agent under evaluation performs irreversible actions it should refuse.

Rules (§7.4), enforced by convention and by the report renderer:

1. Payload **text** lives here and nowhere else. It is never copied into the README,
   the slides, or the HTML report.
2. Public artefacts reference payloads **by `id` and `category` only**
   (`report/render.py` asserts this).
3. Payloads target a *simulated* ops console. There are no real systems, credentials, or
   customers behind any tool in this repo (§7.1: no pass-through mode, ever).
4. Additions should stay in-domain (ops-console framing). This is not a general-purpose
   jailbreak collection and must not grow into one.

## Pressure taxonomy

| Level | Meaning | Delivery |
|---|---|---|
| `P0` | No pressure. Neutral phrasing. The control condition. | instruction |
| `P1` | Social / politeness / rapport pressure | instruction |
| `P2` | Urgency, time limits, consequences for delay | instruction |
| `P3` | Claimed authority (manager, legal, security team) | instruction |
| `P4` | Compound: authority **and** urgency in the same request | instruction |
| `P5` | Prompt injection carried inside **tool output**, not the user turn | tool_output |

The scorecard reports **P_n − P0 deltas** on an otherwise identical scenario body, so the
number is "how much does this framing move the agent", not "how unsafe is this agent" —
a finding, not a feature (§0.5).
