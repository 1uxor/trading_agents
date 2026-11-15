import type { AgentSummary, AccountInfo, Position, CommentaryEvent } from '../types';
import { AgentCard } from './AgentCard';
import { LiveFeed } from './LiveFeed';
import { ConfidenceMeter } from './ConfidenceMeter';

interface Props {
  agents: AgentSummary[];
  account: AccountInfo | null;
  positions: Position[];
  events: CommentaryEvent[];
  onAction: (id: string, action: string) => void;
  onNavigate: (page: string) => void;
}

export function Dashboard({ agents, account, positions, events, onAction, onNavigate }: Props) {
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

      {/* Agents grid */}
      <div>
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-lg font-semibold text-gray-200">Agents</h2>
          <button
            onClick={() => onNavigate('create')}
            className="px-3 py-1.5 bg-blue-600 hover:bg-blue-500 text-white text-sm rounded-lg"
          >
            + New Agent
          </button>
        </div>

        {agents.length === 0 ? (
          <div className="text-center py-12 text-gray-500 border border-dashed border-gray-700 rounded-xl">
            No agents yet. Create one to get started.
          </div>
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
            {agents.map((agent) => (
              <AgentCard
                key={agent.id}
                agent={agent}
                events={events.filter((e) => e.agent_id === agent.id)}
                positions={positions.filter((p) => p.agent_id === agent.id)}
                onAction={onAction}
              />
            ))}
          </div>
        )}
      </div>

      {/* Live feed */}
      <LiveFeed events={events} maxItems={50} />
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
