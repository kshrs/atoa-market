"""
ATOA In-Memory State Store & Lifecycle State Machine.
Maintains thread-safe in-memory ledgers for tasks, bids, deliverables, agent wallets, and reputation.
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
    EventEnvelope,
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
        
        # Pre-seed demo agent wallets
        self._seed_default_wallets()

    def _seed_default_wallets(self):
        """Seed initial agent wallets for demonstration."""
        default_agents = [
            ("0xRequester_A1", "Requester Daemon", "Requester", 1000.0, 100.0),
            ("0xWorker_Optimizer_B2", "Worker Alpha (Optimizer)", "Worker", 200.0, 120.0),
            ("0xWorker_Researcher_C3", "Worker Beta (Researcher)", "Worker", 200.0, 110.0),
            ("0xWorker_Rogue_D4", "Rogue Spammer Bot", "Rogue", 50.0, 40.0),
        ]
        for address, name, role, balance, rep in default_agents:
            self.wallets[address] = WalletState(
                address=address,
                name=name,
                role=role,
                balance_usdc=balance,
                locked_collateral_usdc=0.0,
                total_earned_usdc=0.0,
                total_slashed_usdc=0.0,
                reputation_score=rep,
                completed_tasks_count=0,
                failed_tasks_count=0,
            )

    # -----------------------------------------------------------------------
    # Wallet & Ledger Operations
    # -----------------------------------------------------------------------

    async def get_or_create_wallet(self, address: str, name: Optional[str] = None, role: str = "Worker") -> WalletState:
        async with self._lock:
            if address not in self.wallets:
                self.wallets[address] = WalletState(
                    address=address,
                    name=name or f"Agent_{address[:6]}",
                    role=role,
                    balance_usdc=100.0,
                    locked_collateral_usdc=0.0,
                    reputation_score=100.0,
                )
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
            return True

    async def lock_worker_bond(self, address: str, bond_amount: float) -> bool:
        """Locks collateral bond from worker balance."""
        async with self._lock:
            wallet = self.wallets.get(address)
            if not wallet or wallet.balance_usdc < bond_amount:
                return False
            wallet.balance_usdc -= bond_amount
            wallet.locked_collateral_usdc += bond_amount
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
        """Credits task payout to worker wallet."""
        async with self._lock:
            wallet = self.wallets.get(address)
            if not wallet:
                return False
            wallet.balance_usdc += amount
            wallet.total_earned_usdc += amount
            wallet.completed_tasks_count += 1
            wallet.reputation_score = min(1000.0, wallet.reputation_score + 5.0)
            return True

    async def slash_worker(self, worker_address: str, requester_address: str, bond_amount: float) -> bool:
        """Slashes worker collateral: 50% refund to requester, 50% burned/penalty."""
        async with self._lock:
            worker = self.wallets.get(worker_address)
            requester = self.wallets.get(requester_address)
            if not worker:
                return False
            
            # Deduct locked collateral
            worker.locked_collateral_usdc = max(0.0, worker.locked_collateral_usdc - bond_amount)
            worker.total_slashed_usdc += bond_amount
            worker.failed_tasks_count += 1
            worker.reputation_score = max(0.0, worker.reputation_score - 20.0)

            # Refund 50% of slashed bond to requester as compensation
            if requester:
                requester.balance_usdc += (bond_amount * 0.5)

            return True

    async def refund_requester_escrow(self, requester_address: str, amount: float) -> bool:
        """Refunds full task budget back to requester upon failure/timeout."""
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
                escrow_tx_hash=escrow_tx_hash or f"0xmock_escrow_{int(time.time())}",
            )
            self.tasks[task.task_id] = task
            self.bids[task.task_id] = []
            return task

    async def get_task(self, task_id: str) -> Optional[TaskResponse]:
        async with self._lock:
            return self.tasks.get(task_id)

    async def list_tasks(
        self,
        category: Optional[TaskCategory] = None,
        status: Optional[TaskStatus] = None,
        min_budget: Optional[float] = None
    ) -> List[TaskResponse]:
        async with self._lock:
            results = list(self.tasks.values())
            if category:
                results = [t for t in results if t.category == category]
            if status:
                results = [t for t in results if t.status == status]
            if min_budget is not None:
                results = [t for t in results if t.budget_usdc >= min_budget]
            return results

    # -----------------------------------------------------------------------
    # Bidding & Matchmaking Operations
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
            task.status = TaskStatus.MATCHING
            task.updated_at = time.time()
            return bid

    async def get_task_bids(self, task_id: str) -> List[BidResponse]:
        async with self._lock:
            return self.bids.get(task_id, [])

    async def assign_winning_bid(self, task_id: str, selected_bid_id: Optional[str] = None) -> Optional[BidResponse]:
        """
        Assigns task to specified bid, or automatically selects the best bid
        using Score = (Reputation * 0.4) - (Price * 0.4) - (Duration * 0.2)
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
                # Automated matchmaking formula
                def score_bid(b: BidResponse) -> float:
                    # Higher rep is good, lower price is good, lower duration is good
                    return (b.worker_reputation_score * 0.5) - (b.bid_price_usdc * 0.3) - (b.estimated_duration_seconds * 0.2)
                
                chosen_bid = max(bids, key=score_bid)
            
            if not chosen_bid:
                return None
            
            # Update bid statuses
            for b in bids:
                if b.bid_id == chosen_bid.bid_id:
                    b.status = BidStatus.ACCEPTED
                else:
                    b.status = BidStatus.REJECTED
                    # Refund rejected worker bond if it was locked
                    if b.worker_address in self.wallets:
                        w = self.wallets[b.worker_address]
                        w.locked_collateral_usdc = max(0.0, w.locked_collateral_usdc - b.collateral_bond_locked)
                        w.balance_usdc += b.collateral_bond_locked

            task.status = TaskStatus.IN_PROGRESS
            task.assigned_worker = chosen_bid.worker_address
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
