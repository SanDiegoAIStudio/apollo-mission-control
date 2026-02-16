# Apollo Mission Control

**A multi-agent AI system that simulates NASA's Apollo-era Mission Control, with each flight controller seat powered by a specialized AI agent — all collaborating to fly a KSP Apollo 11 mission end-to-end.**

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://python.org)

---

## What Is This?

During Apollo, Mission Control in Houston had dozens of specialized controller positions — FIDO tracking trajectories, EECOM monitoring life support, GUIDO watching guidance computers, and the Flight Director orchestrating them all. Each controller was an expert in their narrow domain, and together they flew humans to the Moon.

This project recreates that architecture with AI agents. Each controller seat is its own specialized agent with:

- **Scoped telemetry** — it only sees the data relevant to its role
- **Domain tools** — burn planners, power budgets, fault trees
- **Role-specific reasoning** — system prompts and procedures tuned to that position
- **Authority boundaries** — only certain seats can issue certain commands

The agents coordinate through a shared mission state and decision cycle, with the Flight Director agent aggregating recommendations and issuing final commands to KSP via kOS.

## Architecture

```
┌─────────────────────────────────────────────────────────┐
│                    KSP + kOS Mod                        │
│              (Physics / Simulation Core)                │
└──────────────────────┬──────────────────────────────────┘
                       │ kOS Telnet (TCP)
                       │
┌──────────────────────▼──────────────────────────────────┐
│                  kOS Bridge                              │
│         Reads telemetry, sends commands                 │
└──────────────────────┬──────────────────────────────────┘
                       │
┌──────────────────────▼──────────────────────────────────┐
│               Telemetry Bus                             │
│    Normalizes vessel state into structured schema       │
└───┬───────┬───────┬───────┬───────┬───────┬─────────────┘
    │       │       │       │       │       │
    ▼       ▼       ▼       ▼       ▼       ▼
┌──────┐┌──────┐┌──────┐┌──────┐┌──────┐┌──────┐
│FLIGHT││ FIDO ││GUIDO ││EECOM ││CAPCOM││ GNC  │
│  Dir ││      ││      ││      ││      ││      │
└──┬───┘└──┬───┘└──┬───┘└──┬───┘└──┬───┘└──┬───┘
   │       │       │       │       │       │
   └───────┴───────┴───────┴───┬───┴───────┘
                               │
                    ┌──────────▼──────────┐
                    │  Decision Cycle     │
                    │  (Flight Director   │
                    │   aggregates &      │
                    │   resolves)         │
                    └──────────┬──────────┘
                               │
                    ┌──────────▼──────────┐
                    │  Command Dispatch   │
                    │  → kOS Bridge       │
                    └─────────────────────┘
```

## Flight Controller Seats

| Seat | Full Name | Responsibility |
|------|-----------|---------------|
| **FLIGHT** | Flight Director | Overall mission authority. Aggregates Go/No-Go, resolves conflicts, issues final commands. |
| **FIDO** | Flight Dynamics Officer | Trajectory design, maneuver planning, orbit determination, abort options. |
| **GUIDO** | Guidance Officer | Guidance computer monitoring, navigation updates, attitude control. |
| **EECOM** | Electrical, Environmental & Consumables Manager | Power budgets, fuel cells, O2/H2 levels, thermal control, fault detection. |
| **GNC** | Guidance, Navigation & Control | RCS/SPS engine health, thrust vector control, IMU alignment. |
| **CAPCOM** | Capsule Communicator | Voice of Mission Control to crew. Translates technical decisions into crew instructions. |
| **RETRO** | Retrofire Officer | Return-to-Earth trajectories, abort burn calculations, reentry corridor. |
| **TELMU** | Telemetry, Electrical & EVA Mobility Unit | LM electrical systems, telemetry data quality, EVA suit monitoring. |
| **CONTROL** | LM Flight Control | Lunar Module guidance, descent/ascent engine, landing radar. |

> More seats will be added as the project matures. See [docs/agent-roles.md](docs/agent-roles.md) for full details.

## Roadmap

### Phase 1: Single-Agent Proof of Concept
- [ ] kOS telnet bridge (read telemetry, send commands)
- [ ] Telemetry schema and normalization
- [ ] Single monolithic agent controlling a Kerbin orbit mission
- [ ] Basic command dispatch loop

### Phase 2: Core Seat Split (3-4 agents)
- [ ] Flight Director, FIDO, EECOM, CAPCOM agents
- [ ] Shared mission state with authority scoping
- [ ] Decision cycle with Go/No-Go polling
- [ ] LKO insertion → Mun transfer → Mun orbit mission

### Phase 3: Full Mission Control
- [ ] All 9+ controller seats active
- [ ] Role-specific tools (burn planner, power budget calculator, fault trees)
- [ ] Full Apollo 11-style mission: launch → TLI → LOI → descent → landing → ascent → TEI → reentry
- [ ] Mission log and transcript generation

### Phase 4: Community & Polish
- [ ] Web dashboard showing all seats and telemetry
- [ ] Pluggable LLM backends (Claude, GPT, local models)
- [ ] Custom mission profiles
- [ ] Multiplayer: humans can take over any seat

## Prerequisites

- **KSP 1.x** with the [kOS mod](https://ksp-kos.github.io/KOS/) installed
- kOS Telnet server enabled (see [docs/kos-setup.md](docs/kos-setup.md))
- **Python 3.11+**
- An LLM API key (Claude, OpenAI, or local model endpoint)

## Quick Start

```bash
# Clone
git clone https://github.com/lcb-projects/apollo-mission-control.git
cd apollo-mission-control

# Install
uv venv && source .venv/bin/activate
uv pip install -e ".[dev]"

# Configure
cp .env.example .env
# Edit .env with your API key and kOS telnet settings

# Run (Phase 1 - single agent)
python -m apollo_mc
```

## Project Structure

```
apollo-mission-control/
├── src/apollo_mc/
│   ├── core/              # Telemetry bus, mission state, command dispatch
│   ├── bridge/            # kOS telnet client
│   ├── agents/            # Agent implementations per seat
│   ├── tools/             # Domain tools (burn planner, power budget, etc.)
│   ├── schemas/           # Pydantic models for telemetry and commands
│   └── orchestrator/      # Decision cycle, Go/No-Go polling
├── prompts/               # Role-specific system prompts per seat
├── kos_scripts/           # kOS scripts for the KSP side
├── procedures/            # Mission procedures and checklists
├── docs/                  # Architecture docs, setup guides
└── tests/                 # Test suite
```

## How It Works

### Decision Cycle

Every tick (configurable, default 2s):

1. **Telemetry tick** — Bridge reads KSP state, publishes to bus
2. **Seat update** — Each agent receives its scoped telemetry slice
3. **Seat output** — Agents emit status, constraints, recommendations
4. **Aggregation** — Flight Director collects all seat outputs
5. **Decision** — Flight resolves conflicts, chooses action
6. **Dispatch** — Approved commands sent to kOS

### Authority Model

Not all agents can do everything:

| Authority Level | Who | Can Do |
|----------------|-----|--------|
| **Command** | FLIGHT | Issue any command, override any seat |
| **Execute** | FIDO, GUIDO, GNC | Issue burns, attitude changes, nav updates |
| **Recommend** | EECOM, RETRO, TELMU | Flag constraints, recommend actions |
| **Communicate** | CAPCOM | Translate decisions to crew-readable format |

### Agent Architecture

Each seat agent combines:

- **LLM reasoning** for situational assessment and natural-language coordination
- **Algorithmic tools** for precise calculations (orbital mechanics, power budgets)
- **Procedural playbooks** for known scenarios (abort modes, fault responses)

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines. We welcome:

- New controller seat implementations
- Mission procedure playbooks
- kOS script improvements
- Dashboard and visualization work
- Documentation and tutorials

## Research References

This project builds on research in LLM-based spacecraft control:

- [Large Language Models as Autonomous Spacecraft Operators](https://arxiv.org/abs/2408.08676) — LLMs controlling KSP spacecraft
- [KSP-based LLM agent evaluation](https://arxiv.org/abs/2405.01392) — Benchmarking LLM agents in orbital mechanics
- NASA Apollo Mission Control documentation and transcripts

## License

MIT — see [LICENSE](LICENSE).

---

*"Houston, the agents have the conn."*
