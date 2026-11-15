from __future__ import annotations

import numpy as np
import pandas as pd

from backend.market_data.provider import MarketDataProvider, Timeframe


class PaperDataProvider(MarketDataProvider):
    """Serves pre-loaded DataFrames — for backtesting or offline use."""

    def __init__(self):
        self._data: dict[str, dict[str, pd.DataFrame]] = {}  # symbol -> tf -> df

    def load(self, symbol: str, timeframe: Timeframe, df: pd.DataFrame):
        """Load a DataFrame (must have: time, open, high, low, close, volume)."""
        self._data.setdefault(symbol, {})[timeframe.value] = df.reset_index(drop=True)

    def load_synthetic(
        self,
        symbol: str = "EURUSD",
        timeframe: Timeframe = Timeframe.H1,
        bars: int = 5000,
        start_price: float = 1.1000,
        volatility: float = 0.0005,
        seed: int = 42,
    ):
        """Generate synthetic OHLCV data for testing."""
        rng = np.random.default_rng(seed)
        timestamps = pd.date_range("2024-01-01", periods=bars, freq="h")
        closes = [start_price]
        for _ in range(bars - 1):
            change = rng.normal(0, volatility)
            closes.append(closes[-1] + change)
        closes = np.array(closes)

        highs = closes + rng.uniform(0, volatility * 2, bars)
        lows = closes - rng.uniform(0, volatility * 2, bars)
        opens = np.roll(closes, 1)
        opens[0] = start_price
        volumes = rng.uniform(100, 10000, bars)

        df = pd.DataFrame({
            "time": timestamps.astype(np.int64) // 10**9,
            "open": opens,
            "high": highs,
            "low": lows,
            "close": closes,
            "volume": volumes,
        })
        self.load(symbol, timeframe, df)

    async def get_ohlcv(
        self,
        symbol: str,
        timeframe: Timeframe,
        count: int = 500,
    ) -> pd.DataFrame:
        tf_data = self._data.get(symbol, {}).get(timeframe.value)
        if tf_data is None:
            raise ValueError(f"No data loaded for {symbol} {timeframe.value}")
        return tf_data.tail(count).reset_index(drop=True)

    async def get_symbols(self) -> list[str]:
        return list(self._data.keys())
