"""
ATOA Protocol Data Models & Schemas (Pydantic v2).
Defines standard contracts for tasks, reverse-auction bids, deliverables, 
validation specifications, and real-time state telemetry events.
"""

from enum import Enum
from typing import Dict, Any, List, Optional
import time
import uuid
from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------

class TaskStatus(str, Enum):
    BROADCASTED = "BROADCASTED"
    MATCHING = "MATCHING"
    IN_PROGRESS = "IN_PROGRESS"
    VERIFYING = "VERIFYING"
    SETTLED = "SETTLED"
    SLASHED = "SLASHED"
    CANCELLED = "CANCELLED"


class TaskCategory(str, Enum):
    CODE_GENERATION = "code_generation"
    RESEARCH = "research"
    QUERY = "query"


class BidStatus(str, Enum):
    PENDING = "PENDING"
    ACCEPTED = "ACCEPTED"
    REJECTED = "REJECTED"


class EventType(str, Enum):
    TASK_CREATED = "TASK_CREATED"
    BID_PLACED = "BID_PLACED"
    TASK_ASSIGNED = "TASK_ASSIGNED"
    DELIVERABLE_SUBMITTED = "DELIVERABLE_SUBMITTED"
    VERIFICATION_COMPLETED = "VERIFICATION_COMPLETED"
    PAYOUT_SETTLED = "PAYOUT_SETTLED"
    WORKER_SLASHED = "WORKER_SLASHED"
    TASK_CANCELLED = "TASK_CANCELLED"
    WALLET_UPDATED = "WALLET_UPDATED"


# ---------------------------------------------------------------------------
# Task & Bid Models
# ---------------------------------------------------------------------------

class ValidationSpec(BaseModel):
    """Validation requirements depending on task category."""
    test_suite_code: Optional[str] = Field(default=None, description="PyTest / Unit test script")
    min_speedup_factor: Optional[float] = Field(default=1.0, description="Optional benchmark speedup factor")
    json_schema: Optional[Dict[str, Any]] = Field(default=None, description="JSON schema for structural validation")
    required_keys: Optional[List[str]] = Field(default_factory=list, description="Keys that must exist in research output")
    search_query: Optional[str] = Field(default=None, description="Web search query string for fact-checking")
    expected_keywords: Optional[List[str]] = Field(default_factory=list, description="Key factual terms/entities expected")


class BidCreate(BaseModel):
    worker_address: str = Field(..., json_schema_extra={"example": "0x3A2...6C4"})
    bid_price_usdc: float = Field(..., gt=0.0, json_schema_extra={"example": 42.0})
    collateral_bond_locked: float = Field(..., ge=0.0, json_schema_extra={"example": 5.0})
    estimated_duration_seconds: int = Field(default=60, gt=1)
    notes: Optional[str] = None


class BidResponse(BaseModel):
    bid_id: str = Field(default_factory=lambda: f"bid_{uuid.uuid4().hex[:8]}")
    task_id: str
    worker_address: str
    bid_price_usdc: float
    collateral_bond_locked: float
    estimated_duration_seconds: int
    notes: Optional[str] = None
    worker_reputation_score: float = 100.0
    status: BidStatus = BidStatus.PENDING
    created_at: float = Field(default_factory=time.time)


class TaskCreate(BaseModel):
    title: str = Field(..., min_length=3, max_length=200, example="Optimize Matrix Multiplication")
    category: TaskCategory = Field(..., example=TaskCategory.CODE_GENERATION)
    description: str = Field(..., min_length=5, example="Write an O(N^2.8) vectorized Strassen matrix multiplication routine.")
    budget_usdc: float = Field(..., gt=0.0, example=50.0)
    required_worker_bond: float = Field(..., ge=0.0, example=5.0)
    timeout_seconds: int = Field(default=300, ge=10, le=3600)
    requester_address: str = Field(..., example="0x1B4...9A8")
    validation_spec: ValidationSpec = Field(default_factory=ValidationSpec)


class TaskResponse(BaseModel):
    task_id: str = Field(default_factory=lambda: f"task_{uuid.uuid4().hex[:8]}")
    title: str
    category: TaskCategory
    description: str
    budget_usdc: float
    required_worker_bond: float
    timeout_seconds: int
    requester_address: str
    validation_spec: ValidationSpec
    status: TaskStatus = TaskStatus.BROADCASTED
    assigned_worker: Optional[str] = None
    winning_bid_id: Optional[str] = None
    escrow_locked: bool = False
    bids: List[BidResponse] = Field(default_factory=list)
    created_at: float = Field(default_factory=time.time)
    assigned_at: Optional[float] = None
    settled_at: Optional[float] = None


# ---------------------------------------------------------------------------
# Deliverable & Verification Models
# ---------------------------------------------------------------------------

class DeliverableSubmission(BaseModel):
    task_id: str
    worker_address: str
    artifact_payload: Dict[str, Any] = Field(
        ...,
        description="The deliverable data. E.g. {'source_code': '...'} or {'research_json': {...}} or {'answer': '...'}"
    )


class VerificationReport(BaseModel):
    task_id: str
    category: TaskCategory
    passed: bool
    score: float = Field(default=1.0, ge=0.0, le=1.0)
    validation_details: Dict[str, Any] = Field(default_factory=dict)
    error_message: Optional[str] = None
    logs: str = ""
    timestamp: float = Field(default_factory=time.time)


# ---------------------------------------------------------------------------
# Wallet & Reputation Models
# ---------------------------------------------------------------------------

class WalletState(BaseModel):
    address: str
    name: str
    role: str = Field(default="Bidder", description="Delegator | Bidder")
    balance_usdc: float = Field(default=1000.0, ge=0.0)
    locked_collateral_usdc: float = Field(default=0.0, ge=0.0)
    total_earned_usdc: float = Field(default=0.0, ge=0.0)
    total_slashed_usdc: float = Field(default=0.0, ge=0.0)
    reputation_score: float = Field(default=100.0, ge=0.0, le=1000.0)
    completed_tasks_count: int = 0
    failed_tasks_count: int = 0
    last_active_at: float = Field(default_factory=time.time)


# ---------------------------------------------------------------------------
# Global Analytics Model
# ---------------------------------------------------------------------------

class NetworkAnalytics(BaseModel):
    total_tasks_created: int = 0
    total_tasks_settled: int = 0
    total_tasks_slashed: int = 0
    total_volume_usdc: float = 0.0
    total_slashed_usdc: float = 0.0
    average_bids_per_task: float = 0.0
    active_workers_count: int = 0
