"""
ATOA In-Memory State Store & Lifecycle State Machine.
Maintains thread-safe in-memory ledgers for tasks, bids, deliverables, agent wallets, and reputation.
Implements complex multi-parameter matchmaking based on:
1. Agent specialization alignment (category match bonus)
2. Reputation score weighting
3. Price competitiveness (lowest bid efficiency)
4. Collateral bond commitment
5. Historical success rate
"""

import asyncio
from typing import Dict, List, Optional
import time

from backend.app.models import (
    TaskCreate,
    TaskResponse,
    TaskStatus,
    TaskCategory,
    BidCreate,
    BidResponse,
    BidStatus,
    DeliverableSubmission,
    VerificationReport,
    WalletState,
    NetworkAnalytics,
    EventType,
)


class StateStore:
    def __init__(self):
        self._lock = asyncio.Lock()
        self.tasks: Dict[str, TaskResponse] = {}
        self.bids: Dict[str, List[BidResponse]] = {}  # task_id -> list of bids
        self.deliverables: Dict[str, DeliverableSubmission] = {}
        self.verification_reports: Dict[str, VerificationReport] = {}
        self.wallets: Dict[str, WalletState] = {}

    # -----------------------------------------------------------------------
    # Wallet & Ledger Operations
    # -----------------------------------------------------------------------

    async def get_or_create_wallet(self, address: str, name: Optional[str] = None, role: str = "Bidder") -> WalletState:
        async with self._lock:
            now = time.time()
            if address not in self.wallets:
                # Explicitly honor the role requested unless address clearly indicates requester
                if role in ["Delegator", "Requester"] or "requester" in address.lower() or "delegator" in address.lower():
                    assigned_role = "Delegator"
                else:
                    assigned_role = "Bidder"

                self.wallets[address] = WalletState(
                    address=address,
                    name=name or f"Agent_{address[:6]}",
                    role=assigned_role,
                    balance_usdc=500.0,
                    locked_collateral_usdc=0.0,
                    reputation_score=100.0,
                    completed_tasks_count=0,
                    failed_tasks_count=0,
                    last_active_at=now,
                )
            else:
                if name:
                    self.wallets[address].name = name
                # Only upgrade to Delegator if explicitly performing a delegator action
                if role == "Delegator":
                    self.wallets[address].role = "Delegator"
                self.wallets[address].last_active_at = now
            return self.wallets[address]

    async def get_all_wallets(self) -> List[WalletState]:
        async with self._lock:
            return list(self.wallets.values())

    async def get_wallet(self, address: str) -> Optional[WalletState]:
        async with self._lock:
            return self.wallets.get(address)

    async def lock_wallet_escrow(self, address: str, amount: float) -> bool:
        """Deducts balance and locks funds for task escrow."""
        async with self._lock:
            wallet = self.wallets.get(address)
            if not wallet or wallet.balance_usdc < amount:
                return False
            wallet.balance_usdc -= amount
            wallet.role = "Delegator"
            wallet.last_active_at = time.time()
            return True

    async def lock_worker_bond(self, address: str, bond_amount: float) -> bool:
        """Locks collateral bond from worker balance."""
        async with self._lock:
            wallet = self.wallets.get(address)
            if not wallet or wallet.balance_usdc < bond_amount:
                return False
            wallet.balance_usdc -= bond_amount
            wallet.locked_collateral_usdc += bond_amount
            wallet.role = "Bidder"
            wallet.last_active_at = time.time()
            return True

    async def unlock_worker_bond(self, address: str, bond_amount: float) -> bool:
        """Unlocks collateral bond back to worker balance."""
        async with self._lock:
            wallet = self.wallets.get(address)
            if not wallet:
                return False
            wallet.locked_collateral_usdc = max(0.0, wallet.locked_collateral_usdc - bond_amount)
            wallet.balance_usdc += bond_amount
            wallet.role = "Bidder"
            wallet.last_active_at = time.time()
            return True

    async def credit_payout(self, address: str, amount: float) -> bool:
        """Credits task payout to worker wallet and boosts reputation."""
        async with self._lock:
            wallet = self.wallets.get(address)
            if not wallet:
                return False
            wallet.balance_usdc += amount
            wallet.total_earned_usdc += amount
            wallet.completed_tasks_count += 1
            wallet.role = "Bidder"
            wallet.last_active_at = time.time()
            # Progressive reputation reward (up to 1000 max)
            wallet.reputation_score = min(1000.0, wallet.reputation_score + 15.0)
            return True

    async def slash_worker(self, worker_address: str, requester_address: str, bond_amount: float) -> bool:
        """Slashes worker collateral: 50% refund to requester, 50% burned/penalty, and slashes reputation."""
        async with self._lock:
            worker = self.wallets.get(worker_address)
            requester = self.wallets.get(requester_address)
            if not worker:
                return False
            
            now = time.time()
            worker.locked_collateral_usdc = max(0.0, worker.locked_collateral_usdc - bond_amount)
            worker.total_slashed_usdc += bond_amount
            worker.failed_tasks_count += 1
            worker.role = "Bidder"
            worker.reputation_score = max(0.0, worker.reputation_score - 35.0)
            worker.last_active_at = now

            if requester:
                requester.balance_usdc += (bond_amount * 0.5)
                requester.role = "Delegator"
                requester.last_active_at = now

            return True

    async def refund_requester_escrow(self, requester_address: str, amount: float) -> bool:
        """Refunds task budget back to requester upon failure/discount."""
        async with self._lock:
            requester = self.wallets.get(requester_address)
            if not requester:
                return False
            requester.balance_usdc += amount
            requester.role = "Delegator"
            requester.last_active_at = time.time()
            return True

    # -----------------------------------------------------------------------
    # Task Lifecycle State Machine
    # -----------------------------------------------------------------------

    async def create_task(self, task_in: TaskCreate) -> TaskResponse:
        async with self._lock:
            task = TaskResponse(
                title=task_in.title,
                category=task_in.category,
                description=task_in.description,
                budget_usdc=task_in.budget_usdc,
                required_worker_bond=task_in.required_worker_bond,
                timeout_seconds=task_in.timeout_seconds,
                requester_address=task_in.requester_address,
                validation_spec=task_in.validation_spec,
                status=TaskStatus.BROADCASTED,
                bids=[],
            )
            self.tasks[task.task_id] = task
            self.bids[task.task_id] = []
            return task

    async def get_task(self, task_id: str) -> Optional[TaskResponse]:
        async with self._lock:
            task = self.tasks.get(task_id)
            if task:
                task.bids = self.bids.get(task_id, [])
            return task

    async def list_tasks(self, category: Optional[TaskCategory] = None, status: Optional[TaskStatus] = None) -> List[TaskResponse]:
        async with self._lock:
            results = []
            for t in self.tasks.values():
                if category and t.category != category:
                    continue
                if status and t.status != status:
                    continue
                t.bids = self.bids.get(t.task_id, [])
                results.append(t)
            return sorted(results, key=lambda x: x.created_at, reverse=True)

    # -----------------------------------------------------------------------
    # Reverse Auction & Multi-Parameter Matchmaking
    # -----------------------------------------------------------------------

    async def add_bid(self, task_id: str, bid_in: BidCreate) -> Optional[BidResponse]:
        async with self._lock:
            task = self.tasks.get(task_id)
            if not task:
                return None
            
            # Transition task to MATCHING upon first bid
            if task.status == TaskStatus.BROADCASTED:
                task.status = TaskStatus.MATCHING

            # Retrieve reputation of the worker
            worker_rep = 100.0
            if bid_in.worker_address in self.wallets:
                worker_rep = self.wallets[bid_in.worker_address].reputation_score
                self.wallets[bid_in.worker_address].role = "Bidder"
                self.wallets[bid_in.worker_address].last_active_at = time.time()

            bid = BidResponse(
                task_id=task_id,
                worker_address=bid_in.worker_address,
                bid_price_usdc=bid_in.bid_price_usdc,
                collateral_bond_locked=bid_in.collateral_bond_locked,
                estimated_duration_seconds=bid_in.estimated_duration_seconds,
                notes=bid_in.notes,
                worker_reputation_score=worker_rep,
                status=BidStatus.PENDING,
            )
            
            if task_id not in self.bids:
                self.bids[task_id] = []
            self.bids[task_id].append(bid)
            task.bids = self.bids[task_id]
            task.updated_at = time.time()
            return bid

    async def get_task_bids(self, task_id: str) -> List[BidResponse]:
        async with self._lock:
            return self.bids.get(task_id, [])

    async def assign_winning_bid(self, task_id: str, selected_bid_id: Optional[str] = None) -> Optional[TaskResponse]:
        """
        Executes multi-parameter matchmaking algorithm or assigns explicitly selected bid.
        Score = (Reputation * 0.40) + (Price Efficiency * 0.35) + (Domain Specialization * 0.15) + (Bond Ratio * 0.10)
        """
        async with self._lock:
            task = self.tasks.get(task_id)
            if not task or task.status not in [TaskStatus.BROADCASTED, TaskStatus.MATCHING]:
                return None

            task_bids = self.bids.get(task_id, [])
            if not task_bids:
                return None

            if selected_bid_id:
                best_bid = next((b for b in task_bids if b.bid_id == selected_bid_id), None)
                if not best_bid:
                    return None
            else:
                def score_bid(b: BidResponse) -> float:
                    wallet = self.wallets.get(b.worker_address)
                    rep = wallet.reputation_score if wallet else b.worker_reputation_score
                    norm_rep = min(100.0, rep)  # baseline 0-100

                    # 1. Price savings relative to task max budget (0 to 100)
                    price_savings = max(0.0, task.budget_usdc - b.bid_price_usdc)
                    price_score = (price_savings / max(1.0, task.budget_usdc)) * 100.0

                    # 2. Domain specialization match bonus
                    addr_lower = b.worker_address.lower()
                    domain_bonus = 0.0
                    if task.category == TaskCategory.CODE_GENERATION and "code" in addr_lower:
                        domain_bonus = 30.0
                    elif task.category == TaskCategory.RESEARCH and "research" in addr_lower:
                        domain_bonus = 30.0
                    elif task.category == TaskCategory.QUERY and ("query" in addr_lower or "oracle" in addr_lower):
                        domain_bonus = 30.0

                    # 3. Bond commitment ratio
                    bond_ratio = min(2.0, b.collateral_bond_locked / max(1.0, task.required_worker_bond))
                    bond_score = bond_ratio * 10.0

                    # Total Weighted Score
                    total_score = (norm_rep * 0.40) + (price_score * 0.35) + domain_bonus + bond_score
                    return total_score

                # Sort bids descending by total matchmaking score
                best_bid = max(task_bids, key=score_bid)

            # Update bid states
            for b in task_bids:
                if b.bid_id == best_bid.bid_id:
                    b.status = BidStatus.ACCEPTED
                else:
                    b.status = BidStatus.REJECTED

            # Transition task to IN_PROGRESS
            task.assigned_worker = best_bid.worker_address
            task.winning_bid_id = best_bid.bid_id
            task.status = TaskStatus.IN_PROGRESS
            task.assigned_at = time.time()
            task.updated_at = time.time()
            task.bids = task_bids

            # Touch active timestamp & enforce Bidder role
            if best_bid.worker_address in self.wallets:
                self.wallets[best_bid.worker_address].role = "Bidder"
                self.wallets[best_bid.worker_address].last_active_at = time.time()

            return task

    # -----------------------------------------------------------------------
    # Deliverables & Settlement Lifecycle
    # -----------------------------------------------------------------------

    async def record_deliverable(self, submission: DeliverableSubmission) -> Optional[TaskResponse]:
        async with self._lock:
            task = self.tasks.get(submission.task_id)
            if not task:
                return None

            self.deliverables[submission.task_id] = submission
            task.status = TaskStatus.VERIFYING
            task.updated_at = time.time()
            if submission.worker_address in self.wallets:
                self.wallets[submission.worker_address].role = "Bidder"
                self.wallets[submission.worker_address].last_active_at = time.time()
            return task

    async def record_verification_and_settle(
        self,
        task_id: str,
        report: VerificationReport,
        settlement_tx_hash: Optional[str] = None
    ) -> Optional[TaskResponse]:
        async with self._lock:
            task = self.tasks.get(task_id)
            if not task:
                return None

            self.verification_reports[task_id] = report
            if report.passed:
                task.status = TaskStatus.SETTLED
            else:
                task.status = TaskStatus.SLASHED

            task.settlement_tx_hash = settlement_tx_hash
            task.settled_at = time.time()
            task.updated_at = time.time()
            task.bids = self.bids.get(task.task_id, [])
            return task

    # -----------------------------------------------------------------------
    # Analytics Overview
    # -----------------------------------------------------------------------

    async def get_analytics(self) -> NetworkAnalytics:
        async with self._lock:
            total_created = len(self.tasks)
            settled = [t for t in self.tasks.values() if t.status == TaskStatus.SETTLED]
            slashed = [t for t in self.tasks.values() if t.status == TaskStatus.SLASHED]
            
            total_vol = sum(t.budget_usdc for t in settled)
            total_slashed_vol = sum(t.required_worker_bond for t in slashed)
            total_bids = sum(len(b_list) for b_list in self.bids.values())
            avg_bids = (total_bids / total_created) if total_created > 0 else 0.0

            return NetworkAnalytics(
                total_tasks_created=total_created,
                total_tasks_settled=len(settled),
                total_tasks_slashed=len(slashed),
                total_volume_usdc=round(total_vol, 2),
                total_slashed_usdc=round(total_slashed_vol, 2),
                average_bids_per_task=round(avg_bids, 1),
                active_workers_count=len(self.wallets),
            )


# Global singleton instance
state_store = StateStore()
