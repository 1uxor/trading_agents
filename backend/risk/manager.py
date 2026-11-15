from __future__ import annotations

import logging
from typing import Optional

from backend.broker.base import BrokerAdapter, OrderRequest, Direction
from backend.risk.models import RiskProfile, RiskCheckResult
from backend.config import get_settings

logger = logging.getLogger(__name__)


class RiskManager:
    """Mandatory gateway between every agent and the broker.

    No order may bypass this.  Enforces:
      - mandatory stop-loss
      - max risk per trade (% of equity)
      - max lot size
      - max open positions (per-agent and global)
      - max daily loss (then halt all agents)
    """

    def __init__(self, broker: BrokerAdapter):
        self._broker = broker
        self._locked = False                # kill-switch flag
        self._daily_loss = 0.0
        self._day_start_equity: float | None = None
        settings = get_settings()
        self._global_max_positions = settings.max_open_positions_global
        self._global_max_daily_loss_pct = settings.max_daily_loss_pct

    # ── Public API ──────────────────────────────────────────────────────────

    async def validate_order(
        self,
        order: OrderRequest,
        risk_profile: RiskProfile,
    ) -> RiskCheckResult:
        """Validate and optionally adjust an order.  Returns approved/rejected."""

        # Kill switch
        if self._locked:
            return RiskCheckResult(approved=False, reason="Kill switch active — all trading halted")

        # 1. Mandatory stop-loss
        if order.sl <= 0:
            return RiskCheckResult(approved=False, reason="Stop-loss is mandatory on every order")

        # 2. Max lot size
        if order.lot_size > risk_profile.max_lot_size:
            return RiskCheckResult(
                approved=False,
                reason=f"Lot size {order.lot_size} exceeds max {risk_profile.max_lot_size}",
            )

        # 3. Account info for equity-based checks
        account = await self._broker.get_account_info()
        if self._day_start_equity is None:
            self._day_start_equity = account.equity

        # 4. Max daily loss
        daily_loss_pct = abs(self._daily_loss) / self._day_start_equity * 100 if self._day_start_equity > 0 else 0
        if daily_loss_pct >= self._global_max_daily_loss_pct:
            self._locked = True
            logger.warning("Daily loss limit hit (%.2f%%). Locking all trading.", daily_loss_pct)
            return RiskCheckResult(
                approved=False,
                reason=f"Daily loss limit reached ({daily_loss_pct:.1f}% >= {self._global_max_daily_loss_pct}%)",
            )

        # 5. Risk per trade (% of equity)
        bid, ask = await self._broker.get_symbol_price(order.symbol)
        entry = ask if order.direction == Direction.BUY else bid
        sl_distance = abs(entry - order.sl)
        risk_amount = sl_distance * 100_000 * order.lot_size  # forex standard lot
        risk_pct = (risk_amount / account.equity * 100) if account.equity > 0 else 100

        if risk_pct > risk_profile.max_risk_per_trade_pct:
            # Try to adjust lot size down
            max_risk_amount = risk_profile.max_risk_per_trade_pct / 100 * account.equity
            adjusted_lot = max_risk_amount / (sl_distance * 100_000) if sl_distance > 0 else 0
            adjusted_lot = round(adjusted_lot, 2)
            if adjusted_lot < 0.01:
                return RiskCheckResult(
                    approved=False,
                    reason=f"Risk {risk_pct:.1f}% exceeds max {risk_profile.max_risk_per_trade_pct}% and lot too small after adjustment",
                )
            return RiskCheckResult(
                approved=True,
                reason=f"Lot adjusted from {order.lot_size} to {adjusted_lot} to fit {risk_profile.max_risk_per_trade_pct}% risk",
                adjusted_lot_size=adjusted_lot,
            )

        # 6. Max positions per agent
        agent_positions = await self._broker.get_positions(agent_id=order.agent_id)
        if len(agent_positions) >= risk_profile.max_open_positions:
            return RiskCheckResult(
                approved=False,
                reason=f"Agent has {len(agent_positions)} open positions (max {risk_profile.max_open_positions})",
            )

        # 7. Max global positions
        all_positions = await self._broker.get_positions()
        if len(all_positions) >= self._global_max_positions:
            return RiskCheckResult(
                approved=False,
                reason=f"Global position limit reached ({len(all_positions)} / {self._global_max_positions})",
            )

        return RiskCheckResult(approved=True, reason="All checks passed")

    def record_closed_pnl(self, pnl: float):
        """Called after a position is closed to track daily P&L."""
        self._daily_loss += min(pnl, 0)  # only accumulate losses

    def reset_daily(self):
        """Call at start of each trading day."""
        self._daily_loss = 0.0
        self._day_start_equity = None
        if self._locked:
            logger.info("New day — unlocking risk manager")
            self._locked = False

    # ── Kill switch ─────────────────────────────────────────────────────────

    def lock(self):
        self._locked = True
        logger.warning("Risk manager LOCKED — kill switch activated")

    def unlock(self):
        self._locked = False
        logger.info("Risk manager unlocked")

    @property
    def is_locked(self) -> bool:
        return self._locked

    @property
    def daily_loss(self) -> float:
        return self._daily_loss
