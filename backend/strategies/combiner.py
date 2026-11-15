from __future__ import annotations

from enum import Enum
from typing import Any

import pandas as pd
from pydantic import BaseModel

from backend.strategies.base import Strategy, Signal, SignalDirection


class CombineMode(str, Enum):
    MAJORITY_VOTE = "majority_vote"
    WEIGHTED_VOTE = "weighted_vote"
    UNANIMOUS = "unanimous"
    FILTER_CHAIN = "filter_chain"
    CONFIDENCE_WEIGHTED = "confidence_weighted"


class CombinerConfig(BaseModel):
    mode: CombineMode = CombineMode.MAJORITY_VOTE
    weights: dict[str, float] | None = None          # strategy_name -> weight (for weighted_vote)
    filter_roles: dict[str, str] | None = None        # strategy_name -> "direction" | "confirm" | "regime"


class StrategyCombiner:
    """Combine multiple strategy signals with a selectable mode."""

    def __init__(self, strategies: list[tuple[Strategy, dict]], config: CombinerConfig):
        self._strategies = strategies   # list of (strategy_instance, params_dict)
        self._config = config

    def generate_signal(
        self,
        data: pd.DataFrame,
        model_outputs: dict[str, Any] | None = None,
    ) -> tuple[Signal, list[Signal]]:
        """Returns (combined_signal, individual_signals)."""
        model_outputs = model_outputs or {}

        signals: list[Signal] = []
        for strat, params in self._strategies:
            model_out = model_outputs.get(strat.name)
            sig = strat.generate_signal(data, model_output=model_out, params=params)
            signals.append(sig)

        if self._config.mode == CombineMode.MAJORITY_VOTE:
            combined = self._majority_vote(signals)
        elif self._config.mode == CombineMode.WEIGHTED_VOTE:
            combined = self._weighted_vote(signals)
        elif self._config.mode == CombineMode.UNANIMOUS:
            combined = self._unanimous(signals)
        elif self._config.mode == CombineMode.FILTER_CHAIN:
            combined = self._filter_chain(signals)
        elif self._config.mode == CombineMode.CONFIDENCE_WEIGHTED:
            combined = self._confidence_weighted(signals)
        else:
            combined = Signal(reasoning="Unknown combine mode")

        combined.strategy_name = f"combined({self._config.mode.value})"
        return combined, signals

    def _majority_vote(self, signals: list[Signal]) -> Signal:
        votes = {"BUY": 0, "SELL": 0, "HOLD": 0}
        for s in signals:
            votes[s.direction.value] += 1

        winner = max(votes, key=votes.get)  # type: ignore
        total = len(signals)
        agreement = votes[winner] / total

        best = self._best_signal_for(signals, SignalDirection(winner))
        return Signal(
            direction=SignalDirection(winner),
            confidence=agreement * (best.confidence if best else 0.5),
            sl=best.sl if best else None,
            tp=best.tp if best else None,
            reasoning=f"Majority vote: {votes} — {winner} wins ({agreement:.0%} agreement)",
        )

    def _weighted_vote(self, signals: list[Signal]) -> Signal:
        weights = self._config.weights or {}
        scores = {"BUY": 0.0, "SELL": 0.0, "HOLD": 0.0}

        for s in signals:
            w = weights.get(s.strategy_name, 1.0)
            scores[s.direction.value] += w

        total_weight = sum(scores.values()) or 1
        winner = max(scores, key=scores.get)  # type: ignore

        best = self._best_signal_for(signals, SignalDirection(winner))
        return Signal(
            direction=SignalDirection(winner),
            confidence=scores[winner] / total_weight,
            sl=best.sl if best else None,
            tp=best.tp if best else None,
            reasoning=f"Weighted vote: {scores} — {winner} wins",
        )

    def _unanimous(self, signals: list[Signal]) -> Signal:
        active = [s for s in signals if s.direction != SignalDirection.HOLD]
        if not active:
            return Signal(reasoning="All strategies say HOLD")

        directions = set(s.direction for s in active)
        if len(directions) == 1:
            d = directions.pop()
            avg_conf = sum(s.confidence for s in active) / len(active)
            best = self._best_signal_for(signals, d)
            return Signal(
                direction=d,
                confidence=avg_conf,
                sl=best.sl if best else None,
                tp=best.tp if best else None,
                reasoning=f"Unanimous: all {len(active)} active strategies agree on {d.value}",
            )

        return Signal(
            reasoning=f"No unanimity: directions={[s.direction.value for s in active]}",
        )

    def _filter_chain(self, signals: list[Signal]) -> Signal:
        roles = self._config.filter_roles or {}
        direction_signal = None
        confirmations = []
        regime_ok = True

        for (strat, _params), sig in zip(self._strategies, signals):
            role = roles.get(strat.name, "confirm")
            if role == "direction" and direction_signal is None:
                direction_signal = sig
            elif role == "confirm":
                confirmations.append(sig)
            elif role == "regime":
                if sig.direction == SignalDirection.HOLD:
                    regime_ok = False

        if direction_signal is None or direction_signal.direction == SignalDirection.HOLD:
            return Signal(reasoning="Direction strategy says HOLD (or missing)")

        if not regime_ok:
            return Signal(reasoning="Regime filter says HOLD — unfavorable conditions")

        # Check confirmations agree with direction
        for c in confirmations:
            if c.direction != SignalDirection.HOLD and c.direction != direction_signal.direction:
                return Signal(
                    reasoning=f"Confirmation filter disagrees: direction={direction_signal.direction.value}, filter={c.direction.value}",
                )

        return Signal(
            direction=direction_signal.direction,
            confidence=direction_signal.confidence,
            sl=direction_signal.sl,
            tp=direction_signal.tp,
            reasoning=f"Filter chain passed: direction={direction_signal.direction.value}, confirmations OK, regime OK",
        )

    def _confidence_weighted(self, signals: list[Signal]) -> Signal:
        buy_score = sum(s.confidence for s in signals if s.direction == SignalDirection.BUY)
        sell_score = sum(s.confidence for s in signals if s.direction == SignalDirection.SELL)
        total = buy_score + sell_score

        if total == 0:
            return Signal(reasoning="All signals have zero confidence or HOLD")

        if buy_score > sell_score:
            best = self._best_signal_for(signals, SignalDirection.BUY)
            return Signal(
                direction=SignalDirection.BUY,
                confidence=buy_score / total,
                sl=best.sl if best else None,
                tp=best.tp if best else None,
                reasoning=f"Confidence-weighted: BUY={buy_score:.2f} vs SELL={sell_score:.2f}",
            )
        elif sell_score > buy_score:
            best = self._best_signal_for(signals, SignalDirection.SELL)
            return Signal(
                direction=SignalDirection.SELL,
                confidence=sell_score / total,
                sl=best.sl if best else None,
                tp=best.tp if best else None,
                reasoning=f"Confidence-weighted: SELL={sell_score:.2f} vs BUY={buy_score:.2f}",
            )
        return Signal(reasoning=f"Confidence-weighted tie: BUY={buy_score:.2f} == SELL={sell_score:.2f}")

    @staticmethod
    def _best_signal_for(signals: list[Signal], direction: SignalDirection) -> Signal | None:
        matching = [s for s in signals if s.direction == direction]
        if not matching:
            return None
        return max(matching, key=lambda s: s.confidence)
