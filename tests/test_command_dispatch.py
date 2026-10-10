# source: docs/code-review-2026-06-15/REVIEW.md, findings on CommandDispatcher and CommandRequest
"""Tests for command translation and dispatch."""

import pytest
from pydantic import ValidationError

from apollo_mc.bridge.kos_client import KosBridge
from apollo_mc.core.command_dispatch import (
    COMMAND_LOG_SIZE,
    CommandDispatcher,
    CommandLogEntry,
)
from apollo_mc.schemas.commands import (
    AuthorityLevel,
    CommandPriority,
    CommandRequest,
    Parameters,
)


def _command(
    command_type: str,
    parameters: Parameters | None = None,
) -> CommandRequest:
    return CommandRequest(
        source_seat="FIDO",
        command_type=command_type,
        parameters=parameters or {},
        priority=CommandPriority.NORMAL,
        authority_required=AuthorityLevel.EXECUTE,
        rationale="test",
    )


@pytest.mark.parametrize(
    ("command_type", "parameters", "expected"),
    [
        (
            "throttle",
            {"value": 0.5},
            "SET SHIP:CONTROL:PILOTMAINTHROTTLE TO 0.5000.",
        ),
        (
            "throttle",
            {"value": -0.0},
            "SET SHIP:CONTROL:PILOTMAINTHROTTLE TO 0.0000.",
        ),
        (
            "throttle",
            {"value": 1e-05},
            "SET SHIP:CONTROL:PILOTMAINTHROTTLE TO 0.0000.",
        ),
        ("stage", {"unused": 1}, "STAGE."),
        ("sas_on", {}, "SAS ON."),
        ("sas_off", {}, "SAS OFF."),
        ("rcs_on", {}, "RCS ON."),
        ("rcs_off", {}, "RCS OFF."),
        (
            "lock_steering",
            {"direction": "PROGRADE"},
            "LOCK STEERING TO PROGRADE.",
        ),
        (
            "lock_throttle",
            {"value": 0.25},
            "LOCK THROTTLE TO 0.2500.",
        ),
        ("lock_throttle", {"value": 1}, "LOCK THROTTLE TO 1.0000."),
        ("warp", {"value": 3}, "SET WARP TO 3."),
        ("warp", {"value": 3.0}, "SET WARP TO 3."),
        ("execute_node", {}, "EXECUTE_NODE()."),
    ],
)
def test_translate_valid_commands(
    command_type: str,
    parameters: Parameters,
    expected: str,
) -> None:
    # source: No test coverage for CommandDispatcher - critical command translation path
    assert CommandDispatcher().translate(_command(command_type, parameters)) == expected


def test_parameters_reject_injected_direction() -> None:
    # source: Unvalidated Command Parameters in CommandRequest Schema
    with pytest.raises(ValidationError) as caught:
        _command("lock_steering", {"direction": "PROGRADE. STAGE"})
    assert "direction" in str(caught.value)


@pytest.mark.parametrize(
    ("command_type", "parameters"),
    [
        ("lock_steering", {"direction": "sideways"}),
        ("lock_steering", {"direction": "NORMAL"}),
        ("lock_steering", {"direction": 5}),
        ("throttle", {"value": 1.5}),
        ("throttle", {"value": True}),
        ("throttle", {"value": float("nan")}),
        ("throttle", {"value": float("inf")}),
        ("throttle", {}),
        ("warp", {"value": 2.5}),
        ("warp", {"value": float("nan")}),
        ("warp", {"value": -1}),
        ("warp", {"value": 8}),
        ("warp", {"value": True}),
        ("not_a_command", {}),
    ],
)
def test_translate_rejects_invalid(command_type: str, parameters: Parameters) -> None:
    # source: No test coverage for CommandDispatcher - critical command translation path
    assert CommandDispatcher().translate(_command(command_type, parameters)) is None


class _TimeoutBridge(KosBridge):
    async def send_command(self, command: str) -> str:
        raise TimeoutError("kOS timed out")


class _RecordingBridge(KosBridge):
    def __init__(self) -> None:
        super().__init__()
        self.received: list[str] = []

    async def send_command(self, command: str) -> str:
        self.received.append(command)
        return "ok"


class _ConnectionErrorBridge(KosBridge):
    async def send_command(self, command: str) -> str:
        raise ConnectionError("kOS closed the connection")


class _DecodeErrorBridge(KosBridge):
    async def send_command(self, command: str) -> str:
        raise UnicodeDecodeError("utf-8", b"\xff", 0, 1, "invalid start byte")


async def test_dispatch_timeout_leaves_log_empty() -> None:
    # source: Incomplete command dispatch error handling
    dispatcher = CommandDispatcher(bridge=_TimeoutBridge())
    ok = await dispatcher.dispatch(_command("stage"), 10.0)
    assert ok is False
    assert dispatcher.command_log == ()


async def test_dispatch_success_records_command() -> None:
    # source: No test coverage for CommandDispatcher - critical command translation path
    bridge = _RecordingBridge()
    dispatcher = CommandDispatcher(bridge=bridge)
    ok = await dispatcher.dispatch(_command("stage"), 12.0)
    assert ok is True
    assert bridge.received == ["STAGE."]
    assert dispatcher.command_log == (CommandLogEntry(12.0, "FIDO", "STAGE."),)


async def test_dispatch_connection_error_returns_false() -> None:
    # source: Incomplete command dispatch error handling
    dispatcher = CommandDispatcher(bridge=_ConnectionErrorBridge())
    ok = await dispatcher.dispatch(_command("stage"), 10.0)
    assert ok is False
    assert dispatcher.command_log == ()


async def test_dispatch_unicode_decode_error_returns_false() -> None:
    # source: Incomplete command dispatch error handling
    dispatcher = CommandDispatcher(bridge=_DecodeErrorBridge())
    ok = await dispatcher.dispatch(_command("stage"), 10.0)
    assert ok is False
    assert dispatcher.command_log == ()


async def test_command_log_keeps_last_1000() -> None:
    # source: Command log array unbounded growth in CommandDispatcher
    dispatcher = CommandDispatcher()
    command = _command("stage")
    for mission_time in range(COMMAND_LOG_SIZE + 1):
        ok = await dispatcher.dispatch(command, float(mission_time))
        assert ok is True
    assert len(dispatcher.command_log) == COMMAND_LOG_SIZE
    assert dispatcher.command_log[0][0] == 1.0
    assert dispatcher.command_log[-1][0] == float(COMMAND_LOG_SIZE)
