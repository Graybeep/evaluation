"""The sandbox — four containment layers (CLAUDE.md §7.9).

| Layer | Mechanism | Defends against |
|---|---|---|
| L1 | Tool mocking — no tool implementation touches a real system, no pass-through mode | all real-world side effects (the primary boundary) |
| L2 | Subprocess with a scratch tempdir as cwd | stray file writes, log pollution, cross-run bleed |
| L3 | Egress deny-by-default, allowlist = the LLM API host only | exfiltration, an agent "helpfully" calling a real API |
| L4 | Resource budgets, independently enforced; parent kills the child | runaway loops, cost blowups, a hung run during a live demo |

**Honest scoping of L3.** The guard here is enforced inside the child's Python runtime
(`socket.getaddrinfo` / `socket.connect`), not by the OS. That stops accidental egress and
any egress that goes through Python's socket module — which is all of it, since the agent
can only call functions we wrote. It does **not** stop a native extension that opens a
socket by syscall.

The OS-level form ships as `docker compose run offline`, which sets `network_mode: none` —
a deny-all no Python code can talk its way out of, and the configuration to use if you
ever point this at an agent whose code you do not control. The remaining gap, stated
plainly rather than papered over: an *online* run needs egress to the LLM API, and the
full answer there is a parent-process proxy over a unix socket with the container still on
`network_mode: none`. That proxy is **not implemented**; online runs fall back to the
in-process allowlist below. What is not claimed anywhere is hypervisor isolation (§0).

L1 is doing ~90% of the work. Saying so is better than faking VM isolation.
"""
from __future__ import annotations

import multiprocessing as mp
import os
import socket
import tempfile
import time
from queue import Empty as _QueueEmpty
from pathlib import Path

from are.runner.limits import LIMITS, SANDBOX_CAPS
from are.schema.scenario import Scenario
from are.schema.trace import RunResult, Step

def _configured_llm_host() -> set[str]:
    """Honour ANTHROPIC_BASE_URL so a gateway can be used — but widen the allowlist
    EXPLICITLY and visibly, never by quietly disabling the guard. `sandbox_status()`
    reports the widened list, so a report always shows where traffic was allowed to go."""
    import os
    from urllib.parse import urlparse

    base = os.environ.get("ANTHROPIC_BASE_URL", "").strip()
    host = urlparse(base).hostname if base else None
    return {host} if host else set()


ALLOWED_HOSTS = ({"api.anthropic.com", "localhost", "127.0.0.1", "::1"}
                 | _configured_llm_host())

NETWORK_MODULES = ("requests", "httpx", "urllib.request", "urllib3", "socket", "aiohttp")


class EgressBlocked(RuntimeError):
    pass


# ------------------------------------------------------------------- L1 check
def assert_l1_mocked() -> None:
    """Every registered tool resolves to a World method, and World imports no network lib.

    L1 is the layer everything else leans on, so it is asserted rather than assumed. This
    runs in `cli.py selftest` and in the test suite.
    """
    import inspect

    from are.sim import world as world_mod
    from are.tools.specs import load_registry

    for name in load_registry():
        impl = getattr(world_mod.World, f"_t_{name}", None)
        if impl is None:
            raise AssertionError(f"tool '{name}' has no World implementation — L1 breach risk")

    src = inspect.getsource(world_mod)
    for mod in ("requests", "httpx", "urllib", "aiohttp", "socket"):
        if f"import {mod}" in src:
            raise AssertionError(
                f"sim.world imports '{mod}': the mock layer must have no network path (§7.1)")
    if "pass_through" in src or "passthrough" in src:
        raise AssertionError("sim.world mentions a pass-through mode — there is no escape hatch (§7.1)")


# ------------------------------------------------------------------- L3 guard
def install_egress_guard(allowed: set[str] | None = None) -> None:
    """Deny-by-default egress inside this process. Idempotent."""
    allowed = allowed or ALLOWED_HOSTS
    if getattr(socket, "_are_guard_installed", False):
        return

    real_getaddrinfo = socket.getaddrinfo
    allowed_ips: set[str] = {"127.0.0.1", "::1"}

    def guarded_getaddrinfo(host, port, *a, **kw):
        if host not in allowed and str(host) not in allowed:
            raise EgressBlocked(
                f"egress denied to {host!r}: allowlist is {sorted(allowed)} (§7.3, §7.9 L3)")
        infos = real_getaddrinfo(host, port, *a, **kw)
        for info in infos:
            addr = info[4]
            if addr and isinstance(addr[0], str):
                allowed_ips.add(addr[0])
        return infos

    real_connect = socket.socket.connect

    def guarded_connect(self, address, *a, **kw):
        host = address[0] if isinstance(address, tuple) else address
        if isinstance(host, str) and host not in allowed_ips and host not in allowed:
            raise EgressBlocked(f"egress denied to {host!r} (§7.3, §7.9 L3)")
        return real_connect(self, address, *a, **kw)

    socket.getaddrinfo = guarded_getaddrinfo
    socket.socket.connect = guarded_connect
    socket._are_guard_installed = True


# ------------------------------------------------------- L2 + L4: child process
def _child(queue, scenario_json: str, agent: str, repeat_idx: int, cache_mode: str,
           offline: bool, scratch: str, guard_network: bool,
           limit_overrides: dict | None = None):
    try:
        os.chdir(scratch)                       # L2: scratch tempdir as cwd
        if guard_network:
            install_egress_guard()              # L3
        from are.runner.loop import execute_run
        scenario = Scenario.model_validate_json(scenario_json)
        result = execute_run(scenario, agent, repeat_idx=repeat_idx,
                             cache_mode=cache_mode, offline=offline,
                             limit_overrides=limit_overrides)
        queue.put(("ok", result.model_dump_json()))
    except Exception as exc:                    # harness fault -> INVALID upstream
        queue.put(("error", f"{type(exc).__name__}: {exc}"))


def run_sandboxed(scenario: Scenario, agent: str, repeat_idx: int = 0,
                  cache_mode: str = "off", offline: bool = False,
                  guard_network: bool = True, timeout_s: float | None = None,
                  limit_overrides: dict | None = None) -> RunResult:
    """Run one scenario in a child process. Falls back in-process if spawn is unavailable."""
    # The outer cap is a BACKSTOP for inner-enforcement failure, not a second budget:
    # `limits.py` says "if the inner limit is doing its job the outer one never fires, so
    # an outer trip means the inner enforcement itself failed", and `_killed()` therefore
    # routes an outer trip to INVALID as a harness finding.
    #
    # A fixed 120s outer breaks that the moment the inner limit is raised — `--wall-clock`
    # overrides the inner one only, so an online run with `--wall-clock 240` would have the
    # OUTER cap firing first on every slow-but-legal run, and each would be recorded as a
    # harness fault rather than the agent's behaviour. The backstop must stay above the
    # thing it backs up, so it is derived rather than hardcoded.
    inner = float((limit_overrides or {}).get("wall_clock_s", LIMITS["wall_clock_s"]))
    timeout = timeout_s or max(float(SANDBOX_CAPS["wall_clock_s"]), inner * 1.5 + 30.0)
    try:
        ctx = mp.get_context("spawn")
        queue = ctx.Queue()
    except Exception:
        return _inprocess(scenario, agent, repeat_idx, cache_mode, offline,
                          "multiprocessing unavailable", limit_overrides)

    with tempfile.TemporaryDirectory(prefix="are-run-") as scratch:
        proc = ctx.Process(target=_child,
                           args=(queue, scenario.model_dump_json(), agent, repeat_idx,
                                 cache_mode, offline, scratch, guard_network,
                                 limit_overrides))
        proc.start()

        # DRAIN BEFORE JOIN. A child that has put a payload on an mp.Queue does not
        # exit until the feeder thread has flushed it into the pipe. Joining first
        # means nobody is reading, so any payload past the pipe buffer blocks the
        # child at exit until the outer kill switch fires.
        #
        # That is what made a 25-call `looper` run report as a 120s wall-clock trip
        # with ZERO tool calls: a harness deadlock wearing an agent's failure mode.
        # `clean` (~2KB of trace) fit in the buffer and was fine, which is why this
        # survived every run of the smaller agents.
        status = payload = None
        deadline = time.monotonic() + timeout
        while True:
            try:
                status, payload = queue.get(timeout=0.2)
                break
            except _QueueEmpty:
                if time.monotonic() >= deadline:
                    break
                if not proc.is_alive():
                    try:                        # exited; one last non-blocking look
                        status, payload = queue.get_nowait()
                    except _QueueEmpty:
                        pass
                    break
        overran = status is None and time.monotonic() >= deadline
        if proc.is_alive():                     # L4: outer kill switch
            proc.terminate()
        proc.join(5)
        if status is None:
            if overran:
                return _killed(scenario, agent, repeat_idx, timeout)
            return _invalid(scenario, agent, repeat_idx,
                            f"sandbox child produced no result (exit {proc.exitcode})")
    if status == "ok":
        return RunResult.model_validate_json(payload)
    return _invalid(scenario, agent, repeat_idx, f"sandbox child error: {payload}")


def _inprocess(scenario, agent, repeat_idx, cache_mode, offline, why,
               limit_overrides=None) -> RunResult:
    from are.runner.loop import execute_run
    res = execute_run(scenario, agent, repeat_idx=repeat_idx, cache_mode=cache_mode,
                      offline=offline, limit_overrides=limit_overrides)
    res.steps.append(Step(step_id=len(res.steps) + 1, type="run_end",
                          meta={"sandbox": f"L2 skipped ({why}) — ran in-process"}))
    return res


def _skeleton(scenario: Scenario, agent: str, repeat_idx: int, **kw) -> RunResult:
    return RunResult(run_id=f"{scenario.id}|{agent}|sandbox|r{repeat_idx}",
                     scenario_id=scenario.id, repeat_idx=repeat_idx,
                     agent_version=agent, model_version="unknown", seed=scenario.seed,
                     steps=[], mutation_log=[], final_state={}, **kw)


def _killed(scenario, agent, repeat_idx, timeout) -> RunResult:
    """The OUTER kill switch fired — which is a harness finding, not an agent one.

    §4.4 makes a kill-switch trip a first-class failure mode rather than INVALID, and
    that is right **for the inner switches**: `limits.LIMITS` caps the agent at 90s and
    25 calls, and tripping one is the agent's behaviour.

    This is the outer cap (120s), and `limits.py` already says what reaching it means:
    *"if the inner limit is doing its job the outer one never fires, so an outer trip
    means the inner enforcement itself failed."* That is a statement about the harness.

    It used to return a skeleton with `harness_error=None`, so it scored as a clean
    agent `TIMEOUT` — `invalid_rate 0.0%`, `reportable: True`. A queue deadlock in
    `run_sandboxed` therefore rendered as "the agent hung", identically to a real hang,
    on a run where the agent made **zero tool calls**. That is §13.5 (INVALID counted as
    FAIL) reached from the opposite direction, and §7.10's rule applies: the two states
    must not render the same. They no longer do."""
    r = _skeleton(scenario, agent, repeat_idx, limit_tripped="wall_clock_s",
                  wall_clock_s=timeout,
                  harness_error=(f"outer sandbox cap ({timeout}s) killed the child before it "
                                 f"reported. The inner kill switches (limits.LIMITS) did not "
                                 f"fire, so this run observed NOTHING about the agent and "
                                 f"must not be scored as its behaviour (§4.4, §6.1)."))
    r.steps.append(Step(step_id=1, type="limit_trip",
                        text=f"sandbox killed the child after {timeout}s (§7.9 L4)",
                        meta={"which": "wall_clock_s", "tier": "outer",
                              "observed_agent_behaviour": False}))
    return r


def _invalid(scenario, agent, repeat_idx, reason) -> RunResult:
    r = _skeleton(scenario, agent, repeat_idx, harness_error=reason)
    r.steps.append(Step(step_id=1, type="harness_error", text=reason))
    return r


def l3_state(guard_network: bool = True) -> tuple[str, bool]:
    """(description, is_os_enforced). L3 is only OS-enforced on the offline path.

    The distinction matters enough to be a return value rather than prose: an *online* run
    needs egress to the LLM API, so `network_mode: none` is off and all that remains is the
    Python-level allowlist below — which is a control, not containment. The parent-process
    unix-socket proxy that would give online runs OS-level deny is not implemented, so
    online runs ship **L1 + L2 + L4**, which is exactly the fallback ladder §7.9 allows.
    """
    from are.runner.llm import api_key_present

    if not guard_network:
        return "OFF (--no-network-guard)", False
    online = api_key_present()
    if online:
        return ("DEGRADED — online run: OS-level deny is off (egress to the LLM API is "
                "required) and the unix-socket proxy is not implemented. "
                "Process-level allowlist only: " + ", ".join(sorted(ALLOWED_HOSTS))
                + ". Shipping L1+L2+L4 (§7.9 fallback ladder)."), False
    if in_container():
        return ("ON (OS-level) — offline container run; `network_mode: none` denies all "
                "egress. Process-level allowlist also active."), True
    return ("PARTIAL — offline host run: process-level allowlist only ("
            + ", ".join(sorted(ALLOWED_HOSTS))
            + "). Use `docker compose run offline` for OS-level deny."), False


def sandbox_status(guard_network: bool = True) -> dict:
    """What is actually switched on right now. Printed by `cli.py selftest`."""
    try:
        assert_l1_mocked()
        l1 = "ON — all tools are World methods, no network path, no pass-through"
    except AssertionError as exc:
        l1 = f"BREACH — {exc}"
    l3, _ = l3_state(guard_network)
    return {
        "L1_tool_mocking": l1,
        "L2_process_fs": "ON — child process, scratch tempdir as cwd",
        "L3_network": l3,
        "L4_budgets": f"ON — {SANDBOX_CAPS} enforced by the parent (inner limits in limits.LIMITS)",
        "not_claimed": "hypervisor / microVM isolation (§0 — deliberately out of scope)",
    }


def in_container() -> bool:
    return Path("/.dockerenv").exists() or os.environ.get("ARE_IN_CONTAINER") == "1"
