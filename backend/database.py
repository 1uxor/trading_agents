from __future__ import annotations

import datetime as dt
from typing import AsyncGenerator

from sqlalchemy import (
    Column, Integer, Float, String, Text, DateTime, Boolean, Enum as SAEnum,
    ForeignKey, JSON, func,
)
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase, relationship

from backend.config import get_settings


class Base(DeclarativeBase):
    pass


# ── ORM models ──────────────────────────────────────────────────────────────


class DBAgent(Base):
    __tablename__ = "agents"

    id = Column(String, primary_key=True)
    name = Column(String, nullable=False)
    color = Column(String, nullable=False, default="#3498DB")
    symbols = Column(JSON, nullable=False)          # list[str]
    timeframe = Column(String, nullable=False)
    model_provider = Column(String, nullable=False)
    model_config_json = Column(JSON, default=dict)
    strategy_name = Column(String, nullable=False)
    strategy_params = Column(JSON, default=dict)
    combiner_mode = Column(String, nullable=True)
    combiner_config = Column(JSON, nullable=True)
    risk_profile = Column(JSON, default=dict)
    schedule_seconds = Column(Integer, default=60)
    enabled = Column(Boolean, default=True)
    created_at = Column(DateTime, default=func.now())

    trades = relationship("DBTrade", back_populates="agent", lazy="selectin")
    signals = relationship("DBSignalLog", back_populates="agent", lazy="selectin")


class DBTrade(Base):
    __tablename__ = "trades"

    id = Column(Integer, primary_key=True, autoincrement=True)
    agent_id = Column(String, ForeignKey("agents.id"), nullable=False)
    symbol = Column(String, nullable=False)
    direction = Column(String, nullable=False)      # BUY / SELL
    lot_size = Column(Float, nullable=False)
    entry_price = Column(Float, nullable=True)
    exit_price = Column(Float, nullable=True)
    sl = Column(Float, nullable=True)
    tp = Column(Float, nullable=True)
    profit = Column(Float, nullable=True)
    commission = Column(Float, default=0.0)
    status = Column(String, default="open")         # open / closed / cancelled
    opened_at = Column(DateTime, default=func.now())
    closed_at = Column(DateTime, nullable=True)
    broker_ticket = Column(String, nullable=True)
    metadata_json = Column(JSON, default=dict)

    agent = relationship("DBAgent", back_populates="trades")


class DBSignalLog(Base):
    __tablename__ = "signal_log"

    id = Column(Integer, primary_key=True, autoincrement=True)
    agent_id = Column(String, ForeignKey("agents.id"), nullable=False)
    timestamp = Column(DateTime, default=func.now())
    symbol = Column(String, nullable=False)
    model_provider = Column(String, nullable=False)
    strategy_name = Column(String, nullable=False)
    inputs_summary = Column(Text, nullable=True)
    signal = Column(String, nullable=False)         # BUY / SELL / HOLD
    confidence = Column(Float, nullable=True)
    reasoning = Column(Text, nullable=True)
    risk_check_result = Column(String, nullable=True)  # approved / rejected
    risk_check_reason = Column(Text, nullable=True)
    order_result = Column(Text, nullable=True)

    agent = relationship("DBAgent", back_populates="signals")


class DBEquitySnapshot(Base):
    __tablename__ = "equity_snapshots"

    id = Column(Integer, primary_key=True, autoincrement=True)
    timestamp = Column(DateTime, default=func.now())
    equity = Column(Float, nullable=False)
    balance = Column(Float, nullable=False)
    margin_used = Column(Float, default=0.0)
    open_positions = Column(Integer, default=0)
    daily_pnl = Column(Float, default=0.0)


# ── Engine / session ────────────────────────────────────────────────────────


_engine = None
_session_factory = None


def get_engine():
    global _engine
    if _engine is None:
        _engine = create_async_engine(get_settings().database_url, echo=False)
    return _engine


def get_session_factory() -> async_sessionmaker[AsyncSession]:
    global _session_factory
    if _session_factory is None:
        _session_factory = async_sessionmaker(get_engine(), expire_on_commit=False)
    return _session_factory


async def get_session() -> AsyncGenerator[AsyncSession, None]:
    factory = get_session_factory()
    async with factory() as session:
        yield session


async def init_db():
    engine = get_engine()
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
