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
