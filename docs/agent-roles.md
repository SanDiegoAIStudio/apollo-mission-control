# Agent Roles

Detailed breakdown of each flight controller seat, their responsibilities, telemetry inputs, and output capabilities.

## Implemented

### FLIGHT — Flight Director
- **Authority**: COMMAND (highest)
- **Watches**: All telemetry (aggregated view)
- **Outputs**: Go/No-Go decisions, abort calls, phase advancement, command approval
- **Real Apollo role**: Gene Kranz, Cliff Charlesworth, Glynn Lunney

### FIDO — Flight Dynamics Officer
- **Authority**: EXECUTE
- **Watches**: Orbital state, velocity, position, fuel reserves
- **Outputs**: Burn plans, trajectory corrections, abort trajectories, orbit reports
- **Tools**: Hohmann transfer calculator, circularization planner, burn time estimator

### EECOM — Electrical, Environmental & Consumables Manager
- **Authority**: RECOMMEND
- **Watches**: Power levels, resource levels, charge rates
- **Outputs**: Resource warnings, power conservation recommendations, fault alerts

### CAPCOM — Capsule Communicator
- **Authority**: COMMUNICATE
- **Watches**: Communications link, all seat outputs
- **Outputs**: Crew-readable status messages, mission log entries

## Planned

### GUIDO — Guidance Officer
- **Authority**: EXECUTE
- **Watches**: Guidance computer state, navigation accuracy, attitude control
- **Outputs**: IMU alignment commands, navigation updates, attitude corrections

### GNC — Guidance, Navigation & Control
- **Authority**: EXECUTE
- **Watches**: Engine health, RCS status, thrust vector data, IMU readings
- **Outputs**: Engine commands, RCS adjustments, SPS health reports

### RETRO — Retrofire Officer
- **Authority**: RECOMMEND
- **Watches**: Return trajectory options, abort windows, reentry corridor
- **Outputs**: Abort burn parameters, return trajectory recommendations

### TELMU — Telemetry, Electrical & EVA Mobility Unit
- **Authority**: RECOMMEND
- **Watches**: LM electrical systems, telemetry quality, EVA suit data
- **Outputs**: LM power management, telemetry quality reports

### CONTROL — LM Flight Control
- **Authority**: EXECUTE
- **Watches**: LM guidance, descent/ascent engines, landing radar
- **Outputs**: Landing commands, LM attitude control, descent rate management

### INCO — Instrumentation & Communications Officer
- **Authority**: RECOMMEND
- **Watches**: Antenna pointing, signal strength, data rates
- **Outputs**: Antenna switching recommendations, comm window predictions

### SURGEON — Flight Surgeon
- **Authority**: RECOMMEND
- **Watches**: Crew vitals (simulated), mission duration, workload
- **Outputs**: Crew rest recommendations, EVA readiness assessment
