"""kOS Telnet bridge — connects to KSP's kOS mod to read telemetry and send commands."""

import asyncio
import json
import structlog

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

logger = structlog.get_logger()


class KosBridge:
    """Async TCP client that talks to kOS telnet server.

    kOS exposes a telnet interface on a configurable port (default 5410).
    We send kOS commands as plain text and read responses.

    The bridge uses a helper kOS script (kos_scripts/telemetry_server.ks)
    running on the vessel that serializes telemetry as JSON.
    """

    def __init__(self, host: str = "127.0.0.1", port: int = 5410) -> None:
        self.host = host
        self.port = port
        self._reader: asyncio.StreamReader | None = None
        self._writer: asyncio.StreamWriter | None = None
        self._connected = False

    @property
    def connected(self) -> bool:
        return self._connected

    async def connect(self) -> None:
        """Establish TCP connection to kOS telnet server."""
        try:
            self._reader, self._writer = await asyncio.open_connection(
                self.host, self.port
            )
            self._connected = True
            logger.info("kos_connected", host=self.host, port=self.port)

            # Read the kOS welcome banner
            banner = await asyncio.wait_for(self._reader.readline(), timeout=5.0)
            logger.debug("kos_banner", banner=banner.decode().strip())
        except (ConnectionRefusedError, OSError) as e:
            self._connected = False
            logger.error("kos_connection_failed", host=self.host, port=self.port, error=str(e))
            raise

    async def disconnect(self) -> None:
        if self._writer is not None:
            self._writer.close()
            await self._writer.wait_closed()
            self._connected = False
            logger.info("kos_disconnected")

    async def send_command(self, command: str) -> str:
        """Send a kOS command and return the response."""
        if not self._connected or self._writer is None or self._reader is None:
            raise ConnectionError("Not connected to kOS")

        self._writer.write(f"{command}\n".encode())
        await self._writer.drain()

        response = await asyncio.wait_for(self._reader.readline(), timeout=10.0)
        return response.decode().strip()

    async def read_telemetry(self) -> TelemetryFrame:
        """Request a telemetry dump from the kOS helper script and parse it.

        Sends the TELEMETRY_DUMP command which triggers the kOS-side script
        to print a JSON blob of current vessel state.
        """
        raw = await self.send_command("TELEMETRY_DUMP().")
        data = json.loads(raw)
        return self._parse_telemetry(data)

    def _parse_telemetry(self, data: dict) -> TelemetryFrame:  # type: ignore[type-arg]
        """Parse raw kOS JSON into our TelemetryFrame schema."""
        vessel = data["vessel"]
        orbital = data["orbital"]

        return TelemetryFrame(
            timestamp=data["met"],
            phase=MissionPhase(data.get("phase", "orbit")),
            vessel=VesselState(
                mission_time=data["met"],
                mass=vessel["mass"],
                position=Vector3(x=vessel["pos_x"], y=vessel["pos_y"], z=vessel["pos_z"]),
                velocity=Vector3(x=vessel["vel_x"], y=vessel["vel_y"], z=vessel["vel_z"]),
                orbital=OrbitalState(
                    body=orbital["body"],
                    apoapsis=orbital["apoapsis"],
                    periapsis=orbital["periapsis"],
                    inclination=orbital["inclination"],
                    eccentricity=orbital["eccentricity"],
                    semi_major_axis=orbital["sma"],
                    time_to_apoapsis=orbital["eta_ap"],
                    time_to_periapsis=orbital["eta_pe"],
                    orbital_velocity=orbital["velocity"],
                    altitude=vessel["altitude"],
                ),
                heading=vessel["heading"],
                pitch=vessel["pitch"],
                roll=vessel["roll"],
                throttle=vessel["throttle"],
                stage_number=vessel["stage"],
                situation=vessel["situation"],
            ),
            engines=[
                EngineState(**eng) for eng in data.get("engines", [])
            ],
            resources=[
                ResourceLevel(**res) for res in data.get("resources", [])
            ],
            power=PowerState(
                electric_charge=ResourceLevel(**data["power"]["electric_charge"]),
                charge_rate=data["power"]["charge_rate"],
                solar_panels_deployed=data["power"]["solar_deployed"],
                fuel_cells_active=data["power"]["fuel_cells"],
            ),
            comms_connected=data.get("comms", True),
            crew_count=data.get("crew", 0),
        )
