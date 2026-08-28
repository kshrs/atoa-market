"""
Unit and Integration Test Suite for ATOA Web3 Escrow Service
"""

import asyncio
from decimal import Decimal
import unittest

from services import web3_escrow
from services.web3_escrow import (
    EscrowExecutionError,
    TaskState,
    cancel_task,
    deposit_task_escrow,
    execute_slash,
    from_raw_token_units,
    get_async_w3,
    get_escrow_contract,
    get_protocol_account,
    hash_task_id,
    lock_worker_bond,
    settle_successful_payout,
    to_raw_token_units,
)


class TestWeb3EscrowService(unittest.TestCase):
    """Test suite verifying precision, hashing, transaction builders, and mock flows."""

    def setUp(self):
        # Enable mock mode for isolated unit testing
        web3_escrow.MOCK_WEB3 = True

    def tearDown(self):
        asyncio.run(web3_escrow.close_async_w3())

    def test_hash_task_id_deterministic(self):
        """Verify keccak256 hash generation is deterministic and 32 bytes."""
        task_id = "task_arbitrage_001"
        h1 = hash_task_id(task_id)
        h2 = hash_task_id(task_id)
        self.assertEqual(h1, h2)
        self.assertEqual(len(h1), 32)
        self.assertIsInstance(h1, (bytes, bytearray))

    def test_token_units_precision(self):
        """Verify floating point vs Decimal conversions with 6 USDC decimals."""
        # 10.50 USDC -> 10,500,000 base units
        self.assertEqual(to_raw_token_units(10.50, decimals=6), 10500000)
        self.assertEqual(to_raw_token_units("10.50", decimals=6), 10500000)
        self.assertEqual(to_raw_token_units(Decimal("10.50"), decimals=6), 10500000)

        # 0.000001 USDC -> 1 base unit
        self.assertEqual(to_raw_token_units(0.000001, decimals=6), 1)
        self.assertEqual(to_raw_token_units("0.000001", decimals=6), 1)

        # Reverse conversion
        self.assertAlmostEqual(from_raw_token_units(10500000, decimals=6), 10.50)
        self.assertAlmostEqual(from_raw_token_units(1, decimals=6), 0.000001)

    def test_protocol_account_initialization(self):
        """Verify protocol signer initialization."""
        account = get_protocol_account()
        self.assertIsNotNone(account)
        self.assertTrue(account.address.startswith("0x"))
        self.assertEqual(len(account.address), 42)

    def test_contract_initialization(self):
        """Verify contract binding instance."""
        contract = get_escrow_contract()
        self.assertIsNotNone(contract)
        self.assertTrue(hasattr(contract.functions, "depositEscrow"))
        self.assertTrue(hasattr(contract.functions, "settlePayout"))
        self.assertTrue(hasattr(contract.functions, "slashWorker"))
        self.assertTrue(hasattr(contract.functions, "cancelTask"))
        self.assertTrue(hasattr(contract.functions, "getTask"))
        self.assertTrue(hasattr(contract.functions, "getTaskState"))
        self.assertTrue(hasattr(contract.functions, "getTotalTasks"))

    def test_task_state_enum(self):
        """Verify TaskState enum values match Solidity contract definition."""
        self.assertEqual(TaskState.NONE, 0)
        self.assertEqual(TaskState.DEPOSITED, 1)
        self.assertEqual(TaskState.ACTIVE, 2)
        self.assertEqual(TaskState.SETTLED, 3)
        self.assertEqual(TaskState.SLASHED, 4)
        self.assertEqual(TaskState.CANCELLED, 5)

    def test_mock_deposit_escrow(self):
        """Verify deposit escrow flow in mock mode."""
        res = asyncio.run(deposit_task_escrow(
            task_id="task_test_deposit",
            requester_address="0x70997970C51812dc3A010C7d01b50e0d17dc79C8",
            amount_usdc=50.0
        ))
        self.assertTrue(res["success"])
        self.assertEqual(res["action"], "DEPOSIT")
        self.assertEqual(res["task_id"], "task_test_deposit")
        self.assertEqual(res["amount_transferred"], 50.0)
        self.assertTrue(res["tx_hash"].startswith("0x"))

    def test_mock_lock_worker_bond(self):
        """Verify worker bond locking in mock mode."""
        res = asyncio.run(lock_worker_bond(
            task_id="task_test_bond",
            worker_address="0x3C44CdDdB6a900fa2b585dd299e03d12FA4293BC",
            bond_amount_usdc=10.0
        ))
        self.assertTrue(res["success"])
        self.assertEqual(res["action"], "LOCK_BOND")
        self.assertEqual(res["task_id"], "task_test_bond")
        self.assertEqual(res["amount_transferred"], 10.0)

    def test_mock_settle_payout(self):
        """Verify settle payout in mock mode."""
        res = asyncio.run(settle_successful_payout(
            task_id="task_test_settle",
            worker_address="0x3C44CdDdB6a900fa2b585dd299e03d12FA4293BC",
            payout_usdc=60.0
        ))
        self.assertTrue(res["success"])
        self.assertEqual(res["action"], "SETTLE_PAYOUT")
        self.assertEqual(res["task_id"], "task_test_settle")
        self.assertEqual(res["amount_transferred"], 60.0)

    def test_mock_execute_slash(self):
        """Verify slashing in mock mode."""
        res = asyncio.run(execute_slash(
            task_id="task_test_slash",
            worker_address="0x3C44CdDdB6a900fa2b585dd299e03d12FA4293BC",
            requester_address="0x70997970C51812dc3A010C7d01b50e0d17dc79C8",
            bond_amount_usdc=10.0
        ))
        self.assertTrue(res["success"])
        self.assertEqual(res["action"], "SLASH")
        self.assertEqual(res["task_id"], "task_test_slash")
        self.assertEqual(res["amount_transferred"], 10.0)

    def test_mock_cancel_task(self):
        """Verify cancel task in mock mode."""
        res = asyncio.run(cancel_task(
            task_id="task_test_cancel",
            amount_usdc=50.0
        ))
        self.assertTrue(res["success"])
        self.assertEqual(res["action"], "CANCEL")
        self.assertEqual(res["task_id"], "task_test_cancel")

    def test_live_mode_raises_on_unreachable_rpc(self):
        """Verify that when MOCK_WEB3 is False and RPC is down, EscrowExecutionError is raised."""
        web3_escrow.MOCK_WEB3 = False
        web3_escrow.ALLOW_FALLBACK_ON_ERROR = False

        with self.assertRaises(EscrowExecutionError):
            asyncio.run(deposit_task_escrow(
                task_id="task_live_fail",
                requester_address="0x70997970C51812dc3A010C7d01b50e0d17dc79C8",
                amount_usdc=10.0
            ))


if __name__ == "__main__":
    unittest.main()
