from __future__ import annotations

import os
from pathlib import Path

from pydantic_settings import BaseSettings
from pydantic import Field


class Settings(BaseSettings):
    # MT5
    mt5_login: int = 0
    mt5_password: str = ""
    mt5_server: str = ""
    mt5_path: str = ""

    # Live trading safety
    live_trading: bool = False

    # LLM keys
    openai_api_key: str = ""
    anthropic_api_key: str = ""
    gemini_api_key: str = ""
    ollama_base_url: str = "http://localhost:11434"
    hf_token: str = ""

    # Database
    database_url: str = "sqlite+aiosqlite:///./trading_agents.db"

    # Risk defaults
    max_risk_per_trade_pct: float = 1.0
    max_open_positions_per_agent: int = 3
    max_open_positions_global: int = 10
    max_daily_loss_pct: float = 5.0
    max_lot_size: float = 1.0

    # Server
    host: str = "0.0.0.0"
    port: int = 8000

    model_config = {
        "env_file": ".env",
        "env_file_encoding": "utf-8",
        "case_sensitive": False,
    }


_settings: Settings | None = None


def get_settings() -> Settings:
    global _settings
    if _settings is None:
        env_path = Path(__file__).resolve().parent.parent / ".env"
        if env_path.exists():
            # Load .env values and inject into os.environ so they take priority
            # over stale OS-level env vars from previous runs
            from dotenv import dotenv_values
            env_values = dotenv_values(str(env_path))
            for key, val in env_values.items():
                if val is not None:
                    os.environ[key] = val
            _settings = Settings(_env_file=str(env_path))
        else:
            _settings = Settings()
    return _settings
