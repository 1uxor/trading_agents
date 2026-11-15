from __future__ import annotations

import asyncio
import logging
import traceback
from enum import Enum
from typing import Any

import pandas as pd

from backend.agent.commentary import CommentaryEngine, CommentaryEventType, CommentaryCallback
from backend.agent.schemas import AgentConfig
from backend.broker.base import BrokerAdapter, OrderRequest, Direction
from backend.logging_.trade_logger import TradeLogger
from backend.market_data.provider import MarketDataProvider, Timeframe
from backend.models.base import ModelProvider, get_model_provider
from backend.risk.manager import RiskManager
from backend.risk.models import RiskProfile
from backend.strategies.base import Strategy, Signal, SignalDirection, get_strategy
from backend.strategies.combiner import StrategyCombiner, CombinerConfig as StrategyCombinerConfig

logger = logging.getLogger(__name__)


class AgentState(str, Enum):
    STOPPED = "stopped"
    RUNNING = "running"
    PAUSED = "paused"
    ERROR = "error"


class Agent:
    """An independent trading agent: symbol(s) + model + strategy + risk profile."""

    def __init__(
        self,
        config: AgentConfig,
        broker: BrokerAdapter,
        market_data: MarketDataProvider,
        risk_manager: RiskManager,
        trade_logger: TradeLogger,
        commentary_callback: CommentaryCallback | None = None,
    ):
        self.config = config
        self.id = config.id
        self.name = config.name

        self._broker = broker
        self._market_data = market_data
        self._risk_manager = risk_manager
        self._trade_logger = trade_logger

        self._state = AgentState.STOPPED
        self._task: asyncio.Task | None = None

        # Build strategies
        self._strategies: list[tuple[Strategy, dict]] = []
        for sc in config.strategies:
            strat_cls = get_strategy(sc.name)
            self._strategies.append((strat_cls(), sc.params))

        # Build combiner if multiple strategies
        self._combiner: StrategyCombiner | None = None
        if config.combiner and len(self._strategies) > 1:
            combiner_cfg = StrategyCombinerConfig(
                mode=config.combiner.mode,
                weights=config.combiner.weights,
                filter_roles=config.combiner.filter_roles,
            )
            self._combiner = StrategyCombiner(self._strategies, combiner_cfg)

        # Model provider
        self._model: ModelProvider | None = None
        if config.model_provider != "no_model":
            provider_cls = get_model_provider(config.model_provider)
            self._model = provider_cls(**(config.model_config_ or {}))

        # Commentary
        self._commentary = CommentaryEngine(
            agent_id=config.id,
            agent_name=config.name,
            color=config.color,
            callback=commentary_callback,
        )

    @property
    def state(self) -> AgentState:
        return self._state

    @property
    def commentary(self) -> CommentaryEngine:
        return self._commentary

    # ── Lifecycle ───────────────────────────────────────────────────────────

    def start(self):
        if self._state == AgentState.RUNNING:
            return
        self._state = AgentState.RUNNING
        self._task = asyncio.create_task(self._run_loop(), name=f"agent-{self.id}")

    def pause(self):
        self._state = AgentState.PAUSED

    def resume(self):
        if self._state == AgentState.PAUSED:
            self._state = AgentState.RUNNING

    def stop(self):
        self._state = AgentState.STOPPED
        if self._task and not self._task.done():
            self._task.cancel()

    # ── Main loop ───────────────────────────────────────────────────────────

    async def _run_loop(self):
        logger.info("Agent %s (%s) started", self.id, self.name)
        await self._commentary.emit(
            CommentaryEventType.EXPLANATION,
            f"Starting up. Watching {', '.join(self.config.symbols)} on {self.config.timeframe}.",
            strategy=self._strategy_label(),
        )

        try:
            while self._state == AgentState.RUNNING:
                for symbol in self.config.symbols:
                    if self._state != AgentState.RUNNING:
                        break
                    try:
                        await self._tick(symbol)
                    except Exception as e:
                        logger.exception("Agent %s error on %s: %s", self.id, symbol, e)
                        await self._commentary.emit(
                            CommentaryEventType.ERROR,
                            f"Error on {symbol}: {e}",
                            strategy=self._strategy_label(),
                        )

                # Wait for next cycle
                for _ in range(self.config.schedule_seconds):
                    if self._state != AgentState.RUNNING:
                        break
                    await asyncio.sleep(1)

        except asyncio.CancelledError:
            pass
        finally:
            self._state = AgentState.STOPPED
            logger.info("Agent %s stopped", self.id)

    async def _tick(self, symbol: str):
        tf = Timeframe(self.config.timeframe)

        # 1. Fetch data
        await self._commentary.emit(
            CommentaryEventType.THINKING,
            f"Fetching {symbol} {tf.value} data...",
            strategy=self._strategy_label(),
        )
        data = await self._market_data.get_ohlcv(symbol, tf, count=500)

        # 2. Model prediction (if any)
        model_output = None
        if self._model is not None:
            await self._commentary.emit(
                CommentaryEventType.THINKING,
                f"Running {self.config.model_provider} model on {symbol}...",
                strategy=self._strategy_label(),
            )
            try:
                model_output = await self._model.predict(data, symbol=symbol)
            except Exception as e:
                logger.warning("Model error for agent %s: %s", self.id, e)
                await self._commentary.emit(
                    CommentaryEventType.ERROR,
                    f"Model error: {e}",
                    strategy=self._strategy_label(),
                )

        # 3. Generate signal
        if self._combiner:
            model_outputs = {strat.name: model_output for strat, _ in self._strategies}
            signal, sub_signals = self._combiner.generate_signal(data, model_outputs)
            # Commentary for each sub-strategy
            for (strat, params), sub_sig in zip(self._strategies, sub_signals):
                comment = strat.commentary(data, sub_sig, params)
                await self._commentary.emit(
                    CommentaryEventType.SIGNAL,
                    comment,
                    strategy=strat.name,
                    confidence=sub_sig.confidence,
                    data={"direction": sub_sig.direction.value, "symbol": symbol},
                )
        else:
            strat, params = self._strategies[0]
            signal = strat.generate_signal(data, model_output=model_output, params=params)
            comment = strat.commentary(data, signal, params)
            await self._commentary.emit(
                CommentaryEventType.SIGNAL,
                comment,
                strategy=strat.name,
                confidence=signal.confidence,
                data={"direction": signal.direction.value, "symbol": symbol},
            )

        # 4. HOLD => skip
        if signal.direction == SignalDirection.HOLD:
            inputs_summary = f"price={data['close'].iloc[-1]:.5f}"
            await self._trade_logger.log_signal(
                agent_id=self.id, symbol=symbol,
                model_provider=self.config.model_provider,
                strategy_name=self._strategy_label(),
                inputs_summary=inputs_summary,
                signal="HOLD", confidence=signal.confidence,
                reasoning=signal.reasoning,
                risk_check_result="skipped", risk_check_reason="HOLD signal",
                order_result=None,
            )
            return

        # 5. Build order
        if signal.sl is None:
            await self._commentary.emit(
                CommentaryEventType.ERROR,
                "Strategy produced no stop-loss — cannot trade without SL.",
                strategy=self._strategy_label(),
            )
            return

        order = OrderRequest(
            symbol=symbol,
            direction=Direction(signal.direction.value),
            lot_size=self.config.risk_profile.max_lot_size,
            sl=signal.sl,
            tp=signal.tp,
            comment=f"{self.name}|{self._strategy_label()}",
            agent_id=self.id,
        )

        # 6. Risk check (MANDATORY)
        await self._commentary.emit(
            CommentaryEventType.EXECUTING,
            f"Checking risk for {signal.direction.value} {symbol}...",
            strategy=self._strategy_label(),
            confidence=signal.confidence,
        )

        risk_result = await self._risk_manager.validate_order(order, self.config.risk_profile)

        if not risk_result.approved:
            await self._commentary.emit(
                CommentaryEventType.RESULT,
                f"Risk manager rejected: {risk_result.reason}",
                strategy=self._strategy_label(),
                data={"rejected": True, "symbol": symbol},
            )
            await self._trade_logger.log_signal(
                agent_id=self.id, symbol=symbol,
                model_provider=self.config.model_provider,
                strategy_name=self._strategy_label(),
                inputs_summary=f"price={data['close'].iloc[-1]:.5f}",
                signal=signal.direction.value, confidence=signal.confidence,
                reasoning=signal.reasoning,
                risk_check_result="rejected", risk_check_reason=risk_result.reason,
                order_result=None,
            )
            return

        # Adjust lot if risk manager says so
        if risk_result.adjusted_lot_size:
            order.lot_size = risk_result.adjusted_lot_size

        # 7. Execute order
        await self._commentary.emit(
            CommentaryEventType.EXECUTING,
            f"Placing {order.direction.value} {order.lot_size} lots on {symbol} @ market, SL={order.sl:.5f}",
            strategy=self._strategy_label(),
            confidence=signal.confidence,
            data={"direction": order.direction.value, "symbol": symbol, "lots": order.lot_size},
        )

        result = await self._broker.place_order(order)

        # 8. Log everything
        status = "filled" if result.success else "failed"
        await self._commentary.emit(
            CommentaryEventType.RESULT,
            f"Order {status}: {result.message}" + (f" @ {result.fill_price:.5f}" if result.fill_price else ""),
            strategy=self._strategy_label(),
            confidence=signal.confidence,
            data={"ticket": result.ticket, "fill_price": result.fill_price, "symbol": symbol},
        )

        await self._trade_logger.log_signal(
            agent_id=self.id, symbol=symbol,
            model_provider=self.config.model_provider,
            strategy_name=self._strategy_label(),
            inputs_summary=f"price={data['close'].iloc[-1]:.5f}",
            signal=signal.direction.value, confidence=signal.confidence,
            reasoning=signal.reasoning,
            risk_check_result="approved", risk_check_reason=risk_result.reason,
            order_result=f"{status}: {result.message}",
        )

        if result.success:
            await self._trade_logger.log_trade(
                agent_id=self.id, symbol=symbol,
                direction=order.direction.value,
                lot_size=order.lot_size,
                entry_price=result.fill_price,
                sl=order.sl, tp=order.tp,
                broker_ticket=result.ticket,
            )

    def _strategy_label(self) -> str:
        names = [s.name for s, _ in self._strategies]
        if len(names) == 1:
            return names[0]
        mode = self.config.combiner.mode.value if self.config.combiner else "single"
        return f"{mode}({','.join(names)})"
