from __future__ import annotations

from fastapi import APIRouter

from backend.strategies.base import list_strategies
from backend.models.base import list_model_providers

router = APIRouter(prefix="/api/config", tags=["config"])


@router.get("/strategies")
async def get_strategies():
    """List all available strategies with their parameters."""
    result = []
    for name, cls in list_strategies().items():
        result.append({
            "name": name,
            "description": cls.description,
            "parameters": [p.model_dump() for p in cls.parameters()],
        })
    return result


@router.get("/model-providers")
async def get_model_providers():
    """List all available model providers."""
    result = []
    for name, cls in list_model_providers().items():
        result.append({
            "name": name,
            "license": getattr(cls, "license_info", ""),
        })
    return result


@router.get("/timeframes")
async def get_timeframes():
    from backend.market_data.provider import Timeframe
    return [t.value for t in Timeframe]
