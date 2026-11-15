from __future__ import annotations

from typing import Any

import pandas as pd
import ta

from backend.strategies.base import (
    Strategy, Signal, SignalDirection, ParameterSpec, register_strategy,
)


@register_strategy
class BreakoutStrategy(Strategy):
    name = "breakout"
    description = "Donchian channel breakout with ATR-based stops. Buys on upper-band break, sells on lower-band break."

    @classmethod
    def parameters(cls) -> list[ParameterSpec]:
        return [
            ParameterSpec(name="channel_period", label="Channel Period", type="int", default=20, min=5, max=100, step=1),
            ParameterSpec(name="atr_period", label="ATR Period", type="int", default=14, min=5, max=50, step=1),
            ParameterSpec(name="atr_sl_mult", label="ATR SL Multiplier", type="float", default=2.0, min=0.5, max=5.0, step=0.1),
            ParameterSpec(name="atr_tp_mult", label="ATR TP Multiplier", type="float", default=3.0, min=1.0, max=10.0, step=0.1),
            ParameterSpec(name="confirm_close", label="Require Close Outside Channel", type="bool", default=True),
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

        period = int(p["channel_period"])
        close = data["close"]
        high = data["high"]
        low = data["low"]

        if len(data) < period + 2:
            return Signal(strategy_name=self.name, reasoning="Not enough data for Donchian channel")

        # Donchian channel (exclude current bar for the channel)
        upper = high.rolling(window=period).max().shift(1)
        lower = low.rolling(window=period).min().shift(1)

        atr = ta.volatility.AverageTrueRange(high, low, close, window=int(p["atr_period"])).average_true_range()

        current_close = close.iloc[-1]
        current_high = high.iloc[-1]
        current_low = low.iloc[-1]
        prev_upper = upper.iloc[-1]
        prev_lower = lower.iloc[-1]
        current_atr = atr.iloc[-1] if not pd.isna(atr.iloc[-1]) else 0

        direction = SignalDirection.HOLD
        reasoning = f"Donchian({period}): upper={prev_upper:.5f}, lower={prev_lower:.5f}, price={current_close:.5f}"
        confidence = 0.0

        check_price = current_close if p["confirm_close"] else current_high

        if check_price > prev_upper and not pd.isna(prev_upper):
            direction = SignalDirection.BUY
            confidence = 0.65
            reasoning = f"Breakout above Donchian upper ({prev_upper:.5f}). Price: {current_close:.5f}"
        elif (current_close if p["confirm_close"] else current_low) < prev_lower and not pd.isna(prev_lower):
            direction = SignalDirection.SELL
            confidence = 0.65
            reasoning = f"Breakdown below Donchian lower ({prev_lower:.5f}). Price: {current_close:.5f}"

        sl, tp = None, None
        if direction == SignalDirection.BUY and current_atr > 0:
            sl = current_close - current_atr * p["atr_sl_mult"]
            tp = current_close + current_atr * p["atr_tp_mult"]
        elif direction == SignalDirection.SELL and current_atr > 0:
            sl = current_close + current_atr * p["atr_sl_mult"]
            tp = current_close - current_atr * p["atr_tp_mult"]

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
            return f"Price just broke above the {p['channel_period']}-period high — classic breakout. Riding the momentum long."
        elif signal.direction == SignalDirection.SELL:
            return f"Price sliced below the {p['channel_period']}-period low — breakdown. Going short."
        return f"Price is stuck inside the {p['channel_period']}-period range. Waiting for a breakout."
