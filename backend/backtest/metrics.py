from __future__ import annotations

import numpy as np


def compute_metrics(equity_curve: list[float], trades: list[dict]) -> dict:
    """Compute backtest performance metrics from an equity curve and trade list."""
    if len(equity_curve) < 2:
        return _empty_metrics()

    eq = np.array(equity_curve)
    returns = np.diff(eq) / eq[:-1]
    returns = returns[np.isfinite(returns)]

    if len(returns) == 0:
        return _empty_metrics()

    # Total return
    total_return_pct = (eq[-1] / eq[0] - 1) * 100

    # Sharpe ratio (annualized, assuming ~252 trading days)
    mean_r = np.mean(returns)
    std_r = np.std(returns, ddof=1) if len(returns) > 1 else 1e-10
    sharpe_ratio = (mean_r / std_r) * np.sqrt(252) if std_r > 0 else 0.0

    # Sortino ratio
    downside = returns[returns < 0]
    downside_std = np.std(downside, ddof=1) if len(downside) > 1 else 1e-10
    sortino_ratio = (mean_r / downside_std) * np.sqrt(252) if downside_std > 0 else 0.0

    # Max drawdown
    peak = np.maximum.accumulate(eq)
    drawdown = (eq - peak) / peak
    max_drawdown_pct = abs(float(np.min(drawdown))) * 100

    # Trade-level metrics
    if trades:
        pnls = [t.get("pnl", 0) for t in trades]
        wins = [p for p in pnls if p > 0]
        losses = [p for p in pnls if p < 0]

        win_rate = len(wins) / len(pnls) if pnls else 0
        gross_profit = sum(wins) if wins else 0
        gross_loss = abs(sum(losses)) if losses else 1e-10
        profit_factor = gross_profit / gross_loss if gross_loss > 0 else 0
    else:
        win_rate = 0.0
        profit_factor = 0.0

    return {
        "total_return_pct": round(total_return_pct, 4),
        "sharpe_ratio": round(float(sharpe_ratio), 4),
        "sortino_ratio": round(float(sortino_ratio), 4),
        "max_drawdown_pct": round(max_drawdown_pct, 4),
        "win_rate": round(win_rate, 4),
        "profit_factor": round(profit_factor, 4),
        "total_trades": len(trades),
    }


def _empty_metrics() -> dict:
    return {
        "total_return_pct": 0.0,
        "sharpe_ratio": 0.0,
        "sortino_ratio": 0.0,
        "max_drawdown_pct": 0.0,
        "win_rate": 0.0,
        "profit_factor": 0.0,
        "total_trades": 0,
    }
