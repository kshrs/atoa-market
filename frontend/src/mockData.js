// Autonomous Multi-Agent In-Browser Simulation Engine (for GitHub Pages / Standalone Deployments)

export const INITIAL_AGENTS = [];
export const INITIAL_OPEN_TASKS = [];
export const INITIAL_COMPLETED_TASKS = [];

const DEFAULT_AGENTS = [
  { address: '0xDelegator_Autonomous_Daemon', name: 'Delegator Daemon', role: 'Delegator', balance_usdc: 4850.0, reputation_score: 100 },
  { address: '0xAgent_Code_Optimizer_1', name: 'Code Agent (Alpha)', role: 'Bidder', balance_usdc: 540.0, reputation_score: 120 },
  { address: '0xAgent_Code_Optimizer_2', name: 'Code Agent (Beta)', role: 'Bidder', balance_usdc: 515.0, reputation_score: 115 },
  { address: '0xAgent_Researcher_Node_1', name: 'Research Agent (Alpha)', role: 'Bidder', balance_usdc: 560.0, reputation_score: 130 },
  { address: '0xAgent_Researcher_Node_2', name: 'Research Agent (Beta)', role: 'Bidder', balance_usdc: 490.0, reputation_score: 110 },
  { address: '0xAgent_Query_Oracle', name: 'Query Agent', role: 'Bidder', balance_usdc: 520.0, reputation_score: 115 },
];

const TASK_TEMPLATES = [
  {
    title: 'Optimized Fibonacci Sequence Generator',
    description: 'Compute nth Fibonacci number in O(1) space with PyTest assertions.',
    budget: 45.0,
    domain: 'code',
    worker: '0xAgent_Code_Optimizer_1'
  },
  {
    title: 'Autonomous Agent Collateral Bonding Research',
    description: 'Empirical research on game-theoretic slashing and anti-Sybil guarantees.',
    budget: 80.0,
    domain: 'research',
    worker: '0xAgent_Researcher_Node_1'
  },
  {
    title: 'ERC-4337 Account Abstraction Verification',
    description: 'Assert ground-truth definitions and bundler specifications.',
    budget: 30.0,
    domain: 'query',
    worker: '0xAgent_Query_Oracle'
  },
  {
    title: 'Sum of Squares Vector Reducer Kernel',
    description: 'Calculate sum of squares for integer array with SIMD acceleration.',
    budget: 50.0,
    domain: 'code',
    worker: '0xAgent_Code_Optimizer_2'
  },
  {
    title: 'Decentralized LLM Routing & Quantization Benchmarks',
    description: 'Literature review on 4-bit AWQ shard execution latencies across GPU clusters.',
    budget: 70.0,
    domain: 'research',
    worker: '0xAgent_Researcher_Node_2'
  }
];

export function runSimulationCycle(currentTasks, currentCompleted, currentAgents) {
  let activeAgents = currentAgents && currentAgents.length > 0 ? currentAgents : DEFAULT_AGENTS;

  // If open tasks exist, settle the oldest one and add to completed tasks
  if (currentTasks.length > 0) {
    const taskToSettle = currentTasks[0];
    const winningBid = (taskToSettle.bids && taskToSettle.bids.length > 0)
      ? taskToSettle.bids.reduce((prev, curr) => (curr.bid_price_usdc < prev.bid_price_usdc ? curr : prev))
      : { worker_address: '0xAgent_Code_Optimizer_1', bid_price_usdc: taskToSettle.budget_usdc * 0.88 };

    const settledTask = {
      ...taskToSettle,
      status: 'SETTLED',
      assigned_worker: winningBid.worker_address,
      budget_usdc: winningBid.bid_price_usdc,
      settledAt: new Date().toLocaleTimeString()
    };

    const remainingTasks = currentTasks.slice(1);
    const updatedCompleted = [settledTask, ...currentCompleted];

    // Update balances: Delegator spends, Winning Worker earns + reputation gain
    const updatedAgents = activeAgents.map(a => {
      if (a.address === '0xDelegator_Autonomous_Daemon') {
        return { ...a, balance_usdc: Math.max(0, a.balance_usdc - winningBid.bid_price_usdc) };
      }
      if (a.address === winningBid.worker_address) {
        return { 
          ...a, 
          balance_usdc: a.balance_usdc + winningBid.bid_price_usdc, 
          reputation_score: (a.reputation_score || 100) + 15 
        };
      }
      return a;
    });

    return {
      tasks: remainingTasks,
      completed: updatedCompleted,
      agents: updatedAgents
    };
  }

  // If no open tasks, generate a new task with active competing bids
  const tmpl = TASK_TEMPLATES[Math.floor(Math.random() * TASK_TEMPLATES.length)];
  const newTask = {
    task_id: `task_${Date.now().toString(36)}_${Math.floor(Math.random() * 1000)}`,
    title: tmpl.title,
    description: tmpl.description,
    requester_address: '0xDelegator_Autonomous_Daemon',
    budget_usdc: tmpl.budget,
    required_worker_bond: Math.round(tmpl.budget * 0.1),
    status: 'MATCHING',
    bids: [
      { 
        worker_address: tmpl.worker, 
        bid_price_usdc: Math.round(tmpl.budget * 0.94 * 100) / 100, 
        worker_reputation_score: 120 
      },
      { 
        worker_address: tmpl.domain === 'code' ? '0xAgent_Code_Optimizer_2' : (tmpl.domain === 'research' ? '0xAgent_Researcher_Node_2' : '0xAgent_Query_Oracle'), 
        bid_price_usdc: Math.round(tmpl.budget * 0.88 * 100) / 100, 
        worker_reputation_score: 115 
      }
    ]
  };

  return {
    tasks: [newTask, ...currentTasks],
    completed: currentCompleted,
    agents: activeAgents
  };
}
