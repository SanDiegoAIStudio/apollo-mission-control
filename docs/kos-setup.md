# kOS Setup Guide

How to configure KSP and kOS for use with Apollo Mission Control.

## Prerequisites

1. **Kerbal Space Program 1.x** (tested on 1.12.x)
2. **kOS mod** — install via CKAN or manually from [kOS releases](https://github.com/KSP-KOS/KOS/releases)

## Enable Telnet Server

kOS has a built-in telnet server that lets external programs send commands.

### In-Game Configuration

1. Open KSP
2. Go to **Settings → Difficulty → kOS**
3. Enable **Telnet Server**
4. Set port to `5410` (or your preference)
5. Optionally set a password (update `.env` accordingly)

### Via config file

Edit `GameData/kOS/Plugins/kOS.cfg`:
```
EnableTelnet = True
TelnetPort = 5410
```

## Load the Telemetry Script

1. Copy `kos_scripts/telemetry_server.ks` to your KSP save's kOS Scripts folder:
   ```
   KSP/Ships/Script/telemetry_server.ks
   ```
2. In-game, open the kOS terminal on your vessel
3. Run: `RUN telemetry_server.`

The script will print "Telemetry server ready" when loaded.

## Verify Connection

From your terminal:
```bash
telnet 127.0.0.1 5410
```

You should see the kOS welcome banner. Type `PRINT "HELLO".` to verify commands work.

## Vessel Requirements

For the best experience, your vessel should have:
- A kOS processor part (any size)
- Communication antenna (for comms telemetry)
- Solar panels and/or fuel cells
- Standard Apollo-like staging (launch → orbit → transfer → land)

## Troubleshooting

**Connection refused**: Make sure kOS telnet is enabled and KSP is running with a vessel loaded that has a kOS processor.

**No telemetry**: Make sure `telemetry_server.ks` is running on the vessel. Check the kOS terminal for errors.

**Timeout on commands**: kOS processes commands at the game's physics tick rate. If the game is paused or warping, responses may be delayed.
