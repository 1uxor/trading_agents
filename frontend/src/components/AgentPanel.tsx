import { useState, useEffect, useRef } from 'react';
import type { AgentSummary, CommentaryEvent, Position } from '../types';
import { ConfidenceMeter } from './ConfidenceMeter';

interface Props {
  agent: AgentSummary;
  events: CommentaryEvent[];
  positions: Position[];
}

export function AgentPanel({ agent, events, positions }: Props) {
  const lastEvent = events[events.length - 1];
  const [displayText, setDisplayText] = useState('');
  const textRef = useRef('');

  // Typewriter effect
  useEffect(() => {
    if (!lastEvent) return;
    const text = lastEvent.message;
    if (textRef.current === text) return;
    textRef.current = text;
    setDisplayText('');
    let i = 0;
    const timer = setInterval(() => {
      i++;
      if (i <= text.length && textRef.current === text) {
        setDisplayText(text.slice(0, i));
      } else {
        clearInterval(timer);
      }
    }, 15);
    return () => clearInterval(timer);
  }, [lastEvent?.message, lastEvent?.timestamp]);

  const statusLabel: Record<string, string> = {
    thinking: 'ANALYZING',
    signal: 'SIGNAL',
    executing: 'EXECUTING',
    result: 'DONE',
    explanation: 'READY',
    error: 'ERROR',
  };

  const statusColor: Record<string, string> = {
    thinking: 'text-yellow-400',
    signal: 'text-blue-400',
    executing: 'text-purple-400',
    result: 'text-green-400',
    explanation: 'text-gray-400',
    error: 'text-red-400',
  };

  const pnl = positions.reduce((s, p) => s + p.profit, 0);

  return (
    <div className="bg-gray-900/80 border border-gray-800 rounded-xl p-3 flex flex-col gap-2"
         style={{ borderTopColor: agent.color, borderTopWidth: 3 }}>
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <span
            className="w-3 h-3 rounded-full"
            style={{ backgroundColor: agent.color, boxShadow: `0 0 8px ${agent.color}40` }}
          />
          <span className="font-bold text-sm" style={{ color: agent.color }}>
            {agent.name}
          </span>
        </div>
        <span className={`status-dot ${agent.state}`} />
      </div>

      {/* Strategy tag */}
      <div className="text-xs text-gray-500 font-mono truncate">
        {agent.strategy} | {agent.model}
      </div>

      {/* Status + confidence */}
      <div className="flex items-center justify-between">
        {lastEvent ? (
          <span className={`text-xs font-bold ${statusColor[lastEvent.event] || 'text-gray-500'}`}>
            {statusLabel[lastEvent.event] || lastEvent.event.toUpperCase()}
          </span>
        ) : (
          <span className="text-xs text-gray-600">IDLE</span>
        )}
        <ConfidenceMeter value={lastEvent?.confidence ?? 0} color={agent.color} size={32} />
      </div>

      {/* Commentary */}
      <div className="bg-black/30 rounded-lg p-2 min-h-[60px] max-h-[80px] overflow-hidden">
        <p className="text-xs text-gray-300 font-mono leading-relaxed">
          {displayText ? (
            <>
              "{displayText}
              <span className="animate-pulse text-gray-600">|</span>"
            </>
          ) : (
            <span className="text-gray-700 italic">...</span>
          )}
        </p>
      </div>

      {/* Positions summary */}
      <div className="flex items-center justify-between text-xs">
        <span className="text-gray-500">{positions.length} positions</span>
        <span className={pnl >= 0 ? 'text-green-400 font-mono' : 'text-red-400 font-mono'}>
          {pnl >= 0 ? '+' : ''}{pnl.toFixed(2)}
        </span>
      </div>
    </div>
  );
}
