"""Decision cycle — the heartbeat of Mission Control.

Every tick:
1. Read telemetry from kOS bridge
2. Distribute to all seat agents
3. Collect seat recommendations
4. Flight Director makes decision
5. Dispatch approved commands to kOS
"""

import asyncio
import structlog

from apollo_mc.agents.base import SeatAgent
from apollo_mc.agents.flight import FlightDirectorAgent
from apollo_mc.core.command_dispatch import CommandDispatcher
from apollo_mc.core.mission_state import MissionState
from apollo_mc.core.telemetry_bus import TelemetryBus
from apollo_mc.schemas.commands import SeatRecommendation
from apollo_mc.schemas.telemetry import TelemetryFrame

logger = structlog.get_logger()


class DecisionCycle:
    """Runs the evaluate → aggregate → decide → dispatch loop."""

    def __init__(
        self,
        mission_state: MissionState,
        telemetry_bus: TelemetryBus,
        flight_director: FlightDirectorAgent,
        seats: list[SeatAgent],
        dispatcher: CommandDispatcher,
    ) -> None:
        self._state = mission_state
        self._bus = telemetry_bus
        self._flight = flight_director
        self._seats = seats
        self._dispatcher = dispatcher

    async def tick(self, frame: TelemetryFrame) -> None:
        """Run one decision cycle."""
        # Update mission state with new telemetry
        self._state.update_telemetry(frame)

        # All seats evaluate in parallel
        tasks = [seat.evaluate(frame) for seat in self._seats]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Collect recommendations
        recommendations: dict[str, SeatRecommendation] = {}
        for seat, result in zip(self._seats, results, strict=True):
            if isinstance(result, Exception):
                logger.error("seat_evaluation_error", seat=seat.seat_name, error=str(result))
                continue
            recommendations[seat.seat_name] = result

        # Flight Director also evaluates
        flight_rec = await self._flight.evaluate(frame)
        recommendations[self._flight.seat_name] = flight_rec

        # Store all recommendations
        self._state.seat_recommendations = recommendations

        # Flight Director makes the call
        decision = await self._flight.make_decision(recommendations)
        self._state.record_decision(decision)

        # Dispatch approved commands
        for command in decision.approved_commands:
            await self._dispatcher.dispatch(command, frame.timestamp)

        logger.info(
            "cycle_complete",
            cycle=self._state.cycle_count,
            status=decision.overall_status.value,
            met=frame.timestamp,
        )
