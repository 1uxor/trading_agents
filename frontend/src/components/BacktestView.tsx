import { useState, useEffect } from 'react';
import { api } from '../api/client';
import type { BacktestResult, StrategyMeta } from '../types';
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer } from 'recharts';

export function BacktestView() {
  const [strategies, setStrategies] = useState<StrategyMeta[]>([]);
  const [strategy, setStrategy] = useState('ma_crossover');
  const [symbol, setSymbol] = useState('EURUSD');
  const [timeframe, setTimeframe] = useState('H1');
  const [bars, setBars] = useState(3000);
  const [running, setRunning] = useState(false);
  const [result, setResult] = useState<BacktestResult | null>(null);
  const [error, setError] = useState('');

  useEffect(() => {
    api.getStrategies().then(setStrategies);
  }, []);

  const run = async () => {
    setError('');
    setRunning(true);
    setResult(null);
    try {
      const r = await api.runBacktest({
        agent_config: {
          name: 'Backtest',
          color: '#3498DB',
          symbols: [symbol],
          timeframe,
          model_provider: 'no_model',
          model_config: {},
          strategies: [{ name: strategy, params: {} }],
          combiner: null,
          risk_profile: {
            max_risk_per_trade_pct: 1.0,
            max_open_positions: 3,
            max_lot_size: 0.1,
            max_daily_loss_pct: 5.0,
          },
          schedule_seconds: 60,
          enabled: true,
        },
        symbol,
        timeframe,
        bars,
        walk_forward_splits: 1,
        spread_pips: 1.0,
        commission_per_lot: 7.0,
        slippage_pips: 0.5,
      });
      setResult(r);
    } catch (e: any) {
      setError(e.message || 'Backtest failed');
    }
    setRunning(false);
  };

  const equityCurve = result?.equity_curve.map((val, i) => ({ bar: i, equity: val })) || [];

  return (
    <div className="space-y-6 max-w-4xl mx-auto">
      <h2 className="text-lg font-bold text-gray-200">Backtester</h2>

      {/* Config */}
      <div className="bg-gray-900 border border-gray-800 rounded-xl p-4 grid grid-cols-2 md:grid-cols-4 gap-4">
        <div>
          <label className="text-xs text-gray-500">Strategy</label>
          <select value={strategy} onChange={(e) => setStrategy(e.target.value)} className="input-field">
            {strategies.map((s) => <option key={s.name} value={s.name}>{s.name}</option>)}
          </select>
        </div>
        <div>
          <label className="text-xs text-gray-500">Symbol</label>
          <input value={symbol} onChange={(e) => setSymbol(e.target.value)} className="input-field font-mono" />
        </div>
        <div>
          <label className="text-xs text-gray-500">Timeframe</label>
          <select value={timeframe} onChange={(e) => setTimeframe(e.target.value)} className="input-field">
            {['M5', 'M15', 'M30', 'H1', 'H4', 'D1'].map((t) => <option key={t}>{t}</option>)}
          </select>
        </div>
        <div>
          <label className="text-xs text-gray-500">Bars</label>
          <input type="number" value={bars} onChange={(e) => setBars(+e.target.value)} min={100} max={10000} className="input-field" />
        </div>
      </div>

      <button
        onClick={run}
        disabled={running}
        className="px-6 py-2 bg-purple-600 hover:bg-purple-500 disabled:bg-gray-700 text-white font-semibold rounded-xl transition-colors"
      >
        {running ? 'Running...' : 'Run Backtest'}
      </button>

      {error && <div className="bg-red-900/30 border border-red-800 text-red-400 text-sm rounded-lg p-3">{error}</div>}

      {/* Results */}
      {result && (
        <div className="space-y-4">
          <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
            <MetricCard label="Total Return" value={`${result.total_return_pct.toFixed(2)}%`}
              color={result.total_return_pct >= 0 ? 'text-green-400' : 'text-red-400'} />
            <MetricCard label="Sharpe Ratio" value={result.sharpe_ratio.toFixed(2)} />
            <MetricCard label="Sortino Ratio" value={result.sortino_ratio.toFixed(2)} />
            <MetricCard label="Max Drawdown" value={`${result.max_drawdown_pct.toFixed(2)}%`} color="text-red-400" />
            <MetricCard label="Win Rate" value={`${(result.win_rate * 100).toFixed(1)}%`} />
            <MetricCard label="Profit Factor" value={result.profit_factor.toFixed(2)} />
            <MetricCard label="Total Trades" value={String(result.total_trades)} />
          </div>

          {/* Equity curve */}
          {equityCurve.length > 0 && (
            <div className="bg-gray-900 border border-gray-800 rounded-xl p-4">
              <h3 className="text-sm font-semibold text-gray-400 mb-4">Equity Curve</h3>
              <ResponsiveContainer width="100%" height={300}>
                <LineChart data={equityCurve}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#1f2937" />
                  <XAxis dataKey="bar" stroke="#6b7280" />
                  <YAxis stroke="#6b7280" />
                  <Tooltip
                    contentStyle={{ backgroundColor: '#1f2937', border: '1px solid #374151', borderRadius: 8 }}
                    labelStyle={{ color: '#9ca3af' }}
                  />
                  <Line type="monotone" dataKey="equity" stroke="#3b82f6" dot={false} strokeWidth={2} />
                </LineChart>
              </ResponsiveContainer>
            </div>
          )}
        </div>
      )}
    </div>
  );
}

function MetricCard({ label, value, color }: { label: string; value: string; color?: string }) {
  return (
    <div className="bg-gray-900 border border-gray-800 rounded-xl p-3">
      <div className="text-xs text-gray-500">{label}</div>
      <div className={`text-lg font-bold font-mono ${color || 'text-gray-200'}`}>{value}</div>
    </div>
  );
}
