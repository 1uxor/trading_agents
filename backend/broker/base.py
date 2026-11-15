from __future__ import annotations

import datetime as dt
from abc import ABC, abstractmethod
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


class Direction(str, Enum):
    BUY = "BUY"
    SELL = "SELL"


class OrderRequest(BaseModel):
    symbol: str
    direction: Direction
    lot_size: float
    sl: float                           # mandatory stop-loss
    tp: Optional[float] = None
    comment: str = ""
    agent_id: str = ""


class OrderResult(BaseModel):
    success: bool
    ticket: Optional[str] = None
    fill_price: Optional[float] = None
    message: str = ""


class Position(BaseModel):
    ticket: str
    symbol: str
    direction: Direction
    lot_size: float
    open_price: float
    current_price: float
    sl: float
    tp: Optional[float] = None
    profit: float = 0.0
    agent_id: str = ""
    opened_at: Optional[dt.datetime] = None


class AccountInfo(BaseModel):
    balance: float
    equity: float
    margin_used: float
    free_margin: float
    currency: str = "USD"


class BrokerAdapter(ABC):
    """Abstract broker interface.  Every order MUST go through the RiskManager first."""

    @abstractmethod
    async def connect(self) -> bool: ...

    @abstractmethod
    async def disconnect(self) -> None: ...

    @abstractmethod
    async def get_account_info(self) -> AccountInfo: ...

    @abstractmethod
    async def place_order(self, order: OrderRequest) -> OrderResult: ...

    @abstractmethod
    async def close_position(self, ticket: str) -> OrderResult: ...

    @abstractmethod
    async def close_all_positions(self) -> list[OrderResult]: ...

    @abstractmethod
    async def get_positions(self, agent_id: str | None = None) -> list[Position]: ...

    @abstractmethod
    async def get_symbol_price(self, symbol: str) -> tuple[float, float]:
        """Return (bid, ask)."""
        ...
