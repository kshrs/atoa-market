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
  const palette = getAgentPalette(agent.id);

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
          {agent.id}
        </div>

        <div className="min-w-0">
          <div className="text-xs font-semibold text-slate-800 truncate">
            {agent.name}
          </div>
          <div className="text-[11px] text-slate-400 truncate">
            {agent.spec || 'Node'}
          </div>
        </div>
      </div>

      {/* Soft Status Pill (No glowing dot) */}
      <div className="flex-shrink-0">
        {isDelegating ? (
          <span className="inline-flex items-center px-2 py-0.5 rounded-full text-[11px] font-medium bg-amber-50 text-amber-800 border border-amber-200/80">
            Delegating
          </span>
        ) : (
          <span className="inline-flex items-center px-2 py-0.5 rounded-full text-[11px] font-medium bg-slate-100 text-slate-700 border border-slate-200">
            Working
          </span>
        )}
      </div>
    </motion.div>
  );
}

export function AgentPanel({ agents, onSpawn, onRetire }) {
  const delegatingCount = agents.filter((a) => a.status === 'delegating').length;
  const workingCount = agents.filter((a) => a.status === 'working').length;

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

        {/* Quiet Subtitle */}
        <div className="flex items-center gap-2 mt-2 text-xs text-slate-500">
          <span>{delegatingCount} delegating</span>
          <span>·</span>
          <span>{workingCount} working</span>
        </div>
      </div>

      {/* Agent Cards Dynamic List */}
      <div className="flex-1 p-3 overflow-y-auto space-y-2">
        <AnimatePresence mode="popLayout" initial={false}>
          {agents.map((agent) => (
            <AgentChip key={agent.id} agent={agent} />
          ))}
        </AnimatePresence>
      </div>
    </aside>
  );
}

// ----------------------------------------------------------------------
// 2. BIDDING PLACE (TOP RIGHT ZONE) & BID CHIP
// ----------------------------------------------------------------------
export function BidderChip({ bid, isWinner }) {
  const palette = getAgentPalette(bid.bidderId);

  return (
    <div
      className={`inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs transition-colors flex-shrink-0 ${
        isWinner
          ? 'bg-emerald-50 border border-emerald-300 text-emerald-900 font-medium shadow-xs'
          : 'bg-slate-50 border border-slate-200 text-slate-700'
      }`}
    >
      {/* Micro Avatar */}
      <span
        className={`w-4 h-4 rounded-full flex items-center justify-center text-[9px] font-semibold ${palette.bg} ${palette.text}`}
      >
        {bid.bidderId.replace('AG-', '')}
      </span>

      {/* Price */}
      <span>{bid.price.toFixed(2)} ETH</span>

      {/* Winner Label */}
      {isWinner && (
        <span className="text-[10px] text-emerald-700 font-semibold uppercase tracking-wider pl-0.5">
          Low
        </span>
      )}
    </div>
  );
}

export function TaskRow({ task }) {
  const sortedBids = [...task.bids].sort((a, b) => a.price - b.price);
  const lowestPrice = sortedBids.length > 0 ? sortedBids[0].price : null;
  const delegatorPalette = getAgentPalette(task.assignee?.id || 'AG-1');

  return (
    <motion.div
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      exit={{ opacity: 0 }}
      transition={{ duration: 0.2, ease: 'easeOut' }}
      className="p-3.5 rounded-lg bg-white border border-slate-200 hover:border-slate-300 transition-colors"
    >
      <div className="grid grid-cols-12 gap-4 items-center">
        {/* Assignee / Delegator (3 cols) */}
        <div className="col-span-12 sm:col-span-4 lg:col-span-3 flex items-center gap-2.5 min-w-0">
          <div
            className={`w-8 h-8 rounded-full flex-shrink-0 flex items-center justify-center font-semibold text-xs border ${delegatorPalette.bg} ${delegatorPalette.text} ${delegatorPalette.border}`}
          >
            {task.assignee?.id || 'AG'}
          </div>
          <div className="min-w-0">
            <div className="text-xs font-semibold text-slate-800 truncate">
              {task.assignee?.name || 'Delegator'}
            </div>
            <div className="text-[11px] text-slate-400">
              Delegator
            </div>
          </div>
        </div>

        {/* Task Title + Description (4 cols) */}
        <div className="col-span-12 sm:col-span-8 lg:col-span-4 min-w-0">
          <div className="text-xs font-semibold text-slate-900 truncate">
            {task.title}
          </div>
          <div className="text-[11px] text-slate-500 truncate mt-0.5">
            {task.description}
          </div>
          <div className="text-[11px] text-slate-400 mt-1">
            Max budget: {task.maxBudget.toFixed(2)} ETH · {task.bids.length} bids
          </div>
        </div>

        {/* Bids List - Plain horizontal rounded chips sorted low-to-high (5 cols) */}
        <div className="col-span-12 lg:col-span-5 min-w-0">
          <div className="flex items-center gap-1.5 flex-wrap">
            {sortedBids.map((bid) => (
              <BidderChip
                key={bid.bidderId}
                bid={bid}
                isWinner={bid.price === lowestPrice}
              />
            ))}
          </div>
        </div>
      </div>
    </motion.div>
  );
}

export function BiddingBoard({ openTasks, onNewTask, onLowerBid, onResolve }) {
  return (
    <section className="h-full flex flex-col bg-slate-50/50 border-b border-slate-200 overflow-hidden select-none">
      {/* Header */}
      <div className="px-5 py-3 border-b border-slate-200 bg-white flex items-center justify-between flex-shrink-0">
        <div className="flex items-center gap-2">
          <h2 className="text-sm font-semibold text-slate-900">
            Bidding Place
          </h2>
          <span className="text-xs font-medium text-slate-500 bg-slate-100 px-2 py-0.5 rounded-full border border-slate-200">
            {openTasks.length} open
          </span>
        </div>

        {/* Action Controls */}
        <div className="flex items-center gap-2">
          <button
            onClick={onNewTask}
            className="px-2.5 py-1 rounded bg-white hover:bg-slate-50 border border-slate-200 text-slate-700 text-xs font-medium transition-colors"
          >
            + Post Task
          </button>
          <button
            onClick={onLowerBid}
            disabled={openTasks.length === 0}
            className="px-2.5 py-1 rounded bg-white hover:bg-slate-50 border border-slate-200 text-slate-700 text-xs font-medium transition-colors disabled:opacity-40 disabled:cursor-not-allowed"
          >
            Lower Bid
          </button>
          <button
            onClick={onResolve}
            disabled={openTasks.length === 0}
            className="px-2.5 py-1 rounded bg-slate-900 hover:bg-slate-800 text-white text-xs font-medium transition-colors disabled:opacity-40 disabled:cursor-not-allowed"
          >
            Settle Task
          </button>
        </div>
      </div>

      {/* Task Rows List */}
      <div className="flex-1 p-4 overflow-y-auto space-y-2.5">
        <AnimatePresence mode="popLayout" initial={false}>
          {openTasks.length === 0 ? (
            <motion.div
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              className="h-36 flex flex-col items-center justify-center text-center text-slate-400 text-xs border border-dashed border-slate-200 rounded-lg bg-white"
            >
              <span>No open tasks in auction queue.</span>
              <button
                onClick={onNewTask}
                className="mt-2 text-xs font-medium text-slate-700 hover:text-slate-900 underline"
              >
                Post a new task
              </button>
            </motion.div>
          ) : (
            openTasks.map((task) => (
              <TaskRow key={task.id} task={task} />
            ))
          )}
        </AnimatePresence>
      </div>
    </section>
  );
}

// ----------------------------------------------------------------------
// 3. COMPLETED WORKS (BOTTOM RIGHT ZONE)
// ----------------------------------------------------------------------
export function CompletedBoard({ completedTasks }) {
  return (
    <section className="h-full flex flex-col bg-slate-50/50 overflow-hidden select-none">
      {/* Header */}
      <div className="px-5 py-3 border-b border-slate-200 bg-white flex items-center justify-between flex-shrink-0">
        <div className="flex items-center gap-2">
          <h2 className="text-sm font-semibold text-slate-900">
            Completed Works
          </h2>
          <span className="text-xs font-medium text-slate-500 bg-slate-100 px-2 py-0.5 rounded-full border border-slate-200">
            {completedTasks.length} settled
          </span>
        </div>

        <span className="text-xs text-slate-400">
          Autonomous verification & settlement
        </span>
      </div>

      {/* Completed Tasks List */}
      <div className="flex-1 p-4 overflow-y-auto space-y-2.5">
        <AnimatePresence mode="popLayout" initial={false}>
          {completedTasks.map((task) => {
            const delegatorPalette = getAgentPalette(task.assignee?.id || 'AG-1');
            const winnerPalette = getAgentPalette(task.winner?.id || 'AG-2');

            return (
              <motion.div
                key={task.id}
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
                exit={{ opacity: 0 }}
                transition={{ duration: 0.2, ease: 'easeOut' }}
                className="p-3.5 rounded-lg bg-white border border-slate-200 hover:border-slate-300 transition-colors"
              >
                <div className="grid grid-cols-12 gap-4 items-center">
                  {/* Assignee / Delegator (3 cols) */}
                  <div className="col-span-12 sm:col-span-4 lg:col-span-3 flex items-center gap-2.5 min-w-0">
                    <div
                      className={`w-8 h-8 rounded-full flex-shrink-0 flex items-center justify-center font-semibold text-xs border ${delegatorPalette.bg} ${delegatorPalette.text} ${delegatorPalette.border}`}
                    >
                      {task.assignee?.id || 'AG'}
                    </div>
                    <div className="min-w-0">
                      <div className="text-xs font-semibold text-slate-800 truncate">
                        {task.assignee?.name || 'Delegator'}
                      </div>
                      <div className="text-[11px] text-slate-400">
                        Delegator
                      </div>
                    </div>
                  </div>

                  {/* Task Details (4 cols) */}
                  <div className="col-span-12 sm:col-span-8 lg:col-span-4 min-w-0">
                    <div className="text-xs font-semibold text-slate-900 truncate">
                      {task.title}
                    </div>
                    <div className="text-[11px] text-slate-500 truncate mt-0.5">
                      {task.description}
                    </div>
                    <div className="text-[11px] text-slate-400 mt-1">
                      Settled at {task.settledAt}
                    </div>
                  </div>

                  {/* Winner + 3 Status Pills (5 cols) */}
                  <div className="col-span-12 lg:col-span-5 flex items-center justify-between gap-3 min-w-0">
                    {/* Winner Agent Pill */}
                    <div className="flex items-center gap-1.5 min-w-0">
                      <span
                        className={`w-5 h-5 rounded-full flex items-center justify-center text-[10px] font-semibold ${winnerPalette.bg} ${winnerPalette.text} border ${winnerPalette.border} flex-shrink-0`}
                      >
                        {task.winner?.id?.replace('AG-', '') || 'W'}
                      </span>
                      <span className="text-xs font-medium text-slate-700 truncate">
                        {task.winner?.name || 'Worker'}
                      </span>
                    </div>

                    {/* Three Small Status Pills: Verified/Pending, Done/Failed, Payout */}
                    <div className="flex items-center gap-1.5 flex-shrink-0">
                      {/* 1. Verification Pill */}
                      {task.verification === 'Verified' ? (
                        <span className="px-2 py-0.5 rounded-full text-[11px] font-medium bg-emerald-50 text-emerald-800 border border-emerald-200/80">
                          Verified
                        </span>
                      ) : (
                        <span className="px-2 py-0.5 rounded-full text-[11px] font-medium bg-amber-50 text-amber-800 border border-amber-200/80">
                          Pending
                        </span>
                      )}

                      {/* 2. Done / Failed Pill */}
                      {task.status === 'Done' ? (
                        <span className="px-2 py-0.5 rounded-full text-[11px] font-medium bg-slate-100 text-slate-700 border border-slate-200">
                          Done
                        </span>
                      ) : (
                        <span className="px-2 py-0.5 rounded-full text-[11px] font-medium bg-rose-50 text-rose-700 border border-rose-200/80">
                          Failed
                        </span>
                      )}

                      {/* 3. Payout Amount Pill */}
                      <span className="px-2 py-0.5 rounded-full text-[11px] font-semibold bg-slate-50 text-slate-800 border border-slate-200">
                        {task.payment}
                      </span>
                    </div>
                  </div>
                </div>
              </motion.div>
            );
          })}
        </AnimatePresence>
      </div>
    </section>
  );
}

// ----------------------------------------------------------------------
// MAIN APP COMPONENT & SIMULATION ENGINE
// ----------------------------------------------------------------------
export default function App() {
  const [agents, setAgents] = useState(INITIAL_AGENTS);
  const [openTasks, setOpenTasks] = useState(INITIAL_OPEN_TASKS);
  const [completedTasks, setCompletedTasks] = useState(INITIAL_COMPLETED_TASKS);

  // Minimal simulator state
  const [isAutoSimulating, setIsAutoSimulating] = useState(true);

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

  // Automated Swarm Simulator Loop (Calm 3-second interval)
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
              Agent Marketplace
            </h1>
            <p className="text-[11px] text-slate-400 leading-tight">
              Live Autonomous Coordination View
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

        {/* Single Minimal Toggle */}
        <div className="flex items-center gap-2">
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


