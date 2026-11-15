import { useState, useEffect, useRef } from 'react';
import { api } from '../api/client';
import type { AgentSummary, BacktestResult, StrategyMeta } from '../types';
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer } from 'recharts';

const COMBINE_MODES = [
  { value: 'majority_vote', label: 'Majority vote' },
  { value: 'weighted_vote', label: 'Weighted vote' },
  { value: 'unanimous', label: 'Unanimous' },
  { value: 'confidence_weighted', label: 'Confidence-weighted' },
];

export function BacktestView() {
  const [strategies, setStrategies] = useState<StrategyMeta[]>([]);
  const [datasets, setDatasets] = useState<any[]>([]);
  const [agents, setAgents] = useState<AgentSummary[]>([]);
  const [running, setRunning] = useState(false);
  const [result, setResult] = useState<BacktestResult | null>(null);
  const [error, setError] = useState('');

  // Data source
  const [dataSource, setDataSource] = useState<'synthetic' | 'yfinance' | 'csv'>('synthetic');
  const [csvKey, setCsvKey] = useState('');

  // Strategy config
  const [selectedStrategies, setSelectedStrategies] = useState<string[]>(['ma_crossover']);
  const [strategyParams, setStrategyParams] = useState<Record<string, Record<string, unknown>>>({});
  const [combineMode, setCombineMode] = useState('majority_vote');
  const [modelProvider, setModelProvider] = useState('no_model');

  // Market config
  const [symbol, setSymbol] = useState('EURUSD');
  const [timeframe, setTimeframe] = useState('H1');
  const [bars, setBars] = useState(3000);

  // Execution costs
  const [spreadPips, setSpreadPips] = useState(1.0);
  const [commission, setCommission] = useState(7.0);
  const [slippagePips, setSlippagePips] = useState(0.5);

  // Risk
  const [riskPerTrade, setRiskPerTrade] = useState(1.0);
  const [maxLotSize, setMaxLotSize] = useState(0.1);
  const [maxOpenPositions, setMaxOpenPositions] = useState(10);

  // Advanced
  const [showAdvanced, setShowAdvanced] = useState(false);
  const [walkForwardSplits, setWalkForwardSplits] = useState(1);
  const [initialBalance, setInitialBalance] = useState(10000);

  // CSV upload
  const fileInputRef = useRef<HTMLInputElement>(null);
  const [uploading, setUploading] = useState(false);

  useEffect(() => {
    api.getStrategies().then(setStrategies);
    api.getDatasets().then(setDatasets).catch(() => {});
    api.listAgents().then(setAgents).catch(() => {});
  }, []);

  const importAgent = async (agentId: string) => {
    if (!agentId) return;
    try {
      const agent = await api.getAgent(agentId);
      const cfg = agent.config;
      // Populate all fields from agent config
      setSymbol(cfg.symbols?.[0] || 'EURUSD');
      setTimeframe(cfg.timeframe || 'H1');
      setModelProvider(cfg.model_provider || 'no_model');
      setSelectedStrategies(cfg.strategies?.map((s: any) => s.name) || ['ma_crossover']);
      const params: Record<string, Record<string, unknown>> = {};
      for (const s of cfg.strategies || []) {
        if (s.params && Object.keys(s.params).length > 0) {
          params[s.name] = s.params;
        }
      }
      setStrategyParams(params);
      if (cfg.combiner?.mode) {
        setCombineMode(cfg.combiner.mode);
      }
      if (cfg.risk_profile) {
        setRiskPerTrade(cfg.risk_profile.max_risk_per_trade_pct ?? 1.0);
        setMaxLotSize(cfg.risk_profile.max_lot_size ?? 0.1);
        setMaxOpenPositions(cfg.risk_profile.max_open_positions ?? 10);
      }
    } catch (err: any) {
      setError(err.message || 'Failed to load agent config');
    }
  };

  const handleCsvUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;
    setUploading(true);
    setError('');
    try {
      const res = await api.uploadCsv(file, file.name.replace('.csv', ''), symbol, timeframe);
      setCsvKey(res.key);
      setDataSource('csv');
      const updated = await api.getDatasets();
      setDatasets(updated);
    } catch (err: any) {
      setError(err.message || 'Upload failed');
    }
    setUploading(false);
    if (fileInputRef.current) fileInputRef.current.value = '';
  };

  const toggleStrategy = (name: string) => {
    setSelectedStrategies((prev) =>
      prev.includes(name) ? prev.filter((s) => s !== name) : [...prev, name]
    );
  };

  const updateParam = (stratName: string, paramName: string, value: unknown) => {
    setStrategyParams((prev) => ({
      ...prev,
      [stratName]: { ...(prev[stratName] || {}), [paramName]: value },
    }));
  };

  const run = async () => {
    setError('');
    setRunning(true);
    setResult(null);
    try {
      let source = dataSource as string;
      if (dataSource === 'csv') source = `csv:${csvKey}`;

      const r = await api.runBacktest({
        agent_config: {
          name: 'Backtest',
          color: '#3498DB',
          symbols: [symbol],
          timeframe,
          model_provider: modelProvider,
          model_config: {},
          strategies: selectedStrategies.map((sn) => ({
            name: sn,
            params: strategyParams[sn] || {},
          })),
          combiner: selectedStrategies.length > 1 ? { mode: combineMode } : null,
          risk_profile: {
            max_risk_per_trade_pct: riskPerTrade,
            max_open_positions: maxOpenPositions,
            max_lot_size: maxLotSize,
            max_daily_loss_pct: 100,
          },
          schedule_seconds: 60,
          enabled: true,
        },
        symbol,
        timeframe,
        bars,
        walk_forward_splits: walkForwardSplits,
        spread_pips: spreadPips,
        commission_per_lot: commission,
        slippage_pips: slippagePips,
        initial_balance: initialBalance,
        data_source: source,
      });
      setResult(r);
    } catch (e: any) {
      setError(e.message || 'Backtest failed');
    }
    setRunning(false);
  };

  const equityCurve = result?.equity_curve.map((val, i) => ({ bar: i, equity: Math.round(val * 100) / 100 })) || [];

  return (
    <div className="space-y-6 max-w-5xl mx-auto">
      <h2 className="text-lg font-bold text-gray-200">Backtester</h2>

      {error && <div className="bg-red-900/30 border border-red-800 text-red-400 text-sm rounded-lg p-3">{error}</div>}

      {/* Import from Agent */}
      {agents.length > 0 && (
        <Section title="Import from Agent">
          <div className="flex gap-3 items-end">
            <div className="flex-1 space-y-1">
              <label className="text-xs text-gray-500">Select an existing agent to load its configuration</label>
              <select
                defaultValue=""
                onChange={(e) => { importAgent(e.target.value); e.target.value = ''; }}
                className="input-field"
              >
                <option value="" disabled>Choose an agent...</option>
                {agents.map((a) => (
                  <option key={a.id} value={a.id}>
                    {a.name} — {a.strategy} ({a.symbols.join(', ')} {a.timeframe})
                  </option>
                ))}
              </select>
            </div>
          </div>
          <p className="text-xs text-gray-600 mt-1">
            Imports strategy, symbol, timeframe, risk profile, and parameters. You can still adjust them below.
          </p>
        </Section>
      )}

      {/* Data Source */}
      <Section title="Data Source">
        <div className="flex gap-2 mb-3">
          {(['synthetic', 'yfinance', 'csv'] as const).map((src) => (
            <button
              key={src}
              onClick={() => setDataSource(src)}
              className={`px-4 py-2 rounded-lg text-sm font-medium border ${
                dataSource === src
                  ? 'border-blue-500 bg-blue-500/10 text-blue-400'
                  : 'border-gray-700 bg-gray-800 text-gray-400 hover:border-gray-600'
              }`}
            >
              {src === 'synthetic' ? 'Synthetic' : src === 'yfinance' ? 'Yahoo Finance' : 'CSV Upload'}
            </button>
          ))}
        </div>

        {dataSource === 'yfinance' && (
          <p className="text-xs text-green-400/70 mb-2">
            Real market data from Yahoo Finance. Forex pairs, stocks, crypto supported.
          </p>
        )}

        {dataSource === 'csv' && (
          <div className="space-y-2">
            <div className="flex gap-2 items-center">
              <input
                ref={fileInputRef}
                type="file"
                accept=".csv"
                onChange={handleCsvUpload}
                className="text-sm text-gray-400 file:mr-3 file:py-1.5 file:px-3 file:rounded-lg file:border file:border-gray-600 file:bg-gray-800 file:text-gray-300 file:text-sm hover:file:bg-gray-700"
              />
              {uploading && <span className="text-xs text-gray-500">Uploading...</span>}
            </div>
            {datasets.length > 0 && (
              <select
                value={csvKey}
                onChange={(e) => setCsvKey(e.target.value)}
                className="input-field"
              >
                <option value="">Select a dataset...</option>
                {datasets.map((d) => (
                  <option key={d.key} value={d.key}>
                    {d.name} ({d.symbol} {d.timeframe}, {d.bars} bars)
                  </option>
                ))}
              </select>
            )}
            <p className="text-xs text-gray-500">
              CSV must have columns: time (or date/datetime), open, high, low, close, volume
            </p>
          </div>
        )}

        <div className="grid grid-cols-2 md:grid-cols-3 gap-3 mt-3">
          <Field label="Symbol">
            <input value={symbol} onChange={(e) => setSymbol(e.target.value)} className="input-field font-mono" />
          </Field>
          <Field label="Timeframe">
            <select value={timeframe} onChange={(e) => setTimeframe(e.target.value)} className="input-field">
              {['M1', 'M5', 'M15', 'M30', 'H1', 'H4', 'D1', 'W1'].map((t) => <option key={t}>{t}</option>)}
            </select>
          </Field>
          {dataSource === 'synthetic' && (
            <Field label="Bars">
              <input type="number" value={bars} onChange={(e) => setBars(+e.target.value)} min={200} max={50000} className="input-field" />
            </Field>
          )}
        </div>
      </Section>

      {/* Strategies */}
      <Section title="Strategy">
        <div className="space-y-2">
          {strategies.map((strat) => (
            <div key={strat.name} className={`rounded-lg border p-3 ${
              selectedStrategies.includes(strat.name)
                ? 'border-blue-500 bg-blue-500/5'
                : 'border-gray-700 bg-gray-800/50'
            }`}>
              <label className="flex items-start gap-3 cursor-pointer">
                <input
                  type="checkbox"
                  checked={selectedStrategies.includes(strat.name)}
                  onChange={() => toggleStrategy(strat.name)}
                  className="mt-1"
                />
                <div className="flex-1">
                  <div className="font-semibold text-sm text-gray-200">{strat.name}</div>
                  <div className="text-xs text-gray-500 mt-0.5">{strat.description}</div>
                </div>
              </label>

              {selectedStrategies.includes(strat.name) && strat.parameters.length > 0 && (
                <div className="mt-3 pl-7 grid grid-cols-2 md:grid-cols-3 gap-2">
                  {strat.parameters.map((param) => (
                    <div key={param.name}>
                      <label className="text-xs text-gray-500">{param.label}</label>
                      {param.type === 'select' ? (
                        <select
                          value={String(strategyParams[strat.name]?.[param.name] ?? param.default)}
                          onChange={(e) => updateParam(strat.name, param.name, e.target.value)}
                          className="input-field text-sm"
                        >
                          {param.options?.map((o) => <option key={o} value={o}>{o}</option>)}
                        </select>
                      ) : param.type === 'bool' ? (
                        <input
                          type="checkbox"
                          checked={Boolean(strategyParams[strat.name]?.[param.name] ?? param.default)}
                          onChange={(e) => updateParam(strat.name, param.name, e.target.checked)}
                        />
                      ) : (
                        <input
                          type="number"
                          value={Number(strategyParams[strat.name]?.[param.name] ?? param.default)}
                          onChange={(e) => updateParam(strat.name, param.name, +e.target.value)}
                          min={param.min}
                          max={param.max}
                          step={param.step}
                          className="input-field text-sm"
                        />
                      )}
                    </div>
                  ))}
                </div>
              )}
            </div>
          ))}
        </div>

        {selectedStrategies.length > 1 && (
          <div className="mt-3">
            <Field label="Combination Mode">
              <select value={combineMode} onChange={(e) => setCombineMode(e.target.value)} className="input-field">
                {COMBINE_MODES.map((m) => (
                  <option key={m.value} value={m.value}>{m.label}</option>
                ))}
              </select>
            </Field>
          </div>
        )}
      </Section>

      {/* Execution Costs */}
      <Section title="Execution Costs">
        <div className="grid grid-cols-3 gap-4">
          <Field label="Spread (pips)">
            <input type="number" value={spreadPips} onChange={(e) => setSpreadPips(+e.target.value)} min={0} max={20} step={0.1} className="input-field" />
          </Field>
          <Field label="Commission ($/lot)">
            <input type="number" value={commission} onChange={(e) => setCommission(+e.target.value)} min={0} max={50} step={0.5} className="input-field" />
          </Field>
          <Field label="Slippage (pips)">
            <input type="number" value={slippagePips} onChange={(e) => setSlippagePips(+e.target.value)} min={0} max={10} step={0.1} className="input-field" />
          </Field>
        </div>
      </Section>

      {/* Risk Profile */}
      <Section title="Risk Profile">
        <div className="grid grid-cols-3 gap-4">
          <Field label="Max risk per trade (%)">
            <input type="number" value={riskPerTrade} onChange={(e) => setRiskPerTrade(+e.target.value)} min={0.1} max={10} step={0.1} className="input-field" />
          </Field>
          <Field label="Max lot size">
            <input type="number" value={maxLotSize} onChange={(e) => setMaxLotSize(+e.target.value)} min={0.01} max={10} step={0.01} className="input-field" />
          </Field>
          <Field label="Max open positions">
            <input type="number" value={maxOpenPositions} onChange={(e) => setMaxOpenPositions(+e.target.value)} min={1} max={50} step={1} className="input-field" />
          </Field>
        </div>
      </Section>

      {/* Advanced */}
      <div>
        <button
          onClick={() => setShowAdvanced(!showAdvanced)}
          className="text-xs text-gray-500 hover:text-gray-300 mb-2"
        >
          {showAdvanced ? '- Hide' : '+ Show'} Advanced
        </button>
        {showAdvanced && (
          <Section title="Advanced">
            <div className="grid grid-cols-2 gap-4">
              <Field label="Walk-forward splits">
                <input type="number" value={walkForwardSplits} onChange={(e) => setWalkForwardSplits(+e.target.value)} min={1} max={10} className="input-field" />
              </Field>
              <Field label="Initial balance ($)">
                <input type="number" value={initialBalance} onChange={(e) => setInitialBalance(+e.target.value)} min={100} max={1000000} step={1000} className="input-field" />
              </Field>
            </div>
          </Section>
        )}
      </div>

      {/* Run button */}
      <button
        onClick={run}
        disabled={running || selectedStrategies.length === 0 || (dataSource === 'csv' && !csvKey)}
        className="w-full py-3 bg-purple-600 hover:bg-purple-500 disabled:bg-gray-700 disabled:text-gray-500 text-white font-semibold rounded-xl transition-colors"
      >
        {running ? 'Running Backtest...' : 'Run Backtest'}
      </button>

      {/* Results */}
      {result && (
        <div className="space-y-4">
          {/* Info bar */}
          <div className="text-xs text-gray-500">
            Data: {result.data_source || 'synthetic'} | Bars used: {result.bars_used || '?'}
          </div>

          {/* Metrics */}
          <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
            <MetricCard label="Total Return" value={`${result.total_return_pct.toFixed(2)}%`}
              color={result.total_return_pct >= 0 ? 'text-green-400' : 'text-red-400'} />
            <MetricCard label="Sharpe Ratio" value={result.sharpe_ratio.toFixed(2)}
              color={result.sharpe_ratio >= 1 ? 'text-green-400' : result.sharpe_ratio >= 0 ? 'text-yellow-400' : 'text-red-400'} />
            <MetricCard label="Sortino Ratio" value={result.sortino_ratio.toFixed(2)} />
            <MetricCard label="Max Drawdown" value={`${result.max_drawdown_pct.toFixed(2)}%`} color="text-red-400" />
            <MetricCard label="Win Rate" value={`${(result.win_rate * 100).toFixed(1)}%`}
              color={result.win_rate >= 0.5 ? 'text-green-400' : 'text-yellow-400'} />
            <MetricCard label="Profit Factor" value={result.profit_factor.toFixed(2)}
              color={result.profit_factor >= 1.5 ? 'text-green-400' : result.profit_factor >= 1 ? 'text-yellow-400' : 'text-red-400'} />
            <MetricCard label="Total Trades" value={String(result.total_trades)} />
            <MetricCard label="Final Equity" value={`$${result.equity_curve[result.equity_curve.length - 1]?.toFixed(0) || '?'}`}
              color={result.total_return_pct >= 0 ? 'text-green-400' : 'text-red-400'} />
          </div>

          {/* Equity curve */}
          {equityCurve.length > 0 && (
            <div className="bg-gray-900 border border-gray-800 rounded-xl p-4">
              <h3 className="text-sm font-semibold text-gray-400 mb-4">Equity Curve</h3>
              <ResponsiveContainer width="100%" height={300}>
                <LineChart data={equityCurve}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#1f2937" />
                  <XAxis dataKey="bar" stroke="#6b7280" />
                  <YAxis stroke="#6b7280" domain={['auto', 'auto']} />
                  <Tooltip
                    contentStyle={{ backgroundColor: '#1f2937', border: '1px solid #374151', borderRadius: 8 }}
                    labelStyle={{ color: '#9ca3af' }}
                    formatter={(value: number) => [`$${value.toFixed(2)}`, 'Equity']}
                  />
                  <Line type="monotone" dataKey="equity" stroke="#3b82f6" dot={false} strokeWidth={2} />
                </LineChart>
              </ResponsiveContainer>
            </div>
          )}

          {/* Trade list */}
          {result.trades.length > 0 && (
            <div className="bg-gray-900 border border-gray-800 rounded-xl p-4">
              <h3 className="text-sm font-semibold text-gray-400 mb-3">
                Trade Log ({result.trades.length} trades)
              </h3>
              <div className="overflow-x-auto max-h-80 overflow-y-auto">
                <table className="w-full text-xs text-gray-400">
                  <thead className="sticky top-0 bg-gray-900">
                    <tr className="border-b border-gray-700 text-left">
                      <th className="py-1.5 px-2">#</th>
                      <th className="py-1.5 px-2">Dir</th>
                      <th className="py-1.5 px-2">Entry Bar</th>
                      <th className="py-1.5 px-2">Exit Bar</th>
                      <th className="py-1.5 px-2">Entry Price</th>
                      <th className="py-1.5 px-2">Exit Price</th>
                      <th className="py-1.5 px-2">Lots</th>
                      <th className="py-1.5 px-2">PnL</th>
                      <th className="py-1.5 px-2">Exit</th>
                    </tr>
                  </thead>
                  <tbody>
                    {result.trades.map((t: any, i: number) => (
                      <tr key={i} className="border-b border-gray-800 hover:bg-gray-800/50">
                        <td className="py-1 px-2 text-gray-500">{i + 1}</td>
                        <td className={`py-1 px-2 font-medium ${t.direction === 'BUY' ? 'text-green-400' : 'text-red-400'}`}>
                          {t.direction}
                        </td>
                        <td className="py-1 px-2">{t.entry_bar}</td>
                        <td className="py-1 px-2">{t.exit_bar}</td>
                        <td className="py-1 px-2 font-mono">{t.entry_price?.toFixed(5)}</td>
                        <td className="py-1 px-2 font-mono">{t.exit_price?.toFixed(5)}</td>
                        <td className="py-1 px-2">{t.lot_size}</td>
                        <td className={`py-1 px-2 font-mono font-medium ${t.pnl >= 0 ? 'text-green-400' : 'text-red-400'}`}>
                          {t.pnl >= 0 ? '+' : ''}{t.pnl?.toFixed(2)}
                        </td>
                        <td className="py-1 px-2">
                          <span className={`px-1.5 py-0.5 rounded text-[10px] ${
                            t.exit_reason === 'tp' ? 'bg-green-900/30 text-green-400' :
                            t.exit_reason === 'sl' ? 'bg-red-900/30 text-red-400' :
                            'bg-gray-800 text-gray-500'
                          }`}>
                            {t.exit_reason?.toUpperCase()}
                          </span>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div className="bg-gray-900 border border-gray-800 rounded-xl p-4 space-y-3">
      <h3 className="text-sm font-semibold text-gray-400 uppercase tracking-wider">{title}</h3>
      {children}
    </div>
  );
}

function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="space-y-1">
      <label className="text-xs text-gray-500">{label}</label>
      {children}
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
