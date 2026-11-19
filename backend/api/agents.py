from __future__ import annotations

import logging
from typing import Any

import pandas as pd
from fastapi import APIRouter, HTTPException, Depends, Query
from pydantic import BaseModel
from sqlalchemy import select, delete as sa_delete, func as sa_func, case

from backend.agent.schemas import AgentConfig
from backend.api.dependencies import get_runner, get_market_data
from backend.database import DBAgent, DBTrade, DBSignalLog, get_session_factory
from backend.market_data.provider import MarketDataProvider, Timeframe

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/agents", tags=["agents"])


class AgentCreateRequest(BaseModel):
    config: AgentConfig


class AgentActionRequest(BaseModel):
    action: str   # start | stop | pause | resume


@router.get("")
async def list_agents(runner=Depends(get_runner)):
    return runner.status_summary()


@router.post("")
async def create_agent(req: AgentCreateRequest, runner=Depends(get_runner)):
    agent = runner.create_agent(req.config)

    # Persist to database
    factory = get_session_factory()
    async with factory() as session:
        cfg = agent.config
        db_agent = DBAgent(
            id=agent.id,
            name=cfg.name,
            color=cfg.color,
            symbols=cfg.symbols,
            timeframe=cfg.timeframe,
            model_provider=cfg.model_provider,
            model_config_json=cfg.model_config_ or {},
            strategies_json=[s.model_dump() for s in cfg.strategies],
            combiner_json=cfg.combiner.model_dump() if cfg.combiner else None,
            risk_profile=cfg.risk_profile.model_dump(),
            schedule_seconds=cfg.schedule_seconds,
            enabled=cfg.enabled,
        )
        session.add(db_agent)
        await session.commit()
        logger.info("Agent %s persisted to database", agent.id)

    return {"id": agent.id, "name": agent.name, "state": agent.state.value}


@router.get("/leaderboard")
async def leaderboard():
    factory = get_session_factory()
    async with factory() as session:
        # Aggregate trade stats per agent (closed trades only)
        stmt = (
            select(
                DBTrade.agent_id,
                sa_func.count().label("total_trades"),
                sa_func.sum(case((DBTrade.profit > 0, 1), else_=0)).label("wins"),
                sa_func.sum(case((DBTrade.profit <= 0, 1), else_=0)).label("losses"),
                sa_func.coalesce(sa_func.sum(DBTrade.profit), 0).label("total_profit"),
                sa_func.coalesce(sa_func.avg(DBTrade.profit), 0).label("avg_profit"),
                sa_func.coalesce(sa_func.max(DBTrade.profit), 0).label("best_trade"),
                sa_func.coalesce(sa_func.min(DBTrade.profit), 0).label("worst_trade"),
            )
            .where(DBTrade.status == "closed")
            .group_by(DBTrade.agent_id)
        )
        trade_stats = {row.agent_id: row for row in (await session.execute(stmt)).all()}

        # Get all agents
        agents_result = await session.execute(select(DBAgent))
        agents = agents_result.scalars().all()

        rows = []
        for a in agents:
            stats = trade_stats.get(a.id)
            total = stats.total_trades if stats else 0
            wins = stats.wins if stats else 0
            rows.append({
                "agent_id": a.id,
                "name": a.name,
                "color": a.color,
                "symbols": a.symbols,
                "strategies": [s.get("name", "") for s in (a.strategies_json or [])],
                "total_trades": total,
                "wins": wins,
                "losses": stats.losses if stats else 0,
                "win_rate": round(wins / total * 100, 1) if total > 0 else 0,
                "total_profit": round(float(stats.total_profit), 2) if stats else 0,
                "avg_profit": round(float(stats.avg_profit), 2) if stats else 0,
                "best_trade": round(float(stats.best_trade), 2) if stats else 0,
                "worst_trade": round(float(stats.worst_trade), 2) if stats else 0,
            })

        rows.sort(key=lambda r: r["total_profit"], reverse=True)
        return rows


@router.get("/{agent_id}")
async def get_agent(agent_id: str, runner=Depends(get_runner)):
    agent = runner.get_agent(agent_id)
    if not agent:
        raise HTTPException(404, "Agent not found")
    return {
        "id": agent.id,
        "name": agent.name,
        "state": agent.state.value,
        "config": agent.config.model_dump(by_alias=True),
    }


@router.post("/{agent_id}/action")
async def agent_action(agent_id: str, req: AgentActionRequest, runner=Depends(get_runner)):
    actions = {
        "start": runner.start_agent,
        "stop": runner.stop_agent,
        "pause": runner.pause_agent,
        "resume": runner.resume_agent,
    }
    fn = actions.get(req.action)
    if not fn:
        raise HTTPException(400, f"Unknown action: {req.action}")
    ok = fn(agent_id)
    if not ok:
        raise HTTPException(404, "Agent not found")
    agent = runner.get_agent(agent_id)
    return {"id": agent_id, "state": agent.state.value if agent else "unknown"}


@router.delete("/{agent_id}")
async def delete_agent(agent_id: str, runner=Depends(get_runner)):
    if not runner.remove_agent(agent_id):
        raise HTTPException(404, "Agent not found")

    # Remove from database
    factory = get_session_factory()
    async with factory() as session:
        await session.execute(sa_delete(DBAgent).where(DBAgent.id == agent_id))
        await session.commit()
        logger.info("Agent %s removed from database", agent_id)

    return {"deleted": agent_id}


@router.get("/{agent_id}/commentary")
async def get_commentary(agent_id: str, runner=Depends(get_runner)):
    agent = runner.get_agent(agent_id)
    if not agent:
        raise HTTPException(404, "Agent not found")
    return [e.model_dump() for e in agent.commentary.history]


@router.get("/{agent_id}/trades")
async def get_agent_trades(agent_id: str, limit: int = Query(100, ge=1, le=1000)):
    factory = get_session_factory()
    async with factory() as session:
        stmt = (
            select(DBTrade)
            .where(DBTrade.agent_id == agent_id)
            .order_by(DBTrade.opened_at.desc())
            .limit(limit)
        )
        result = await session.execute(stmt)
        trades = result.scalars().all()
        return [
            {
                "id": t.id,
                "symbol": t.symbol,
                "direction": t.direction,
                "lot_size": t.lot_size,
                "entry_price": t.entry_price,
                "exit_price": t.exit_price,
                "sl": t.sl,
                "tp": t.tp,
                "profit": t.profit,
                "status": t.status,
                "opened_at": t.opened_at.isoformat() if t.opened_at else None,
                "closed_at": t.closed_at.isoformat() if t.closed_at else None,
                "broker_ticket": t.broker_ticket,
            }
            for t in trades
        ]


@router.get("/{agent_id}/signals")
async def get_agent_signals(agent_id: str, limit: int = Query(100, ge=1, le=1000)):
    factory = get_session_factory()
    async with factory() as session:
        stmt = (
            select(DBSignalLog)
            .where(DBSignalLog.agent_id == agent_id)
            .order_by(DBSignalLog.timestamp.desc())
            .limit(limit)
        )
        result = await session.execute(stmt)
        signals = result.scalars().all()
        return [
            {
                "id": s.id,
                "timestamp": s.timestamp.isoformat() if s.timestamp else None,
                "symbol": s.symbol,
                "strategy_name": s.strategy_name,
                "signal": s.signal,
                "confidence": s.confidence,
                "reasoning": s.reasoning,
                "risk_check_result": s.risk_check_result,
                "risk_check_reason": s.risk_check_reason,
                "order_result": s.order_result,
            }
            for s in signals
        ]


@router.get("/{agent_id}/indicators")
async def get_agent_indicators(
    agent_id: str,
    symbol: str = Query(...),
    timeframe: str = Query("H1"),
    count: int = Query(200, ge=50, le=2000),
    runner=Depends(get_runner),
    market_data: MarketDataProvider = Depends(get_market_data),
):
    agent = runner.get_agent(agent_id)
    if not agent:
        raise HTTPException(404, "Agent not found")

    tf = Timeframe(timeframe)
    df = await market_data.get_ohlcv(symbol, tf, count)

    indicators: list[dict] = []

    for strat_cfg in agent.config.strategies:
        params = strat_cfg.params
        name = strat_cfg.name

        if name == "ma_crossover":
            import ta
            close = df["close"]
            fast = int(params.get("fast_period", 20))
            slow = int(params.get("slow_period", 50))
            ma_type = params.get("ma_type", "SMA")
            if ma_type == "EMA":
                fast_vals = ta.trend.EMAIndicator(close, window=fast).ema_indicator()
                slow_vals = ta.trend.EMAIndicator(close, window=slow).ema_indicator()
            else:
                fast_vals = ta.trend.SMAIndicator(close, window=fast).sma_indicator()
                slow_vals = ta.trend.SMAIndicator(close, window=slow).sma_indicator()

            indicators.append({
                "strategy": name, "type": "line",
                "label": f"{ma_type}({fast})", "color": "#2196F3",
                "data": [{"time": int(t), "value": round(float(v), 5)}
                         for t, v in zip(df["time"], fast_vals) if not pd.isna(v)],
            })
            indicators.append({
                "strategy": name, "type": "line",
                "label": f"{ma_type}({slow})", "color": "#FF9800",
                "data": [{"time": int(t), "value": round(float(v), 5)}
                         for t, v in zip(df["time"], slow_vals) if not pd.isna(v)],
            })

        elif name == "breakout":
            period = int(params.get("channel_period", 20))
            upper = df["high"].rolling(window=period).max().shift(1)
            lower = df["low"].rolling(window=period).min().shift(1)
            indicators.append({
                "strategy": name, "type": "line",
                "label": f"Donchian Upper({period})", "color": "#4CAF50",
                "data": [{"time": int(t), "value": round(float(v), 5)}
                         for t, v in zip(df["time"], upper) if not pd.isna(v)],
            })
            indicators.append({
                "strategy": name, "type": "line",
                "label": f"Donchian Lower({period})", "color": "#F44336",
                "data": [{"time": int(t), "value": round(float(v), 5)}
                         for t, v in zip(df["time"], lower) if not pd.isna(v)],
            })

        elif name == "rsi_reversion":
            import ta
            rsi_period = int(params.get("rsi_period", 14))
            rsi_vals = ta.momentum.RSIIndicator(df["close"], window=rsi_period).rsi()
            indicators.append({
                "strategy": name, "type": "rsi",
                "label": f"RSI({rsi_period})", "color": "#9C27B0",
                "oversold": params.get("oversold", 30),
                "overbought": params.get("overbought", 70),
                "data": [{"time": int(t), "value": round(float(v), 2)}
                         for t, v in zip(df["time"], rsi_vals) if not pd.isna(v)],
            })

        elif name == "forecast_driven":
            indicators.append({
                "strategy": name, "type": "forecast_placeholder",
                "label": "Forecast", "color": "#00BCD4", "data": [],
            })

    return {"indicators": indicators}
