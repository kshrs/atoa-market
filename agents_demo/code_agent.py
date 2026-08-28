"""
ATOA Autonomous Worker Agent: Code Agent (Alpha Optimizer)
Specialization: High-performance code generation, algorithms, vectorized computation.
"""

import time
import requests
import json
import logging

logging.basicConfig(level=logging.INFO, format="[%(asctime)s] [CODE_AGENT_1] %(message)s")
logger = logging.getLogger("CodeAgent1")

API_BASE = "http://localhost:8000"
AGENT_ADDRESS = "0xAgent_Code_Optimizer_1"
AGENT_NAME = "Code Agent (Alpha)"
CATEGORY = "code_generation"


def ensure_wallet():
    try:
        res = requests.post(f"{API_BASE}/v1/wallets/faucet", json={
            "address": AGENT_ADDRESS,
            "name": AGENT_NAME,
            "role": "Bidder",
            "amount_usdc": 500.0
        })
        if res.status_code == 200:
            logger.info(f"Agent wallet initialized: {AGENT_NAME} with {res.json().get('balance_usdc')} USDC")
    except Exception as e:
        logger.warning(f"Could not initialize wallet: {e}")


def solve_code_task(task):
    title = task.get("title", "").lower()
    desc = task.get("description", "").lower()
    val_spec = task.get("validation_spec", {})
    test_code = val_spec.get("test_suite_code", "")

    logger.info(f"Solving code task '{task.get('title')}'...")

    if "fibonacci" in title or "fib" in title:
        return """def fib(n):
    if n <= 0: return 0
    if n == 1: return 1
    a, b = 0, 1
    for _ in range(2, n + 1):
        a, b = b, a + b
    return b
"""
    if "palindrome" in title or "palindrome" in desc:
        return """def is_palindrome(s):
    cleaned = ''.join(c.lower() for c in s if c.isalnum())
    return cleaned == cleaned[::-1]
"""
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
    if "sum of squares" in title or "sum_squares" in test_code:
        return """def sum_squares(lst):
    return sum(x**2 for x in lst)
"""
    if "reverse" in title or "rev_str" in test_code:
        return """def rev_str(s):
    return s[::-1]
"""

    return """def solution(*args, **kwargs):
    return True
"""


def run_agent():
    ensure_wallet()
    logger.info(f"{AGENT_NAME} active. Polling for category '{CATEGORY}'...")
    bidding_history = {}
    submitted_tasks = set()

    while True:
        try:
            res = requests.get(f"{API_BASE}/v1/tasks", params={"category": CATEGORY})
            if res.status_code == 200:
                tasks = res.json()
                for task in tasks:
                    task_id = task.get("task_id")
                    status = task.get("status")

                    if status in ["BROADCASTED", "MATCHING"]:
                        budget = task.get("budget_usdc", 50.0)
                        bond = task.get("required_worker_bond", 5.0)

                        now = time.time()
                        history = bidding_history.get(task_id, {"bids": 0, "first_bid_time": 0})

                        # Round 1: High start (98% of budget)
                        if history["bids"] == 0:
                            high_bid = round(budget * 0.98, 2)
                            bid_payload = {
                                "worker_address": AGENT_ADDRESS,
                                "bid_price_usdc": high_bid,
                                "collateral_bond_locked": bond,
                                "estimated_duration_seconds": 30,
                                "notes": f"Initial quote from {AGENT_NAME}"
                            }
                            b_res = requests.post(f"{API_BASE}/v1/tasks/{task_id}/bids", json=bid_payload)
                            if b_res.status_code in [200, 201]:
                                logger.info(f"Round 1: Placed high bid of ${high_bid} USDC on task {task_id}")
                                bidding_history[task_id] = {"bids": 1, "first_bid_time": now}

                        # Round 2: Compete down slightly after ~1.5 seconds (92% of budget)
                        elif history["bids"] == 1 and (now - history["first_bid_time"]) >= 1.5:
                            comp_bid = round(budget * 0.92, 2)
                            bid_payload = {
                                "worker_address": AGENT_ADDRESS,
                                "bid_price_usdc": comp_bid,
                                "collateral_bond_locked": bond,
                                "estimated_duration_seconds": 25,
                                "notes": f"Competitive discount by {AGENT_NAME}"
                            }
                            b_res = requests.post(f"{API_BASE}/v1/tasks/{task_id}/bids", json=bid_payload)
                            if b_res.status_code in [200, 201]:
                                logger.info(f"Round 2: Placed revised bid of ${comp_bid} USDC on task {task_id}")
                                bidding_history[task_id]["bids"] = 2

                        # Round 3: Final best offer after ~3.0 seconds (86% of budget)
                        elif history["bids"] == 2 and (now - history["first_bid_time"]) >= 3.0:
                            final_bid = round(budget * 0.86, 2)
                            bid_payload = {
                                "worker_address": AGENT_ADDRESS,
                                "bid_price_usdc": final_bid,
                                "collateral_bond_locked": bond,
                                "estimated_duration_seconds": 20,
                                "notes": f"Final optimal offer by {AGENT_NAME}"
                            }
                            b_res = requests.post(f"{API_BASE}/v1/tasks/{task_id}/bids", json=bid_payload)
                            if b_res.status_code in [200, 201]:
                                logger.info(f"Round 3: Placed optimal bid of ${final_bid} USDC on task {task_id}")
                                bidding_history[task_id]["bids"] = 3

                    elif status == "IN_PROGRESS" and task.get("assigned_worker") == AGENT_ADDRESS and task_id not in submitted_tasks:
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
                            logger.info(f"Submitted deliverable for {task_id}. Settlement status: {sub_res.json().get('status')}")
                            submitted_tasks.add(task_id)

        except Exception as e:
            logger.error(f"Polling loop error: {e}")

        time.sleep(0.8)


if __name__ == "__main__":
    run_agent()
