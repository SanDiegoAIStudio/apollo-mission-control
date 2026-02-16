"""Base class for all flight controller seat agents."""

from abc import ABC, abstractmethod

import structlog

from apollo_mc.core.mission_state import MissionState
from apollo_mc.schemas.commands import AuthorityLevel, GoNoGo, SeatRecommendation
from apollo_mc.schemas.telemetry import TelemetryFrame

logger = structlog.get_logger()


class SeatAgent(ABC):
    """Abstract base for a Mission Control seat.

    Each seat agent:
    1. Receives telemetry relevant to its role
    2. Evaluates its domain constraints
    3. Outputs a SeatRecommendation (Go/No-Go + actions)
    """

    seat_name: str
    authority: AuthorityLevel

    # Which telemetry fields this seat cares about (for future filtering)
    telemetry_scope: list[str] = []

    def __init__(self, mission_state: MissionState) -> None:
        self._state = mission_state
        self._log = logger.bind(seat=self.seat_name)

    @abstractmethod
    async def evaluate(self, frame: TelemetryFrame) -> SeatRecommendation:
        """Evaluate current telemetry and return seat recommendation.

        This is called every tick. The agent should:
        - Check its domain constraints
        - Determine Go/No-Go status
        - Recommend any actions needed
        """
        ...

    def go(self, summary: str) -> SeatRecommendation:
        """Convenience: return a clean GO with no actions."""
        return SeatRecommendation(
            seat=self.seat_name,
            go_nogo=GoNoGo.GO,
            status_summary=summary,
            constraints=[],
            warnings=[],
            recommended_actions=[],
        )

    def no_go(self, summary: str, constraints: list[str]) -> SeatRecommendation:
        """Convenience: return a NO_GO with constraint violations."""
        self._log.warning("no_go", summary=summary, constraints=constraints)
        return SeatRecommendation(
            seat=self.seat_name,
            go_nogo=GoNoGo.NO_GO,
            status_summary=summary,
            constraints=constraints,
            warnings=[],
            recommended_actions=[],
        )
