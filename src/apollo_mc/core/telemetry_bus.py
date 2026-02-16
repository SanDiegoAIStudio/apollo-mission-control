"""Telemetry bus — receives frames from the kOS bridge and distributes to agents."""

import asyncio
import structlog
from collections.abc import Callable, Coroutine
from typing import Any

from apollo_mc.schemas.telemetry import TelemetryFrame

logger = structlog.get_logger()

Subscriber = Callable[[TelemetryFrame], Coroutine[Any, Any, None]]


class TelemetryBus:
    """Pub/sub bus for telemetry frames. Bridge publishes, agents subscribe."""

    def __init__(self) -> None:
        self._subscribers: dict[str, Subscriber] = {}
        self._latest_frame: TelemetryFrame | None = None

    def subscribe(self, seat_name: str, callback: Subscriber) -> None:
        self._subscribers[seat_name] = callback
        logger.info("telemetry_subscribe", seat=seat_name)

    def unsubscribe(self, seat_name: str) -> None:
        self._subscribers.pop(seat_name, None)

    @property
    def latest(self) -> TelemetryFrame | None:
        return self._latest_frame

    async def publish(self, frame: TelemetryFrame) -> None:
        self._latest_frame = frame
        logger.debug("telemetry_tick", met=frame.timestamp, phase=frame.phase.value)

        tasks = [
            callback(frame)
            for callback in self._subscribers.values()
        ]
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)
