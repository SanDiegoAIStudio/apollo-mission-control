"""Shared builders for telemetry fixtures."""

from apollo_mc.schemas.telemetry import (
    MissionPhase,
    OrbitalState,
    PowerState,
    ResourceLevel,
    TelemetryFrame,
    Vector3,
    VesselState,
)


def make_frame(
    periapsis: float = 80_000,
    apoapsis: float = 80_000,
    eccentricity: float = 0.001,
    electric_pct: float = 90.0,
    fuel_pct: float = 80.0,
    comms: bool = True,
    charge_rate: float = 1.0,
) -> TelemetryFrame:
    """Build a test telemetry frame with configurable parameters."""
    return TelemetryFrame(
        timestamp=1000.0,
        phase=MissionPhase.ORBIT,
        vessel=VesselState(
            mission_time=1000.0,
            mass=10_000,
            position=Vector3(x=0, y=680_000, z=0),
            velocity=Vector3(x=2280, y=0, z=0),
            orbital=OrbitalState(
                body="Kerbin",
                apoapsis=apoapsis,
                periapsis=periapsis,
                inclination=0,
                eccentricity=eccentricity,
                semi_major_axis=(apoapsis + periapsis) / 2 + 600_000,
                time_to_apoapsis=300,
                time_to_periapsis=600,
                orbital_velocity=2280,
                altitude=80_000,
            ),
            heading=90,
            pitch=0,
            roll=0,
            throttle=0,
            stage_number=2,
            situation="ORBITING",
        ),
        engines=[],
        resources=[
            ResourceLevel(name="LiquidFuel", amount=fuel_pct, max_amount=100),
            ResourceLevel(name="Oxidizer", amount=fuel_pct * 1.22, max_amount=122),
        ],
        power=PowerState(
            electric_charge=ResourceLevel(
                name="ElectricCharge",
                amount=electric_pct,
                max_amount=100,
            ),
            charge_rate=charge_rate,
            solar_panels_deployed=True,
            fuel_cells_active=False,
        ),
        comms_connected=comms,
        crew_count=3,
    )
