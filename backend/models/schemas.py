from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, Field


class LLMSignal(BaseModel):
    """Validated JSON that every LLM provider must return."""
    signal: str = "HOLD"            # BUY | SELL | HOLD
    confidence: float = Field(0.0, ge=0.0, le=1.0)
    sl: Optional[float] = None
    tp: Optional[float] = None
    reasoning: str = ""


class ForecastResult(BaseModel):
    """Output from time-series foundation models."""
    forecast: float                  # predicted price
    quantile_low: Optional[float] = None   # e.g. 10th percentile
    quantile_high: Optional[float] = None  # e.g. 90th percentile
    horizon: int = 1                 # bars ahead


class MarketContext(BaseModel):
    """Structured summary sent to LLM providers."""
    symbol: str
    timeframe: str
    current_price: float
    recent_candles: list[dict]       # last N candles as dicts
    indicators: dict = {}            # name -> value
    news_summary: str = ""
