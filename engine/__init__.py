"""
ATOA Verifier / Evaluator Agent Engine Package.
"""
from engine.models import TaskManifest, DeliverablePayload, EvaluationResult, VerificationReport
from engine.verifier_engine import evaluate_task, evaluate_task_sync, atoa_submit_verdict

__all__ = [
    "TaskManifest", 
    "DeliverablePayload", 
    "EvaluationResult", 
    "VerificationReport",
    "evaluate_task",
    "evaluate_task_sync",
    "atoa_submit_verdict",
]
