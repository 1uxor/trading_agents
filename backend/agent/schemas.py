from __future__ import annotations

from typing import Any, Optional

from pydantic import BaseModel, Field

from backend.risk.models import RiskProfile
from backend.strategies.combiner import CombineMode


class StrategyConfig(BaseModel):
    name: str
    params: dict[str, Any] = {}


class CombinerConfig(BaseModel):
    mode: CombineMode = CombineMode.MAJORITY_VOTE
    weights: dict[str, float] | None = None
    filter_roles: dict[str, str] | None = None


class AgentConfig(BaseModel):
    """Full agent configuration — serializable to YAML/JSON."""
    id: str = ""
    name: str = "Agent"
    color: str = "#3498DB"
    symbols: list[str] = ["EURUSD"]
    timeframe: str = "H1"
    model_provider: str = "no_model"
    model_config_: dict[str, Any] = Field(default_factory=dict, alias="model_config")
    strategies: list[StrategyConfig] = [StrategyConfig(name="ma_crossover")]
    combiner: CombinerConfig | None = None          # None = single strategy, no combiner
    risk_profile: RiskProfile = RiskProfile()
    schedule_seconds: int = 60
    enabled: bool = True

    model_config = {"populate_by_name": True}
