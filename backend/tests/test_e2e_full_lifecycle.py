"""
End-to-End Test for the Complete ATOA Marketplace & Verification Pipeline.
Tests honest workflow settlement and malicious/rogue worker slashing across all domains.
"""

import pytest
from fastapi.testclient import TestClient
from backend.app.main import app

client = TestClient(app)


def test_code_generation_honest_settlement():
    # 1. Requester creates a task with unit test validation
    task_res = client.post("/v1/tasks", json={
        "title": "Build Sum of Squares",
        "category": "code_generation",
        "description": "Function returning sum of squares for a list of numbers",
        "budget_usdc": 40.0,
        "required_worker_bond": 4.0,
        "timeout_seconds": 120,
        "requester_address": "0xRequester_A1",
        "validation_spec": {
            "test_suite_code": "from solution import sum_squares\ndef test_sum_squares():\n    assert sum_squares([1, 2, 3]) == 14\n    assert sum_squares([]) == 0"
        }
    })
    assert task_res.status_code == 201
    task = task_res.json()
    task_id = task["task_id"]
    assert task["status"] == "BROADCASTED"

    # 2. Worker Alpha bids on task
    bid_res = client.post(f"/v1/tasks/{task_id}/bids", json={
        "worker_address": "0xWorker_Optimizer_B2",
        "bid_price_usdc": 35.0,
        "collateral_bond_locked": 4.0,
        "estimated_duration_seconds": 30
    })
    assert bid_res.status_code == 201

    # 3. Matchmaking assigns task
    assign_res = client.post(f"/v1/tasks/{task_id}/assign")
    assert assign_res.status_code == 200
    assert assign_res.json()["status"] == "IN_PROGRESS"
    assert assign_res.json()["assigned_worker"] == "0xWorker_Optimizer_B2"

    # 4. Worker submits correct solution
    deliver_res = client.post(f"/v1/tasks/{task_id}/deliverables", json={
        "task_id": task_id,
        "worker_address": "0xWorker_Optimizer_B2",
        "artifact_payload": {
            "source_code": "def sum_squares(lst):\n    return sum(x**2 for x in lst)"
        }
    })
    assert deliver_res.status_code == 200
    settled_task = deliver_res.json()
    assert settled_task["status"] == "SETTLED"
    assert settled_task["settlement_tx_hash"] is not None


def test_malicious_worker_slashing():
    # 1. Requester creates a task
    task_res = client.post("/v1/tasks", json={
        "title": "Reverse String Function",
        "category": "code_generation",
        "description": "Reverse a given string",
        "budget_usdc": 30.0,
        "required_worker_bond": 5.0,
        "timeout_seconds": 120,
        "requester_address": "0xRequester_A1",
        "validation_spec": {
            "test_suite_code": "from solution import rev_str\ndef test_rev():\n    assert rev_str('hello') == 'olleh'"
        }
    })
    assert task_res.status_code == 201
    task_id = task_res.json()["task_id"]

    # 2. Rogue Worker bids on task
    bid_res = client.post(f"/v1/tasks/{task_id}/bids", json={
        "worker_address": "0xWorker_Rogue_D4",
        "bid_price_usdc": 15.0,
        "collateral_bond_locked": 5.0,
        "estimated_duration_seconds": 5
    })
    assert bid_res.status_code == 201
    bid_id = bid_res.json()["bid_id"]

    # 3. Assign task to rogue worker
    assign_res = client.post(f"/v1/tasks/{task_id}/assign", params={"selected_bid_id": bid_id})
    assert assign_res.status_code == 200

    # 4. Rogue worker submits broken / spam code
    deliver_res = client.post(f"/v1/tasks/{task_id}/deliverables", json={
        "task_id": task_id,
        "worker_address": "0xWorker_Rogue_D4",
        "artifact_payload": {
            "source_code": "def rev_str(s):\n    return 'wrong_output'"  # Broken
        }
    })
    assert deliver_res.status_code == 200
    slashed_task = deliver_res.json()
    assert slashed_task["status"] == "SLASHED"
    assert slashed_task["settlement_tx_hash"] is not None

    # Verify that rogue worker reputation was slashed
    rogue_wallet = client.get("/v1/wallets/0xWorker_Rogue_D4").json()
    assert rogue_wallet["total_slashed_usdc"] >= 5.0
    assert rogue_wallet["failed_tasks_count"] >= 1
