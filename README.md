# agent-plan-py

Multi-step plan executor with dependency tracking for agent workflows.

```bash
pip install agent-plan-py
```

## Quick start

```python
from agent_plan import Plan

plan = Plan()
plan.add_step("fetch",  fetch_data)
plan.add_step("parse",  parse_data,   deps=["fetch"])
plan.add_step("save",   save_result,  deps=["parse"])
plan.run()

assert plan.status("save").value == "done"
print(plan.result("save"))
```

## Dependency results as kwargs

Each step receives the **results of its dependencies as kwargs**:

```python
plan = Plan()
plan.add_step("get_user",    lambda: {"id": 42, "name": "Alice"})
plan.add_step("get_profile", lambda get_user: fetch_profile(get_user["id"]), deps=["get_user"])
plan.run()
```

## Shared context

```python
plan = Plan()
plan.add_step("greet", lambda api_key: call_api(api_key))
plan.run(context={"api_key": "sk-..."})
```

## Error handling

Failed steps are marked `FAILED`; all steps that depend on them (directly or transitively) are automatically `SKIPPED`.

```python
plan.run()
if plan.failed_steps():
    print("Failed:", plan.failed_steps())
print(plan.summary())   # {"fetch": "done", "parse": "failed", "save": "skipped"}
```

## API

```python
Plan()
  .add_step(id, fn, deps=None, args=None) -> Plan   # chainable
  .run(context=None) -> Plan
  .result(step_id) -> Any
  .status(step_id) -> StepStatus
  .all_done() -> bool
  .failed_steps() -> list[str]
  .summary() -> dict[str, str]

StepStatus: PENDING | READY | RUNNING | DONE | FAILED | SKIPPED
```

## Zero dependencies
