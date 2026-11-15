"""Shared utilities for all LLM-based model providers."""
from __future__ import annotations

import json
import logging

import pandas as pd
import ta

from backend.models.schemas import LLMSignal, MarketContext

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """You are a quantitative trading analyst. Analyze the market data and return ONLY a JSON object with this exact structure:
{"signal": "BUY" or "SELL" or "HOLD", "confidence": 0.0 to 1.0, "sl": stop_loss_price_or_null, "tp": take_profit_price_or_null, "reasoning": "brief explanation"}

Rules:
- signal must be exactly "BUY", "SELL", or "HOLD"
- confidence must be between 0 and 1
- sl and tp should be specific prices (not pips) or null
- reasoning should be 1-3 sentences
- Return ONLY the JSON, no markdown, no extra text"""


def build_market_context(data: pd.DataFrame, symbol: str, timeframe: str = "H1") -> str:
    """Build a structured market summary string from OHLCV data."""
    close = data["close"]
    high = data["high"]
    low = data["low"]

    # Compute indicators
    rsi = ta.momentum.RSIIndicator(close, window=14).rsi()
    sma_20 = ta.trend.SMAIndicator(close, window=20).sma_indicator()
    sma_50 = ta.trend.SMAIndicator(close, window=50).sma_indicator()
    ema_12 = ta.trend.EMAIndicator(close, window=12).ema_indicator()
    ema_26 = ta.trend.EMAIndicator(close, window=26).ema_indicator()
    atr = ta.volatility.AverageTrueRange(high, low, close, window=14).average_true_range()
    bb = ta.volatility.BollingerBands(close, window=20, window_dev=2)

    # Last 10 candles
    last_candles = data.tail(10)[["open", "high", "low", "close", "volume"]].to_dict("records")
    for c in last_candles:
        for k, v in c.items():
            c[k] = round(v, 5) if isinstance(v, float) else v

    ctx = f"""Symbol: {symbol} | Timeframe: {timeframe}
Current Price: {close.iloc[-1]:.5f}
RSI(14): {rsi.iloc[-1]:.1f}
SMA(20): {sma_20.iloc[-1]:.5f} | SMA(50): {sma_50.iloc[-1]:.5f}
EMA(12): {ema_12.iloc[-1]:.5f} | EMA(26): {ema_26.iloc[-1]:.5f}
ATR(14): {atr.iloc[-1]:.5f}
Bollinger Upper: {bb.bollinger_hband().iloc[-1]:.5f} | Lower: {bb.bollinger_lband().iloc[-1]:.5f}
Last 10 candles: {json.dumps(last_candles)}"""
    return ctx


def parse_llm_response(text: str) -> dict:
    """Parse LLM response text into a validated signal dict. Returns HOLD on failure."""
    text = text.strip()
    # Try to extract JSON from possible markdown code block
    if "```" in text:
        parts = text.split("```")
        for part in parts:
            part = part.strip()
            if part.startswith("json"):
                part = part[4:].strip()
            if part.startswith("{"):
                text = part
                break

    try:
        raw = json.loads(text)
        signal = LLMSignal(**raw)
        return signal.model_dump()
    except Exception as e:
        logger.warning("Failed to parse LLM response: %s — treating as HOLD", e)
        return LLMSignal(signal="HOLD", reasoning=f"Parse error: {e}").model_dump()
