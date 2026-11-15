from __future__ import annotations

import pandas as pd

from backend.models.base import ModelProvider, register_model_provider


@register_model_provider
class NoModel(ModelProvider):
    """Pass-through: returns empty output so strategies run purely on rules."""

    name = "no_model"

    async def predict(self, data: pd.DataFrame, symbol: str = "", **kwargs) -> dict:
        return {}
