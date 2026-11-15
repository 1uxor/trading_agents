import pytest

# Import strategy modules to trigger registration
import backend.strategies.ma_crossover
import backend.strategies.rsi_reversion
import backend.strategies.breakout
import backend.strategies.forecast_driven
import backend.strategies.llm_discretionary

from backend.agent.schemas import AgentConfig, StrategyConfig
from backend.backtest.engine import Backtester
from backend.backtest.metrics import compute_metrics
from backend.risk.models import RiskProfile


@pytest.mark.asyncio
async def test_backtest_runs():
    config = AgentConfig(
        name="Test",
        color="#FF0000",
        symbols=["EURUSD"],
        timeframe="H1",
        model_provider="no_model",
        strategies=[StrategyConfig(name="ma_crossover", params={"fast_period": 10, "slow_period": 30})],
        risk_profile=RiskProfile(max_risk_per_trade_pct=1.0, max_open_positions=3, max_lot_size=0.1),
    )
    bt = Backtester(
        agent_config=config,
        symbol="EURUSD",
        timeframe="H1",
        bars=1000,
        spread_pips=1.0,
        commission_per_lot=7.0,
        slippage_pips=0.5,
    )
    result = await bt.run()

    assert "total_return_pct" in result
    assert "sharpe_ratio" in result
    assert "equity_curve" in result
    assert "trades" in result
    assert len(result["equity_curve"]) > 0
    assert isinstance(result["total_trades"], int)


def test_compute_metrics_empty():
    m = compute_metrics([10000], [])
    assert m["total_trades"] == 0
    assert m["sharpe_ratio"] == 0


def test_compute_metrics_with_trades():
    equity = [10000, 10050, 10020, 10100, 10080, 10150]
    trades = [
        {"pnl": 50}, {"pnl": -30}, {"pnl": 80}, {"pnl": -20}, {"pnl": 70},
    ]
    m = compute_metrics(equity, trades)
    assert m["total_return_pct"] > 0
    assert m["total_trades"] == 5
    assert 0 < m["win_rate"] <= 1
    assert m["profit_factor"] > 0


@pytest.mark.asyncio
async def test_backtest_rsi():
    config = AgentConfig(
        name="RSI Test",
        symbols=["EURUSD"],
        timeframe="H1",
        model_provider="no_model",
        strategies=[StrategyConfig(name="rsi_reversion")],
        risk_profile=RiskProfile(max_risk_per_trade_pct=1.0, max_open_positions=3, max_lot_size=0.1),
    )
    bt = Backtester(agent_config=config, bars=2000)
    result = await bt.run()
    assert len(result["equity_curve"]) > 0
