"""FLIGHT — Flight Director agent.

The Flight Director has overall mission authority. Aggregates Go/No-Go
from all seats, resolves conflicts, and issues final commands.
"""

import structlog

from apollo_mc.agents.base import SeatAgent
from apollo_mc.core.mission_state import MissionState
from apollo_mc.schemas.commands import (
    AuthorityLevel,
    CommandRequest,
    FlightDirectorDecision,
    GoNoGo,
    SeatRecommendation,
)
from apollo_mc.schemas.telemetry import TelemetryFrame

logger = structlog.get_logger()


class FlightDirectorAgent(SeatAgent):
    seat_name = "FLIGHT"
    authority = AuthorityLevel.COMMAND

    def __init__(self, mission_state: MissionState) -> None:
        super().__init__(mission_state)

    async def evaluate(self, frame: TelemetryFrame) -> SeatRecommendation:
        """Flight Director evaluates the overall mission state."""
        # In Phase 1, this is mostly passthrough
        # In later phases, this will use an LLM to reason about the aggregate state
        if self._state.abort_called:
            return self.no_go("ABORT called", ["Abort in progress"])

        return self.go(f"Phase: {frame.phase.value}, MET: {frame.timestamp:.1f}s")

    async def make_decision(
        self,
        seat_recommendations: dict[str, SeatRecommendation],
    ) -> FlightDirectorDecision:
        """Aggregate all seat recommendations into a final decision."""
        seat_statuses = {
            seat: rec.go_nogo for seat, rec in seat_recommendations.items()
        }

        # Collect all recommended actions
        all_actions: list[CommandRequest] = []
        for rec in seat_recommendations.values():
            all_actions.extend(rec.recommended_actions)

        # Determine overall status
        no_go_seats = [s for s, status in seat_statuses.items() if status == GoNoGo.NO_GO]

        if no_go_seats:
            overall = GoNoGo.NO_GO
            approved: list[CommandRequest] = []
            rejected = all_actions
            notes = f"NO GO from: {', '.join(no_go_seats)}"
        else:
            overall = GoNoGo.GO
            approved = all_actions
            rejected = []
            notes = "All seats GO"

        decision = FlightDirectorDecision(
            cycle_number=self._state.cycle_count,
            mission_time=self._state.latest_telemetry.timestamp
            if self._state.latest_telemetry
            else 0.0,
            overall_status=overall,
            seat_statuses=seat_statuses,
            approved_commands=approved,
            rejected_commands=rejected,
            flight_notes=notes,
        )

        logger.info(
            "flight_decision",
            cycle=decision.cycle_number,
            status=overall.value,
            approved=len(approved),
            rejected=len(rejected),
            notes=notes,
        )

        return decision
