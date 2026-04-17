# Apollo Mission Control Instructions

Global preferences live in `~/.claude/CLAUDE.md`. This file defines local context for Apollo Mission Control.

Hand-reviewed: 2026-04-17.

## Project Identity

Apollo Mission Control is a Python 3.11+ multi-agent simulation of NASA Apollo-era flight control for a Kerbal Space Program Apollo 11 mission. Each controller seat has scoped telemetry, tools, authority boundaries, and role-specific prompts. The Flight Director aggregates controller recommendations and dispatches commands through kOS.

## Setup

```bash
uv venv --python 3.11
source .venv/bin/activate
uv pip install -e '.[dev]'
```

Install optional extras only when needed:

```bash
uv pip install -e '.[openai]'
uv pip install -e '.[dashboard]'
```

## Verification

```bash
uv run pytest
uv run ruff check .
uv run mypy src
```

For kOS or KSP integration work, also verify against the simulator/bridge path described in the README and docs.

## Architecture

- `src/apollo_mc/` contains the Python package.
- `docs/` documents controller roles and system design.
- `prompts/` holds role-specific agent prompts.
- `procedures/` contains mission/control procedures.
- `kos_scripts/` contains KSP/kOS-side scripts.
- `tests/` contains Python tests.

## Boundaries

- Preserve controller authority boundaries; do not give every agent every tool.
- Treat telemetry schemas and command dispatch as safety-critical even though this is a simulation.
- Keep role prompts grounded in the real controller responsibility.
- Do not add paid-model or API requirements to core paths unless optional.

