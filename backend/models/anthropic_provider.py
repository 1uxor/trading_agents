from __future__ import annotations

import logging

import pandas as pd

from backend.config import get_settings
from backend.models.base import ModelProvider, register_model_provider
from backend.models._llm_common import SYSTEM_PROMPT, build_market_context, parse_llm_response

logger = logging.getLogger(__name__)


@register_model_provider
class AnthropicProvider(ModelProvider):
    name = "anthropic"

    def __init__(self, model: str = "claude-sonnet-4-20250514", temperature: float = 0.2, **kwargs):
        self._model = model
        self._temperature = temperature

    async def predict(self, data: pd.DataFrame, symbol: str = "", **kwargs) -> dict:
        from anthropic import AsyncAnthropic

        settings = get_settings()
        if not settings.anthropic_api_key:
            return parse_llm_response("")

        client = AsyncAnthropic(api_key=settings.anthropic_api_key)
        context = build_market_context(data, symbol)

        response = await client.messages.create(
            model=self._model,
            max_tokens=500,
            temperature=self._temperature,
            system=SYSTEM_PROMPT,
            messages=[{"role": "user", "content": context}],
        )

        text = response.content[0].text if response.content else ""
        return parse_llm_response(text)
