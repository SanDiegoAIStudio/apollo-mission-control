"""Shared mission state — the single source of truth all agents query."""

from dataclasses import dataclass, field

from apollo_mc.schemas.commands import FlightDirectorDecision, GoNoGo, SeatRecommendation
from apollo_mc.schemas.telemetry import MissionPhase, TelemetryFrame


@dataclass
class MissionState:
    """Immutable-ish shared state. Only the orchestrator mutates this; agents read it."""

    mission_name: str = "Apollo-KSP-1"
    phase: MissionPhase = MissionPhase.PRELAUNCH
    cycle_count: int = 0
    latest_telemetry: TelemetryFrame | None = None
    seat_recommendations: dict[str, SeatRecommendation] = field(default_factory=dict)
    latest_decision: FlightDirectorDecision | None = None
    command_history: list[FlightDirectorDecision] = field(default_factory=list)
    abort_called: bool = False
    mission_complete: bool = False

    @property
    def overall_go(self) -> bool:
        if not self.seat_recommendations:
            return False
        return all(
            rec.go_nogo == GoNoGo.GO for rec in self.seat_recommendations.values()
        )

    @property
    def no_go_seats(self) -> list[str]:
        return [
            seat
            for seat, rec in self.seat_recommendations.items()
            if rec.go_nogo == GoNoGo.NO_GO
        ]

    def update_telemetry(self, frame: TelemetryFrame) -> None:
        self.latest_telemetry = frame
        self.phase = frame.phase
        self.cycle_count += 1

    def record_decision(self, decision: FlightDirectorDecision) -> None:
        self.latest_decision = decision
        self.command_history.append(decision)
