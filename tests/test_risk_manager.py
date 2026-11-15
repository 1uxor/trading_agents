import pytest
from backend.broker.paper_broker import PaperBroker
from backend.broker.base import OrderRequest, Direction
from backend.risk.manager import RiskManager
from backend.risk.models import RiskProfile


@pytest.fixture
def setup():
    broker = PaperBroker(initial_balance=10_000)
    broker.set_price("EURUSD", 1.1000)
    rm = RiskManager(broker)
    profile = RiskProfile(
        max_risk_per_trade_pct=1.0,
        max_open_positions=2,
        max_lot_size=0.5,
        max_daily_loss_pct=5.0,
    )
    return broker, rm, profile


@pytest.mark.asyncio
async def test_mandatory_sl(setup):
    broker, rm, profile = setup
    await broker.connect()
    order = OrderRequest(symbol="EURUSD", direction=Direction.BUY, lot_size=0.1, sl=0, agent_id="a1")
    result = await rm.validate_order(order, profile)
    assert result.approved is False
    assert "stop-loss" in result.reason.lower()


@pytest.mark.asyncio
async def test_max_lot_size(setup):
    broker, rm, profile = setup
    await broker.connect()
    order = OrderRequest(symbol="EURUSD", direction=Direction.BUY, lot_size=1.0, sl=1.0950, agent_id="a1")
    result = await rm.validate_order(order, profile)
    assert result.approved is False
    assert "lot size" in result.reason.lower()


@pytest.mark.asyncio
async def test_approved_order(setup):
    broker, rm, profile = setup
    await broker.connect()
    order = OrderRequest(symbol="EURUSD", direction=Direction.BUY, lot_size=0.01, sl=1.0950, agent_id="a1")
    result = await rm.validate_order(order, profile)
    assert result.approved is True


@pytest.mark.asyncio
async def test_kill_switch_blocks(setup):
    broker, rm, profile = setup
    await broker.connect()
    rm.lock()
    order = OrderRequest(symbol="EURUSD", direction=Direction.BUY, lot_size=0.01, sl=1.0950, agent_id="a1")
    result = await rm.validate_order(order, profile)
    assert result.approved is False
    assert "kill switch" in result.reason.lower()


@pytest.mark.asyncio
async def test_max_positions_per_agent(setup):
    broker, rm, profile = setup
    await broker.connect()

    # Fill up positions
    for _ in range(2):
        await broker.place_order(OrderRequest(
            symbol="EURUSD", direction=Direction.BUY, lot_size=0.01, sl=1.0950, agent_id="a1"
        ))

    order = OrderRequest(symbol="EURUSD", direction=Direction.BUY, lot_size=0.01, sl=1.0950, agent_id="a1")
    result = await rm.validate_order(order, profile)
    assert result.approved is False
    assert "positions" in result.reason.lower()
