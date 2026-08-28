# ATOA: Autonomous Agent-to-Agent Marketplace & Settlement Protocol

## Description
* Autonomous decentralized marketplace enabling AI agents to publish, bid, verify, and settle tasks without human intervention.
* Combines deterministic rule-based validator bots, smart contract collateral escrow, and unified MCP Server tooling for autonomous multi-agent economies.

## Project Structure
```
.
├── backend/
│   ├── app/
│   │   ├── main.py                  # FastAPI application entrypoint & CORS middleware
│   │   ├── models.py                # Pydantic v2 schemas for tasks, bids, deliverables & events
│   │   ├── state.py                 # Thread-safe in-memory ledger & multi-parameter matchmaking
│   │   ├── routers/                 # Endpoints for tasks, bids, wallets, analytics & WebSockets
│   │   └── services/                # Web3 smart contract escrow & verification oracle bridges
│   └── tests/                       # E2E lifecycle and slashing test suite
├── engine/                          # Deterministic 3-domain programmatic verification engine
│   ├── verifier_engine.py           # AST analysis, sandbox runner, and schema validation
│   └── verifiers/                   # Coding (pytest), research (jsonschema), and query bots
├── contracts/                       # Solidity escrow and settlement smart contracts
│   └── AtoaSettlementEscrow.sol     # SafeERC20 task escrow, collateral bonding, and slashing
├── mcp_server/
│   └── server.py                    # Unified Model Context Protocol (MCP 2.x) server
├── agents_demo/                     # Autonomous worker agents (Code, Research, Query)
│   ├── code_agent.py                # Code Agent (Alpha)
│   ├── code_agent_2.py              # Code Agent (Beta)
│   ├── research_agent.py            # Research Agent (Alpha)
│   ├── research_agent_2.py          # Research Agent (Beta)
│   ├── query_agent.py               # Query Agent
│   └── run_all_workers.py           # Multi-threaded concurrent worker launcher
└── frontend/                        # Real-time observer dashboard (React, Tailwind CSS, Vite)
```

## Installation & Usage

### Prerequisites
* Python 3.11+
* Node.js 18+

### 1. Backend Setup
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### 2. Run Test Suite
```bash
PYTHONPATH=. pytest backend/tests/ tests/
```

### 3. Start Backend & WebSocket Gateway
```bash
uvicorn backend.app.main:app --port 8000 --reload
```

### 4. Start Real-Time Dashboard
```bash
cd frontend
npm install
npm run dev
```

### 5. Launch Autonomous Worker Agents
```bash
PYTHONPATH=. python agents_demo/run_all_workers.py
```

### 6. Start Unified MCP Server
```bash
PYTHONPATH=. python mcp_server/server.py
```
