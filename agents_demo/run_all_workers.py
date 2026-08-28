"""
ATOA Multi-Agent Autonomous Fleet Runner:
Launches 5 Specialized Autonomous Worker Nodes concurrently:
• Code Agent (Alpha)     [code_agent.py]
• Code Agent (Beta)      [code_agent_2.py]
• Research Agent (Alpha) [research_agent.py]
• Research Agent (Beta)  [research_agent_2.py]
• Query Agent            [query_agent.py]
"""

import threading
import time
from agents_demo.code_agent import run_agent as run_code_1
from agents_demo.code_agent_2 import run_agent as run_code_2
from agents_demo.research_agent import run_agent as run_res_1
from agents_demo.research_agent_2 import run_agent as run_res_2
from agents_demo.query_agent import run_agent as run_query

def main():
    print("=" * 68)
    print("  ATOA Autonomous Multi-Agent Marketplace Fleet (5 Worker Nodes)")
    print("  1. Code Agent (Alpha)     [code_agent.py]")
    print("  2. Code Agent (Beta)      [code_agent_2.py]")
    print("  3. Research Agent (Alpha) [research_agent.py]")
    print("  4. Research Agent (Beta)  [research_agent_2.py]")
    print("  5. Query Agent            [query_agent.py]")
    print("=" * 68)

    threads = [
        threading.Thread(target=run_code_1, daemon=True),
        threading.Thread(target=run_code_2, daemon=True),
        threading.Thread(target=run_res_1, daemon=True),
        threading.Thread(target=run_res_2, daemon=True),
        threading.Thread(target=run_query, daemon=True),
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
