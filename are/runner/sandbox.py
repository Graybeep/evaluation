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
from pathlib import Path

from are.runner.limits import SANDBOX_CAPS
from are.schema.scenario import Scenario
from are.schema.trace import RunResult, Step

ALLOWED_HOSTS = {"api.anthropic.com", "localhost", "127.0.0.1", "::1"}

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
           offline: bool, scratch: str, guard_network: bool):
    try:
        os.chdir(scratch)                       # L2: scratch tempdir as cwd
        if guard_network:
            install_egress_guard()              # L3
        from are.runner.loop import execute_run
        scenario = Scenario.model_validate_json(scenario_json)
        result = execute_run(scenario, agent, repeat_idx=repeat_idx,
                             cache_mode=cache_mode, offline=offline)
        queue.put(("ok", result.model_dump_json()))
    except Exception as exc:                    # harness fault -> INVALID upstream
        queue.put(("error", f"{type(exc).__name__}: {exc}"))


def run_sandboxed(scenario: Scenario, agent: str, repeat_idx: int = 0,
                  cache_mode: str = "off", offline: bool = False,
                  guard_network: bool = True, timeout_s: float | None = None) -> RunResult:
    """Run one scenario in a child process. Falls back in-process if spawn is unavailable."""
    timeout = timeout_s or float(SANDBOX_CAPS["wall_clock_s"])
    try:
        ctx = mp.get_context("spawn")
        queue = ctx.Queue()
    except Exception:
        return _inprocess(scenario, agent, repeat_idx, cache_mode, offline,
                          "multiprocessing unavailable")

    with tempfile.TemporaryDirectory(prefix="are-run-") as scratch:
        proc = ctx.Process(target=_child,
                           args=(queue, scenario.model_dump_json(), agent, repeat_idx,
                                 cache_mode, offline, scratch, guard_network))
        proc.start()
        proc.join(timeout)
        if proc.is_alive():                     # L4: outer kill switch
            proc.terminate()
            proc.join(5)
            return _killed(scenario, agent, repeat_idx, timeout)
        try:
            status, payload = queue.get_nowait()
        except Exception:
            return _invalid(scenario, agent, repeat_idx,
                            f"sandbox child produced no result (exit {proc.exitcode})")
    if status == "ok":
        return RunResult.model_validate_json(payload)
    return _invalid(scenario, agent, repeat_idx, f"sandbox child error: {payload}")


def _inprocess(scenario, agent, repeat_idx, cache_mode, offline, why) -> RunResult:
    from are.runner.loop import execute_run
    res = execute_run(scenario, agent, repeat_idx=repeat_idx, cache_mode=cache_mode,
                      offline=offline)
    res.steps.append(Step(step_id=len(res.steps) + 1, type="run_end",
                          meta={"sandbox": f"L2 skipped ({why}) — ran in-process"}))
    return res


def _skeleton(scenario: Scenario, agent: str, repeat_idx: int, **kw) -> RunResult:
    return RunResult(run_id=f"{scenario.id}|{agent}|sandbox|r{repeat_idx}",
                     scenario_id=scenario.id, repeat_idx=repeat_idx,
                     agent_version=agent, model_version="unknown", seed=scenario.seed,
                     steps=[], mutation_log=[], final_state={}, **kw)


def _killed(scenario, agent, repeat_idx, timeout) -> RunResult:
    # A kill-switch trip is a first-class failure mode, not INVALID (§4.4)
    r = _skeleton(scenario, agent, repeat_idx, limit_tripped="wall_clock_s",
                  wall_clock_s=timeout)
    r.steps.append(Step(step_id=1, type="limit_trip",
                        text=f"sandbox killed the child after {timeout}s (§7.9 L4)",
                        meta={"which": "wall_clock_s"}))
    return r


def _invalid(scenario, agent, repeat_idx, reason) -> RunResult:
    r = _skeleton(scenario, agent, repeat_idx, harness_error=reason)
    r.steps.append(Step(step_id=1, type="harness_error", text=reason))
    return r


def sandbox_status(guard_network: bool = True) -> dict:
    """What is actually switched on right now. Printed by `cli.py selftest`."""
    try:
        assert_l1_mocked()
        l1 = "ON — all tools are World methods, no network path, no pass-through"
    except AssertionError as exc:
        l1 = f"BREACH — {exc}"
    return {
        "L1_tool_mocking": l1,
        "L2_process_fs": "ON — child process, scratch tempdir as cwd",
        "L3_network": ("ON (process-level guard; allowlist: "
                       + ", ".join(sorted(ALLOWED_HOSTS)) + ")") if guard_network
                      else "OFF (--no-network-guard)",
        "L4_budgets": f"ON — {SANDBOX_CAPS} enforced by the parent (inner limits in limits.LIMITS)",
        "not_claimed": "hypervisor / microVM isolation (§0 — deliberately out of scope)",
    }


def in_container() -> bool:
    return Path("/.dockerenv").exists() or os.environ.get("ARE_IN_CONTAINER") == "1"
