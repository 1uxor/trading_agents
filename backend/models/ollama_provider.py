from __future__ import annotations

import logging

import pandas as pd
import httpx

from backend.config import get_settings
from backend.models.base import ModelProvider, register_model_provider
from backend.models._llm_common import SYSTEM_PROMPT, build_market_context, parse_llm_response

logger = logging.getLogger(__name__)


@register_model_provider
class OllamaProvider(ModelProvider):
    name = "ollama"

    def __init__(self, model: str = "llama3.1", temperature: float = 0.2, **kwargs):
        self._model = model
        self._temperature = temperature

    async def predict(self, data: pd.DataFrame, symbol: str = "", **kwargs) -> dict:
        settings = get_settings()
        url = f"{settings.ollama_base_url}/api/chat"
        context = build_market_context(data, symbol)

        payload = {
            "model": self._model,
            "stream": False,
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": context},
            ],
            "options": {"temperature": self._temperature},
        }

        try:
            async with httpx.AsyncClient(timeout=120) as client:
                resp = await client.post(url, json=payload)
                resp.raise_for_status()
                data_resp = resp.json()
                text = data_resp.get("message", {}).get("content", "")
                return parse_llm_response(text)
        except Exception as e:
            logger.warning("Ollama error: %s", e)
            return parse_llm_response("")
