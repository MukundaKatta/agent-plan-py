"""agent-plan-py — multi-step plan executor with dependency tracking."""

from __future__ import annotations

import enum
from dataclasses import dataclass, field
from typing import Any, Callable


class StepStatus(enum.Enum):
    PENDING = "pending"
    READY = "ready"
    RUNNING = "running"
    DONE = "done"
    FAILED = "failed"
    SKIPPED = "skipped"


class PlanError(Exception):
    """Raised when the plan is invalid (e.g., circular dependency)."""


@dataclass
class Step:
    id: str
    fn: Callable[..., Any]
    deps: list[str] = field(default_factory=list)
    args: dict = field(default_factory=dict)
    status: StepStatus = StepStatus.PENDING
    result: Any = None
    error: Exception | None = None


class Plan:
    """
    Multi-step plan executor with dependency tracking.

    Steps run only when all their dependencies are done.
    Results of dependency steps are passed as kwargs to dependent steps.

    Example::

        plan = Plan()
        plan.add_step("fetch", fetch_data)
        plan.add_step("parse", parse_data, deps=["fetch"])
        plan.add_step("save", save_result, deps=["parse"])
        plan.run()
        assert plan.result("save") is not None
    """

    def __init__(self) -> None:
        self._steps: dict[str, Step] = {}

    def add_step(
        self,
        step_id: str,
        fn: Callable[..., Any],
        deps: list[str] | None = None,
        args: dict | None = None,
    ) -> "Plan":
        """Register a step. Returns self for chaining."""
        self._steps[step_id] = Step(
            id=step_id,
            fn=fn,
            deps=deps or [],
            args=args or {},
        )
        return self

    def run(self, context: dict | None = None) -> "Plan":
        """
        Execute all steps in dependency order.
        Results of completed dependencies are injected as kwargs into each step.
        """
        self._validate()
        ctx = dict(context or {})

        # Mark steps that have satisfied deps as READY
        self._refresh_ready()

        max_iters = len(self._steps) * 2 + 1
        for _ in range(max_iters):
            ready = [s for s in self._steps.values() if s.status == StepStatus.READY]
            if not ready:
                break

            for step in ready:
                step.status = StepStatus.RUNNING
                dep_results = {dep_id: self._steps[dep_id].result for dep_id in step.deps}
                kwargs = {**ctx, **dep_results, **step.args}
                try:
                    step.result = step.fn(**kwargs)
                    step.status = StepStatus.DONE
                except Exception as exc:
                    step.error = exc
                    step.status = StepStatus.FAILED
                    # Mark dependents as skipped
                    self._skip_dependents(step.id)

            self._refresh_ready()

        return self

    def result(self, step_id: str) -> Any:
        """Return the result of a completed step."""
        return self._steps[step_id].result

    def status(self, step_id: str) -> StepStatus:
        return self._steps[step_id].status

    def all_done(self) -> bool:
        return all(
            s.status in (StepStatus.DONE, StepStatus.FAILED, StepStatus.SKIPPED)
            for s in self._steps.values()
        )

    def failed_steps(self) -> list[str]:
        return [s.id for s in self._steps.values() if s.status == StepStatus.FAILED]

    def summary(self) -> dict[str, str]:
        return {s.id: s.status.value for s in self._steps.values()}

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _refresh_ready(self) -> None:
        for step in self._steps.values():
            if step.status != StepStatus.PENDING:
                continue
            if all(
                self._steps[dep].status == StepStatus.DONE
                for dep in step.deps
                if dep in self._steps
            ):
                step.status = StepStatus.READY

    def _skip_dependents(self, failed_id: str) -> None:
        for step in self._steps.values():
            if failed_id in step.deps and step.status == StepStatus.PENDING:
                step.status = StepStatus.SKIPPED
                self._skip_dependents(step.id)

    def _validate(self) -> None:
        """Detect cycles via DFS."""
        visited: set[str] = set()
        in_stack: set[str] = set()

        def dfs(node: str) -> None:
            visited.add(node)
            in_stack.add(node)
            for dep in self._steps.get(node, Step(node, lambda: None)).deps:
                if dep not in self._steps:
                    raise PlanError(f"Step '{node}' depends on unknown step '{dep}'")
                if dep not in visited:
                    dfs(dep)
                elif dep in in_stack:
                    raise PlanError(f"Circular dependency detected: {node} → {dep}")
            in_stack.discard(node)

        for step_id in self._steps:
            if step_id not in visited:
                dfs(step_id)


__all__ = ["Plan", "Step", "StepStatus", "PlanError"]
