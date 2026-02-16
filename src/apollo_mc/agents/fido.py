"""FIDO — Flight Dynamics Officer.

Responsible for trajectory design, maneuver planning, orbit determination,
and abort options. The numbers person.
"""

from apollo_mc.agents.base import SeatAgent
from apollo_mc.schemas.commands import (
    AuthorityLevel,
    CommandPriority,
    CommandRequest,
    SeatRecommendation,
)
from apollo_mc.schemas.telemetry import TelemetryFrame


class FidoAgent(SeatAgent):
    seat_name = "FIDO"
    authority = AuthorityLevel.EXECUTE
    telemetry_scope = ["vessel.orbital", "vessel.velocity", "vessel.position"]

    # Configurable orbit constraints
    MIN_PERIAPSIS_KERBIN = 70_000  # meters — below this we're in atmo
    CIRCULAR_ORBIT_TOLERANCE = 0.05  # eccentricity threshold

    async def evaluate(self, frame: TelemetryFrame) -> SeatRecommendation:
        orbital = frame.vessel.orbital
        warnings: list[str] = []
        constraints: list[str] = []
        actions: list[CommandRequest] = []

        # Check periapsis is safe
        if orbital.periapsis < self.MIN_PERIAPSIS_KERBIN and orbital.body == "Kerbin":
            constraints.append(
                f"Periapsis {orbital.periapsis:.0f}m is below safe altitude "
                f"({self.MIN_PERIAPSIS_KERBIN}m)"
            )

        # Warn on high eccentricity if we expect circular
        if orbital.eccentricity > self.CIRCULAR_ORBIT_TOLERANCE:
            warnings.append(
                f"Orbit eccentricity {orbital.eccentricity:.4f} "
                f"(threshold: {self.CIRCULAR_ORBIT_TOLERANCE})"
            )

        # If approaching apoapsis and need to circularize
        if (
            orbital.time_to_apoapsis < 60
            and orbital.eccentricity > self.CIRCULAR_ORBIT_TOLERANCE
            and orbital.periapsis < self.MIN_PERIAPSIS_KERBIN
        ):
            actions.append(
                CommandRequest(
                    source_seat=self.seat_name,
                    command_type="lock_steering",
                    parameters={"direction": "PROGRADE"},
                    priority=CommandPriority.HIGH,
                    authority_required=AuthorityLevel.EXECUTE,
                    rationale="Approaching apoapsis — align prograde for circularization",
                )
            )

        if constraints:
            return SeatRecommendation(
                seat=self.seat_name,
                go_nogo="NO_GO",
                status_summary=f"Trajectory constraint violation: {constraints[0]}",
                constraints=constraints,
                warnings=warnings,
                recommended_actions=actions,
            )

        return SeatRecommendation(
            seat=self.seat_name,
            go_nogo="GO",
            status_summary=(
                f"Orbit {orbital.periapsis / 1000:.1f}km x {orbital.apoapsis / 1000:.1f}km, "
                f"e={orbital.eccentricity:.4f}"
            ),
            constraints=[],
            warnings=warnings,
            recommended_actions=actions,
        )
