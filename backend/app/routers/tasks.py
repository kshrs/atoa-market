"""
ATOA Tasks & Bidding Router (Part 1: Discovery & Creation).
Handles publishing tasks with escrow reservation and querying tasks with granular filters.
"""

from typing import List, Optional
from fastapi import APIRouter, HTTPException, Query, status

from backend.app.models import (
    TaskCreate,
    TaskResponse,
    TaskCategory,
    TaskStatus,
    EventType,
)
from backend.app.state import state_store
from backend.app.routers.events import ws_manager

router = APIRouter(prefix="/v1/tasks", tags=["tasks"])


@router.post("", response_model=TaskResponse, status_code=status.HTTP_201_CREATED)
async def create_task(task_in: TaskCreate):
    """
    Publish a new task to the network.
    1. Validates requester wallet and balance.
    2. Locks budget in escrow state.
    3. Broadcasts TASK_CREATED event to WebSocket observers.
    """
    # 1. Check & ensure requester wallet exists
    wallet = await state_store.get_or_create_wallet(
        address=task_in.requester_address,
        role="Requester"
    )
    
    # 2. Lock escrow budget
    escrow_locked = await state_store.lock_wallet_escrow(
        address=task_in.requester_address,
        amount=task_in.budget_usdc
    )
    if not escrow_locked:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Insufficient balance in requester wallet ({wallet.balance_usdc} USDC) to fund task budget ({task_in.budget_usdc} USDC)."
        )
    
    # 3. Create task record
    task = await state_store.create_task(task_in)
    
    # 4. Broadcast live telemetry event
    await ws_manager.broadcast_event(
        event_type=EventType.TASK_CREATED,
        data={
            "task_id": task.task_id,
            "title": task.title,
            "category": task.category.value,
            "budget_usdc": task.budget_usdc,
            "required_worker_bond": task.required_worker_bond,
            "requester_address": task.requester_address,
            "status": task.status.value,
            "created_at": task.created_at,
        }
    )
    
    return task


@router.get("", response_model=List[TaskResponse])
async def list_tasks(
    category: Optional[TaskCategory] = Query(None, description="Filter by task category"),
    status: Optional[TaskStatus] = Query(None, description="Filter by task status (e.g. BROADCASTED, MATCHING, IN_PROGRESS)"),
    min_budget: Optional[float] = Query(None, description="Filter by minimum USDC budget")
):
    """
    List tasks available across the network with optional filters.
    Used by Worker Agents (`agy-cli`) and the frontend dashboard (`nvss`).
    """
    return await state_store.list_tasks(
        category=category,
        status=status,
        min_budget=min_budget
    )


@router.get("/{task_id}", response_model=TaskResponse)
async def get_task(task_id: str):
    """Retrieve detailed state of a specific task."""
    task = await state_store.get_task(task_id)
    if not task:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Task with ID '{task_id}' not found."
        )
    return task


# ---------------------------------------------------------------------------
# Bidding & Matchmaking Endpoints (Part 2)
# ---------------------------------------------------------------------------

from backend.app.models import (
    BidCreate,
    BidResponse,
)


@router.post("/{task_id}/bids", response_model=BidResponse, status_code=status.HTTP_201_CREATED)
async def submit_bid(task_id: str, bid_in: BidCreate):
    """
    Submit a bid for an open task.
    1. Checks that the task exists and is in BROADCASTED or MATCHING state.
    2. Validates worker wallet balance for the required collateral bond.
    3. Locks collateral bond from worker balance.
    4. Records bid and broadcasts BID_PLACED event.
    """
    task = await state_store.get_task(task_id)
    if not task:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Task with ID '{task_id}' not found."
        )
    if task.status not in [TaskStatus.BROADCASTED, TaskStatus.MATCHING]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Task is in '{task.status.value}' state and is not accepting bids."
        )
    
    # Ensure worker has enough collateral bond
    if bid_in.collateral_bond_locked < task.required_worker_bond:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Collateral bond ({bid_in.collateral_bond_locked} USDC) is less than required bond ({task.required_worker_bond} USDC)."
        )
    
    worker_wallet = await state_store.get_or_create_wallet(
        address=bid_in.worker_address,
        role="Worker"
    )
    
    bond_locked = await state_store.lock_worker_bond(
        address=bid_in.worker_address,
        bond_amount=bid_in.collateral_bond_locked
    )
    if not bond_locked:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Insufficient balance in worker wallet ({worker_wallet.balance_usdc} USDC) to lock collateral bond ({bid_in.collateral_bond_locked} USDC)."
        )
    
    # Record bid in state
    bid = await state_store.add_bid(task_id, bid_in)
    if not bid:
        # Refund bond if adding bid failed
        await state_store.unlock_worker_bond(bid_in.worker_address, bid_in.collateral_bond_locked)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Failed to record bid on task."
        )
    
    # Broadcast live telemetry event
    await ws_manager.broadcast_event(
        event_type=EventType.BID_PLACED,
        data={
            "task_id": task_id,
            "bid_id": bid.bid_id,
            "worker_address": bid.worker_address,
            "bid_price_usdc": bid.bid_price_usdc,
            "collateral_bond_locked": bid.collateral_bond_locked,
            "worker_reputation_score": bid.worker_reputation_score,
            "estimated_duration_seconds": bid.estimated_duration_seconds,
            "created_at": bid.created_at,
        }
    )
    
    return bid


@router.get("/{task_id}/bids", response_model=List[BidResponse])
async def list_task_bids(task_id: str):
    """List all bids submitted for a specific task."""
    task = await state_store.get_task(task_id)
    if not task:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Task with ID '{task_id}' not found."
        )
    return await state_store.get_task_bids(task_id)


@router.post("/{task_id}/assign", response_model=TaskResponse)
async def assign_task(
    task_id: str,
    selected_bid_id: Optional[str] = Query(None, description="Optional specific bid ID. If omitted, automated matchmaking selects the optimal bid.")
):
    """
    Triggers matchmaking for the task:
    - If selected_bid_id is provided, assigns to that specific worker.
    - Otherwise, automatically selects best bid balancing reputation, price, and latency.
    - Transitions task to IN_PROGRESS.
    - Refunds collateral bonds for non-winning bidders.
    - Broadcasts TASK_ASSIGNED event.
    """
    winning_bid = await state_store.assign_winning_bid(task_id, selected_bid_id)
    if not winning_bid:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Could not assign task. Verify that the task exists, is in BROADCASTED/MATCHING state, and has valid bids."
        )
    
    task = await state_store.get_task(task_id)
    
    # Broadcast live telemetry event
    await ws_manager.broadcast_event(
        event_type=EventType.TASK_ASSIGNED,
        data={
            "task_id": task_id,
            "assigned_worker": winning_bid.worker_address,
            "accepted_bid_id": winning_bid.bid_id,
            "final_price_usdc": winning_bid.bid_price_usdc,
            "worker_bond_locked": winning_bid.collateral_bond_locked,
            "status": task.status.value,
            "updated_at": task.updated_at,
        }
    )
    
    return task


# ---------------------------------------------------------------------------
# Deliverables & Settlement Pipeline (Part 3)
# ---------------------------------------------------------------------------

from backend.app.models import DeliverableSubmission, VerificationReport
from backend.app.services.verification_oracle import verification_oracle
from backend.app.services.web3_escrow import web3_service


@router.post("/{task_id}/deliverables", response_model=TaskResponse)
async def submit_deliverable(task_id: str, submission: DeliverableSubmission):
    """
    Submit completed task deliverable (code, research JSON, or query answer).
    1. Validates that task exists and is in IN_PROGRESS state.
    2. Verifies that the submitting worker is the assigned worker.
    3. Runs programmatic verification oracle across the task's category.
    4. IF PASS:
       - Triggers Web3 payout & returns worker collateral bond.
       - Credits worker wallet balance (+payout) and reputation (+5).
       - Broadcasts PAYOUT_SETTLED event.
    5. IF FAIL:
       - Triggers Web3 slashing of worker bond.
       - Slashes worker wallet collateral & slashes reputation (-20).
       - Refunds escrow budget back to requester.
       - Broadcasts WORKER_SLASHED event.
    """
    task = await state_store.get_task(task_id)
    if not task:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Task with ID '{task_id}' not found."
        )
    if task.status != TaskStatus.IN_PROGRESS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Task is in '{task.status.value}' state and cannot accept deliverables. Must be 'IN_PROGRESS'."
        )
    if task.assigned_worker and task.assigned_worker != submission.worker_address:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Worker '{submission.worker_address}' is not assigned to this task. Assigned to: '{task.assigned_worker}'."
        )
    
    # 1. Record deliverable and set state to VERIFYING
    await state_store.record_deliverable(submission)
    
    await ws_manager.broadcast_event(
        event_type=EventType.DELIVERABLE_SUBMITTED,
        data={
            "task_id": task_id,
            "worker_address": submission.worker_address,
            "category": task.category.value,
            "status": TaskStatus.VERIFYING.value,
        }
    )
    
    # 2. Run programmatic verification oracle
    report: VerificationReport = await verification_oracle.verify_deliverable(
        task_id=task_id,
        category=task.category,
        artifact_payload=submission.artifact_payload,
        validation_spec=task.validation_spec
    )
    
    # Broadcast verification report
    await ws_manager.broadcast_event(
        event_type=EventType.VERIFICATION_COMPLETED,
        data={
            "task_id": task_id,
            "category": task.category.value,
            "passed": report.passed,
            "score": report.score,
            "error_message": report.error_message,
            "logs": report.logs,
        }
    )
    
    # 3. Handle Settlement or Slashing based on verification verdict
    if report.passed:
        # Payout & Settlement Path
        tx = await web3_service.settle_successful_payout(
            task_id=task_id,
            worker_address=submission.worker_address,
            payout_usdc=task.budget_usdc
        )
        
        # Credit worker and return collateral bond
        await state_store.credit_payout(submission.worker_address, task.budget_usdc)
        await state_store.unlock_worker_bond(submission.worker_address, task.required_worker_bond)
        
        task = await state_store.record_verification_and_settle(
            task_id=task_id,
            report=report,
            settlement_tx_hash=tx.get("tx_hash")
        )
        
        # Broadcast settlement event
        await ws_manager.broadcast_event(
            event_type=EventType.PAYOUT_SETTLED,
            data={
                "task_id": task_id,
                "worker_address": submission.worker_address,
                "payout_amount_usdc": task.budget_usdc,
                "worker_bond_returned": task.required_worker_bond,
                "tx_hash": tx.get("tx_hash"),
                "status": TaskStatus.SETTLED.value,
            }
        )
    else:
        # Slashing Path (Malicious / Failed submission)
        tx = await web3_service.execute_slash(
            task_id=task_id,
            worker_address=submission.worker_address,
            requester_address=task.requester_address,
            bond_amount_usdc=task.required_worker_bond
        )
        
        # Slash worker collateral bond and refund requester escrow
        await state_store.slash_worker(
            worker_address=submission.worker_address,
            requester_address=task.requester_address,
            bond_amount=task.required_worker_bond
        )
        await state_store.refund_requester_escrow(task.requester_address, task.budget_usdc)
        
        task = await state_store.record_verification_and_settle(
            task_id=task_id,
            report=report,
            settlement_tx_hash=tx.get("tx_hash")
        )
        
        # Broadcast slashing event
        await ws_manager.broadcast_event(
            event_type=EventType.WORKER_SLASHED,
            data={
                "task_id": task_id,
                "worker_address": submission.worker_address,
                "requester_address": task.requester_address,
                "slashed_bond_usdc": task.required_worker_bond,
                "escrow_refunded_usdc": task.budget_usdc,
                "reason": report.error_message or "Failed programmatic verification criteria.",
                "tx_hash": tx.get("tx_hash"),
                "status": TaskStatus.SLASHED.value,
            }
        )
        
    return task
