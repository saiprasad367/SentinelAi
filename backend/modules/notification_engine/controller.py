"""
SentinelAI — WebSocket Realtime Hub
Broadcasts all system events to connected frontend clients.
"""
from __future__ import annotations

import asyncio
import json
import logging
from datetime import datetime, timezone
from typing import Set

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from fastapi.responses import StreamingResponse

from core.events import Event, EventType, event_bus

logger = logging.getLogger("sentinel.realtime.hub")
router = APIRouter(prefix="/realtime", tags=["Realtime"])


class ConnectionManager:
    """Manages active WebSocket connections and broadcasts to all."""

    def __init__(self):
        self.active_connections: Set[WebSocket] = set()

    async def connect(self, ws: WebSocket) -> None:
        await ws.accept()
        self.active_connections.add(ws)
        logger.info(f"WebSocket connected. Total: {len(self.active_connections)}")

    def disconnect(self, ws: WebSocket) -> None:
        self.active_connections.discard(ws)
        logger.info(f"WebSocket disconnected. Total: {len(self.active_connections)}")

    async def broadcast(self, message: dict) -> None:
        """Send message to all connected clients."""
        if not self.active_connections:
            return
        data = json.dumps(message, default=str)
        dead = set()
        for ws in self.active_connections.copy():
            try:
                await ws.send_text(data)
            except Exception:
                dead.add(ws)
        for ws in dead:
            self.active_connections.discard(ws)

    @property
    def connection_count(self) -> int:
        return len(self.active_connections)


# Global connection manager
manager = ConnectionManager()


async def handle_event_broadcast(event: Event) -> None:
    """
    Event bus subscriber - broadcasts all events to WebSocket clients.
    Connected to event bus on startup.
    """
    message = {
        "event_type": event.type.value,
        "event_id": event.event_id,
        "incident_id": event.incident_id,
        "payload": event.payload,
        "timestamp": event.timestamp.isoformat(),
    }
    await manager.broadcast(message)


@router.websocket("/ws")
async def websocket_endpoint(ws: WebSocket):
    """
    Main WebSocket endpoint.
    Frontend connects here to receive all live system events.
    """
    await manager.connect(ws)

    # Send welcome message with connection count
    await ws.send_text(json.dumps({
        "event_type": "connected",
        "payload": {
            "message": "Connected to SentinelAI event stream",
            "connections": manager.connection_count,
        },
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }))

    try:
        while True:
            # Keep connection alive, wait for client ping
            try:
                data = await asyncio.wait_for(ws.receive_text(), timeout=30.0)
                if data == "ping":
                    await ws.send_text(json.dumps({"event_type": "pong"}))
            except asyncio.TimeoutError:
                # Send keepalive
                await ws.send_text(json.dumps({"event_type": "keepalive", "timestamp": datetime.now(timezone.utc).isoformat()}))
    except WebSocketDisconnect:
        manager.disconnect(ws)
    except Exception as e:
        logger.error(f"WebSocket error: {e}")
        manager.disconnect(ws)


@router.get("/status")
async def realtime_status():
    """Get realtime connection status."""
    return {
        "active_connections": manager.connection_count,
        "event_bus_status": "running",
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


async def global_sse_stream():
    """SSE fallback for clients that don't support WebSocket."""
    queue: asyncio.Queue = asyncio.Queue(maxsize=100)

    async def enqueue(event: Event):
        try:
            await queue.put(event)
        except asyncio.QueueFull:
            pass

    event_bus.subscribe_all(enqueue)
    try:
        while True:
            try:
                event = await asyncio.wait_for(queue.get(), timeout=30.0)
                data = json.dumps({
                    "event_type": event.type.value,
                    "incident_id": event.incident_id,
                    "payload": event.payload,
                    "timestamp": event.timestamp.isoformat(),
                }, default=str)
                yield f"data: {data}\n\n"
            except asyncio.TimeoutError:
                yield "data: {\"event_type\": \"keepalive\"}\n\n"
    finally:
        event_bus.unsubscribe(EventType.INCIDENT_DETECTED, enqueue)


@router.get("/events")
async def sse_events():
    """SSE endpoint for all system events (WebSocket alternative)."""
    return StreamingResponse(
        global_sse_stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
