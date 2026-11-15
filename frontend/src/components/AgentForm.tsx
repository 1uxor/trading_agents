import { useState, useEffect } from 'react';
import { api } from '../api/client';
import type { StrategyMeta, ParameterSpec, AgentConfig } from '../types';

interface Props {
  onCreated: () => void;
}

const AGENT_COLORS = [
  '#E74C3C', '#3498DB', '#2ECC71', '#F1C40F', '#9B59B6',
  '#E67E22', '#1ABC9C', '#E84393', '#00CEC9', '#6C5CE7',
];

const COMBINE_MODES = [
  { value: '', label: 'Single strategy (no combiner)' },
  { value: 'majority_vote', label: 'Majority vote' },
  { value: 'weighted_vote', label: 'Weighted vote' },
  { value: 'unanimous', label: 'Unanimous' },
  { value: 'filter_chain', label: 'Filter chain' },
  { value: 'confidence_weighted', label: 'Confidence-weighted average' },
];

export function AgentForm({ onCreated }: Props) {
  const [strategies, setStrategies] = useState<StrategyMeta[]>([]);
  const [providers, setProviders] = useState<{ name: string; license: string }[]>([]);
  const [timeframes, setTimeframes] = useState<string[]>([]);

  const [name, setName] = useState('New Agent');
  const [color, setColor] = useState(AGENT_COLORS[Math.floor(Math.random() * AGENT_COLORS.length)]);
  const [symbols, setSymbols] = useState('EURUSD');
  const [timeframe, setTimeframe] = useState('H1');
  const [modelProvider, setModelProvider] = useState('no_model');
  const [selectedStrategies, setSelectedStrategies] = useState<string[]>(['ma_crossover']);
  const [strategyParams, setStrategyParams] = useState<Record<string, Record<string, unknown>>>({});
  const [combineMode, setCombineMode] = useState('');
  const [scheduleSeconds, setScheduleSeconds] = useState(60);
  const [riskPerTrade, setRiskPerTrade] = useState(1.0);
  const [maxPositions, setMaxPositions] = useState(3);
  const [maxLotSize, setMaxLotSize] = useState(0.1);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState('');

  useEffect(() => {
    Promise.all([api.getStrategies(), api.getModelProviders(), api.getTimeframes()]).then(
      ([s, p, t]) => {
        setStrategies(s);
        setProviders(p);
        setTimeframes(t);
      }
    );
  }, []);

  const handleSubmit = async () => {
    setError('');
    setSubmitting(true);
    try {
      const config: AgentConfig = {
        name,
        color,
        symbols: symbols.split(',').map((s) => s.trim()),
        timeframe,
        model_provider: modelProvider,
        model_config: {},
        strategies: selectedStrategies.map((sn) => ({
          name: sn,
          params: strategyParams[sn] || {},
        })),
        combiner: combineMode ? { mode: combineMode as any } : null,
        risk_profile: {
          max_risk_per_trade_pct: riskPerTrade,
          max_open_positions: maxPositions,
          max_lot_size: maxLotSize,
          max_daily_loss_pct: 5.0,
        },
        schedule_seconds: scheduleSeconds,
        enabled: true,
      };
      await api.createAgent(config);
      onCreated();
    } catch (e: any) {
      setError(e.message || 'Failed to create agent');
    }
    setSubmitting(false);
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

  return (
    <div className="max-w-2xl mx-auto space-y-6">
      <h2 className="text-lg font-bold text-gray-200">Create New Agent</h2>

      {error && (
        <div className="bg-red-900/30 border border-red-800 text-red-400 text-sm rounded-lg p-3">{error}</div>
      )}

      {/* Basic info */}
      <Section title="Identity">
        <Field label="Name">
          <input value={name} onChange={(e) => setName(e.target.value)} className="input-field" />
        </Field>
        <Field label="Color">
          <div className="flex gap-2">
            {AGENT_COLORS.map((c) => (
              <button
                key={c}
                onClick={() => setColor(c)}
                className={`w-8 h-8 rounded-full border-2 ${color === c ? 'border-white' : 'border-transparent'}`}
                style={{ backgroundColor: c }}
              />
            ))}
          </div>
        </Field>
        <Field label="Symbols (comma-separated)">
          <input value={symbols} onChange={(e) => setSymbols(e.target.value)} className="input-field font-mono" />
        </Field>
        <Field label="Timeframe">
          <select value={timeframe} onChange={(e) => setTimeframe(e.target.value)} className="input-field">
            {timeframes.map((t) => (
              <option key={t} value={t}>{t}</option>
            ))}
          </select>
        </Field>
        <Field label="Check interval (seconds)">
          <input type="number" value={scheduleSeconds} onChange={(e) => setScheduleSeconds(+e.target.value)} className="input-field" min={5} />
        </Field>
      </Section>

      {/* Model */}
      <Section title="Model Provider">
        <div className="grid grid-cols-2 gap-2">
          {providers.map((p) => (
            <button
              key={p.name}
              onClick={() => setModelProvider(p.name)}
              className={`p-3 rounded-lg border text-left text-sm ${
                modelProvider === p.name
                  ? 'border-blue-500 bg-blue-500/10 text-blue-400'
                  : 'border-gray-700 bg-gray-800 text-gray-400 hover:border-gray-600'
              }`}
            >
              <div className="font-semibold">{p.name}</div>
              {p.license && <div className="text-xs text-gray-500 mt-1">License: {p.license}</div>}
            </button>
          ))}
        </div>
      </Section>

      {/* Strategies */}
      <Section title="Strategies">
        <div className="space-y-3">
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
                <div>
                  <div className="font-semibold text-sm text-gray-200">{strat.name}</div>
                  <div className="text-xs text-gray-500 mt-0.5">{strat.description}</div>
                </div>
              </label>

              {/* Parameters */}
              {selectedStrategies.includes(strat.name) && strat.parameters.length > 0 && (
                <div className="mt-3 pl-7 grid grid-cols-2 gap-2">
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

        {/* Combiner mode */}
        {selectedStrategies.length > 1 && (
          <Field label="Combination Mode">
            <select value={combineMode} onChange={(e) => setCombineMode(e.target.value)} className="input-field">
              {COMBINE_MODES.map((m) => (
                <option key={m.value} value={m.value}>{m.label}</option>
              ))}
            </select>
          </Field>
        )}
      </Section>

      {/* Risk */}
      <Section title="Risk Profile">
        <div className="grid grid-cols-3 gap-4">
          <Field label="Max risk/trade (%)">
            <input type="number" value={riskPerTrade} onChange={(e) => setRiskPerTrade(+e.target.value)} min={0.1} max={10} step={0.1} className="input-field" />
          </Field>
          <Field label="Max positions">
            <input type="number" value={maxPositions} onChange={(e) => setMaxPositions(+e.target.value)} min={1} max={20} className="input-field" />
          </Field>
          <Field label="Max lot size">
            <input type="number" value={maxLotSize} onChange={(e) => setMaxLotSize(+e.target.value)} min={0.01} max={10} step={0.01} className="input-field" />
          </Field>
        </div>
      </Section>

      <button
        onClick={handleSubmit}
        disabled={submitting || selectedStrategies.length === 0}
        className="w-full py-3 bg-blue-600 hover:bg-blue-500 disabled:bg-gray-700 disabled:text-gray-500 text-white font-semibold rounded-xl transition-colors"
      >
        {submitting ? 'Creating...' : 'Create Agent'}
      </button>
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
