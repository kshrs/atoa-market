"""
ATOA Autonomous Verifier / Evaluator Engine.
Exposes the public evaluate_task interface, CLI runner, and backend API payload formatting.
"""
import argparse
import asyncio
import json
import sys
from typing import Dict, Any, Union, Optional
from engine.models import TaskManifest, DeliverablePayload, EvaluationResult
from engine.verifiers.dispatcher import dispatch_evaluation


async def evaluate_task(
    task_spec: Union[TaskManifest, Dict[str, Any]], 
    deliverable: Union[DeliverablePayload, Dict[str, Any]]
) -> EvaluationResult:
    """
    Evaluates a worker deliverable against a task specification.
    
    Args:
        task_spec: TaskManifest instance or dictionary representation.
        deliverable: DeliverablePayload instance or dictionary representation.

    Returns:
        EvaluationResult containing task_id, verdict ("PASS" / "FAIL"),
        score (0.0 - 1.0), benchmark metrics, and proof logs.
    """
    return await dispatch_evaluation(task_spec, deliverable)


def evaluate_task_sync(
    task_spec: Union[TaskManifest, Dict[str, Any]], 
    deliverable: Union[DeliverablePayload, Dict[str, Any]]
) -> EvaluationResult:
    """Synchronous wrapper for evaluate_task."""
    try:
        loop = asyncio.get_event_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
    
    if loop.is_running():
        # Running inside existing event loop
        import nest_asyncio  # if available or run in thread
        nest_asyncio.apply()
        return loop.run_until_complete(evaluate_task(task_spec, deliverable))
    else:
        return loop.run_until_complete(evaluate_task(task_spec, deliverable))


def atoa_submit_verdict(result: EvaluationResult) -> Dict[str, Any]:
    """
    Format evaluation result into the standard payload for the escrow & slashing vault backend.
    Compatible with POST /v1/evaluations
    """
    return result.to_backend_payload()


def main():
    """CLI runner for direct evaluation invocation."""
    parser = argparse.ArgumentParser(description="ATOA Verification Engine CLI")
    parser.add_argument("--manifest", type=str, required=True, help="Path to TaskManifest JSON file")
    parser.add_argument("--deliverable", type=str, required=True, help="Path to DeliverablePayload JSON file")
    parser.add_argument("--output", type=str, default=None, help="Optional output path for EvaluationResult JSON")

    args = parser.parse_args()

    with open(args.manifest, "r", encoding="utf-8") as f:
        task_data = json.load(f)
    with open(args.deliverable, "r", encoding="utf-8") as f:
        deliv_data = json.load(f)

    result = evaluate_task_sync(task_data, deliv_data)
    payload = atoa_submit_verdict(result)
    output_str = json.dumps(payload, indent=2)

    if args.output:
        with open(args.output, "w", encoding="utf-8") as f:
            f.write(output_str)
    else:
        print(output_str)

    sys.exit(0 if result.verdict == "PASS" else 1)


if __name__ == "__main__":
    main()
