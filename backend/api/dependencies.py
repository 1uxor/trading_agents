"""FastAPI dependency injection for shared singletons."""
from __future__ import annotations

from backend.agent.runner import AgentRunner
from backend.broker.base import BrokerAdapter
from backend.logging_.trade_logger import TradeLogger
from backend.market_data.provider import MarketDataProvider
from backend.risk.manager import RiskManager

# These are set during app startup (in main.py lifespan)
_broker: BrokerAdapter | None = None
_market_data: MarketDataProvider | None = None
_risk_manager: RiskManager | None = None
_trade_logger: TradeLogger | None = None
_runner: AgentRunner | None = None


def set_instances(
    broker: BrokerAdapter,
    market_data: MarketDataProvider,
    risk_manager: RiskManager,
    trade_logger: TradeLogger,
    runner: AgentRunner,
):
    global _broker, _market_data, _risk_manager, _trade_logger, _runner
    _broker = broker
    _market_data = market_data
    _risk_manager = risk_manager
    _trade_logger = trade_logger
    _runner = runner


def get_broker() -> BrokerAdapter:
    assert _broker is not None
    return _broker


def get_market_data() -> MarketDataProvider:
    assert _market_data is not None
    return _market_data


def get_risk_manager() -> RiskManager:
    assert _risk_manager is not None
    return _risk_manager


def get_trade_logger() -> TradeLogger:
    assert _trade_logger is not None
    return _trade_logger


def get_runner() -> AgentRunner:
    assert _runner is not None
    return _runner
