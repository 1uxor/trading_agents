from __future__ import annotations

import logging

import pandas as pd

from backend.market_data.provider import MarketDataProvider, Timeframe

logger = logging.getLogger(__name__)

# Map our Timeframe enum to MT5 timeframe constants
_TF_MAP = {
    Timeframe.M1: 1,       # mt5.TIMEFRAME_M1
    Timeframe.M5: 5,
    Timeframe.M15: 15,
    Timeframe.M30: 30,
    Timeframe.H1: 16385,   # mt5.TIMEFRAME_H1
    Timeframe.H4: 16388,
    Timeframe.D1: 16408,
    Timeframe.W1: 32769,
    Timeframe.MN1: 49153,
}


class MT5DataProvider(MarketDataProvider):
    """Fetch OHLCV from a live MT5 terminal."""

    async def get_ohlcv(
        self,
        symbol: str,
        timeframe: Timeframe,
        count: int = 500,
    ) -> pd.DataFrame:
        import MetaTrader5 as mt5

        mt5_tf = _TF_MAP.get(timeframe)
        if mt5_tf is None:
            raise ValueError(f"Unsupported timeframe: {timeframe}")

        rates = mt5.copy_rates_from_pos(symbol, mt5_tf, 0, count)
        if rates is None or len(rates) == 0:
            raise ValueError(f"No data from MT5 for {symbol} {timeframe.value}")

        df = pd.DataFrame(rates)
        df = df.rename(columns={
            "time": "time",
            "open": "open",
            "high": "high",
            "low": "low",
            "close": "close",
            "tick_volume": "volume",
        })
        df = df[["time", "open", "high", "low", "close", "volume"]]
        return df.reset_index(drop=True)

    async def get_symbols(self) -> list[str]:
        import MetaTrader5 as mt5
        symbols = mt5.symbols_get()
        if symbols is None:
            return []
        return [s.name for s in symbols if s.visible]
