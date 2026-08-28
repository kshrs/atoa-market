"""
Comprehensive Test Suite for ATOA Programmatic Verification Engine & Oracle.
Validates I/O contracts from splitup_file.md, AST security hardening (eval/exec/__import__),
deep jsonschema validation, and sync ThreadPool runner.
"""
import asyncio
import pytest
import time
from engine.models import TaskManifest, DeliverablePayload, EvaluationResult, VerificationReport
from engine.verifier_engine import evaluate_task, atoa_submit_verdict
from services.verification_oracle import verify_deliverable, verify_deliverable_sync


# =========================================================================
# 1. I/O CONTRACT & VERIFICATION ORACLE TESTS (from splitup_file.md)
# =========================================================================

@pytest.mark.asyncio
async def test_verify_deliverable_code_generation_pass():
    """Verify code generation deliverable produces valid VerificationReport matching spec."""
    task_id = "task_code_sprint_01"
    category = "code_generation"
    artifact_payload = {
        "submitted_code": "def solve(x: int) -> int:\n    return x * 2\n"
    }
    validation_spec = {
        "test_suite": "from solution import solve\ndef test_solve():\n    assert solve(10) == 20\n    assert solve(-3) == -6\n",
        "timeout_seconds": 5
    }

    report = await verify_deliverable(task_id, category, artifact_payload, validation_spec)
    assert isinstance(report, VerificationReport)
    assert report.task_id == task_id
    assert report.category == "code_generation"
    assert report.passed is True
    assert report.score == 1.0
    assert report.error_message is None
    assert report.timestamp > 0
    assert "tests_passed" in report.validation_details
    assert "STDOUT" in report.logs


@pytest.mark.asyncio
async def test_verify_deliverable_research_jsonschema_pass():
    """Verify research deliverable using jsonschema schema validation."""
    task_id = "task_res_sprint_02"
    category = "research"
    schema = {
        "type": "object",
        "required": ["market_analysis", "sources", "confidence_score"],
        "properties": {
            "market_analysis": {
                "type": "object",
                "required": ["summary", "total_volume_usd"],
                "properties": {
                    "summary": {"type": "string", "minLength": 10},
                    "total_volume_usd": {"type": "number", "minimum": 0}
                }
            },
            "sources": {
                "type": "array",
                "items": {"type": "string", "format": "uri"},
                "minItems": 1
            },
            "confidence_score": {"type": "number", "minimum": 0.0, "maximum": 1.0}
        }
    }
    artifact_payload = {
        "submitted_data": {
            "market_analysis": {
                "summary": "Decentralized automated escrow trading volume surged 45% in Q3.",
                "total_volume_usd": 1500000.0
            },
            "sources": [
                "https://reports.atoa.network/escrow-v1.pdf"
            ],
            "confidence_score": 0.95
        },
        "citations": [
            {"claim": "Volume surged 45%", "source": "https://reports.atoa.network/escrow-v1.pdf"}
        ]
    }
    validation_spec = {
        "schema": schema,
        "required_keys": ["market_analysis", "sources", "confidence_score"],
        "min_words": 10
    }

    report = await verify_deliverable(task_id, category, artifact_payload, validation_spec)
    assert report.passed is True
    assert report.score >= 0.80
    assert report.validation_details["schema_valid"] is True
    assert report.error_message is None


@pytest.mark.asyncio
async def test_verify_deliverable_research_jsonschema_invalid():
    """Verify research deliverable failing nested jsonschema rules is rejected."""
    task_id = "task_res_sprint_03"
    category = "research"
    schema = {
        "type": "object",
        "required": ["items"],
        "properties": {
            "items": {
                "type": "array",
                "items": {
                    "type": "object",
                    "required": ["id", "price"],
                    "properties": {
                        "id": {"type": "string"},
                        "price": {"type": "number", "minimum": 0}
                    }
                }
            }
        }
    }
    # Deliberately violate nested item schema (price is negative and missing id)
    artifact_payload = {
        "submitted_data": {
            "items": [
                {"price": -50}
            ]
        }
    }
    validation_spec = {"schema": schema}

    report = await verify_deliverable(task_id, category, artifact_payload, validation_spec)
    assert report.passed is False
    assert report.validation_details["schema_valid"] is False
    assert report.error_message is not None


@pytest.mark.asyncio
async def test_verify_deliverable_query_bot():
    """Verify query validator bot with ground-truth keywords and regex assertions."""
    task_id = "task_query_sprint_04"
    category = "query"
    artifact_payload = {
        "submitted_text": "The latest finalized block hash is 0x7f9a8b1c2d3e4f5a6b7c8d9e0f1a2b3c4d5e6f7a8b9c0d1e2f3a4b5c6d7e8f9a with 128 active validators."
    }
    validation_spec = {
        "required_keywords": ["block hash", "validators"],
        "regex_patterns": [r"0x[a-fA-F0-9]{64}"],
        "ground_truth_entities": ["128", "validators"]
    }

    report = await verify_deliverable(task_id, category, artifact_payload, validation_spec)
    assert report.passed is True
    assert report.score >= 0.80
    assert report.validation_details["constraint_score"] == 1.0


# =========================================================================
# 2. SECURITY HARDENING TESTS (AST eval/exec/__import__/__subclasses__)
# =========================================================================

@pytest.mark.asyncio
async def test_coding_verifier_blocks_eval():
    """AST check catches dynamic eval() call and triggers slashing."""
    task = TaskManifest(
        task_id="sec_eval_01",
        task_type="coding",
        prompt="Safe computation"
    )
    deliverable = DeliverablePayload(
        task_id="sec_eval_01",
        submitted_code="""
def compute():
    return eval("2 + 2")
"""
    )
    result = await evaluate_task(task, deliverable)
    assert result.verdict == "FAIL"
    assert result.score == 0.0
    assert result.slashing_recommended is True
    assert "SecurityViolation" in result.proof_logs
    assert "eval" in result.proof_logs


@pytest.mark.asyncio
async def test_coding_verifier_blocks_exec():
    """AST check catches exec() call and triggers slashing."""
    task = TaskManifest(
        task_id="sec_exec_02",
        task_type="coding",
        prompt="Safe computation"
    )
    deliverable = DeliverablePayload(
        task_id="sec_exec_02",
        submitted_code="""
def run_code():
    exec("x = 10")
"""
    )
    result = await evaluate_task(task, deliverable)
    assert result.verdict == "FAIL"
    assert result.score == 0.0
    assert result.slashing_recommended is True
    assert "SecurityViolation" in result.proof_logs
    assert "exec" in result.proof_logs


@pytest.mark.asyncio
async def test_coding_verifier_blocks_dynamic_import():
    """AST check catches __import__() call and triggers slashing."""
    task = TaskManifest(
        task_id="sec_imp_03",
        task_type="coding",
        prompt="Safe computation"
    )
    deliverable = DeliverablePayload(
        task_id="sec_imp_03",
        submitted_code="""
def sneaky():
    mod = __import__("os")
    return mod.name
"""
    )
    result = await evaluate_task(task, deliverable)
    assert result.verdict == "FAIL"
    assert result.score == 0.0
    assert result.slashing_recommended is True
    assert "SecurityViolation" in result.proof_logs
    assert "__import__" in result.proof_logs


@pytest.mark.asyncio
async def test_coding_verifier_blocks_subclasses_introspection():
    """AST check blocks __subclasses__ gadget chains."""
    task = TaskManifest(
        task_id="sec_sub_04",
        task_type="coding",
        prompt="Safe computation"
    )
    deliverable = DeliverablePayload(
        task_id="sec_sub_04",
        submitted_code="""
def exploit():
    return ().__class__.__bases__[0].__subclasses__()
"""
    )
    result = await evaluate_task(task, deliverable)
    assert result.verdict == "FAIL"
    assert result.score == 0.0
    assert result.slashing_recommended is True
    assert "SecurityViolation" in result.proof_logs


# =========================================================================
# 3. THREAD-SAFE SYNC RUNNER IN RUNNING EVENT LOOP
# =========================================================================

def test_sync_runner_standalone():
    """Test verify_deliverable_sync in standard synchronous context."""
    task_id = "task_sync_01"
    category = "query"
    artifact_payload = {"submitted_text": "Finalized payment confirmation."}
    validation_spec = {"required_keywords": ["payment"]}

    report = verify_deliverable_sync(task_id, category, artifact_payload, validation_spec)
    assert isinstance(report, VerificationReport)
    assert report.passed is True


@pytest.mark.asyncio
async def test_sync_runner_inside_active_async_loop():
    """Test verify_deliverable_sync when called inside an already running event loop."""
    task_id = "task_sync_02"
    category = "query"
    artifact_payload = {"submitted_text": "Active event loop execution test."}
    validation_spec = {"required_keywords": ["event loop"]}

    # This calls sync runner while the test's asyncio loop is active
    report = verify_deliverable_sync(task_id, category, artifact_payload, validation_spec)
    assert isinstance(report, VerificationReport)
    assert report.passed is True


# =========================================================================
# 4. EXISTING COMPREHENSIVE SUITE REGRESSION CHECKS
# =========================================================================

@pytest.mark.asyncio
async def test_coding_verifier_valid_submission():
    task = TaskManifest(
        task_id="task_code_001",
        task_type="coding",
        prompt="Write a function `add(a, b)` that returns the sum.",
        test_suite="from solution import add\ndef test_add(): assert add(2, 3) == 5"
    )
    deliverable = DeliverablePayload(
        task_id="task_code_001",
        submitted_code="def add(a: int, b: int) -> int: return a + b"
    )
    result = await evaluate_task(task, deliverable)
    assert result.verdict == "PASS"
    assert result.score == 1.0


@pytest.mark.asyncio
async def test_coding_verifier_timeout_slashed():
    task = TaskManifest(
        task_id="task_code_004",
        task_type="coding",
        prompt="Infinite loop",
        constraints={"timeout_sec": 1.0}
    )
    deliverable = DeliverablePayload(
        task_id="task_code_004",
        submitted_code="import time\nwhile True: time.sleep(0.1)"
    )
    result = await evaluate_task(task, deliverable)
    assert result.verdict == "FAIL"
    assert result.slashing_recommended is True


@pytest.mark.asyncio
async def test_researcher_verifier_grounded_report():
    task = TaskManifest(
        task_id="task_res_001",
        task_type="research",
        prompt="Summarize Ethereum settlement.",
        ground_truth_references=["https://arxiv.org/abs/2301.00001", "Ethereum settlement protocol requires 2/3"],
        constraints={"min_words": 10, "require_citations": True}
    )
    deliverable = DeliverablePayload(
        task_id="task_res_001",
        submitted_text="The Ethereum settlement protocol requires 2/3 consensus.",
        citations=[{"claim": "consensus", "source": "https://arxiv.org/abs/2301.00001"}]
    )
    result = await evaluate_task(task, deliverable)
    assert result.verdict == "PASS"
    assert result.score >= 0.80


@pytest.mark.asyncio
async def test_dispatcher_backend_payload():
    task = TaskManifest(
        task_id="task_dispatch_001",
        task_type="general",
        prompt="Echo test keyword: alpha_protocol",
        constraints={"required_keywords": ["alpha_protocol"]}
    )
    deliverable = DeliverablePayload(
        task_id="task_dispatch_001",
        submitted_text="Verification of alpha_protocol is complete."
    )
    result = await evaluate_task(task, deliverable)
    assert result.verdict == "PASS"
    payload = atoa_submit_verdict(result)
    assert payload["task_id"] == "task_dispatch_001"
    assert payload["verdict"] == "PASS"


def test_cli_execution(tmp_path):
    """Test CLI runner via subprocess with JSON files."""
    import json
    import subprocess
    import sys

    manifest_file = tmp_path / "manifest.json"
    deliverable_file = tmp_path / "deliverable.json"
    output_file = tmp_path / "result.json"

    manifest_data = {
        "task_id": "cli_task_01",
        "task_type": "coding",
        "prompt": "Return square of number",
        "test_suite": "from solution import sq\ndef test_sq(): assert sq(3) == 9"
    }
    deliverable_data = {
        "task_id": "cli_task_01",
        "submitted_code": "def sq(n): return n * n"
    }

    manifest_file.write_text(json.dumps(manifest_data), encoding="utf-8")
    deliverable_file.write_text(json.dumps(deliverable_data), encoding="utf-8")

    cmd = [
        sys.executable,
        "-m",
        "engine.verifier_engine",
        "--manifest", str(manifest_file),
        "--deliverable", str(deliverable_file),
        "--output", str(output_file)
    ]
    res = subprocess.run(cmd, capture_output=True, text=True)
    assert res.returncode == 0
    assert output_file.exists()

    result_json = json.loads(output_file.read_text(encoding="utf-8"))
    assert result_json["task_id"] == "cli_task_01"
    assert result_json["verdict"] == "PASS"
    assert result_json["score"] == 1.0


# =========================================================================
# 5. PLAN 002: PROCESS GROUP CLEANUP & LIVE QUERY SEARCH TESTS
# =========================================================================

@pytest.mark.asyncio
async def test_process_tree_cleanup_on_timeout():
    """Verify that process tree termination terminates lingering subprocesses cleanly."""
    task = TaskManifest(
        task_id="task_proc_tree_01",
        task_type="coding",
        prompt="Process tree timeout test",
        constraints={"timeout_sec": 1.0, "allow_subprocess": True}
    )
    deliverable = DeliverablePayload(
        task_id="task_proc_tree_01",
        submitted_code="""
import time
import sys
# Spawn or run long loop
while True:
    time.sleep(0.05)
"""
    )
    result = await evaluate_task(task, deliverable)
    assert result.verdict == "FAIL"
    assert result.benchmark_metrics["timed_out"] is True
    assert result.slashing_recommended is True


@pytest.mark.asyncio
async def test_query_validator_live_search_enrichment(monkeypatch):
    """Verify that QueryValidatorBot enriches ground truth when live search is enabled."""
    from engine.verifiers.query_matcher import resolve_query_ground_truth

    # Mock the web search resolver to return deterministic ground truth entities for test
    def mock_fetch(query: str):
        return ["Solana", "Proof of History", "65000 TPS", "Anatoly Yakovenko"]

    monkeypatch.setattr("engine.verifiers.query_matcher.resolve_query_ground_truth", mock_fetch)

    task_id = "task_live_query_01"
    category = "query"
    artifact_payload = {
        "submitted_text": "Solana achieves up to 65000 TPS using Proof of History designed by Anatoly Yakovenko."
    }
    validation_spec = {
        "prompt": "What is Solana throughput and consensus mechanism?",
        "enable_live_search": True,
        "required_keywords": ["Solana"]
    }

    report = await verify_deliverable(task_id, category, artifact_payload, validation_spec)
    assert report.passed is True
    assert report.score >= 0.85
    assert report.validation_details["live_search_enabled"] is True
    assert len(report.validation_details["ground_truth_entities"]) >= 4


# =========================================================================
# 6. PLAN 003: TELEMETRY ENRICHMENT & HASH DETERMINISM TESTS
# =========================================================================

@pytest.mark.asyncio
async def test_failure_telemetry_categorization():
    """Verify that failure_category is accurately injected into validation_details."""
    # 1. Security Violation
    rep_sec = await verify_deliverable(
        "task_telemetry_01",
        "code_generation",
        {"submitted_code": "import ctypes\ndef f(): pass"},
        {"test_suite": "assert True"}
    )
    assert rep_sec.passed is False
    assert rep_sec.validation_details.get("failure_category") == "SECURITY_VIOLATION"

    # 2. Timeout
    rep_timeout = await verify_deliverable(
        "task_telemetry_02",
        "code_generation",
        {"submitted_code": "import time\nwhile True: time.sleep(0.01)"},
        {"timeout_seconds": 0.5}
    )
    assert rep_timeout.passed is False
    assert rep_timeout.validation_details.get("failure_category") == "TIMEOUT"

    # 3. Schema Mismatch
    rep_schema = await verify_deliverable(
        "task_telemetry_03",
        "research",
        {"submitted_data": {"wrong_field": 123}},
        {"schema": {"type": "object", "required": ["expected_field"]}}
    )
    assert rep_schema.passed is False
    assert rep_schema.validation_details.get("failure_category") == "SCHEMA_MISMATCH"

    # 4. Success (NONE)
    rep_pass = await verify_deliverable(
        "task_telemetry_04",
        "query",
        {"submitted_text": "Ethereum network"},
        {"required_keywords": ["Ethereum"]}
    )
    assert rep_pass.passed is True
    assert rep_pass.validation_details.get("failure_category") == "NONE"


@pytest.mark.asyncio
async def test_sandbox_deterministic_hash_seed():
    """Verify that PYTHONHASHSEED is set to '0' during sandbox code execution."""
    task_id = "task_hash_01"
    category = "code_generation"
    artifact_payload = {
        "submitted_code": """
import os
def check_hash_seed():
    return os.environ.get("PYTHONHASHSEED", "")
"""
    }
    validation_spec = {
        "test_suite": """
from solution import check_hash_seed
def test_seed():
    assert check_hash_seed() == "0"
"""
    }

    report = await verify_deliverable(task_id, category, artifact_payload, validation_spec)
    assert report.passed is True
    assert report.score == 1.0



