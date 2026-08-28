"""
Core Data Models for the ATOA Autonomous Verifier / Evaluator Engine.
"""
from typing import Literal, Dict, Any, List, Optional
from pydantic import BaseModel, Field


class TaskManifest(BaseModel):
    task_id: str
    task_type: Literal["coding", "research", "query_matching", "general"] = "general"
    prompt: str
    spec_schema: Optional[Dict[str, Any]] = None
    constraints: Dict[str, Any] = Field(default_factory=dict)
    # e.g., {"timeout_sec": 5.0, "max_memory_mb": 256, "passing_score": 0.8, "required_keywords": [...]}
    test_suite: Optional[str] = None  # python test code or assertions
    ground_truth_references: List[str] = Field(default_factory=list)
    slashing_threshold: float = 0.30  # Below this score, trigger slashing recommendation
    passing_threshold: float = 0.80   # Equal or above this score -> PASS


class DeliverablePayload(BaseModel):
    task_id: str
    worker_id: Optional[str] = None
    task_type: Optional[Literal["coding", "research", "query_matching", "general"]] = None
    submitted_code: Optional[str] = None
    submitted_files: Dict[str, str] = Field(default_factory=dict)  # filename -> content
    submitted_data: Optional[Dict[str, Any]] = None
    submitted_text: Optional[str] = None
    citations: List[Dict[str, str]] = Field(default_factory=list)  # [{"claim": "...", "source": "..."}]
    metadata: Dict[str, Any] = Field(default_factory=dict)


class EvaluationResult(BaseModel):
    task_id: str
    verdict: Literal["PASS", "FAIL"]
    score: float = Field(ge=0.0, le=1.0)  # 0.0 to 1.0
    benchmark_metrics: Dict[str, Any] = Field(default_factory=dict)
    proof_logs: str = ""
    slashing_recommended: bool = False
    details: Dict[str, Any] = Field(default_factory=dict)

    def to_backend_payload(self) -> Dict[str, Any]:
        """Format for backend /v1/evaluations and atoa_submit_verdict endpoint."""
        return {
            "task_id": self.task_id,
            "verdict": self.verdict,
            "score": round(self.score, 4),
            "benchmark_metrics": self.benchmark_metrics,
            "proof_logs": self.proof_logs,
            "slashing_recommended": self.slashing_recommended,
            "details": self.details,
        }
