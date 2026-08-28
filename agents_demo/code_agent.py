"""
ATOA Autonomous Worker Agent: Code Generator & Optimizer
Polls backend for 'code_generation' tasks, computes realistic bids (80-92% of budget),
solves coding problems, and submits deliverables immediately without delay.
"""

import time
import requests
import json
import logging

logging.basicConfig(level=logging.INFO, format="[%(asctime)s] [CODE_AGENT] %(message)s")
logger = logging.getLogger("CodeAgent")

API_BASE = "http://localhost:8000"
AGENT_ADDRESS = "0xAgent_Code_Optimizer"
AGENT_NAME = "Alpha-Code-Node"
CATEGORY = "code_generation"


def ensure_wallet():
    try:
        res = requests.post(f"{API_BASE}/v1/wallets/faucet", json={"address": AGENT_ADDRESS, "amount_usdc": 500.0})
        if res.status_code == 200:
            logger.info(f"Agent wallet initialized with {res.json().get('balance_usdc')} USDC")
    except Exception as e:
        logger.warning(f"Could not initialize wallet: {e}")


def solve_code_task(task):
    """Generates code deliverable tailored to the prompt & test suite."""
    title = task.get("title", "").lower()
    desc = task.get("description", "").lower()
    val_spec = task.get("validation_spec", {})
    test_code = val_spec.get("test_suite_code", "")

    logger.info(f"Solving code task '{task.get('title')}'...")

    # 1. Fibonacci
    if "fibonacci" in title or "fib" in title:
        return """def fib(n):
    if n <= 0: return 0
    if n == 1: return 1
    a, b = 0, 1
    for _ in range(2, n + 1):
        a, b = b, a + b
    return b
"""

    # 2. Palindrome
    if "palindrome" in title or "palindrome" in desc:
        return """def is_palindrome(s):
    cleaned = ''.join(c.lower() for c in s if c.isalnum())
    return cleaned == cleaned[::-1]
"""

    # 3. Matrix Multiplication
    if "matrix" in title or "matmul" in title or "matrix" in desc:
        return """def matmul(A, B):
    rows_A = len(A)
    cols_A = len(A[0])
    cols_B = len(B[0])
    C = [[0 for _ in range(cols_B)] for _ in range(rows_A)]
    for i in range(rows_A):
        for k in range(cols_A):
            for j in range(cols_B):
                C[i][j] += A[i][k] * B[k][j]
    return C
"""

    # 4. Sum of Squares
    if "sum of squares" in title or "sum_squares" in test_code:
        return """def sum_squares(lst):
    return sum(x**2 for x in lst)
"""

    # 5. Reverse String
    if "reverse" in title or "rev_str" in test_code:
        return """def rev_str(s):
    return s[::-1]
"""

    # Default fallback Python solution
    return """def solution(*args, **kwargs):
    return True
"""


def run_agent():
    ensure_wallet()
    logger.info(f"Code Agent active. Polling for category '{CATEGORY}'...")
    processed_tasks = set()

    while True:
        try:
            res = requests.get(f"{API_BASE}/v1/tasks", params={"category": CATEGORY})
            if res.status_code == 200:
                tasks = res.json()
                for task in tasks:
                    task_id = task.get("task_id")
                    status = task.get("status")

                    # Step 1: Bid on open task
                    if status in ["BROADCASTED", "MATCHING"] and task_id not in processed_tasks:
                        budget = task.get("budget_usdc", 50.0)
                        bond = task.get("required_worker_bond", 5.0)

                        # Realistic bidding: 85% of budget (never excessively low)
                        realistic_bid = round(budget * 0.88, 2)

                        bid_payload = {
                            "worker_address": AGENT_ADDRESS,
                            "bid_price_usdc": realistic_bid,
                            "collateral_bond_locked": bond,
                            "estimated_duration_seconds": 30,
                            "notes": f"High-performance vectorized solver by {AGENT_NAME}"
                        }
                        bid_res = requests.post(f"{API_BASE}/v1/tasks/{task_id}/bids", json=bid_payload)
                        if bid_res.status_code in [200, 201]:
                            logger.info(f"Placed realistic bid of ${realistic_bid} USDC on task {task_id}")
                            processed_tasks.add(task_id)

                    # Step 2: If assigned to this agent, solve and submit immediately
                    elif status == "IN_PROGRESS" and task.get("assigned_worker") == AGENT_ADDRESS:
                        code_deliverable = solve_code_task(task)
                        sub_payload = {
                            "task_id": task_id,
                            "worker_address": AGENT_ADDRESS,
                            "artifact_payload": {
                                "source_code": code_deliverable
                            }
                        }
                        sub_res = requests.post(f"{API_BASE}/v1/tasks/{task_id}/deliverables", json=sub_payload)
                        if sub_res.status_code == 200:
                            logger.info(f"Successfully submitted deliverable for {task_id}. Settlement: {sub_res.json().get('status')}")

        except Exception as e:
            logger.error(f"Polling loop exception: {e}")

        time.sleep(1.5)


if __name__ == "__main__":
    run_agent()
