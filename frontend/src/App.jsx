import React, { useState, useEffect, useCallback } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import {
  INITIAL_AGENTS,
  INITIAL_OPEN_TASKS,
  INITIAL_COMPLETED_TASKS,
  spawnAgent,
  retireAgent,
  createNewTask,
  placeLowerBidOnTask,
  resolveTask
} from './mockData';
import { fetchTasks, fetchWallets, subscribeToLiveEvents } from './api';

// ----------------------------------------------------------------------
// HELPER: AGENT AVATAR & COLOR GENERATOR
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

function getShortLabel(nameOrAddress = '') {
  if (nameOrAddress.includes('AG-')) return nameOrAddress;
  if (nameOrAddress.toLowerCase().includes('requester')) return 'REQ';
  if (nameOrAddress.toLowerCase().includes('optimizer') || nameOrAddress.toLowerCase().includes('alpha')) return 'AG-1';
  if (nameOrAddress.toLowerCase().includes('researcher') || nameOrAddress.toLowerCase().includes('beta')) return 'AG-2';
  if (nameOrAddress.toLowerCase().includes('rogue')) return 'ROG';
  return (nameOrAddress.slice(0, 4) || 'AG').toUpperCase();
}

// ----------------------------------------------------------------------
// 1. ACTIVE AGENTS PANEL (LEFT ZONE - Matching Wireframe)
// ----------------------------------------------------------------------
export function ActiveAgentsPanel({ agents, onSpawn, onRetire }) {
  return (
    <aside className="h-full flex flex-col bg-white border-2 border-slate-900 rounded-3xl p-5 shadow-[4px_4px_0px_0px_rgba(15,23,42,1)] overflow-hidden">
      {/* Header with Title & Legend */}
      <div className="pb-4 border-b-2 border-slate-200 flex-shrink-0">
        <div className="flex items-center justify-between">
          <h2 className="text-xl font-bold font-mono tracking-tight text-slate-900">
            Active Agents
          </h2>
          <div className="flex items-center gap-1.5">
            <button
              onClick={onSpawn}
              title="Spawn Agent"
              className="px-2 py-0.5 text-xs font-mono font-bold bg-slate-100 hover:bg-slate-200 border-2 border-slate-800 rounded-lg text-slate-800 transition-all shadow-[2px_2px_0px_0px_rgba(15,23,42,1)] active:translate-x-0.5 active:translate-y-0.5"
            >
              +
            </button>
            <button
              onClick={onRetire}
              disabled={agents.length <= 2}
              title="Retire Agent"
              className="px-2 py-0.5 text-xs font-mono font-bold bg-slate-100 hover:bg-slate-200 border-2 border-slate-800 rounded-lg text-slate-800 transition-all disabled:opacity-40 disabled:cursor-not-allowed"
            >
              -
            </button>
          </div>
        </div>

        {/* Role Legend from Wireframe */}
        <div className="flex items-center gap-4 mt-3 text-xs font-mono text-slate-600">
          <div className="flex items-center gap-1.5">
            <span className="w-3.5 h-3.5 rounded-full bg-amber-200 border-2 border-slate-800 inline-block" />
            <span className="font-semibold">Delegation</span>
          </div>
          <div className="flex items-center gap-1.5">
            <span className="w-3.5 h-3.5 rounded-full bg-rose-200 border-2 border-slate-800 inline-block" />
            <span className="font-semibold">Worker</span>
          </div>
        </div>
      </div>

      {/* Dynamic Agent Cards List */}
      <div className="flex-1 overflow-y-auto pt-4 space-y-3 pr-1">
        <AnimatePresence>
          {agents.map((agent) => {
            const isDelegation =
              agent.status === 'delegating' ||
              agent.role === 'Requester' ||
              (agent.name && agent.name.toLowerCase().includes('requester'));

            const color = getAgentColor(agent.name || agent.address || agent.id);
            const shortLabel = getShortLabel(agent.id || agent.name || agent.address);

            return (
              <motion.div
                key={agent.id || agent.address}
                initial={{ opacity: 0, y: 8 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0, scale: 0.95 }}
                className="flex items-center justify-between p-3.5 rounded-2xl bg-white border-2 border-slate-900 shadow-[3px_3px_0px_0px_rgba(15,23,42,1)]"
              >
                {/* Avatar + Name */}
                <div className="flex items-center gap-3 min-w-0">
                  <div
                    className={`w-10 h-10 rounded-full border-2 border-slate-900 flex items-center justify-center font-mono font-bold text-xs ${color.bg} ${color.text}`}
                  >
                    {shortLabel}
                  </div>
                  <div className="min-w-0">
                    <div className="text-sm font-bold text-slate-900 font-mono truncate">
                      {agent.name || agent.address}
                    </div>
                    <div className="text-xs text-slate-500 font-mono">
                      {agent.balance_usdc != null
                        ? `${agent.balance_usdc} USDC`
                        : `${agent.txCount || 100} txs`}
                    </div>
                  </div>
                </div>

                {/* Role Indicator Pill */}
                <div
                  className={`w-6 h-6 rounded-full border-2 border-slate-900 flex-shrink-0 ${
                    isDelegation ? 'bg-amber-200' : 'bg-rose-200'
                  }`}
                  title={isDelegation ? 'Delegation / Requester' : 'Worker Node'}
                />
              </motion.div>
            );
          })}
        </AnimatePresence>
      </div>

      <div className="pt-3 border-t-2 border-slate-100 text-[11px] font-mono text-slate-400 text-center">
        On n agents dynamically made
      </div>
    </aside>
  );
}

// ----------------------------------------------------------------------
// 2. BIDDING PLACE BOARD (TOP RIGHT ZONE - Matching Wireframe)
// ----------------------------------------------------------------------
export function BiddingPlaceBoard({ openTasks, onNewTask, onLowerBid, onResolve }) {
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

        <div className="flex items-center gap-2">
          <button
            onClick={onNewTask}
            className="px-3 py-1 text-xs font-mono font-bold bg-slate-900 hover:bg-slate-800 text-white rounded-lg transition-all shadow-[2px_2px_0px_0px_rgba(15,23,42,1)] active:translate-x-0.5 active:translate-y-0.5"
          >
            + Task
          </button>
          <button
            onClick={onLowerBid}
            disabled={openTasks.length === 0}
            className="px-3 py-1 text-xs font-mono font-bold bg-white hover:bg-slate-50 border-2 border-slate-900 rounded-lg text-slate-800 transition-all shadow-[2px_2px_0px_0px_rgba(15,23,42,1)] disabled:opacity-40 disabled:cursor-not-allowed"
          >
            ↓ Bid
          </button>
          <button
            onClick={onResolve}
            disabled={openTasks.length === 0}
            className="px-3 py-1 text-xs font-mono font-bold bg-emerald-100 hover:bg-emerald-200 border-2 border-slate-900 rounded-lg text-emerald-900 transition-all shadow-[2px_2px_0px_0px_rgba(15,23,42,1)] disabled:opacity-40 disabled:cursor-not-allowed"
          >
            ✓ Settle
          </button>
        </div>
      </div>

      {/* Task Rows List */}
      <div className="flex-1 overflow-y-auto pt-3 space-y-3 pr-1">
        {openTasks.length === 0 ? (
          <div className="h-full flex items-center justify-center font-mono text-xs text-slate-400">
            No active bids. Awaiting tasks from agy-cli agents...
          </div>
        ) : (
          openTasks.map((task, idx) => {
            const assigneeName =
              task.assignee?.name || task.requester_address || 'Requester';
            const assigneeShort = getShortLabel(assigneeName);
            const assigneeColor = getAgentColor(assigneeName);

            const winnerName =
              task.assigned_worker || (task.bids && task.bids[0]?.agentName) || 'Pending';
            const winnerShort = getShortLabel(winnerName);
            const winnerColor = getAgentColor(winnerName);

            return (
              <div
                key={task.id || task.task_id || idx}
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

                  {/* Column 4: Bids Stream (4 Cols) */}
                  <div className="col-span-12 sm:col-span-4 flex items-center gap-1.5 overflow-x-auto py-1 pl-2 border-t sm:border-t-0 border-slate-200">
                    {task.bids && task.bids.length > 0 ? (
                      task.bids.map((bid, bIdx) => {
                        const bShort = getShortLabel(bid.agentName || bid.worker_address || bid.bidderId);
                        const bColor = getAgentColor(bid.agentName || bid.worker_address || bid.bidderId);
                        return (
                          <div
                            key={bIdx}
                            className="flex flex-col items-center flex-shrink-0"
                            title={`${bid.agentName || bid.worker_address}: $${bid.price || bid.bid_price_usdc}`}
                          >
                            <div
                              className={`w-7 h-7 rounded-full border-2 border-slate-900 flex items-center justify-center font-mono text-[10px] font-bold ${bColor.bg} ${bColor.text}`}
                            >
                              {bShort}
                            </div>
                            <span className="text-[9px] font-mono font-bold text-slate-700 mt-0.5">
                              ${bid.price || bid.bid_price_usdc}
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
// 3. COMPLETED WORKS BOARD (BOTTOM RIGHT ZONE - Matching Wireframe)
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
          <div className="h-full flex items-center justify-center font-mono text-xs text-slate-400">
            No completed tasks yet. Settled transactions will display here.
          </div>
        ) : (
          completedTasks.map((task, idx) => {
            const isSlashed = task.status === 'Failed' || task.status === 'SLASHED';
            const assigneeName = task.assignee?.name || task.requester_address || 'Requester';
            const assigneeShort = getShortLabel(assigneeName);
            const assigneeColor = getAgentColor(assigneeName);

            const winnerName = task.winner?.name || task.assigned_worker || 'Winner Node';
            const winnerShort = getShortLabel(winnerName);
            const winnerColor = getAgentColor(winnerName);

            const payment =
              task.payment ||
              (task.budget_usdc ? `${task.budget_usdc} USDC` : '$35 USDC');

            return (
              <div
                key={task.id || task.task_id || idx}
                className="border-2 border-slate-900 rounded-2xl bg-white p-3.5 shadow-[3px_3px_0px_0px_rgba(15,23,42,1)] flex items-center justify-between gap-4"
              >
                {/* Assignee Avatar + Task Description */}
                <div className="flex items-center gap-3 min-w-0 flex-1">
                  <div
                    className={`w-9 h-9 rounded-full border-2 border-slate-900 flex items-center justify-center font-mono font-bold text-xs flex-shrink-0 ${assigneeColor.bg} ${assigneeColor.text}`}
                  >
                    {assigneeShort}
                  </div>
                  <div className="min-w-0">
                    <div className="text-xs font-bold font-mono text-slate-900 truncate">
                      {task.title}
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
// MAIN CONTAINER COMPONENT
// ----------------------------------------------------------------------
export default function App() {
  const [agents, setAgents] = useState(INITIAL_AGENTS);
  const [openTasks, setOpenTasks] = useState(INITIAL_OPEN_TASKS);
  const [completedTasks, setCompletedTasks] = useState(INITIAL_COMPLETED_TASKS);
  const [isLiveConnected, setIsLiveConnected] = useState(false);
  const [isAutoSimulating, setIsAutoSimulating] = useState(true);

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
      if (open.length > 0) setOpenTasks(open);
      if (closed.length > 0) setCompletedTasks(closed);
    }
  }, []);

  useEffect(() => {
    syncWithBackend();
  }, [syncWithBackend]);

  // 2. Real-Time WebSocket Telemetry
  useEffect(() => {
    const unsubscribe = subscribeToLiveEvents(
      (event) => {
        if (event.event_type === 'TASK_CREATED') {
          setOpenTasks((prev) => [event.data, ...prev]);
        } else if (event.event_type === 'PAYOUT_SETTLED' || event.event_type === 'WORKER_SLASHED') {
          syncWithBackend();
        } else if (event.event_type === 'WALLET_UPDATED') {
          syncWithBackend();
        }
      },
      (status) => {
        setIsLiveConnected(status);
        if (status) {
          setIsAutoSimulating(false);
        }
      }
    );

    return unsubscribe;
  }, [syncWithBackend]);

  // Action Handlers
  const handleSpawn = useCallback(() => {
    setAgents((prev) => spawnAgent(prev));
  }, []);

  const handleRetire = useCallback(() => {
    setAgents((prev) => retireAgent(prev));
  }, []);

  const handleNewTask = useCallback(() => {
    setOpenTasks((prev) => createNewTask(prev, agents));
  }, [agents]);

  const handleLowerBid = useCallback(() => {
    setOpenTasks((prev) => placeLowerBidOnTask(prev, agents));
  }, [agents]);

  const handleResolve = useCallback(() => {
    setOpenTasks((prevOpen) => {
      const res = resolveTask(prevOpen, completedTasks);
      setCompletedTasks(res.completed);
      return res.tasks;
    });
  }, [completedTasks]);

  // Fallback simulator loop
  useEffect(() => {
    if (!isAutoSimulating) return;

    const interval = setInterval(() => {
      const roll = Math.random();
      if (roll < 0.2) {
        if (Math.random() < 0.6 || agents.length < 4) {
          handleSpawn();
        } else {
          handleRetire();
        }
      } else if (roll < 0.5) {
        if (openTasks.length > 0) {
          handleLowerBid();
        } else {
          handleNewTask();
        }
      } else if (roll < 0.75) {
        if (openTasks.length < 4) {
          handleNewTask();
        } else {
          handleResolve();
        }
      } else {
        if (openTasks.length > 0) {
          handleResolve();
        } else {
          handleNewTask();
        }
      }
    }, 3000);

    return () => clearInterval(interval);
  }, [isAutoSimulating, agents, openTasks, handleSpawn, handleRetire, handleNewTask, handleLowerBid, handleResolve]);

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
              Autonomous Agent Financial Infrastructure
            </p>
          </div>
        </div>

        {/* Live indicator & toggle */}
        <div className="flex items-center gap-3">
          <div className="flex items-center gap-2 px-3 py-1 rounded-xl text-xs font-mono font-bold bg-white border-2 border-slate-900 shadow-[2px_2px_0px_0px_rgba(15,23,42,1)]">
            <span
              className={`w-2.5 h-2.5 rounded-full border border-slate-900 ${
                isLiveConnected ? 'bg-emerald-400 animate-pulse' : 'bg-amber-400'
              }`}
            />
            <span>{isLiveConnected ? 'Live Backend Connected' : 'Local Standalone'}</span>
          </div>

          <button
            onClick={() => setIsAutoSimulating(!isAutoSimulating)}
            className="px-3 py-1 rounded-xl text-xs font-mono font-bold bg-white hover:bg-slate-50 border-2 border-slate-900 shadow-[2px_2px_0px_0px_rgba(15,23,42,1)] transition-all active:translate-x-0.5 active:translate-y-0.5"
          >
            {isAutoSimulating ? '⏸ Pause Sim' : '▶ Play Sim'}
          </button>
        </div>
      </header>

      {/* 3-ZONE WIREFRAME GRID */}
      <main className="flex-1 grid grid-cols-12 gap-4 overflow-hidden min-h-0">
        {/* ZONE 1: ACTIVE AGENTS (Left Column - 3 Cols) */}
        <div className="col-span-12 md:col-span-4 lg:col-span-3 h-full overflow-hidden">
          <ActiveAgentsPanel
            agents={agents}
            onSpawn={handleSpawn}
            onRetire={handleRetire}
          />
        </div>

        {/* RIGHT STACK: ZONE 2 & ZONE 3 (9 Cols) */}
        <div className="col-span-12 md:col-span-8 lg:col-span-9 h-full flex flex-col gap-4 overflow-hidden">
          {/* ZONE 2: BIDDING PLACE (Top 55%) */}
          <div className="h-[55%] min-h-0">
            <BiddingPlaceBoard
              openTasks={openTasks}
              onNewTask={handleNewTask}
              onLowerBid={handleLowerBid}
              onResolve={handleResolve}
            />
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
