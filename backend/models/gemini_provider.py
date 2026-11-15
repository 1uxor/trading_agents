from __future__ import annotations

import logging

import pandas as pd

from backend.config import get_settings
from backend.models.base import ModelProvider, register_model_provider
from backend.models._llm_common import SYSTEM_PROMPT, build_market_context, parse_llm_response

logger = logging.getLogger(__name__)


@register_model_provider
class GeminiProvider(ModelProvider):
    name = "gemini"

    def __init__(self, model: str = "gemini-2.0-flash", temperature: float = 0.2, **kwargs):
        self._model = model
        self._temperature = temperature

    async def predict(self, data: pd.DataFrame, symbol: str = "", **kwargs) -> dict:
        import google.generativeai as genai

        settings = get_settings()
        if not settings.gemini_api_key:
            return parse_llm_response("")

        genai.configure(api_key=settings.gemini_api_key)
        model = genai.GenerativeModel(
            self._model,
            system_instruction=SYSTEM_PROMPT,
        )

        context = build_market_context(data, symbol)
        response = await model.generate_content_async(
            context,
            generation_config=genai.GenerationConfig(
                temperature=self._temperature,
                max_output_tokens=500,
            ),
        )

        text = response.text if response.text else ""
        return parse_llm_response(text)
