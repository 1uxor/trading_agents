from __future__ import annotations

from typing import Any

import pandas as pd

from backend.strategies.base import (
    Strategy, Signal, SignalDirection, ParameterSpec, register_strategy,
)


@register_strategy
class ForecastDrivenStrategy(Strategy):
    name = "forecast_driven"
    description = "Trade when the model's forecast return exceeds a threshold and quantile bands agree on direction."

    @classmethod
    def parameters(cls) -> list[ParameterSpec]:
        return [
            ParameterSpec(name="return_threshold", label="Min Forecast Return (%)", type="float", default=0.005, min=0.001, max=5.0, step=0.001),
            ParameterSpec(name="quantile_agreement", label="Require Quantile Agreement", type="bool", default=False),
            ParameterSpec(name="atr_sl_mult", label="ATR SL Multiplier", type="float", default=1.5, min=0.5, max=5.0, step=0.1),
            ParameterSpec(name="atr_tp_mult", label="ATR TP Multiplier", type="float", default=2.5, min=0.5, max=10.0, step=0.1),
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

        if model_output is None:
            return Signal(strategy_name=self.name, reasoning="No model output — forecast required")

        # Expected model_output: dict with "forecast", "quantile_low", "quantile_high"
        forecast = model_output.get("forecast")
        q_low = model_output.get("quantile_low")
        q_high = model_output.get("quantile_high")

        if forecast is None:
            return Signal(strategy_name=self.name, reasoning="Model output missing 'forecast' field")

        price = data["close"].iloc[-1]
        forecast_return = (forecast - price) / price * 100

        direction = SignalDirection.HOLD
        confidence = 0.0
        reasoning = f"Forecast return: {forecast_return:+.3f}% (threshold: {p['return_threshold']}%)"

        # Check quantile agreement
        quantiles_bullish = (q_low is not None and q_low > price) if p["quantile_agreement"] else True
        quantiles_bearish = (q_high is not None and q_high < price) if p["quantile_agreement"] else True

        if forecast_return > p["return_threshold"]:
            if not p["quantile_agreement"] or quantiles_bullish or (q_low is not None and q_low >= price * 0.999):
                direction = SignalDirection.BUY
                confidence = min(abs(forecast_return) / (p["return_threshold"] * 3), 1.0)
                reasoning = f"Forecast predicts +{forecast_return:.3f}% return. Quantiles agree: bullish."
            else:
                reasoning = f"Forecast bullish (+{forecast_return:.3f}%) but quantile band doesn't confirm."

        elif forecast_return < -p["return_threshold"]:
            if not p["quantile_agreement"] or quantiles_bearish or (q_high is not None and q_high <= price * 1.001):
                direction = SignalDirection.SELL
                confidence = min(abs(forecast_return) / (p["return_threshold"] * 3), 1.0)
                reasoning = f"Forecast predicts {forecast_return:.3f}% return. Quantiles agree: bearish."
            else:
                reasoning = f"Forecast bearish ({forecast_return:.3f}%) but quantile band doesn't confirm."

        # SL/TP from ATR
        import ta as _ta
        atr = _ta.volatility.AverageTrueRange(
            data["high"], data["low"], data["close"], window=14
        ).average_true_range()
        current_atr = atr.iloc[-1] if not pd.isna(atr.iloc[-1]) else 0

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
        if signal.direction == SignalDirection.BUY:
            return "The forecast model is pointing up and quantile bands confirm — positioning long."
        elif signal.direction == SignalDirection.SELL:
            return "Forecast is bearish with quantile confirmation — going short."
        return "Forecast return is too small or quantiles disagree. No trade."
