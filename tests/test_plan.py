"""Unit tests for agent_plan.Plan.

These tests use only the Python standard library (``unittest``) so they can run
with ``python3 -m unittest discover -s tests`` and no third-party dependencies.
"""

import os
import sys
import unittest

# Make the package importable when running the suite directly from a checkout
# (the package lives under ``src/``) without requiring an editable install or a
# manually set PYTHONPATH.
_SRC = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "src")
if _SRC not in sys.path:
    sys.path.insert(0, _SRC)

from agent_plan import Plan, Step, StepStatus, PlanError


class TestBasicExecution(unittest.TestCase):
    def test_single_step_runs(self):
        plan = Plan()
        plan.add_step("a", lambda: 42)
        plan.run()
        self.assertEqual(plan.result("a"), 42)

    def test_sequential_steps(self):
        plan = Plan()
        plan.add_step("fetch", lambda: [1, 2, 3])
        plan.add_step("count", lambda fetch: len(fetch), deps=["fetch"])
        plan.run()
        self.assertEqual(plan.result("count"), 3)

    def test_chain_three_steps(self):
        plan = Plan()
        plan.add_step("a", lambda: 10)
        plan.add_step("b", lambda a: a * 2, deps=["a"])
        plan.add_step("c", lambda b: b + 5, deps=["b"])
        plan.run()
        self.assertEqual(plan.result("c"), 25)


class TestDependencies(unittest.TestCase):
    def test_multiple_deps(self):
        plan = Plan()
        plan.add_step("x", lambda: 3)
        plan.add_step("y", lambda: 4)
        plan.add_step("sum", lambda x, y: x + y, deps=["x", "y"])
        plan.run()
        self.assertEqual(plan.result("sum"), 7)

    def test_diamond_dependency(self):
        plan = Plan()
        plan.add_step("root", lambda: 1)
        plan.add_step("left", lambda root: root + 10, deps=["root"])
        plan.add_step("right", lambda root: root + 20, deps=["root"])
        plan.add_step(
            "merge", lambda left, right: left + right, deps=["left", "right"]
        )
        plan.run()
        self.assertEqual(plan.result("merge"), 32)

    def test_step_with_explicit_args(self):
        plan = Plan()
        plan.add_step(
            "greet", lambda name: f"Hello, {name}!", args={"name": "World"}
        )
        plan.run()
        self.assertEqual(plan.result("greet"), "Hello, World!")

    def test_context_passed_to_steps(self):
        plan = Plan()
        plan.add_step("use_ctx", lambda greeting: greeting.upper())
        plan.run(context={"greeting": "hello"})
        self.assertEqual(plan.result("use_ctx"), "HELLO")

    def test_dependency_result_injected_as_kwarg(self):
        plan = Plan()
        plan.add_step("get_user", lambda: {"id": 42, "name": "Alice"})
        plan.add_step(
            "name", lambda get_user: get_user["name"], deps=["get_user"]
        )
        plan.run()
        self.assertEqual(plan.result("name"), "Alice")


class TestStatusTracking(unittest.TestCase):
    def test_status_done_after_run(self):
        plan = Plan()
        plan.add_step("a", lambda: 1)
        plan.run()
        self.assertEqual(plan.status("a"), StepStatus.DONE)

    def test_status_pending_before_run(self):
        plan = Plan()
        plan.add_step("a", lambda: 1)
        self.assertEqual(plan.status("a"), StepStatus.PENDING)

    def test_all_done(self):
        plan = Plan()
        plan.add_step("a", lambda: 1)
        plan.add_step("b", lambda: 2)
        plan.run()
        self.assertTrue(plan.all_done())

    def test_summary_all_done(self):
        plan = Plan()
        plan.add_step("x", lambda: 1)
        plan.run()
        self.assertEqual(plan.summary()["x"], "done")


class TestErrorHandling(unittest.TestCase):
    def test_failed_step_status(self):
        plan = Plan()
        plan.add_step("bad", lambda: 1 / 0)
        plan.run()
        self.assertEqual(plan.status("bad"), StepStatus.FAILED)

    def test_failed_step_error_stored(self):
        plan = Plan()
        plan.add_step("bad", lambda: (_ for _ in ()).throw(ValueError("oops")))
        plan.run()
        self.assertEqual(plan.status("bad"), StepStatus.FAILED)

    def test_error_accessor_returns_exception(self):
        plan = Plan()
        plan.add_step("bad", lambda: 1 / 0)
        plan.run()
        err = plan.error("bad")
        self.assertIsInstance(err, ZeroDivisionError)

    def test_error_accessor_none_for_successful_step(self):
        plan = Plan()
        plan.add_step("ok", lambda: 1)
        plan.run()
        self.assertIsNone(plan.error("ok"))

    def test_dependent_step_skipped_on_failure(self):
        plan = Plan()
        plan.add_step("bad", lambda: 1 / 0)
        plan.add_step("child", lambda bad: bad + 1, deps=["bad"])
        plan.run()
        self.assertEqual(plan.status("child"), StepStatus.SKIPPED)

    def test_cascade_skip(self):
        plan = Plan()
        plan.add_step("root", lambda: 1 / 0)
        plan.add_step("mid", lambda root: root, deps=["root"])
        plan.add_step("leaf", lambda mid: mid, deps=["mid"])
        plan.run()
        self.assertEqual(plan.status("leaf"), StepStatus.SKIPPED)

    def test_failed_steps_list(self):
        plan = Plan()
        plan.add_step("ok", lambda: 1)
        plan.add_step("bad", lambda: 1 / 0)
        plan.run()
        self.assertIn("bad", plan.failed_steps())
        self.assertNotIn("ok", plan.failed_steps())

    def test_independent_step_runs_despite_unrelated_failure(self):
        plan = Plan()
        plan.add_step("bad", lambda: 1 / 0)
        plan.add_step("good", lambda: 7)
        plan.run()
        self.assertEqual(plan.status("good"), StepStatus.DONE)
        self.assertEqual(plan.result("good"), 7)

    def test_diamond_with_one_failing_branch_skips_merge(self):
        plan = Plan()
        plan.add_step("root", lambda: 1)
        plan.add_step("good", lambda root: root, deps=["root"])
        plan.add_step("bad", lambda root: 1 / 0, deps=["root"])
        plan.add_step(
            "merge", lambda good, bad: good + bad, deps=["good", "bad"]
        )
        plan.run()
        self.assertEqual(plan.status("merge"), StepStatus.SKIPPED)
        self.assertEqual(plan.status("good"), StepStatus.DONE)


class TestChaining(unittest.TestCase):
    def test_add_step_returns_plan(self):
        plan = Plan()
        result = plan.add_step("a", lambda: 1)
        self.assertIs(result, plan)

    def test_run_returns_plan(self):
        plan = Plan().add_step("a", lambda: 1)
        self.assertIs(plan.run(), plan)

    def test_method_chaining(self):
        plan = (
            Plan()
            .add_step("a", lambda: 2)
            .add_step("b", lambda a: a * 3, deps=["a"])
        )
        plan.run()
        self.assertEqual(plan.result("b"), 6)


class TestValidation(unittest.TestCase):
    def test_direct_cycle_detection(self):
        plan = Plan()
        plan.add_step("a", lambda: 1, deps=["b"])
        plan.add_step("b", lambda: 2, deps=["a"])
        with self.assertRaisesRegex(PlanError, "Circular"):
            plan.run()

    def test_self_cycle_detection(self):
        plan = Plan()
        plan.add_step("a", lambda: 1, deps=["a"])
        with self.assertRaisesRegex(PlanError, "Circular"):
            plan.run()

    def test_long_cycle_detection(self):
        plan = Plan()
        plan.add_step("a", lambda: 1, deps=["c"])
        plan.add_step("b", lambda: 1, deps=["a"])
        plan.add_step("c", lambda: 1, deps=["b"])
        with self.assertRaisesRegex(PlanError, "Circular"):
            plan.run()

    def test_unknown_dependency(self):
        plan = Plan()
        plan.add_step("a", lambda: 1, deps=["nonexistent"])
        with self.assertRaises(PlanError):
            plan.run()

    def test_valid_diamond_dag_does_not_raise(self):
        plan = Plan()
        plan.add_step("a", lambda: 1)
        plan.add_step("b", lambda a: a, deps=["a"])
        plan.add_step("c", lambda a, b: a + b, deps=["a", "b"])
        plan.run()
        self.assertTrue(plan.all_done())


class TestEdgeCases(unittest.TestCase):
    def test_empty_plan_runs_cleanly(self):
        plan = Plan()
        plan.run()
        self.assertTrue(plan.all_done())

    def test_empty_plan_summary(self):
        self.assertEqual(Plan().run().summary(), {})

    def test_run_twice_idempotent(self):
        plan = Plan()
        plan.add_step("a", lambda: 99)
        plan.run()
        plan.run()
        self.assertEqual(plan.result("a"), 99)

    def test_run_twice_does_not_re_execute(self):
        calls = []
        plan = Plan()
        plan.add_step("a", lambda: calls.append("a") or 1)
        plan.run()
        plan.run()
        self.assertEqual(calls, ["a"])

    def test_args_override_dependency_result(self):
        plan = Plan()
        plan.add_step("dep", lambda: 1)
        plan.add_step("use", lambda dep: dep, deps=["dep"], args={"dep": 100})
        plan.run()
        self.assertEqual(plan.result("use"), 100)

    def test_result_unknown_step_raises_plan_error(self):
        plan = Plan()
        plan.add_step("a", lambda: 1)
        plan.run()
        with self.assertRaisesRegex(PlanError, "Unknown step"):
            plan.result("missing")

    def test_status_unknown_step_raises_plan_error(self):
        plan = Plan()
        plan.run()
        with self.assertRaisesRegex(PlanError, "Unknown step"):
            plan.status("missing")

    def test_error_unknown_step_raises_plan_error(self):
        plan = Plan()
        plan.run()
        with self.assertRaisesRegex(PlanError, "Unknown step"):
            plan.error("missing")

    def test_summary_reflects_failed_and_skipped(self):
        plan = Plan()
        plan.add_step("root", lambda: 1 / 0)
        plan.add_step("child", lambda root: root, deps=["root"])
        plan.run()
        self.assertEqual(plan.summary(), {"root": "failed", "child": "skipped"})

    def test_add_step_overwrites_same_id(self):
        plan = Plan()
        plan.add_step("a", lambda: 1)
        plan.add_step("a", lambda: 2)
        plan.run()
        self.assertEqual(plan.result("a"), 2)


class TestDataclass(unittest.TestCase):
    def test_step_defaults(self):
        step = Step(id="s", fn=lambda: None)
        self.assertEqual(step.deps, [])
        self.assertEqual(step.args, {})
        self.assertEqual(step.status, StepStatus.PENDING)
        self.assertIsNone(step.result)
        self.assertIsNone(step.error)


if __name__ == "__main__":
    unittest.main()
