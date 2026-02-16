# Architecture

## Overview

Apollo Mission Control is a multi-agent system where each flight controller seat runs as an independent agent. Agents communicate through a shared mission state and a structured decision cycle orchestrated by the Flight Director.

## Components

### kOS Bridge (`bridge/kos_client.py`)
TCP client that connects to KSP's kOS telnet server. Reads raw vessel telemetry and translates it into our `TelemetryFrame` schema. Also sends approved commands back to kOS.

### Telemetry Bus (`core/telemetry_bus.py`)
Pub/sub system. The bridge publishes telemetry frames; seat agents subscribe. Each agent receives the same frame but focuses on its scoped fields.

### Seat Agents (`agents/`)
Each agent extends `SeatAgent` and implements `evaluate(frame) -> SeatRecommendation`. Agents run in parallel every tick.

### Mission State (`core/mission_state.py`)
Single source of truth. Holds current telemetry, all seat recommendations, decision history, and phase tracking. Agents read from it; only the orchestrator writes to it.

### Decision Cycle (`orchestrator/decision_cycle.py`)
The heartbeat loop:
1. Telemetry tick from bridge
2. All seats evaluate in parallel
3. Flight Director aggregates
4. Approved commands dispatched

### Command Dispatcher (`core/command_dispatch.py`)
Translates `CommandRequest` objects into kOS telnet command strings.

### Domain Tools (`tools/`)
Pure functions for calculations (orbital mechanics, power budgets). Agents call these as needed — the LLM decides when, the tool does the math.

## Data Flow

```
KSP/kOS → Bridge → TelemetryFrame → Bus → Agents (parallel)
                                              ↓
                                    SeatRecommendation[]
                                              ↓
                                      Flight Director
                                              ↓
                                   FlightDirectorDecision
                                              ↓
                                    CommandDispatcher → kOS
```

## Authority Model

Agents have tiered authority levels that constrain what commands they can issue:

- **COMMAND** (Flight only): Can issue any command
- **EXECUTE** (FIDO, GUIDO, GNC): Can issue burns and attitude changes
- **RECOMMEND** (EECOM, RETRO, TELMU): Can only recommend actions
- **COMMUNICATE** (CAPCOM): Translates decisions for crew

The Flight Director validates authority before approving commands.

## Extension Points

- **New seats**: Extend `SeatAgent`, add to the orchestrator's seat list
- **New tools**: Add to `tools/`, wire into relevant agent
- **LLM integration**: Replace `evaluate()` logic with LLM calls using the role prompt from `prompts/`
- **Dashboard**: Subscribe to the telemetry bus and mission state for real-time visualization
