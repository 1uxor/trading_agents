from __future__ import annotations

import logging
from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession

from backend.database import DBSignalLog, DBTrade, DBEquitySnapshot, get_session_factory

logger = logging.getLogger(__name__)


class TradeLogger:
    """Structured decision + trade logger that writes to SQLite."""

    async def log_signal(
        self,
        agent_id: str,
        symbol: str,
        model_provider: str,
        strategy_name: str,
        inputs_summary: str,
        signal: str,
        confidence: float | None,
        reasoning: str | None,
        risk_check_result: str,
        risk_check_reason: str,
        order_result: str | None,
    ) -> int:
        factory = get_session_factory()
        async with factory() as session:
            row = DBSignalLog(
                agent_id=agent_id,
                symbol=symbol,
                model_provider=model_provider,
                strategy_name=strategy_name,
                inputs_summary=inputs_summary,
                signal=signal,
                confidence=confidence,
                reasoning=reasoning,
                risk_check_result=risk_check_result,
                risk_check_reason=risk_check_reason,
                order_result=order_result,
            )
            session.add(row)
            await session.commit()
            logger.info(
                "Signal logged | agent=%s symbol=%s signal=%s conf=%.2f risk=%s",
                agent_id, symbol, signal, confidence or 0, risk_check_result,
            )
            return row.id

    async def log_trade(
        self,
        agent_id: str,
        symbol: str,
        direction: str,
        lot_size: float,
        entry_price: float | None,
        sl: float | None,
        tp: float | None,
        broker_ticket: str | None,
        status: str = "open",
    ) -> int:
        factory = get_session_factory()
        async with factory() as session:
            row = DBTrade(
                agent_id=agent_id,
                symbol=symbol,
                direction=direction,
                lot_size=lot_size,
                entry_price=entry_price,
                sl=sl,
                tp=tp,
                broker_ticket=broker_ticket,
                status=status,
            )
            session.add(row)
            await session.commit()
            return row.id

    async def close_trade(
        self,
        broker_ticket: str,
        exit_price: float,
        profit: float,
    ):
        factory = get_session_factory()
        async with factory() as session:
            from sqlalchemy import select, update
            import datetime as dt
            stmt = (
                update(DBTrade)
                .where(DBTrade.broker_ticket == broker_ticket)
                .values(
                    exit_price=exit_price,
                    profit=profit,
                    status="closed",
                    closed_at=dt.datetime.utcnow(),
                )
            )
            await session.execute(stmt)
            await session.commit()

    async def log_equity_snapshot(
        self,
        equity: float,
        balance: float,
        margin_used: float = 0.0,
        open_positions: int = 0,
        daily_pnl: float = 0.0,
    ):
        factory = get_session_factory()
        async with factory() as session:
            row = DBEquitySnapshot(
                equity=equity,
                balance=balance,
                margin_used=margin_used,
                open_positions=open_positions,
                daily_pnl=daily_pnl,
            )
            session.add(row)
            await session.commit()
