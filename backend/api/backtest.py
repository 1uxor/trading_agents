from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from backend.agent.schemas import AgentConfig

router = APIRouter(prefix="/api/backtest", tags=["backtest"])


class BacktestRequest(BaseModel):
    agent_config: AgentConfig
    symbol: str = "EURUSD"
    timeframe: str = "H1"
    bars: int = 5000
    walk_forward_splits: int = 1
    spread_pips: float = 1.0
    commission_per_lot: float = 7.0
    slippage_pips: float = 0.5
    initial_balance: float = 10_000.0
    data_source: str = "synthetic"   # "synthetic" | "yfinance" | "csv:<key>"


class BacktestResult(BaseModel):
    total_return_pct: float
    sharpe_ratio: float
    sortino_ratio: float
    max_drawdown_pct: float
    win_rate: float
    profit_factor: float
    total_trades: int
    equity_curve: list[float]
    trades: list[dict]
    data_source: str = "synthetic"
    bars_used: int = 0


@router.post("", response_model=BacktestResult)
async def run_backtest(req: BacktestRequest):
    """Run a backtest with configurable data source and parameters."""
    from backend.backtest.engine import Backtester
    try:
        bt = Backtester(
            agent_config=req.agent_config,
            symbol=req.symbol,
            timeframe=req.timeframe,
            bars=req.bars,
            walk_forward_splits=req.walk_forward_splits,
            spread_pips=req.spread_pips,
            commission_per_lot=req.commission_per_lot,
            slippage_pips=req.slippage_pips,
            initial_balance=req.initial_balance,
            data_source=req.data_source,
        )
        result = await bt.run()
        return result
    except Exception as e:
        raise HTTPException(500, f"Backtest error: {e}")
