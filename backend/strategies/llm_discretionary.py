from __future__ import annotations

from typing import Any

import pandas as pd

from backend.strategies.base import (
    Strategy, Signal, SignalDirection, ParameterSpec, register_strategy,
)


@register_strategy
class LLMDiscretionaryStrategy(Strategy):
    name = "llm_discretionary"
    description = "Uses the LLM's signal directly. The model analyzes market data and returns BUY/SELL/HOLD with reasoning."

    @classmethod
    def parameters(cls) -> list[ParameterSpec]:
        return [
            ParameterSpec(name="min_confidence", label="Min Confidence to Trade", type="float", default=0.15, min=0.0, max=1.0, step=0.05),
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
            return Signal(strategy_name=self.name, reasoning="No LLM output available")

        # model_output should be an LLMSignal dict: {signal, confidence, sl, tp, reasoning}
        raw_signal = model_output.get("signal", "HOLD").upper()
        confidence = float(model_output.get("confidence", 0))
        sl = model_output.get("sl")
        tp = model_output.get("tp")
        reasoning = model_output.get("reasoning", "")

        direction_map = {"BUY": SignalDirection.BUY, "SELL": SignalDirection.SELL}
        direction = direction_map.get(raw_signal, SignalDirection.HOLD)

        # Apply minimum confidence filter
        if confidence < p["min_confidence"] and direction != SignalDirection.HOLD:
            reasoning = f"LLM said {raw_signal} (conf={confidence:.0%}) but below min threshold ({p['min_confidence']:.0%}). Holding."
            direction = SignalDirection.HOLD

        return Signal(
            direction=direction,
            confidence=confidence,
            sl=sl,
            tp=tp,
            reasoning=reasoning,
            strategy_name=self.name,
        )

    def commentary(self, data: pd.DataFrame, signal: Signal, params: dict | None = None) -> str:
        # The LLM's own reasoning IS the commentary
        if signal.reasoning:
            return signal.reasoning
        return f"LLM says {signal.direction.value} with {signal.confidence:.0%} confidence."
