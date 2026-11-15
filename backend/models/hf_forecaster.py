from __future__ import annotations

import logging
from typing import Optional

import numpy as np
import pandas as pd

from backend.models.base import ModelProvider, register_model_provider

logger = logging.getLogger(__name__)

# License info for common HF time-series models
HF_MODEL_LICENSES = {
    "google/timesfm-2.0-500m-pytorch": "Apache 2.0",
    "google/timesfm-1.0-200m-pytorch": "Apache 2.0",
    "amazon/chronos-t5-small": "Apache 2.0",
    "amazon/chronos-t5-base": "Apache 2.0",
    "amazon/chronos-t5-large": "Apache 2.0",
    "amazon/chronos-bolt-small": "Apache 2.0",
    "amazon/chronos-bolt-base": "Apache 2.0",
    "Salesforce/moirai-1.1-R-small": "Apache 2.0",
    "Salesforce/moirai-1.1-R-base": "Apache 2.0",
    "Salesforce/moirai-1.1-R-large": "Apache 2.0",
}


@register_model_provider
class HuggingFaceForecaster(ModelProvider):
    name = "hf_forecaster"

    def __init__(
        self,
        model_id: str = "amazon/chronos-bolt-small",
        horizon: int = 5,
        device: str = "cpu",
        **kwargs,
    ):
        self._model_id = model_id
        self._horizon = horizon
        self._device = device
        self._pipeline = None
        self.license_info = HF_MODEL_LICENSES.get(model_id, "Check model card")

    def _load_pipeline(self):
        """Lazy-load the model pipeline."""
        if self._pipeline is not None:
            return

        if "chronos" in self._model_id.lower():
            self._load_chronos()
        else:
            self._load_generic()

    def _load_chronos(self):
        try:
            from chronos import BaseChronosPipeline
            self._pipeline = BaseChronosPipeline.from_pretrained(
                self._model_id,
                device_map=self._device,
            )
            self._pipeline_type = "chronos"
        except ImportError:
            logger.warning("chronos package not installed. Install with: pip install chronos-forecasting")
            raise

    def _load_generic(self):
        """Fallback: load as a generic HF pipeline via transformers."""
        try:
            from transformers import pipeline
            self._pipeline = pipeline(
                "time-series-forecasting",
                model=self._model_id,
                device=self._device,
            )
            self._pipeline_type = "generic"
        except Exception:
            logger.warning("Could not load %s as time-series-forecasting pipeline, using basic approach", self._model_id)
            self._pipeline = None
            self._pipeline_type = "none"

    async def predict(self, data: pd.DataFrame, symbol: str = "", **kwargs) -> dict:
        import torch

        self._load_pipeline()

        close_prices = data["close"].values.astype(np.float32)

        if self._pipeline is None or self._pipeline_type == "none":
            # Fallback: simple moving average forecast
            forecast_val = float(np.mean(close_prices[-20:]))
            return {
                "forecast": forecast_val,
                "quantile_low": forecast_val * 0.998,
                "quantile_high": forecast_val * 1.002,
                "horizon": self._horizon,
            }

        if self._pipeline_type == "chronos":
            context = torch.tensor(close_prices, dtype=torch.float32).unsqueeze(0)
            forecast = self._pipeline.predict(
                context,
                prediction_length=self._horizon,
            )
            # forecast shape: (1, num_samples, horizon) or (1, horizon) for bolt
            if forecast.dim() == 3:
                # Probabilistic: get median and quantiles
                median = forecast.median(dim=1).values[0]
                q_low = forecast.quantile(0.1, dim=1)[0]
                q_high = forecast.quantile(0.9, dim=1)[0]
                return {
                    "forecast": float(median[-1]),
                    "quantile_low": float(q_low[-1]),
                    "quantile_high": float(q_high[-1]),
                    "horizon": self._horizon,
                }
            else:
                val = float(forecast[0, -1])
                return {
                    "forecast": val,
                    "quantile_low": val * 0.998,
                    "quantile_high": val * 1.002,
                    "horizon": self._horizon,
                }

        # Generic pipeline
        try:
            result = self._pipeline(close_prices.tolist(), prediction_length=self._horizon)
            if isinstance(result, dict):
                return {
                    "forecast": float(result.get("mean", [close_prices[-1]])[-1]),
                    "quantile_low": float(result.get("quantile_0.1", [close_prices[-1] * 0.998])[-1]),
                    "quantile_high": float(result.get("quantile_0.9", [close_prices[-1] * 1.002])[-1]),
                    "horizon": self._horizon,
                }
        except Exception as e:
            logger.warning("HF forecaster prediction error: %s", e)

        # Final fallback
        return {
            "forecast": float(close_prices[-1]),
            "quantile_low": float(close_prices[-1] * 0.998),
            "quantile_high": float(close_prices[-1] * 1.002),
            "horizon": self._horizon,
        }
