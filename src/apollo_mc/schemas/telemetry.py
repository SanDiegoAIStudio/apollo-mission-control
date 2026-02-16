"""Telemetry data models — the shared language between KSP and all agent seats."""

from enum import Enum
from pydantic import BaseModel


class MissionPhase(str, Enum):
    PRELAUNCH = "prelaunch"
    LAUNCH = "launch"
    ASCENT = "ascent"
    ORBIT = "orbit"
    TLI = "tli"  # Trans-Lunar Injection
    COAST = "coast"
    LOI = "loi"  # Lunar Orbit Insertion
    DESCENT = "descent"
    LANDING = "landing"
    SURFACE = "surface"
    ASCENT_LUNAR = "ascent_lunar"
    RENDEZVOUS = "rendezvous"
    TEI = "tei"  # Trans-Earth Injection
    REENTRY = "reentry"
    RECOVERY = "recovery"


class Vector3(BaseModel):
    x: float
    y: float
    z: float


class OrbitalState(BaseModel):
    """Keplerian orbital elements + useful derived values."""

    body: str  # "Kerbin", "Mun", etc.
    apoapsis: float  # meters
    periapsis: float  # meters
    inclination: float  # degrees
    eccentricity: float
    semi_major_axis: float  # meters
    time_to_apoapsis: float  # seconds
    time_to_periapsis: float  # seconds
    orbital_velocity: float  # m/s
    altitude: float  # meters above surface


class VesselState(BaseModel):
    """Core vessel telemetry — what the kOS bridge reads every tick."""

    mission_time: float  # seconds since launch
    mass: float  # kg
    position: Vector3
    velocity: Vector3
    orbital: OrbitalState
    heading: float  # degrees
    pitch: float  # degrees
    roll: float  # degrees
    throttle: float  # 0.0 - 1.0
    stage_number: int
    situation: str  # "ORBITING", "LANDED", "FLYING", etc.


class EngineState(BaseModel):
    """Propulsion system status."""

    engine_name: str
    active: bool
    thrust: float  # kN
    max_thrust: float  # kN
    isp: float  # seconds
    fuel_flow: float  # units/s
    flameout: bool


class ResourceLevel(BaseModel):
    """A single resource (LiquidFuel, Oxidizer, ElectricCharge, etc.)."""

    name: str
    amount: float
    max_amount: float

    @property
    def percentage(self) -> float:
        if self.max_amount == 0:
            return 0.0
        return (self.amount / self.max_amount) * 100.0


class PowerState(BaseModel):
    """Electrical system status."""

    electric_charge: ResourceLevel
    charge_rate: float  # units/s (positive = generating)
    solar_panels_deployed: bool
    fuel_cells_active: bool


class TelemetryFrame(BaseModel):
    """One complete telemetry snapshot — published every tick."""

    timestamp: float  # mission elapsed time
    phase: MissionPhase
    vessel: VesselState
    engines: list[EngineState]
    resources: list[ResourceLevel]
    power: PowerState
    comms_connected: bool
    crew_count: int
