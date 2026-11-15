from __future__ import annotations

import asyncio
import datetime as dt
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

# Strategies that consume model output
MODEL_STRATEGIES = {"forecast_driven", "llm_discretionary"}

# Timeframe to approximate seconds mapping for candle close detection
_TF_SECONDS = {
    "M1": 60, "M5": 300, "M15": 900, "M30": 1800,
    "H1": 3600, "H4": 14400, "D1": 86400, "W1": 604800,
    "MN1": 2592000,
}


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

        # Model provider — only instantiate if at least one strategy needs it
        self._model: ModelProvider | None = None
        self._needs_model = any(
            s.name in MODEL_STRATEGIES for s, _ in self._strategies
        )
        if config.model_provider != "no_model" and self._needs_model:
            provider_cls = get_model_provider(config.model_provider)
            self._model = provider_cls(**(config.model_config_ or {}))

        # Commentary
        self._commentary = CommentaryEngine(
            agent_id=config.id,
            agent_name=config.name,
            color=config.color,
            callback=commentary_callback,
        )

        # Candle tracking per symbol (for new-candle detection)
        self._last_candle_ts: dict[str, float] = {}
        # Market-closed tracking — only log once per closed period
        self._market_closed_logged: dict[str, bool] = {}

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

    def _is_market_closed(self) -> bool:
        """Check if market is likely closed (weekend for FX)."""
        now = dt.datetime.utcnow()
        # FX market: closed from Friday ~22:00 UTC to Sunday ~22:00 UTC
        weekday = now.weekday()  # Monday=0, Sunday=6
        if weekday == 5:  # Saturday
            return True
        if weekday == 6 and now.hour < 22:  # Sunday before 22:00 UTC
            return True
        if weekday == 4 and now.hour >= 22:  # Friday after 22:00 UTC
            return True
        return False

    async def _tick(self, symbol: str):
        tf = Timeframe(self.config.timeframe)

        # Market closed detection
        if self._is_market_closed():
            if not self._market_closed_logged.get(symbol, False):
                await self._commentary.emit(
                    CommentaryEventType.EXPLANATION,
                    f"Market closed for {symbol}. Will resume when market opens.",
                    strategy=self._strategy_label(),
                )
                self._market_closed_logged[symbol] = True
                logger.info("Agent %s: Market closed for %s", self.id, symbol)
            return
        # Reset the market-closed flag when market is open
        self._market_closed_logged[symbol] = False

        # 1. Fetch data
        data = await self._market_data.get_ohlcv(symbol, tf, count=500)

        # 2. Check for new candle
        latest_ts = float(data["time"].iloc[-1])
        prev_ts = self._last_candle_ts.get(symbol)
        if prev_ts is not None and latest_ts == prev_ts:
            logger.debug("Agent %s: No new candle for %s %s", self.id, symbol, tf.value)
            return
        self._last_candle_ts[symbol] = latest_ts

        await self._commentary.emit(
            CommentaryEventType.THINKING,
            f"New {tf.value} candle for {symbol}. Analyzing...",
            strategy=self._strategy_label(),
        )

        # 3. Model prediction — only if strategies need it
        model_output = None
        if self._model is not None and self._needs_model:
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

        # 4. Generate signal
        if self._combiner:
            model_outputs = {strat.name: model_output for strat, _ in self._strategies}
            signal, sub_signals = self._combiner.generate_signal(data, model_outputs)
            # Commentary for each sub-strategy
            for (strat, params), sub_sig in zip(self._strategies, sub_signals):
                comment = self._build_signal_commentary(strat, data, sub_sig, params, model_output)
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
            comment = self._build_signal_commentary(strat, data, signal, params, model_output)
            await self._commentary.emit(
                CommentaryEventType.SIGNAL,
                comment,
                strategy=strat.name,
                confidence=signal.confidence,
                data={"direction": signal.direction.value, "symbol": symbol},
            )

        # 5. HOLD => skip
        price = data['close'].iloc[-1]
        if signal.direction == SignalDirection.HOLD:
            inputs_summary = f"price={price:.5f}"
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

        # 6. Build order
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

        # 7. Risk check (MANDATORY)
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
                inputs_summary=f"price={price:.5f}",
                signal=signal.direction.value, confidence=signal.confidence,
                reasoning=signal.reasoning,
                risk_check_result="rejected", risk_check_reason=risk_result.reason,
                order_result=None,
            )
            return

        # Adjust lot if risk manager says so
        if risk_result.adjusted_lot_size:
            order.lot_size = risk_result.adjusted_lot_size

        # 8. Execute order
        await self._commentary.emit(
            CommentaryEventType.EXECUTING,
            f"Placing {order.direction.value} {order.lot_size} lots on {symbol} @ market, SL={order.sl:.5f}",
            strategy=self._strategy_label(),
            confidence=signal.confidence,
            data={"direction": order.direction.value, "symbol": symbol, "lots": order.lot_size},
        )

        result = await self._broker.place_order(order)

        # 9. Log everything
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
            inputs_summary=f"price={price:.5f}",
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

    def _build_signal_commentary(
        self,
        strat: Strategy,
        data: pd.DataFrame,
        signal: Signal,
        params: dict,
        model_output: Any | None,
    ) -> str:
        """Build enriched signal commentary with actual numbers."""
        price = data["close"].iloc[-1]

        if strat.name == "forecast_driven" and model_output:
            forecast = model_output.get("forecast")
            q_low = model_output.get("quantile_low")
            q_high = model_output.get("quantile_high")
            forecast_return = ((forecast - price) / price * 100) if forecast else 0
            p = {spec.name: spec.default for spec in strat.parameters()}
            if params:
                p.update(params)
            parts = [
                f"forecast_driven | price={price:.5f}",
                f"forecast={forecast:.5f}" if forecast else "forecast=N/A",
                f"return={forecast_return:+.3f}%",
                f"threshold={p.get('return_threshold', 0.1)}%",
            ]
            if q_low is not None:
                parts.append(f"q10={q_low:.5f}")
            parts.append(f"q50={forecast:.5f}" if forecast else "q50=N/A")
            if q_high is not None:
                parts.append(f"q90={q_high:.5f}")
            parts.append(f"=> {signal.direction.value} (conf={signal.confidence:.0%})")
            return " | ".join(parts)

        if strat.name == "llm_discretionary" and model_output:
            raw_signal = model_output.get("signal", "HOLD")
            raw_conf = model_output.get("confidence", 0)
            raw_reasoning = model_output.get("reasoning", "")
            provider = self.config.model_provider
            model_name = (self.config.model_config_ or {}).get("model", "default")
            return (
                f"llm_discretionary | provider={provider} model={model_name} | "
                f"LLM output: signal={raw_signal} conf={raw_conf:.0%} | "
                f"reasoning: {raw_reasoning} | => {signal.direction.value}"
            )

        if strat.name == "ma_crossover":
            import ta
            p = {spec.name: spec.default for spec in strat.parameters()}
            if params:
                p.update(params)
            close = data["close"]
            fast = int(p["fast_period"])
            slow = int(p["slow_period"])
            if p.get("ma_type") == "EMA":
                ma_fast_val = ta.trend.EMAIndicator(close, window=fast).ema_indicator().iloc[-1]
                ma_slow_val = ta.trend.EMAIndicator(close, window=slow).ema_indicator().iloc[-1]
            else:
                ma_fast_val = ta.trend.SMAIndicator(close, window=fast).sma_indicator().iloc[-1]
                ma_slow_val = ta.trend.SMAIndicator(close, window=slow).sma_indicator().iloc[-1]
            return (
                f"ma_crossover | price={price:.5f} | "
                f"MA({fast})={ma_fast_val:.5f} MA({slow})={ma_slow_val:.5f} | "
                f"=> {signal.direction.value} (conf={signal.confidence:.0%})"
            )

        if strat.name == "rsi_reversion":
            import ta
            p = {spec.name: spec.default for spec in strat.parameters()}
            if params:
                p.update(params)
            close = data["close"]
            rsi_val = ta.momentum.RSIIndicator(close, window=int(p["rsi_period"])).rsi().iloc[-1]
            return (
                f"rsi_reversion | price={price:.5f} | "
                f"RSI({int(p['rsi_period'])})={rsi_val:.1f} "
                f"[oversold={p['oversold']} overbought={p['overbought']}] | "
                f"=> {signal.direction.value} (conf={signal.confidence:.0%})"
            )

        if strat.name == "breakout":
            p = {spec.name: spec.default for spec in strat.parameters()}
            if params:
                p.update(params)
            period = int(p["channel_period"])
            upper = data["high"].rolling(window=period).max().shift(1).iloc[-1]
            lower = data["low"].rolling(window=period).min().shift(1).iloc[-1]
            return (
                f"breakout | price={price:.5f} | "
                f"Donchian({period}): upper={upper:.5f} lower={lower:.5f} | "
                f"=> {signal.direction.value} (conf={signal.confidence:.0%})"
            )

        # Fallback: use strategy's own commentary
        return strat.commentary(data, signal, params)

    def _strategy_label(self) -> str:
        names = [s.name for s, _ in self._strategies]
        if len(names) == 1:
            return names[0]
        mode = self.config.combiner.mode.value if self.config.combiner else "single"
        return f"{mode}({','.join(names)})"
