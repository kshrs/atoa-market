# Plan 003: Packaging Standards, Hash Seed Determinism, and Telemetry Enrichment

## Context & Objective
The ATOA Autonomous Verification Engine and Oracle (`engine/`, `services/`) fulfill Developer `bk`'s programmatic rule-based verification role. This plan establishes standardized packaging metadata (`pyproject.toml`), enforces hash seed determinism (`PYTHONHASHSEED=0`) during code sandbox execution, and enriches failure categorization in `VerificationReport.validation_details` for seamless visual telemetry consumption by Developer `nvss`'s Observer Dashboard.

---

## Verification Baseline Gate
Before and after applying any changes, the executor must run the test suite to verify 100% pass rate:
```bash
python -m pytest -v
```

---

## Required Changes

### 1. Standard Packaging & Tooling Configuration (`pyproject.toml`)
- **Location**: Project root (`pyproject.toml`)
- **Action**: Create declarative packaging configuration.
- **Specification**:
  - `[project]` metadata: `name = "atoa-verifier-engine"`, `version = "0.1.0"`, `requires-python = ">=3.11"`.
  - `dependencies = ["pydantic>=2.10.0", "jsonschema>=4.20.0"]`.
  - `[project.optional-dependencies] test = ["pytest>=8.0.0", "pytest-asyncio>=0.23.0"]`.
  - `[tool.pytest.ini_options]`: `asyncio_mode = "auto"`, `testpaths = ["tests"]`.

### 2. Hash Seed Determinism in Sandbox Execution (`engine/verifiers/coding.py`)
- **Location**: `engine/verifiers/coding.py` inside `verify_coding` sandbox environment setup
- **Action**: Set `clean_env["PYTHONHASHSEED"] = "0"` in the execution environment.
- **Rationale**: Ensures deterministic object hashing and reproducible test execution across worker evaluations.

### 3. Structured Failure Telemetry Categorization (`services/verification_oracle.py`)
- **Location**: `services/verification_oracle.py` inside `verify_deliverable`
- **Action**: Add an explicit `failure_category` key to `validation_details` (`"NONE" | "SECURITY_VIOLATION" | "TIMEOUT" | "TEST_FAILURE" | "SCHEMA_MISMATCH" | "GROUNDING_FAILURE" | "EXECUTION_ERROR"`).
- **Rationale**: Enables `nvss`'s frontend dashboard to instantly categorize and render color-coded alert badges for judges and network observers.

---

## Test Verification
Add unit test cases in `tests/test_verifiers.py`:
1. `test_verification_details_failure_categorization`: Test that AST security violations, timeouts, and schema mismatches assign distinct, structured `failure_category` codes in `validation_details`.
2. `test_sandbox_deterministic_hash_seed`: Verify that `PYTHONHASHSEED` is set to `"0"` in the sandbox execution environment.

Run the test suite:
```bash
python -m pytest -v
```
All tests must pass.
