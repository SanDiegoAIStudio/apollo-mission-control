"""CAPCOM — Capsule Communicator.

The voice of Mission Control. Translates technical decisions from all seats
into crew-readable communications. In our sim, this produces human-readable
mission log entries and status messages.
"""

from apollo_mc.agents.base import SeatAgent
from apollo_mc.schemas.commands import AuthorityLevel, GoNoGo, SeatRecommendation
from apollo_mc.schemas.telemetry import TelemetryFrame


class CapcomAgent(SeatAgent):
    seat_name = "CAPCOM"
    authority = AuthorityLevel.COMMUNICATE

    async def evaluate(self, frame: TelemetryFrame) -> SeatRecommendation:
        """CAPCOM always reports GO unless comms are down."""
        if not frame.comms_connected:
            return self.no_go("Loss of signal", ["Communications link lost"])

        return self.go(f"Comms nominal, MET {frame.timestamp:.0f}s")

    def format_status_for_crew(
        self,
        seat_recommendations: dict[str, SeatRecommendation],
    ) -> str:
        """Generate a crew-readable status message from all seat outputs."""
        lines: list[str] = []
        lines.append("--- MISSION CONTROL STATUS ---")

        for seat, rec in sorted(seat_recommendations.items()):
            icon = "GO" if rec.go_nogo == GoNoGo.GO else "NO GO"
            lines.append(f"  {seat:>8}: [{icon}] {rec.status_summary}")

            for warning in rec.warnings:
                lines.append(f"           ! {warning}")

        overall = all(r.go_nogo == GoNoGo.GO for r in seat_recommendations.values())
        lines.append(f"\n  OVERALL: {'GO' if overall else 'NO GO'}")
        lines.append("---")

        return "\n".join(lines)
