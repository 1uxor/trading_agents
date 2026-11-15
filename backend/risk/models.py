from __future__ import annotations

from pydantic import BaseModel, Field


class RiskProfile(BaseModel):
    max_risk_per_trade_pct: float = 1.0
    max_open_positions: int = 3
    max_lot_size: float = 1.0
    max_daily_loss_pct: float = 5.0


class RiskCheckResult(BaseModel):
    approved: bool
    reason: str = ""
    adjusted_lot_size: float | None = None
