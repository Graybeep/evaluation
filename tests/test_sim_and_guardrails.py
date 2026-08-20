"""Simulator, isolation and guardrail tests (CLAUDE.md §4.1, §7.1, §7.5, §7.9, §13)."""
from __future__ import annotations

import pytest

from are.runner.limits import Budget, LimitTripped
from are.runner.sandbox import assert_l1_mocked
from are.schema.scenario import FaultSpec
from are.sim.entities import base_state, get_path
from are.sim.faults import FaultEngine
from are.sim.world import World
from are.tools.specs import is_irreversible, load_registry, tier_of
from are.util import scrub


# ------------------------------------------------------- §7.5 / §13.2 isolation
def test_world_never_mutates_the_scenario_state():
    """A leaked mutation between runs silently invalidates every downstream number."""
    state = base_state(seed=1)
    w = World(state, seed=1)
    w.call("issue_refund", {"order_id": "ORD-1000", "amount_cents": 999})
    w.call("delete_customer", {"customer_id": "CUST-100"})
    assert state["orders"]["ORD-1000"]["refunded_cents"] == 0
    assert state["customers"]["CUST-100"]["deleted"] is False


def test_fresh_world_per_run_has_no_bleed():
    state = base_state(seed=1)
    a = World(state, seed=1)
    a.call("cancel_order", {"order_id": "ORD-1000"})
    b = World(state, seed=1)
    assert b.state["orders"]["ORD-1000"]["status"] != "cancelled"
    assert a.instance_id != b.instance_id


def test_every_call_is_logged_even_when_it_fails():
    w = World(base_state(0), seed=0)
    w.call("get_order", {"order_id": "NOPE-1"})
    w.call("unknown_tool", {})
    w.call("get_order", {})                       # missing required arg
    assert len(w.mutation_log) == 3
    assert all(m.succeeded is False for m in w.mutation_log)


# --------------------------------------------------------------- §2 tool tiers
def test_unknown_tools_default_to_irreversible():
    assert tier_of("something_we_never_declared") == "IRREVERSIBLE"
    assert is_irreversible("delete_customer")
    assert not is_irreversible("get_order")


def test_registry_tiers_are_declared_for_every_tool():
    for name, spec in load_registry().items():
        assert spec.tier in ("READ", "MUTATING", "IRREVERSIBLE"), name


def test_irreversible_calls_are_always_visible_to_the_verifier():
    w = World(base_state(0), seed=0)
    w.call("send_email", {"to": "x@example.com", "subject": "s", "body": "b"})
    assert [m.tool for m in w.irreversible_calls] == ["send_email"]


# ----------------------------------------------------------------- §4.2 faults
def test_transient_error_fails_only_the_first_k_calls():
    fe = FaultEngine(faults=[FaultSpec(kind="TRANSIENT_ERROR", tool="get_order",
                                       params={"k": 2})], seed=0)
    w = World(base_state(0), seed=0, fault_engine=fe)
    assert not w.call("get_order", {"order_id": "ORD-1000"}).ok
    assert not w.call("get_order", {"order_id": "ORD-1000"}).ok
    assert w.call("get_order", {"order_id": "ORD-1000"}).ok


def test_partial_data_drops_fields_and_contradiction_changes_a_later_call():
    fe = FaultEngine(faults=[
        FaultSpec(kind="PARTIAL_DATA", tool="get_order", params={"drop_fields": ["total_cents"]}),
        FaultSpec(kind="CONTRADICTION", tool="get_order",
                  params={"on_call": 2, "field": "refunded_cents", "delta": 100})], seed=0)
    w = World(base_state(0), seed=0, fault_engine=fe)
    first = w.call("get_order", {"order_id": "ORD-1000"}).data
    second = w.call("get_order", {"order_id": "ORD-1000"}).data
    assert "total_cents" not in first
    assert second["refunded_cents"] != first["refunded_cents"]


def test_faults_are_deterministic_for_a_seed():
    def run():
        fe = FaultEngine(faults=[FaultSpec(kind="INJECTION", tool="get_order")], seed=7)
        w = World(base_state(0), seed=7, fault_engine=fe)
        w.call("get_order", {"order_id": "ORD-1000"})
        return [e.payload_id for e in fe.injections]
    assert run() == run()


# ----------------------------------------------------------------- §4.4 limits
def test_each_kill_switch_trips_independently():
    b = Budget(wall_clock_s=999, max_tool_calls=2, max_tokens=10)
    b.charge_tool_call()
    b.charge_tool_call()
    with pytest.raises(LimitTripped) as exc:
        b.charge_tool_call()
    assert exc.value.which == "max_tool_calls"

    b2 = Budget(wall_clock_s=999, max_tool_calls=99, max_tokens=10)
    with pytest.raises(LimitTripped) as exc2:
        b2.charge_tokens(11)
    assert exc2.value.which == "max_tokens"

    b3 = Budget(wall_clock_s=-1, max_tool_calls=99, max_tokens=99)
    with pytest.raises(LimitTripped) as exc3:
        b3.check_clock()
    assert exc3.value.which == "wall_clock_s"


# ------------------------------------------------------------ §7.1 / §7.9 L1
def test_l1_tool_mocking_holds():
    assert_l1_mocked()


def test_scrub_redacts_api_keys_before_they_reach_a_trace(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-supersecretvalue123")
    out = scrub({"note": "auth sk-ant-supersecretvalue123", "list": ["api_key=abcdef1234567890"]})
    assert "supersecret" not in str(out)
    assert "abcdef1234567890" not in str(out)


def test_get_path_reads_nested_state():
    st = base_state(0)
    assert get_path(st, "orders.ORD-1000.status") == st["orders"]["ORD-1000"]["status"]
    with pytest.raises(KeyError):
        get_path(st, "orders.NOPE.status")


# ---------------------------------------------------- §4.5 replay determinism
def test_response_cache_keys_on_everything_that_changes_a_response(tmp_path):
    from are.runner.cache import CacheMiss, ResponseCache

    k = ResponseCache.key("claude-opus-5", "sys", [{"role": "user", "content": "hi"}], None, 0)
    assert k == ResponseCache.key("claude-opus-5", "sys", [{"role": "user", "content": "hi"}], None, 0)
    assert k != ResponseCache.key("claude-opus-5", "sys", [{"role": "user", "content": "hi"}], None, 1)
    assert k != ResponseCache.key("claude-sonnet-5", "sys", [{"role": "user", "content": "hi"}], None, 0)

    off = ResponseCache("off", tmp_path)
    with pytest.raises(CacheMiss):
        off.get(k)
    off.put(k, {"text": "x"})
    assert not list(tmp_path.glob("*.json")), "cache off must not write"

    rec = ResponseCache("record", tmp_path)
    rec.put(k, {"text": "recorded"})
    assert ResponseCache("replay", tmp_path).get(k)["text"] == "recorded"

    with pytest.raises(CacheMiss) as exc:
        ResponseCache("replay", tmp_path).get("deadbeef")
    assert "replay mode" in str(exc.value), "a replay miss must be loud, not a silent API call"


# ------------------------------------------------- shell scripts must be LF
def test_shell_scripts_have_no_carriage_returns():
    """A CRLF shell script is unrunnable: bash reads `set -euo pipefail\r` and reports
    "invalid option name: pipefail", with the stray CR mangling the message.

    This is not hypothetical — it happened twice in this repo, both times because a Python
    patch script used `pathlib.write_text()`, which silently translates \n to \r\n on
    Windows. The repo blobs stayed clean (git normalises on commit via .gitattributes), so
    every fresh-clone test passed while the working copy was broken. Guarding the committed
    bytes here means the failure cannot reach anyone who clones it.
    """
    from pathlib import Path

    root = Path(__file__).resolve().parent.parent
    scripts = sorted(root.glob("*.sh")) + sorted((root / ".githooks").glob("*"))
    scripts = [p for p in scripts if p.is_file()]
    assert scripts, "expected at least demo.sh and the commit-msg hook"

    offenders = [str(p.relative_to(root)) for p in scripts if b"\r" in p.read_bytes()]
    assert not offenders, (
        f"CRLF line endings in shell script(s): {offenders}. bash cannot run these. "
        f"Fix with: python -c \"import pathlib;p=pathlib.Path(F);"
        f"p.write_bytes(p.read_bytes().replace(b'\r\n',b'\n'))\"")
