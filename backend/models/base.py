from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

import pandas as pd


class ModelProvider(ABC):
    """Abstract model provider — wraps LLMs, time-series models, etc."""

    name: str = "base"
    license_info: str = ""     # shown in UI for HF models

    @abstractmethod
    async def predict(self, data: pd.DataFrame, symbol: str = "", **kwargs) -> dict:
        """Return a dict suitable for the strategy (LLMSignal fields or ForecastResult fields)."""
        ...


# ── Registry ────────────────────────────────────────────────────────────────

_MODEL_REGISTRY: dict[str, type[ModelProvider]] = {}


def register_model_provider(cls: type[ModelProvider]) -> type[ModelProvider]:
    _MODEL_REGISTRY[cls.name] = cls
    return cls


def get_model_provider(name: str) -> type[ModelProvider]:
    if name not in _MODEL_REGISTRY:
        raise ValueError(f"Unknown model provider: {name}. Available: {list(_MODEL_REGISTRY.keys())}")
    return _MODEL_REGISTRY[name]


def list_model_providers() -> dict[str, type[ModelProvider]]:
    return dict(_MODEL_REGISTRY)
