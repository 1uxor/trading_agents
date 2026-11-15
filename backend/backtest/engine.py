from __future__ import annotations

import logging
from typing import Any

import numpy as np
import pandas as pd

from backend.agent.schemas import AgentConfig
from backend.backtest.metrics import compute_metrics
from backend.broker.base import Direction
from backend.market_data.paper_data import PaperDataProvider
from backend.market_data.provider import Timeframe
from backend.strategies.base import get_strategy, Signal, SignalDirection
from backend.strategies.combiner import StrategyCombiner, CombinerConfig as StrategyCombinerConfig

logger = logging.getLogger(__name__)


class Backtester:
    """Run any agent config on historical data with walk-forward and no lookahead."""

    def __init__(
        self,
        agent_config: AgentConfig,
        symbol: str = "EURUSD",
        timeframe: str = "H1",
        bars: int = 5000,
        walk_forward_splits: int = 1,
        spread_pips: float = 1.0,
        commission_per_lot: float = 7.0,
        slippage_pips: float = 0.5,
        initial_balance: float = 10_000.0,
        data_source: str = "synthetic",
    ):
        self._config = agent_config
        self._symbol = symbol
        self._timeframe = timeframe
        self._bars = bars
        self._splits = max(walk_forward_splits, 1)
        self._spread = spread_pips * 0.0001  # convert to price
        self._commission = commission_per_lot
        self._slippage = slippage_pips * 0.0001
        self._balance = initial_balance
        self._data_source = data_source

    async def _load_data(self) -> pd.DataFrame:
        """Load OHLCV data from the configured source."""
        if self._data_source == "yfinance":
            from backend.market_data.yfinance_provider import fetch_yfinance_ohlcv
            return fetch_yfinance_ohlcv(
                symbol=self._symbol,
                timeframe=self._timeframe,
                bars=self._bars,
            )

        if self._data_source.startswith("csv:"):
            from backend.api.data_upload import get_dataset
            key = self._data_source[4:]  # strip "csv:" prefix
            df = get_dataset(key)
            if len(df) > self._bars:
                df = df.tail(self._bars).reset_index(drop=True)
            return df

        # Default: synthetic
        data_provider = PaperDataProvider()
        data_provider.load_synthetic(
            symbol=self._symbol,
            timeframe=Timeframe(self._timeframe),
            bars=self._bars,
        )
        return await data_provider.get_ohlcv(self._symbol, Timeframe(self._timeframe), self._bars)

    async def run(self) -> dict:
        full_data = await self._load_data()

        # Build strategies
        strategies = []
        for sc in self._config.strategies:
            strat_cls = get_strategy(sc.name)
            strategies.append((strat_cls(), sc.params))

        combiner = None
        if self._config.combiner and len(strategies) > 1:
            combiner_cfg = StrategyCombinerConfig(
                mode=self._config.combiner.mode,
                weights=self._config.combiner.weights,
                filter_roles=self._config.combiner.filter_roles,
            )
            combiner = StrategyCombiner(strategies, combiner_cfg)

        # Walk-forward splits
        split_size = len(full_data) // self._splits
        all_trades: list[dict] = []
        equity_curve: list[float] = [self._balance]
        balance = self._balance

        for split_idx in range(self._splits):
            start = split_idx * split_size
            end = min(start + split_size, len(full_data))
            split_data = full_data.iloc[start:end].reset_index(drop=True)

            # Minimum lookback
            lookback = 100
            if len(split_data) < lookback + 10:
                continue

            position: dict | None = None

            for i in range(lookback, len(split_data)):
                window = split_data.iloc[:i + 1].reset_index(drop=True)
                current_price = window["close"].iloc[-1]

                # Check SL/TP on open position
                if position:
                    hit_sl = False
                    hit_tp = False
                    bar_high = window["high"].iloc[-1]
                    bar_low = window["low"].iloc[-1]

                    if position["direction"] == "BUY":
                        if bar_low <= position["sl"]:
                            hit_sl = True
                            exit_price = position["sl"]
                        elif position["tp"] and bar_high >= position["tp"]:
                            hit_tp = True
                            exit_price = position["tp"]
                    else:  # SELL
                        if bar_high >= position["sl"]:
                            hit_sl = True
                            exit_price = position["sl"]
                        elif position["tp"] and bar_low <= position["tp"]:
                            hit_tp = True
                            exit_price = position["tp"]

                    if hit_sl or hit_tp:
                        # Close position
                        pnl = self._calculate_pnl(position, exit_price)
                        balance += pnl
                        trade = {
                            "entry_bar": position["entry_bar"],
                            "exit_bar": i,
                            "direction": position["direction"],
                            "entry_price": position["entry_price"],
                            "exit_price": exit_price,
                            "lot_size": position["lot_size"],
                            "pnl": round(pnl, 2),
                            "exit_reason": "sl" if hit_sl else "tp",
                        }
                        all_trades.append(trade)
                        position = None

                equity_curve.append(balance + (self._floating_pnl(position, current_price) if position else 0))

                # Generate signal if no position
                if position is not None:
                    continue

                if combiner:
                    signal, _ = combiner.generate_signal(window, {})
                else:
                    strat, params = strategies[0]
                    signal = strat.generate_signal(window, params=params)

                if signal.direction == SignalDirection.HOLD or signal.sl is None:
                    continue

                # Risk check: simple % of equity
                sl_distance = abs(current_price - signal.sl)
                if sl_distance <= 0:
                    continue

                risk_amount = self._config.risk_profile.max_risk_per_trade_pct / 100 * balance
                lot_size = risk_amount / (sl_distance * 100_000)
                lot_size = min(lot_size, self._config.risk_profile.max_lot_size)
                lot_size = round(lot_size, 2)
                if lot_size < 0.01:
                    continue

                # Apply spread + slippage
                if signal.direction == SignalDirection.BUY:
                    entry_price = current_price + self._spread / 2 + self._slippage
                else:
                    entry_price = current_price - self._spread / 2 - self._slippage

                commission = self._commission * lot_size
                balance -= commission

                position = {
                    "direction": signal.direction.value,
                    "entry_price": entry_price,
                    "entry_bar": i,
                    "lot_size": lot_size,
                    "sl": signal.sl,
                    "tp": signal.tp,
                }

            # Close any open position at end of split
            if position:
                exit_price = split_data["close"].iloc[-1]
                pnl = self._calculate_pnl(position, exit_price)
                balance += pnl
                all_trades.append({
                    "entry_bar": position["entry_bar"],
                    "exit_bar": len(split_data) - 1,
                    "direction": position["direction"],
                    "entry_price": position["entry_price"],
                    "exit_price": exit_price,
                    "lot_size": position["lot_size"],
                    "pnl": round(pnl, 2),
                    "exit_reason": "end_of_data",
                })
                position = None

        # Compute metrics
        metrics = compute_metrics(equity_curve, all_trades)

        return {
            **metrics,
            "equity_curve": equity_curve,
            "trades": all_trades,
            "data_source": self._data_source,
            "bars_used": len(full_data),
        }

    def _calculate_pnl(self, position: dict, exit_price: float) -> float:
        multiplier = 100_000 * position["lot_size"]
        if position["direction"] == "BUY":
            return (exit_price - position["entry_price"]) * multiplier
        else:
            return (position["entry_price"] - exit_price) * multiplier

    def _floating_pnl(self, position: dict | None, current_price: float) -> float:
        if position is None:
            return 0
        return self._calculate_pnl(position, current_price)
