"""
ATOA 3-Domain Programmatic Validator Oracle Bridge.
Delegates to the engine package (developed by bk) to run isolated AST security checks,
subprocess sandboxes, deep JSON schema validation, and live query matching.
"""

from typing import Dict, Any, Optional
from backend.app.models import TaskCategory, VerificationReport, ValidationSpec
from engine.verifier_engine import evaluate_task
from engine.models import TaskManifest, DeliverablePayload


class VerificationOracle:
    """Delegates evaluation to the engine package."""

    @staticmethod
    async def verify_deliverable(
        task_id: str,
        category: TaskCategory,
        artifact_payload: Dict[str, Any],
        validation_spec: ValidationSpec
    ) -> VerificationReport:
        # 1. Map ValidationSpec to TaskManifest
        test_suite = validation_spec.test_suite_code
        spec_schema = validation_spec.json_schema
        ground_truth = validation_spec.expected_keywords or []
        
        # Determine category string
        cat_str = category.value if hasattr(category, "value") else str(category)
        
        task_manifest = TaskManifest(
            task_id=task_id,
            task_type=cat_str if cat_str in ("code_generation", "coding", "research", "query", "query_matching") else "general",
            prompt=validation_spec.search_query or "",
            spec_schema=spec_schema,
            constraints={
                "required_keys": validation_spec.required_keys,
                "required_keywords": validation_spec.expected_keywords,
                "min_speedup_factor": validation_spec.min_speedup_factor,
            },
            test_suite=test_suite,
            ground_truth_references=ground_truth,
            passing_threshold=0.80,
            slashing_threshold=0.30,
        )

        # 2. Map artifact_payload to DeliverablePayload
        submitted_code = artifact_payload.get("source_code") or artifact_payload.get("submitted_code")
        submitted_data = artifact_payload.get("research_json") or artifact_payload.get("submitted_data")
        submitted_text = artifact_payload.get("answer") or artifact_payload.get("submitted_text")
        
        # If payload was dict without special keys, pass as submitted_data
        if submitted_data is None and not submitted_code and not submitted_text:
            submitted_data = artifact_payload

        deliverable = DeliverablePayload(
            task_id=task_id,
            task_type=cat_str if cat_str in ("code_generation", "coding", "research", "query", "query_matching") else "general",
            submitted_code=submitted_code,
            submitted_data=submitted_data if isinstance(submitted_data, dict) else None,
            submitted_text=submitted_text or (str(submitted_data) if submitted_data else ""),
            metadata=artifact_payload.get("metadata", {}),
        )

        # 3. Execute evaluation via engine
        eval_result = await evaluate_task(task_manifest, deliverable)

        # 4. Map EvaluationResult to backend VerificationReport
        passed = (eval_result.verdict == "PASS")
        error_msg = eval_result.details.get("error") if not passed else None
        
        return VerificationReport(
            task_id=task_id,
            category=category,
            passed=passed,
            score=eval_result.score,
            validation_details={
                "benchmark_metrics": eval_result.benchmark_metrics,
                "slashing_recommended": eval_result.slashing_recommended,
                "failure_category": eval_result.benchmark_metrics.get("failure_category", "NONE"),
            },
            error_message=error_msg,
            logs=eval_result.proof_logs,
        )


# Singleton verification oracle
verification_oracle = VerificationOracle()
