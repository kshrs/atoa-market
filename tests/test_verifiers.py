"""
Comprehensive Test Suite for ATOA Autonomous Verification Engine.
Tests all verifiers: Coding, Researcher, Query/Spec Matcher, and Dispatcher.
"""
import pytest
import asyncio
from engine.models import TaskManifest, DeliverablePayload, EvaluationResult
from engine.verifier_engine import evaluate_task, atoa_submit_verdict


# =========================================================================
# 1. CODING VERIFIER TESTS
# =========================================================================

@pytest.mark.asyncio
async def test_coding_verifier_valid_submission():
    """Valid Python solution passes pytest suite and returns PASS."""
    task = TaskManifest(
        task_id="task_code_001",
        task_type="coding",
        prompt="Write a function `add(a, b)` that returns the sum.",
        test_suite="""
from solution import add
def test_add():
    assert add(2, 3) == 5
    assert add(-1, 1) == 0
    assert add(0, 0) == 0
"""
    )
    deliverable = DeliverablePayload(
        task_id="task_code_001",
        submitted_code="""
def add(a: int, b: int) -> int:
    return a + b
"""
    )

    result = await evaluate_task(task, deliverable)
    assert result.verdict == "PASS"
    assert result.score == 1.0
    assert not result.slashing_recommended
    assert result.benchmark_metrics["syntax_valid"] is True
    assert result.benchmark_metrics["ast_safe"] is True
    assert result.benchmark_metrics["returncode"] == 0
    assert "STDOUT" in result.proof_logs


@pytest.mark.asyncio
async def test_coding_verifier_failing_tests():
    """Incorrect solution fails unit tests and returns FAIL."""
    task = TaskManifest(
        task_id="task_code_002",
        task_type="coding",
        prompt="Write a function `multiply(a, b)`.",
        test_suite="""
from solution import multiply
def test_multiply():
    assert multiply(2, 3) == 6
    assert multiply(4, 5) == 20
"""
    )
    deliverable = DeliverablePayload(
        task_id="task_code_002",
        submitted_code="""
def multiply(a: int, b: int) -> int:
    return a + b  # Buggy implementation
"""
    )

    result = await evaluate_task(task, deliverable)
    assert result.verdict == "FAIL"
    assert result.score < 0.80
    assert result.benchmark_metrics["returncode"] != 0


@pytest.mark.asyncio
async def test_coding_verifier_malicious_code_slashed():
    """Malicious code attempting forbidden imports is caught in AST check and flagged for slashing."""
    task = TaskManifest(
        task_id="task_code_003",
        task_type="coding",
        prompt="Calculate factorial.",
        constraints={"allow_subprocess": False}
    )
    deliverable = DeliverablePayload(
        task_id="task_code_003",
        submitted_code="""
import ctypes
def evil():
    return 1
"""
    )

    result = await evaluate_task(task, deliverable)
    assert result.verdict == "FAIL"
    assert result.score == 0.0
    assert result.slashing_recommended is True
    assert "SecurityViolation" in result.proof_logs


@pytest.mark.asyncio
async def test_coding_verifier_timeout_slashed():
    """Code that enters an infinite loop times out and is flagged for slashing."""
    task = TaskManifest(
        task_id="task_code_004",
        task_type="coding",
        prompt="Quick sort implementation",
        constraints={"timeout_sec": 1.0}
    )
    deliverable = DeliverablePayload(
        task_id="task_code_004",
        submitted_code="""
import time
while True:
    time.sleep(0.1)
"""
    )

    result = await evaluate_task(task, deliverable)
    assert result.verdict == "FAIL"
    assert result.score == 0.0
    assert result.slashing_recommended is True
    assert result.benchmark_metrics["timed_out"] is True


# =========================================================================
# 2. RESEARCHER VERIFIER TESTS
# =========================================================================

@pytest.mark.asyncio
async def test_researcher_verifier_grounded_report():
    """Well-grounded research deliverable with valid citations passes."""
    ground_truth = [
        "https://arxiv.org/abs/2301.00001",
        "Ethereum settlement protocol requires 2/3 validator consensus",
        "Slashing mechanism burns 10% of staked collateral on double signing"
    ]
    task = TaskManifest(
        task_id="task_res_001",
        task_type="research",
        prompt="Summarize Ethereum settlement and slashing rules.",
        ground_truth_references=ground_truth,
        constraints={"min_words": 15, "require_citations": True}
    )
    deliverable = DeliverablePayload(
        task_id="task_res_001",
        submitted_text="The Ethereum settlement protocol requires 2/3 validator consensus for finality. Additionally, the slashing mechanism burns 10% of staked collateral on double signing violations.",
        citations=[
            {
                "claim": "2/3 validator consensus required",
                "source": "https://arxiv.org/abs/2301.00001"
            }
        ]
    )

    result = await evaluate_task(task, deliverable)
    assert result.verdict == "PASS"
    assert result.score >= 0.80
    assert not result.slashing_recommended
    assert result.benchmark_metrics["citations_valid"] == 1
    assert result.benchmark_metrics["grounding_score"] > 0.5


@pytest.mark.asyncio
async def test_researcher_verifier_hallucinated_report():
    """Ungrounded report with bogus citations receives low score and slashing trigger."""
    ground_truth = [
        "https://official-source.org/data",
        "Solana uses Proof of History clock synchronization"
    ]
    task = TaskManifest(
        task_id="task_res_002",
        task_type="research",
        prompt="Analyze Solana consensus.",
        ground_truth_references=ground_truth,
        constraints={"min_words": 20, "require_citations": True}
    )
    deliverable = DeliverablePayload(
        task_id="task_res_002",
        submitted_text="Totally unrelated content about cooking recipes with random cheese and pepper.",
        citations=[
            {
                "claim": "Solana baking temperature",
                "source": "invalid://not_a_valid_url"
            }
        ]
    )

    result = await evaluate_task(task, deliverable)
    assert result.verdict == "FAIL"
    assert result.score < 0.30
    assert result.slashing_recommended is True


# =========================================================================
# 3. QUERY & SPEC MATCHER VERIFIER TESTS
# =========================================================================

@pytest.mark.asyncio
async def test_matcher_verifier_strict_schema_pass():
    """Deliverable strictly matching JSON schema and keywords passes."""
    schema = {
        "type": "object",
        "required": ["agent_id", "reputation_score", "active_escrow"],
        "properties": {
            "agent_id": {"type": "string"},
            "reputation_score": {"type": "number"},
            "active_escrow": {"type": "boolean"},
        }
    }
    task = TaskManifest(
        task_id="task_match_001",
        task_type="query_matching",
        prompt="Generate an agent status report in JSON with required fields.",
        spec_schema=schema,
        constraints={"format": "json", "required_keywords": ["agent_id", "reputation_score"]}
    )
    deliverable = DeliverablePayload(
        task_id="task_match_001",
        submitted_data={
            "agent_id": "agent_alpha_99",
            "reputation_score": 0.98,
            "active_escrow": True
        }
    )

    result = await evaluate_task(task, deliverable)
    assert result.verdict == "PASS"
    assert result.score >= 0.80
    assert result.benchmark_metrics["schema_valid"] is True
    assert len(result.benchmark_metrics["missing_fields"]) == 0


@pytest.mark.asyncio
async def test_matcher_verifier_missing_schema_fail():
    """Deliverable with missing required fields fails verification."""
    schema = {
        "type": "object",
        "required": ["user_id", "balance"],
        "properties": {
            "user_id": {"type": "string"},
            "balance": {"type": "number"},
        }
    }
    task = TaskManifest(
        task_id="task_match_002",
        task_type="query_matching",
        prompt="Provide account balance.",
        spec_schema=schema
    )
    deliverable = DeliverablePayload(
        task_id="task_match_002",
        submitted_data={"user_id": "usr_123"}  # missing 'balance'
    )

    result = await evaluate_task(task, deliverable)
    assert result.verdict == "FAIL"
    assert result.benchmark_metrics["schema_valid"] is False
    assert any("balance" in err for err in result.benchmark_metrics["missing_fields"])


# =========================================================================
# 4. DISPATCHER & BACKEND ADAPTER PAYLOAD TEST
# =========================================================================

@pytest.mark.asyncio
async def test_coding_verifier_syntax_error():
    """Invalid syntax fails immediately."""
    task = TaskManifest(
        task_id="task_code_syn",
        task_type="coding",
        prompt="Write valid python function."
    )
    deliverable = DeliverablePayload(
        task_id="task_code_syn",
        submitted_code="def broken_func(:\n    pass"
    )
    result = await evaluate_task(task, deliverable)
    assert result.verdict == "FAIL"
    assert result.benchmark_metrics["syntax_valid"] is False
    assert "SyntaxError" in result.proof_logs


@pytest.mark.asyncio
async def test_coding_verifier_standalone_execution():
    """Standalone script executing cleanly passes."""
    task = TaskManifest(
        task_id="task_code_stand",
        task_type="coding",
        prompt="Print greeting."
    )
    deliverable = DeliverablePayload(
        task_id="task_code_stand",
        submitted_code="print('Hello ATOA Market')"
    )
    result = await evaluate_task(task, deliverable)
    assert result.verdict == "PASS"
    assert result.score == 1.0
    assert "Hello ATOA Market" in result.proof_logs


@pytest.mark.asyncio
async def test_researcher_verifier_missing_required_citations():
    """Missing required citations triggers failure."""
    task = TaskManifest(
        task_id="task_res_nocite",
        task_type="research",
        prompt="Explain zk-SNARKs.",
        constraints={"require_citations": True, "min_words": 10}
    )
    deliverable = DeliverablePayload(
        task_id="task_res_nocite",
        submitted_text="zk-SNARKs enable succinct zero knowledge proof verification on-chain.",
        citations=[]
    )
    result = await evaluate_task(task, deliverable)
    assert result.verdict == "FAIL"
    assert "Citations were required but none were provided" in result.proof_logs


@pytest.mark.asyncio
async def test_matcher_verifier_regex_constraints():
    """Regex pattern constraint verification."""
    task = TaskManifest(
        task_id="task_match_regex",
        task_type="query_matching",
        prompt="Provide Ethereum transaction hash and address.",
        constraints={
            "regex_patterns": [r"0x[a-fA-F0-9]{40}", r"0x[a-fA-F0-9]{64}"]
        }
    )
    # Valid matching deliverable
    deliverable_valid = DeliverablePayload(
        task_id="task_match_regex",
        submitted_text="Address: 0xd8dA6BF26964aF9D7eEd9e03E53415D37aA96045 Tx: 0x5c504ed432cb51138bcf09aa5e8a410dd4a1e204ef84bfed1be16dfba1b22060"
    )
    res_valid = await evaluate_task(task, deliverable_valid)
    assert res_valid.verdict == "PASS"

    # Invalid deliverable missing tx hash
    deliverable_invalid = DeliverablePayload(
        task_id="task_match_regex",
        submitted_text="Address: 0xd8dA6BF26964aF9D7eEd9e03E53415D37aA96045"
    )
    res_invalid = await evaluate_task(task, deliverable_invalid)
    assert res_invalid.benchmark_metrics["constraint_score"] < 1.0


@pytest.mark.asyncio
async def test_dispatcher_backend_payload():
    """Verify backend payload formatting for /v1/evaluations and atoa_submit_verdict."""
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
    assert "score" in payload
    assert "benchmark_metrics" in payload
    assert "proof_logs" in payload
    assert isinstance(payload["slashing_recommended"], bool)


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


