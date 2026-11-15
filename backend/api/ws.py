from __future__ import annotations

import asyncio
import logging
from typing import Any

from fastapi import WebSocket, WebSocketDisconnect

from backend.agent.commentary import CommentaryEvent

logger = logging.getLogger(__name__)


class WebSocketHub:
    """Manages WebSocket connections and broadcasts events."""

    def __init__(self):
        self._connections: list[WebSocket] = []
        self._lock = asyncio.Lock()

    async def connect(self, ws: WebSocket):
        await ws.accept()
        async with self._lock:
            self._connections.append(ws)
        logger.info("WS client connected (%d total)", len(self._connections))

    async def disconnect(self, ws: WebSocket):
        async with self._lock:
            if ws in self._connections:
                self._connections.remove(ws)
        logger.info("WS client disconnected (%d remaining)", len(self._connections))

    async def broadcast(self, data: dict):
        async with self._lock:
            dead: list[WebSocket] = []
            for ws in self._connections:
                try:
                    await ws.send_json(data)
                except Exception:
                    dead.append(ws)
            for ws in dead:
                self._connections.remove(ws)

    async def broadcast_commentary(self, event: CommentaryEvent):
        await self.broadcast(event.model_dump())

    @property
    def client_count(self) -> int:
        return len(self._connections)


# Singleton
ws_hub = WebSocketHub()


async def commentary_broadcast_callback(event: CommentaryEvent):
    """Callback passed to AgentRunner so all commentary goes to WS clients."""
    await ws_hub.broadcast_commentary(event)
