from __future__ import annotations

import time
from typing import Optional

import pandas as pd

from backend.market_data.provider import MarketDataProvider, Timeframe


class CachedMarketData(MarketDataProvider):
    """Wrap any MarketDataProvider with an in-memory TTL cache."""

    def __init__(self, inner: MarketDataProvider, ttl_seconds: float = 30.0):
        self._inner = inner
        self._ttl = ttl_seconds
        self._cache: dict[str, tuple[float, pd.DataFrame]] = {}

    def _key(self, symbol: str, timeframe: Timeframe, count: int) -> str:
        return f"{symbol}:{timeframe.value}:{count}"

    async def get_ohlcv(
        self,
        symbol: str,
        timeframe: Timeframe,
        count: int = 500,
    ) -> pd.DataFrame:
        key = self._key(symbol, timeframe, count)
        now = time.time()

        if key in self._cache:
            ts, df = self._cache[key]
            if now - ts < self._ttl:
                return df.copy()

        df = await self._inner.get_ohlcv(symbol, timeframe, count)
        self._cache[key] = (now, df)
        return df.copy()

    async def get_symbols(self) -> list[str]:
        return await self._inner.get_symbols()

    def invalidate(self, symbol: str | None = None):
        if symbol is None:
            self._cache.clear()
        else:
            to_drop = [k for k in self._cache if k.startswith(f"{symbol}:")]
            for k in to_drop:
                del self._cache[k]
