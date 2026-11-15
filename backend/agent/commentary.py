from __future__ import annotations

import datetime as dt
from enum import Enum
from typing import Any, Callable, Awaitable

from pydantic import BaseModel


class CommentaryEventType(str, Enum):
    THINKING = "thinking"
    SIGNAL = "signal"
    EXECUTING = "executing"
    RESULT = "result"
    EXPLANATION = "explanation"
    ERROR = "error"


class CommentaryEvent(BaseModel):
    type: str = "agent_commentary"
    agent_id: str
    agent_name: str
    strategy: str
    color: str
    event: CommentaryEventType
    message: str
    data: dict[str, Any] = {}
    confidence: float | None = None
    timestamp: str = ""

    def model_post_init(self, __context: Any) -> None:
        if not self.timestamp:
            self.timestamp = dt.datetime.utcnow().isoformat()


# Type for the callback that broadcasts commentary
CommentaryCallback = Callable[[CommentaryEvent], Awaitable[None]]


class CommentaryEngine:
    """Produces and broadcasts agent commentary events."""

    def __init__(self, agent_id: str, agent_name: str, color: str, callback: CommentaryCallback | None = None):
        self._agent_id = agent_id
        self._agent_name = agent_name
        self._color = color
        self._callback = callback
        self._history: list[CommentaryEvent] = []

    async def emit(
        self,
        event: CommentaryEventType,
        message: str,
        strategy: str = "",
        data: dict | None = None,
        confidence: float | None = None,
    ):
        evt = CommentaryEvent(
            agent_id=self._agent_id,
            agent_name=self._agent_name,
            strategy=strategy,
            color=self._color,
            event=event,
            message=message,
            data=data or {},
            confidence=confidence,
        )
        self._history.append(evt)
        # Keep last 200
        if len(self._history) > 200:
            self._history = self._history[-200:]

        if self._callback:
            await self._callback(evt)

    @property
    def history(self) -> list[CommentaryEvent]:
        return list(self._history)
