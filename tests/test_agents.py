"""Tests for agent seat evaluation logic."""

import pytest

from apollo_mc.agents.capcom import CapcomAgent
from apollo_mc.agents.eecom import EecomAgent
from apollo_mc.agents.fido import FidoAgent
from apollo_mc.agents.flight import FlightDirectorAgent
from apollo_mc.core.mission_state import MissionState
from apollo_mc.schemas.commands import GoNoGo
from apollo_mc.schemas.telemetry import (
    EngineState,
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


@pytest.mark.asyncio
async def test_fido_go_on_stable_orbit() -> None:
    state = MissionState()
    agent = FidoAgent(state)
    frame = make_frame(periapsis=80_000, apoapsis=82_000, eccentricity=0.001)
    rec = await agent.evaluate(frame)
    assert rec.go_nogo == GoNoGo.GO


@pytest.mark.asyncio
async def test_fido_no_go_on_low_periapsis() -> None:
    state = MissionState()
    agent = FidoAgent(state)
    frame = make_frame(periapsis=50_000)  # below 70km atmosphere
    rec = await agent.evaluate(frame)
    assert rec.go_nogo == GoNoGo.NO_GO


@pytest.mark.asyncio
async def test_eecom_go_on_healthy_power() -> None:
    state = MissionState()
    agent = EecomAgent(state)
    frame = make_frame(electric_pct=90.0, fuel_pct=80.0)
    rec = await agent.evaluate(frame)
    assert rec.go_nogo == GoNoGo.GO


@pytest.mark.asyncio
async def test_eecom_no_go_on_critical_power() -> None:
    state = MissionState()
    agent = EecomAgent(state)
    frame = make_frame(electric_pct=5.0)
    rec = await agent.evaluate(frame)
    assert rec.go_nogo == GoNoGo.NO_GO


@pytest.mark.asyncio
async def test_eecom_warning_on_low_fuel() -> None:
    state = MissionState()
    agent = EecomAgent(state)
    frame = make_frame(fuel_pct=12.0)
    rec = await agent.evaluate(frame)
    assert len(rec.warnings) > 0


@pytest.mark.asyncio
async def test_capcom_go_with_comms() -> None:
    state = MissionState()
    agent = CapcomAgent(state)
    frame = make_frame(comms=True)
    rec = await agent.evaluate(frame)
    assert rec.go_nogo == GoNoGo.GO


@pytest.mark.asyncio
async def test_capcom_no_go_without_comms() -> None:
    state = MissionState()
    agent = CapcomAgent(state)
    frame = make_frame(comms=False)
    rec = await agent.evaluate(frame)
    assert rec.go_nogo == GoNoGo.NO_GO


@pytest.mark.asyncio
async def test_flight_director_go() -> None:
    state = MissionState()
    agent = FlightDirectorAgent(state)
    frame = make_frame()
    rec = await agent.evaluate(frame)
    assert rec.go_nogo == GoNoGo.GO


@pytest.mark.asyncio
async def test_flight_director_no_go_on_abort() -> None:
    state = MissionState()
    state.abort_called = True
    agent = FlightDirectorAgent(state)
    frame = make_frame()
    rec = await agent.evaluate(frame)
    assert rec.go_nogo == GoNoGo.NO_GO
