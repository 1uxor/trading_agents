from __future__ import annotations

from abc import ABC, abstractmethod
from enum import Enum
from typing import Optional

import numpy as np
import pandas as pd
from pydantic import BaseModel


class Timeframe(str, Enum):
    M1 = "M1"
    M5 = "M5"
    M15 = "M15"
    M30 = "M30"
    H1 = "H1"
    H4 = "H4"
    D1 = "D1"
    W1 = "W1"
    MN1 = "MN1"


class OHLCV(BaseModel):
    """Single candle."""
    timestamp: float
    open: float
    high: float
    low: float
    close: float
    volume: float


class MarketDataProvider(ABC):
    """Fetch OHLCV bars for any symbol / timeframe."""

    @abstractmethod
    async def get_ohlcv(
        self,
        symbol: str,
        timeframe: Timeframe,
        count: int = 500,
    ) -> pd.DataFrame:
        """Return a DataFrame with columns: time, open, high, low, close, volume.
        Sorted oldest-first, indexed 0..N-1.
        """
        ...

    @abstractmethod
    async def get_symbols(self) -> list[str]:
        """Return list of available symbols."""
        ...
