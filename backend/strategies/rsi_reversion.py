from __future__ import annotations

from typing import Any

import pandas as pd
import ta

from backend.strategies.base import (
    Strategy, Signal, SignalDirection, ParameterSpec, register_strategy,
)


@register_strategy
class RSIReversionStrategy(Strategy):
    name = "rsi_reversion"
    description = "Mean-reversion strategy: buy when RSI is oversold, sell when overbought."

    @classmethod
    def parameters(cls) -> list[ParameterSpec]:
        return [
            ParameterSpec(name="rsi_period", label="RSI Period", type="int", default=14, min=2, max=50, step=1),
            ParameterSpec(name="oversold", label="Oversold Level", type="float", default=30.0, min=10, max=40, step=1),
            ParameterSpec(name="overbought", label="Overbought Level", type="float", default=70.0, min=60, max=90, step=1),
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

        close = data["close"]
        rsi = ta.momentum.RSIIndicator(close, window=int(p["rsi_period"])).rsi()
        atr = ta.volatility.AverageTrueRange(data["high"], data["low"], close, window=14).average_true_range()

        if rsi.dropna().empty:
            return Signal(strategy_name=self.name, reasoning="Not enough data for RSI")

        current_rsi = rsi.iloc[-1]
        current_atr = atr.iloc[-1] if not pd.isna(atr.iloc[-1]) else 0
        price = close.iloc[-1]

        direction = SignalDirection.HOLD
        reasoning = f"RSI({int(p['rsi_period'])}) = {current_rsi:.1f}"
        confidence = 0.0

        if current_rsi < p["oversold"]:
            direction = SignalDirection.BUY
            confidence = min((p["oversold"] - current_rsi) / p["oversold"], 1.0)
            reasoning = f"RSI at {current_rsi:.1f} — oversold territory (< {p['oversold']}). Looking for a bounce."
        elif current_rsi > p["overbought"]:
            direction = SignalDirection.SELL
            confidence = min((current_rsi - p["overbought"]) / (100 - p["overbought"]), 1.0)
            reasoning = f"RSI at {current_rsi:.1f} — overbought (> {p['overbought']}). Expecting a pullback."

        sl, tp = None, None
        if direction == SignalDirection.BUY and current_atr > 0:
            sl = price - current_atr * p["atr_sl_mult"]
            tp = price + current_atr * p["atr_tp_mult"]
        elif direction == SignalDirection.SELL and current_atr > 0:
            sl = price + current_atr * p["atr_sl_mult"]
            tp = price - current_atr * p["atr_tp_mult"]

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
        close = data["close"]
        rsi = ta.momentum.RSIIndicator(close, window=int(p["rsi_period"])).rsi()
        current_rsi = rsi.iloc[-1] if not rsi.dropna().empty else 50

        if signal.direction == SignalDirection.BUY:
            return f"RSI just hit {current_rsi:.1f} — that's deep in oversold territory. History says this bounces. Going long."
        elif signal.direction == SignalDirection.SELL:
            return f"RSI at {current_rsi:.1f} — way overbought. This thing needs to cool off. Shorting."
        return f"RSI sitting at {current_rsi:.1f} — neutral zone. Nothing to do here."
