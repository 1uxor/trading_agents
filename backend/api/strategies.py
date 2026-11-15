from __future__ import annotations

from fastapi import APIRouter, HTTPException

from backend.strategies.base import list_strategies
from backend.models.base import list_model_providers, get_model_provider

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


@router.get("/model-providers/{provider}/models")
async def get_provider_models(provider: str):
    """List available models for a specific provider."""
    try:
        cls = get_model_provider(provider)
    except ValueError:
        raise HTTPException(404, f"Unknown provider: {provider}")
    return getattr(cls, "available_models", [])


@router.get("/timeframes")
async def get_timeframes():
    from backend.market_data.provider import Timeframe
    return [t.value for t in Timeframe]
