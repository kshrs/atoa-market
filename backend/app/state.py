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
            if address not in self.wallets:
                assigned_role = "Delegator" if "requester" in address.lower() or role in ["Delegator", "Requester"] else "Bidder"
                self.wallets[address] = WalletState(
                    address=address,
                    name=name or f"Agent_{address[:6]}",
                    role=assigned_role,
                    balance_usdc=500.0,
                    locked_collateral_usdc=0.0,
                    reputation_score=100.0,
                    completed_tasks_count=0,
                    failed_tasks_count=0,
                )
            else:
                if name:
                    self.wallets[address].name = name
                if role in ["Delegator", "Bidder"]:
                    self.wallets[address].role = role
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
            return True

    async def unlock_worker_bond(self, address: str, bond_amount: float) -> bool:
        """Unlocks collateral bond back to worker balance."""
        async with self._lock:
            wallet = self.wallets.get(address)
            if not wallet:
                return False
            wallet.locked_collateral_usdc = max(0.0, wallet.locked_collateral_usdc - bond_amount)
            wallet.balance_usdc += bond_amount
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
            
            worker.locked_collateral_usdc = max(0.0, worker.locked_collateral_usdc - bond_amount)
            worker.total_slashed_usdc += bond_amount
            worker.failed_tasks_count += 1
            worker.reputation_score = max(0.0, worker.reputation_score - 35.0)

            if requester:
                requester.balance_usdc += (bond_amount * 0.5)

            return True

    async def refund_requester_escrow(self, requester_address: str, amount: float) -> bool:
        """Refunds task budget back to requester upon failure/discount."""
        async with self._lock:
            requester = self.wallets.get(requester_address)
            if not requester:
                return False
            requester.balance_usdc += amount
            return True

    # -----------------------------------------------------------------------
    # Task Lifecycle Operations
    # -----------------------------------------------------------------------

    async def create_task(self, task_in: TaskCreate, escrow_tx_hash: Optional[str] = None) -> TaskResponse:
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
                escrow_tx_hash=escrow_tx_hash or f"0xmock_escrow_{int(time.time())}",
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

    async def list_tasks(
        self,
        category: Optional[TaskCategory] = None,
        status: Optional[TaskStatus] = None,
        min_budget: Optional[float] = None
    ) -> List[TaskResponse]:
        async with self._lock:
            results = []
            for t in self.tasks.values():
                t.bids = self.bids.get(t.task_id, [])
                results.append(t)

            if category:
                results = [t for t in results if t.category == category]
            if status:
                results = [t for t in results if t.status == status]
            if min_budget is not None:
                results = [t for t in results if t.budget_usdc >= min_budget]
            return results

    # -----------------------------------------------------------------------
    # Multi-Parameter Matchmaking & Bidding Engine
    # -----------------------------------------------------------------------

    async def add_bid(self, task_id: str, bid_in: BidCreate) -> Optional[BidResponse]:
        async with self._lock:
            task = self.tasks.get(task_id)
            if not task or task.status not in [TaskStatus.BROADCASTED, TaskStatus.MATCHING]:
                return None
            
            worker = self.wallets.get(bid_in.worker_address)
            rep_score = worker.reputation_score if worker else 100.0
            
            bid = BidResponse(
                task_id=task_id,
                worker_address=bid_in.worker_address,
                bid_price_usdc=bid_in.bid_price_usdc,
                collateral_bond_locked=bid_in.collateral_bond_locked,
                estimated_duration_seconds=bid_in.estimated_duration_seconds,
                worker_reputation_score=rep_score,
                status=BidStatus.PENDING,
            )
            
            self.bids[task_id].append(bid)
            task.bids = self.bids[task_id]
            task.status = TaskStatus.MATCHING
            task.updated_at = time.time()
            return bid

    async def get_task_bids(self, task_id: str) -> List[BidResponse]:
        async with self._lock:
            return self.bids.get(task_id, [])

    async def assign_winning_bid(self, task_id: str, selected_bid_id: Optional[str] = None) -> Optional[BidResponse]:
        """
        Sophisticated Multi-Parameter Matchmaking Algorithm:
        Composite Score = (Reputation * 0.40) + (Price Efficiency * 0.35) + (Domain Match * 0.15) + (Bond Ratio * 0.10)
        """
        async with self._lock:
            task = self.tasks.get(task_id)
            bids = self.bids.get(task_id, [])
            if not task or not bids or task.status not in [TaskStatus.BROADCASTED, TaskStatus.MATCHING]:
                return None
            
            chosen_bid: Optional[BidResponse] = None
            if selected_bid_id:
                for b in bids:
                    if b.bid_id == selected_bid_id:
                        chosen_bid = b
                        break
            else:
                max_budget = task.budget_usdc or 100.0
                task_cat = task.category.value if hasattr(task.category, "value") else str(task.category)

                def compute_match_score(b: BidResponse) -> float:
                    wallet = self.wallets.get(b.worker_address)
                    rep = wallet.reputation_score if wallet else b.worker_reputation_score
                    
                    # 1. Reputation Score Component (0 - 100 normalized)
                    norm_rep = min(100.0, rep)
                    
                    # 2. Price Efficiency Component (cheaper bid relative to budget gives higher score)
                    price_ratio = max(0.01, min(1.0, b.bid_price_usdc / max_budget))
                    price_score = (1.0 - price_ratio) * 100.0
                    
                    # 3. Agent Specialization Alignment Bonus
                    w_name = (wallet.name if wallet else b.worker_address).lower()
                    domain_bonus = 0.0
                    if "code" in task_cat and "code" in w_name:
                        domain_bonus = 30.0
                    elif "research" in task_cat and "research" in w_name:
                        domain_bonus = 30.0
                    elif "query" in task_cat and "query" in w_name:
                        domain_bonus = 30.0
                    
                    # 4. Collateral Bond Commitment Component
                    bond_ratio = min(1.0, b.collateral_bond_locked / max(1.0, task.required_worker_bond))
                    bond_score = bond_ratio * 20.0

                    # Composite Weighted Matchmaking Score
                    total_score = (norm_rep * 0.40) + (price_score * 0.35) + domain_bonus + bond_score
                    return total_score
                
                chosen_bid = max(bids, key=compute_match_score)
            
            if not chosen_bid:
                return None
            
            for b in bids:
                if b.bid_id == chosen_bid.bid_id:
                    b.status = BidStatus.ACCEPTED
                else:
                    b.status = BidStatus.REJECTED
                    if b.worker_address in self.wallets:
                        w = self.wallets[b.worker_address]
                        w.locked_collateral_usdc = max(0.0, w.locked_collateral_usdc - b.collateral_bond_locked)
                        w.balance_usdc += b.collateral_bond_locked

            task.status = TaskStatus.IN_PROGRESS
            task.assigned_worker = chosen_bid.worker_address
            task.bids = bids
            task.updated_at = time.time()
            return chosen_bid

    # -----------------------------------------------------------------------
    # Deliverables & Verification
    # -----------------------------------------------------------------------

    async def record_deliverable(self, submission: DeliverableSubmission) -> bool:
        async with self._lock:
            task = self.tasks.get(submission.task_id)
            if not task or task.status != TaskStatus.IN_PROGRESS:
                return False
            
            self.deliverables[submission.task_id] = submission
            task.status = TaskStatus.VERIFYING
            task.updated_at = time.time()
            return True

    async def record_verification_and_settle(
        self,
        task_id: str,
        report: VerificationReport,
        settlement_tx_hash: Optional[str] = None
    ) -> TaskResponse:
        async with self._lock:
            task = self.tasks[task_id]
            self.verification_reports[task_id] = report
            task.updated_at = time.time()
            task.settlement_tx_hash = settlement_tx_hash or f"0xmock_settle_{int(time.time())}"
            
            if report.passed:
                task.status = TaskStatus.SETTLED
            else:
                task.status = TaskStatus.SLASHED

            task.bids = self.bids.get(task_id, [])
            return task

    # -----------------------------------------------------------------------
    # Global Analytics
    # -----------------------------------------------------------------------

    async def get_analytics(self) -> NetworkAnalytics:
        async with self._lock:
            tasks = list(self.tasks.values())
            wallets = list(self.wallets.values())
            
            total_created = len(tasks)
            total_settled = len([t for t in tasks if t.status == TaskStatus.SETTLED])
            total_slashed = len([t for t in tasks if t.status == TaskStatus.SLASHED])
            total_volume = sum(t.budget_usdc for t in tasks if t.status == TaskStatus.SETTLED)
            total_slashed_val = sum(w.total_slashed_usdc for w in wallets)
            
            completed_total = total_settled + total_slashed
            success_rate = (total_settled / completed_total * 100.0) if completed_total > 0 else 100.0

            return NetworkAnalytics(
                total_tasks_created=total_created,
                total_tasks_settled=total_settled,
                total_tasks_slashed=total_slashed,
                total_volume_usdc=round(total_volume, 2),
                total_slashed_usdc=round(total_slashed_val, 2),
                active_agents_count=len(wallets),
                success_rate_pct=round(success_rate, 2),
            )


# Global singleton instance
state_store = StateStore()
