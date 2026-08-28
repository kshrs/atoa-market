"""
ATOA Autonomous Delegator Daemon:
Continuously publishes diverse, parameterized tasks across Code Generation, Research Synthesis,
and Fact-Assertion Query domains with randomized budgets, collateral stakes, and validation specs.
"""

import time
import random
import requests
import logging

logging.basicConfig(level=logging.INFO, format="[%(asctime)s] [DELEGATOR_DAEMON] %(message)s")
logger = logging.getLogger("DelegatorDaemon")

API_BASE = "http://localhost:8000"
DELEGATOR_ADDRESS = "0xDelegator_Autonomous_Daemon"
DELEGATOR_NAME = "Delegator Daemon"


TASK_TEMPLATES = [
    # --- 1. CODE GENERATION TEMPLATES ---
    {
        "title": "Optimized Fibonacci Sequence Generator",
        "category": "code_generation",
        "description": "Compute the nth Fibonacci number efficiently with O(1) space complexity.",
        "budget_range": (35.0, 55.0),
        "bond_range": (4.0, 7.0),
        "validation_spec": {
            "test_suite_code": "from solution import fib\ndef test_fib():\n    assert fib(0) == 0\n    assert fib(1) == 1\n    assert fib(7) == 13\n    assert fib(10) == 55"
        }
    },
    {
        "title": "Alphanumeric Palindrome Verifier",
        "category": "code_generation",
        "description": "Verify if an input string is a valid palindrome ignoring non-alphanumeric characters.",
        "budget_range": (25.0, 45.0),
        "bond_range": (3.0, 5.0),
        "validation_spec": {
            "test_suite_code": "from solution import is_palindrome\ndef test_pal():\n    assert is_palindrome('A man, a plan, a canal: Panama') == True\n    assert is_palindrome('race a car') == False\n    assert is_palindrome('') == True"
        }
    },
    {
        "title": "Vectorized 2D Matrix Multiplication Kernel",
        "category": "code_generation",
        "description": "Compute the dot product multiplication of two 2D numerical matrices.",
        "budget_range": (50.0, 80.0),
        "bond_range": (6.0, 10.0),
        "validation_spec": {
            "test_suite_code": "from solution import matmul\ndef test_matmul():\n    A = [[1, 2], [3, 4]]\n    B = [[2, 0], [1, 2]]\n    assert matmul(A, B) == [[4, 4], [10, 8]]"
        }
    },
    {
        "title": "Sum of Squares Vector Reducer",
        "category": "code_generation",
        "description": "Calculate the sum of squares for an array of integers.",
        "budget_range": (30.0, 50.0),
        "bond_range": (4.0, 6.0),
        "validation_spec": {
            "test_suite_code": "from solution import sum_squares\ndef test_sum_squares():\n    assert sum_squares([1, 2, 3]) == 14\n    assert sum_squares([]) == 0\n    assert sum_squares([-2, 3]) == 13"
        }
    },

    # --- 2. RESEARCH SYNTHESIS TEMPLATES ---
    {
        "title": "Zero-Knowledge Rollup Settlement Latency",
        "category": "research",
        "description": "Synthesize empirical performance analysis on recursive ZK-SNARK batch verification.",
        "budget_range": (45.0, 75.0),
        "bond_range": (5.0, 9.0),
        "validation_spec": {
            "required_keys": ["executive_summary", "methodology", "findings", "citations", "confidence_score"],
            "json_schema": {
                "type": "object",
                "required": ["executive_summary", "findings", "citations"],
                "properties": {
                    "executive_summary": {"type": "string"},
                    "findings": {"type": "array"},
                    "confidence_score": {"type": "number"}
                }
            }
        }
    },
    {
        "title": "Autonomous Agent Game-Theoretic Collateral Bonding",
        "category": "research",
        "description": "Investigate slashing dynamics and anti-Sybil guarantees in decentralized agent markets.",
        "budget_range": (50.0, 85.0),
        "bond_range": (6.0, 10.0),
        "validation_spec": {
            "required_keys": ["executive_summary", "findings", "citations"],
            "json_schema": {
                "type": "object",
                "required": ["findings", "citations"]
            }
        }
    },
    {
        "title": "Decentralized LLM Routing & Quantization Benchmarks",
        "category": "research",
        "description": "Literature review on 4-bit AWQ shard execution latencies across decentralized clusters.",
        "budget_range": (40.0, 70.0),
        "bond_range": (5.0, 8.0),
        "validation_spec": {
            "required_keys": ["executive_summary", "methodology", "findings"],
            "json_schema": {
                "type": "object",
                "required": ["executive_summary", "methodology"]
            }
        }
    },

    # --- 3. FACT-ASSERTION QUERY TEMPLATES ---
    {
        "title": "Solana Consensus & Throughput Verification",
        "category": "query",
        "description": "Verify high-frequency transaction throughput and Proof of History consensus parameters.",
        "budget_range": (20.0, 40.0),
        "bond_range": (2.0, 5.0),
        "validation_spec": {
            "search_query": "Solana Proof of History consensus throughput",
            "expected_keywords": ["Solana", "throughput", "consensus", "verified"]
        }
    },
    {
        "title": "Ethereum ERC-4337 Account Abstraction Protocol",
        "category": "query",
        "description": "Assert ground-truth definitions and bundler specifications for ERC-4337 smart contract wallets.",
        "budget_range": (25.0, 45.0),
        "bond_range": (3.0, 5.0),
        "validation_spec": {
            "search_query": "ERC-4337 Account Abstraction bundler",
            "expected_keywords": ["ERC-4337", "Abstraction", "wallets", "smart"]
        }
    },
    {
        "title": "Decentralized Oracle Slashing & Settlement Dynamics",
        "category": "query",
        "description": "Validate economic security proofs and dispute arbitration periods in decentralized oracles.",
        "budget_range": (25.0, 50.0),
        "bond_range": (3.0, 6.0),
        "validation_spec": {
            "search_query": "Oracle slashing settlement economic security",
            "expected_keywords": ["Oracle", "slashing", "security", "settlement"]
        }
    }
]


def ensure_delegator_wallet():
    """Ensure the Delegator wallet is funded with ample escrow capital."""
    try:
        res = requests.post(f"{API_BASE}/v1/wallets/faucet", json={
            "address": DELEGATOR_ADDRESS,
            "name": DELEGATOR_NAME,
            "role": "Delegator",
            "amount_usdc": 5000.0
        })
        if res.status_code == 200:
            logger.info(f"Delegator wallet ready with {res.json().get('balance_usdc')} USDC")
    except Exception as e:
        logger.warning(f"Could not initialize Delegator wallet: {e}")


def publish_random_task():
    """Selects a random template and posts a new task to the marketplace."""
    template = random.choice(TASK_TEMPLATES)
    budget = round(random.uniform(*template["budget_range"]), 2)
    bond = round(random.uniform(*template["bond_range"]), 2)

    task_payload = {
        "title": template["title"],
        "category": template["category"],
        "description": template["description"],
        "budget_usdc": budget,
        "required_worker_bond": bond,
        "timeout_seconds": 180,
        "requester_address": DELEGATOR_ADDRESS,
        "validation_spec": template["validation_spec"]
    }

    try:
        res = requests.post(f"{API_BASE}/v1/tasks", json=task_payload)
        if res.status_code in [200, 201]:
            task = res.json()
            logger.info(
                f"Published Task: [{task.get('category').upper()}] '{task.get('title')}' "
                f"(ID: {task.get('task_id')}, Budget: ${budget} USDC, Bond: ${bond} USDC)"
            )
            return task
        else:
            logger.error(f"Failed to publish task: ({res.status_code}) {res.text}")
    except Exception as e:
        logger.error(f"Error publishing task: {e}")
    return None


def run_delegator(interval_seconds: float = 6.0):
    """
    Main loop: Continuously publishes tasks with randomized intervals.
    """
    ensure_delegator_wallet()
    logger.info(f"Delegator Daemon initialized. Publishing new tasks every {interval_seconds}s...")

    while True:
        try:
            # Check how many tasks are currently open to avoid flooding
            res = requests.get(f"{API_BASE}/v1/tasks")
            if res.status_code == 200:
                open_tasks = [t for t in res.json() if t.get("status") in ["BROADCASTED", "MATCHING", "IN_PROGRESS"]]
                if len(open_tasks) < 5:
                    publish_random_task()
                else:
                    logger.info(f"{len(open_tasks)} active tasks in flight. Waiting for worker fleet to settle...")
        except Exception as e:
            logger.error(f"Delegator loop exception: {e}")

        # Stagger task generation interval slightly (e.g. 5–8 seconds)
        jitter = random.uniform(interval_seconds * 0.8, interval_seconds * 1.3)
        time.sleep(jitter)


if __name__ == "__main__":
    run_delegator(interval_seconds=6.0)
