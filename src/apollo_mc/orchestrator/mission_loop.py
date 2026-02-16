"""Main mission loop — ties everything together."""

import asyncio
import os

import structlog
from rich.console import Console
from rich.live import Live
from rich.table import Table

from apollo_mc.agents.capcom import CapcomAgent
from apollo_mc.agents.eecom import EecomAgent
from apollo_mc.agents.fido import FidoAgent
from apollo_mc.agents.flight import FlightDirectorAgent
from apollo_mc.bridge.kos_client import KosBridge
from apollo_mc.core.command_dispatch import CommandDispatcher
from apollo_mc.core.mission_state import MissionState
from apollo_mc.core.telemetry_bus import TelemetryBus
from apollo_mc.orchestrator.decision_cycle import DecisionCycle

logger = structlog.get_logger()
console = Console()


def build_status_table(state: MissionState) -> Table:
    """Build a rich table showing current mission status."""
    table = Table(title=f"MISSION CONTROL — {state.mission_name}", expand=True)
    table.add_column("Seat", style="bold cyan", width=10)
    table.add_column("Status", width=8)
    table.add_column("Summary", ratio=2)
    table.add_column("Warnings", ratio=1, style="yellow")

    for seat, rec in sorted(state.seat_recommendations.items()):
        status_style = "bold green" if rec.go_nogo.value == "GO" else "bold red"
        warnings = "; ".join(rec.warnings) if rec.warnings else "—"
        table.add_row(
            seat,
            f"[{status_style}]{rec.go_nogo.value}[/]",
            rec.status_summary,
            warnings,
        )

    if state.latest_telemetry:
        t = state.latest_telemetry
        table.caption = (
            f"MET: {t.timestamp:.1f}s | Phase: {t.phase.value} | "
            f"Cycle: {state.cycle_count} | "
            f"Alt: {t.vessel.orbital.altitude / 1000:.1f}km"
        )

    return table


async def run_mission() -> None:
    """Launch Mission Control and run the decision loop."""
    console.print("[bold blue]APOLLO MISSION CONTROL[/bold blue]")
    console.print("Initializing systems...\n")

    # Configuration
    kos_host = os.getenv("KOS_HOST", "127.0.0.1")
    kos_port = int(os.getenv("KOS_PORT", "5410"))
    tick_interval = float(os.getenv("TICK_INTERVAL_SEC", "2.0"))

    # Initialize core systems
    state = MissionState()
    bus = TelemetryBus()
    bridge = KosBridge(host=kos_host, port=kos_port)
    dispatcher = CommandDispatcher(bridge=bridge)

    # Initialize agents
    flight = FlightDirectorAgent(state)
    seats = [
        FidoAgent(state),
        EecomAgent(state),
        CapcomAgent(state),
    ]

    cycle = DecisionCycle(
        mission_state=state,
        telemetry_bus=bus,
        flight_director=flight,
        seats=seats,
        dispatcher=dispatcher,
    )

    # Connect to KSP
    console.print(f"Connecting to kOS at {kos_host}:{kos_port}...")
    try:
        await bridge.connect()
        console.print("[green]kOS connection established.[/green]\n")
    except ConnectionRefusedError:
        console.print("[red]Failed to connect to kOS.[/red]")
        console.print("Make sure KSP is running with kOS telnet enabled.")
        console.print(f"Expected at {kos_host}:{kos_port}")
        return

    # Main loop
    console.print("[bold]Mission Control is GO. Starting decision loop.[/bold]\n")

    with Live(build_status_table(state), console=console, refresh_per_second=1) as live:
        while not state.mission_complete and not state.abort_called:
            try:
                # Read telemetry
                frame = await bridge.read_telemetry()

                # Publish to bus
                await bus.publish(frame)

                # Run decision cycle
                await cycle.tick(frame)

                # Update display
                live.update(build_status_table(state))

                # Wait for next tick
                await asyncio.sleep(tick_interval)

            except ConnectionError:
                console.print("[red]Lost connection to kOS![/red]")
                break
            except KeyboardInterrupt:
                break

    # Cleanup
    await bridge.disconnect()
    console.print("\n[bold]Mission Control signing off.[/bold]")
