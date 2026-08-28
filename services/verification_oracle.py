"""
Programmatic Verification Oracle Service for Developer `bk`.
Exposes verify_deliverable to kshrs (FastAPI Core & MCP Server) to trigger ashb on-chain settlement.
"""
import asyncio
import concurrent.futures
import time
from typing import Dict, Any, Optional
from engine.models import TaskManifest, DeliverablePayload, VerificationReport
from engine.verifiers.dispatcher import dispatch_evaluation


async def verify_deliverable(
    task_id: str,
    category: str,               # "code_generation" | "research" | "query"
    artifact_payload: dict,      # submitted code string, research JSON, or query answer
    validation_spec: dict        # test suite code, JSON schema, or search assertion rules
) -> VerificationReport:
    """
    Evaluates a worker deliverable using deterministic, rule-based validator bots (no LLM agents).
    
    Returns:
        VerificationReport matching the exact ATOA Sprint specification.
    """
    # 1. Construct TaskManifest from validation_spec
    test_suite = validation_spec.get("test_suite")
    spec_schema = validation_spec.get("schema") or validation_spec.get("spec_schema")
    ground_truth = validation_spec.get("ground_truth_references") or validation_spec.get("ground_truth_entities", [])
    
    task_spec = TaskManifest(
        task_id=task_id,
        task_type=category if category in ("code_generation", "coding", "research", "query", "query_matching") else "general",
        prompt=validation_spec.get("prompt", ""),
        spec_schema=spec_schema,
        constraints=validation_spec,
        test_suite=test_suite,
        ground_truth_references=ground_truth,
        passing_threshold=validation_spec.get("passing_threshold", 0.80),
        slashing_threshold=validation_spec.get("slashing_threshold", 0.30)
    )

    # 2. Construct DeliverablePayload from artifact_payload
    deliverable = DeliverablePayload(
        task_id=task_id,
        task_type=category if category in ("code_generation", "coding", "research", "query", "query_matching") else "general",
        submitted_code=artifact_payload.get("submitted_code") or artifact_payload.get("code"),
        submitted_files=artifact_payload.get("submitted_files", {}),
        submitted_data=artifact_payload.get("submitted_data") or artifact_payload.get("data"),
        submitted_text=artifact_payload.get("submitted_text") or artifact_payload.get("text") or artifact_payload.get("answer"),
        citations=artifact_payload.get("citations", []),
        metadata=artifact_payload.get("metadata", {})
    )

    # 3. Execute deterministic evaluation
    eval_result = await dispatch_evaluation(task_spec, deliverable)

    # 4. Construct formal VerificationReport
    passed = (eval_result.verdict == "PASS")
    err_msg = None
    if not passed:
        err_msg = eval_result.details.get("error")
        if not err_msg and eval_result.details.get("schema_errors"):
            err_msg = "; ".join(eval_result.details["schema_errors"])
        if not err_msg:
            err_msg = f"Verification failed with score {eval_result.score:.2f} (passing threshold: {task_spec.passing_threshold})"

    details = dict(eval_result.benchmark_metrics)
    if "failure_category" not in details:
        details["failure_category"] = "NONE" if passed else "EXECUTION_ERROR"

    return VerificationReport(
        task_id=task_id,
        category=category,
        passed=passed,
        score=eval_result.score,
        validation_details=details,
        error_message=err_msg,
        logs=eval_result.proof_logs,
        timestamp=time.time()
    )


def verify_deliverable_sync(
    task_id: str,
    category: str,
    artifact_payload: dict,
    validation_spec: dict
) -> VerificationReport:
    """
    Synchronous wrapper for verify_deliverable with thread-safe event loop execution.
    Uses stdlib ThreadPoolExecutor to prevent blocking or nested loop issues.
    """
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = None

    if loop and loop.is_running():
        # Execute inside a dedicated worker thread with its own event loop
        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
            future = pool.submit(
                asyncio.run, 
                verify_deliverable(task_id, category, artifact_payload, validation_spec)
            )
            return future.result()
    else:
        return asyncio.run(verify_deliverable(task_id, category, artifact_payload, validation_spec))
