from __future__ import annotations

from abc import ABC, abstractmethod
from enum import Enum
from typing import Any, Optional

import pandas as pd
from pydantic import BaseModel, Field


class SignalDirection(str, Enum):
    BUY = "BUY"
    SELL = "SELL"
    HOLD = "HOLD"


class Signal(BaseModel):
    direction: SignalDirection = SignalDirection.HOLD
    confidence: float = 0.0            # 0-1
    sl: Optional[float] = None         # suggested stop-loss price
    tp: Optional[float] = None         # suggested take-profit price
    reasoning: str = ""
    strategy_name: str = ""


class ParameterSpec(BaseModel):
    """Describes one strategy parameter so the UI can auto-build a form."""
    name: str
    label: str
    type: str = "float"                # float | int | bool | select
    default: Any = None
    min: Any = None
    max: Any = None
    step: Any = None
    options: list[str] | None = None   # for type="select"


class Strategy(ABC):
    """Base class for all trading strategies."""

    name: str = "base"
    description: str = ""

    @classmethod
    @abstractmethod
    def parameters(cls) -> list[ParameterSpec]:
        """Declare parameters with types/defaults/ranges for auto-UI."""
        ...

    @abstractmethod
    def generate_signal(
        self,
        data: pd.DataFrame,
        model_output: Any | None = None,
        params: dict | None = None,
    ) -> Signal:
        """Produce a trading signal from OHLCV data + optional model output."""
        ...

    def commentary(self, data: pd.DataFrame, signal: Signal, params: dict | None = None) -> str:
        """Generate a human-readable narration of what the strategy is doing."""
        return f"{self.name}: {signal.direction.value} (conf={signal.confidence:.0%}) — {signal.reasoning}"


# ── Strategy registry ───────────────────────────────────────────────────────

_STRATEGY_REGISTRY: dict[str, type[Strategy]] = {}


def register_strategy(cls: type[Strategy]) -> type[Strategy]:
    _STRATEGY_REGISTRY[cls.name] = cls
    return cls


def get_strategy(name: str) -> type[Strategy]:
    if name not in _STRATEGY_REGISTRY:
        raise ValueError(f"Unknown strategy: {name}. Available: {list(_STRATEGY_REGISTRY.keys())}")
    return _STRATEGY_REGISTRY[name]


def list_strategies() -> dict[str, type[Strategy]]:
    return dict(_STRATEGY_REGISTRY)
