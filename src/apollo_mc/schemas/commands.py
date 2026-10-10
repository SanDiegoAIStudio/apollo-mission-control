"""Command schemas — what agents can request and what gets sent to kOS."""

import re
from enum import StrEnum

from pydantic import BaseModel, field_validator

Parameters = dict[str, float | str | bool]

_PARAMETER_TOKEN = re.compile(r"[A-Za-z0-9_]+")


class CommandPriority(StrEnum):
    CRITICAL = "critical"  # abort, emergency
    HIGH = "high"  # burns, staging
    NORMAL = "normal"  # attitude adjustments
    LOW = "low"  # telemetry requests


class AuthorityLevel(StrEnum):
    COMMAND = "command"  # Flight Director — can issue anything
    EXECUTE = "execute"  # FIDO, GUIDO, GNC — can issue burns/attitude
    RECOMMEND = "recommend"  # EECOM, RETRO, TELMU — can only recommend
    COMMUNICATE = "communicate"  # CAPCOM — translates for crew


class GoNoGo(StrEnum):
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
    parameters: Parameters
    priority: CommandPriority
    authority_required: AuthorityLevel
    rationale: str

    # Parameters are kOS tokens the dispatcher interpolates; human text belongs in rationale.
    @field_validator("parameters")
    @classmethod
    def reject_unsafe_parameter_strings(cls, value: Parameters) -> Parameters:
        for key, item in value.items():
            if isinstance(item, str) and _PARAMETER_TOKEN.fullmatch(item) is None:
                raise ValueError(
                    f"parameter {key!r} does not match {_PARAMETER_TOKEN.pattern}"
                )
        return value


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
