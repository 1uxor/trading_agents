from __future__ import annotations

import datetime as dt
import logging
from typing import Optional

from backend.broker.base import (
    BrokerAdapter, OrderRequest, OrderResult, Position, AccountInfo, Direction,
)
from backend.config import get_settings

logger = logging.getLogger(__name__)


class MT5Broker(BrokerAdapter):
    """Real MetaTrader 5 broker adapter."""

    def __init__(self):
        self._connected = False

    async def connect(self) -> bool:
        import MetaTrader5 as mt5

        settings = get_settings()
        if not mt5.initialize(
            path=settings.mt5_path or None,
            login=settings.mt5_login,
            password=settings.mt5_password,
            server=settings.mt5_server,
        ):
            error = mt5.last_error()
            logger.error("MT5 init failed: %s", error)
            return False

        info = mt5.account_info()
        if info is None:
            logger.error("MT5 account info unavailable")
            return False

        logger.info(
            "MT5 connected: account=%d server=%s balance=%.2f",
            info.login, info.server, info.balance,
        )
        self._connected = True
        return True

    async def disconnect(self) -> None:
        import MetaTrader5 as mt5
        mt5.shutdown()
        self._connected = False

    async def get_account_info(self) -> AccountInfo:
        import MetaTrader5 as mt5
        info = mt5.account_info()
        if info is None:
            raise RuntimeError("MT5 account info unavailable")
        return AccountInfo(
            balance=info.balance,
            equity=info.equity,
            margin_used=info.margin,
            free_margin=info.margin_free,
            currency=info.currency,
        )

    async def place_order(self, order: OrderRequest) -> OrderResult:
        import MetaTrader5 as mt5

        symbol_info = mt5.symbol_info(order.symbol)
        if symbol_info is None:
            return OrderResult(success=False, message=f"Symbol {order.symbol} not found")

        if not symbol_info.visible:
            mt5.symbol_select(order.symbol, True)

        tick = mt5.symbol_info_tick(order.symbol)
        if tick is None:
            return OrderResult(success=False, message=f"No tick data for {order.symbol}")

        price = tick.ask if order.direction == Direction.BUY else tick.bid
        order_type = mt5.ORDER_TYPE_BUY if order.direction == Direction.BUY else mt5.ORDER_TYPE_SELL

        request = {
            "action": mt5.TRADE_ACTION_DEAL,
            "symbol": order.symbol,
            "volume": order.lot_size,
            "type": order_type,
            "price": price,
            "sl": order.sl,
            "tp": order.tp if order.tp else 0.0,
            "deviation": 20,
            "magic": 234000,
            "comment": order.comment[:31],  # MT5 comment limit
            "type_time": mt5.ORDER_TIME_GTC,
            "type_filling": mt5.ORDER_FILLING_IOC,
        }

        result = mt5.order_send(request)
        if result is None:
            return OrderResult(success=False, message="order_send returned None")

        if result.retcode != mt5.TRADE_RETCODE_DONE:
            return OrderResult(
                success=False,
                message=f"MT5 error {result.retcode}: {result.comment}",
            )

        return OrderResult(
            success=True,
            ticket=str(result.order),
            fill_price=result.price,
            message=f"Filled: {result.comment}",
        )

    async def close_position(self, ticket: str) -> OrderResult:
        import MetaTrader5 as mt5

        positions = mt5.positions_get(ticket=int(ticket))
        if not positions:
            return OrderResult(success=False, message=f"Position {ticket} not found")

        pos = positions[0]
        tick = mt5.symbol_info_tick(pos.symbol)
        if tick is None:
            return OrderResult(success=False, message=f"No tick for {pos.symbol}")

        # Reverse direction to close
        close_type = mt5.ORDER_TYPE_SELL if pos.type == mt5.ORDER_TYPE_BUY else mt5.ORDER_TYPE_BUY
        close_price = tick.bid if pos.type == mt5.ORDER_TYPE_BUY else tick.ask

        request = {
            "action": mt5.TRADE_ACTION_DEAL,
            "symbol": pos.symbol,
            "volume": pos.volume,
            "type": close_type,
            "position": pos.ticket,
            "price": close_price,
            "deviation": 20,
            "magic": 234000,
            "comment": "close",
            "type_time": mt5.ORDER_TIME_GTC,
            "type_filling": mt5.ORDER_FILLING_IOC,
        }

        result = mt5.order_send(request)
        if result is None:
            return OrderResult(success=False, message="close order_send returned None")

        if result.retcode != mt5.TRADE_RETCODE_DONE:
            return OrderResult(success=False, message=f"Close error {result.retcode}: {result.comment}")

        return OrderResult(
            success=True,
            ticket=ticket,
            fill_price=result.price,
            message=f"Closed: PnL={pos.profit:.2f}",
        )

    async def close_all_positions(self) -> list[OrderResult]:
        import MetaTrader5 as mt5
        positions = mt5.positions_get()
        results = []
        for pos in (positions or []):
            results.append(await self.close_position(str(pos.ticket)))
        return results

    async def get_positions(self, agent_id: str | None = None) -> list[Position]:
        import MetaTrader5 as mt5
        positions = mt5.positions_get() or []
        result = []
        for pos in positions:
            direction = Direction.BUY if pos.type == mt5.ORDER_TYPE_BUY else Direction.SELL
            p = Position(
                ticket=str(pos.ticket),
                symbol=pos.symbol,
                direction=direction,
                lot_size=pos.volume,
                open_price=pos.price_open,
                current_price=pos.price_current,
                sl=pos.sl,
                tp=pos.tp if pos.tp else None,
                profit=pos.profit,
                agent_id=pos.comment.split("|")[0] if pos.comment else "",
                opened_at=dt.datetime.fromtimestamp(pos.time),
            )
            result.append(p)

        if agent_id:
            result = [p for p in result if p.agent_id == agent_id]
        return result

    async def get_symbol_price(self, symbol: str) -> tuple[float, float]:
        import MetaTrader5 as mt5
        tick = mt5.symbol_info_tick(symbol)
        if tick is None:
            raise ValueError(f"No tick data for {symbol}")
        return (tick.bid, tick.ask)
