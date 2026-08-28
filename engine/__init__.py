"""
ATOA Verifier / Evaluator Agent Engine Package.
"""
from engine.models import TaskManifest, DeliverablePayload, EvaluationResult
from engine.verifier_engine import evaluate_task

__all__ = ["TaskManifest", "DeliverablePayload", "EvaluationResult", "evaluate_task"]
