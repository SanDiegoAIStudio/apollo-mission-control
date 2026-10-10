"""Tests for agent seat evaluation logic."""

import pytest

from apollo_mc.agents.capcom import CapcomAgent
from apollo_mc.agents.eecom import EecomAgent
from apollo_mc.agents.fido import FidoAgent
from apollo_mc.agents.flight import FlightDirectorAgent
from apollo_mc.core.mission_state import MissionState
from apollo_mc.schemas.commands import GoNoGo
from tests.factories import make_frame


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
