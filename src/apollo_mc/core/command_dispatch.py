"""Command dispatch — translates approved commands into kOS instructions."""

import structlog

from apollo_mc.schemas.commands import CommandRequest

logger = structlog.get_logger()


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
        "lock_steering": 'LOCK STEERING TO {direction}.',
        "lock_throttle": "LOCK THROTTLE TO {value}.",
        "warp": "SET WARP TO {value}.",
        "execute_node": "EXECUTE_NODE().",  # Requires helper script
    }

    def __init__(self, bridge: "KosBridge | None" = None) -> None:  # noqa: F821
        self._bridge = bridge
        self._command_log: list[tuple[float, str, str]] = []  # (MET, seat, kos_cmd)

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

        try:
            kos_cmd = template.format(**command.parameters)
        except KeyError as e:
            logger.error(
                "command_parameter_missing",
                command_type=command.command_type,
                missing_key=str(e),
            )
            return None

        return kos_cmd

    async def dispatch(self, command: CommandRequest, mission_time: float) -> bool:
        """Translate and send a command to kOS."""
        kos_cmd = self.translate(command)
        if kos_cmd is None:
            return False

        logger.info(
            "command_dispatch",
            seat=command.source_seat,
            type=command.command_type,
            kos=kos_cmd,
            met=mission_time,
        )

        self._command_log.append((mission_time, command.source_seat, kos_cmd))

        if self._bridge is not None:
            await self._bridge.send_command(kos_cmd)

        return True
