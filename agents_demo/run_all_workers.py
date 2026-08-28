"""
ATOA Multi-Agent Autonomous Fleet Runner:
Launches 5 Specialized Autonomous Worker Nodes concurrently:
• Code Agent (Alpha)     [code_agent.py]
• Code Agent (Beta)      [code_agent_2.py]
• Research Agent (Alpha) [research_agent.py]
• Research Agent (Beta)  [research_agent_2.py]
• Query Agent            [query_agent.py]
Plus an automated Matchmaking Arbiter that triggers assignment once bids settle (~3.5s).
"""

import threading
import time
import requests
import logging
from agents_demo.code_agent import run_agent as run_code_1
from agents_demo.code_agent_2 import run_agent as run_code_2
from agents_demo.research_agent import run_agent as run_res_1
from agents_demo.research_agent_2 import run_agent as run_res_2
from agents_demo.query_agent import run_agent as run_query

API_BASE = "http://localhost:8000"
logging.basicConfig(level=logging.INFO, format="[%(asctime)s] [MATCHMAKER] %(message)s")
logger = logging.getLogger("Matchmaker")


def run_matchmaking_arbiter():
    """
    Monitors tasks in MATCHING state and triggers assignment once multi-round bids arrive (>3s).
    """
    logger.info("Matchmaking Arbiter active. Observing auction bidding rounds...")
    task_first_seen = {}

    while True:
        try:
            res = requests.get(f"{API_BASE}/v1/tasks")
            if res.status_code == 200:
                tasks = res.json()
                for task in tasks:
                    task_id = task.get("task_id")
                    status = task.get("status")
                    bids = task.get("bids", [])

                    now = time.time()
                    if status == "MATCHING" and len(bids) > 0:
                        if task_id not in task_first_seen:
                            task_first_seen[task_id] = now
                        
                        # Once auction window (~3.5s) elapses, assign winning bid
                        elif (now - task_first_seen[task_id]) >= 3.5:
                            assign_res = requests.post(f"{API_BASE}/v1/tasks/{task_id}/assign")
                            if assign_res.status_code == 200:
                                assigned = assign_res.json()
                                logger.info(
                                    f"Assigned task '{assigned.get('title')}' -> Winner: {assigned.get('assigned_worker')} "
                                    f"(Total Bids: {len(bids)})"
                                )
                                task_first_seen.pop(task_id, None)
        except Exception as e:
            logger.error(f"Matchmaker exception: {e}")

        time.sleep(1.0)


def main():
    print("=" * 68)
    print("  ATOA Autonomous Multi-Agent Marketplace Fleet (5 Worker Nodes)")
    print("  1. Code Agent (Alpha)     [code_agent.py]")
    print("  2. Code Agent (Beta)      [code_agent_2.py]")
    print("  3. Research Agent (Alpha) [research_agent.py]")
    print("  4. Research Agent (Beta)  [research_agent_2.py]")
    print("  5. Query Agent            [query_agent.py]")
    print("  + Matchmaking Arbiter (Auto-selects optimal bidder)")
    print("=" * 68)

    threads = [
        threading.Thread(target=run_code_1, daemon=True),
        threading.Thread(target=run_code_2, daemon=True),
        threading.Thread(target=run_res_1, daemon=True),
        threading.Thread(target=run_res_2, daemon=True),
        threading.Thread(target=run_query, daemon=True),
        threading.Thread(target=run_matchmaking_arbiter, daemon=True),
    ]

    for t in threads:
        t.start()

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\nShutting down ATOA worker nodes...")

if __name__ == "__main__":
    main()
