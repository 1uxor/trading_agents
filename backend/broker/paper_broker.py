from __future__ import annotations

import datetime as dt
import uuid
from typing import Optional

from backend.broker.base import (
    BrokerAdapter, OrderRequest, OrderResult, Position, AccountInfo, Direction,
)


class PaperBroker(BrokerAdapter):
    """In-memory simulated broker for paper trading and backtesting."""

    def __init__(
        self,
        initial_balance: float = 10_000.0,
        spread_pips: float = 1.0,
        commission_per_lot: float = 7.0,
        currency: str = "USD",
    ):
        self._balance = initial_balance
        self._equity = initial_balance
        self._spread_pips = spread_pips
        self._commission_per_lot = commission_per_lot
        self._currency = currency

        self._positions: dict[str, Position] = {}
        self._prices: dict[str, tuple[float, float]] = {}   # symbol -> (bid, ask)
        self._connected = False
        self._daily_pnl = 0.0

    # ── Connection ──────────────────────────────────────────────────────────

    async def connect(self) -> bool:
        self._connected = True
        return True

    async def disconnect(self) -> None:
        self._connected = False

    # ── Account ─────────────────────────────────────────────────────────────

    async def get_account_info(self) -> AccountInfo:
        floating = sum(p.profit for p in self._positions.values())
        self._equity = self._balance + floating
        return AccountInfo(
            balance=self._balance,
            equity=self._equity,
            margin_used=0.0,
            free_margin=self._equity,
            currency=self._currency,
        )

    # ── Price feed (set externally or via market data) ──────────────────────

    def set_price(self, symbol: str, bid: float, ask: float | None = None):
        if ask is None:
            half_spread = self._spread_pips * 0.0001 / 2
            ask = bid + half_spread * 2
        self._prices[symbol] = (bid, ask)
        self._update_floating()

    async def get_symbol_price(self, symbol: str) -> tuple[float, float]:
        if symbol not in self._prices:
            raise ValueError(f"No price data for {symbol}")
        return self._prices[symbol]

    # ── Orders ──────────────────────────────────────────────────────────────

    async def place_order(self, order: OrderRequest) -> OrderResult:
        if order.symbol not in self._prices:
            return OrderResult(success=False, message=f"No price for {order.symbol}")

        bid, ask = self._prices[order.symbol]
        fill_price = ask if order.direction == Direction.BUY else bid

        commission = self._commission_per_lot * order.lot_size
        self._balance -= commission

        ticket = str(uuid.uuid4())[:8]
        pos = Position(
            ticket=ticket,
            symbol=order.symbol,
            direction=order.direction,
            lot_size=order.lot_size,
            open_price=fill_price,
            current_price=fill_price,
            sl=order.sl,
            tp=order.tp,
            profit=-commission,
            agent_id=order.agent_id,
            opened_at=dt.datetime.utcnow(),
        )
        self._positions[ticket] = pos

        return OrderResult(success=True, ticket=ticket, fill_price=fill_price, message="Paper fill")

    async def close_position(self, ticket: str) -> OrderResult:
        pos = self._positions.pop(ticket, None)
        if pos is None:
            return OrderResult(success=False, message=f"Position {ticket} not found")

        bid, ask = self._prices.get(pos.symbol, (pos.current_price, pos.current_price))
        close_price = bid if pos.direction == Direction.BUY else ask

        # PnL: for BUY, profit = (close - open) * lot * 100_000
        multiplier = 100_000 * pos.lot_size
        if pos.direction == Direction.BUY:
            pnl = (close_price - pos.open_price) * multiplier
        else:
            pnl = (pos.open_price - close_price) * multiplier

        self._balance += pnl
        self._daily_pnl += pnl

        return OrderResult(
            success=True,
            ticket=ticket,
            fill_price=close_price,
            message=f"Closed. PnL: {pnl:.2f}",
        )

    async def close_all_positions(self) -> list[OrderResult]:
        results = []
        for ticket in list(self._positions.keys()):
            results.append(await self.close_position(ticket))
        return results

    async def get_positions(self, agent_id: str | None = None) -> list[Position]:
        self._update_floating()
        positions = list(self._positions.values())
        if agent_id:
            positions = [p for p in positions if p.agent_id == agent_id]
        return positions

    # ── Internal ────────────────────────────────────────────────────────────

    def _update_floating(self):
        for pos in self._positions.values():
            prices = self._prices.get(pos.symbol)
            if not prices:
                continue
            bid, ask = prices
            pos.current_price = bid if pos.direction == Direction.BUY else ask
            multiplier = 100_000 * pos.lot_size
            if pos.direction == Direction.BUY:
                pos.profit = (bid - pos.open_price) * multiplier
            else:
                pos.profit = (pos.open_price - ask) * multiplier

    def reset_daily_pnl(self):
        self._daily_pnl = 0.0

    @property
    def daily_pnl(self) -> float:
        return self._daily_pnl
