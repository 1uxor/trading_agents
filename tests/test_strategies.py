import pytest
import numpy as np
import pandas as pd

from backend.strategies.ma_crossover import MACrossoverStrategy
from backend.strategies.rsi_reversion import RSIReversionStrategy
from backend.strategies.breakout import BreakoutStrategy
from backend.strategies.forecast_driven import ForecastDrivenStrategy
from backend.strategies.llm_discretionary import LLMDiscretionaryStrategy
from backend.strategies.base import SignalDirection


def make_data(prices: list[float], bars: int = 200) -> pd.DataFrame:
    """Generate synthetic OHLCV data ending with the given prices."""
    rng = np.random.default_rng(42)
    if len(prices) < bars:
        # Pad with random walk
        base = prices[0] if prices else 1.1
        prefix = [base + rng.normal(0, 0.0003) * i for i in range(bars - len(prices))]
        prices = prefix + prices
    n = len(prices)
    close = np.array(prices[-bars:])
    high = close + rng.uniform(0, 0.001, bars)
    low = close - rng.uniform(0, 0.001, bars)
    opens = np.roll(close, 1)
    opens[0] = close[0]
    return pd.DataFrame({
        "time": np.arange(bars),
        "open": opens,
        "high": high,
        "low": low,
        "close": close,
        "volume": rng.uniform(100, 1000, bars),
    })


def test_ma_crossover_has_parameters():
    params = MACrossoverStrategy.parameters()
    assert len(params) >= 3
    names = [p.name for p in params]
    assert "fast_period" in names
    assert "slow_period" in names


def test_ma_crossover_generates_signal():
    strat = MACrossoverStrategy()
    data = make_data([1.1 + i * 0.0001 for i in range(200)])
    signal = strat.generate_signal(data)
    assert signal.direction in [SignalDirection.BUY, SignalDirection.SELL, SignalDirection.HOLD]
    assert signal.strategy_name == "ma_crossover"


def test_rsi_reversion_oversold():
    # Create data that drops sharply to trigger oversold
    prices = [1.1] * 100 + [1.1 - i * 0.002 for i in range(100)]
    data = make_data(prices)
    strat = RSIReversionStrategy()
    signal = strat.generate_signal(data)
    # With a big drop, RSI should be oversold -> BUY
    assert signal.direction in [SignalDirection.BUY, SignalDirection.HOLD]


def test_breakout_parameters():
    params = BreakoutStrategy.parameters()
    names = [p.name for p in params]
    assert "channel_period" in names


def test_forecast_driven_no_model():
    strat = ForecastDrivenStrategy()
    data = make_data([1.1] * 200)
    signal = strat.generate_signal(data, model_output=None)
    assert signal.direction == SignalDirection.HOLD


def test_forecast_driven_bullish():
    strat = ForecastDrivenStrategy()
    data = make_data([1.1] * 200)
    model_output = {"forecast": 1.105, "quantile_low": 1.102, "quantile_high": 1.108}
    signal = strat.generate_signal(data, model_output=model_output, params={"return_threshold": 0.1, "quantile_agreement": False, "atr_sl_mult": 1.5, "atr_tp_mult": 2.5})
    assert signal.direction == SignalDirection.BUY


def test_llm_discretionary():
    strat = LLMDiscretionaryStrategy()
    data = make_data([1.1] * 200)
    model_output = {"signal": "BUY", "confidence": 0.8, "sl": 1.095, "tp": 1.110, "reasoning": "bullish setup"}
    signal = strat.generate_signal(data, model_output=model_output)
    assert signal.direction == SignalDirection.BUY
    assert signal.confidence == 0.8


def test_llm_discretionary_low_confidence_filtered():
    strat = LLMDiscretionaryStrategy()
    data = make_data([1.1] * 200)
    model_output = {"signal": "BUY", "confidence": 0.2, "reasoning": "weak"}
    signal = strat.generate_signal(data, model_output=model_output, params={"min_confidence": 0.5})
    assert signal.direction == SignalDirection.HOLD


def test_commentary():
    strat = MACrossoverStrategy()
    data = make_data([1.1 + i * 0.0001 for i in range(200)])
    signal = strat.generate_signal(data)
    comment = strat.commentary(data, signal)
    assert isinstance(comment, str)
    assert len(comment) > 10
