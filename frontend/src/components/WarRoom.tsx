import { useState } from 'react';
import type { AgentSummary, CommentaryEvent, Position } from '../types';
import { AgentPanel } from './AgentPanel';
import { LiveFeed } from './LiveFeed';
import { Chart } from './Chart';

interface Props {
  agents: AgentSummary[];
  events: CommentaryEvent[];
  positions: Position[];
}

export function WarRoom({ agents, events, positions }: Props) {
  const [selectedSymbol, setSelectedSymbol] = useState('EURUSD');

  const allSymbols = [...new Set(agents.flatMap((a) => a.symbols))];
  if (allSymbols.length > 0 && !allSymbols.includes(selectedSymbol)) {
    setSelectedSymbol(allSymbols[0]);
  }

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h2 className="text-lg font-bold text-gray-200">War Room</h2>
        <div className="flex gap-2">
          {(allSymbols.length > 0 ? allSymbols : ['EURUSD', 'GBPUSD', 'USDJPY']).map((sym) => (
            <button
              key={sym}
              onClick={() => setSelectedSymbol(sym)}
              className={`px-3 py-1 text-xs font-mono rounded ${
                selectedSymbol === sym ? 'bg-blue-600 text-white' : 'bg-gray-800 text-gray-400 hover:bg-gray-700'
              }`}
            >
              {sym}
            </button>
          ))}
        </div>
      </div>

      {/* Agent panels grid */}
      {agents.length > 0 ? (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-3">
          {agents.map((agent) => (
            <AgentPanel
              key={agent.id}
              agent={agent}
              events={events.filter((e) => e.agent_id === agent.id).slice(-10)}
              positions={positions.filter((p) => p.agent_id === agent.id)}
            />
          ))}
        </div>
      ) : (
        <div className="text-center py-8 text-gray-600 border border-dashed border-gray-700 rounded-xl">
          No agents active. Create agents and start them to see the War Room in action.
        </div>
      )}

      {/* Chart */}
      <Chart symbol={selectedSymbol} agents={agents} events={events} />

      {/* Unified live feed */}
      <LiveFeed events={events} maxItems={100} />
    </div>
  );
}
