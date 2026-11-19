import { useState, useEffect } from 'react';
import { api } from '../api/client';

interface AgentStats {
  agent_id: string;
  name: string;
  color: string;
  symbols: string[];
  strategies: string[];
  total_trades: number;
  wins: number;
  losses: number;
  win_rate: number;
  total_profit: number;
  avg_profit: number;
  best_trade: number;
  worst_trade: number;
}

type SortKey = 'total_profit' | 'win_rate' | 'total_trades' | 'avg_profit';

export function Leaderboard() {
  const [stats, setStats] = useState<AgentStats[]>([]);
  const [sortBy, setSortBy] = useState<SortKey>('total_profit');
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const load = async () => {
      try {
        const data = await api.getLeaderboard();
        setStats(data);
      } catch (e) {
        console.error('Leaderboard load failed:', e);
      } finally {
        setLoading(false);
      }
    };
    load();
    const interval = setInterval(load, 10_000);
    return () => clearInterval(interval);
  }, []);

  const sorted = [...stats].sort((a, b) => {
    if (sortBy === 'win_rate') return b.win_rate - a.win_rate;
    if (sortBy === 'total_trades') return b.total_trades - a.total_trades;
    if (sortBy === 'avg_profit') return b.avg_profit - a.avg_profit;
    return b.total_profit - a.total_profit;
  });

  const getRankBadge = (index: number) => {
    if (index === 0) return 'bg-yellow-500/20 text-yellow-400 border-yellow-500/30';
    if (index === 1) return 'bg-gray-400/20 text-gray-300 border-gray-400/30';
    if (index === 2) return 'bg-orange-500/20 text-orange-400 border-orange-500/30';
    return 'bg-gray-800 text-gray-500 border-gray-700';
  };

  const sortButtons: { key: SortKey; label: string }[] = [
    { key: 'total_profit', label: 'Profit' },
    { key: 'win_rate', label: 'Win Rate' },
    { key: 'total_trades', label: 'Trades' },
    { key: 'avg_profit', label: 'Avg Profit' },
  ];

  return (
    <div>
      <div className="flex items-center justify-between mb-6">
        <h2 className="text-2xl font-bold text-white">Agent Leaderboard</h2>
        <div className="flex gap-1">
          {sortButtons.map((btn) => (
            <button
              key={btn.key}
              onClick={() => setSortBy(btn.key)}
              className={`px-3 py-1.5 text-xs rounded-lg transition-colors ${
                sortBy === btn.key
                  ? 'bg-blue-500/20 text-blue-400 border border-blue-500/30'
                  : 'bg-gray-800 text-gray-400 border border-gray-700 hover:bg-gray-700'
              }`}
            >
              {btn.label}
            </button>
          ))}
        </div>
      </div>

      {loading ? (
        <div className="text-center text-gray-500 py-12">Loading leaderboard...</div>
      ) : sorted.length === 0 ? (
        <div className="text-center text-gray-500 py-12">
          <p className="text-lg mb-2">No trade data yet</p>
          <p className="text-sm">Agents need to complete trades before they appear on the leaderboard.</p>
        </div>
      ) : (
        <div className="space-y-3">
          {sorted.map((agent, index) => (
            <div
              key={agent.agent_id}
              className="bg-gray-900 border border-gray-800 rounded-xl p-4 hover:border-gray-700 transition-colors"
            >
              <div className="flex items-center gap-4">
                {/* Rank */}
                <div className={`w-10 h-10 rounded-lg border flex items-center justify-center font-bold text-lg ${getRankBadge(index)}`}>
                  {index + 1}
                </div>

                {/* Agent info */}
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2 mb-1">
                    <div className="w-3 h-3 rounded-full" style={{ backgroundColor: agent.color }} />
                    <span className="font-semibold text-white truncate">{agent.name}</span>
                    <span className="text-xs text-gray-500">{agent.symbols.join(', ')}</span>
                  </div>
                  <div className="flex gap-1 flex-wrap">
                    {agent.strategies.map((s, i) => (
                      <span key={i} className="text-[10px] px-1.5 py-0.5 rounded bg-gray-800 text-gray-400">
                        {s}
                      </span>
                    ))}
                  </div>
                </div>

                {/* Stats */}
                <div className="flex gap-6 items-center text-sm">
                  <div className="text-center">
                    <div className="text-gray-500 text-[10px] uppercase tracking-wider mb-0.5">Trades</div>
                    <div className="text-white font-medium">{agent.total_trades}</div>
                  </div>
                  <div className="text-center">
                    <div className="text-gray-500 text-[10px] uppercase tracking-wider mb-0.5">W / L</div>
                    <div>
                      <span className="text-green-400">{agent.wins}</span>
                      <span className="text-gray-600"> / </span>
                      <span className="text-red-400">{agent.losses}</span>
                    </div>
                  </div>
                  <div className="text-center">
                    <div className="text-gray-500 text-[10px] uppercase tracking-wider mb-0.5">Win Rate</div>
                    <div className={`font-medium ${agent.win_rate >= 50 ? 'text-green-400' : agent.win_rate > 0 ? 'text-red-400' : 'text-gray-500'}`}>
                      {agent.win_rate}%
                    </div>
                  </div>
                  <div className="text-center">
                    <div className="text-gray-500 text-[10px] uppercase tracking-wider mb-0.5">Avg P/L</div>
                    <div className={`font-medium ${agent.avg_profit >= 0 ? 'text-green-400' : 'text-red-400'}`}>
                      {agent.avg_profit >= 0 ? '+' : ''}{agent.avg_profit}
                    </div>
                  </div>
                  <div className="text-center min-w-[80px]">
                    <div className="text-gray-500 text-[10px] uppercase tracking-wider mb-0.5">Total Profit</div>
                    <div className={`font-bold text-base ${agent.total_profit >= 0 ? 'text-green-400' : 'text-red-400'}`}>
                      {agent.total_profit >= 0 ? '+' : ''}{agent.total_profit.toFixed(2)}
                    </div>
                  </div>
                  <div className="text-center">
                    <div className="text-gray-500 text-[10px] uppercase tracking-wider mb-0.5">Best</div>
                    <div className="text-green-400 text-xs">+{agent.best_trade}</div>
                  </div>
                  <div className="text-center">
                    <div className="text-gray-500 text-[10px] uppercase tracking-wider mb-0.5">Worst</div>
                    <div className="text-red-400 text-xs">{agent.worst_trade}</div>
                  </div>
                </div>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
