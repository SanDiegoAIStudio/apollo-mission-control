"""Entry point for running Apollo Mission Control."""

import asyncio
import sys

from apollo_mc.orchestrator.mission_loop import run_mission


def main() -> None:
    try:
        asyncio.run(run_mission())
    except KeyboardInterrupt:
        print("\n[FLIGHT] Mission Control shutting down.")
        sys.exit(0)


if __name__ == "__main__":
    main()
