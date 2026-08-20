"""MCP adapter — serve one scenario's sandboxed toolset over the Model Context Protocol.

WHAT MCP IS, and why the adapter has this shape
-----------------------------------------------
MCP is JSON-RPC 2.0 (usually over stdio) by which a *host* — Claude Code, Claude Desktop,
someone's own agent — discovers and calls **tools** exposed by a *server*. Tools flow
server -> host; the host owns the model and the loop.

So "MCP adapter" has only one coherent direction here: ARE is already the tool provider
(§2, §4.1), therefore ARE is the **server** and the agent under test is the host that
connects to it. There is no useful "ARE as MCP client" — that would mean calling an agent
as if it were a tool, which is not what the protocol does.

WHAT THIS COSTS, STATED UP FRONT (§7.7)
---------------------------------------
An external host owns the loop, so the harness loses instrumentation it has in-process.
This is a real measurement degradation, so it is recorded on every run rather than
discovered later:

| §4.4 kill switch | in-harness | over MCP |
|---|---|---|
| max_tool_calls | enforced | **enforced** — every call comes through us |
| wall_clock_s   | enforced | **enforced** — timed from the first call |
| max_tokens     | enforced | **CANNOT BE ENFORCED** — token usage is between the host and its provider; we never see it |

The trace is partial too: we observe tool calls and results, never the agent's internal
messages. Assertion kinds that read the mutation log or final state (`no_call`,
`must_call`, `mutations_subset_of`, `state_equals`, `max_tool_calls`) stay fully
evaluable. Kinds decided partly by text over the final answer (`must_refuse`,
`must_request_clarification`) and both judge modes (§6.3) need the agent to report an
answer — hence the `submit_answer` tool below, which lets a cooperating host restore them.
If it is never called, those assertions are reported as unevaluable rather than silently
passing.

Runs produced this way carry `transport: mcp` provenance and an `@mcp` suffix on
`agent_version`, so their numbers are never pooled with in-harness runs invisibly.
"""
from __future__ import annotations

import json
import sys
import time
from typing import Any, Callable, TextIO

from are.runner.limits import Budget, LimitTripped
from are.schema.scenario import Scenario
from are.schema.trace import RunResult, Step
from are.sim.faults import FaultEngine
from are.sim.world import World
from are.tools.specs import all_specs
from are.util import scrub

PROTOCOL_VERSION = "2024-11-05"
SERVER_INFO = {"name": "are-sim", "version": "1"}

SUBMIT_ANSWER = "submit_answer"
SUBMIT_SPEC = {
    "name": SUBMIT_ANSWER,
    "description": ("Report your final answer to the user's task. Call this last. "
                    "Assertions about refusing or asking for clarification are evaluated "
                    "against this text; if you never call it they cannot be evaluated."),
    "inputSchema": {"type": "object",
                    "properties": {"text": {"type": "string"}},
                    "required": ["text"]},
}


def tool_schemas() -> list[dict]:
    """The sim's registry in MCP shape, plus submit_answer."""
    out = []
    for spec in all_specs():
        s = spec.anthropic_schema()
        out.append({"name": s["name"], "description": s["description"],
                    "inputSchema": s["input_schema"]})
    out.append(SUBMIT_SPEC)
    return out


class ScenarioServer:
    """One scenario, one World, one JSON-RPC session. Fresh World per session (§7.5)."""

    def __init__(self, scenario: Scenario, agent_label: str = "external",
                 limit_overrides: dict | None = None):
        self.scenario = scenario
        self.agent_label = agent_label
        self.faults = FaultEngine(faults=list(scenario.faults), seed=scenario.seed)
        self.world = World(scenario.world_state, seed=scenario.seed,
                           fault_engine=self.faults)
        self.budget = Budget.from_limits(limit_overrides)
        self.steps: list[Step] = []
        self.final_answer = ""
        self.answer_submitted = False
        self.limit_tripped: str | None = None
        self.harness_error: str | None = None
        self.started: float | None = None
        self._n = 0

    # ------------------------------------------------------------- recording
    def _next_id(self) -> int:
        self._n += 1
        return self._n

    def _record(self, **kw) -> Step:
        st = Step(step_id=self._next_id(), **kw)
        self.steps.append(st)
        return st

    # -------------------------------------------------------------- dispatch
    def handle(self, req: dict) -> dict | None:
        """Returns a JSON-RPC response, or None for a notification."""
        method = req.get("method")
        rid = req.get("id")
        if rid is None:                       # notification: nothing to answer
            return None
        try:
            if method == "initialize":
                return _ok(rid, {"protocolVersion": PROTOCOL_VERSION,
                                 "capabilities": {"tools": {}},
                                 "serverInfo": SERVER_INFO,
                                 "instructions": self.scenario.instruction})
            if method == "tools/list":
                return _ok(rid, {"tools": tool_schemas()})
            if method == "tools/call":
                return self._call(rid, req.get("params") or {})
            if method in ("ping", "shutdown"):
                return _ok(rid, {})
            return _err(rid, -32601, "method not found: " + str(method))
        except Exception as exc:              # a host must not be able to crash us
            self.harness_error = f"{type(exc).__name__}: {exc}"
            return _err(rid, -32603, self.harness_error)

    def _call(self, rid, params: dict) -> dict:
        name = params.get("name") or ""
        args = dict(params.get("arguments") or {})
        if self.started is None:
            # Clock the AGENT's session, not the time the server sat idle waiting for a
            # host to connect. Budget.started is set at construction, which for a stdio
            # server can be well before the first call arrives.
            self.started = time.monotonic()
            self.budget.started = self.started

        if name == SUBMIT_ANSWER:
            self.final_answer = str(args.get("text", ""))
            self.answer_submitted = True
            self._record(type="final_answer", text=self.final_answer)
            return _ok(rid, _content("recorded"))

        try:
            self.budget.charge_tool_call()      # checks the clock, then the depth
        except LimitTripped as trip:
            self.limit_tripped = trip.which
            self._record(type="limit_trip", text=str(trip), meta={"which": trip.which})
            return _ok(rid, _content("HARNESS LIMIT REACHED: " + str(trip), is_error=True))

        st = self._record(type="tool_call", tool=name, args=scrub(dict(args)))
        result = self.world.call(name, args, step_id=st.step_id)
        self._record(type="tool_result", tool=name, ok=result.ok,
                     data=scrub(result.data), error=result.error)
        return _ok(rid, _content(result.render(), is_error=not result.ok))

    # --------------------------------------------------------------- outcome
    def to_run_result(self, repeat_idx: int = 0) -> RunResult:
        elapsed = 0.0 if self.started is None else time.monotonic() - self.started
        version = f"{self.agent_label}@mcp"
        return RunResult(
            run_id=f"{self.scenario.id}|{version}|mcp-host|s{self.scenario.seed}|r{repeat_idx}",
            scenario_id=self.scenario.id,
            repeat_idx=repeat_idx,
            agent_version=version,
            model_version="mcp-host (model unknown to harness)",
            seed=self.scenario.seed,
            steps=self.steps,
            mutation_log=self.world.mutation_log,
            final_state=self.world.snapshot(),
            final_answer=self.final_answer,
            limit_tripped=self.limit_tripped,
            harness_error=self.harness_error,
            tokens_used=0,                    # unobservable over MCP; never guessed
            wall_clock_s=round(elapsed, 3),
            tool_call_count=self.budget.tool_calls,
            cache_mode="off",
        )

    def provenance(self) -> dict:
        """Written beside the run so its limits are never inferred from an ordinary one."""
        return {
            "transport": "mcp",
            "budgets_enforced": ["max_tool_calls", "wall_clock_s"],
            "budgets_unenforceable": ["max_tokens"],
            "token_accounting": "unavailable - the host owns the model",
            "final_answer_submitted": self.answer_submitted,
            "text_assertions_evaluable": self.answer_submitted,
            "note": ("Trace is tool-level only; agent-internal messages are not "
                     "observable. Do not pool with in-harness runs (§11.5)."),
        }


# ------------------------------------------------------------- JSON-RPC glue
def _ok(rid, result) -> dict:
    return {"jsonrpc": "2.0", "id": rid, "result": result}


def _err(rid, code, message) -> dict:
    return {"jsonrpc": "2.0", "id": rid, "error": {"code": code, "message": message}}


def _content(text: str, is_error: bool = False) -> dict:
    return {"content": [{"type": "text", "text": text}], "isError": is_error}


def serve(scenario: Scenario, stdin: TextIO | None = None, stdout: TextIO | None = None,
          agent_label: str = "external", limit_overrides: dict | None = None,
          on_close: Callable[[ScenarioServer], Any] | None = None) -> ScenarioServer:
    """Blocking line-delimited JSON-RPC loop. Returns the session when stdin closes."""
    stdin = stdin or sys.stdin
    stdout = stdout or sys.stdout
    session = ScenarioServer(scenario, agent_label=agent_label,
                             limit_overrides=limit_overrides)
    for line in stdin:
        line = line.strip()
        if not line:
            continue
        try:
            req = json.loads(line)
        except json.JSONDecodeError:
            stdout.write(json.dumps(_err(None, -32700, "parse error")) + "\n")
            stdout.flush()
            continue
        resp = session.handle(req)
        if resp is not None:
            stdout.write(json.dumps(resp, default=str) + "\n")
            stdout.flush()
    if on_close:
        on_close(session)
    return session
