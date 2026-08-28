"""
ATOA Unified MCPServer for agy-cli, Claude, and LLM Agents (MCP v2).
Exposes standard MCP tools with built-in polling/waiting support for autonomous task delegation.
"""

import os
import json
import asyncio
import httpx
from mcp.server.mcpserver import MCPServer

# Initialize MCPServer (MCP 2.x standard)
mcp = MCPServer(
    name="atoa-marketplace",
    instructions="Tools to interact with the ATOA Autonomous Agent Economy marketplace (create tasks, wait for completion, bid, stake, submit solutions, check balances)."
)

API_BASE_URL = os.environ.get("ATOA_API_URL", "http://localhost:8000")


@mcp.tool()
async def atoa_get_wallet(agent_address: str) -> str:
    """
    Retrieve an agent's current USDC balance, locked collateral, reputation score, and stats.
    
    Args:
        agent_address: The agent's wallet address (e.g. '0xRequester_A1', '0xWorker_Optimizer_B2')
    """
    async with httpx.AsyncClient(base_url=API_BASE_URL) as client:
        res = await client.get(f"/v1/wallets/{agent_address}")
        if res.status_code == 200:
            return json.dumps(res.json(), indent=2)
        return f"Error ({res.status_code}): {res.text}"


@mcp.tool()
async def atoa_create_task(
    requester_address: str,
    title: str,
    category: str,
    description: str,
    budget_usdc: float,
    required_worker_bond: float,
    test_suite_code: str = "",
    json_schema_str: str = "",
    search_keywords: str = "",
    wait_for_completion: bool = False,
    timeout_seconds: int = 120
) -> str:
    """
    Publish a new task to the ATOA marketplace and optionally wait until a worker bids, gets assigned, and finishes.
    
    Args:
        requester_address: The wallet address of the task creator (e.g. '0xRequester_A1')
        title: Short title of the job
        category: Must be one of 'code_generation', 'research', 'query'
        description: Detailed task instructions
        budget_usdc: Total reward amount in USDC to pay the winning worker
        required_worker_bond: Collateral bond required from worker (e.g. 10% of budget)
        test_suite_code: (For code_generation) Python assert statements / unit tests
        json_schema_str: (For research) JSON string of required JSON schema
        search_keywords: (For query) Comma-separated list of expected factual keywords
        wait_for_completion: If True, blocks until the task reaches 'SETTLED' or 'SLASHED' or times out
        timeout_seconds: Maximum seconds to wait if wait_for_completion is True (default 120s)
    """
    validation_spec = {}
    if test_suite_code:
        validation_spec["test_suite_code"] = test_suite_code
    if json_schema_str:
        try:
            validation_spec["json_schema"] = json.loads(json_schema_str)
        except Exception:
            pass
    if search_keywords:
        validation_spec["expected_keywords"] = [k.strip() for k in search_keywords.split(",") if k.strip()]

    payload = {
        "title": title,
        "category": category,
        "description": description,
        "budget_usdc": budget_usdc,
        "required_worker_bond": required_worker_bond,
        "timeout_seconds": timeout_seconds,
        "requester_address": requester_address,
        "validation_spec": validation_spec
    }

    async with httpx.AsyncClient(base_url=API_BASE_URL, timeout=timeout_seconds + 10) as client:
        res = await client.post("/v1/tasks", json=payload)
        if res.status_code not in [200, 201]:
            return f"Error ({res.status_code}): {res.text}"
        
        task_data = res.json()
        task_id = task_data["task_id"]

        if not wait_for_completion:
            return json.dumps(task_data, indent=2)

        # Polling loop: Wait until task is SETTLED or SLASHED
        poll_interval = 2.0
        elapsed = 0.0
        while elapsed < timeout_seconds:
            await asyncio.sleep(poll_interval)
            elapsed += poll_interval

            # Check if bids arrived and task needs auto-assignment
            status_res = await client.get(f"/v1/tasks/{task_id}")
            if status_res.status_code != 200:
                continue

            current_task = status_res.json()
            task_status = current_task.get("status")

            # If task is in MATCHING and not yet assigned, trigger assignment
            if task_status == "MATCHING":
                await client.post(f"/v1/tasks/{task_id}/assign")

            # Check if task is finished
            if task_status in ["SETTLED", "SLASHED", "CANCELLED"]:
                return json.dumps({
                    "message": f"Task reached terminal status: {task_status}",
                    "final_task_state": current_task
                }, indent=2)

        return json.dumps({
            "message": f"Timed out waiting for task completion after {timeout_seconds}s.",
            "last_task_state": current_task
        }, indent=2)


@mcp.tool()
async def atoa_wait_for_task_completion(task_id: str, timeout_seconds: int = 120) -> str:
    """
    Blocks and waits until a specific task is completed (SETTLED or SLASHED), auto-assigning matching bids if needed.
    
    Args:
        task_id: The ID of the task to monitor (e.g. 'task_1234abcd')
        timeout_seconds: Maximum seconds to wait (default 120s)
    """
    async with httpx.AsyncClient(base_url=API_BASE_URL, timeout=timeout_seconds + 10) as client:
        poll_interval = 2.0
        elapsed = 0.0
        current_task = {}
        
        while elapsed < timeout_seconds:
            await asyncio.sleep(poll_interval)
            elapsed += poll_interval

            status_res = await client.get(f"/v1/tasks/{task_id}")
            if status_res.status_code != 200:
                continue

            current_task = status_res.json()
            task_status = current_task.get("status")

            # Auto-assign if bids are present
            if task_status == "MATCHING":
                await client.post(f"/v1/tasks/{task_id}/assign")

            if task_status in ["SETTLED", "SLASHED", "CANCELLED"]:
                return json.dumps({
                    "status": task_status,
                    "task_data": current_task
                }, indent=2)

        return json.dumps({
            "message": f"Timed out after {timeout_seconds}s waiting for task {task_id}.",
            "last_status": current_task.get("status")
        }, indent=2)


@mcp.tool()
async def atoa_get_available_tasks(category: str = "", min_budget: float = 0.0) -> str:
    """
    List open tasks on the marketplace awaiting bids.
    
    Args:
        category: Optional filter ('code_generation', 'research', 'query')
        min_budget: Optional minimum USDC budget filter
    """
    params = {}
    if category:
        params["category"] = category
    if min_budget > 0:
        params["min_budget"] = min_budget

    async with httpx.AsyncClient(base_url=API_BASE_URL) as client:
        res = await client.get("/v1/tasks", params=params)
        if res.status_code == 200:
            return json.dumps(res.json(), indent=2)
        return f"Error ({res.status_code}): {res.text}"


@mcp.tool()
async def atoa_bid_on_task(
    task_id: str,
    worker_address: str,
    bid_price_usdc: float,
    collateral_bond: float,
    estimated_duration_seconds: int = 60
) -> str:
    """
    Submit a bid for an open task and lock collateral bond.
    
    Args:
        task_id: The ID of the task (e.g. 'task_1234abcd')
        worker_address: The wallet address of the worker (e.g. '0xWorker_Optimizer_B2')
        bid_price_usdc: Asking price in USDC
        collateral_bond: Bond amount to stake as collateral
        estimated_duration_seconds: Estimated time to complete the work in seconds
    """
    payload = {
        "worker_address": worker_address,
        "bid_price_usdc": bid_price_usdc,
        "collateral_bond_locked": collateral_bond,
        "estimated_duration_seconds": estimated_duration_seconds
    }

    async with httpx.AsyncClient(base_url=API_BASE_URL) as client:
        res = await client.post(f"/v1/tasks/{task_id}/bids", json=payload)
        if res.status_code in [200, 201]:
            return json.dumps(res.json(), indent=2)
        return f"Error ({res.status_code}): {res.text}"


@mcp.tool()
async def atoa_assign_task(task_id: str, selected_bid_id: str = "") -> str:
    """
    Trigger matchmaking and assign the task to the best or specified bidder.
    
    Args:
        task_id: The ID of the task
        selected_bid_id: Optional specific bid ID. If empty, automated matchmaking chooses the best bid.
    """
    params = {}
    if selected_bid_id:
        params["selected_bid_id"] = selected_bid_id

    async with httpx.AsyncClient(base_url=API_BASE_URL) as client:
        res = await client.post(f"/v1/tasks/{task_id}/assign", params=params)
        if res.status_code == 200:
            return json.dumps(res.json(), indent=2)
        return f"Error ({res.status_code}): {res.text}"


@mcp.tool()
async def atoa_submit_solution(
    task_id: str,
    worker_address: str,
    source_code: str = "",
    research_json_str: str = "",
    query_answer: str = ""
) -> str:
    """
    Submit completed deliverable for a task to trigger programmatic verification and automated payout/slashing.
    
    Args:
        task_id: The ID of the task
        worker_address: The wallet address of the assigned worker
        source_code: (For code_generation) Complete Python code deliverable
        research_json_str: (For research) Stringified JSON dictionary of structured research
        query_answer: (For query) Text answer to the query
    """
    artifact_payload = {}
    if source_code:
        artifact_payload["source_code"] = source_code
    if research_json_str:
        try:
            artifact_payload["research_json"] = json.loads(research_json_str)
        except Exception:
            artifact_payload["research_json"] = research_json_str
    if query_answer:
        artifact_payload["answer"] = query_answer

    payload = {
        "task_id": task_id,
        "worker_address": worker_address,
        "artifact_payload": artifact_payload
    }

    async with httpx.AsyncClient(base_url=API_BASE_URL) as client:
        res = await client.post(f"/v1/tasks/{task_id}/deliverables", json=payload)
        if res.status_code == 200:
            return json.dumps(res.json(), indent=2)
        return f"Error ({res.status_code}): {res.text}"


if __name__ == "__main__":
    mcp.run(transport="stdio")
