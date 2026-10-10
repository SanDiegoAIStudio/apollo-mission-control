"""Tests for one decision-cycle tick."""

from apollo_mc.agents.base import SeatAgent
from apollo_mc.agents.capcom import CapcomAgent
from apollo_mc.agents.eecom import EecomAgent
from apollo_mc.agents.fido import FidoAgent
from apollo_mc.agents.flight import FlightDirectorAgent
from apollo_mc.core.command_dispatch import CommandDispatcher
from apollo_mc.core.mission_state import MissionState
from apollo_mc.core.telemetry_bus import TelemetryBus
from apollo_mc.orchestrator.decision_cycle import DecisionCycle
from apollo_mc.schemas.commands import (
    AuthorityLevel,
    CommandPriority,
    CommandRequest,
    GoNoGo,
    SeatRecommendation,
)
from apollo_mc.schemas.telemetry import TelemetryFrame
from tests.factories import make_frame


class _BoomSeat(SeatAgent):
    seat_name = "BOOM"
    authority = AuthorityLevel.RECOMMEND

    async def evaluate(self, frame: TelemetryFrame) -> SeatRecommendation:
        raise RuntimeError("seat blew up")


class _SteeringSeat(SeatAgent):
    seat_name = "GUIDO"
    authority = AuthorityLevel.EXECUTE

    async def evaluate(self, frame: TelemetryFrame) -> SeatRecommendation:
        return SeatRecommendation(
            seat=self.seat_name,
            go_nogo=GoNoGo.GO,
            status_summary="align prograde",
            constraints=[],
            warnings=[],
            recommended_actions=[
                CommandRequest(
                    source_seat=self.seat_name,
                    command_type="lock_steering",
                    parameters={"direction": "PROGRADE"},
                    priority=CommandPriority.HIGH,
                    authority_required=AuthorityLevel.EXECUTE,
                    rationale="align for the burn",
                )
            ],
        )


class _BoomFlight(FlightDirectorAgent):
    async def evaluate(self, frame: TelemetryFrame) -> SeatRecommendation:
        raise RuntimeError("flight director down")


class _RecordingDispatcher(CommandDispatcher):
    def __init__(self) -> None:
        super().__init__()
        self.calls: list[tuple[CommandRequest, float]] = []

    async def dispatch(self, command: CommandRequest, mission_time: float) -> bool:
        self.calls.append((command, mission_time))
        return True


class _TwoCommandSeat(SeatAgent):
    seat_name = "FIDO"
    authority = AuthorityLevel.EXECUTE

    async def evaluate(self, frame: TelemetryFrame) -> SeatRecommendation:
        throttle = CommandRequest(
            source_seat=self.seat_name,
            command_type="throttle",
            parameters={"value": 0.5},
            priority=CommandPriority.HIGH,
            authority_required=AuthorityLevel.EXECUTE,
            rationale="throttle up",
        )
        stage = CommandRequest(
            source_seat=self.seat_name,
            command_type="stage",
            parameters={},
            priority=CommandPriority.HIGH,
            authority_required=AuthorityLevel.EXECUTE,
            rationale="stage",
        )
        return SeatRecommendation(
            seat=self.seat_name,
            go_nogo=GoNoGo.GO,
            status_summary="two commands",
            constraints=[],
            warnings=[],
            recommended_actions=[throttle, stage],
        )


class _ExplodingDispatcher(CommandDispatcher):
    def __init__(self) -> None:
        super().__init__()
        self.calls: list[tuple[CommandRequest, float]] = []

    async def dispatch(self, command: CommandRequest, mission_time: float) -> bool:
        self.calls.append((command, mission_time))
        raise RuntimeError("dispatch failed")


class _RejectingDispatcher(CommandDispatcher):
    def __init__(self) -> None:
        super().__init__()
        self.calls: list[tuple[CommandRequest, float]] = []

    async def dispatch(self, command: CommandRequest, mission_time: float) -> bool:
        self.calls.append((command, mission_time))
        return False


def _cycle(
    state: MissionState,
    seats: list[SeatAgent],
    dispatcher: CommandDispatcher | None = None,
    flight: FlightDirectorAgent | None = None,
) -> DecisionCycle:
    return DecisionCycle(
        mission_state=state,
        telemetry_bus=TelemetryBus(),
        flight_director=flight or FlightDirectorAgent(state),
        seats=seats,
        dispatcher=dispatcher or CommandDispatcher(),
    )


async def test_tick_records_go_and_four_seats() -> None:
    # source: REVIEW.md No test coverage for DecisionCycle - core orchestration logic
    state = MissionState()
    seats = [FidoAgent(state), EecomAgent(state), CapcomAgent(state)]
    await _cycle(state, seats).tick(make_frame())
    assert state.latest_decision is not None
    assert state.latest_decision.overall_status == GoNoGo.GO
    assert set(state.seat_recommendations) == {"FIDO", "EECOM", "CAPCOM", "FLIGHT"}


async def test_tick_failed_seat_is_no_go() -> None:
    # source: crashed seat fails closed as NO_GO
    state = MissionState()
    seats = [
        FidoAgent(state),
        _BoomSeat(state),
        EecomAgent(state),
        CapcomAgent(state),
    ]
    await _cycle(state, seats).tick(make_frame())
    boom = state.seat_recommendations["BOOM"]
    assert boom.go_nogo == GoNoGo.NO_GO
    assert boom.status_summary == "evaluation failed"
    assert state.latest_decision is not None
    assert state.latest_decision.overall_status == GoNoGo.NO_GO


async def test_tick_flight_failure_becomes_no_go() -> None:
    # source: REVIEW.md Flight Director evaluation not wrapped in exception handling
    state = MissionState()
    flight = _BoomFlight(state)
    dispatcher = _RecordingDispatcher()
    await _cycle(
        state,
        [CapcomAgent(state), _SteeringSeat(state)],
        dispatcher=dispatcher,
        flight=flight,
    ).tick(make_frame())
    flight_rec = state.seat_recommendations["FLIGHT"]
    assert flight_rec.go_nogo == GoNoGo.NO_GO
    assert flight_rec.status_summary == "Flight Director evaluation failed"
    assert state.latest_decision is not None
    assert state.latest_decision.overall_status == GoNoGo.NO_GO
    assert dispatcher.calls == []


async def test_approved_command_reaches_dispatcher() -> None:
    # source: REVIEW.md No test coverage for DecisionCycle - core orchestration logic
    state = MissionState()
    dispatcher = _RecordingDispatcher()
    frame = make_frame()
    await _cycle(state, [_SteeringSeat(state)], dispatcher=dispatcher).tick(frame)
    assert len(dispatcher.calls) == 1
    command, mission_time = dispatcher.calls[0]
    assert command.command_type == "lock_steering"
    assert command.parameters["direction"] == "PROGRADE"
    assert mission_time == frame.timestamp
    assert state.latest_decision is not None
    assert state.latest_decision.approved_commands == [command]


async def test_dispatch_error_does_not_abort_tick() -> None:
    # source: REVIEW.md Command dispatch exceptions silently ignored
    state = MissionState()
    dispatcher = _ExplodingDispatcher()
    await _cycle(state, [_SteeringSeat(state)], dispatcher=dispatcher).tick(make_frame())
    assert state.latest_decision is not None
    assert len(state.command_history) == 1
    assert state.latest_decision.overall_status == GoNoGo.GO


async def test_dispatch_raise_aborts_the_batch() -> None:
    # source: failed dispatch stops the command batch
    state = MissionState()
    dispatcher = _ExplodingDispatcher()
    await _cycle(state, [_TwoCommandSeat(state)], dispatcher=dispatcher).tick(make_frame())
    assert len(dispatcher.calls) == 1
    assert dispatcher.calls[0][0].command_type == "throttle"


async def test_rejected_dispatch_aborts_the_batch() -> None:
    # source: failed dispatch stops the command batch
    state = MissionState()
    dispatcher = _RejectingDispatcher()
    await _cycle(state, [_TwoCommandSeat(state)], dispatcher=dispatcher).tick(make_frame())
    assert len(dispatcher.calls) == 1
    assert dispatcher.calls[0][0].command_type == "throttle"
    assert state.latest_decision is not None
