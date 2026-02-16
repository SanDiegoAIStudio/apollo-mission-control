# Contributing to Apollo Mission Control

Thanks for your interest in contributing! This project aims to build a multi-agent AI simulation of NASA's Apollo Mission Control, and there's plenty of work across many domains.

## Getting Started

1. Fork the repo
2. Clone your fork
3. Create a feature branch: `git checkout -b feat/your-feature`
4. Install dependencies:
   ```bash
   uv venv && source .venv/bin/activate
   uv pip install -e ".[dev]"
   ```
5. Make your changes
6. Run tests: `pytest`
7. Open a PR

## What We Need Help With

### Agent Seats
Each Apollo controller position needs its own agent implementation. Pick an unimplemented seat and build it:
- Define its telemetry inputs (what data does it watch?)
- Define its outputs (recommendations, constraints, commands)
- Write its system prompt in `prompts/`
- Implement the agent class in `src/apollo_mc/agents/`
- Add domain-specific tools in `src/apollo_mc/tools/`

### Mission Procedures
Real Apollo missions followed detailed procedures. Help encode these as structured playbooks:
- Launch and ascent procedures
- TLI (Trans-Lunar Injection) checklist
- LOI (Lunar Orbit Insertion) procedures
- Descent and landing procedures
- Abort mode decision trees

### kOS Scripts
The KSP side needs kOS scripts for:
- Richer telemetry export
- Staging automation
- Navigation and guidance helpers

### Dashboard
A web-based dashboard showing:
- All seat statuses in real-time
- Telemetry graphs
- Mission timeline
- Agent decision logs

## Code Style

- Python 3.11+ with type hints everywhere
- Pydantic for all data models
- `ruff` for linting and formatting
- No `any` types in Python type hints — use proper types or `Unknown`
- Tests for all new functionality

## Commit Messages

Use conventional commits:
- `feat:` new feature
- `fix:` bug fix
- `docs:` documentation
- `refactor:` code restructuring
- `test:` adding or updating tests

## Questions?

Open an issue or start a discussion. We're happy to help you find a good first contribution.
