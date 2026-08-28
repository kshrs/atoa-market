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
import { fetchAnalytics, fetchTasks, fetchWallets, subscribeToLiveEvents } from './api';

// ----------------------------------------------------------------------
// HELPER UTILITIES: AVATAR PALETTES
// ----------------------------------------------------------------------
const AVATAR_PALETTES = [
  { bg: 'bg-slate-100', text: 'text-slate-700', border: 'border-slate-300' },
  { bg: 'bg-sky-50', text: 'text-sky-700', border: 'border-sky-200' },
  { bg: 'bg-indigo-50', text: 'text-indigo-700', border: 'border-indigo-200' },
  { bg: 'bg-emerald-50', text: 'text-emerald-700', border: 'border-emerald-200' },
  { bg: 'bg-amber-50', text: 'text-amber-800', border: 'border-amber-200' },
  { bg: 'bg-violet-50', text: 'text-violet-700', border: 'border-violet-200' },
  { bg: 'bg-teal-50', text: 'text-teal-700', border: 'border-teal-200' }
];

function getAgentPalette(id = '') {
  let hash = 0;
  for (let i = 0; i < id.length; i++) {
    hash = id.charCodeAt(i) + ((hash << 5) - hash);
  }
  const index = Math.abs(hash) % AVATAR_PALETTES.length;
  return AVATAR_PALETTES[index];
}

// ----------------------------------------------------------------------
// 1. ACTIVE AGENTS (LEFT SIDEBAR)
// ----------------------------------------------------------------------
export function AgentChip({ agent }) {
  const isDelegating = agent.status === 'delegating';
  const palette = getAgentPalette(agent.id || agent.address || '');

  return (
    <motion.div
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      exit={{ opacity: 0 }}
      transition={{ duration: 0.2, ease: 'easeOut' }}
      className="flex items-center justify-between gap-3 p-3 rounded-lg bg-white border border-slate-200 hover:border-slate-300 hover:bg-slate-50/50 transition-colors"
    >
      {/* Avatar + Name + Spec */}
      <div className="flex items-center gap-2.5 min-w-0">
        <div
          className={`w-8 h-8 rounded-full flex-shrink-0 flex items-center justify-center font-semibold text-xs border ${palette.bg} ${palette.text} ${palette.border}`}
        >
          {(agent.id || agent.name || 'AG').slice(0, 4)}
        </div>

        <div className="min-w-0">
          <div className="text-xs font-semibold text-slate-800 truncate">
            {agent.name || agent.address}
          </div>
          <div className="text-[11px] text-slate-400 truncate">
            {agent.role || agent.spec || 'Agent Node'} • {agent.balance_usdc != null ? `${agent.balance_usdc} USDC` : ''}
          </div>
        </div>
      </div>

      {/* Soft Status Pill */}
      <div className="flex-shrink-0">
        {isDelegating ? (
          <span className="inline-flex items-center px-2 py-0.5 rounded-full text-[11px] font-medium bg-amber-50 text-amber-800 border border-amber-200/80">
            Delegating
          </span>
        ) : (
          <span className="inline-flex items-center px-2 py-0.5 rounded-full text-[11px] font-medium bg-slate-100 text-slate-700 border border-slate-200">
            {agent.role === 'Rogue' ? 'Rogue Bot' : 'Working'}
          </span>
        )}
      </div>
    </motion.div>
  );
}

export function AgentPanel({ agents, onSpawn, onRetire }) {
  return (
    <aside className="h-full flex flex-col bg-white border-r border-slate-200 select-none">
      {/* Panel Header */}
      <div className="p-4 border-b border-slate-200 flex-shrink-0">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <h2 className="text-sm font-semibold text-slate-900">
              Active Agents
            </h2>
            <span className="text-xs font-medium text-slate-500 bg-slate-100 px-2 py-0.5 rounded-full border border-slate-200">
              {agents.length}
            </span>
          </div>

          <div className="flex items-center gap-1.5">
            <button
              onClick={onSpawn}
              title="Add Agent"
              className="text-xs font-medium px-2 py-1 rounded bg-slate-50 hover:bg-slate-100 border border-slate-200 text-slate-700 transition-colors"
            >
              + Add
            </button>
            <button
              onClick={onRetire}
              disabled={agents.length <= 3}
              title="Remove Agent"
              className="text-xs font-medium px-2 py-1 rounded bg-slate-50 hover:bg-slate-100 border border-slate-200 text-slate-600 transition-colors disabled:opacity-40 disabled:cursor-not-allowed"
            >
              - Remove
            </button>
          </div>
        </div>
      </div>

      {/* Agents Scrollable List */}
      <div className="flex-1 overflow-y-auto p-3 space-y-2">
        <AnimatePresence>
          {agents.map((agent) => (
            <AgentChip key={agent.id || agent.address} agent={agent} />
          ))}
        </AnimatePresence>
      </div>
    </aside>
  );
}

// ----------------------------------------------------------------------
// 2. BIDDING BOARD (TOP 55%)
// ----------------------------------------------------------------------
export function BiddingBoard({ openTasks, onNewTask, onLowerBid, onResolve }) {
  return (
    <section className="h-full flex flex-col bg-white border-b border-slate-200 select-none">
      {/* Header */}
      <div className="p-4 border-b border-slate-200 flex-shrink-0 flex items-center justify-between">
        <div className="flex items-center gap-2">
          <h2 className="text-sm font-semibold text-slate-900">
            Open Task Auctions & Bidding
          </h2>
          <span className="text-xs font-medium text-slate-500 bg-slate-100 px-2 py-0.5 rounded-full border border-slate-200">
            {openTasks.length} active
          </span>
        </div>

        <div className="flex items-center gap-2">
          <button
            onClick={onNewTask}
            className="text-xs font-medium px-2.5 py-1 rounded bg-slate-900 text-white hover:bg-slate-800 transition-colors"
          >
            + Post Task
          </button>
          <button
            onClick={onLowerBid}
            disabled={openTasks.length === 0}
            className="text-xs font-medium px-2.5 py-1 rounded bg-white hover:bg-slate-50 border border-slate-200 text-slate-700 transition-colors disabled:opacity-40 disabled:cursor-not-allowed"
          >
            ↓ Simulate Bid
          </button>
          <button
            onClick={onResolve}
            disabled={openTasks.length === 0}
            className="text-xs font-medium px-2.5 py-1 rounded bg-white hover:bg-slate-50 border border-slate-200 text-slate-700 transition-colors disabled:opacity-40 disabled:cursor-not-allowed"
          >
            ✓ Verify & Settle
          </button>
        </div>
      </div>

      {/* Task Cards Grid / List */}
      <div className="flex-1 overflow-y-auto p-4 space-y-3">
        {openTasks.length === 0 ? (
          <div className="h-full flex items-center justify-center text-xs text-slate-400">
            No open auctions. Awaiting new tasks from agy-cli agents or simulator...
          </div>
        ) : (
          openTasks.map((task) => (
            <div
              key={task.id || task.task_id}
              className="p-3.5 rounded-lg bg-slate-50/70 border border-slate-200 flex flex-col gap-2.5"
            >
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <span className="text-xs font-semibold text-slate-900">
                    {task.title}
                  </span>
                  <span className="text-[10px] uppercase font-mono px-1.5 py-0.5 rounded bg-slate-200 text-slate-700">
                    {task.category || 'TASK'}
                  </span>
                </div>
                <div className="text-xs font-mono font-semibold text-slate-900">
                  {task.budget_usdc != null ? `${task.budget_usdc} USDC` : `${task.maxBudget || 0} ${task.unit || 'USDC'}`}
                </div>
              </div>

              <p className="text-xs text-slate-500 line-clamp-2">
                {task.description}
              </p>

              {/* Bids List */}
              {task.bids && task.bids.length > 0 && (
                <div className="flex flex-wrap gap-1.5 pt-1 border-t border-slate-200/60">
                  <span className="text-[11px] text-slate-400 self-center mr-1">Bids:</span>
                  {task.bids.map((b, idx) => (
                    <span
                      key={idx}
                      className="inline-flex items-center gap-1 text-[11px] px-2 py-0.5 rounded bg-white border border-slate-200 text-slate-700 font-mono"
                    >
                      <span>{b.agentName || b.worker_address || b.bidderId}</span>
                      <strong className="text-slate-900">${b.price || b.bid_price_usdc}</strong>
                    </span>
                  ))}
                </div>
              )}
            </div>
          ))
        )}
      </div>
    </section>
  );
}

// ----------------------------------------------------------------------
// 3. COMPLETED BOARD (BOTTOM 45%)
// ----------------------------------------------------------------------
export function CompletedBoard({ completedTasks }) {
  return (
    <section className="h-full flex flex-col bg-white select-none">
      {/* Header */}
      <div className="p-4 border-b border-slate-200 flex-shrink-0 flex items-center justify-between">
        <div className="flex items-center gap-2">
          <h2 className="text-sm font-semibold text-slate-900">
            Settled & Slashed Tasks (Ledger)
          </h2>
          <span className="text-xs font-medium text-slate-500 bg-slate-100 px-2 py-0.5 rounded-full border border-slate-200">
            {completedTasks.length} settled
          </span>
        </div>
      </div>

      {/* Completed List */}
      <div className="flex-1 overflow-y-auto p-4 space-y-2">
        {completedTasks.length === 0 ? (
          <div className="h-full flex items-center justify-center text-xs text-slate-400">
            No completed tasks yet. Completed transactions will appear here.
          </div>
        ) : (
          completedTasks.map((t, idx) => {
            const isSlashed = t.status === 'Failed' || t.status === 'SLASHED';
            return (
              <div
                key={t.id || t.task_id || idx}
                className="p-3 rounded-lg bg-slate-50/50 border border-slate-200 flex items-center justify-between gap-4"
              >
                <div className="min-w-0">
                  <div className="flex items-center gap-2">
                    <span className="text-xs font-semibold text-slate-800 truncate">
                      {t.title}
                    </span>
                    <span
                      className={`text-[10px] px-1.5 py-0.2 rounded font-medium ${
                        isSlashed
                          ? 'bg-rose-50 text-rose-700 border border-rose-200'
                          : 'bg-emerald-50 text-emerald-700 border border-emerald-200'
                      }`}
                    >
                      {isSlashed ? 'Slashed' : 'Verified'}
                    </span>
                  </div>
                  <div className="text-[11px] text-slate-400 truncate mt-0.5">
                    Winner: {t.winner?.name || t.assigned_worker || 'Unknown'} • {t.settledAt || 'Just now'}
                  </div>
                </div>

                <div className="text-xs font-mono font-semibold text-slate-800 flex-shrink-0">
                  {t.payment || (t.budget_usdc ? `${t.budget_usdc} USDC` : '')}
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
// MAIN APP COMPONENT (HYBRID: LIVE BACKEND + SIMULATOR FALLBACK)
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
        console.log('[ATOA Live Event]', event);
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
          // If live backend connected, turn off local random simulator to avoid collisions
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

  // Simulator fallback loop
  useEffect(() => {
    if (!isAutoSimulating) return;

    const interval = setInterval(() => {
      const roll = Math.random();
      if (roll < 0.2) {
        if (Math.random() < 0.6 || agents.length < 5) {
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
        if (openTasks.length < 5) {
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
    <div className="h-screen w-screen flex flex-col bg-slate-50 text-slate-800 overflow-hidden font-sans">
      {/* TOP STRIP: CLEAN & MINIMAL SUMMARY */}
      <header className="h-14 flex-shrink-0 bg-white border-b border-slate-200 px-6 flex items-center justify-between z-10">
        {/* Branding */}
        <div className="flex items-center gap-3">
          <div className="w-7 h-7 rounded-md bg-slate-900 text-white flex items-center justify-center text-xs font-bold tracking-tight">
            A2A
          </div>
          <div>
            <h1 className="text-sm font-semibold text-slate-900 leading-tight">
              ATOA Protocol Dashboard
            </h1>
            <p className="text-[11px] text-slate-400 leading-tight">
              Live Autonomous Coordination & Settlement View
            </p>
          </div>
        </div>

        {/* Small Plain Text Summary */}
        <div className="hidden md:flex items-center gap-3 text-xs text-slate-500">
          <span>
            <strong className="font-semibold text-slate-800">{agents.length}</strong> active agents
          </span>
          <span className="text-slate-300">·</span>
          <span>
            <strong className="font-semibold text-slate-800">{openTasks.length}</strong> open auctions
          </span>
          <span className="text-slate-300">·</span>
          <span>
            <strong className="font-semibold text-slate-800">{completedTasks.length}</strong> settled tasks
          </span>
        </div>

        {/* Live Backend Connection Indicator & Toggle */}
        <div className="flex items-center gap-2">
          <div className="flex items-center gap-1.5 px-2.5 py-1 rounded-md text-[11px] font-medium bg-slate-100 text-slate-700 border border-slate-200">
            <span
              className={`w-2 h-2 rounded-full ${
                isLiveConnected ? 'bg-emerald-500 animate-pulse' : 'bg-amber-400'
              }`}
            />
            <span>{isLiveConnected ? 'Live Backend Connected' : 'Local Standalone'}</span>
          </div>

          <button
            onClick={() => setIsAutoSimulating(!isAutoSimulating)}
            className="px-3 py-1.5 rounded-md text-xs font-medium bg-white hover:bg-slate-50 border border-slate-200 text-slate-700 transition-colors flex items-center gap-2 shadow-xs"
          >
            <span
              className={`w-2 h-2 rounded-full ${
                isAutoSimulating ? 'bg-emerald-500' : 'bg-slate-300'
              }`}
            />
            <span>{isAutoSimulating ? 'Simulator Active' : 'Simulator Paused'}</span>
          </button>
        </div>
      </header>

      {/* 3-ZONE LAYOUT */}
      <main className="flex-1 grid grid-cols-12 overflow-hidden">
        {/* ZONE 1: ACTIVE AGENTS (Left Column, ~25% width, full height) */}
        <div className="col-span-12 md:col-span-4 lg:col-span-3 h-full overflow-hidden">
          <AgentPanel
            agents={agents}
            onSpawn={handleSpawn}
            onRetire={handleRetire}
          />
        </div>

        {/* RIGHT STACK: TOP 55% BIDDING PLACE, BOTTOM 45% COMPLETED WORKS */}
        <div className="col-span-12 md:col-span-8 lg:col-span-9 h-full flex flex-col overflow-hidden">
          {/* ZONE 2: BIDDING PLACE (Top 55%) */}
          <div className="h-[55%] min-h-0">
            <BiddingBoard
              openTasks={openTasks}
              onNewTask={handleNewTask}
              onLowerBid={handleLowerBid}
              onResolve={handleResolve}
            />
          </div>

          {/* ZONE 3: COMPLETED WORKS (Bottom 45%) */}
          <div className="h-[45%] min-h-0">
            <CompletedBoard
              completedTasks={completedTasks}
            />
          </div>
        </div>
      </main>
    </div>
  );
}
