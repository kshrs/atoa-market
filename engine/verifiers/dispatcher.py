"""
Verifier Dispatcher Module.
Routes evaluation tasks to specialized verification sub-modules based on task specifications.
"""
import logging
from typing import Dict, Any, Union
from engine.models import TaskManifest, DeliverablePayload, EvaluationResult
from engine.verifiers.coding import verify_coding
from engine.verifiers.researcher import verify_researcher
from engine.verifiers.query_matcher import verify_matcher

logger = logging.getLogger("atoa.verifier.dispatcher")


def _infer_task_type(task_spec: TaskManifest, deliverable: DeliverablePayload) -> str:
    """Infer task type if set to general or unspecified."""
    if task_spec.task_type and task_spec.task_type != "general":
        return task_spec.task_type
    if deliverable.task_type and deliverable.task_type != "general":
        return deliverable.task_type
    
    # Infer based on payload contents
    if deliverable.submitted_code or task_spec.test_suite or "solution.py" in deliverable.submitted_files:
        return "coding"
    if deliverable.citations or task_spec.ground_truth_references:
        return "research"
    if task_spec.spec_schema or task_spec.constraints.get("required_keywords"):
        return "query_matching"

    return "query_matching"


async def dispatch_evaluation(
    task_spec: Union[TaskManifest, Dict[str, Any]], 
    deliverable: Union[DeliverablePayload, Dict[str, Any]]
) -> EvaluationResult:
    """
    Unified entry point for task verification.
    """
    # Normalize inputs to Pydantic models if dict passed
    if isinstance(task_spec, dict):
        task_spec = TaskManifest(**task_spec)
    if isinstance(deliverable, dict):
        deliverable = DeliverablePayload(**deliverable)

    task_type = _infer_task_type(task_spec, deliverable)

    try:
        if task_type == "coding":
            return await verify_coding(task_spec, deliverable)
        elif task_type == "research":
            return await verify_researcher(task_spec, deliverable)
        elif task_type in ("query_matching", "general"):
            return await verify_matcher(task_spec, deliverable)
        else:
            return EvaluationResult(
                task_id=task_spec.task_id,
                verdict="FAIL",
                score=0.0,
                slashing_recommended=False,
                benchmark_metrics={"unsupported_type": task_type},
                proof_logs=f"FAIL: Unsupported task verification type '{task_type}'."
            )
    except Exception as ex:
        logger.exception(f"Unexpected error during verification of task {task_spec.task_id}: {ex}")
        return EvaluationResult(
            task_id=task_spec.task_id,
            verdict="FAIL",
            score=0.0,
            slashing_recommended=False,
            benchmark_metrics={"engine_exception": str(ex)},
            proof_logs=f"FAIL: Internal verification engine exception: {str(ex)}",
            details={"error": str(ex)}
        )
