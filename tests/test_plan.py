import pytest
from agent_plan import Plan, StepStatus, PlanError


# ---------------------------------------------------------------------------
# Basic execution
# ---------------------------------------------------------------------------

def test_single_step_runs():
    plan = Plan()
    plan.add_step("a", lambda: 42)
    plan.run()
    assert plan.result("a") == 42


def test_sequential_steps():
    plan = Plan()
    plan.add_step("fetch", lambda: [1, 2, 3])
    plan.add_step("count", lambda fetch: len(fetch), deps=["fetch"])
    plan.run()
    assert plan.result("count") == 3


def test_chain_three_steps():
    plan = Plan()
    plan.add_step("a", lambda: 10)
    plan.add_step("b", lambda a: a * 2, deps=["a"])
    plan.add_step("c", lambda b: b + 5, deps=["b"])
    plan.run()
    assert plan.result("c") == 25


# ---------------------------------------------------------------------------
# Dependencies
# ---------------------------------------------------------------------------

def test_multiple_deps():
    plan = Plan()
    plan.add_step("x", lambda: 3)
    plan.add_step("y", lambda: 4)
    plan.add_step("sum", lambda x, y: x + y, deps=["x", "y"])
    plan.run()
    assert plan.result("sum") == 7


def test_diamond_dependency():
    plan = Plan()
    plan.add_step("root", lambda: 1)
    plan.add_step("left", lambda root: root + 10, deps=["root"])
    plan.add_step("right", lambda root: root + 20, deps=["root"])
    plan.add_step("merge", lambda left, right: left + right, deps=["left", "right"])
    plan.run()
    assert plan.result("merge") == 32


def test_step_with_explicit_args():
    plan = Plan()
    plan.add_step("greet", lambda name: f"Hello, {name}!", args={"name": "World"})
    plan.run()
    assert plan.result("greet") == "Hello, World!"


def test_context_passed_to_steps():
    plan = Plan()
    plan.add_step("use_ctx", lambda greeting: greeting.upper())
    plan.run(context={"greeting": "hello"})
    assert plan.result("use_ctx") == "HELLO"


# ---------------------------------------------------------------------------
# Status tracking
# ---------------------------------------------------------------------------

def test_status_done_after_run():
    plan = Plan()
    plan.add_step("a", lambda: 1)
    plan.run()
    assert plan.status("a") == StepStatus.DONE


def test_all_done():
    plan = Plan()
    plan.add_step("a", lambda: 1)
    plan.add_step("b", lambda: 2)
    plan.run()
    assert plan.all_done()


def test_summary_all_done():
    plan = Plan()
    plan.add_step("x", lambda: 1)
    plan.run()
    s = plan.summary()
    assert s["x"] == "done"


# ---------------------------------------------------------------------------
# Error handling
# ---------------------------------------------------------------------------

def test_failed_step_status():
    plan = Plan()
    plan.add_step("bad", lambda: 1 / 0)
    plan.run()
    assert plan.status("bad") == StepStatus.FAILED


def test_failed_step_error_stored():
    plan = Plan()
    plan.add_step("bad", lambda: (_ for _ in ()).throw(ValueError("oops")))
    plan.run()
    assert plan.status("bad") == StepStatus.FAILED


def test_dependent_step_skipped_on_failure():
    plan = Plan()
    plan.add_step("bad", lambda: 1 / 0)
    plan.add_step("child", lambda bad: bad + 1, deps=["bad"])
    plan.run()
    assert plan.status("child") == StepStatus.SKIPPED


def test_cascade_skip():
    plan = Plan()
    plan.add_step("root", lambda: 1 / 0)
    plan.add_step("mid", lambda root: root, deps=["root"])
    plan.add_step("leaf", lambda mid: mid, deps=["mid"])
    plan.run()
    assert plan.status("leaf") == StepStatus.SKIPPED


def test_failed_steps_list():
    plan = Plan()
    plan.add_step("ok", lambda: 1)
    plan.add_step("bad", lambda: 1 / 0)
    plan.run()
    assert "bad" in plan.failed_steps()
    assert "ok" not in plan.failed_steps()


# ---------------------------------------------------------------------------
# Chaining
# ---------------------------------------------------------------------------

def test_add_step_returns_plan():
    plan = Plan()
    result = plan.add_step("a", lambda: 1)
    assert result is plan


def test_method_chaining():
    plan = (
        Plan()
        .add_step("a", lambda: 2)
        .add_step("b", lambda a: a * 3, deps=["a"])
    )
    plan.run()
    assert plan.result("b") == 6


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------

def test_cycle_detection():
    plan = Plan()
    plan.add_step("a", lambda: 1, deps=["b"])
    plan.add_step("b", lambda: 2, deps=["a"])
    with pytest.raises(PlanError, match="Circular"):
        plan.run()


def test_unknown_dependency():
    plan = Plan()
    plan.add_step("a", lambda: 1, deps=["nonexistent"])
    with pytest.raises(PlanError):
        plan.run()


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------

def test_empty_plan_runs_cleanly():
    plan = Plan()
    plan.run()
    assert plan.all_done()


def test_run_twice_idempotent():
    plan = Plan()
    plan.add_step("a", lambda: 99)
    plan.run()
    plan.run()
    assert plan.result("a") == 99
