import { useState, useEffect, useRef } from 'react';
import type { AgentSummary, CommentaryEvent, Position } from '../types';
import { ConfidenceMeter } from './ConfidenceMeter';

interface Props {
  agent: AgentSummary;
  events: CommentaryEvent[];
  positions: Position[];
  onAction: (id: string, action: string) => void;
}

export function AgentCard({ agent, events, positions, onAction }: Props) {
  const lastEvent = events[events.length - 1];
  const [displayText, setDisplayText] = useState('');
  const textRef = useRef('');

  // Typewriter effect for latest commentary
  useEffect(() => {
    if (!lastEvent) return;
    const text = lastEvent.message;
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
    }, 20);
    return () => clearInterval(timer);
  }, [lastEvent?.message]);

  const agentProfit = positions.reduce((s, p) => s + p.profit, 0);

  const eventIcon: Record<string, string> = {
    thinking: '\u{1F914}',
    signal: '\u{1F4CA}',
    executing: '\u{26A1}',
    result: '\u{2705}',
    explanation: '\u{1F4AC}',
    error: '\u{274C}',
  };

  return (
    <div
      className="bg-gray-900 border border-gray-800 rounded-xl p-4 space-y-3 relative overflow-hidden"
      style={{ borderLeftColor: agent.color, borderLeftWidth: 4 }}
    >
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <span className={`status-dot ${agent.state}`} />
          <span className="font-semibold" style={{ color: agent.color }}>
            {agent.name}
          </span>
        </div>
        <div className="flex gap-1">
          {agent.state === 'stopped' && (
            <ActionBtn label="Start" onClick={() => onAction(agent.id, 'start')} />
          )}
          {agent.state === 'running' && (
            <>
              <ActionBtn label="Pause" onClick={() => onAction(agent.id, 'pause')} />
              <ActionBtn label="Stop" onClick={() => onAction(agent.id, 'stop')} variant="danger" />
            </>
          )}
          {agent.state === 'paused' && (
            <>
              <ActionBtn label="Resume" onClick={() => onAction(agent.id, 'resume')} />
              <ActionBtn label="Stop" onClick={() => onAction(agent.id, 'stop')} variant="danger" />
            </>
          )}
        </div>
      </div>

      {/* Info row */}
      <div className="flex items-center gap-3 text-xs text-gray-400">
        <span className="font-mono">{agent.symbols.join(', ')}</span>
        <span>{agent.timeframe}</span>
        <span className="px-1.5 py-0.5 bg-gray-800 rounded text-gray-300">{agent.strategy}</span>
      </div>

      {/* Confidence + positions */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          {lastEvent && (
            <ConfidenceMeter value={lastEvent.confidence ?? 0} color={agent.color} size={36} />
          )}
          <div className="text-xs text-gray-500">
            {positions.length} pos | P&L:{' '}
            <span className={agentProfit >= 0 ? 'text-green-400' : 'text-red-400'}>
              ${agentProfit.toFixed(2)}
            </span>
          </div>
        </div>
        {lastEvent && (
          <span className="text-lg">{eventIcon[lastEvent.event] || ''}</span>
        )}
      </div>

      {/* Commentary bubble */}
      <div className="bg-gray-800/50 rounded-lg p-3 min-h-[48px]">
        {displayText ? (
          <p className="text-sm text-gray-300 font-mono leading-relaxed">
            <span className="text-gray-500 mr-1">&gt;</span>
            {displayText}
            <span className="animate-pulse ml-0.5 text-gray-500">|</span>
          </p>
        ) : (
          <p className="text-sm text-gray-600 italic">Waiting for activity...</p>
        )}
      </div>
    </div>
  );
}

function ActionBtn({ label, onClick, variant }: { label: string; onClick: () => void; variant?: string }) {
  const cls =
    variant === 'danger'
      ? 'bg-red-600/20 text-red-400 hover:bg-red-600/40'
      : 'bg-blue-600/20 text-blue-400 hover:bg-blue-600/40';
  return (
    <button onClick={onClick} className={`px-2 py-1 text-xs rounded ${cls} transition-colors`}>
      {label}
    </button>
  );
}
