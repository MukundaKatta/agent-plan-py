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

## Inspecting failures

When a step raises, the exception is captured and can be retrieved with
`error()` for logging or re-raising:

```python
plan = Plan()
plan.add_step("bad", lambda: 1 / 0)
plan.run()

print(plan.status("bad"))   # StepStatus.FAILED
print(plan.error("bad"))    # ZeroDivisionError('division by zero')
```

`result()` returns `None` for steps that did not complete successfully, so use
`status()` or `error()` to tell a real `None` result apart from a failure.

## API

```python
Plan()
  .add_step(step_id, fn, deps=None, args=None) -> Plan   # chainable
  .run(context=None) -> Plan                             # chainable
  .result(step_id) -> Any                                # None if not DONE
  .status(step_id) -> StepStatus
  .error(step_id) -> Exception | None                    # set when a step FAILED
  .all_done() -> bool                                    # all steps terminal
  .failed_steps() -> list[str]
  .summary() -> dict[str, str]                           # {step_id: status.value}

StepStatus: PENDING | READY | RUNNING | DONE | FAILED | SKIPPED
```

Unknown step ids passed to `result()`, `status()`, or `error()` raise
`PlanError`. Cycles and references to undefined dependencies are detected by
`run()` and also raise `PlanError`.

## Development

The library has **zero runtime dependencies**, and the test suite uses only the
Python standard library (`unittest`) — no pytest or other tooling required:

```bash
python3 -m unittest discover -s tests
```

## Zero dependencies

`agent-plan-py` is a single pure-Python module with no third-party runtime
requirements. It supports Python 3.9+ and ships type hints (PEP 561 `py.typed`).

## License

MIT
