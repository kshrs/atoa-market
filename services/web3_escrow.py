"""
ATOA Smart Escrow Web3 Service Module
======================================
Asynchronous Web3 integration layer for the ATOA (Agent-to-Agent) economy.
Handles zero-trust smart escrow deposits, worker collateral bonding,
automated oracle verification payouts, and game-theoretic slashing.

Author: Ashwin Balaji G
"""

import asyncio
from decimal import Decimal
from enum import IntEnum
import hashlib
import logging
import os
import time
from typing import Any, Callable, Dict, Optional, TypedDict, Union

from eth_account import Account
from eth_account.signers.local import LocalAccount
from web3 import AsyncHTTPProvider, AsyncWeb3
from web3.contract.async_contract import AsyncContract

# Configure module logger
logger = logging.getLogger("atoa.services.web3_escrow")
if not logger.handlers:
    handler = logging.StreamHandler()
    formatter = logging.Formatter("[%(asctime)s] [%(levelname)s] [web3_escrow]: %(message)s")
    handler.setFormatter(formatter)
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)

# --- CONFIGURATION & ENVIRONMENT VARIABLES ---

RPC_URL: str = os.getenv("WEB3_RPC_URL", os.getenv("RPC_URL", "http://127.0.0.1:8545"))
ESCROW_CONTRACT_ADDRESS: str = os.getenv(
    "ESCROW_CONTRACT_ADDRESS",
    os.getenv("ATOA_ESCROW_ADDRESS", "0x5FbDB2315678afecb367f032d93F642f64180aa3")
)
PROTOCOL_PRIVATE_KEY: str = os.getenv(
    "PROTOCOL_PRIVATE_KEY",
    os.getenv("ORACLE_PRIVATE_KEY", "0xac0974bec39a17e36ba4a6b4d238ff944bacb478cbed5efcae784d7bf4f2ff80")
)
USDC_DECIMALS: int = int(os.getenv("USDC_DECIMALS", os.getenv("TOKEN_DECIMALS", "6")))
MOCK_WEB3: bool = os.getenv("MOCK_WEB3", "false").lower() in ("true", "1", "yes")
ALLOW_FALLBACK_ON_ERROR: bool = os.getenv("ALLOW_FALLBACK_ON_ERROR", "false").lower() in ("true", "1", "yes")

# Concurrency lock for sequential transaction nonces in async environment
_nonce_lock = asyncio.Lock()


# --- ENUMS & TYPING ---

class TaskState(IntEnum):
    """Corresponds to the TaskState enum defined in AtoaSettlementEscrow.sol."""
    NONE = 0
    DEPOSITED = 1
    ACTIVE = 2
    SETTLED = 3
    SLASHED = 4
    CANCELLED = 5


class EscrowTransactionResult(TypedDict):
    success: bool
    tx_hash: str
    block_number: int
    task_id: str
    action: str
    amount_transferred: float
    timestamp: int


class TaskEscrowDetails(TypedDict):
    task_id: str
    requester: str
    worker: str
    escrow_amount: float
    worker_bond: float
    state: TaskState
    created_at: int
    settled_at: int


class EscrowExecutionError(Exception):
    """Custom exception raised when an escrow transaction or contract call fails."""
    pass


# --- COMPLETE ATOA SETTLEMENT ESCROW ABI ---

ATOA_ESCROW_ABI: list[dict[str, Any]] = [
    {
        "inputs": [
            {"internalType": "address", "name": "_settlementToken", "type": "address"},
            {"internalType": "address", "name": "_protocolOracle", "type": "address"},
            {"internalType": "address", "name": "_feeRecipient", "type": "address"}
        ],
        "stateMutability": "nonpayable",
        "type": "constructor"
    },
    {
        "inputs": [
            {"internalType": "bytes32", "name": "taskId", "type": "bytes32"},
            {"internalType": "uint256", "name": "amount", "type": "uint256"}
        ],
        "name": "depositEscrow",
        "outputs": [],
        "stateMutability": "nonpayable",
        "type": "function"
    },
    {
        "inputs": [
            {"internalType": "bytes32", "name": "taskId", "type": "bytes32"},
            {"internalType": "address", "name": "requester", "type": "address"},
            {"internalType": "uint256", "name": "amount", "type": "uint256"}
        ],
        "name": "depositEscrowFor",
        "outputs": [],
        "stateMutability": "nonpayable",
        "type": "function"
    },
    {
        "inputs": [
            {"internalType": "bytes32", "name": "taskId", "type": "bytes32"},
            {"internalType": "uint256", "name": "bondAmount", "type": "uint256"}
        ],
        "name": "lockWorkerBond",
        "outputs": [],
        "stateMutability": "nonpayable",
        "type": "function"
    },
    {
        "inputs": [
            {"internalType": "bytes32", "name": "taskId", "type": "bytes32"},
            {"internalType": "address", "name": "worker", "type": "address"},
            {"internalType": "uint256", "name": "bondAmount", "type": "uint256"}
        ],
        "name": "lockWorkerBondFor",
        "outputs": [],
        "stateMutability": "nonpayable",
        "type": "function"
    },
    {
        "inputs": [
            {"internalType": "bytes32", "name": "taskId", "type": "bytes32"},
            {"internalType": "address", "name": "worker", "type": "address"}
        ],
        "name": "settlePayout",
        "outputs": [],
        "stateMutability": "nonpayable",
        "type": "function"
    },
    {
        "inputs": [
            {"internalType": "bytes32", "name": "taskId", "type": "bytes32"},
            {"internalType": "address", "name": "worker", "type": "address"},
            {"internalType": "address", "name": "requester", "type": "address"}
        ],
        "name": "slashWorker",
        "outputs": [],
        "stateMutability": "nonpayable",
        "type": "function"
    },
    {
        "inputs": [{"internalType": "bytes32", "name": "taskId", "type": "bytes32"}],
        "name": "cancelTask",
        "outputs": [],
        "stateMutability": "nonpayable",
        "type": "function"
    },
    {
        "inputs": [{"internalType": "bytes32", "name": "taskId", "type": "bytes32"}],
        "name": "getTask",
        "outputs": [
            {
                "components": [
                    {"internalType": "bytes32", "name": "taskId", "type": "bytes32"},
                    {"internalType": "address", "name": "requester", "type": "address"},
                    {"internalType": "address", "name": "worker", "type": "address"},
                    {"internalType": "uint256", "name": "escrowAmount", "type": "uint256"},
                    {"internalType": "uint256", "name": "workerBond", "type": "uint256"},
                    {"internalType": "uint8", "name": "state", "type": "uint8"},
                    {"internalType": "uint256", "name": "createdAt", "type": "uint256"},
                    {"internalType": "uint256", "name": "settledAt", "type": "uint256"}
                ],
                "internalType": "struct AtoaSettlementEscrow.TaskEscrow",
                "name": "",
                "type": "tuple"
            }
        ],
        "stateMutability": "view",
        "type": "function"
    },
    {
        "inputs": [{"internalType": "bytes32", "name": "taskId", "type": "bytes32"}],
        "name": "getTaskState",
        "outputs": [{"internalType": "uint8", "name": "", "type": "uint8"}],
        "stateMutability": "view",
        "type": "function"
    },
    {
        "inputs": [],
        "name": "getTotalTasks",
        "outputs": [{"internalType": "uint256", "name": "", "type": "uint256"}],
        "stateMutability": "view",
        "type": "function"
    }
]

# --- SINGLETON WEB3 CLIENT & CONTRACT STATE ---

_async_w3: Optional[AsyncWeb3] = None
_protocol_account: Optional[LocalAccount] = None


def get_protocol_account() -> LocalAccount:
    """Initializes and returns the LocalAccount instance for signing transactions."""
    global _protocol_account
    if _protocol_account is None:
        key = PROTOCOL_PRIVATE_KEY.strip()
        if not key.startswith("0x"):
            key = f"0x{key}"
        _protocol_account = Account.from_key(key)
    return _protocol_account


def get_async_w3() -> AsyncWeb3:
    """Initializes and returns the singleton AsyncWeb3 client instance."""
    global _async_w3
    if _async_w3 is None:
        provider = AsyncHTTPProvider(RPC_URL, request_kwargs={"timeout": 30.0})
        _async_w3 = AsyncWeb3(provider)
    return _async_w3


async def close_async_w3() -> None:
    """Closes the underlying async HTTP provider session if initialized."""
    global _async_w3
    if _async_w3 is not None:
        try:
            if hasattr(_async_w3.provider, "disconnect"):
                await _async_w3.provider.disconnect()
        except Exception as err:
            logger.debug(f"Error during async provider session teardown: {err}")
        finally:
            _async_w3 = None


def get_escrow_contract(w3: Optional[AsyncWeb3] = None) -> AsyncContract:
    """Instantiates the Async Contract binding."""
    client = w3 or get_async_w3()
    checksum_addr = AsyncWeb3.to_checksum_address(ESCROW_CONTRACT_ADDRESS)
    return client.eth.contract(address=checksum_addr, abi=ATOA_ESCROW_ABI)


def hash_task_id(task_id: str) -> bytes:
    """Computes the keccak256 hash of the string task_id to pass as bytes32 to Solidity."""
    return AsyncWeb3.keccak(text=task_id)


def to_raw_token_units(amount_usdc: Union[float, int, str, Decimal], decimals: int = USDC_DECIMALS) -> int:
    """
    Converts USDC amount to integer base units with exact Decimal precision.
    Prevents binary floating-point representation rounding bugs.
    """
    dec_amount = Decimal(str(amount_usdc))
    multiplier = Decimal(10 ** decimals)
    return int(dec_amount * multiplier)


def from_raw_token_units(raw_amount: int, decimals: int = USDC_DECIMALS) -> float:
    """Converts integer base units back to human-readable float token amount."""
    return float(Decimal(raw_amount) / Decimal(10 ** decimals))


def _generate_mock_result(action_name: str, task_id: str, amount_transferred: float) -> EscrowTransactionResult:
    """Generates a deterministic verified receipt for development / mock mode."""
    mock_tx_seed = f"{task_id}:{action_name}:{amount_transferred}:{time.time()}"
    mock_hash = f"0x{hashlib.sha256(mock_tx_seed.encode()).hexdigest()}"
    mock_block = 19482000 + int(time.time()) % 10000
    now = int(time.time())

    logger.info(f"[DEV/MOCK] Handled {action_name} for task {task_id} with tx {mock_hash}")
    return {
        "success": True,
        "tx_hash": mock_hash,
        "block_number": mock_block,
        "task_id": task_id,
        "action": action_name,
        "amount_transferred": float(amount_transferred),
        "timestamp": now
    }


async def _execute_contract_call(
    build_tx_coroutine_fn: Callable[[Dict[str, Any]], Any],
    action_name: str,
    task_id: str,
    amount_transferred: float
) -> EscrowTransactionResult:
    """
    Internal helper to construct, sign, broadcast, and await transactions asynchronously.
    Uses sequential nonce locking for concurrent safety.
    """
    if MOCK_WEB3:
        return _generate_mock_result(action_name, task_id, amount_transferred)

    w3 = get_async_w3()
    account = get_protocol_account()

    try:
        is_connected = await w3.is_connected()
        if not is_connected:
            raise ConnectionError(f"Cannot connect to Web3 RPC at {RPC_URL}")

        async with _nonce_lock:
            nonce = await w3.eth.get_transaction_count(account.address, "pending")
            gas_price = await w3.eth.gas_price
            chain_id = await w3.eth.chain_id

            tx_params = {
                "from": account.address,
                "nonce": nonce,
                "gasPrice": gas_price,
                "chainId": chain_id,
            }

            # Build contract transaction
            tx_data = await build_tx_coroutine_fn(tx_params)

            # Estimate gas with safety margin
            try:
                estimated_gas = await w3.eth.estimate_gas(tx_data)
                tx_data["gas"] = int(estimated_gas * 1.25)
            except Exception as gas_err:
                logger.debug(f"Gas estimation fallback triggered: {gas_err}")
                tx_data["gas"] = 350000

            # Sign transaction
            signed_tx = account.sign_transaction(tx_data)

            # Send raw transaction
            tx_hash_bytes = await w3.eth.send_raw_transaction(signed_tx.raw_transaction)
            tx_hash_str = tx_hash_bytes.hex()
            if not tx_hash_str.startswith("0x"):
                tx_hash_str = f"0x{tx_hash_str}"

            logger.info(f"Broadcasted {action_name} for task {task_id}: {tx_hash_str}")

            # Wait for receipt non-blockingly
            receipt = await w3.eth.wait_for_transaction_receipt(tx_hash_bytes, timeout=120)
            block_number = receipt.blockNumber

            # Retrieve block timestamp
            block = await w3.eth.get_block(block_number)
            timestamp = block.get("timestamp", int(time.time()))

            return {
                "success": True,
                "tx_hash": tx_hash_str,
                "block_number": int(block_number),
                "task_id": task_id,
                "action": action_name,
                "amount_transferred": float(amount_transferred),
                "timestamp": int(timestamp)
            }

    except Exception as exc:
        logger.error(f"Web3 execution error during {action_name} for task {task_id}: {exc}")
        if ALLOW_FALLBACK_ON_ERROR:
            logger.warning("Falling back to dev/mock result due to ALLOW_FALLBACK_ON_ERROR=true")
            return _generate_mock_result(action_name, task_id, amount_transferred)
        raise EscrowExecutionError(f"Escrow operation '{action_name}' failed for task '{task_id}': {exc}") from exc


# --- CORE ASYNC WEB3 TRANSACTIONS ---

async def deposit_task_escrow(
    task_id: str,
    requester_address: str,
    amount_usdc: Union[float, int, str, Decimal]
) -> EscrowTransactionResult:
    """
    Locks USDC escrow into the smart contract for a specific task.
    """
    task_id_bytes = hash_task_id(task_id)
    raw_amount = to_raw_token_units(amount_usdc)
    checksum_requester = AsyncWeb3.to_checksum_address(requester_address)
    contract = get_escrow_contract()

    async def _build(tx_params):
        return await contract.functions.depositEscrowFor(
            task_id_bytes,
            checksum_requester,
            raw_amount
        ).build_transaction(tx_params)

    return await _execute_contract_call(_build, "DEPOSIT", task_id, float(amount_usdc))


async def lock_worker_bond(
    task_id: str,
    worker_address: str,
    bond_amount_usdc: Union[float, int, str, Decimal]
) -> EscrowTransactionResult:
    """
    Allows an autonomous Worker agent to lock their collateral bond for a specific task.
    """
    task_id_bytes = hash_task_id(task_id)
    raw_bond = to_raw_token_units(bond_amount_usdc)
    checksum_worker = AsyncWeb3.to_checksum_address(worker_address)
    contract = get_escrow_contract()

    async def _build(tx_params):
        return await contract.functions.lockWorkerBondFor(
            task_id_bytes,
            checksum_worker,
            raw_bond
        ).build_transaction(tx_params)

    return await _execute_contract_call(_build, "LOCK_BOND", task_id, float(bond_amount_usdc))


async def settle_successful_payout(
    task_id: str,
    worker_address: str,
    payout_usdc: Union[float, int, str, Decimal]
) -> EscrowTransactionResult:
    """
    Called by the authorized protocol oracle wallet to release the escrow + return
    the collateral bond to the worker upon successful verification.
    """
    task_id_bytes = hash_task_id(task_id)
    checksum_worker = AsyncWeb3.to_checksum_address(worker_address)
    contract = get_escrow_contract()

    async def _build(tx_params):
        return await contract.functions.settlePayout(
            task_id_bytes,
            checksum_worker
        ).build_transaction(tx_params)

    return await _execute_contract_call(_build, "SETTLE_PAYOUT", task_id, float(payout_usdc))


async def execute_slash(
    task_id: str,
    worker_address: str,
    requester_address: str,
    bond_amount_usdc: Union[float, int, str, Decimal]
) -> EscrowTransactionResult:
    """
    Called by the protocol oracle upon failed verification to slash the worker's bond
    and refund the initial escrow to the requester.
    """
    task_id_bytes = hash_task_id(task_id)
    checksum_worker = AsyncWeb3.to_checksum_address(worker_address)
    checksum_requester = AsyncWeb3.to_checksum_address(requester_address)
    contract = get_escrow_contract()

    async def _build(tx_params):
        return await contract.functions.slashWorker(
            task_id_bytes,
            checksum_worker,
            checksum_requester
        ).build_transaction(tx_params)

    return await _execute_contract_call(_build, "SLASH", task_id, float(bond_amount_usdc))


async def cancel_task(
    task_id: str,
    amount_usdc: Union[float, int, str, Decimal] = 0.0
) -> EscrowTransactionResult:
    """
    Cancels an unassigned task and refunds the deposited escrow to the requester.
    """
    task_id_bytes = hash_task_id(task_id)
    contract = get_escrow_contract()

    async def _build(tx_params):
        return await contract.functions.cancelTask(task_id_bytes).build_transaction(tx_params)

    return await _execute_contract_call(_build, "CANCEL", task_id, float(amount_usdc))


# --- READ / VIEW CONTRACT METHODS ---

async def get_task(task_id: str) -> Optional[TaskEscrowDetails]:
    """
    Queries on-chain task details by task_id string.
    Returns None if MOCK_WEB3 is active or if task is uninitialized.
    """
    if MOCK_WEB3:
        return None

    task_id_bytes = hash_task_id(task_id)
    contract = get_escrow_contract()

    try:
        data = await contract.functions.getTask(task_id_bytes).call()
        # Tuple order: [taskId, requester, worker, escrowAmount, workerBond, state, createdAt, settledAt]
        state = TaskState(data[5])
        if state == TaskState.NONE:
            return None

        return {
            "task_id": task_id,
            "requester": data[1],
            "worker": data[2],
            "escrow_amount": from_raw_token_units(data[3]),
            "worker_bond": from_raw_token_units(data[4]),
            "state": state,
            "created_at": int(data[6]),
            "settled_at": int(data[7])
        }
    except Exception as exc:
        logger.error(f"Failed to query getTask({task_id}): {exc}")
        raise EscrowExecutionError(f"Failed to query task '{task_id}': {exc}") from exc


async def get_task_state(task_id: str) -> Optional[TaskState]:
    """Queries on-chain task lifecycle state."""
    if MOCK_WEB3:
        return None

    task_id_bytes = hash_task_id(task_id)
    contract = get_escrow_contract()

    try:
        state_int = await contract.functions.getTaskState(task_id_bytes).call()
        return TaskState(state_int)
    except Exception as exc:
        logger.error(f"Failed to query getTaskState({task_id}): {exc}")
        raise EscrowExecutionError(f"Failed to query state for '{task_id}': {exc}") from exc


async def get_total_tasks() -> int:
    """Queries the total count of registered tasks on the contract."""
    if MOCK_WEB3:
        return 0

    contract = get_escrow_contract()
    try:
        return await contract.functions.getTotalTasks().call()
    except Exception as exc:
        logger.error(f"Failed to query getTotalTasks: {exc}")
        raise EscrowExecutionError(f"Failed to query total tasks: {exc}") from exc

