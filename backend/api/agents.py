from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel

from backend.agent.schemas import AgentConfig
from backend.api.dependencies import get_runner

router = APIRouter(prefix="/api/agents", tags=["agents"])


class AgentCreateRequest(BaseModel):
    config: AgentConfig


class AgentActionRequest(BaseModel):
    action: str   # start | stop | pause | resume


@router.get("")
async def list_agents(runner=Depends(get_runner)):
    return runner.status_summary()


@router.post("")
async def create_agent(req: AgentCreateRequest, runner=Depends(get_runner)):
    agent = runner.create_agent(req.config)
    return {"id": agent.id, "name": agent.name, "state": agent.state.value}


@router.get("/{agent_id}")
async def get_agent(agent_id: str, runner=Depends(get_runner)):
    agent = runner.get_agent(agent_id)
    if not agent:
        raise HTTPException(404, "Agent not found")
    return {
        "id": agent.id,
        "name": agent.name,
        "state": agent.state.value,
        "config": agent.config.model_dump(by_alias=True),
    }


@router.post("/{agent_id}/action")
async def agent_action(agent_id: str, req: AgentActionRequest, runner=Depends(get_runner)):
    actions = {
        "start": runner.start_agent,
        "stop": runner.stop_agent,
        "pause": runner.pause_agent,
        "resume": runner.resume_agent,
    }
    fn = actions.get(req.action)
    if not fn:
        raise HTTPException(400, f"Unknown action: {req.action}")
    ok = fn(agent_id)
    if not ok:
        raise HTTPException(404, "Agent not found")
    agent = runner.get_agent(agent_id)
    return {"id": agent_id, "state": agent.state.value if agent else "unknown"}


@router.delete("/{agent_id}")
async def delete_agent(agent_id: str, runner=Depends(get_runner)):
    if not runner.remove_agent(agent_id):
        raise HTTPException(404, "Agent not found")
    return {"deleted": agent_id}


@router.get("/{agent_id}/commentary")
async def get_commentary(agent_id: str, runner=Depends(get_runner)):
    agent = runner.get_agent(agent_id)
    if not agent:
        raise HTTPException(404, "Agent not found")
    return [e.model_dump() for e in agent.commentary.history]
