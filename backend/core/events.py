"""
SentinelAI — Internal Event Bus
Lightweight pub/sub system for cross-module communication.
No Redis, no Celery - pure async Python.
"""
from __future__ import annotations

import asyncio
import enum
import logging
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Callable, Coroutine, Dict, List
from uuid import uuid4

logger = logging.getLogger("sentinel.events")


class EventType(str, enum.Enum):
    """All system events - emitted and consumed by modules."""
    # Incident lifecycle
    INCIDENT_DETECTED = "incident.detected"
    INCIDENT_UPDATED = "incident.updated"
    INCIDENT_RESOLVED = "incident.resolved"

    # Investigation
    INVESTIGATION_STARTED = "investigation.started"
    INVESTIGATION_STEP_COMPLETED = "investigation.step_completed"
    ROOT_CAUSE_FOUND = "investigation.root_cause_found"
    INVESTIGATION_COMPLETED = "investigation.completed"

    # Prediction
    PREDICTION_GENERATED = "prediction.generated"
    ANOMALY_DETECTED = "prediction.anomaly_detected"

    # Memory
    MEMORY_STORED = "memory.stored"
    MEMORY_MATCHED = "memory.matched"

    # Impact
    IMPACT_CALCULATED = "impact.calculated"
    BLAST_RADIUS_COMPUTED = "impact.blast_radius"

    # Recommendations
    RECOMMENDATION_GENERATED = "recommendation.generated"

    # Reports
    REPORT_GENERATED = "report.generated"

    # Service health
    SERVICE_HEALTH_CHANGED = "service.health_changed"
    METRIC_UPDATED = "metric.updated"

    # Chat
    CHAT_MESSAGE_RECEIVED = "chat.message_received"
    CHAT_RESPONSE_GENERATED = "chat.response_generated"


@dataclass
class Event:
    """A system event carrying typed payload."""
    type: EventType
    payload: Dict[str, Any]
    incident_id: str | None = None
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    event_id: str = field(default_factory=lambda: str(uuid4()))


# Type alias for async event handlers
EventHandler = Callable[[Event], Coroutine[Any, Any, None]]


class EventBus:
    """
    Async publish-subscribe event bus.
    Decouples modules without requiring message queues.
    """

    def __init__(self) -> None:
        self._subscribers: Dict[EventType, List[EventHandler]] = defaultdict(list)
        self._wildcard_subscribers: List[EventHandler] = []
        self._queue: asyncio.Queue[Event] = asyncio.Queue(maxsize=1000)
        self._running = False
        self._worker_task: asyncio.Task | None = None

    def subscribe(self, event_type: EventType, handler: EventHandler) -> None:
        """Subscribe a handler to a specific event type."""
        self._subscribers[event_type].append(handler)
        logger.debug(f"Subscribed {handler.__name__} to {event_type.value}")

    def subscribe_all(self, handler: EventHandler) -> None:
        """Subscribe a handler to ALL events (e.g., WebSocket broadcaster)."""
        self._wildcard_subscribers.append(handler)

    def unsubscribe(self, event_type: EventType, handler: EventHandler) -> None:
        """Remove a specific subscription."""
        self._subscribers[event_type] = [
            h for h in self._subscribers[event_type] if h != handler
        ]

    async def publish(self, event: Event) -> None:
        """Publish an event to all subscribers."""
        await self._queue.put(event)
        logger.info(f"Event published: {event.type.value} [{event.event_id}]")

    async def emit(self, event_type: EventType, payload: Dict[str, Any], incident_id: str | None = None) -> None:
        """Convenience method - creates and publishes an event."""
        event = Event(type=event_type, payload=payload, incident_id=incident_id)
        await self.publish(event)

    async def _process_event(self, event: Event) -> None:
        """Dispatch event to all matching handlers."""
        handlers = self._subscribers.get(event.type, [])
        all_handlers = handlers + self._wildcard_subscribers

        if not all_handlers:
            logger.debug(f"No handlers for event type: {event.type.value}")
            return

        tasks = [asyncio.create_task(h(event)) for h in all_handlers]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        for i, result in enumerate(results):
            if isinstance(result, Exception):
                handler_name = all_handlers[i].__name__
                logger.error(f"Handler {handler_name} failed for {event.type.value}: {result}")

    async def _worker(self) -> None:
        """Background worker that drains the event queue."""
        logger.info("Event bus worker started")
        while self._running:
            try:
                event = await asyncio.wait_for(self._queue.get(), timeout=1.0)
                await self._process_event(event)
                self._queue.task_done()
            except asyncio.TimeoutError:
                continue
            except Exception as e:
                logger.error(f"Event bus worker error: {e}")

    async def start(self) -> None:
        """Start the event bus background worker."""
        self._running = True
        self._worker_task = asyncio.create_task(self._worker())
        logger.info("SentinelAI event bus started")

    async def stop(self) -> None:
        """Gracefully stop the event bus."""
        self._running = False
        if self._worker_task:
            await asyncio.wait_for(self._worker_task, timeout=5.0)
        logger.info("SentinelAI event bus stopped")


# Global singleton - imported across modules
event_bus = EventBus()
