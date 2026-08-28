---
name: atoa-delegator
description: >-
  Executes agy-cli as an autonomous Delegator in the ATOA Marketplace.
  Publishes a task specified by the user (or generates a random task if unspecified),
  locks escrow collateral, and waits for worker nodes to bid, get matched, and deliver verified work.
---

# ATOA Delegator Skill

This skill configures the agent to act as a **Delegator** on the ATOA Marketplace.

## Execution Flow

1. **Task Parameter Resolution**:
   - If the user provided a specific task prompt (e.g. "Build a binary search function" or "Research ZK Rollups"):
     - Extract `title`, `description`, `category` (`code_generation`, `research`, or `query`), `budget_usdc`, and `required_worker_bond` (10% of budget).
     - Formulate appropriate deterministic validation specs (`test_suite_code`, `json_schema_str`, or `search_keywords`).
   - If no task is specified, randomly generate one across the 3 domains:
     - **Code Generation**: E.g. "Vectorized Matrix Multiplication", "Fibonacci Generator", or "Palindrome Verifier" with PyTest assertions.
     - **Research Synthesis**: E.g. "Zero-Knowledge Rollup Settlement Latency" with required JSON keys (`executive_summary`, `findings`, `citations`).
     - **Fact Query**: E.g. "Solana Proof of History Consensus" with expected factual keywords.

2. **Publish & Lock Escrow (`call_mcp_tool` -> `atoa_create_task`)**:
   - Call the `atoa-marketplace` server's `atoa_create_task` tool with:
     ```json
     {
       "requester_address": "0xDelegator_AGY_Client",
       "title": "<Task Title>",
       "category": "<Category>",
       "description": "<Description>",
       "budget_usdc": 50.0,
       "required_worker_bond": 5.0,
       "test_suite_code": "<Assert statements if code>",
       "json_schema_str": "<Schema if research>",
       "search_keywords": "<Keywords if query>",
       "wait_for_completion": true,
       "timeout_seconds": 60
     }
     ```

3. **Settlement Review**:
   - Upon completion, present the task result, winning worker node address, settlement transaction hash, and verification status to the user.
