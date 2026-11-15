"""Fetch real historical OHLCV data from Yahoo Finance (direct API)."""
from __future__ import annotations

import logging
from datetime import datetime, timezone

import numpy as np
import pandas as pd
import requests

logger = logging.getLogger(__name__)

# Timeframe mapping: our enum values → Yahoo Finance interval strings
_TF_MAP = {
    "M1": "1m",
    "M5": "5m",
    "M15": "15m",
    "M30": "30m",
    "H1": "1h",
    "H4": None,  # handled by resampling H1
    "D1": "1d",
    "W1": "1wk",
    "MN1": "1mo",
}

# Max range lookback per interval (Yahoo Finance limits)
_MAX_RANGE = {
    "1m": "7d",
    "5m": "60d",
    "15m": "60d",
    "30m": "60d",
    "1h": "730d",
    "1d": "10y",
    "1wk": "10y",
    "1mo": "10y",
}


def _to_yahoo_symbol(symbol: str) -> str:
    """Convert trading symbol to Yahoo Finance ticker.

    EURUSD → EURUSD=X   (forex)
    XAUUSD → GC=F       (gold futures)
    AAPL   → AAPL       (stocks stay as-is)
    """
    # Gold
    if symbol.upper() == "XAUUSD":
        return "GC=F"
    # Common forex pairs (6 chars, all uppercase letters)
    if len(symbol) == 6 and symbol.isalpha() and symbol.isupper():
        return f"{symbol}=X"
    return symbol


def _fetch_chart(yahoo_symbol: str, interval: str, range_: str) -> pd.DataFrame:
    """Call Yahoo Finance chart API directly."""
    url = f"https://query1.finance.yahoo.com/v8/finance/chart/{yahoo_symbol}"
    params = {"interval": interval, "range": range_}
    headers = {"User-Agent": "Mozilla/5.0"}

    resp = requests.get(url, params=params, headers=headers, timeout=30)
    resp.raise_for_status()
    data = resp.json()

    chart = data.get("chart", {})
    error = chart.get("error")
    if error:
        raise ValueError(f"Yahoo Finance error: {error.get('description', error)}")

    results = chart.get("result")
    if not results:
        raise ValueError(f"No data returned from Yahoo Finance for {yahoo_symbol}")

    result = results[0]
    timestamps = result.get("timestamp")
    if not timestamps:
        raise ValueError(f"No timestamp data for {yahoo_symbol} ({interval}, {range_})")

    quote = result["indicators"]["quote"][0]

    df = pd.DataFrame({
        "time": timestamps,
        "open": quote["open"],
        "high": quote["high"],
        "low": quote["low"],
        "close": quote["close"],
        "volume": quote.get("volume", [0] * len(timestamps)),
    })

    # Drop rows with NaN prices (can happen at market boundaries)
    df = df.dropna(subset=["open", "high", "low", "close"]).reset_index(drop=True)
    return df


def fetch_yfinance_ohlcv(
    symbol: str,
    timeframe: str,
    bars: int = 5000,
) -> pd.DataFrame:
    """Download OHLCV data from Yahoo Finance.

    Returns DataFrame with columns: time, open, high, low, close, volume
    matching the format used by PaperDataProvider.

    Raises ValueError if timeframe unsupported or no data returned.
    """
    interval = _TF_MAP.get(timeframe)

    # Handle H4 by downloading H1 and resampling
    resample_4h = False
    if timeframe == "H4":
        interval = "1h"
        resample_4h = True

    if interval is None:
        raise ValueError(f"Timeframe {timeframe} not supported by Yahoo Finance")

    yahoo_symbol = _to_yahoo_symbol(symbol)
    range_ = _MAX_RANGE.get(interval, "10y")

    logger.info("Fetching %s %s from Yahoo Finance (range=%s)", yahoo_symbol, interval, range_)

    df = _fetch_chart(yahoo_symbol, interval, range_)

    # Resample to 4H if needed
    if resample_4h:
        df["dt"] = pd.to_datetime(df["time"], unit="s")
        df = df.set_index("dt")
        df = df.resample("4h").agg({
            "time": "first",
            "open": "first",
            "high": "max",
            "low": "min",
            "close": "last",
            "volume": "sum",
        }).dropna().reset_index(drop=True)

    # Take last N bars
    if len(df) > bars:
        df = df.tail(bars).reset_index(drop=True)

    logger.info("Fetched %d bars for %s %s", len(df), symbol, timeframe)
    return df
