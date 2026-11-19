import type { AgentSummary, AccountInfo, Position, CommentaryEvent } from '../types';
import { AgentCard } from './AgentCard';
import { AgentDetailView } from './AgentDetailView';
import { LiveFeed } from './LiveFeed';

interface Props {
  agents: AgentSummary[];
  account: AccountInfo | null;
  positions: Position[];
  events: CommentaryEvent[];
  onAction: (id: string, action: string) => void;
  onDelete: (id: string) => void;
  onNavigate: (page: any) => void;
  selectedAgentId: string | null;
  onSelectAgent: (id: string | null) => void;
}

export function Dashboard({ agents, account, positions, events, onAction, onDelete, onNavigate, selectedAgentId, onSelectAgent }: Props) {
  const totalProfit = positions.reduce((s, p) => s + p.profit, 0);

  return (
    <div className="space-y-6">
      {/* Account overview */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
        <StatCard label="Balance" value={account ? `$${account.balance.toFixed(2)}` : '--'} />
        <StatCard label="Equity" value={account ? `$${account.equity.toFixed(2)}` : '--'} />
        <StatCard
          label="Floating P&L"
          value={`$${totalProfit.toFixed(2)}`}
          color={totalProfit >= 0 ? 'text-green-400' : 'text-red-400'}
        />
        <StatCard label="Open Positions" value={String(positions.length)} />
      </div>

      {/* Agents section */}
      <div>
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-lg font-semibold text-gray-200">Agents</h2>
          <div className="flex items-center gap-2">
            {selectedAgentId && (
              <button
                onClick={() => onSelectAgent(null)}
                className="px-3 py-1.5 text-gray-400 hover:text-gray-200 text-sm rounded-lg hover:bg-gray-800 transition-colors"
              >
                Close Detail
              </button>
            )}
            <button
              onClick={() => onNavigate('create')}
              className="px-3 py-1.5 bg-blue-600 hover:bg-blue-500 text-white text-sm rounded-lg"
            >
              + New Agent
            </button>
          </div>
        </div>

        {agents.length === 0 ? (
          <div className="text-center py-12 text-gray-500 border border-dashed border-gray-700 rounded-xl">
            No agents yet. Create one to get started.
          </div>
        ) : selectedAgentId ? (
          /* Split view: sidebar + detail */
          <div className="flex gap-4">
            {/* Left: compact agent list */}
            <div className="w-80 flex-shrink-0 space-y-2 max-h-[calc(100vh-220px)] overflow-y-auto pr-1">
              {agents.map((agent) => (
                <div
                  key={agent.id}
                  onClick={() => onSelectAgent(agent.id)}
                  className={`cursor-pointer rounded-xl transition-all ${
                    agent.id === selectedAgentId
                      ? 'ring-2 ring-blue-500 ring-offset-1 ring-offset-gray-950'
                      : 'hover:ring-1 hover:ring-gray-600'
                  }`}
                >
                  <AgentCard
                    agent={agent}
                    events={events.filter((e) => e.agent_id === agent.id)}
                    positions={positions.filter((p) => p.agent_id === agent.id)}
                    onAction={onAction}
                    onDelete={onDelete}
                    compact
                  />
                </div>
              ))}
            </div>

            {/* Right: detail view */}
            <div className="flex-1 min-w-0">
              <AgentDetailView
                agentId={selectedAgentId}
                agents={agents}
                events={events}
                positions={positions}
              />
            </div>
          </div>
        ) : (
          /* Normal grid view — click to select */
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
            {agents.map((agent) => (
              <div
                key={agent.id}
                onClick={() => onSelectAgent(agent.id)}
                className="cursor-pointer hover:ring-1 hover:ring-gray-600 rounded-xl transition-all"
              >
                <AgentCard
                  agent={agent}
                  events={events.filter((e) => e.agent_id === agent.id)}
                  positions={positions.filter((p) => p.agent_id === agent.id)}
                  onAction={onAction}
                  onDelete={onDelete}
                />
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Live feed — only show when not in detail view */}
      {!selectedAgentId && <LiveFeed events={events} maxItems={50} />}
    </div>
  );
}

function StatCard({ label, value, color }: { label: string; value: string; color?: string }) {
  return (
    <div className="bg-gray-900 border border-gray-800 rounded-xl p-4">
      <div className="text-xs text-gray-500 uppercase tracking-wider">{label}</div>
      <div className={`text-2xl font-bold font-mono mt-1 ${color || 'text-gray-100'}`}>{value}</div>
    </div>
  );
}
