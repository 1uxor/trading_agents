export interface AgentSummary {
  id: string;
  name: string;
  state: 'stopped' | 'running' | 'paused' | 'error';
  color: string;
  symbols: string[];
  timeframe: string;
  strategy: string;
  model: string;
}

export interface AgentConfig {
  id?: string;
  name: string;
  color: string;
  symbols: string[];
  timeframe: string;
  model_provider: string;
  model_config: Record<string, unknown>;
  strategies: StrategyConfig[];
  combiner?: CombinerConfig | null;
  risk_profile: RiskProfile;
  schedule_seconds: number;
  enabled: boolean;
}

export interface StrategyConfig {
  name: string;
  params: Record<string, unknown>;
}

export interface CombinerConfig {
  mode: 'majority_vote' | 'weighted_vote' | 'unanimous' | 'filter_chain' | 'confidence_weighted';
  weights?: Record<string, number>;
  filter_roles?: Record<string, string>;
}

export interface RiskProfile {
  max_risk_per_trade_pct: number;
  max_open_positions: number;
  max_lot_size: number;
  max_daily_loss_pct: number;
}

export interface CommentaryEvent {
  type: string;
  agent_id: string;
  agent_name: string;
  strategy: string;
  color: string;
  event: 'thinking' | 'signal' | 'executing' | 'result' | 'explanation' | 'error';
  message: string;
  data: Record<string, unknown>;
  confidence: number | null;
  timestamp: string;
}

export interface Position {
  ticket: string;
  symbol: string;
  direction: 'BUY' | 'SELL';
  lot_size: number;
  open_price: number;
  current_price: number;
  sl: number;
  tp: number | null;
  profit: number;
  agent_id: string;
}

export interface AccountInfo {
  balance: number;
  equity: number;
  margin_used: number;
  free_margin: number;
  currency: string;
}

export interface StrategyMeta {
  name: string;
  description: string;
  parameters: ParameterSpec[];
}

export interface ParameterSpec {
  name: string;
  label: string;
  type: 'float' | 'int' | 'bool' | 'select';
  default: unknown;
  min?: number;
  max?: number;
  step?: number;
  options?: string[];
}

export interface BacktestRequest {
  agent_config: AgentConfig;
  symbol: string;
  timeframe: string;
  bars: number;
  walk_forward_splits: number;
  spread_pips: number;
  commission_per_lot: number;
  slippage_pips: number;
  initial_balance: number;
  data_source: string;
}

export interface BacktestResult {
  total_return_pct: number;
  sharpe_ratio: number;
  sortino_ratio: number;
  max_drawdown_pct: number;
  win_rate: number;
  profit_factor: number;
  total_trades: number;
  equity_curve: number[];
  trades: Record<string, unknown>[];
  data_source: string;
  bars_used: number;
}

export interface OHLCVBar {
  time: number;
  open: number;
  high: number;
  low: number;
  close: number;
  volume: number;
}

export interface TradeRecord {
  id: number;
  symbol: string;
  direction: 'BUY' | 'SELL';
  lot_size: number;
  entry_price: number | null;
  exit_price: number | null;
  sl: number | null;
  tp: number | null;
  profit: number | null;
  status: 'open' | 'closed' | 'cancelled';
  opened_at: string | null;
  closed_at: string | null;
  broker_ticket: string | null;
}

export interface SignalRecord {
  id: number;
  timestamp: string | null;
  symbol: string;
  strategy_name: string;
  signal: 'BUY' | 'SELL' | 'HOLD';
  confidence: number | null;
  reasoning: string | null;
  risk_check_result: string | null;
  risk_check_reason: string | null;
  order_result: string | null;
}

export interface IndicatorSeries {
  strategy: string;
  type: 'line' | 'rsi' | 'forecast_placeholder';
  label: string;
  color: string;
  oversold?: number;
  overbought?: number;
  data: { time: number; value: number }[];
}
