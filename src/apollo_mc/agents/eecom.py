"""EECOM — Electrical, Environmental & Consumables Manager.

Monitors power budgets, fuel cells, O2/H2 levels, thermal control,
and handles fault detection and response.
"""

from apollo_mc.agents.base import SeatAgent
from apollo_mc.schemas.commands import (
    AuthorityLevel,
    CommandPriority,
    CommandRequest,
    SeatRecommendation,
)
from apollo_mc.schemas.telemetry import TelemetryFrame


class EecomAgent(SeatAgent):
    seat_name = "EECOM"
    authority = AuthorityLevel.RECOMMEND
    telemetry_scope = ["power", "resources"]

    # Thresholds
    ELECTRIC_CHARGE_CRITICAL = 10.0  # percent
    ELECTRIC_CHARGE_WARNING = 25.0
    FUEL_CRITICAL = 5.0  # percent
    FUEL_WARNING = 15.0

    async def evaluate(self, frame: TelemetryFrame) -> SeatRecommendation:
        warnings: list[str] = []
        constraints: list[str] = []
        actions: list[CommandRequest] = []

        # Check electric charge
        ec_pct = frame.power.electric_charge.percentage
        if ec_pct < self.ELECTRIC_CHARGE_CRITICAL:
            constraints.append(
                f"Electric charge CRITICAL: {ec_pct:.1f}%"
            )
        elif ec_pct < self.ELECTRIC_CHARGE_WARNING:
            warnings.append(f"Electric charge low: {ec_pct:.1f}%")

        # Check propellant resources
        for resource in frame.resources:
            if resource.name in ("LiquidFuel", "Oxidizer"):
                pct = resource.percentage
                if pct < self.FUEL_CRITICAL:
                    constraints.append(f"{resource.name} CRITICAL: {pct:.1f}%")
                elif pct < self.FUEL_WARNING:
                    warnings.append(f"{resource.name} low: {pct:.1f}%")

        # Check power generation
        if frame.power.charge_rate < 0 and ec_pct < 50:
            warnings.append(
                f"Net power drain: {frame.power.charge_rate:.2f} units/s"
            )
            if not frame.power.solar_panels_deployed:
                actions.append(
                    CommandRequest(
                        source_seat=self.seat_name,
                        command_type="deploy_solar",
                        parameters={},
                        priority=CommandPriority.NORMAL,
                        authority_required=AuthorityLevel.RECOMMEND,
                        rationale="Power draining, solar panels not deployed",
                    )
                )

        if constraints:
            return SeatRecommendation(
                seat=self.seat_name,
                go_nogo="NO_GO",
                status_summary=f"Resource constraint: {constraints[0]}",
                constraints=constraints,
                warnings=warnings,
                recommended_actions=actions,
            )

        return SeatRecommendation(
            seat=self.seat_name,
            go_nogo="GO",
            status_summary=f"Power {ec_pct:.0f}%, charge rate {frame.power.charge_rate:+.2f}/s",
            constraints=[],
            warnings=warnings,
            recommended_actions=actions,
        )
