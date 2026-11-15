import pytest
from backend.broker.paper_broker import PaperBroker
from backend.broker.base import OrderRequest, Direction


@pytest.fixture
def broker():
    b = PaperBroker(initial_balance=10_000, spread_pips=1.0, commission_per_lot=7.0)
    b.set_price("EURUSD", 1.1000)
    return b


@pytest.mark.asyncio
async def test_connect(broker):
    assert await broker.connect() is True


@pytest.mark.asyncio
async def test_account_info(broker):
    await broker.connect()
    info = await broker.get_account_info()
    assert info.balance == 10_000
    assert info.equity == 10_000


@pytest.mark.asyncio
async def test_place_order(broker):
    await broker.connect()
    order = OrderRequest(
        symbol="EURUSD", direction=Direction.BUY, lot_size=0.1,
        sl=1.0950, agent_id="test"
    )
    result = await broker.place_order(order)
    assert result.success is True
    assert result.ticket is not None

    positions = await broker.get_positions()
    assert len(positions) == 1
    assert positions[0].symbol == "EURUSD"


@pytest.mark.asyncio
async def test_close_position(broker):
    await broker.connect()
    order = OrderRequest(
        symbol="EURUSD", direction=Direction.BUY, lot_size=0.1,
        sl=1.0950, agent_id="test"
    )
    result = await broker.place_order(order)

    # Move price up
    broker.set_price("EURUSD", 1.1050)
    close_result = await broker.close_position(result.ticket)
    assert close_result.success is True

    positions = await broker.get_positions()
    assert len(positions) == 0


@pytest.mark.asyncio
async def test_close_all(broker):
    await broker.connect()
    for _ in range(3):
        await broker.place_order(OrderRequest(
            symbol="EURUSD", direction=Direction.BUY, lot_size=0.01, sl=1.0900, agent_id="test"
        ))
    assert len(await broker.get_positions()) == 3
    results = await broker.close_all_positions()
    assert len(results) == 3
    assert len(await broker.get_positions()) == 0


@pytest.mark.asyncio
async def test_no_price_symbol(broker):
    await broker.connect()
    order = OrderRequest(
        symbol="XAUUSD", direction=Direction.BUY, lot_size=0.1, sl=1900, agent_id="test"
    )
    result = await broker.place_order(order)
    assert result.success is False
