const BASE = '';

async function request<T>(path: string, options?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    headers: { 'Content-Type': 'application/json' },
    ...options,
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(err.detail || res.statusText);
  }
  return res.json();
}

export const api = {
  // Agents
  listAgents: () => request<any[]>('/api/agents'),
  createAgent: (config: any) => request<any>('/api/agents', { method: 'POST', body: JSON.stringify({ config }) }),
  getAgent: (id: string) => request<any>(`/api/agents/${id}`),
  agentAction: (id: string, action: string) =>
    request<any>(`/api/agents/${id}/action`, { method: 'POST', body: JSON.stringify({ action }) }),
  deleteAgent: (id: string) => request<any>(`/api/agents/${id}`, { method: 'DELETE' }),
  getCommentary: (id: string) => request<any[]>(`/api/agents/${id}/commentary`),
  getAgentTrades: (id: string, limit = 100) =>
    request<any[]>(`/api/agents/${id}/trades?limit=${limit}`),
  getAgentSignals: (id: string, limit = 100) =>
    request<any[]>(`/api/agents/${id}/signals?limit=${limit}`),
  getAgentIndicators: (id: string, symbol: string, timeframe: string, count = 200) =>
    request<any>(`/api/agents/${id}/indicators?symbol=${symbol}&timeframe=${timeframe}&count=${count}`),

  getLeaderboard: () => request<any[]>('/api/agents/leaderboard'),

  // Market
  getSymbols: () => request<{ symbols: string[] }>('/api/market/symbols'),
  getOHLCV: (symbol: string, timeframe: string, count: number) =>
    request<{ data: any[] }>(`/api/market/ohlcv/${symbol}?timeframe=${timeframe}&count=${count}`),
  getPrice: (symbol: string) => request<any>(`/api/market/price/${symbol}`),
  getAccount: () => request<any>('/api/market/account'),
  getPositions: () => request<any[]>('/api/market/positions'),

  // Risk
  killSwitch: () => request<any>('/api/risk/kill-switch', { method: 'POST' }),
  unlock: () => request<any>('/api/risk/unlock', { method: 'POST' }),
  getRiskStatus: () => request<any>('/api/risk/status'),

  // Config
  getStrategies: () => request<any[]>('/api/config/strategies'),
  getModelProviders: () => request<any[]>('/api/config/model-providers'),
  getProviderModels: (provider: string) => request<any[]>(`/api/config/model-providers/${provider}/models`),
  getTimeframes: () => request<string[]>('/api/config/timeframes'),

  // Backtest
  runBacktest: (req: any) => request<any>('/api/backtest', { method: 'POST', body: JSON.stringify(req) }),

  // Data
  getDatasets: () => request<any[]>('/api/data/datasets'),
  uploadCsv: async (file: File, name: string, symbol: string, timeframe: string) => {
    const form = new FormData();
    form.append('file', file);
    form.append('name', name);
    form.append('symbol', symbol);
    form.append('timeframe', timeframe);
    const res = await fetch('/api/data/upload-csv', { method: 'POST', body: form });
    if (!res.ok) {
      const err = await res.json().catch(() => ({ detail: res.statusText }));
      throw new Error(err.detail || res.statusText);
    }
    return res.json();
  },

  // Health
  health: () => request<any>('/api/health'),
};
