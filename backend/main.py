from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware

from backend.config import get_settings
from backend.database import init_db

# Import all model providers and strategies to trigger registration
import backend.models.no_model
import backend.models.openai_provider
import backend.models.anthropic_provider
import backend.models.gemini_provider
import backend.models.ollama_provider
import backend.models.hf_forecaster
import backend.strategies.ma_crossover
import backend.strategies.rsi_reversion
import backend.strategies.breakout
import backend.strategies.forecast_driven
import backend.strategies.llm_discretionary

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup / shutdown."""
    logger.info("Starting Trading Agents platform...")

    # Init DB
    await init_db()

    # Create broker (paper by default)
    settings = get_settings()

    from backend.broker.paper_broker import PaperBroker
    from backend.market_data.paper_data import PaperDataProvider
    from backend.market_data.cache import CachedMarketData
    from backend.risk.manager import RiskManager
    from backend.logging_.trade_logger import TradeLogger
    from backend.agent.runner import AgentRunner
    from backend.api.ws import commentary_broadcast_callback
    from backend.api.dependencies import set_instances

    broker = PaperBroker(initial_balance=10_000.0)
    await broker.connect()

    # Paper data provider with synthetic data
    paper_data = PaperDataProvider()
    paper_data.load_synthetic("EURUSD", bars=5000, start_price=1.1000)
    paper_data.load_synthetic("GBPUSD", bars=5000, start_price=1.2700, seed=99)
    paper_data.load_synthetic("USDJPY", bars=5000, start_price=149.50, volatility=0.05, seed=77)

    # Set prices on paper broker
    import pandas as pd
    from backend.market_data.provider import Timeframe
    for sym in ["EURUSD", "GBPUSD", "USDJPY"]:
        df = await paper_data.get_ohlcv(sym, Timeframe.H1, 1)
        price = df["close"].iloc[-1]
        broker.set_price(sym, price)

    market_data = CachedMarketData(paper_data, ttl_seconds=10)
    risk_manager = RiskManager(broker)
    trade_logger = TradeLogger()
    runner = AgentRunner(
        broker=broker,
        market_data=market_data,
        risk_manager=risk_manager,
        trade_logger=trade_logger,
        commentary_callback=commentary_broadcast_callback,
    )

    set_instances(broker, market_data, risk_manager, trade_logger, runner)

    # Restore agents from database
    from backend.database import DBAgent, get_session_factory
    from backend.agent.schemas import AgentConfig, StrategyConfig, CombinerConfig
    from backend.risk.models import RiskProfile

    factory = get_session_factory()
    async with factory() as session:
        from sqlalchemy import select
        result = await session.execute(select(DBAgent))
        db_agents = result.scalars().all()
        for dba in db_agents:
            try:
                config = AgentConfig(
                    id=dba.id,
                    name=dba.name,
                    color=dba.color,
                    symbols=dba.symbols,
                    timeframe=dba.timeframe,
                    model_provider=dba.model_provider,
                    model_config=dba.model_config_json or {},
                    strategies=[StrategyConfig(**s) for s in (dba.strategies_json or [])],
                    combiner=CombinerConfig(**dba.combiner_json) if dba.combiner_json else None,
                    risk_profile=RiskProfile(**(dba.risk_profile or {})),
                    schedule_seconds=dba.schedule_seconds,
                    enabled=dba.enabled,
                )
                runner.create_agent(config)
                logger.info("Restored agent %s (%s) from database", dba.id, dba.name)
            except Exception as e:
                logger.error("Failed to restore agent %s: %s", dba.id, e)

    # Try to connect MT5 if credentials exist
    if settings.mt5_login and settings.mt5_password and settings.live_trading:
        logger.info("MT5 credentials found — but live trading requires UI confirmation")

    logger.info("Platform ready (paper trading mode)")

    yield

    # Shutdown
    logger.info("Shutting down...")
    for agent in runner.list_agents():
        agent.stop()
    await broker.disconnect()


app = FastAPI(
    title="Trading Agents Platform",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Routes ──────────────────────────────────────────────────────────────────

from backend.api.agents import router as agents_router
from backend.api.market import router as market_router
from backend.api.risk import router as risk_router
from backend.api.backtest import router as backtest_router
from backend.api.strategies import router as config_router
from backend.api.data_upload import router as data_router

app.include_router(agents_router)
app.include_router(market_router)
app.include_router(risk_router)
app.include_router(backtest_router)
app.include_router(config_router)
app.include_router(data_router)


# ── WebSocket ───────────────────────────────────────────────────────────────

from backend.api.ws import ws_hub


@app.websocket("/ws")
async def websocket_endpoint(ws: WebSocket):
    await ws_hub.connect(ws)
    try:
        while True:
            # Keep alive — client can send pings
            await ws.receive_text()
    except WebSocketDisconnect:
        await ws_hub.disconnect(ws)


# ── Health ──────────────────────────────────────────────────────────────────

@app.get("/api/health")
async def health():
    return {"status": "ok", "ws_clients": ws_hub.client_count}
