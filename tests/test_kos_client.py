"""Tests for kOS telemetry parsing and read failures."""

import asyncio
import json
from typing import Any

import pytest

from apollo_mc.bridge.kos_client import KosBridge, TelemetryError
from apollo_mc.schemas.telemetry import TelemetryFrame


def _minimal_telemetry() -> dict[str, Any]:
    return {
        "met": 10.0,
        "phase": "orbit",
        "vessel": {
            "mass": 1000.0,
            "pos_x": 0.0,
            "pos_y": 700000.0,
            "pos_z": 0.0,
            "vel_x": 2200.0,
            "vel_y": 0.0,
            "vel_z": 0.0,
            "altitude": 80000.0,
            "heading": 90.0,
            "pitch": 0.0,
            "roll": 0.0,
            "throttle": 0.0,
            "stage": 2,
            "situation": "ORBITING",
        },
        "orbital": {
            "body": "Kerbin",
            "apoapsis": 80000.0,
            "periapsis": 80000.0,
            "inclination": 0.0,
            "eccentricity": 0.0,
            "sma": 680000.0,
            "eta_ap": 300.0,
            "eta_pe": 600.0,
            "velocity": 2200.0,
        },
        "engines": [],
        "resources": [],
        "power": {
            "electric_charge": {
                "name": "ElectricCharge",
                "amount": 90.0,
                "max_amount": 100.0,
            },
            "charge_rate": 1.0,
            "solar_deployed": True,
            "fuel_cells": False,
        },
        "comms": True,
        "crew": 3,
    }


class _IdleWriter:
    def write(self, data: bytes) -> None:
        return None

    async def drain(self) -> None:
        return None

    def close(self) -> None:
        return None

    async def wait_closed(self) -> None:
        return None


class _ResponseBridge(KosBridge):
    def __init__(self, response: str) -> None:
        super().__init__()
        self._response = response

    async def send_command(self, command: str) -> str:
        return self._response


class _TimeoutBridge(KosBridge):
    async def send_command(self, command: str) -> str:
        raise TimeoutError("timed out")


def _connected_bridge(
    data: bytes | None = None,
    *,
    eof: bool = False,
    command_timeout: float = 10.0,
) -> KosBridge:
    reader = asyncio.StreamReader()
    if data is not None:
        reader.feed_data(data)
    if eof:
        reader.feed_eof()
    bridge = KosBridge(command_timeout=command_timeout)
    bridge._connected = True
    bridge._reader = reader
    bridge._writer = _IdleWriter()
    return bridge


def test_parse_empty_payload_raises() -> None:
    # source: REVIEW.md Unhandled KeyError exceptions in telemetry parsing
    with pytest.raises(TelemetryError):
        KosBridge()._parse_telemetry({})


def test_parse_missing_power_names_key() -> None:
    # source: REVIEW.md Unhandled KeyError exceptions in telemetry parsing
    payload = _minimal_telemetry()
    del payload["power"]
    with pytest.raises(TelemetryError) as caught:
        KosBridge()._parse_telemetry(payload)
    assert "power" in str(caught.value)


def test_parse_minimal_payload() -> None:
    # source: REVIEW.md Untyped dict parameter with type: ignore suppression
    frame = KosBridge()._parse_telemetry(_minimal_telemetry())
    assert isinstance(frame, TelemetryFrame)
    assert frame.vessel.orbital.altitude == 80000.0


def test_parse_rejects_non_finite_mass() -> None:
    # source: non-finite telemetry parses as valid
    payload = _minimal_telemetry()
    payload["vessel"]["mass"] = float("nan")
    with pytest.raises(TelemetryError):
        KosBridge()._parse_telemetry(payload)


async def test_read_telemetry_rejects_non_json() -> None:
    # source: REVIEW.md Unhandled JSON parse exceptions in telemetry bridge
    bridge = _ResponseBridge("not json")
    with pytest.raises(TelemetryError) as caught:
        await bridge.read_telemetry()
    assert "not json" in str(caught.value)
    assert isinstance(caught.value.__cause__, json.JSONDecodeError)


async def test_read_telemetry_timeout_is_telemetry_error() -> None:
    # source: Unhandled JSON parse exceptions in telemetry bridge
    with pytest.raises(TelemetryError) as caught:
        await _TimeoutBridge().read_telemetry()
    assert "timeout" in str(caught.value)


async def test_read_telemetry_rejects_non_object() -> None:
    # source: Unhandled JSON parse exceptions in telemetry bridge
    with pytest.raises(TelemetryError) as caught:
        await _ResponseBridge("[1, 2]").read_telemetry()
    assert "not an object" in str(caught.value)


async def test_undecodable_reply_is_not_a_successful_read() -> None:
    # source: kOS bridge leaks UnicodeDecodeError and ValueError
    bridge = _connected_bridge(b"\xff\n", eof=True)
    with pytest.raises(UnicodeDecodeError):
        await bridge.send_command("TELEMETRY_DUMP().")
    with pytest.raises(TelemetryError) as caught:
        await _connected_bridge(b"\xff\n", eof=True).read_telemetry()
    assert "telemetry read failed" in str(caught.value)


async def test_send_command_eof_raises_connection_error() -> None:
    # source: EOF counts as a successful send
    bridge = _connected_bridge(eof=True)
    with pytest.raises(ConnectionError):
        await bridge.send_command("STAGE.")
    assert bridge.connected is False


async def test_send_command_timeout_drops_connection() -> None:
    # source: timed-out reply desynchronizes the request/response stream
    bridge = _connected_bridge(command_timeout=0.01)
    with pytest.raises(TimeoutError):
        await bridge.send_command("STAGE.")
    assert bridge.connected is False


class _NestedJsonBridge(KosBridge):
    async def send_command(self, command: str) -> str:
        return "[" * 100_000 + "]" * 100_000


async def test_read_telemetry_rejects_deeply_nested_json() -> None:
    # source: Codex pass 2, RecursionError from json.loads escaped run_mission
    with pytest.raises(TelemetryError):
        await _NestedJsonBridge().read_telemetry()


class _SilentWriter:
    def write(self, data: bytes) -> None:
        return None

    async def drain(self) -> None:
        return None

    def close(self) -> None:
        return None

    async def wait_closed(self) -> None:
        return None


async def test_connect_silent_banner_raises_connection_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # source: Codex pass 2, a kOS that never sends its banner escaped run_mission as TimeoutError
    reader = asyncio.StreamReader()

    async def fake_open_connection(
        host: str, port: int
    ) -> tuple[asyncio.StreamReader, _SilentWriter]:
        return reader, _SilentWriter()

    monkeypatch.setattr(asyncio, "open_connection", fake_open_connection)
    bridge = KosBridge(banner_timeout=0.01)
    with pytest.raises(ConnectionError):
        await bridge.connect()
    assert bridge.connected is False


async def test_connect_overlong_banner_raises_connection_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # source: Codex pass 3, a banner line over the 64 KiB reader limit escaped connect()
    reader = asyncio.StreamReader()
    reader.feed_data(b"x" * 65_537 + b"\n")
    reader.feed_eof()

    async def fake_open_connection(
        host: str, port: int
    ) -> tuple[asyncio.StreamReader, _SilentWriter]:
        return reader, _SilentWriter()

    monkeypatch.setattr(asyncio, "open_connection", fake_open_connection)
    bridge = KosBridge()
    with pytest.raises(ConnectionError):
        await bridge.connect()
    assert bridge.connected is False
