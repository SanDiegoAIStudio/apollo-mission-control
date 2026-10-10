"""Command dispatch — translates approved commands into kOS instructions."""

import math
from collections import deque
from collections.abc import Callable
from typing import TYPE_CHECKING, NamedTuple

import structlog

from apollo_mc.schemas.commands import CommandRequest

if TYPE_CHECKING:
    from apollo_mc.bridge.kos_client import KosBridge

logger = structlog.get_logger()

# Normal and radial steering need vector expressions and are tracked in an issue.
STEERING_DIRECTIONS: frozenset[str] = frozenset(
    {
        "PROGRADE",
        "RETROGRADE",
        "SRFPROGRADE",
        "SRFRETROGRADE",
        "UP",
        "NORTH",
    }
)


class CommandLogEntry(NamedTuple):
    mission_time: float
    seat: str
    kos_command: str


COMMAND_LOG_SIZE = 1000


class CommandDispatcher:
    """Translates CommandRequest objects into kOS telnet commands."""

    # Maps our command types to kOS command templates
    KOS_TEMPLATES: dict[str, str] = {
        "throttle": "SET SHIP:CONTROL:PILOTMAINTHROTTLE TO {value}.",
        "stage": "STAGE.",
        "sas_on": "SAS ON.",
        "sas_off": "SAS OFF.",
        "rcs_on": "RCS ON.",
        "rcs_off": "RCS OFF.",
        "lock_steering": "LOCK STEERING TO {direction}.",
        "lock_throttle": "LOCK THROTTLE TO {value}.",
        "warp": "SET WARP TO {value}.",
        "execute_node": "EXECUTE_NODE().",  # Requires helper script
    }

    def __init__(self, bridge: "KosBridge | None" = None) -> None:
        self._bridge = bridge
        self._command_log: deque[CommandLogEntry] = deque(maxlen=COMMAND_LOG_SIZE)

    @property
    def command_log(self) -> tuple[CommandLogEntry, ...]:
        """Holds commands that reached kOS (or ran with no bridge)."""
        return tuple(self._command_log)

    def translate(self, command: CommandRequest) -> str | None:
        """Convert a CommandRequest to a kOS command string."""
        template = self.KOS_TEMPLATES.get(command.command_type)
        if template is None:
            logger.warning(
                "unknown_command_type",
                command_type=command.command_type,
                source=command.source_seat,
            )
            return None

        spec = _PARAMETER_CHECKS.get(command.command_type)
        if spec is None:
            return template

        key, check = spec
        if key not in command.parameters:
            logger.error(
                "command_parameter_missing",
                command_type=command.command_type,
                key=key,
            )
            return None

        try:
            text = check(command.parameters[key])
        except ValueError as exc:
            logger.error(
                "command_parameter_invalid",
                command_type=command.command_type,
                key=key,
                reason=str(exc),
            )
            return None
        return template.format(**{key: text})

    async def dispatch(self, command: CommandRequest, mission_time: float) -> bool:
        """Translate and send a command to kOS."""
        kos_cmd = self.translate(command)
        if kos_cmd is None:
            return False

        if self._bridge is not None:
            try:
                await self._bridge.send_command(kos_cmd)
            except (OSError, UnicodeDecodeError, ValueError) as exc:
                logger.error(
                    "command_send_failed",
                    seat=command.source_seat,
                    command_type=command.command_type,
                    error=str(exc),
                )
                return False

        logger.info(
            "command_dispatch",
            seat=command.source_seat,
            type=command.command_type,
            kos=kos_cmd,
            met=mission_time,
        )
        self._command_log.append(
            CommandLogEntry(mission_time, command.source_seat, kos_cmd)
        )
        return True


def _throttle_text(raw: object) -> str:
    if isinstance(raw, bool) or not isinstance(raw, int | float):
        raise ValueError("expected a number")
    if not math.isfinite(raw):
        raise ValueError("value must be finite")
    if raw < 0.0 or raw > 1.0:
        raise ValueError("value must be between 0.0 and 1.0 inclusive")
    return format(float(raw) + 0.0, ".4f")


def _warp_text(raw: object) -> str:
    if isinstance(raw, bool) or not isinstance(raw, int | float):
        raise ValueError("expected an int")
    if not math.isfinite(raw) or not float(raw).is_integer():
        raise ValueError("expected an int")
    if raw < 0 or raw > 7:
        raise ValueError("value must be between 0 and 7 inclusive")
    return str(int(raw))


def _steering_text(raw: object) -> str:
    if not isinstance(raw, str):
        raise ValueError("expected a string")
    direction = raw.upper()
    if direction not in STEERING_DIRECTIONS:
        raise ValueError("unknown steering direction")
    return direction


_PARAMETER_CHECKS: dict[str, tuple[str, Callable[[object], str]]] = {
    "throttle": ("value", _throttle_text),
    "lock_throttle": ("value", _throttle_text),
    "warp": ("value", _warp_text),
    "lock_steering": ("direction", _steering_text),
}
