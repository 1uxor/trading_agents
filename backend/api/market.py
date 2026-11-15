from __future__ import annotations

from fastapi import APIRouter, HTTPException, Depends, Query

from backend.api.dependencies import get_market_data, get_broker
from backend.market_data.provider import Timeframe

router = APIRouter(prefix="/api/market", tags=["market"])


@router.get("/symbols")
async def get_symbols(market_data=Depends(get_market_data)):
    symbols = await market_data.get_symbols()
    return {"symbols": symbols}


@router.get("/ohlcv/{symbol}")
async def get_ohlcv(
    symbol: str,
    timeframe: str = Query("H1"),
    count: int = Query(500, ge=1, le=5000),
    market_data=Depends(get_market_data),
):
    try:
        tf = Timeframe(timeframe)
    except ValueError:
        raise HTTPException(400, f"Invalid timeframe: {timeframe}")

    df = await market_data.get_ohlcv(symbol, tf, count)
    return {
        "symbol": symbol,
        "timeframe": timeframe,
        "data": df.to_dict("records"),
    }


@router.get("/price/{symbol}")
async def get_price(symbol: str, broker=Depends(get_broker)):
    try:
        bid, ask = await broker.get_symbol_price(symbol)
        return {"symbol": symbol, "bid": bid, "ask": ask, "spread": ask - bid}
    except Exception as e:
        raise HTTPException(400, str(e))


@router.get("/account")
async def get_account(broker=Depends(get_broker)):
    info = await broker.get_account_info()
    return info.model_dump()


@router.get("/positions")
async def get_positions(agent_id: str | None = None, broker=Depends(get_broker)):
    positions = await broker.get_positions(agent_id)
    return [p.model_dump() for p in positions]
