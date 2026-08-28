"""
ATOA Multi-Agent Runner:
Launches Code, Research, and Query autonomous worker agents in concurrent background threads.
"""

import threading
import time
from agents_demo.code_agent import run_agent as run_code_agent
from agents_demo.research_agent import run_agent as run_research_agent
from agents_demo.query_agent import run_agent as run_query_agent

def main():
    print("=" * 60)
    print("  ATOA Autonomous Worker Fleet: Launching 3 Specialized Nodes")
    print("  • Code Agent      [0xAgent_Code_Optimizer]")
    print("  • Research Agent  [0xAgent_Researcher_Node]")
    print("  • Query Agent     [0xAgent_Query_Oracle]")
    print("=" * 60)

    t1 = threading.Thread(target=run_code_agent, daemon=True)
    t2 = threading.Thread(target=run_research_agent, daemon=True)
    t3 = threading.Thread(target=run_query_agent, daemon=True)

    t1.start()
    t2.start()
    t3.start()

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\nStopping ATOA worker fleet...")

if __name__ == "__main__":
    main()
