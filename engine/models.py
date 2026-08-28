"""
Core Data Models for the ATOA Autonomous Verifier / Evaluator Engine.
Aligned with ATOA Engineering Sprint 4-Developer Work Split-Up Spec.
"""
import time
from typing import Literal, Dict, Any, List, Optional
from pydantic import BaseModel, Field


class TaskManifest(BaseModel):
    task_id: str
    task_type: Literal["code_generation", "coding", "research", "query", "query_matching", "general"] = "general"
    prompt: str = ""
    spec_schema: Optional[Dict[str, Any]] = None
    constraints: Dict[str, Any] = Field(default_factory=dict)
    test_suite: Optional[str] = None  # python test code or assertions
    ground_truth_references: List[str] = Field(default_factory=list)
    slashing_threshold: float = 0.30  # Below this score, trigger slashing recommendation
    passing_threshold: float = 0.80   # Equal or above this score -> PASS


class DeliverablePayload(BaseModel):
    task_id: str
    worker_id: Optional[str] = None
    task_type: Optional[Literal["code_generation", "coding", "research", "query", "query_matching", "general"]] = None
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


class VerificationReport(BaseModel):
    """
    Formal I/O Contract Return Schema for Developer `bk` (Programmatic Verification Bots)
    consumed directly by `kshrs` (Lead Backend & MCP) to trigger `ashb` on-chain escrow/slashing.
    """
    task_id: str
    category: str                 # "code_generation" | "research" | "query"
    passed: bool                  # True if deterministic criteria satisfied; False otherwise
    score: float                  # Quality score 0.0 to 1.0
    validation_details: Dict[str, Any] = Field(default_factory=dict)
    error_message: Optional[str] = None
    logs: str = ""
    timestamp: float = Field(default_factory=time.time)
