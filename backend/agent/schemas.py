from __future__ import annotations

from typing import Any, Optional

from pydantic import BaseModel, Field, model_validator

from backend.risk.models import RiskProfile
from backend.strategies.combiner import CombineMode

# Strategies that require an LLM provider (not hf_forecaster, not no_model)
LLM_STRATEGIES = {"llm_discretionary"}
# Valid LLM providers for llm_discretionary
LLM_PROVIDERS = {"gemini", "openai", "anthropic", "ollama", "hf_trading_models"}


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

    @model_validator(mode="after")
    def validate_config(self):
        strategy_names = {s.name for s in self.strategies}

        # Multiple strategies require a combiner
        if len(self.strategies) > 1 and self.combiner is None:
            self.combiner = CombinerConfig(mode=CombineMode.MAJORITY_VOTE)

        # Single strategy must not have a combiner
        if len(self.strategies) == 1 and self.combiner is not None:
            self.combiner = None

        # Auto-fix: hf_trading_models outputs LLMSignal format (signal/confidence),
        # NOT ForecastResult. Only llm_discretionary can consume it.
        if self.model_provider == "hf_trading_models":
            if "llm_discretionary" not in strategy_names:
                self.strategies = [StrategyConfig(name="llm_discretionary")]
                self.combiner = None

        # llm_discretionary requires an LLM provider
        if {s.name for s in self.strategies} & LLM_STRATEGIES:
            if self.model_provider not in LLM_PROVIDERS:
                raise ValueError(
                    f"Strategy llm_discretionary requires an LLM provider "
                    f"({', '.join(sorted(LLM_PROVIDERS))}), "
                    f"got '{self.model_provider}'"
                )

        return self
