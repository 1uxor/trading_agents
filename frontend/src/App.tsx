import { useState, useEffect } from 'react';
import { useWebSocket } from './api/useWebSocket';
import { api } from './api/client';
import { Dashboard } from './components/Dashboard';
import { WarRoom } from './components/WarRoom';
import { AgentForm } from './components/AgentForm';
import { BacktestView } from './components/BacktestView';
import { TradeLog } from './components/TradeLog';
import { Leaderboard } from './components/Leaderboard';
import { StrategyPresets } from './components/StrategyPresets';
import type { AgentSummary, AccountInfo, Position, CommentaryEvent } from './types';

type Page = 'dashboard' | 'warroom' | 'create' | 'backtest' | 'logs' | 'leaderboard' | 'presets';

export default function App() {
  const [page, setPage] = useState<Page>('dashboard');
  const [agents, setAgents] = useState<AgentSummary[]>([]);
  const [account, setAccount] = useState<AccountInfo | null>(null);
  const [positions, setPositions] = useState<Position[]>([]);
  const [selectedAgentId, setSelectedAgentId] = useState<string | null>(null);
  const { events, connected } = useWebSocket();

  const refresh = async () => {
    try {
      const [a, acc, pos] = await Promise.all([
        api.listAgents(),
        api.getAccount(),
        api.getPositions(),
      ]);
      setAgents(a);
      setAccount(acc);
      setPositions(pos);
    } catch (e) {
      console.error('Refresh failed:', e);
    }
  };

  useEffect(() => {
    refresh();
    const interval = setInterval(refresh, 5000);
    return () => clearInterval(interval);
  }, []);

  // Refresh when we get trade results
  useEffect(() => {
    const lastEvent = events[events.length - 1];
    if (lastEvent?.event === 'result') refresh();
  }, [events]);

  const handleKillSwitch = async () => {
    if (!confirm('KILL SWITCH: This will close ALL positions and stop ALL agents. Continue?')) return;
    await api.killSwitch();
    refresh();
  };

  const handleDeleteAgent = async (id: string) => {
    await api.deleteAgent(id);
    if (selectedAgentId === id) setSelectedAgentId(null);
    refresh();
  };

  const navItems: { key: Page; label: string }[] = [
    { key: 'dashboard', label: 'Dashboard' },
    { key: 'warroom', label: 'War Room' },
    { key: 'leaderboard', label: 'Leaderboard' },
    { key: 'presets', label: 'Presets' },
    { key: 'create', label: 'New Agent' },
    { key: 'backtest', label: 'Backtest' },
    { key: 'logs', label: 'Trade Log' },
  ];

  return (
    <div className="min-h-screen bg-gray-950">
      {/* Header */}
      <header className="border-b border-gray-800 bg-gray-900/80 backdrop-blur sticky top-0 z-50">
        <div className="max-w-7xl mx-auto px-4 py-3 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <h1 className="text-xl font-bold bg-gradient-to-r from-blue-400 to-purple-400 bg-clip-text text-transparent">
              Trading Agents
            </h1>
            <span className={`text-xs px-2 py-0.5 rounded-full ${connected ? 'bg-green-500/20 text-green-400' : 'bg-red-500/20 text-red-400'}`}>
              {connected ? 'LIVE' : 'OFFLINE'}
            </span>
          </div>

          <nav className="flex gap-1">
            {navItems.map((item) => (
              <button
                key={item.key}
                onClick={() => { setPage(item.key); if (item.key !== 'dashboard') setSelectedAgentId(null); }}
                className={`px-3 py-1.5 text-sm rounded-lg transition-colors ${
                  page === item.key
                    ? 'bg-blue-500/20 text-blue-400'
                    : 'text-gray-400 hover:text-gray-200 hover:bg-gray-800'
                }`}
              >
                {item.label}
              </button>
            ))}
          </nav>

          <button
            onClick={handleKillSwitch}
            className="px-4 py-1.5 bg-red-600 hover:bg-red-500 text-white text-sm font-bold rounded-lg transition-colors animate-none hover:animate-pulse"
          >
            KILL SWITCH
          </button>
        </div>
      </header>

      {/* Main */}
      <main className={`mx-auto px-4 py-6 ${selectedAgentId ? 'max-w-[1400px]' : 'max-w-7xl'}`}>
        {page === 'dashboard' && (
          <Dashboard
            agents={agents}
            account={account}
            positions={positions}
            events={events}
            onAction={async (id, action) => { await api.agentAction(id, action); refresh(); }}
            onDelete={handleDeleteAgent}
            onNavigate={setPage}
            selectedAgentId={selectedAgentId}
            onSelectAgent={setSelectedAgentId}
          />
        )}
        {page === 'warroom' && (
          <WarRoom agents={agents} events={events} positions={positions} />
        )}
        {page === 'create' && (
          <AgentForm onCreated={() => { refresh(); setPage('dashboard'); }} />
        )}
        {page === 'leaderboard' && <Leaderboard />}
        {page === 'presets' && <StrategyPresets onNavigate={(p) => { setPage(p as Page); refresh(); }} />}
        {page === 'backtest' && <BacktestView />}
        {page === 'logs' && <TradeLog events={events} />}
      </main>
    </div>
  );
}
