import { useState } from 'react';
import type { CommentaryEvent } from '../types';

interface Props {
  events: CommentaryEvent[];
}

export function TradeLog({ events }: Props) {
  const [filter, setFilter] = useState('');
  const [eventFilter, setEventFilter] = useState('all');

  const filtered = events.filter((e) => {
    if (eventFilter !== 'all' && e.event !== eventFilter) return false;
    if (filter && !e.message.toLowerCase().includes(filter.toLowerCase()) &&
        !e.agent_name.toLowerCase().includes(filter.toLowerCase())) return false;
    return true;
  }).reverse();

  return (
    <div className="space-y-4">
      <div className="flex items-center gap-3">
        <h2 className="text-lg font-bold text-gray-200">Decision Log</h2>
        <span className="text-xs text-gray-500">{filtered.length} entries</span>
      </div>

      {/* Filters */}
      <div className="flex gap-3">
        <input
          value={filter}
          onChange={(e) => setFilter(e.target.value)}
          placeholder="Search messages..."
          className="input-field flex-1"
        />
        <select value={eventFilter} onChange={(e) => setEventFilter(e.target.value)} className="input-field w-40">
          <option value="all">All events</option>
          <option value="signal">Signals</option>
          <option value="result">Results</option>
          <option value="executing">Executing</option>
          <option value="thinking">Thinking</option>
          <option value="error">Errors</option>
        </select>
      </div>

      {/* Table */}
      <div className="bg-gray-900 border border-gray-800 rounded-xl overflow-hidden">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-gray-800 text-gray-500 text-xs uppercase">
              <th className="px-4 py-2 text-left">Time</th>
              <th className="px-4 py-2 text-left">Agent</th>
              <th className="px-4 py-2 text-left">Event</th>
              <th className="px-4 py-2 text-left">Strategy</th>
              <th className="px-4 py-2 text-left">Confidence</th>
              <th className="px-4 py-2 text-left">Message</th>
            </tr>
          </thead>
          <tbody>
            {filtered.slice(0, 200).map((evt, i) => (
              <tr key={i} className="border-b border-gray-800/50 hover:bg-gray-800/30">
                <td className="px-4 py-2 text-gray-500 font-mono text-xs whitespace-nowrap">
                  {new Date(evt.timestamp).toLocaleTimeString()}
                </td>
                <td className="px-4 py-2">
                  <span className="flex items-center gap-1.5">
                    <span className="w-2 h-2 rounded-full" style={{ backgroundColor: evt.color }} />
                    <span style={{ color: evt.color }}>{evt.agent_name}</span>
                  </span>
                </td>
                <td className="px-4 py-2">
                  <EventBadge event={evt.event} />
                </td>
                <td className="px-4 py-2 text-gray-400 font-mono text-xs">{evt.strategy}</td>
                <td className="px-4 py-2 text-gray-400 font-mono">
                  {evt.confidence != null ? `${(evt.confidence * 100).toFixed(0)}%` : '--'}
                </td>
                <td className="px-4 py-2 text-gray-300 max-w-md truncate">{evt.message}</td>
              </tr>
            ))}
          </tbody>
        </table>

        {filtered.length === 0 && (
          <div className="text-center py-12 text-gray-600">No matching log entries.</div>
        )}
      </div>
    </div>
  );
}

function EventBadge({ event }: { event: string }) {
  const colors: Record<string, string> = {
    thinking: 'bg-yellow-500/20 text-yellow-400',
    signal: 'bg-blue-500/20 text-blue-400',
    executing: 'bg-purple-500/20 text-purple-400',
    result: 'bg-green-500/20 text-green-400',
    explanation: 'bg-gray-500/20 text-gray-400',
    error: 'bg-red-500/20 text-red-400',
  };
  return (
    <span className={`text-xs px-2 py-0.5 rounded-full ${colors[event] || 'bg-gray-700 text-gray-400'}`}>
      {event}
    </span>
  );
}
