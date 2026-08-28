# Plan 002: Process Group Sandbox Cleanup and Live Query Search Ground-Truth Adapter

## Context & Objective
The ATOA Programmatic Verification Engine (`engine/` and `services/verification_oracle.py`) runs isolated tests and validates deliverables for the ATOA Marketplace. This plan implements robust process-tree termination for timed-out sandboxes across platforms (Windows and POSIX) and provides an optional pluggable live search ground-truth retriever for Developer `bk`'s `QueryValidatorBot` as outlined in `splitup_file.md`.

---

## Verification Baseline Gate
Before and after applying any changes, the executor must run the test suite to verify 100% pass rate:
```bash
python -m pytest -v
```

---

## Required Changes

### 1. Robust Process-Tree Termination on Timeout (`engine/verifiers/coding.py`)
- **Location**: `engine/verifiers/coding.py` inside `verify_coding` exception handling for `asyncio.TimeoutError`
- **Action**: Ensure process tree termination so child processes do not become orphaned when code execution times out.
- **Implementation Guidance**:
  - On Windows: Check if `proc.pid` exists; if process is alive, call `taskkill /F /T /PID <pid>` or `proc.kill()`.
  - On POSIX: Use `start_new_session=True` in `create_subprocess_exec` and `os.killpg(os.getpgid(proc.pid), signal.SIGKILL)` on timeout.
  - Wrap in a `try/except Exception: proc.kill()` fallback.

### 2. Live Search / External Ground-Truth Query Adapter (`engine/verifiers/query_matcher.py`)
- **Location**: `engine/verifiers/query_matcher.py`
- **Action**: Add an optional ground-truth resolver for `QueryValidatorBot` when `fetch_live_ground_truth: True` is configured in `validation_spec`.
- **Implementation Guidance**:
  - Create a lightweight helper `fetch_query_ground_truth(query: str) -> List[str]` that extracts snippets/entities from search queries or local mock endpoints.
  - Integrate with `verify_matcher`: if `ground_truth_references` is empty but `task_spec.constraints.get("enable_live_search")` is `True`, resolve ground-truth entities dynamically before assertion matching.

---

## Test Verification
Add the following unit test cases to `tests/test_verifiers.py`:
1. `test_process_tree_cleanup_on_timeout`: Verify that child processes spawned within a timeout script are terminated cleanly without lingering.
2. `test_query_validator_live_search_enrichment`: Verify that query validation enriches entity matching when `enable_live_search` constraint is enabled.

Run the test suite:
```bash
python -m pytest -v
```
All tests must pass with 100% pass rate.
