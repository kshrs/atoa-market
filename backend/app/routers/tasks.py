"""
ATOA Task Operations Router.
Covers task creation, bidding, matchmaking assignment, and deliverable settlement/slashing.
"""

from typing import List, Optional
from fastapi import APIRouter, HTTPException, Query, status
import time

from backend.app.models import (
    TaskCreate,
    TaskResponse,
    TaskStatus,
    TaskCategory,
    BidCreate,
    BidResponse,
    EventType,
    DeliverableSubmission,
    VerificationReport,
)
from backend.app.state import state_store
from backend.app.routers.events import ws_manager
from backend.app.services.verification_oracle import verification_oracle
from backend.app.services.web3_escrow import web3_service

router = APIRouter(prefix="/v1/tasks", tags=["tasks"])


# ---------------------------------------------------------------------------
# Task Discovery & Creation (Part 1)
# ---------------------------------------------------------------------------

@router.post("", response_model=TaskResponse, status_code=status.HTTP_201_CREATED)
async def create_task(task_in: TaskCreate):
    """
    Publish a new computational/research task to the marketplace.
    Locks the budget from the requester's wallet into escrow.
    """
    # 1. Ensure or create requester wallet
    wallet = await state_store.get_or_create_wallet(
        address=task_in.requester_address,
        role="Delegator"
    )
    
    # 2. Lock escrow funds
    locked = await state_store.lock_wallet_escrow(task_in.requester_address, task_in.budget_usdc)
    if not locked:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Insufficient balance in requester wallet '{task_in.requester_address}'. Available: {wallet.balance_usdc} USDC, Required: {task_in.budget_usdc} USDC"
        )
    
    # 3. Create task in state store
    task = await state_store.create_task(task_in)
    task.escrow_locked = True
    
    # 4. Broadcast live WebSocket event
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
    
    # Broadcast updated wallet
    w_updated = await state_store.get_wallet(task_in.requester_address)
    if w_updated:
        await ws_manager.broadcast_event(EventType.WALLET_UPDATED, data=w_updated.model_dump())
        
    return task


@router.get("", response_model=List[TaskResponse])
async def list_tasks(
    category: Optional[TaskCategory] = Query(None, description="Filter by task category"),
    status_filter: Optional[TaskStatus] = Query(None, alias="status", description="Filter by status")
):
    """List tasks on the marketplace."""
    return await state_store.list_tasks(category=category, status=status_filter)


@router.get("/{task_id}", response_model=TaskResponse)
async def get_task(task_id: str):
    """Retrieve details for a specific task."""
    task = await state_store.get_task(task_id)
    if not task:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Task with ID '{task_id}' not found."
        )
    return task


# ---------------------------------------------------------------------------
# Reverse Auction & Bidding (Part 2)
# ---------------------------------------------------------------------------

@router.post("/{task_id}/bids", response_model=BidResponse, status_code=status.HTTP_201_CREATED)
async def place_bid(task_id: str, bid_in: BidCreate):
    """
    Worker places a bid with collateral bond.
    Locks collateral bond from worker wallet.
    """
    task = await state_store.get_task(task_id)
    if not task:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Task '{task_id}' not found."
        )
    if task.status not in [TaskStatus.BROADCASTED, TaskStatus.MATCHING]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Task is in '{task.status.value}' state and is not accepting bids."
        )
    if bid_in.collateral_bond_locked < task.required_worker_bond:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Collateral bond too low. Required: {task.required_worker_bond} USDC, Provided: {bid_in.collateral_bond_locked} USDC"
        )
    
    # 1. Ensure or create worker wallet
    wallet = await state_store.get_or_create_wallet(
        address=bid_in.worker_address,
        role="Bidder"
    )
    
    # 2. Lock worker collateral bond
    locked = await state_store.lock_worker_bond(bid_in.worker_address, bid_in.collateral_bond_locked)
    if not locked:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Insufficient balance in worker wallet '{bid_in.worker_address}'. Available: {wallet.balance_usdc} USDC, Required Bond: {bid_in.collateral_bond_locked} USDC"
        )
        
    # 3. Record bid
    bid = await state_store.add_bid(task_id, bid_in)
    
    # 4. Broadcast event
    await ws_manager.broadcast_event(
        event_type=EventType.BID_PLACED,
        data={
            "task_id": task_id,
            "bid_id": bid.bid_id,
            "worker_address": bid.worker_address,
            "bid_price_usdc": bid.bid_price_usdc,
            "collateral_bond_locked": bid.collateral_bond_locked,
            "worker_reputation_score": bid.worker_reputation_score,
            "status": task.status.value,
        }
    )
    
    # Broadcast updated wallet
    w_updated = await state_store.get_wallet(bid_in.worker_address)
    if w_updated:
        await ws_manager.broadcast_event(EventType.WALLET_UPDATED, data=w_updated.model_dump())
        
    return bid


@router.get("/{task_id}/bids", response_model=List[BidResponse])
async def get_task_bids(task_id: str):
    """Retrieve all bids submitted for a task."""
    return await state_store.get_task_bids(task_id)


@router.post("/{task_id}/assign", response_model=TaskResponse)
async def assign_task(
    task_id: str,
    selected_bid_id: Optional[str] = Query(None, description="Optional specific bid ID")
):
    """Matchmaking assigns winning bidder to task."""
    task = await state_store.assign_winning_bid(task_id, selected_bid_id)
    if not task:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Could not assign task. Verify that the task exists, is in BROADCASTED/MATCHING state, and has valid bids."
        )
    
    winning_bid = next((b for b in task.bids if b.status.value == "ACCEPTED" or b.bid_id == task.winning_bid_id), None)
    
    await ws_manager.broadcast_event(
        event_type=EventType.TASK_ASSIGNED,
        data={
            "task_id": task_id,
            "assigned_worker": task.assigned_worker,
            "accepted_bid_id": task.winning_bid_id,
            "final_price_usdc": winning_bid.bid_price_usdc if winning_bid else task.budget_usdc,
            "worker_bond_locked": winning_bid.collateral_bond_locked if winning_bid else task.required_worker_bond,
            "status": task.status.value,
            "updated_at": task.updated_at,
        }
    )
    
    return task


# ---------------------------------------------------------------------------
# Deliverables & Settlement Pipeline (Part 3)
# ---------------------------------------------------------------------------

@router.post("/{task_id}/deliverables", response_model=TaskResponse)
async def submit_deliverable(task_id: str, submission: DeliverableSubmission):
    """
    Submit completed task deliverable.
    - Runs programmatic verification.
    - If PASS: Winner gains payout USDC + returns bond.
    - If FAIL: Worker is slashed and escrow refunded to Delegator.
    """
    task = await state_store.get_task(task_id)
    if not task:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Task '{task_id}' not found."
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
    
    # 2. Run verification oracle
    report: VerificationReport = await verification_oracle.verify_deliverable(
        task_id=task_id,
        category=task.category,
        artifact_payload=submission.artifact_payload,
        validation_spec=task.validation_spec
    )
    
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
    
    # 3. Handle Settlement or Slashing
    if report.passed:
        # Determine winning payout (from accepted bid price or task budget)
        winning_bid = next((b for b in task.bids if b.status.value == "ACCEPTED" or b.worker_address == submission.worker_address), None)
        payout_amount = winning_bid.bid_price_usdc if winning_bid else task.budget_usdc

        tx = await web3_service.settle_successful_payout(
            task_id=task_id,
            worker_address=submission.worker_address,
            payout_usdc=payout_amount
        )
        
        # Credit winning worker with payout and return collateral bond
        await state_store.credit_payout(submission.worker_address, payout_amount)
        await state_store.unlock_worker_bond(submission.worker_address, task.required_worker_bond)
        
        # If worker bid lower than budget, refund remainder to Delegator
        budget_remainder = task.budget_usdc - payout_amount
        if budget_remainder > 0:
            await state_store.refund_requester_escrow(task.requester_address, budget_remainder)

        task = await state_store.record_verification_and_settle(
            task_id=task_id,
            report=report,
            settlement_tx_hash=tx.get("tx_hash")
        )
        
        await ws_manager.broadcast_event(
            event_type=EventType.PAYOUT_SETTLED,
            data={
                "task_id": task_id,
                "worker_address": submission.worker_address,
                "payout_amount_usdc": payout_amount,
                "worker_bond_returned": task.required_worker_bond,
                "tx_hash": tx.get("tx_hash"),
                "status": TaskStatus.SETTLED.value,
            }
        )
        
        # Broadcast updated wallet balances
        w_worker = await state_store.get_wallet(submission.worker_address)
        w_delegator = await state_store.get_wallet(task.requester_address)
        if w_worker:
            await ws_manager.broadcast_event(EventType.WALLET_UPDATED, data=w_worker.model_dump())
        if w_delegator:
            await ws_manager.broadcast_event(EventType.WALLET_UPDATED, data=w_delegator.model_dump())

    else:
        # Slashing Path
        tx = await web3_service.execute_slash(
            task_id=task_id,
            worker_address=submission.worker_address,
            requester_address=task.requester_address,
            bond_amount_usdc=task.required_worker_bond
        )
        
        await state_store.slash_worker(
            worker_address=submission.worker_address,
            requester_address=task.requester_address,
            bond_amount=task.required_worker_bond
        )
        
        # Refund initial budget back to Delegator
        await state_store.refund_requester_escrow(task.requester_address, task.budget_usdc)

        task = await state_store.record_verification_and_settle(
            task_id=task_id,
            report=report,
            settlement_tx_hash=tx.get("tx_hash")
        )
        
        await ws_manager.broadcast_event(
            event_type=EventType.WORKER_SLASHED,
            data={
                "task_id": task_id,
                "worker_address": submission.worker_address,
                "slashed_bond_usdc": task.required_worker_bond,
                "requester_refunded_usdc": task.budget_usdc + (task.required_worker_bond * 0.5),
                "tx_hash": tx.get("tx_hash"),
                "status": TaskStatus.SLASHED.value,
            }
        )
        
        # Broadcast updated wallet balances
        w_worker = await state_store.get_wallet(submission.worker_address)
        w_delegator = await state_store.get_wallet(task.requester_address)
        if w_worker:
            await ws_manager.broadcast_event(EventType.WALLET_UPDATED, data=w_worker.model_dump())
        if w_delegator:
            await ws_manager.broadcast_event(EventType.WALLET_UPDATED, data=w_delegator.model_dump())

    return task
