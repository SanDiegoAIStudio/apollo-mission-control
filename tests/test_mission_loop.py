"""Tests for the mission loop telemetry-error limit."""

import asyncio
import errno

import pytest

from apollo_mc.bridge.kos_client import TelemetryError
from apollo_mc.orchestrator.mission_loop import run_mission
from apollo_mc.schemas.telemetry import TelemetryFrame
from tests.factories import make_frame


def _install(
    monkeypatch: pytest.MonkeyPatch,
    script: list[TelemetryFrame | Exception],
    connect_error: Exception | None = None,
) -> type:
    class FakeKosBridge:
        def __init__(
            self,
            host: str = "127.0.0.1",
            port: int = 5410,
            command_timeout: float = 10.0,
            banner_timeout: float = 5.0,
        ) -> None:
            self.host = host
            self.port = port
            self.command_timeout = command_timeout
            self.banner_timeout = banner_timeout
            self.reads = 0
            self.disconnected = False
            FakeKosBridge.instance = self

        async def connect(self) -> None:
            if connect_error is not None:
                raise connect_error

        async def read_telemetry(self) -> TelemetryFrame:
            self.reads += 1
            if not script:
                await asyncio.Event().wait()
            item = script.pop(0)
            if isinstance(item, BaseException):
                raise item
            return item

        async def disconnect(self) -> None:
            self.disconnected = True

    monkeypatch.setattr(
        "apollo_mc.orchestrator.mission_loop.KosBridge",
        FakeKosBridge,
    )
    return FakeKosBridge


async def test_five_telemetry_errors_stop_the_loop(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # source: consecutive telemetry errors stop the mission loop
    monkeypatch.setenv("TICK_INTERVAL_SEC", "0")
    script = [TelemetryError("read failed") for _ in range(5)]
    bridge_type = _install(monkeypatch, script)
    await asyncio.wait_for(run_mission(), timeout=2.0)
    bridge = bridge_type.instance
    assert bridge.reads == 5
    assert bridge.disconnected is True


async def test_telemetry_errors_reset_after_a_good_frame(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # source: consecutive telemetry errors stop the mission loop
    monkeypatch.setenv("TICK_INTERVAL_SEC", "0")
    script: list[TelemetryFrame | TelemetryError] = [
        *[TelemetryError("read failed") for _ in range(4)],
        make_frame(),
        *[TelemetryError("read failed") for _ in range(5)],
    ]
    bridge_type = _install(monkeypatch, script)
    await asyncio.wait_for(run_mission(), timeout=2.0)
    bridge = bridge_type.instance
    assert bridge.reads == 10
    assert bridge.disconnected is True


async def test_connect_failure_returns_without_raising(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # source: Codex pass 2, connect() errors other than ConnectionRefusedError escaped run_mission
    monkeypatch.setenv("TICK_INTERVAL_SEC", "0")
    bridge_type = _install(monkeypatch, [], connect_error=ConnectionError("no banner"))
    await asyncio.wait_for(run_mission(), timeout=2.0)
    assert bridge_type.instance.reads == 0


async def test_transport_oserror_stops_the_loop(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # source: Codex pass 3, an OSError that is not a ConnectionError escaped run_mission
    monkeypatch.setenv("TICK_INTERVAL_SEC", "0")
    script: list[TelemetryFrame | Exception] = [
        make_frame(),
        OSError(errno.ENETDOWN, "Network is down"),
    ]
    bridge_type = _install(monkeypatch, script)
    await asyncio.wait_for(run_mission(), timeout=2.0)
    bridge = bridge_type.instance
    assert bridge.reads == 2
    assert bridge.disconnected is True
