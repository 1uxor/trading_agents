import { useState } from 'react';
import { api } from '../api/client';
import type { AgentConfig } from '../types';

interface Preset {
  name: string;
  description: string;
  ictConcepts: string[];
  riskLevel: 'Low' | 'Medium' | 'High';
  config: AgentConfig;
}

const PRESETS: Preset[] = [
  {
    name: 'ICT Smart Money Scalper',
    description:
      'Combines EMA crossover for trend direction with RSI for optimal entry timing. Buys when fast EMA crosses above slow EMA and RSI confirms the move is not overbought.',
    ictConcepts: ['Institutional Order Flow', 'Optimal Trade Entry (OTE)', 'Confluence'],
    riskLevel: 'Medium',
    config: {
      name: 'ICT Smart Money Scalper',
      color: '#2ECC71',
      symbols: ['EURUSD', 'GBPUSD'],
      timeframe: 'M15',
      model_provider: 'no_model',
      model_config: {},
      strategies: [
        { name: 'ma_crossover', params: { fast_period: 9, slow_period: 21, ma_type: 'EMA' } },
        { name: 'rsi_reversion', params: { rsi_period: 14, oversold: 30, overbought: 70 } },
      ],
      combiner: { mode: 'confidence_weighted' },
      risk_profile: { max_risk_per_trade_pct: 1.0, max_open_positions: 2, max_lot_size: 0.05, max_daily_loss_pct: 3.0 },
      schedule_seconds: 60,
      enabled: true,
    },
  },
  {
    name: 'ICT Breakout Sniper',
    description:
      'Watches Donchian channel breakouts confirmed by MA trend. When price breaks above the channel and the trend is bullish, it enters. Similar to ICT liquidity sweep concept.',
    ictConcepts: ['Liquidity Sweep', 'Market Structure Shift', 'Institutional Bias'],
    riskLevel: 'Medium',
    config: {
      name: 'ICT Breakout Sniper',
      color: '#E74C3C',
      symbols: ['EURUSD', 'USDJPY'],
      timeframe: 'H1',
      model_provider: 'no_model',
      model_config: {},
      strategies: [
        { name: 'breakout', params: { channel_period: 20, atr_period: 14 } },
        { name: 'ma_crossover', params: { fast_period: 20, slow_period: 50, ma_type: 'SMA' } },
      ],
      combiner: { mode: 'filter_chain', filter_roles: { ma_crossover: 'filter', breakout: 'entry' } },
      risk_profile: { max_risk_per_trade_pct: 1.5, max_open_positions: 3, max_lot_size: 0.1, max_daily_loss_pct: 4.0 },
      schedule_seconds: 60,
      enabled: true,
    },
  },
  {
    name: 'ICT Trend Follower',
    description:
      'Uses the classic 50/200 SMA golden cross & death cross. When the 50 crosses above 200, it signals institutional long-term bullish bias. Very conservative, few trades.',
    ictConcepts: ['Institutional Long-Term Bias', 'Higher Timeframe Confluence', 'Premium/Discount Zone'],
    riskLevel: 'Low',
    config: {
      name: 'ICT Trend Follower',
      color: '#3498DB',
      symbols: ['EURUSD', 'GBPUSD', 'USDJPY'],
      timeframe: 'H4',
      model_provider: 'no_model',
      model_config: {},
      strategies: [
        { name: 'ma_crossover', params: { fast_period: 50, slow_period: 200, ma_type: 'SMA' } },
      ],
      risk_profile: { max_risk_per_trade_pct: 0.5, max_open_positions: 2, max_lot_size: 0.05, max_daily_loss_pct: 2.0 },
      schedule_seconds: 120,
      enabled: true,
    },
  },
  {
    name: 'ICT AI Discretionary',
    description:
      'Uses an AI model (Gemini) to analyze price action, support/resistance, and market structure. The AI decides whether to buy, sell, or hold — similar to ICT discretionary analysis.',
    ictConcepts: ['Discretionary Analysis', 'Price Action', 'Smart Money Concepts'],
    riskLevel: 'High',
    config: {
      name: 'ICT AI Discretionary',
      color: '#9B59B6',
      symbols: ['EURUSD'],
      timeframe: 'H1',
      model_provider: 'gemini',
      model_config: { model_name: 'gemini-2.0-flash' },
      strategies: [
        { name: 'llm_discretionary', params: {} },
      ],
      risk_profile: { max_risk_per_trade_pct: 1.0, max_open_positions: 2, max_lot_size: 0.1, max_daily_loss_pct: 3.0 },
      schedule_seconds: 60,
      enabled: true,
    },
  },
  {
    name: 'ICT Mean Reversion',
    description:
      'Short-period RSI catches overextended moves (liquidity grabs). When RSI drops below 25, it buys the reversal. When above 75, it sells. Inspired by ICT "judas swing" concept.',
    ictConcepts: ['Judas Swing', 'Liquidity Grab', 'Stop Hunt Reversal'],
    riskLevel: 'Medium',
    config: {
      name: 'ICT Mean Reversion',
      color: '#F1C40F',
      symbols: ['EURUSD', 'GBPUSD'],
      timeframe: 'M15',
      model_provider: 'no_model',
      model_config: {},
      strategies: [
        { name: 'rsi_reversion', params: { rsi_period: 7, oversold: 25, overbought: 75 } },
      ],
      risk_profile: { max_risk_per_trade_pct: 1.0, max_open_positions: 3, max_lot_size: 0.05, max_daily_loss_pct: 3.0 },
      schedule_seconds: 60,
      enabled: true,
    },
  },
  {
    name: 'ICT Forecast Trader',
    description:
      'Uses an AI model to forecast future price direction. If the forecast is up, it buys. If down, it sells. Similar to ICT weekly/daily bias analysis but automated with machine learning.',
    ictConcepts: ['Weekly/Daily Bias', 'Directional Bias', 'Time-Based Analysis'],
    riskLevel: 'Medium',
    config: {
      name: 'ICT Forecast Trader',
      color: '#00CEC9',
      symbols: ['EURUSD'],
      timeframe: 'H1',
      model_provider: 'hf_forecaster',
      model_config: {},
      strategies: [
        { name: 'forecast_driven', params: {} },
      ],
      risk_profile: { max_risk_per_trade_pct: 1.0, max_open_positions: 2, max_lot_size: 0.1, max_daily_loss_pct: 3.0 },
      schedule_seconds: 60,
      enabled: true,
    },
  },
];

const RISK_COLORS = {
  Low: 'bg-green-500/20 text-green-400 border-green-500/30',
  Medium: 'bg-yellow-500/20 text-yellow-400 border-yellow-500/30',
  High: 'bg-red-500/20 text-red-400 border-red-500/30',
};

interface Props {
  onNavigate: (page: string) => void;
}

export function StrategyPresets({ onNavigate }: Props) {
  const [adding, setAdding] = useState<string | null>(null);
  const [added, setAdded] = useState<Set<string>>(new Set());
  const [error, setError] = useState('');

  const handleAdd = async (preset: Preset) => {
    setAdding(preset.name);
    setError('');
    try {
      await api.createAgent(preset.config);
      setAdded((prev) => new Set(prev).add(preset.name));
      setTimeout(() => onNavigate('dashboard'), 1000);
    } catch (e: any) {
      setError(e.message || 'Failed to create agent');
    } finally {
      setAdding(null);
    }
  };

  return (
    <div>
      <div className="mb-6">
        <h2 className="text-2xl font-bold text-white mb-1">ICT Strategy Presets</h2>
        <p className="text-gray-400 text-sm">
          Pre-configured trading agents based on ICT (Inner Circle Trader) concepts. Click "Add Agent" to deploy one instantly.
        </p>
      </div>

      {error && (
        <div className="mb-4 p-3 bg-red-500/10 border border-red-500/30 rounded-lg text-red-400 text-sm">
          {error}
        </div>
      )}

      <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4">
        {PRESETS.map((preset) => (
          <div
            key={preset.name}
            className="bg-gray-900 border border-gray-800 rounded-xl p-5 hover:border-gray-700 transition-colors flex flex-col"
          >
            {/* Header */}
            <div className="flex items-start justify-between mb-3">
              <div className="flex items-center gap-2">
                <div className="w-3 h-3 rounded-full" style={{ backgroundColor: preset.config.color }} />
                <h3 className="font-semibold text-white text-sm">{preset.name}</h3>
              </div>
              <span className={`text-[10px] px-2 py-0.5 rounded-full border ${RISK_COLORS[preset.riskLevel]}`}>
                {preset.riskLevel} Risk
              </span>
            </div>

            {/* Description */}
            <p className="text-gray-400 text-xs leading-relaxed mb-3 flex-1">{preset.description}</p>

            {/* ICT Concepts */}
            <div className="flex flex-wrap gap-1 mb-3">
              {preset.ictConcepts.map((c) => (
                <span key={c} className="text-[10px] px-1.5 py-0.5 rounded bg-purple-500/10 text-purple-400 border border-purple-500/20">
                  {c}
                </span>
              ))}
            </div>

            {/* Config summary */}
            <div className="grid grid-cols-2 gap-2 mb-4 text-[11px]">
              <div className="bg-gray-800/50 rounded-lg px-2 py-1.5">
                <span className="text-gray-500">Pairs: </span>
                <span className="text-gray-300">{preset.config.symbols.join(', ')}</span>
              </div>
              <div className="bg-gray-800/50 rounded-lg px-2 py-1.5">
                <span className="text-gray-500">Timeframe: </span>
                <span className="text-gray-300">{preset.config.timeframe}</span>
              </div>
              <div className="bg-gray-800/50 rounded-lg px-2 py-1.5">
                <span className="text-gray-500">Risk/trade: </span>
                <span className="text-gray-300">{preset.config.risk_profile.max_risk_per_trade_pct}%</span>
              </div>
              <div className="bg-gray-800/50 rounded-lg px-2 py-1.5">
                <span className="text-gray-500">Max lots: </span>
                <span className="text-gray-300">{preset.config.risk_profile.max_lot_size}</span>
              </div>
              <div className="bg-gray-800/50 rounded-lg px-2 py-1.5">
                <span className="text-gray-500">Strategy: </span>
                <span className="text-gray-300">{preset.config.strategies.map((s) => s.name).join(' + ')}</span>
              </div>
              <div className="bg-gray-800/50 rounded-lg px-2 py-1.5">
                <span className="text-gray-500">Model: </span>
                <span className="text-gray-300">{preset.config.model_provider}</span>
              </div>
            </div>

            {/* Add button */}
            <button
              onClick={() => handleAdd(preset)}
              disabled={adding !== null || added.has(preset.name)}
              className={`w-full py-2 rounded-lg text-sm font-medium transition-colors ${
                added.has(preset.name)
                  ? 'bg-green-500/20 text-green-400 border border-green-500/30 cursor-default'
                  : adding === preset.name
                  ? 'bg-blue-500/20 text-blue-400 border border-blue-500/30 cursor-wait'
                  : 'bg-blue-600 hover:bg-blue-500 text-white cursor-pointer'
              }`}
            >
              {added.has(preset.name) ? 'Added!' : adding === preset.name ? 'Creating...' : 'Add Agent'}
            </button>
          </div>
        ))}
      </div>
    </div>
  );
}
