"""Command schemas — what agents can request and what gets sent to kOS."""

from enum import Enum
from pydantic import BaseModel


class CommandPriority(str, Enum):
    CRITICAL = "critical"  # abort, emergency
    HIGH = "high"  # burns, staging
    NORMAL = "normal"  # attitude adjustments
    LOW = "low"  # telemetry requests


class AuthorityLevel(str, Enum):
    COMMAND = "command"  # Flight Director — can issue anything
    EXECUTE = "execute"  # FIDO, GUIDO, GNC — can issue burns/attitude
    RECOMMEND = "recommend"  # EECOM, RETRO, TELMU — can only recommend
    COMMUNICATE = "communicate"  # CAPCOM — translates for crew


class GoNoGo(str, Enum):
    GO = "GO"
    NO_GO = "NO_GO"
    STANDBY = "STANDBY"


class SeatRecommendation(BaseModel):
    """Output from a seat agent each tick."""

    seat: str
    go_nogo: GoNoGo
    status_summary: str
    constraints: list[str]  # things that must be true for GO
    warnings: list[str]  # potential issues
    recommended_actions: list["CommandRequest"]


class CommandRequest(BaseModel):
    """A command an agent wants to execute."""

    source_seat: str
    command_type: str  # "burn", "stage", "attitude", "throttle", "sas", "rcs", etc.
    parameters: dict[str, float | str | bool]
    priority: CommandPriority
    authority_required: AuthorityLevel
    rationale: str


class BurnCommand(BaseModel):
    """A planned engine burn."""

    delta_v: float  # m/s
    direction: str  # "prograde", "retrograde", "normal", "antinormal", "radial_in", "radial_out"
    burn_time: float  # seconds
    start_time: float  # MET to start burn
    engine: str  # which engine to use


class AttitudeCommand(BaseModel):
    """Attitude adjustment."""

    heading: float | None = None
    pitch: float | None = None
    roll: float | None = None
    target: str | None = None  # "prograde", "retrograde", "target", etc.


class FlightDirectorDecision(BaseModel):
    """The Flight Director's final word each decision cycle."""

    cycle_number: int
    mission_time: float
    overall_status: GoNoGo
    seat_statuses: dict[str, GoNoGo]
    approved_commands: list[CommandRequest]
    rejected_commands: list[CommandRequest]
    flight_notes: str


# Rebuild forward refs
SeatRecommendation.model_rebuild()
