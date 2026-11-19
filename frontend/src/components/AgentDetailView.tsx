import { useState, useEffect, useRef } from 'react';
import { api } from '../api/client';
import { AgentChart } from './AgentChart';
import type { AgentSummary, CommentaryEvent, Position, TradeRecord, SignalRecord, IndicatorSeries } from '../types';

interface Props {
  agentId: string;
  agents: AgentSummary[];
  events: CommentaryEvent[];
  positions: Position[];
}

export function AgentDetailView({ agentId, agents, events, positions }: Props) {
  const [agentConfig, setAgentConfig] = useState<any>(null);
  const [trades, setTrades] = useState<TradeRecord[]>([]);
  const [signals, setSignals] = useState<SignalRecord[]>([]);
  const [indicators, setIndicators] = useState<IndicatorSeries[]>([]);
  const [activeTab, setActiveTab] = useState<'trades' | 'signals' | 'commentary'>('trades');

  const agent = agents.find((a) => a.id === agentId);
  const agentEvents = events.filter((e) => e.agent_id === agentId);
  const agentPositions = positions.filter((p) => p.agent_id === agentId);
  const agentProfit = agentPositions.reduce((s, p) => s + p.profit, 0);

  useEffect(() => {
    let cancelled = false;

    async function load() {
      try {
        const [cfg, t, s] = await Promise.all([
          api.getAgent(agentId),
          api.getAgentTrades(agentId),
          api.getAgentSignals(agentId),
        ]);
        if (cancelled) return;
        setAgentConfig(cfg);
        setTrades(t);
        setSignals(s);

        // Fetch indicators
        if (cfg.config?.symbols?.length) {
          const ind = await api.getAgentIndicators(
            agentId, cfg.config.symbols[0], cfg.config.timeframe || 'H1'
          );
          if (!cancelled) setIndicators(ind.indicators || []);
        }
      } catch (e) {
        console.error('AgentDetailView load error:', e);
      }
    }

    load();
    const interval = setInterval(load, 15000);
    return () => { cancelled = true; clearInterval(interval); };
  }, [agentId]);

  if (!agent) {
    return <div className="text-gray-500 text-center py-12">Agent not found</div>;
  }

  const config = agentConfig?.config;
  const riskProfile = config?.risk_profile;

  return (
    <div className="space-y-4">
      {/* Agent Info Header */}
      <div className="bg-gray-900 border border-gray-800 rounded-xl p-4" style={{ borderLeftColor: agent.color, borderLeftWidth: 4 }}>
        <div className="flex items-center justify-between mb-2">
          <div className="flex items-center gap-3">
            <span className={`status-dot ${agent.state}`} />
            <h2 className="text-lg font-bold" style={{ color: agent.color }}>{agent.name}</h2>
            <span className={`text-xs px-2 py-0.5 rounded-full ${
              agent.state === 'running' ? 'bg-green-500/20 text-green-400' :
              agent.state === 'paused' ? 'bg-yellow-500/20 text-yellow-400' :
              'bg-gray-500/20 text-gray-400'
            }`}>
              {agent.state.toUpperCase()}
            </span>
          </div>
          <div className="text-right">
            <div className="text-xs text-gray-500">Open P&L</div>
            <div className={`text-xl font-bold font-mono ${agentProfit >= 0 ? 'text-green-400' : 'text-red-400'}`}>
              ${agentProfit.toFixed(2)}
            </div>
          </div>
        </div>

        <div className="flex flex-wrap items-center gap-4 text-xs text-gray-400">
          <span className="font-mono">{agent.symbols.join(', ')}</span>
          <span>{agent.timeframe}</span>
          <span className="px-1.5 py-0.5 bg-gray-800 rounded text-gray-300">{agent.strategy}</span>
          <span className="text-gray-600">|</span>
          <span>Model: {agent.model || 'none'}</span>
          {riskProfile && (
            <>
              <span className="text-gray-600">|</span>
              <span>Risk: {riskProfile.max_risk_per_trade_pct}%/trade, max {riskProfile.max_open_positions} pos, {riskProfile.max_lot_size} lot</span>
            </>
          )}
        </div>

        {/* Open positions */}
        {agentPositions.length > 0 && (
          <div className="mt-3 border-t border-gray-800 pt-3">
            <div className="text-xs text-gray-500 mb-2">Open Positions</div>
            <div className="space-y-1">
              {agentPositions.map((pos) => (
                <div key={pos.ticket} className="flex items-center justify-between text-xs font-mono">
                  <div className="flex items-center gap-2">
                    <span className={pos.direction === 'BUY' ? 'text-green-400' : 'text-red-400'}>
                      {pos.direction}
                    </span>
                    <span className="text-gray-300">{pos.lot_size} lots @ {pos.open_price.toFixed(5)}</span>
                    <span className="text-gray-600">SL: {pos.sl.toFixed(5)}</span>
                    {pos.tp && <span className="text-gray-600">TP: {pos.tp.toFixed(5)}</span>}
                  </div>
                  <span className={pos.profit >= 0 ? 'text-green-400' : 'text-red-400'}>
                    {pos.profit >= 0 ? '+' : ''}{pos.profit.toFixed(2)}
                  </span>
                </div>
              ))}
            </div>
          </div>
        )}
      </div>

      {/* Chart + Explainer side by side */}
      <div className="flex gap-4">
        {/* Chart */}
        <div className="flex-1 min-w-0">
          <AgentChart
            symbol={agent.symbols[0] || 'EURUSD'}
            timeframe={agent.timeframe}
            agentId={agentId}
            agentColor={agent.color}
            agentName={agent.name}
            events={events}
            indicators={indicators}
          />
        </div>

        {/* Explainer panel */}
        <div className="w-[340px] flex-shrink-0 space-y-3">
          <StrategyExplainer
            strategyName={agent.strategy}
            agentEvents={agentEvents}
            signals={signals}
            riskProfile={riskProfile}
            agentColor={agent.color}
          />
        </div>
      </div>

      {/* Tabbed section: Trades / Signals / Commentary */}
      <div className="bg-gray-900 border border-gray-800 rounded-xl overflow-hidden">
        {/* Tab bar */}
        <div className="flex border-b border-gray-800">
          {(['trades', 'signals', 'commentary'] as const).map((tab) => (
            <button
              key={tab}
              onClick={() => setActiveTab(tab)}
              className={`px-4 py-2.5 text-sm font-medium transition-colors ${
                activeTab === tab
                  ? 'text-blue-400 border-b-2 border-blue-400 bg-blue-500/5'
                  : 'text-gray-500 hover:text-gray-300'
              }`}
            >
              {tab === 'trades' ? `Trades (${trades.length})` :
               tab === 'signals' ? `Signals (${signals.length})` :
               `Commentary (${agentEvents.length})`}
            </button>
          ))}
        </div>

        {/* Tab content */}
        <div className="max-h-[400px] overflow-y-auto">
          {activeTab === 'trades' && <TradesTable trades={trades} />}
          {activeTab === 'signals' && <SignalsTable signals={signals} />}
          {activeTab === 'commentary' && <CommentaryList events={agentEvents} />}
        </div>
      </div>
    </div>
  );
}


function TradesTable({ trades }: { trades: TradeRecord[] }) {
  if (trades.length === 0) {
    return <div className="text-center py-8 text-gray-600 text-sm">No trades yet</div>;
  }

  return (
    <table className="w-full text-xs">
      <thead className="bg-gray-800/50 sticky top-0">
        <tr className="text-gray-500 uppercase tracking-wider">
          <th className="px-3 py-2 text-left">Time</th>
          <th className="px-3 py-2 text-left">Dir</th>
          <th className="px-3 py-2 text-right">Entry</th>
          <th className="px-3 py-2 text-right">Exit</th>
          <th className="px-3 py-2 text-right">SL</th>
          <th className="px-3 py-2 text-right">TP</th>
          <th className="px-3 py-2 text-right">P&L</th>
          <th className="px-3 py-2 text-center">Status</th>
        </tr>
      </thead>
      <tbody className="font-mono">
        {trades.map((t) => (
          <tr key={t.id} className="border-t border-gray-800/50 hover:bg-gray-800/30">
            <td className="px-3 py-2 text-gray-400">
              {t.opened_at ? new Date(t.opened_at).toLocaleString([], { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' }) : '--'}
            </td>
            <td className={`px-3 py-2 font-bold ${t.direction === 'BUY' ? 'text-green-400' : 'text-red-400'}`}>
              {t.direction}
            </td>
            <td className="px-3 py-2 text-right text-gray-300">{t.entry_price?.toFixed(5) ?? '--'}</td>
            <td className="px-3 py-2 text-right text-gray-300">{t.exit_price?.toFixed(5) ?? '--'}</td>
            <td className="px-3 py-2 text-right text-gray-500">{t.sl?.toFixed(5) ?? '--'}</td>
            <td className="px-3 py-2 text-right text-gray-500">{t.tp?.toFixed(5) ?? '--'}</td>
            <td className={`px-3 py-2 text-right font-bold ${
              (t.profit ?? 0) >= 0 ? 'text-green-400' : 'text-red-400'
            }`}>
              {t.profit != null ? `${t.profit >= 0 ? '+' : ''}${t.profit.toFixed(2)}` : '--'}
            </td>
            <td className="px-3 py-2 text-center">
              <span className={`px-1.5 py-0.5 rounded text-[10px] ${
                t.status === 'open' ? 'bg-blue-500/20 text-blue-400' :
                t.status === 'closed' ? 'bg-gray-500/20 text-gray-400' :
                'bg-red-500/20 text-red-400'
              }`}>
                {t.status}
              </span>
            </td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}


function SignalsTable({ signals }: { signals: SignalRecord[] }) {
  if (signals.length === 0) {
    return <div className="text-center py-8 text-gray-600 text-sm">No signals yet</div>;
  }

  return (
    <table className="w-full text-xs">
      <thead className="bg-gray-800/50 sticky top-0">
        <tr className="text-gray-500 uppercase tracking-wider">
          <th className="px-3 py-2 text-left">Time</th>
          <th className="px-3 py-2 text-left">Signal</th>
          <th className="px-3 py-2 text-right">Conf</th>
          <th className="px-3 py-2 text-left">Strategy</th>
          <th className="px-3 py-2 text-left">Risk</th>
          <th className="px-3 py-2 text-left">Reasoning</th>
        </tr>
      </thead>
      <tbody className="font-mono">
        {signals.map((s) => (
          <tr key={s.id} className="border-t border-gray-800/50 hover:bg-gray-800/30">
            <td className="px-3 py-2 text-gray-400">
              {s.timestamp ? new Date(s.timestamp).toLocaleString([], { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' }) : '--'}
            </td>
            <td className={`px-3 py-2 font-bold ${
              s.signal === 'BUY' ? 'text-green-400' :
              s.signal === 'SELL' ? 'text-red-400' : 'text-gray-500'
            }`}>
              {s.signal}
            </td>
            <td className="px-3 py-2 text-right text-gray-300">
              {s.confidence != null ? `${(s.confidence * 100).toFixed(0)}%` : '--'}
            </td>
            <td className="px-3 py-2 text-gray-400">{s.strategy_name}</td>
            <td className="px-3 py-2">
              <span className={`px-1.5 py-0.5 rounded text-[10px] ${
                s.risk_check_result === 'approved' ? 'bg-green-500/20 text-green-400' :
                s.risk_check_result === 'rejected' ? 'bg-red-500/20 text-red-400' :
                'bg-gray-500/20 text-gray-500'
              }`}>
                {s.risk_check_result || 'skipped'}
              </span>
            </td>
            <td className="px-3 py-2 text-gray-500 max-w-[300px] truncate" title={s.reasoning || ''}>
              {s.reasoning || '--'}
            </td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}


// ── Strategy descriptions for beginners ──────────────────────────────────

const STRATEGY_INFO: Record<string, { title: string; description: string; howItWorks: string }> = {
  ma_crossover: {
    title: 'Moving Average Crossover',
    description: 'Follows the trend by watching two moving averages (fast & slow).',
    howItWorks: 'When the fast average crosses ABOVE the slow one, it means the price is trending up — the agent buys. When it crosses BELOW, the price is trending down — the agent sells. The bigger the gap between the two averages, the stronger the trend.',
  },
  rsi_reversion: {
    title: 'RSI Mean Reversion',
    description: 'Looks for overbought/oversold conditions to catch price reversals.',
    howItWorks: 'RSI measures how "tired" a price move is on a scale of 0-100. Below 30 = oversold (too cheap, likely to bounce up — agent buys). Above 70 = overbought (too expensive, likely to drop — agent sells). The more extreme the RSI, the more confident the signal.',
  },
  breakout: {
    title: 'Channel Breakout',
    description: 'Watches price channels and trades when price breaks out.',
    howItWorks: 'The agent tracks the highest high and lowest low over the last 20 candles (Donchian channel). When price breaks above the channel top, it signals strong upward momentum — agent buys. When it breaks below the bottom, it sells. Inside the channel, it gives weaker signals based on position.',
  },
  llm_discretionary: {
    title: 'AI Model Decision',
    description: 'An AI model analyzes the market and decides what to do.',
    howItWorks: 'The agent sends recent price data to an AI model (like a neural network or language model). The model returns a BUY, SELL, or HOLD signal with a confidence level. The agent only trades when the AI is confident enough. Think of it as asking an AI analyst for their opinion.',
  },
  forecast_driven: {
    title: 'AI Price Forecast',
    description: 'An AI model predicts the future price, and the agent trades accordingly.',
    howItWorks: 'The model forecasts where the price will be in the next candle. If the forecast is higher than current price by enough margin, the agent buys. If lower, it sells. The bigger the predicted move, the more confident the signal.',
  },
};

function getStrategyInfo(name: string) {
  // Handle combiner names like "confidence_weighted(ma_crossover,llm_discretionary)"
  const match = name.match(/^(\w+)\((.+)\)$/);
  if (match) {
    const mode = match[1];
    const subs = match[2].split(',');
    const modeLabels: Record<string, string> = {
      confidence_weighted: 'Confidence-Weighted Vote',
      majority_vote: 'Majority Vote',
      weighted_vote: 'Weighted Vote',
      unanimous: 'Unanimous Agreement',
      filter_chain: 'Filter Chain',
    };
    return {
      title: modeLabels[mode] || 'Multi-Strategy',
      description: `Combines ${subs.length} strategies: ${subs.map(s => STRATEGY_INFO[s]?.title || s).join(' + ')}.`,
      howItWorks: `Each strategy generates its own signal independently. Then they are combined using "${mode.replace(/_/g, ' ')}": the strategies vote and the final decision weighs each strategy by how confident it is. This reduces false signals because multiple approaches must agree.`,
      subs,
    };
  }
  return STRATEGY_INFO[name] || { title: name, description: 'Custom strategy.', howItWorks: '' };
}

function explainSignalForBeginner(signal: SignalRecord): string {
  const dir = signal.signal;
  const conf = signal.confidence != null ? Math.round(signal.confidence * 100) : 0;
  const strat = signal.strategy_name || '';
  const reasoning = signal.reasoning || '';

  let explanation = '';

  if (dir === 'BUY') {
    explanation = `The agent decided to BUY (go long) with ${conf}% confidence. `;
    explanation += 'This means it expects the price to go UP. ';
  } else if (dir === 'SELL') {
    explanation = `The agent decided to SELL (go short) with ${conf}% confidence. `;
    explanation += 'This means it expects the price to go DOWN. ';
  } else {
    explanation = `The agent decided to HOLD (do nothing) with ${conf}% confidence. `;
    explanation += "It didn't see a strong enough opportunity to trade. ";
  }

  if (signal.risk_check_result === 'approved') {
    explanation += 'The risk manager approved the trade.';
  } else if (signal.risk_check_result === 'rejected') {
    explanation += `The risk manager BLOCKED the trade: ${signal.risk_check_reason || 'too risky'}.`;
  }

  return explanation;
}


function StrategyExplainer({
  strategyName,
  agentEvents,
  signals,
  riskProfile,
  agentColor,
}: {
  strategyName: string;
  agentEvents: CommentaryEvent[];
  signals: SignalRecord[];
  riskProfile: any;
  agentColor: string;
}) {
  const info = getStrategyInfo(strategyName);
  const latestSignal = signals[0]; // signals are ordered desc
  const lastResult = [...agentEvents].reverse().find((e) => e.event === 'result');
  const lastSignalEvt = [...agentEvents].reverse().find((e) => e.event === 'signal');

  return (
    <>
      {/* Strategy explanation */}
      <div className="bg-gray-900 border border-gray-800 rounded-xl p-4">
        <div className="flex items-center gap-2 mb-2">
          <div className="w-2 h-2 rounded-full" style={{ backgroundColor: agentColor }} />
          <h3 className="text-sm font-semibold text-gray-200">Strategy: {info.title}</h3>
        </div>
        <p className="text-xs text-gray-400 mb-2">{info.description}</p>
        <div className="bg-gray-800/50 rounded-lg p-3">
          <div className="text-[10px] text-gray-500 uppercase tracking-wider mb-1">How it works</div>
          <p className="text-xs text-gray-300 leading-relaxed">{info.howItWorks}</p>
        </div>
      </div>

      {/* Latest signal explanation */}
      <div className="bg-gray-900 border border-gray-800 rounded-xl p-4">
        <h3 className="text-sm font-semibold text-gray-200 mb-2">Latest Decision</h3>
        {latestSignal ? (
          <div className="space-y-2">
            <div className="flex items-center gap-2">
              <span className={`text-lg font-bold ${
                latestSignal.signal === 'BUY' ? 'text-green-400' :
                latestSignal.signal === 'SELL' ? 'text-red-400' : 'text-gray-500'
              }`}>
                {latestSignal.signal}
              </span>
              {latestSignal.confidence != null && (
                <div className="flex-1">
                  <div className="flex items-center justify-between text-[10px] text-gray-500 mb-0.5">
                    <span>Confidence</span>
                    <span>{Math.round(latestSignal.confidence * 100)}%</span>
                  </div>
                  <div className="h-1.5 bg-gray-800 rounded-full overflow-hidden">
                    <div
                      className={`h-full rounded-full transition-all ${
                        latestSignal.confidence > 0.6 ? 'bg-green-500' :
                        latestSignal.confidence > 0.3 ? 'bg-yellow-500' : 'bg-gray-500'
                      }`}
                      style={{ width: `${Math.round(latestSignal.confidence * 100)}%` }}
                    />
                  </div>
                </div>
              )}
            </div>
            <p className="text-xs text-gray-300 leading-relaxed">
              {explainSignalForBeginner(latestSignal)}
            </p>
            {latestSignal.timestamp && (
              <div className="text-[10px] text-gray-600">
                {new Date(latestSignal.timestamp).toLocaleString()}
              </div>
            )}
          </div>
        ) : (
          <p className="text-xs text-gray-600 italic">No signals yet. Waiting for the next candle...</p>
        )}
      </div>

      {/* What happened */}
      {lastResult && (
        <div className="bg-gray-900 border border-gray-800 rounded-xl p-4">
          <h3 className="text-sm font-semibold text-gray-200 mb-2">What Happened</h3>
          <div className={`text-xs leading-relaxed ${
            lastResult.message.includes('filled') || lastResult.message.includes('Filled')
              ? 'text-green-400'
              : lastResult.message.includes('failed') || lastResult.message.includes('rejected')
              ? 'text-red-400'
              : 'text-gray-300'
          }`}>
            {lastResult.message.includes('Filled') || lastResult.message.includes('filled')
              ? `Trade executed successfully. ${lastResult.message}`
              : lastResult.message.includes('rejected')
              ? `Trade was blocked by the risk manager to protect your account. ${lastResult.message}`
              : lastResult.message.includes('failed')
              ? `Trade could not be placed. ${lastResult.message}`
              : lastResult.message
            }
          </div>
          <div className="text-[10px] text-gray-600 mt-1">
            {new Date(lastResult.timestamp).toLocaleTimeString()}
          </div>
        </div>
      )}

      {/* Risk profile */}
      {riskProfile && (
        <div className="bg-gray-900 border border-gray-800 rounded-xl p-4">
          <h3 className="text-sm font-semibold text-gray-200 mb-2">Risk Protection</h3>
          <div className="space-y-1.5 text-xs">
            <div className="flex justify-between">
              <span className="text-gray-500">Max risk per trade</span>
              <span className="text-gray-300">{riskProfile.max_risk_per_trade_pct}% of account</span>
            </div>
            <div className="flex justify-between">
              <span className="text-gray-500">Max open positions</span>
              <span className="text-gray-300">{riskProfile.max_open_positions} at once</span>
            </div>
            <div className="flex justify-between">
              <span className="text-gray-500">Max lot size</span>
              <span className="text-gray-300">{riskProfile.max_lot_size} lots</span>
            </div>
            <div className="flex justify-between">
              <span className="text-gray-500">Max daily loss</span>
              <span className="text-gray-300">{riskProfile.max_daily_loss_pct}% — stops all trading</span>
            </div>
          </div>
          <p className="text-[10px] text-gray-600 mt-2">
            These limits protect your account. If any limit is hit, the agent stops trading until conditions improve.
          </p>
        </div>
      )}
    </>
  );
}


function CommentaryList({ events }: { events: CommentaryEvent[] }) {
  const reversed = [...events].reverse();

  if (reversed.length === 0) {
    return <div className="text-center py-8 text-gray-600 text-sm">No commentary yet</div>;
  }

  const eventColor: Record<string, string> = {
    thinking: 'text-yellow-400',
    signal: 'text-blue-400',
    executing: 'text-purple-400',
    result: 'text-green-400',
    explanation: 'text-gray-400',
    error: 'text-red-400',
  };

  return (
    <div className="divide-y divide-gray-800/50">
      {reversed.map((evt, idx) => (
        <div key={idx} className="px-4 py-2.5 hover:bg-gray-800/30">
          <div className="flex items-center gap-2 mb-1">
            <span className={`text-[10px] font-bold uppercase ${eventColor[evt.event] || 'text-gray-500'}`}>
              {evt.event}
            </span>
            <span className="text-[10px] text-gray-600">
              {new Date(evt.timestamp).toLocaleTimeString()}
            </span>
            {evt.confidence != null && evt.confidence > 0 && (
              <span className="text-[10px] text-gray-500">
                conf: {(evt.confidence * 100).toFixed(0)}%
              </span>
            )}
          </div>
          <p className="text-xs text-gray-300 font-mono leading-relaxed">{evt.message}</p>
        </div>
      ))}
    </div>
  );
}
