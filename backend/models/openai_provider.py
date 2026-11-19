from __future__ import annotations

import logging

import pandas as pd

from backend.config import get_settings
from backend.models.base import ModelProvider, register_model_provider
from backend.models._llm_common import SYSTEM_PROMPT, build_market_context, parse_llm_response

logger = logging.getLogger(__name__)


@register_model_provider
class OpenAIProvider(ModelProvider):
    name = "openai"
    available_models = [
        {"id": "gpt-4o-mini", "label": "GPT-4o Mini"},
        {"id": "gpt-4o", "label": "GPT-4o"},
        {"id": "gpt-4.1-mini", "label": "GPT-4.1 Mini"},
        {"id": "gpt-4.1", "label": "GPT-4.1"},
        {"id": "o3-mini", "label": "o3 Mini"},
    ]

    def __init__(self, model: str = "gpt-4o-mini", temperature: float = 0.2, **kwargs):
        self._model = model
        self._temperature = temperature

    async def predict(self, data: pd.DataFrame, symbol: str = "", **kwargs) -> dict:
        from openai import AsyncOpenAI

        settings = get_settings()
        if not settings.openai_api_key:
            return parse_llm_response("")

        client = AsyncOpenAI(api_key=settings.openai_api_key)
        context = build_market_context(data, symbol)

        response = await client.chat.completions.create(
            model=self._model,
            temperature=self._temperature,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": context},
            ],
            max_tokens=500,
        )

        text = response.choices[0].message.content or ""
        return parse_llm_response(text)
