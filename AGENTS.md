# Apollo Mission Control Agent Instructions

Use this file for Codex/agent work in Apollo Mission Control. Project background lives in `CLAUDE.md`.

## Commands

```bash
uv venv --python 3.11
source .venv/bin/activate
uv pip install -e '.[dev]'
uv run pytest
uv run ruff check .
uv run mypy src
```

## Working Rules

- Preserve flight-controller role boundaries and command authority.
- Treat telemetry schemas, kOS bridge code, and command dispatch as safety-critical simulation surfaces.
- Keep core dependencies light; optional model/dashboard integrations should remain optional.
- Add or update tests for controller logic, telemetry normalization, or command dispatch changes.
- Do not require live KSP/kOS for unit-testable behavior.

