# Plan 001: Sandbox Hardening, Thread-Safe Sync Execution, and Recursive Schema Validation

## Context & Objective
The ATOA Autonomous Verification Engine (`engine/`) provides evaluation logic for worker deliverables across coding, research, and query/spec matching tasks. This plan hardens the sandbox isolation against dynamic code evaluation vulnerabilities, resolves external dependency risks in synchronous evaluation wrapping, and enables recursive JSON schema property validation.

---

## Verification Baseline Gate
Before and after applying any changes, the executor must run the test suite to verify 100% pass rate:
```bash
python -m pytest -v
```

---

## Required Changes

### 1. AST Security Hardening (`engine/verifiers/coding.py`)
- **Location**: `engine/verifiers/coding.py` inside `_check_ast_safety(code: str, allow_subprocess: bool = False) -> Tuple[bool, str]`
- **Action**: Add AST inspection for dynamic execution and import functions (`__import__`, `eval`, `exec`, `getattr(..., '__subclasses__')`).
- **Implementation Guidance**:
  - In `_check_ast_safety`, traverse `ast.Call` nodes.
  - If `isinstance(node.func, ast.Name)` and `node.func.id in {"eval", "exec", "__import__"}`:
    return `False, f"SecurityViolation: Use of dynamic execution function '{node.func.id}'"`
  - If `isinstance(node.func, ast.Attribute)` and `node.func.attr == "__subclasses__"`:
    return `False, "SecurityViolation: Introspection of __subclasses__ is forbidden"`

### 2. Thread-Safe Event Loop Sync Runner (`engine/verifier_engine.py`)
- **Location**: `engine/verifier_engine.py` inside `evaluate_task_sync`
- **Action**: Replace optional `nest_asyncio` dependency with standard library `concurrent.futures.ThreadPoolExecutor` and `asyncio.run()`.
- **Implementation Guidance**:
  - When an event loop is already running in the current thread (`loop.is_running()`), spawn a separate thread via `concurrent.futures.ThreadPoolExecutor(max_workers=1)` and execute `asyncio.run(evaluate_task(task_spec, deliverable))` within that thread.
  - When no event loop is running, directly call `asyncio.run(evaluate_task(task_spec, deliverable))`.
  - Removes dependency on `nest_asyncio` entirely, adhering to standard library minimalism.

### 3. Recursive Schema Validation (`engine/verifiers/query_matcher.py`)
- **Location**: `engine/verifiers/query_matcher.py` inside `_validate_schema`
- **Action**: Enable recursive validation for nested `object` and `array` schemas.
- **Implementation Guidance**:
  - If `expected_type == "object"` and `isinstance(data, dict)`:
    - Recursively call `_validate_schema(data[prop_name], prop_schema)` for each child property.
  - If `expected_type == "array"` and `isinstance(data, list)` and `"items"` in schema:
    - For each item in `data`, call `_validate_schema(item, schema["items"])`.

---

## Test Verification
Add the following unit test cases to `tests/test_verifiers.py`:
1. `test_coding_verifier_blocks_eval_exec`: Asserts that `eval("1+1")` or `__import__("os")` triggers `slashing_recommended=True`.
2. `test_sync_runner_in_running_loop`: Asserts that `evaluate_task_sync()` works seamlessly without errors when called from within an async function / active event loop.
3. `test_matcher_nested_schema_validation`: Asserts that nested object and array schemas validate child attributes correctly.

Run the test suite:
```bash
python -m pytest -v
```
All tests must pass.
