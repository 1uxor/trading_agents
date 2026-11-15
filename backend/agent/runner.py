from __future__ import annotations

import logging
import uuid
import yaml
from pathlib import Path
from typing import Any

from backend.agent.agent import Agent, AgentState
from backend.agent.commentary import CommentaryCallback, CommentaryEvent
from backend.agent.schemas import AgentConfig
from backend.broker.base import BrokerAdapter
from backend.logging_.trade_logger import TradeLogger
from backend.market_data.provider import MarketDataProvider
from backend.risk.manager import RiskManager

logger = logging.getLogger(__name__)


class AgentRunner:
    """Manages the lifecycle of all agents.  Owns the global kill switch."""

    def __init__(
        self,
        broker: BrokerAdapter,
        market_data: MarketDataProvider,
        risk_manager: RiskManager,
        trade_logger: TradeLogger,
        commentary_callback: CommentaryCallback | None = None,
    ):
        self._broker = broker
        self._market_data = market_data
        self._risk_manager = risk_manager
        self._trade_logger = trade_logger
        self._commentary_callback = commentary_callback

        self._agents: dict[str, Agent] = {}

    # ── Agent CRUD ──────────────────────────────────────────────────────────

    def create_agent(self, config: AgentConfig) -> Agent:
        if not config.id:
            config.id = uuid.uuid4().hex[:8]
        agent = Agent(
            config=config,
            broker=self._broker,
            market_data=self._market_data,
            risk_manager=self._risk_manager,
            trade_logger=self._trade_logger,
            commentary_callback=self._commentary_callback,
        )
        self._agents[agent.id] = agent
        logger.info("Created agent %s (%s)", agent.id, agent.name)
        return agent

    def get_agent(self, agent_id: str) -> Agent | None:
        return self._agents.get(agent_id)

    def list_agents(self) -> list[Agent]:
        return list(self._agents.values())

    def remove_agent(self, agent_id: str) -> bool:
        agent = self._agents.pop(agent_id, None)
        if agent:
            agent.stop()
            return True
        return False

    # ── Lifecycle ───────────────────────────────────────────────────────────

    def start_agent(self, agent_id: str) -> bool:
        agent = self._agents.get(agent_id)
        if agent:
            agent.start()
            return True
        return False

    def pause_agent(self, agent_id: str) -> bool:
        agent = self._agents.get(agent_id)
        if agent:
            agent.pause()
            return True
        return False

    def resume_agent(self, agent_id: str) -> bool:
        agent = self._agents.get(agent_id)
        if agent:
            agent.resume()
            return True
        return False

    def stop_agent(self, agent_id: str) -> bool:
        agent = self._agents.get(agent_id)
        if agent:
            agent.stop()
            return True
        return False

    # ── Kill switch ─────────────────────────────────────────────────────────

    async def kill_all(self) -> dict:
        """Global kill switch: stop all agents, lock risk, close all positions."""
        logger.warning("KILL SWITCH ACTIVATED")

        # 1. Stop all agents
        for agent in self._agents.values():
            agent.stop()

        # 2. Lock the risk manager
        self._risk_manager.lock()

        # 3. Close all positions
        results = await self._broker.close_all_positions()

        close_summary = [
            {"ticket": r.ticket, "success": r.success, "message": r.message}
            for r in results
        ]

        # Broadcast kill event
        if self._commentary_callback:
            from backend.agent.commentary import CommentaryEvent, CommentaryEventType
            await self._commentary_callback(CommentaryEvent(
                agent_id="system",
                agent_name="SYSTEM",
                strategy="kill_switch",
                color="#FF0000",
                event=CommentaryEventType.ERROR,
                message=f"KILL SWITCH ACTIVATED — all agents stopped, {len(results)} positions closed.",
                data={"closed": close_summary},
            ))

        return {
            "agents_stopped": len(self._agents),
            "positions_closed": len(results),
            "details": close_summary,
        }

    def unlock(self):
        """Unlock the risk manager after a kill switch."""
        self._risk_manager.unlock()

    # ── Config persistence ──────────────────────────────────────────────────

    def save_config(self, agent_id: str, path: Path | str):
        agent = self._agents.get(agent_id)
        if not agent:
            raise ValueError(f"Agent {agent_id} not found")
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        data = agent.config.model_dump(by_alias=True)
        with open(path, "w") as f:
            yaml.dump(data, f, default_flow_style=False, sort_keys=False)

    def load_config(self, path: Path | str) -> AgentConfig:
        with open(path) as f:
            data = yaml.safe_load(f)
        return AgentConfig(**data)

    def status_summary(self) -> list[dict]:
        return [
            {
                "id": a.id,
                "name": a.name,
                "state": a.state.value,
                "color": a.config.color,
                "symbols": a.config.symbols,
                "timeframe": a.config.timeframe,
                "strategy": a._strategy_label(),
                "model": a.config.model_provider,
            }
            for a in self._agents.values()
        ]
