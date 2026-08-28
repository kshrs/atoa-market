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
