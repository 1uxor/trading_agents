from __future__ import annotations

from typing import Any

import pandas as pd
import ta

from backend.strategies.base import (
    Strategy, Signal, SignalDirection, ParameterSpec, register_strategy,
)


@register_strategy
class MACrossoverStrategy(Strategy):
    name = "ma_crossover"
    description = "Generates signals when a fast moving average crosses a slow moving average."

    @classmethod
    def parameters(cls) -> list[ParameterSpec]:
        return [
            ParameterSpec(name="fast_period", label="Fast MA Period", type="int", default=20, min=2, max=200, step=1),
            ParameterSpec(name="slow_period", label="Slow MA Period", type="int", default=50, min=5, max=500, step=1),
            ParameterSpec(name="ma_type", label="MA Type", type="select", default="SMA", options=["SMA", "EMA"]),
            ParameterSpec(name="atr_sl_mult", label="ATR SL Multiplier", type="float", default=1.5, min=0.5, max=5.0, step=0.1),
            ParameterSpec(name="atr_tp_mult", label="ATR TP Multiplier", type="float", default=2.0, min=0.5, max=10.0, step=0.1),
        ]

    def generate_signal(
        self,
        data: pd.DataFrame,
        model_output: Any | None = None,
        params: dict | None = None,
    ) -> Signal:
        p = {spec.name: spec.default for spec in self.parameters()}
        if params:
            p.update(params)

        fast = int(p["fast_period"])
        slow = int(p["slow_period"])
        ma_type = p["ma_type"]

        close = data["close"]

        if ma_type == "EMA":
            ma_fast = ta.trend.EMAIndicator(close, window=fast).ema_indicator()
            ma_slow = ta.trend.EMAIndicator(close, window=slow).ema_indicator()
        else:
            ma_fast = ta.trend.SMAIndicator(close, window=fast).sma_indicator()
            ma_slow = ta.trend.SMAIndicator(close, window=slow).sma_indicator()

        atr = ta.volatility.AverageTrueRange(data["high"], data["low"], close, window=14).average_true_range()

        if len(ma_fast.dropna()) < 2 or len(ma_slow.dropna()) < 2:
            return Signal(strategy_name=self.name, reasoning="Not enough data for MA calculation")

        prev_fast, curr_fast = ma_fast.iloc[-2], ma_fast.iloc[-1]
        prev_slow, curr_slow = ma_slow.iloc[-2], ma_slow.iloc[-1]
        current_atr = atr.iloc[-1] if not pd.isna(atr.iloc[-1]) else 0
        price = close.iloc[-1]

        direction = SignalDirection.HOLD
        reasoning = f"Fast MA({fast})={curr_fast:.5f}, Slow MA({slow})={curr_slow:.5f}"

        # Bullish crossover
        if prev_fast <= prev_slow and curr_fast > curr_slow:
            direction = SignalDirection.BUY
            reasoning = f"Bullish crossover: Fast MA({fast}) crossed above Slow MA({slow})"
        # Bearish crossover
        elif prev_fast >= prev_slow and curr_fast < curr_slow:
            direction = SignalDirection.SELL
            reasoning = f"Bearish crossover: Fast MA({fast}) crossed below Slow MA({slow})"

        sl = None
        tp = None
        if direction == SignalDirection.BUY and current_atr > 0:
            sl = price - current_atr * p["atr_sl_mult"]
            tp = price + current_atr * p["atr_tp_mult"]
        elif direction == SignalDirection.SELL and current_atr > 0:
            sl = price + current_atr * p["atr_sl_mult"]
            tp = price - current_atr * p["atr_tp_mult"]

        confidence = 0.6 if direction != SignalDirection.HOLD else 0.0

        return Signal(
            direction=direction,
            confidence=confidence,
            sl=sl,
            tp=tp,
            reasoning=reasoning,
            strategy_name=self.name,
        )

    def commentary(self, data: pd.DataFrame, signal: Signal, params: dict | None = None) -> str:
        p = {spec.name: spec.default for spec in self.parameters()}
        if params:
            p.update(params)

        if signal.direction == SignalDirection.BUY:
            return f"The {p['fast_period']}-period MA just punched above the {p['slow_period']}-period MA — that's a bullish crossover. I'm going long."
        elif signal.direction == SignalDirection.SELL:
            return f"The {p['fast_period']}-period MA dropped below the {p['slow_period']}-period MA — bearish crossover. Flipping short."
        return f"MAs are flat — {p['fast_period']}-MA and {p['slow_period']}-MA haven't crossed. Sitting tight."
