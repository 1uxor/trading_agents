"""Tests for agent config validation, model skipping, candle detection, and signal enrichment."""
import asyncio
import datetime as dt
from unittest.mock import AsyncMock, MagicMock, patch

import numpy as np
import pandas as pd
import pytest

# Import strategy/model modules to trigger registration
import backend.strategies.ma_crossover
import backend.strategies.rsi_reversion
import backend.strategies.breakout
import backend.strategies.forecast_driven
import backend.strategies.llm_discretionary
import backend.models.no_model

from backend.agent.schemas import AgentConfig, StrategyConfig, CombinerConfig
from backend.agent.agent import Agent, AgentState, MODEL_STRATEGIES
from backend.strategies.combiner import CombineMode


# ── Helpers ──────────────────────────────────────────────────────────────────


def make_data(bars: int = 200, start_price: float = 1.1) -> pd.DataFrame:
    rng = np.random.default_rng(42)
    closes = [start_price + rng.normal(0, 0.0003) * i for i in range(bars)]
    close = np.array(closes)
    high = close + rng.uniform(0, 0.001, bars)
    low = close - rng.uniform(0, 0.001, bars)
    opens = np.roll(close, 1)
    opens[0] = close[0]
    timestamps = pd.date_range("2024-01-01", periods=bars, freq="h")
    return pd.DataFrame({
        "time": timestamps.astype(np.int64) // 10**9,
        "open": opens,
        "high": high,
        "low": low,
        "close": close,
        "volume": rng.uniform(100, 1000, bars),
    })


def _run(coro):
    """Run an async coroutine synchronously."""
    return asyncio.get_event_loop().run_until_complete(coro)


# ── Issue 2: Combiner validation ────────────────────────────────────────────


def test_multi_strategy_auto_sets_combiner():
    """Multiple strategies without combiner should auto-default to majority_vote."""
    config = AgentConfig(
        strategies=[
            StrategyConfig(name="ma_crossover"),
            StrategyConfig(name="rsi_reversion"),
        ],
        combiner=None,
    )
    assert config.combiner is not None
    assert config.combiner.mode == CombineMode.MAJORITY_VOTE


def test_single_strategy_removes_combiner():
    """Single strategy with combiner set should have combiner removed."""
    config = AgentConfig(
        strategies=[StrategyConfig(name="ma_crossover")],
        combiner=CombinerConfig(mode=CombineMode.UNANIMOUS),
    )
    assert config.combiner is None


def test_multi_strategy_keeps_explicit_combiner():
    """Explicit combiner on multi-strategy should be preserved."""
    config = AgentConfig(
        strategies=[
            StrategyConfig(name="ma_crossover"),
            StrategyConfig(name="rsi_reversion"),
        ],
        combiner=CombinerConfig(mode=CombineMode.UNANIMOUS),
    )
    assert config.combiner is not None
    assert config.combiner.mode == CombineMode.UNANIMOUS


# ── Issue 3: LLM provider validation ────────────────────────────────────────


def test_llm_discretionary_rejects_no_model():
    """llm_discretionary with no_model should raise."""
    with pytest.raises(ValueError, match="LLM provider"):
        AgentConfig(
            strategies=[StrategyConfig(name="llm_discretionary")],
            model_provider="no_model",
        )


def test_llm_discretionary_rejects_hf_forecaster():
    """llm_discretionary with hf_forecaster should raise."""
    with pytest.raises(ValueError, match="LLM provider"):
        AgentConfig(
            strategies=[StrategyConfig(name="llm_discretionary")],
            model_provider="hf_forecaster",
        )


def test_llm_discretionary_accepts_gemini():
    """llm_discretionary with gemini should be accepted."""
    config = AgentConfig(
        strategies=[StrategyConfig(name="llm_discretionary")],
        model_provider="gemini",
    )
    assert config.model_provider == "gemini"


def test_llm_discretionary_accepts_openai():
    config = AgentConfig(
        strategies=[StrategyConfig(name="llm_discretionary")],
        model_provider="openai",
    )
    assert config.model_provider == "openai"


def test_rule_based_allows_no_model():
    """Rule-based strategies should work with no_model."""
    config = AgentConfig(
        strategies=[StrategyConfig(name="ma_crossover")],
        model_provider="no_model",
    )
    assert config.model_provider == "no_model"


# ── Issue 4: Model skip for rule-based ───────────────────────────────────────


def test_model_strategies_set():
    """Verify MODEL_STRATEGIES contains the expected set."""
    assert "forecast_driven" in MODEL_STRATEGIES
    assert "llm_discretionary" in MODEL_STRATEGIES
    assert "ma_crossover" not in MODEL_STRATEGIES
    assert "rsi_reversion" not in MODEL_STRATEGIES
    assert "breakout" not in MODEL_STRATEGIES


def test_agent_skips_model_for_rule_based():
    """Agent with rule-based strategy should not instantiate model provider."""
    config = AgentConfig(
        strategies=[StrategyConfig(name="ma_crossover")],
        model_provider="gemini",
        model_config={"model": "gemini-3.8-flash"},
    )
    with patch("backend.agent.agent.get_model_provider") as mock_get:
        mock_cls = MagicMock()
        mock_get.return_value = mock_cls

        agent = Agent(
            config=config,
            broker=MagicMock(),
            market_data=MagicMock(),
            risk_manager=MagicMock(),
            trade_logger=MagicMock(),
        )

        # Model should NOT be instantiated since ma_crossover is rule-based
        assert agent._model is None
        assert agent._needs_model is False
        mock_get.assert_not_called()


def test_agent_instantiates_model_for_llm_strategy():
    """Agent with llm_discretionary should instantiate model provider."""
    config = AgentConfig(
        strategies=[StrategyConfig(name="llm_discretionary")],
        model_provider="gemini",
        model_config={"model": "gemini-3.8-flash"},
    )
    with patch("backend.agent.agent.get_model_provider") as mock_get:
        mock_cls = MagicMock()
        mock_get.return_value = mock_cls

        agent = Agent(
            config=config,
            broker=MagicMock(),
            market_data=MagicMock(),
            risk_manager=MagicMock(),
            trade_logger=MagicMock(),
        )

        assert agent._model is not None
        assert agent._needs_model is True
        mock_get.assert_called_once_with("gemini")


# ── Issue 5: Candle-based scheduling ────────────────────────────────────────


def test_no_new_candle_skips_tick():
    """Tick should skip processing when candle timestamp hasn't changed."""
    config = AgentConfig(
        strategies=[StrategyConfig(name="ma_crossover")],
        model_provider="no_model",
    )
    data = make_data(200)

    market_data = AsyncMock()
    market_data.get_ohlcv = AsyncMock(return_value=data)
    trade_logger = AsyncMock()
    trade_logger.log_signal = AsyncMock(return_value=1)
    callback = AsyncMock()

    agent = Agent(
        config=config,
        broker=MagicMock(),
        market_data=market_data,
        risk_manager=MagicMock(),
        trade_logger=trade_logger,
        commentary_callback=callback,
    )

    # First tick — should process (new candle)
    with patch.object(agent, '_is_market_closed', return_value=False):
        _run(agent._tick("EURUSD"))
    first_call_count = callback.call_count
    assert first_call_count > 0  # Should have emitted events

    # Second tick with same data — should skip (no new candle)
    callback.reset_mock()
    with patch.object(agent, '_is_market_closed', return_value=False):
        _run(agent._tick("EURUSD"))
    assert callback.call_count == 0  # No events emitted


def test_new_candle_processes():
    """Tick should process when candle timestamp changes."""
    config = AgentConfig(
        strategies=[StrategyConfig(name="ma_crossover")],
        model_provider="no_model",
    )
    data1 = make_data(200)
    data2 = data1.copy()
    # Change last timestamp to simulate new candle
    data2.iloc[-1, data2.columns.get_loc("time")] = data1["time"].iloc[-1] + 3600

    market_data = AsyncMock()
    trade_logger = AsyncMock()
    trade_logger.log_signal = AsyncMock(return_value=1)
    callback = AsyncMock()

    agent = Agent(
        config=config,
        broker=MagicMock(),
        market_data=market_data,
        risk_manager=MagicMock(),
        trade_logger=trade_logger,
        commentary_callback=callback,
    )

    # First tick
    market_data.get_ohlcv = AsyncMock(return_value=data1)
    with patch.object(agent, '_is_market_closed', return_value=False):
        _run(agent._tick("EURUSD"))
    assert callback.call_count > 0

    # Second tick with new candle
    callback.reset_mock()
    market_data.get_ohlcv = AsyncMock(return_value=data2)
    with patch.object(agent, '_is_market_closed', return_value=False):
        _run(agent._tick("EURUSD"))
    assert callback.call_count > 0  # Should have processed


# ── Issue 6: Market closed detection ─────────────────────────────────────────


def test_market_closed_saturday():
    """Saturday should be detected as market closed."""
    config = AgentConfig(strategies=[StrategyConfig(name="ma_crossover")])
    agent = Agent(
        config=config,
        broker=MagicMock(),
        market_data=MagicMock(),
        risk_manager=MagicMock(),
        trade_logger=MagicMock(),
    )
    # Saturday 2024-01-06
    with patch("backend.agent.agent.dt") as mock_dt:
        mock_dt.datetime.utcnow.return_value = dt.datetime(2024, 1, 6, 12, 0)
        assert agent._is_market_closed() is True


def test_market_open_wednesday():
    """Wednesday should not be detected as market closed."""
    config = AgentConfig(strategies=[StrategyConfig(name="ma_crossover")])
    agent = Agent(
        config=config,
        broker=MagicMock(),
        market_data=MagicMock(),
        risk_manager=MagicMock(),
        trade_logger=MagicMock(),
    )
    with patch("backend.agent.agent.dt") as mock_dt:
        mock_dt.datetime.utcnow.return_value = dt.datetime(2024, 1, 3, 14, 0)
        assert agent._is_market_closed() is False


def test_market_closed_logs_once():
    """Market closed should be logged only once per closed period."""
    config = AgentConfig(
        strategies=[StrategyConfig(name="ma_crossover")],
        model_provider="no_model",
    )
    callback = AsyncMock()

    agent = Agent(
        config=config,
        broker=MagicMock(),
        market_data=AsyncMock(),
        risk_manager=MagicMock(),
        trade_logger=AsyncMock(),
        commentary_callback=callback,
    )

    with patch.object(agent, '_is_market_closed', return_value=True):
        _run(agent._tick("EURUSD"))
        first_count = callback.call_count
        assert first_count == 1  # Should log "Market closed"

        _run(agent._tick("EURUSD"))
        assert callback.call_count == 1  # Should NOT log again


# ── Issue 7: Signal commentary enrichment ────────────────────────────────────


def test_signal_commentary_ma_crossover():
    """MA crossover commentary should include indicator values."""
    config = AgentConfig(
        strategies=[StrategyConfig(name="ma_crossover")],
        model_provider="no_model",
    )
    agent = Agent(
        config=config,
        broker=MagicMock(),
        market_data=MagicMock(),
        risk_manager=MagicMock(),
        trade_logger=MagicMock(),
    )
    data = make_data(200)
    from backend.strategies.ma_crossover import MACrossoverStrategy
    strat = MACrossoverStrategy()
    signal = strat.generate_signal(data)

    comment = agent._build_signal_commentary(strat, data, signal, {}, None)
    assert "ma_crossover" in comment
    assert "price=" in comment
    assert "MA(" in comment


def test_signal_commentary_forecast_driven():
    """Forecast-driven commentary should include forecast, return, and quantiles."""
    config = AgentConfig(
        strategies=[StrategyConfig(name="forecast_driven")],
        model_provider="hf_forecaster",
    )
    # Need to mock get_model_provider since hf_forecaster is a MODEL_STRATEGY
    with patch("backend.agent.agent.get_model_provider") as mock_get:
        mock_cls = MagicMock()
        mock_get.return_value = mock_cls
        agent = Agent(
            config=config,
            broker=MagicMock(),
            market_data=MagicMock(),
            risk_manager=MagicMock(),
            trade_logger=MagicMock(),
        )

    data = make_data(200)
    from backend.strategies.forecast_driven import ForecastDrivenStrategy
    strat = ForecastDrivenStrategy()
    model_output = {"forecast": 1.105, "quantile_low": 1.102, "quantile_high": 1.108}
    signal = strat.generate_signal(
        data, model_output=model_output,
        params={"return_threshold": 0.1, "quantile_agreement": False, "atr_sl_mult": 1.5, "atr_tp_mult": 2.5},
    )

    comment = agent._build_signal_commentary(strat, data, signal, {"return_threshold": 0.1}, model_output)
    assert "forecast_driven" in comment
    assert "forecast=" in comment
    assert "return=" in comment
    assert "q10=" in comment
    assert "q90=" in comment


def test_signal_commentary_rsi_reversion():
    """RSI reversion commentary should include RSI value."""
    config = AgentConfig(
        strategies=[StrategyConfig(name="rsi_reversion")],
        model_provider="no_model",
    )
    agent = Agent(
        config=config,
        broker=MagicMock(),
        market_data=MagicMock(),
        risk_manager=MagicMock(),
        trade_logger=MagicMock(),
    )
    data = make_data(200)
    from backend.strategies.rsi_reversion import RSIReversionStrategy
    strat = RSIReversionStrategy()
    signal = strat.generate_signal(data)

    comment = agent._build_signal_commentary(strat, data, signal, {}, None)
    assert "rsi_reversion" in comment
    assert "RSI(" in comment
    assert "price=" in comment


def test_signal_commentary_llm_discretionary():
    """LLM discretionary commentary should include provider, model, and raw JSON."""
    config = AgentConfig(
        strategies=[StrategyConfig(name="llm_discretionary")],
        model_provider="gemini",
        model_config={"model": "gemini-3.8-flash"},
    )
    with patch("backend.agent.agent.get_model_provider") as mock_get:
        mock_cls = MagicMock()
        mock_get.return_value = mock_cls
        agent = Agent(
            config=config,
            broker=MagicMock(),
            market_data=MagicMock(),
            risk_manager=MagicMock(),
            trade_logger=MagicMock(),
        )

    data = make_data(200)
    from backend.strategies.llm_discretionary import LLMDiscretionaryStrategy
    strat = LLMDiscretionaryStrategy()
    model_output = {"signal": "BUY", "confidence": 0.8, "sl": 1.095, "tp": 1.110, "reasoning": "bullish setup"}
    signal = strat.generate_signal(data, model_output=model_output)

    comment = agent._build_signal_commentary(strat, data, signal, {}, model_output)
    assert "llm_discretionary" in comment
    assert "provider=gemini" in comment
    assert "model=gemini-3.8-flash" in comment
    assert "signal=BUY" in comment
    assert "bullish setup" in comment


def test_signal_commentary_breakout():
    """Breakout commentary should include Donchian channel values."""
    config = AgentConfig(
        strategies=[StrategyConfig(name="breakout")],
        model_provider="no_model",
    )
    agent = Agent(
        config=config,
        broker=MagicMock(),
        market_data=MagicMock(),
        risk_manager=MagicMock(),
        trade_logger=MagicMock(),
    )
    data = make_data(200)
    from backend.strategies.breakout import BreakoutStrategy
    strat = BreakoutStrategy()
    signal = strat.generate_signal(data)

    comment = agent._build_signal_commentary(strat, data, signal, {}, None)
    assert "breakout" in comment
    assert "Donchian(" in comment
    assert "upper=" in comment
    assert "lower=" in comment


# ── Issue 1: WebSocket dedup (backend side — ensure single emit) ─────────────


def test_commentary_emits_once():
    """Commentary engine should call callback exactly once per emit."""
    from backend.agent.commentary import CommentaryEngine, CommentaryEventType

    callback = AsyncMock()
    engine = CommentaryEngine(
        agent_id="test", agent_name="Test", color="#FFF", callback=callback
    )

    _run(engine.emit(CommentaryEventType.THINKING, "test message", strategy="test"))
    assert callback.call_count == 1
    assert len(engine.history) == 1


# ── Issue 8: Default name ───────────────────────────────────────────────────


def test_default_agent_name():
    """AgentConfig with default name should accept custom names."""
    config = AgentConfig(
        strategies=[StrategyConfig(name="rsi_reversion")],
        symbols=["GBPUSD"],
    )
    assert config.name == "Agent"

    config2 = AgentConfig(
        name="rsi_reversion-GBPUSD-1",
        strategies=[StrategyConfig(name="rsi_reversion")],
        symbols=["GBPUSD"],
    )
    assert config2.name == "rsi_reversion-GBPUSD-1"
