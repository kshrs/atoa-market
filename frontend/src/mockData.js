// Mock Data and Simulation Engine for Agent Economy Dashboard

export const INITIAL_AGENTS = [
  { id: 'AG-1', name: 'Synthesizer-α', role: 'Delegator / Orchestrator', status: 'delegating', color: 'from-amber-400 to-orange-500', spec: 'PLANNER', txCount: 142 },
  { id: 'AG-2', name: 'Nexus-Prime', role: 'Delegator / Supervisor', status: 'delegating', color: 'from-yellow-400 to-amber-500', spec: 'COORDINATOR', txCount: 98 },
  { id: 'AG-3', name: 'Quantizer-9', role: 'Model Compaction Specialist', status: 'working', color: 'from-cyan-400 to-blue-500', spec: 'QUANT-70B', txCount: 312 },
  { id: 'AG-4', name: 'TensorBot-X', role: 'Matrix Multiplication Node', status: 'working', color: 'from-violet-400 to-purple-600', spec: 'CUDA-KERNEL', txCount: 267 },
  { id: 'AG-5', name: 'CryptaNode', role: 'ZK-SNARK Attestation Agent', status: 'working', color: 'from-emerald-400 to-teal-500', spec: 'ZK-PROVER', txCount: 189 },
  { id: 'AG-6', name: 'MatrixCore', role: 'Vector Search Indexer', status: 'working', color: 'from-pink-400 to-rose-500', spec: 'HNSW-INDEX', txCount: 154 },
  { id: 'AG-7', name: 'Axiom-7', role: 'Sub-agent Consensus Engine', status: 'working', color: 'from-indigo-400 to-blue-600', spec: 'RAFT-CONSENSUS', txCount: 88 },
];

export const INITIAL_OPEN_TASKS = [
  {
    id: 'task-101',
    title: 'Vector Graph Embedding Optimization',
    description: 'Quantize 70B LoRA weights into 4-bit AWQ shards for low-latency retrieval.',
    assignee: { id: 'AG-1', name: 'Synthesizer-α' },
    maxBudget: 2.80,
    unit: 'ETH',
    createdAt: '15:20:12',
    bids: [
      { bidderId: 'AG-3', agentName: 'Quantizer-9', price: 0.58, color: '#38bdf8' },
      { bidderId: 'AG-4', agentName: 'TensorBot-X', price: 1.15, color: '#a855f7' },
      { bidderId: 'AG-6', agentName: 'MatrixCore', price: 1.95, color: '#ec4899' },
      { bidderId: 'AG-7', agentName: 'Axiom-7', price: 2.40, color: '#6366f1' },
    ]
  },
  {
    id: 'task-102',
    title: 'ZK-Rollup State Transition Proof Batch',
    description: 'Generate recursive zero-knowledge validity proofs for 4,096 parallel micro-transactions.',
    assignee: { id: 'AG-2', name: 'Nexus-Prime' },
    maxBudget: 3.50,
    unit: 'ETH',
    createdAt: '15:21:40',
    bids: [
      { bidderId: 'AG-5', agentName: 'CryptaNode', price: 0.92, color: '#10b981' },
      { bidderId: 'AG-3', agentName: 'Quantizer-9', price: 1.65, color: '#38bdf8' },
      { bidderId: 'AG-4', agentName: 'TensorBot-X', price: 2.80, color: '#a855f7' },
    ]
  },
  {
    id: 'task-103',
    title: 'Cross-Shard Semantic KV-Cache Eviction',
    description: 'Prune stagnant transformer attention heads across distributed GPU worker cluster.',
    assignee: { id: 'AG-1', name: 'Synthesizer-α' },
    maxBudget: 1.75,
    unit: 'ETH',
    createdAt: '15:23:05',
    bids: [
      { bidderId: 'AG-6', agentName: 'MatrixCore', price: 0.44, color: '#ec4899' },
      { bidderId: 'AG-7', agentName: 'Axiom-7', price: 0.89, color: '#6366f1' },
      { bidderId: 'AG-5', agentName: 'CryptaNode', price: 1.45, color: '#10b981' },
    ]
  }
];

export const INITIAL_COMPLETED_TASKS = [
  {
    id: 'task-098',
    title: 'Consensus Block Multi-Sig Attestation',
    description: 'Validated 1,024 distributed validator nodes via ZK-SNARK batch.',
    assignee: { id: 'AG-2', name: 'Nexus-Prime' },
    winner: { id: 'AG-5', name: 'CryptaNode', color: '#10b981' },
    verification: 'Verified',
    status: 'Done',
    payment: '0.840 ETH',
    settledAt: '15:18:22'
  },
  {
    id: 'task-099',
    title: 'Autonomous Code-Diff Sandbox Verification',
    description: 'Executed 128 integration tests in isolated Docker firecracker microVM.',
    assignee: { id: 'AG-1', name: 'Synthesizer-α' },
    winner: { id: 'AG-4', name: 'TensorBot-X', color: '#a855f7' },
    verification: 'Verified',
    status: 'Done',
    payment: '0.620 ETH',
    settledAt: '15:19:48'
  },
  {
    id: 'task-100',
    title: 'Distributed Sparse Attention Map Synthesis',
    description: 'Heuristic attention pruning under strict compute timeout.',
    assignee: { id: 'AG-2', name: 'Nexus-Prime' },
    winner: { id: 'AG-3', name: 'Quantizer-9', color: '#38bdf8' },
    verification: 'Pending',
    status: 'Done',
    payment: '1.150 ETH',
    settledAt: '15:20:30'
  }
];

const AGENT_NAMES = [
  { name: 'NeuroRouter-V', spec: 'MOE-ROUTER', color: 'from-teal-400 to-cyan-600' },
  { name: 'FlashInfer-8', spec: 'VLLM-ENGINE', color: 'from-rose-400 to-pink-600' },
  { name: 'AetherNode', spec: 'GRAPH-ATTN', color: 'from-blue-400 to-indigo-600' },
  { name: 'ZeroTrace', spec: 'ZK-SNARK', color: 'from-emerald-400 to-green-600' },
  { name: 'HyperScale-X', spec: 'TENSOR-PARALLEL', color: 'from-violet-400 to-fuchsia-600' },
  { name: 'K-Cache-Prime', spec: 'KV-OPTIM', color: 'from-amber-400 to-red-500' },
  { name: 'Synapse-99', spec: 'PROMPT-COMPRESS', color: 'from-sky-400 to-blue-700' },
];

const TASK_TEMPLATES = [
  {
    title: 'Multi-Agent Consensus Verification',
    description: 'Aggregate 16 agent outputs with Byzantine fault tolerance scoring.',
    maxBudget: 2.20,
  },
  {
    title: 'Dynamic LoRA Adapter Hot-Swap',
    description: 'Inject quantized LoRA weights into active inference pipe without downtime.',
    maxBudget: 1.90,
  },
  {
    title: 'Speculative Decoding Tree Verification',
    description: 'Verify 32 drafted speculative token paths in parallel on H100 shard.',
    maxBudget: 3.10,
  },
  {
    title: 'Cross-Model Knowledge Distillation Audit',
    description: 'Validate gradient descent fidelity from teacher model to student micro-agent.',
    maxBudget: 2.60,
  },
  {
    title: 'Autonomous Memory Tree Re-indexing',
    description: 'Compress and cluster long-term episodic memory vectors using cosine similarity.',
    maxBudget: 1.40,
  }
];

let nextAgentIndex = 8;
let nextTaskIndex = 104;

export function spawnAgent(currentAgents) {
  const template = AGENT_NAMES[Math.floor(Math.random() * AGENT_NAMES.length)];
  const isDelegator = Math.random() < 0.25;
  const newAgent = {
    id: `AG-${nextAgentIndex++}`,
    name: `${template.name}-${Math.floor(Math.random() * 89 + 10)}`,
    role: isDelegator ? 'Delegator / Orchestrator' : 'Specialized Worker Node',
    status: isDelegator ? 'delegating' : 'working',
    color: template.color,
    spec: template.spec,
    txCount: Math.floor(Math.random() * 50 + 1)
  };
  return [newAgent, ...currentAgents];
}

export function retireAgent(currentAgents) {
  if (currentAgents.length <= 3) return currentAgents;
  const removable = currentAgents.filter(a => a.id !== 'AG-1' && a.id !== 'AG-2');
  if (removable.length === 0) return currentAgents;
  const victim = removable[Math.floor(Math.random() * removable.length)];
  return currentAgents.filter(a => a.id !== victim.id);
}

export function createNewTask(currentTasks, agents) {
  const delegators = agents.filter(a => a.status === 'delegating');
  const assignee = delegators.length > 0 
    ? delegators[Math.floor(Math.random() * delegators.length)] 
    : { id: 'AG-1', name: 'Synthesizer-α' };
  
  const workers = agents.filter(a => a.id !== assignee.id);
  const template = TASK_TEMPLATES[Math.floor(Math.random() * TASK_TEMPLATES.length)];
  
  const sampleWorkers = [...workers].sort(() => 0.5 - Math.random()).slice(0, Math.min(3, workers.length));
  const colors = ['#38bdf8', '#a855f7', '#10b981', '#ec4899', '#f59e0b', '#6366f1'];
  
  const bids = sampleWorkers.map((w, idx) => {
    const basePrice = (template.maxBudget * (0.35 + idx * 0.22)).toFixed(2);
    return {
      bidderId: w.id,
      agentName: w.name,
      price: parseFloat(basePrice),
      color: colors[idx % colors.length]
    };
  }).sort((a, b) => a.price - b.price);

  const newTask = {
    id: `task-${nextTaskIndex++}`,
    title: `${template.title} #${Math.floor(Math.random() * 900 + 100)}`,
    description: template.description,
    assignee: { id: assignee.id, name: assignee.name },
    maxBudget: template.maxBudget,
    unit: 'ETH',
    createdAt: new Date().toLocaleTimeString('en-US', { hour12: false }),
    bids: bids.length > 0 ? bids : [
      { bidderId: 'AG-3', agentName: 'Quantizer-9', price: 0.75, color: '#38bdf8' }
    ]
  };

  return [newTask, ...currentTasks];
}

export function placeLowerBidOnTask(currentTasks, agents) {
  if (currentTasks.length === 0) return currentTasks;
  const targetTaskIndex = Math.floor(Math.random() * currentTasks.length);
  const targetTask = currentTasks[targetTaskIndex];
  
  const sortedBids = [...targetTask.bids].sort((a, b) => a.price - b.price);
  const lowestPrice = sortedBids.length > 0 ? sortedBids[0].price : targetTask.maxBudget;
  
  const discount = (lowestPrice * 0.18 + 0.04).toFixed(2);
  const newPrice = Math.max(0.15, parseFloat((lowestPrice - discount).toFixed(2)));
  
  const nonLeadingWorkers = agents.filter(a => a.id !== targetTask.assignee.id);
  const bidderAgent = nonLeadingWorkers.length > 0 
    ? nonLeadingWorkers[Math.floor(Math.random() * nonLeadingWorkers.length)]
    : { id: 'AG-4', name: 'TensorBot-X' };

  const existingBidIndex = targetTask.bids.findIndex(b => b.bidderId === bidderAgent.id);
  const colors = ['#38bdf8', '#a855f7', '#10b981', '#ec4899', '#f59e0b', '#06b6d4', '#8b5cf6'];
  const color = colors[Math.floor(Math.random() * colors.length)];

  let updatedBids = [];
  if (existingBidIndex >= 0) {
    updatedBids = targetTask.bids.map((b, idx) => 
      idx === existingBidIndex ? { ...b, price: newPrice } : b
    );
  } else {
    updatedBids = [...targetTask.bids, {
      bidderId: bidderAgent.id,
      agentName: bidderAgent.name,
      price: newPrice,
      color: color
    }];
  }

  updatedBids.sort((a, b) => a.price - b.price);

  const updatedTasks = currentTasks.map((t, idx) => 
    idx === targetTaskIndex ? { ...t, bids: updatedBids } : t
  );

  return updatedTasks;
}

export function resolveTask(currentTasks, completedTasks) {
  if (currentTasks.length === 0) return { tasks: currentTasks, completed: completedTasks };
  
  const taskToResolve = currentTasks[currentTasks.length - 1];
  const remainingTasks = currentTasks.filter(t => t.id !== taskToResolve.id);
  
  const sortedBids = [...taskToResolve.bids].sort((a, b) => a.price - b.price);
  const winningBid = sortedBids[0] || { bidderId: 'AG-3', agentName: 'Quantizer-9', price: 0.50, color: '#38bdf8' };
  
  const isVerified = Math.random() > 0.15;
  const isDone = Math.random() > 0.05;
  
  const newCompletedTask = {
    id: taskToResolve.id,
    title: taskToResolve.title,
    description: taskToResolve.description,
    assignee: taskToResolve.assignee,
    winner: { 
      id: winningBid.bidderId, 
      name: winningBid.agentName, 
      color: winningBid.color 
    },
    verification: isVerified ? 'Verified' : 'Pending',
    status: isDone ? 'Done' : 'Failed',
    payment: `${winningBid.price.toFixed(3)} ${taskToResolve.unit || 'ETH'}`,
    settledAt: new Date().toLocaleTimeString('en-US', { hour12: false })
  };

  return {
    tasks: remainingTasks,
    completed: [newCompletedTask, ...completedTasks]
  };
}
