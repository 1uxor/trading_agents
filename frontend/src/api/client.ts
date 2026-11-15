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
  getTimeframes: () => request<string[]>('/api/config/timeframes'),

  // Backtest
  runBacktest: (req: any) => request<any>('/api/backtest', { method: 'POST', body: JSON.stringify(req) }),

  // Health
  health: () => request<any>('/api/health'),
};
