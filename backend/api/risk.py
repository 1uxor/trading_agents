from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from backend.api.dependencies import get_runner, get_risk_manager
from backend.config import get_settings

router = APIRouter(prefix="/api/risk", tags=["risk"])


class LiveTradingConfirmation(BaseModel):
    confirmation_text: str    # Must type "ENABLE LIVE TRADING"


@router.post("/kill-switch")
async def kill_switch(runner=Depends(get_runner)):
    """Global kill switch: close all positions, stop all agents."""
    result = await runner.kill_all()
    return result


@router.post("/unlock")
async def unlock(runner=Depends(get_runner)):
    """Unlock risk manager after kill switch."""
    runner.unlock()
    return {"status": "unlocked"}


@router.get("/status")
async def risk_status(risk_manager=Depends(get_risk_manager)):
    return {
        "locked": risk_manager.is_locked,
        "daily_loss": risk_manager.daily_loss,
        "settings": {
            "max_risk_per_trade_pct": get_settings().max_risk_per_trade_pct,
            "max_open_positions_global": get_settings().max_open_positions_global,
            "max_daily_loss_pct": get_settings().max_daily_loss_pct,
            "max_lot_size": get_settings().max_lot_size,
        },
    }


@router.post("/enable-live-trading")
async def enable_live_trading(req: LiveTradingConfirmation):
    """Enable live trading. Requires LIVE_TRADING=true in .env AND typed confirmation."""
    settings = get_settings()
    if not settings.live_trading:
        raise HTTPException(
            403,
            "LIVE_TRADING is not set to true in .env. "
            "This is a safety measure — edit your .env file first.",
        )
    if req.confirmation_text != "ENABLE LIVE TRADING":
        raise HTTPException(
            400,
            "You must type exactly 'ENABLE LIVE TRADING' to confirm.",
        )
    return {"status": "live_trading_enabled", "warning": "You are now trading with real money."}
