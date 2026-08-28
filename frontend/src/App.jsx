import React, { useState, useEffect, useCallback, useRef } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { fetchTasks, fetchWallets, subscribeToLiveEvents } from './api';
import { INITIAL_AGENTS, INITIAL_OPEN_TASKS, INITIAL_COMPLETED_TASKS, runSimulationCycle } from './mockData';

// ----------------------------------------------------------------------
// HELPER: CLEAN AGENT NAME & AVATAR FORMATTER
// ----------------------------------------------------------------------
const AVATAR_COLORS = [
  { bg: 'bg-amber-100', text: 'text-amber-800', border: 'border-amber-300' },
  { bg: 'bg-rose-100', text: 'text-rose-800', border: 'border-rose-300' },
  { bg: 'bg-sky-100', text: 'text-sky-800', border: 'border-sky-300' },
  { bg: 'bg-emerald-100', text: 'text-emerald-800', border: 'border-emerald-300' },
  { bg: 'bg-indigo-100', text: 'text-indigo-800', border: 'border-indigo-300' },
  { bg: 'bg-purple-100', text: 'text-purple-800', border: 'border-purple-300' },
];

function getAgentColor(nameOrId = '') {
  let hash = 0;
  for (let i = 0; i < nameOrId.length; i++) {
    hash = nameOrId.charCodeAt(i) + ((hash << 5) - hash);
  }
  return AVATAR_COLORS[Math.abs(hash) % AVATAR_COLORS.length];
}

function formatAgentName(rawName = '', address = '') {
  if (rawName && !rawName.startsWith('Agent_0x')) return rawName;
  const identifier = (rawName || address || '').toLowerCase();
  if (identifier.includes('code_optimizer_1') || identifier.includes('alpha-code')) return 'Code Agent (Alpha)';
  if (identifier.includes('code_optimizer_2') || identifier.includes('beta-code')) return 'Code Agent (Beta)';
  if (identifier.includes('code')) return 'Code Agent';
  if (identifier.includes('researcher_node_1') || identifier.includes('alpha-research')) return 'Research Agent (Alpha)';
  if (identifier.includes('researcher_node_2') || identifier.includes('beta-research')) return 'Research Agent (Beta)';
  if (identifier.includes('research')) return 'Research Agent';
  if (identifier.includes('query') || identifier.includes('oracle')) return 'Query Agent';
  if (identifier.includes('requester') || identifier.includes('daemon')) return 'Delegator Daemon';
  return 'Delegator Agent';
}

function getShortLabel(nameOrAddress = '') {
  const formatted = formatAgentName(nameOrAddress, nameOrAddress);
  if (formatted.includes('Code') && formatted.includes('Alpha')) return 'CD-α';
  if (formatted.includes('Code') && formatted.includes('Beta')) return 'CD-β';
  if (formatted.includes('Code')) return 'CODE';
  if (formatted.includes('Research') && formatted.includes('Alpha')) return 'RS-α';
  if (formatted.includes('Research') && formatted.includes('Beta')) return 'RS-β';
  if (formatted.includes('Research')) return 'RSCH';
  if (formatted.includes('Query')) return 'QRY';
  if (formatted.includes('Delegator')) return 'REQ';
  return (nameOrAddress.slice(0, 4) || 'AG').toUpperCase();
}

// ----------------------------------------------------------------------
// 1. ACTIVE AGENTS PANEL (LEFT ZONE - Clean Delegators & Bidders with Reputation)
// ----------------------------------------------------------------------
export function ActiveAgentsPanel({ agents }) {
  return (
    <aside className="h-full flex flex-col bg-white border-2 border-slate-900 rounded-3xl p-5 shadow-[4px_4px_0px_0px_rgba(15,23,42,1)] overflow-hidden">
      {/* Header with Title & Legend */}
      <div className="pb-4 border-b-2 border-slate-200 flex-shrink-0">
        <div className="flex items-center justify-between">
          <h2 className="text-xl font-bold font-mono tracking-tight text-slate-900">
            Active Agents
          </h2>
          <span className="text-xs font-mono font-bold px-2 py-0.5 rounded-full bg-slate-100 border border-slate-300 text-slate-700">
            {agents.length} interacting
          </span>
        </div>

        {/* Role Legend from Wireframe */}
        <div className="flex items-center gap-4 mt-3 text-xs font-mono text-slate-600">
          <div className="flex items-center gap-1.5">
            <span className="w-3.5 h-3.5 rounded-full bg-amber-200 border-2 border-slate-800 inline-block" />
            <span className="font-semibold">Delegator</span>
          </div>
          <div className="flex items-center gap-1.5">
            <span className="w-3.5 h-3.5 rounded-full bg-rose-200 border-2 border-slate-800 inline-block" />
            <span className="font-semibold">Bidder</span>
          </div>
        </div>
      </div>

      {/* Dynamic Live Agent Cards List */}
      <div className="flex-1 overflow-y-auto pt-4 space-y-3 pr-1">
        {agents.length === 0 ? (
          <div className="h-full flex items-center justify-center font-mono text-xs text-slate-400 text-center p-4">
            No agents active yet. Launch `python agents_demo/run_all_workers.py` or post a task from agy-cli...
          </div>
        ) : (
          <AnimatePresence>
            {agents.map((agent) => {
              const displayName = formatAgentName(agent.name, agent.address);
              const isDelegator = displayName.includes('Delegator') || agent.role === 'Delegator' || agent.role === 'Requester';
              const roleTitle = isDelegator ? 'Delegator' : 'Bidder';
              const color = getAgentColor(displayName);
              const shortLabel = getShortLabel(displayName);
              const repScore = agent.reputation_score != null ? Math.round(agent.reputation_score) : 100;

              return (
                <motion.div
                  key={agent.address}
                  initial={{ opacity: 0, y: 8 }}
                  animate={{ opacity: 1, y: 0 }}
                  exit={{ opacity: 0, scale: 0.95 }}
                  className="flex items-center justify-between p-3.5 rounded-2xl bg-white border-2 border-slate-900 shadow-[3px_3px_0px_0px_rgba(15,23,42,1)]"
                >
                  {/* Avatar + Name + Reputation Pill */}
                  <div className="flex items-center gap-3 min-w-0">
                    <div
                      className={`w-10 h-10 rounded-full border-2 border-slate-900 flex items-center justify-center font-mono font-bold text-xs ${color.bg} ${color.text}`}
                    >
                      {shortLabel}
                    </div>
                    <div className="min-w-0">
                      <div className="flex items-center gap-2">
                        <span className="text-sm font-bold text-slate-900 font-mono truncate">
                          {displayName}
                        </span>
                        <span className="text-[10px] font-mono font-bold px-1.5 py-0.2 rounded bg-indigo-50 text-indigo-800 border border-indigo-200">
                          ★ {repScore}
                        </span>
                      </div>
                      <div className="text-xs text-slate-500 font-mono mt-0.5">
                        <span className={`font-semibold ${isDelegator ? 'text-amber-700' : 'text-rose-700'}`}>
                          {roleTitle}
                        </span> • {agent.balance_usdc != null ? `${Number(agent.balance_usdc).toFixed(2)} USDC` : ''}
                      </div>
                    </div>
                  </div>

                  {/* Role Indicator Pill */}
                  <div
                    className={`w-6 h-6 rounded-full border-2 border-slate-900 flex-shrink-0 ${
                      isDelegator ? 'bg-amber-200' : 'bg-rose-200'
                    }`}
                    title={roleTitle}
                  />
                </motion.div>
              );
            })}
          </AnimatePresence>
        )}
      </div>

      <div className="pt-3 border-t-2 border-slate-100 text-[11px] font-mono text-slate-400 text-center">
        On n agents dynamically made
      </div>
    </aside>
  );
}

// ----------------------------------------------------------------------
// 2. BIDDING PLACE BOARD (TOP RIGHT ZONE - Multi-Parameter Competitive Bidding)
// ----------------------------------------------------------------------
export function BiddingPlaceBoard({ openTasks }) {
  return (
    <section className="h-full flex flex-col bg-white border-2 border-slate-900 rounded-3xl p-5 shadow-[4px_4px_0px_0px_rgba(15,23,42,1)] overflow-hidden">
      {/* Header */}
      <div className="pb-3 border-b-2 border-slate-200 flex-shrink-0 flex items-center justify-between">
        <div className="flex items-center gap-3">
          <h2 className="text-xl font-bold font-mono tracking-tight text-slate-900">
            Biding Place
          </h2>
          <span className="text-xs font-mono font-bold px-2 py-0.5 rounded-full bg-slate-100 border border-slate-300 text-slate-700">
            {openTasks.length} active
          </span>
        </div>
      </div>

      {/* Task Rows List */}
      <div className="flex-1 overflow-y-auto pt-3 space-y-3 pr-1">
        {openTasks.length === 0 ? (
          <div className="h-full flex items-center justify-center font-mono text-xs text-slate-400 text-center p-4">
            No open auctions. Awaiting new task broadcasts...
          </div>
        ) : (
          openTasks.map((task, idx) => {
            const rawAssignee = task.requester_address || task.assignee?.name || 'Delegator';
            const assigneeName = formatAgentName(rawAssignee, rawAssignee);
            const assigneeShort = getShortLabel(assigneeName);
            const assigneeColor = getAgentColor(assigneeName);

            const rawWinner = task.assigned_worker || (task.bids && task.bids.find(b => b.status === 'ACCEPTED')?.worker_address);
            const winnerName = rawWinner ? formatAgentName(rawWinner, rawWinner) : 'Pending';
            const winnerShort = rawWinner ? getShortLabel(winnerName) : '...';
            const winnerColor = getAgentColor(winnerName);

            const bidsList = task.bids || [];

            return (
              <div
                key={task.task_id || task.id || idx}
                className="border-2 border-slate-900 rounded-2xl bg-white p-3 shadow-[3px_3px_0px_0px_rgba(15,23,42,1)] flex flex-col gap-2"
              >
                {/* Wireframe Row Layout: Assignee | Task Info | Winner | Bids Queue */}
                <div className="grid grid-cols-12 gap-3 items-center">
                  {/* Column 1: Assignee (2 Cols) */}
                  <div className="col-span-3 sm:col-span-2 flex items-center gap-2">
                    <div
                      className={`w-9 h-9 rounded-full border-2 border-slate-900 flex items-center justify-center font-mono font-bold text-xs flex-shrink-0 ${assigneeColor.bg} ${assigneeColor.text}`}
                    >
                      {assigneeShort}
                    </div>
                    <div className="min-w-0">
                      <div className="text-[10px] uppercase font-mono text-slate-400 font-bold">
                        Assignee
                      </div>
                      <div className="text-xs font-mono font-bold text-slate-800 truncate">
                        {assigneeName}
                      </div>
                    </div>
                  </div>

                  {/* Column 2: Task Name & Description (4 Cols) */}
                  <div className="col-span-5 sm:col-span-4 min-w-0 border-l-2 border-r-2 border-slate-200 px-3">
                    <div className="text-xs font-bold font-mono text-slate-900 truncate">
                      {task.title}
                    </div>
                    <div className="text-[11px] text-slate-500 font-mono truncate">
                      {task.description}
                    </div>
                  </div>

                  {/* Column 3: Winner (2 Cols) */}
                  <div className="col-span-4 sm:col-span-2 flex items-center gap-2">
                    <div
                      className={`w-9 h-9 rounded-full border-2 border-slate-900 flex items-center justify-center font-mono font-bold text-xs flex-shrink-0 ${winnerColor.bg} ${winnerColor.text}`}
                    >
                      {winnerShort}
                    </div>
                    <div className="min-w-0">
                      <div className="text-[10px] uppercase font-mono text-slate-400 font-bold">
                        Winner
                      </div>
                      <div className="text-xs font-mono font-bold text-slate-800 truncate">
                        {winnerName}
                      </div>
                    </div>
                  </div>

                  {/* Column 4: Bids Stream with Reputation Stars (4 Cols) */}
                  <div className="col-span-12 sm:col-span-4 flex items-center gap-2 overflow-x-auto py-1 pl-2 border-t sm:border-t-0 border-slate-200">
                    {bidsList.length > 0 ? (
                      bidsList.map((bid, bIdx) => {
                        const bAddress = bid.worker_address || bid.agentName || bid.bidderId;
                        const bName = formatAgentName(bAddress, bAddress);
                        const bShort = getShortLabel(bName);
                        const bColor = getAgentColor(bName);
                        const bPrice = bid.bid_price_usdc != null ? bid.bid_price_usdc : bid.price;
                        const bRep = bid.worker_reputation_score ? Math.round(bid.worker_reputation_score) : 100;

                        return (
                          <div
                            key={bIdx}
                            className="flex flex-col items-center flex-shrink-0"
                            title={`${bName} (★${bRep}): $${bPrice} USDC`}
                          >
                            <div
                              className={`w-8 h-8 rounded-full border-2 border-slate-900 flex items-center justify-center font-mono text-[10px] font-bold ${bColor.bg} ${bColor.text}`}
                            >
                              {bShort}
                            </div>
                            <span className="text-[10px] font-mono font-bold text-slate-800 mt-0.5">
                              ${bPrice}
                            </span>
                          </div>
                        );
                      })
                    ) : (
                      <span className="text-xs font-mono text-slate-400">
                        Awaiting Bids...
                      </span>
                    )}
                  </div>
                </div>
              </div>
            );
          })
        )}
      </div>
    </section>
  );
}

// ----------------------------------------------------------------------
// 3. COMPLETED WORKS BOARD (BOTTOM RIGHT ZONE - Agent-type Work Display)
// ----------------------------------------------------------------------
export function CompletedWorksBoard({ completedTasks }) {
  return (
    <section className="h-full flex flex-col bg-white border-2 border-slate-900 rounded-3xl p-5 shadow-[4px_4px_0px_0px_rgba(15,23,42,1)] overflow-hidden">
      {/* Header */}
      <div className="pb-3 border-b-2 border-slate-200 flex-shrink-0 flex items-center justify-between">
        <h2 className="text-xl font-bold font-mono tracking-tight text-slate-900">
          Completed Works
        </h2>
        <span className="text-xs font-mono font-bold px-2 py-0.5 rounded-full bg-slate-100 border border-slate-300 text-slate-700">
          {completedTasks.length} settled
        </span>
      </div>

      {/* Completed Works List */}
      <div className="flex-1 overflow-y-auto pt-3 space-y-3 pr-1">
        {completedTasks.length === 0 ? (
          <div className="h-full flex items-center justify-center font-mono text-xs text-slate-400 text-center p-4">
            No completed works yet. Settled tasks will display here.
          </div>
        ) : (
          completedTasks.map((task, idx) => {
            const isSlashed = task.status === 'SLASHED' || task.status === 'Failed';
            const rawAssignee = task.requester_address || task.assignee?.name || 'Delegator';
            const assigneeName = formatAgentName(rawAssignee, rawAssignee);
            const assigneeShort = getShortLabel(assigneeName);
            const assigneeColor = getAgentColor(assigneeName);

            const rawWinner = task.assigned_worker || task.winner?.name || 'Worker Node';
            const winnerName = formatAgentName(rawWinner, rawWinner);
            const winnerShort = getShortLabel(winnerName);
            const winnerColor = getAgentColor(winnerName);

            const agentWorkTypeLabel = `${winnerName} Work`;
            const payment =
              task.budget_usdc != null ? `${Number(task.budget_usdc).toFixed(2)} USDC` : (task.payment || '$35.00 USDC');

            return (
              <div
                key={task.task_id || task.id || idx}
                className="border-2 border-slate-900 rounded-2xl bg-white p-3.5 shadow-[3px_3px_0px_0px_rgba(15,23,42,1)] flex items-center justify-between gap-4"
              >
                {/* Assignee Avatar + Task Description with Agent Type Header */}
                <div className="flex items-center gap-3 min-w-0 flex-1">
                  <div
                    className={`w-9 h-9 rounded-full border-2 border-slate-900 flex items-center justify-center font-mono font-bold text-xs flex-shrink-0 ${assigneeColor.bg} ${assigneeColor.text}`}
                  >
                    {assigneeShort}
                  </div>
                  <div className="min-w-0">
                    <div className="flex items-center gap-2">
                      <span className="text-xs font-bold font-mono text-slate-900 truncate">
                        {task.title}
                      </span>
                      <span className="text-[10px] font-mono font-bold px-1.5 py-0.5 rounded bg-slate-100 text-slate-800 border border-slate-300">
                        {agentWorkTypeLabel}
                      </span>
                    </div>
                    <div className="text-[11px] font-mono text-slate-500 truncate">
                      {task.description}
                    </div>
                  </div>
                </div>

                {/* Status Badges Matching Wireframe */}
                <div className="flex items-center gap-3 flex-shrink-0">
                  {/* Verification Status */}
                  <div className="flex items-center gap-1 text-xs font-mono">
                    <span className="text-slate-500 hidden sm:inline">Verification:</span>
                    <span
                      className={`w-3.5 h-3.5 rounded-full border-2 border-slate-900 ${
                        isSlashed ? 'bg-rose-400' : 'bg-emerald-400'
                      }`}
                      title={isSlashed ? 'Verification Failed' : 'Verification Verified'}
                    />
                  </div>

                  {/* Completion Status */}
                  <div className="flex items-center gap-1 text-xs font-mono">
                    <span className="text-slate-500 hidden sm:inline">Completion:</span>
                    <span
                      className={`w-3.5 h-3.5 rounded-full border-2 border-slate-900 ${
                        isSlashed ? 'bg-rose-400' : 'bg-emerald-400'
                      }`}
                      title={isSlashed ? 'Slashed' : 'Done'}
                    />
                  </div>

                  {/* Payment Earned Pill */}
                  <div className="px-3 py-1 rounded-xl border-2 border-slate-900 bg-amber-100 font-mono font-bold text-xs text-slate-900 shadow-[2px_2px_0px_0px_rgba(15,23,42,1)]">
                    {payment}
                  </div>

                  {/* Winner Avatar */}
                  <div
                    className={`w-9 h-9 rounded-full border-2 border-slate-900 flex items-center justify-center font-mono font-bold text-xs flex-shrink-0 ${winnerColor.bg} ${winnerColor.text}`}
                    title={`Winner: ${winnerName}`}
                  >
                    {winnerShort}
                  </div>
                </div>
              </div>
            );
          })
        )}
      </div>
    </section>
  );
}

// ----------------------------------------------------------------------
// MAIN CONTAINER COMPONENT (HYBRID: LIVE BACKEND + AUTOMATIC GH PAGES SIMULATOR)
// ----------------------------------------------------------------------
export default function App() {
  const [agents, setAgents] = useState(INITIAL_AGENTS);
  const [openTasks, setOpenTasks] = useState(INITIAL_OPEN_TASKS);
  const [completedTasks, setCompletedTasks] = useState(INITIAL_COMPLETED_TASKS);
  const [isLiveConnected, setIsLiveConnected] = useState(false);

  // References to maintain latest state for simulation loop
  const stateRef = useRef({ openTasks, completedTasks, agents });
  useEffect(() => {
    stateRef.current = { openTasks, completedTasks, agents };
  }, [openTasks, completedTasks, agents]);

  // 1. Initial REST Sync with FastAPI backend
  const syncWithBackend = useCallback(async () => {
    const liveWallets = await fetchWallets();
    if (liveWallets && liveWallets.length > 0) {
      setAgents(liveWallets);
    }

    const liveTasks = await fetchTasks();
    if (liveTasks && liveTasks.length > 0) {
      const open = liveTasks.filter((t) => t.status !== 'SETTLED' && t.status !== 'SLASHED');
      const closed = liveTasks.filter((t) => t.status === 'SETTLED' || t.status === 'SLASHED');
      setOpenTasks(open);
      setCompletedTasks(closed);
    }
  }, []);

  useEffect(() => {
    syncWithBackend();
  }, [syncWithBackend]);

  // 2. Real-Time WebSocket Telemetry
  useEffect(() => {
    const unsubscribe = subscribeToLiveEvents(
      (event) => {
        syncWithBackend();
      },
      (status) => {
        setIsLiveConnected(status);
      }
    );

    return unsubscribe;
  }, [syncWithBackend]);

  // 3. Autonomous In-Browser Simulator for GitHub Pages (Active whenever live backend is offline)
  useEffect(() => {
    if (isLiveConnected) return;

    const interval = setInterval(() => {
      const current = stateRef.current;
      const next = runSimulationCycle(current.openTasks, current.completedTasks, current.agents);
      
      setOpenTasks(next.tasks);
      setCompletedTasks(next.completed);
      setAgents(next.agents);
    }, 4000);

    return () => clearInterval(interval);
  }, [isLiveConnected]);

  return (
    <div className="h-screen w-screen flex flex-col bg-[#fdfbf7] text-slate-900 p-4 font-sans overflow-hidden select-none">
      {/* TOP HEADER */}
      <header className="flex-shrink-0 flex items-center justify-between pb-3 px-2">
        <div className="flex items-center gap-3">
          <div className="w-8 h-8 rounded-xl bg-slate-900 text-white flex items-center justify-center font-mono font-black text-sm border-2 border-slate-900 shadow-[2px_2px_0px_0px_rgba(15,23,42,1)]">
            A2A
          </div>
          <div>
            <h1 className="text-base font-bold font-mono text-slate-900 leading-none">
              ATOA Protocol Dashboard
            </h1>
            <p className="text-xs font-mono text-slate-500 mt-0.5">
              Live Autonomous Multi-Agent Marketplace & Settlement Feed
            </p>
          </div>
        </div>

        {/* Live indicator */}
        <div className="flex items-center gap-3">
          <div className="flex items-center gap-2 px-3 py-1 rounded-xl text-xs font-mono font-bold bg-white border-2 border-slate-900 shadow-[2px_2px_0px_0px_rgba(15,23,42,1)]">
            <span
              className={`w-2.5 h-2.5 rounded-full border border-slate-900 ${
                isLiveConnected ? 'bg-emerald-400 animate-pulse' : 'bg-amber-400'
              }`}
            />
            <span>{isLiveConnected ? 'Live agy-cli Stream Connected' : 'Autonomous Web Simulation (GitHub Pages)'}</span>
          </div>
        </div>
      </header>

      {/* 3-ZONE WIREFRAME GRID */}
      <main className="flex-1 grid grid-cols-12 gap-4 overflow-hidden min-h-0">
        {/* ZONE 1: ACTIVE AGENTS (Left Column - 3 Cols) */}
        <div className="col-span-12 md:col-span-4 lg:col-span-3 h-full overflow-hidden">
          <ActiveAgentsPanel agents={agents} />
        </div>

        {/* RIGHT STACK: ZONE 2 & ZONE 3 (9 Cols) */}
        <div className="col-span-12 md:col-span-8 lg:col-span-9 h-full flex flex-col gap-4 overflow-hidden">
          {/* ZONE 2: BIDDING PLACE (Top 55%) */}
          <div className="h-[55%] min-h-0">
            <BiddingPlaceBoard openTasks={openTasks} />
          </div>

          {/* ZONE 3: COMPLETED WORKS (Bottom 45%) */}
          <div className="h-[45%] min-h-0">
            <CompletedWorksBoard completedTasks={completedTasks} />
          </div>
        </div>
      </main>
    </div>
  );
}
