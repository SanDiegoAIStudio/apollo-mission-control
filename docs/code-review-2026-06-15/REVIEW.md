# Apollo Mission Control — Code Review (2026-06-16)

> **Findings surfaced by review; critical/high are adversarially verified in the Verification section below.**
> Repo: `apollo-mission-control` (tier 2). Surfaced by a 9-dimension review pass; not yet adversarially verified at time of writing.

## Summary

| Severity | Count |
|----------|------:|
| Critical | 6 |
| High | 28 |
| Medium | 25 |
| Low | 12 |
| **Total** | **71** |

A handful of findings overlap (the FIDO/EECOM `GoNoGo` string-literal bug, the `command_dispatch` template injection, the telemetry-bridge JSON/KeyError handling, and unbounded log growth each appear under multiple dimensions). They are kept as listed but cross-noted where duplicated.

---

## Critical

**Unsafe String Formatting in Command Dispatch (Format String Injection)**
`src/apollo_mc/core/command_dispatch.py:43`
`CommandDispatcher.translate()` uses `str.format()` to interpolate user-controlled parameters directly into kOS command templates without sanitization. `template.format(**command.parameters)` at line 43 allows arbitrary kOS code injection. `CommandRequest.parameters` is a `dict[str, float | str | bool]` that accepts unvalidated strings. An attacker who can control parameter values (e.g. via LLM-generated commands in Phase 2/3, or if command generation is ever externalized) can inject arbitrary kOS code via malicious string values containing closing braces, newlines, and additional kOS statements.
*Fix:* Replace `str.format()` with a safe substitution mechanism that validates/restricts parameter values: (1) explicit mapping with strict type coercion + validation before interpolation, (2) a command builder that validates each parameter against a per-command whitelist, (3) parameterized builders that never let user strings reach template interpolation, or (4) schema-level allowed values via Pydantic validators that reject strings containing `{`, `}`, `.`, newlines, etc.

**Unhandled JSON parse exceptions in telemetry bridge**
`src/apollo_mc/bridge/kos_client.py:83-85`
`read_telemetry()` calls `json.loads(raw)` with no exception handling. Malformed, truncated, or invalid JSON raises `JSONDecodeError` uncaught and crashes the mission loop. The 10s stream-read timeout may also raise `asyncio.TimeoutError`, also uncaught.
*Fix:* Wrap `json.loads()` and `send_command()` in try/except for `json.JSONDecodeError` and `asyncio.TimeoutError`. Log and either retry or propagate a custom exception with context.

**Unhandled KeyError exceptions in telemetry parsing**
`src/apollo_mc/bridge/kos_client.py:87-133`
`_parse_telemetry()` uses direct dict access (`data['vessel']`, `data['orbital']`, `data['power']['electric_charge']`) with no try/except. Missing/malformed fields raise `KeyError` uncaught, silently terminating the mission loop with no graceful degradation.
*Fix:* Wrap `_parse_telemetry()` in try/except, use `data.get()` for optional fields, or run the raw dict through the (already-imported) Pydantic validation layer before field extraction.

**No test coverage for CommandDispatcher — critical command translation path**
`src/apollo_mc/core/command_dispatch.py`
`translate()` and `dispatch()` are untested. `translate()` does template substitution with user-supplied parameters (line 43) and can silently fail on missing keys. No tests verify parameter validation, template correctness, or error recovery.
*Fix:* Add unit tests for: (1) valid translation for each `KOS_TEMPLATES` entry, (2) `KeyError` handling when parameters are missing, (3) `None` return on unknown command type, (4) dispatch logging + bridge integration.

**No test coverage for DecisionCycle — core orchestration logic**
`src/apollo_mc/orchestrator/decision_cycle.py`
`DecisionCycle.tick()` contains the entire decision loop (telemetry update, parallel seat evaluation, recommendation aggregation, command dispatch) with zero test coverage. Line 54 logs exceptions but error recovery is untested.
*Fix:* Add integration tests: (1) happy path with all seats returning valid recommendations, (2) exception handling when a seat raises, (3) Flight Director aggregation with mixed GO/NO_GO, (4) command-dispatch invocation verification.

**No test coverage for TelemetryBus pub/sub system**
`src/apollo_mc/core/telemetry_bus.py`
`TelemetryBus.publish()` (line 33) uses `asyncio.gather(return_exceptions=True)` but tests never verify callback invocation, exception isolation, or correct frame distribution.
*Fix:* Add tests for: (1) subscribe/unsubscribe lifecycle, (2) publish triggers all subscribers, (3) one callback's exception doesn't block others, (4) `latest` returns the correct frame.

---

## High

**Type Error: String literal passed to Enum-typed field in EecomAgent**
`src/apollo_mc/agents/eecom.py:71,80`
`EecomAgent.evaluate()` passes string literals (`"NO_GO"`, `"GO"`) directly to the `go_nogo` parameter of `SeatRecommendation`, which expects a `GoNoGo` enum — a Pydantic validation error at runtime. The base class uses `GoNoGo.GO`/`GoNoGo.NO_GO`; EECOM uses strings.
*Fix:* Replace `go_nogo="NO_GO"` → `go_nogo=GoNoGo.NO_GO` and `go_nogo="GO"` → `go_nogo=GoNoGo.GO` on lines 71 and 80.

**Type Error: String literal passed to Enum-typed field in FidoAgent**
`src/apollo_mc/agents/fido.py:66,75`
Same as EECOM: `FidoAgent.evaluate()` passes `"NO_GO"`/`"GO"` strings to the `go_nogo` field which expects `GoNoGo`.
*Fix:* Replace with `go_nogo=GoNoGo.NO_GO` and `go_nogo=GoNoGo.GO` on lines 66 and 75.

> **Note:** The FIDO/EECOM `GoNoGo` string-literal issue is reported under several review dimensions (type-safety, schema-consistency, agent-implementation). The remaining duplicate entries below describe the same root cause from different angles — fix once in both files (`fido.py:66,75` and `eecom.py:71,80`), ideally via the inherited `go()`/`no_go()` helpers.

**Unreachable Code: Impossible circularization action condition in FidoAgent**
`src/apollo_mc/agents/fido.py:47-50`
The circularization-action condition (`time_to_apoapsis < 60 AND eccentricity > 0.05 AND periapsis < 70km`) is unreachable: if `periapsis < 70km` the function already returns a NO_GO constraint at lines 63-71, so the action at lines 52-61 never executes.
*Fix:* Clarify intent. If circularization should fire when periapsis is low, move the action logic before the constraint check. If `periapsis < 70km` must always block, remove the periapsis check (line 50) since safe-periapsis orbits don't need this emergency action.

**Unvalidated Command Parameters in CommandRequest Schema**
`src/apollo_mc/schemas/commands.py:43`
`CommandRequest.parameters` is `dict[str, float | str | bool]` with no validation constraints. Agents currently hardcode safe values, but the schema permits arbitrary strings with malicious kOS syntax (newlines, braces, semicolons) — the foundational enabler of the `command_dispatch.py` format-string injection. If command generation is ever delegated to LLM APIs, user input, or config files, malicious parameters flow through undetected.
*Fix:* Add Pydantic validators enforcing strict constraints: (1) command-specific subclasses (`BurnCommand`, `AttitudeCommand`) with exact param names/types/ranges, (2) a root validator that rejects strings with `{}`, newlines, semicolons based on `command_type`, or (3) constrained `constr` regex types allowing only safe chars (alphanumerics, dots, underscores, hyphens).

**String literals used instead of GoNoGo enum values (FIDO)**
`src/apollo_mc/agents/fido.py:66,75`
`SeatRecommendation.go_nogo` expects `GoNoGo` but receives `"NO_GO"`/`"GO"`. Defeats type safety; fails under Pydantic strict mode or mypy strict mode. *(Duplicate of the FIDO type-error finding above.)*
*Fix:* Use `GoNoGo.NO_GO` / `GoNoGo.GO`; import `GoNoGo` from `apollo_mc.schemas.commands` if needed.

**String literals used instead of GoNoGo enum values (EECOM)**
`src/apollo_mc/agents/eecom.py:71,80`
Same as FIDO — string literals undermine type safety. *(Duplicate of the EECOM type-error finding above.)*
*Fix:* Use `GoNoGo.NO_GO` / `GoNoGo.GO`; `GoNoGo` already imported.

**Untyped dict parameter with `type: ignore` suppression**
`src/apollo_mc/bridge/kos_client.py:87`
`_parse_telemetry` accepts an untyped `dict` (implicitly `dict[str, Any]`), suppressed with `type: ignore[type-arg]`, then does unsafe string-keyed access (`data["vessel"]`, `data["orbital"]`) with no runtime validation — a gap between external JSON and type-checked code.
*Fix:* Use a `TypedDict` or Pydantic `BaseModel` to validate incoming JSON (e.g. `TelemetryData: TypedDict`) before parsing.

**Command log array unbounded growth in CommandDispatcher**
`src/apollo_mc/core/command_dispatch.py:29,68`
`_command_log` appends a tuple for every dispatched command with no size limit. Over a multi-hour mission with frequent commands (attitude corrections), this is a memory leak. Each entry stores `mission_time`, `seat_name`, and the kOS command string.
*Fix:* Use `collections.deque(maxlen=10000)` or similar bounded structure, or rotate older logs to disk.

**Decision cycle: resource iterated multiple times per frame**
`src/apollo_mc/agents/eecom.py:43-49`
`EecomAgent` linearly scans `frame.resources` for `'LiquidFuel'` and `'Oxidizer'` every evaluation tick — O(n) repeated work for vessels with many resources.
*Fix:* Index resources by name at the bridge layer when parsing telemetry (`resources_by_name: dict[str, ResourceLevel]`) so agent lookups are O(1); or cache the index in `TelemetryFrame`.

**Unhandled exceptions swallowed in telemetry bus subscribers**
`src/apollo_mc/core/telemetry_bus.py:37-42`
`publish()` uses `asyncio.gather(*tasks, return_exceptions=True)` but never inspects or logs the exceptions. Subscriber callbacks that raise fail silently — agents may not evaluate without mission control noticing, producing incomplete recommendations and wrong GO/NO-GO decisions.
*Fix:* After `gather()`, iterate results and log any exceptions. Consider raising an aggregated exception if critical subscribers fail, or at minimum log warnings.

**Flight Director evaluation not wrapped in exception handling**
`src/apollo_mc/orchestrator/decision_cycle.py:59-61`
The Flight Director `evaluate()` call (line 60) is NOT wrapped in try/except, unlike seat evaluations (line 49 uses `gather(return_exceptions=True)`). A Flight Director exception fails the entire decision cycle.
*Fix:* Wrap the Flight Director call in try/except, or add it to the `asyncio.gather()` call with `return_exceptions=True` and handle exceptions like the seats.

**Command dispatch exceptions silently ignored**
`src/apollo_mc/orchestrator/decision_cycle.py:70-72`
The dispatch loop (`for command in decision.approved_commands: await self._dispatcher.dispatch(...)`) has no try/except. A dropped kOS connection or `send_command()` timeout propagates unhandled, breaking the mission loop. `dispatch()` only logs translate failures, not network errors.
*Fix:* Wrap dispatch in try/except. Consider retry with exponential backoff for transient failures, or queue failed commands for retry.

**Type mismatch in FIDO and EECOM agents — string vs GoNoGo enum**
`src/apollo_mc/agents/fido.py:66,75` (also `eecom.py:71,80`)
FIDO returns `SeatRecommendation` with `go_nogo='NO_GO'`/`'GO'` strings; EECOM does the same. Base agent and FlightDirector use the enum. Inconsistency may cause type errors, JSON-serialization failures, or wrong comparisons under strict validation. *(Same root cause as the type-error findings above.)*
*Fix:* Change all string literals to `GoNoGo.GO`/`GoNoGo.NO_GO` in both files; use the base `go()`/`no_go()` helpers for consistency.

**Incomplete command dispatch error handling**
`src/apollo_mc/core/command_dispatch.py:54-73`
`dispatch()` doesn't catch exceptions from `bridge.send_command()`. Network failure / timeout / kOS error propagates uncaught. The `bool` return value isn't checked by callers (`decision_cycle.py:72`), so failed dispatches are silently dropped.
*Fix:* Wrap `send_command()` in try/except, return `False` on network errors, and have callers check the return or log failures. Alternatively raise a custom `CommandDispatchError` handled in `decision_cycle`.

**Missing timeout/retry for critical loop — no recovery mechanism**
`src/apollo_mc/orchestrator/mission_loop.py:102-122`
The main mission loop has only two exception handlers: `ConnectionError` and `KeyboardInterrupt`. Any other exception (`TimeoutError`, `ValueError`, etc.) crashes the loop. Transient network blips abort the mission instead of retrying. No backoff or circuit breaker.
*Fix:* Add a catch-all handler logging unhandled exceptions. Add exponential backoff + jitter for transient errors before aborting. Separate transient (timeout, `ConnectionError`) from fatal (malformed data) exceptions.

**MissionState property logic untested**
`src/apollo_mc/core/mission_state.py`
`overall_go` (lines 24-29) and `no_go_seats` (lines 32-37) contain filtering logic but are never exercised. No tests cover empty recommendations or mixed statuses.
*Fix:* Add tests: (1) `overall_go` is `False` when empty, (2) `overall_go` is `True` only when all seats GO, (3) `no_go_seats` correctly filters NO_GO entries.

**FIDO conditional action generation logic untested**
`src/apollo_mc/agents/fido.py`
Lines 47-61 have a complex AND condition (`time_to_apoapsis < 60 AND high eccentricity AND low periapsis`) generating a `lock_steering` command, but tests never verify generation or condition boundaries.
*Fix:* Add tests: (1) action generated when all three conditions met, (2) no action when only two met, (3) boundary at exactly 60s time-to-apoapsis. *(See also the "unreachable code" finding — the test may reveal it never fires.)*

**EECOM solar panel deployment logic untested**
`src/apollo_mc/agents/eecom.py`
Lines 52-66 conditionally recommend solar-panel deployment (`charge_rate < 0 AND charge < 50% AND panels not deployed`) but no test verifies the recommendation.
*Fix:* Add case: `charge_rate=-1.0, electric_pct=40, solar_panels_deployed=False` → expect a `deploy_solar` action.

**CommandDispatcher parameter validation missing**
`src/apollo_mc/core/command_dispatch.py`
`template.format(**command.parameters)` (line 43) can raise `KeyError`/`ValueError`, but no tests verify recovery. Unknown command types return `None` silently (line 34) with no assertion that `None` is handled downstream.
*Fix:* Test: (1) missing required parameter (e.g. `lock_steering` without `direction`), (2) extra parameters not in template, (3) type mismatch (string vs float), (4) verify `None` handling doesn't crash dispatch.

**No error-path tests for agent telemetry handling**
`tests/test_agents.py`
All agent tests use `make_frame()` with valid data. Tests never exercise negative resource amounts, `orbital.eccentricity > 1.0`, NaN `time_to_apoapsis`, or missing nested objects.
*Fix:* Add invalid-telemetry tests: (1) negative fuel %, (2) eccentricity > 1.0, (3) zero `max_amount` (percentage division), (4) `None` orbital state.

**Orbital mechanics edge case untested — infinite time_to_phase_angle**
`src/apollo_mc/tools/orbital_mechanics.py`
`time_to_phase_angle()` returns `float('inf')` when `omega_rel <= 0` (lines 141-142), but no test verifies this boundary.
*Fix:* Add test: faster target orbit (lower altitude) gives negative `omega_rel` → verify `inf` returned; add a test for `omega_rel == 0` exactly.

**CAPCOM status formatting untested**
`src/apollo_mc/agents/capcom.py`
`format_status_for_crew()` (lines 24-43) builds multi-line mission-status text but is never called or verified in tests.
*Fix:* Add test: call with mixed GO/NO_GO seats and warnings; verify output contains all seats, correct GO/NO_GO markers, and all warnings.

**Duplicate constraint-check pattern in agent evaluation methods**
`src/apollo_mc/agents/eecom.py:28-85` (and `fido.py:26-83`)
Both agents repeat the same structure: init warnings/constraints/actions lists, run domain checks, early-return NO_GO if constraints exist, else GO. DRY violation; should live in the base class.
*Fix:* Extract a protected helper into `SeatAgent` (e.g. `_make_recommendation(warnings, constraints, actions, summary_go, summary_no_go)`) that handles the conditional return; agents just populate the three lists and call it.

**Race condition in TelemetryBus._subscribers during concurrent publish and unsubscribe**
`src/apollo_mc/core/telemetry_bus.py:37-42`
`publish()` iterates `self._subscribers.values()` (line 39) while `unsubscribe()` can mutate the dict (line 27) concurrently. Dict iteration is not atomic — an unsubscribe mid-publish raises "dictionary changed size during iteration" or unpredictably skips callbacks.
*Fix:* Snapshot before iterating: `tasks = [callback(frame) for callback in list(self._subscribers.values())]`, or guard subscribe/unsubscribe/publish with a lock.

**Concurrent mutation of mission state during decision cycle without synchronization**
`src/apollo_mc/orchestrator/decision_cycle.py:45,64,68`
Line 64 writes `self._state.seat_recommendations = recommendations` while line 45 modifies telemetry. If the mission loop reads `seat_recommendations` mid-replace (e.g. `build_status_table` at `mission_loop.py:33`), a partial/stale read occurs. `MissionState` is mutable with no write locks.
*Fix:* (1) make `MissionState` immutable by rebuilding instead of mutating, (2) wrap mutations in `asyncio.Lock`, or (3) use copy-on-write where the cycle creates a new state dict.

**Unguarded direct mutation of shared mutable collections in decision cycle**
`src/apollo_mc/core/mission_state.py:17,19,46,64`
`seat_recommendations` (line 17) and `command_history` (line 19) are mutable field defaults mutated directly. Line 64 in `decision_cycle.py` fully replaces, but other code may hold references to the old dict; an agent evaluating against an earlier snapshot (lines 28, 35) sees stale constraint data.
*Fix:* Produce a new `MissionState` per cycle rather than mutating the shared one. Use `dataclass(frozen=True)` or return new instances.

**FlightDirectorAgent decision logic bypasses authority boundaries**
`src/apollo_mc/agents/flight.py:39-88`
`make_decision()` collects all `CommandRequest` objects (lines 50-51) and approves/rejects based only on Go/No-Go status, bypassing the `authority_required` field. Seats with RECOMMEND authority (EECOM) can get actions auto-approved when overall status is GO, violating the scoped-authority design in `CLAUDE.md`.
*Fix:* Add authority validation in `make_decision()`: check each command's `authority_required` against the source seat's authority level (`seat.authority`) before approval; reject commands exceeding it. Preserves role-based gating.

**Inconsistent Go/No-Go enum usage in agent implementations**
`src/apollo_mc/agents/fido.py:64-71,73-83`
Agents use `'GO'`/`'NO_GO'` string literals (lines 66, 75) instead of `GoNoGo.GO`/`GoNoGo.NO_GO`. The base class provides `go()`/`no_go()` helpers, but not all paths use them, creating type inconsistency and fragile enum-value refactors. *(Same root cause as the FIDO/EECOM findings above.)*
*Fix:* Replace all string literals with `GoNoGo` values across `fido.py`/`eecom.py`; use the inherited `go()`/`no_go()` helpers consistently.

---

## Medium

**Missing exception handling for JSON parsing in KosBridge**
`src/apollo_mc/bridge/kos_client.py:84`
`read_telemetry()` calls `json.loads(raw)` with no try-except; malformed/truncated JSON raises `JSONDecodeError` uncaught. `_parse_telemetry()` also accesses `data["vessel"]`/`data["orbital"]` (lines 89-90) with no existence check → `KeyError`. *(Overlaps the two critical telemetry-bridge findings.)*
*Fix:* Wrap `json.loads()` in try-except; use `data.get()` with defaults or validate JSON structure before nested access.

**Unhandled exception from Flight Director evaluation in decision cycle**
`src/apollo_mc/orchestrator/decision_cycle.py:60`
Seat agents use `gather(return_exceptions=True)` (line 49), but the Flight Director `evaluate()` (line 60) is unguarded — an exception propagates uncaught to the mission loop. *(Overlaps the high-severity Flight Director finding.)*
*Fix:* Wrap the line-60 call in try-except; log and provide a conservative NO_GO fallback on failure.

**Unhandled JSON Parsing Exceptions in Telemetry Bridge**
`src/apollo_mc/bridge/kos_client.py:84`
`read_telemetry()` calls `json.loads(raw)` without handling; corruption / kOS mod bug / attacker on the telnet stream crashes the mission loop with no degradation. *(Overlaps the critical JSON-parse finding.)*
*Fix:* try-except around `json.loads()`, log the raw response, return a last-known-good frame or raise a custom exception. Add post-parse schema validation before building `TelemetryFrame`.

**Missing Input Validation on Telemetry Dictionary Keys**
`src/apollo_mc/bridge/kos_client.py:87-90`
`_parse_telemetry()` directly accesses `data['vessel']`/`data['orbital']`/`data['met']` with no existence check, relying on `KeyError`. Pydantic validates the final frame but a gap remains for missing required keys. *(Overlaps the critical KeyError finding.)*
*Fix:* Use Pydantic `model_validate()` on the raw dict, or add explicit key checks raising a descriptive error. Log malformed JSON.

**Forward reference with type ignore for circular import avoidance**
`src/apollo_mc/core/command_dispatch.py:27`
The `bridge` parameter uses a forward-reference string `"KosBridge | None"` with `# noqa: F821` instead of importing `KosBridge`. Avoids circular imports but bypasses static type checking; `TYPE_CHECKING` guard not used.
*Fix:* Use `if TYPE_CHECKING: from apollo_mc.bridge.kos_client import KosBridge` for full type safety without circular imports.

**Unsafe dictionary unpacking with unknown key structure**
`src/apollo_mc/bridge/kos_client.py:120,123,126`
`EngineState(**eng)`, `ResourceLevel(**res)`, and `PowerState` construction unpack without validating required fields exist. Malformed/missing keys raise `KeyError` at runtime.
*Fix:* Validate each dict before unpacking or use `EngineState.model_validate(eng)` / wrap in try-except with informative errors.

**Unsafe string formatting with untrusted dict keys**
`src/apollo_mc/core/command_dispatch.py:43`
`CommandRequest.parameters` is `dict[str, float | str | bool]` used with `template.format(**parameters)`. Missing template keys raise `KeyError` (caught but silently returns `None`); type mismatch possible if `bool` hits a numeric placeholder. *(Overlaps the critical injection finding.)*
*Fix:* Use `template.format_map()` with defaults, or type-check parameters before formatting; log what's missing/mismatched.

**Unbounded command history list growing indefinitely**
`src/apollo_mc/core/mission_state.py:19,46`
`command_history` appends every `FlightDirectorDecision` with no retention limit. Long missions (hours) consume unbounded memory; each decision carries full command payloads and seat statuses. *(Overlaps the `_command_log` growth finding.)*
*Fix:* Use a fixed-size `collections.deque` (e.g. `maxlen=1000`) or rotate to a log file; add a `max_history_size` parameter.

**Sorted seat recommendations called on every display update**
`src/apollo_mc/orchestrator/mission_loop.py:33`
`build_status_table()` calls `sorted(state.seat_recommendations.items())` on every display refresh (up to 1/sec). Negligible at 3-4 seats but recomputes display data each frame; display refresh rate (1/sec) also mismatches telemetry tick rate (2s default).
*Fix:* Cache sorted recommendations in `MissionState`, re-sort only on change; or move table construction to a lower-frequency path.

**Telemetry frame is deep-copied implicitly on publish**
`src/apollo_mc/core/telemetry_bus.py:33-42`
`TelemetryFrame` is a nested Pydantic model. Published via `asyncio.gather(*tasks)`, every callback gets the same frame reference; Pydantic models aren't designed for zero-copy pass-by-reference in concurrent contexts. If agents store frames, hidden copies appear.
*Fix:* Verify agents don't store frame references between ticks; if they do, use a reference counter or document frames as ephemeral. Consider `@property` access to the latest frame instead of stored copies.

**Telemetry decode errors not handled**
`src/apollo_mc/bridge/kos_client.py:74-75`
`send_command()` calls `response.decode().strip()` with no handling; non-UTF-8 data raises `UnicodeDecodeError` uncaught. `readline()` may also read partial/corrupted frames.
*Fix:* Wrap `decode()` in try/except, log decode errors, retry or raise with context. Consider `response.decode('utf-8', errors='replace')`.

**Partial-write risk in command dispatch log**
`src/apollo_mc/core/command_dispatch.py:68`
Command history appends to the in-memory `_command_log`. If the mission crashes before persistence, history is lost; no atomicity/durability if the process dies between append and the next checkpoint.
*Fix:* Write the command log to disk immediately (atomic ops) or checkpoint periodically. If in-memory is acceptable, document that history is volatile.

**Seat recommendation collection with missing Flight Director**
`src/apollo_mc/orchestrator/decision_cycle.py:59-64`
If Flight Director `evaluate()` raises uncaught, line 61 never runs and the recommendations dict lacks the FLIGHT entry. `make_decision()` then runs with incomplete recommendations; `overall_go`/`no_go_seats` won't reflect Flight Director status. *(Overlaps the Flight Director exception findings.)*
*Fix:* Wrap Flight Director `evaluate()` in a handler and insert a default NO_GO recommendation on failure.

**FIDO warning generation — no test verification**
`src/apollo_mc/agents/fido.py`
Lines 40-44 generate high-eccentricity warnings but tests never verify they're emitted. The line-90 test checks NO_GO on low periapsis but not the warnings field.
*Fix:* Add test: high eccentricity but safe periapsis → GO with the eccentricity warning in `warnings`.

**Weak float tolerance in orbital mechanics tests**
`tests/test_orbital_mechanics.py`
Tests use loose approximations (`abs(v - expected) < 0.01` line 20, `t < 60` line 61, `dv < 500` line 49) instead of exact conditions/properties; tolerance unjustified.
*Fix:* Tighten tolerances with justification or use exact assertions — vis-viva tests can use machine-epsilon tolerance; `burn_time` should verify the math directly, not just an upper bound.

**No tests for EECOM warnings on low resources**
`src/apollo_mc/agents/eecom.py`
Lines 39-40 (electric-charge warning) and 48-49 (fuel warning) fire on low-but-not-critical levels, but tests only verify NO_GO at critical.
*Fix:* Add test: `electric_pct=20` (between WARNING and CRITICAL) → GO with the warning in `warnings`.

**KosBridge connection and timeout handling untested**
`src/apollo_mc/bridge/kos_client.py`
`connect()` (line 42) uses `asyncio.wait_for` with a 5.0s timeout (line 52); no test verifies timeout handling or banner parsing. `send_command()` uses a 10.0s timeout but incomplete reads aren't tested.
*Fix:* Mock-based tests: (1) connection refused → `ConnectionRefusedError`, (2) banner read timeout, (3) command-response timeout, (4) malformed JSON response.

**DecisionCycle exception handling not verified**
`src/apollo_mc/orchestrator/decision_cycle.py`
Line 54 logs seat-evaluation exceptions and continues, but tests never verify the exception is caught, the mission continues after a seat fails, or a decision is still made with a subset of recommendations.
*Fix:* Add test: mock one `seat.evaluate()` to raise; verify the cycle continues, recommendations exclude the failed seat, and a decision is still made.

**FlightDirector.make_decision aggregation logic not fully tested**
`src/apollo_mc/agents/flight.py`
`make_decision()` (lines 39-88) aggregates recommendations but tests only check that abort sets NO_GO. Missing: `no_go_seats` correctness, approved-vs-rejected separation, decision logging.
*Fix:* Add test: mixed GO/NO_GO → verify `overall_status` is NO_GO, `no_go_seats` correct, all commands approved or rejected.

**Missing isolation of agent telemetry_scope declarations**
`src/apollo_mc/agents/base.py:27`
`telemetry_scope` is a mutable default list in the base class. Currently overridden correctly, but fragile (a new agent could forget). It's also never used for filtering in `TelemetryBus`/`DecisionCycle`.
*Fix:* Either remove `telemetry_scope` if filtering isn't implemented, or make it a required abstract property each agent must declare. Document intent.

**Type inconsistency: string literals vs enum in schemas (FIDO)**
`src/apollo_mc/agents/fido.py:66,75`
FIDO passes `go_nogo` as string literals; `SeatRecommendation.go_nogo: GoNoGo` allows Pydantic coercion to silently hide the type error. *(Same root cause as the high-severity findings.)*
*Fix:* Import `GoNoGo` and use `GoNoGo.GO` / `GoNoGo.NO_GO`.

**Tight coupling between DecisionCycle and agent concrete types**
`src/apollo_mc/orchestrator/decision_cycle.py:25-40`
`DecisionCycle` couples to `FlightDirectorAgent`, passed separately from the seats list. `tick()` calls `seat.evaluate()`, `flight.evaluate()`, then `flight.make_decision()` — hard to swap agents or mock.
*Fix:* Either add Flight Director to the seats list with a special flag, or extract a `DecisionMaker` interface; make `flight_director` optional if all agents can participate equally.

**Command log unbounded growth without retention policy**
`src/apollo_mc/core/command_dispatch.py:29,68`
`_command_log` (line 29) appends every command (line 68) with no limit → unbounded memory in long missions. No retention/truncation/archival. *(Duplicate of the high-severity `_command_log` finding.)*
*Fix:* Use a `maxlen` `collections.deque` (e.g. `maxlen=10000`) or periodic archival; add an export/clear method.

**Stale data from `gather(return_exceptions=True)` hides agent failures silently**
`src/apollo_mc/orchestrator/decision_cycle.py:48-57`
Line 49's `gather(return_exceptions=True)` converts agent exceptions to Exception objects; line 55 logs and continues, but the seat recommendation is skipped entirely. A critical seat (EECOM, FIDO) can silently fail, leaving the cycle inconsistent with missing seat data.
*Fix:* Provide a fallback recommendation (default NO_GO) for failed seats. Log with full tracebacks. Consider failing the whole cycle if critical seats fail rather than proceeding with partial data.

**No transaction semantics for decision → dispatch sequence**
`src/apollo_mc/orchestrator/decision_cycle.py:67-72`
The cycle atomically makes a decision (line 67) but dispatches commands one at a time (line 72) without atomicity. A mid-dispatch failure (kOS drops after command 2 of 5) executes some commands while `decision_history` records approval of all; on reconnect, no retry/dedup → commands re-execute or are lost.
*Fix:* Pre-validate all commands and execute as a batch with rollback on failure, or mark commands with a `dispatch_status` (pending/sent/acked) rather than binary approve/reject.

**Telemetry frame parsing lacks validation; null/missing fields cause cascading agent failures**
`src/apollo_mc/bridge/kos_client.py:84,87-133`
`_parse_telemetry()` parses raw JSON with loose handling. Line 94 uses `.get('phase', 'orbit')` (silent default) but `vessel`/`orbital` (lines 89-90) assume presence. Malformed JSON (e.g. missing resources array) at line 84 can fail or partially parse, feeding all agents bad data. *(Overlaps the critical telemetry findings.)*
*Fix:* Use Pydantic strict validation or explicit handling; pre-validate the JSON schema; return a validation-error tuple so the cycle can skip and retry instead of crashing.

**Missing error recovery for agent evaluation failures in decision cycle**
`src/apollo_mc/orchestrator/decision_cycle.py:48-57`
`tick()` uses `gather(return_exceptions=True)`; exceptions are logged and skipped (lines 54-56), but the cycle continues with missing recommendations. If a critical seat like FIDO fails, Flight Director still decides with incomplete info; no fallback or safe default. *(Overlaps the "stale data" finding.)*
*Fix:* For each failed seat, synthesize a safe default (e.g. STANDBY + no approved actions) for a complete `seat_recommendations`. Log at WARN with context. Add a `healthy_seats` metric to the decision record.

**MissionState mutable shared state lacks transaction semantics for concurrent access**
`src/apollo_mc/core/mission_state.py:39-46`
`MissionState` is documented "immutable-ish" ("Only the orchestrator mutates this; agents read it", line 11) but has mutable `update_telemetry()` / `record_decision()`. Multiple agents read `self._state` concurrently (`decision_cycle.py:48`) while the orchestrator mutates (lines 45, 68). The GIL helps but the pattern is fragile and assumes single-threaded cycle execution; async yields during mutation enable races.
*Fix:* Make `MissionState` truly immutable (return new instances), or protect mutations with an `asyncio.Lock`. Add a version counter to detect concurrent mutations. Document the threading model.

**Telemetry bus subscribers share state mutation without isolation**
`src/apollo_mc/core/telemetry_bus.py:37-42`
`publish()` calls all subscriber callbacks in parallel via `gather()`. Each subscriber gets the same frame reference and can mutate it or share state via the `MissionState` reference; no per-subscriber copy and no isolation boundary.
*Fix:* Snapshot the `TelemetryFrame` before publishing (`copy.deepcopy` or a frozen dataclass), or document that frames must be treated as immutable by subscribers. Consider a `FrameSnapshotID` to trace which snapshot each recommendation maps to.

**CommandDispatcher template substitution vulnerable to injection and missing parameters**
`src/apollo_mc/core/command_dispatch.py:31-52`
`translate()` uses `string.format()` (line 43) with no parameter type/value validation — `{value}` could be a string with newlines that breaks the kOS protocol. Templates are static/hardcoded (new commands need code changes). `eecom.py:60` dispatches a `deploy_solar` command absent from `KOS_TEMPLATES`, causing a silent translation failure. *(Overlaps the critical injection finding; also flags a real missing-template bug.)*
*Fix:* Add per-command-type parameter validation schemas (Pydantic). Whitelist allowed keys/types. Add a `deploy_solar` template or reject it with a clear error at dispatch. Consider externalizing templates to config for runtime extensibility.

**KosBridge assumes stable TCP connection without heartbeat or reconnect logic**
`src/apollo_mc/bridge/kos_client.py:66-75,77-85`
`send_command()` and `read_telemetry()` assume a healthy connection. If the kOS telnet server closes unexpectedly (network glitch, KSP crash), `asyncio.wait_for(..., timeout=10)` may hang or fail, leaving the bridge inconsistent. No backoff, heartbeat, or transparent reconnect. `mission_loop.py:118-120` catches `ConnectionError` but doesn't recover.
*Fix:* Add a periodic heartbeat (PING) to detect dead connections early. Implement exponential-backoff auto-reconnect in `send_command()`. Add a `_connection_healthy` flag and a retry decorator with max attempts. Document timeout behavior.

---

## Low

**No validation of MissionPhase enum in telemetry parsing**
`src/apollo_mc/bridge/kos_client.py:94`
`MissionPhase(data.get("phase", "orbit"))` doesn't catch `ValueError`; an unknown phase string raises uncaught. The `"orbit"` fallback masks the error.
*Fix:* Wrap the `MissionPhase()` constructor in try-except, log a warning before falling back to default, surfacing unexpected phase values.

**Broad `Any` usage in Coroutine return type**
`src/apollo_mc/core/telemetry_bus.py:12`
The `Subscriber` alias uses `Coroutine[Any, Any, None]`. Acceptable for simple callbacks but masks potential type issues if the coroutine receives unexpected values.
*Fix:* Use `Coroutine[None, None, None]` for callbacks that don't receive values, or define specific input types if `send()` is used.

**FlightDirector.make_decision iterates seat_recommendations twice**
`src/apollo_mc/agents/flight.py:44-51`
`make_decision()` iterates `.items()` (line 45) to build `seat_statuses`, then `.values()` again (line 50) to collect recommended actions. Negligible at ≤5 seats, but a single pass suffices.
*Fix:* Combine into one loop that builds `seat_statuses` and `all_actions` together.

**`overall_go` property re-evaluates all seats every access**
`src/apollo_mc/core/mission_state.py:24-29`
`overall_go` uses `all(...)` over the full recommendation set on every access — redundant if read multiple times per cycle, and violates O(1) property expectations.
*Fix:* Cache `overall_go` and update only when recommendations change, or read it at most once per cycle.

**Orbital velocity vis-viva test doesn't validate semi-major axis edge cases**
`tests/test_orbital_mechanics.py`
`test_circular_orbit_velocity` (line 15) only tests `r == a`. No test for elliptical orbits (`r != a`) or rejection of `r > a` (negative under-square-root).
*Fix:* Add: (1) elliptical `r < a` (periapsis), (2) elliptical `r > a` (apoapsis), (3) `math.sqrt` error on invalid input where vis-viva goes negative.

**Unused telemetry_scope declarations not enforced (EECOM)**
`src/apollo_mc/agents/eecom.py:20`
EECOM declares `telemetry_scope = ['power', 'resources']` but it's never used to filter/optimize delivery; `TelemetryBus` ignores it and `DecisionCycle` broadcasts the full frame. Dead code / incomplete feature.
*Fix:* Implement scope-based filtering in `TelemetryBus.publish()`, or remove the declarations and document the decision.

**Incomplete error handling in command dispatch**
`src/apollo_mc/core/command_dispatch.py:54-58`
`dispatch()` logs success but doesn't distinguish translation failure (returns `False` before logging) from actual dispatch failure. Silent bridge failures have no indication; `_command_log` is built but never exposed or summarized.
*Fix:* Log explicitly when `dispatch()` returns `False`. Consider a `Result[bool, DispatchError]` or `DispatchOutcome` dataclass. Expose `command_log` via a property or summary method.

**Lack of defensive null checks in KosBridge parsing**
`src/apollo_mc/bridge/kos_client.py:87-133`
`_parse_telemetry()` assumes all expected keys exist (`data['vessel']`, `data['orbital']`, etc.); `.get()` is only used for optional fields (`phase`, `comms`, `crew`). Incomplete or updated kOS data raises `KeyError`. *(Overlaps the critical KeyError finding.)*
*Fix:* Use `.get()` with sensible defaults for all nested accesses, or validate the whole structure with a schema before constructing `TelemetryFrame` for clearer errors.

**Command dispatch does not verify seat authority before logging**
`src/apollo_mc/core/command_dispatch.py:54-72`
`dispatch()` (line 54) logs and appends to `_command_log` without verifying the source seat's `authority_required`. Flight Director filtering (`flight.py:74-75`) is the only gate; a rogue agent calling `dispatch()` directly logs unauthorized commands as approved. *(Related to the high-severity authority-bypass finding.)*
*Fix:* Add an authority check in `dispatch()` before logging: `if command.authority_required > source_seat.authority: raise PermissionError(...)`.

**No idempotency guarantees for telemetry subscription/unsubscribe**
`src/apollo_mc/core/telemetry_bus.py:22-27`
`subscribe()` (lines 22-24) is idempotent (overwrites), but `unsubscribe()` (lines 26-27) silently succeeds even if the seat was never subscribed; double-unsubscribe silently drops the second call. No error reporting or state-change trace.
*Fix:* Return success/failure from `unsubscribe()` or raise `KeyError` if absent. Log subscribe/unsubscribe operations at debug/info.

**Agent telemetry_scope declarations are unused and inconsistently defined**
`src/apollo_mc/agents/base.py:27`
`SeatAgent` declares `telemetry_scope` as field names (line 27), and agents like `FidoAgent` (line 20) define it, but it's never used — all agents receive the full `TelemetryFrame`. A placeholder for future filtering creating dead code; some agents populate it, others don't. *(Overlaps the medium-severity base-class finding.)*
*Fix:* Implement filtering in `TelemetryBus.publish()`, or remove `telemetry_scope` and document in the README that all agents see full telemetry (intentional for Phase 2). Decide now to avoid Phase-3 confusion.

**No validation of phase transitions in MissionPhase enum**
`src/apollo_mc/schemas/telemetry.py:7-22`
`MissionPhase` is a flat enum with no valid-transition validation. `_parse_telemetry()` can coerce any phase string (line 94) without checking transition legality (e.g. PRELAUNCH → REENTRY), masking simulation/bridge bugs.
*Fix:* Define a transition graph (`dict[MissionPhase, set[MissionPhase]]`) and validate in `MissionState.update_telemetry()` or `_parse_telemetry()`. Log a warning on unexpected transitions; add a `phase_violation` constraint in relevant seat evaluations.

---

## Verification (pending)

Critical and High findings are slated for adversarial verification against the actual source. Until that pass completes, treat the following as **likely-true but unconfirmed**, with the highest-leverage real bugs to confirm first:

1. **`GoNoGo` string literals** in `agents/fido.py:66,75` and `agents/eecom.py:71,80` — confirm whether Pydantic silently coerces (works at runtime today) or raises. This single root cause spans ~10 reported entries.
2. **`deploy_solar` missing from `KOS_TEMPLATES`** (`command_dispatch.py` / `eecom.py:60`) — confirm the command an agent emits has no template, i.e. a real silent-failure path today.
3. **Format-string injection** (`command_dispatch.py:43`) — confirm exploitability is gated only by "command generation is internal today"; severity depends on the Phase 2/3 externalization plan.
4. **Unhandled JSON / KeyError in the bridge** (`kos_client.py:83-133`) — confirm no upstream guard catches these before the mission loop.
5. **FIDO unreachable circularization action** (`fido.py:47-61`) — confirm the early NO_GO return at lines 63-71 truly dominates the action condition.

---

## Adversarial verification (critical/high)

- **Unsafe String Formatting in Command Dispatch (Format String Injection)** — REFUTED: `str.format()` does not execute embedded code, brace-bearing values are treated as literal text, and parameters are currently agent-hardcoded (no untrusted source); safe as implemented today.
- **Unhandled JSON parse exceptions in telemetry bridge** — CONFIRMED-REAL: `json.loads()` (and the `wait_for` timeout) in `read_telemetry()` raise `JSONDecodeError`/`asyncio.TimeoutError` that the mission loop's `ConnectionError`/`KeyboardInterrupt`-only handler doesn't catch, crashing the loop.
- **Unhandled KeyError exceptions in telemetry parsing** — CONFIRMED-REAL: `_parse_telemetry()` does direct dict access on `vessel`/`orbital`/`power` with no `.get()`/try-except; a malformed/incomplete kOS frame raises `KeyError` uncaught by the mission loop.
- **No test coverage for CommandDispatcher** — CONFIRMED-REAL: `translate()`/`dispatch()` have zero tests; untested error handling and unchecked `dispatch()` return value let malformed agent commands fail only at runtime.
- **No test coverage for DecisionCycle** — CONFIRMED-REAL: the core orchestration class (`tick()`, parallel seat eval, exception recovery, dispatch) has zero unit tests despite running every production tick.
- **No test coverage for TelemetryBus pub/sub system** — CONFIRMED-REAL: no `TelemetryBus` test exists; callback invocation/exception-isolation/frame distribution are untested (and `subscribe()` is unused dead code, so failures would be silent).
- **Type Error: String literal passed to Enum-typed field in EecomAgent** — REFUTED: `GoNoGo` is a str-backed enum and Pydantic v2 coerces `"GO"`/`"NO_GO"` to enum members; all tests pass — a style preference, not a runtime error.
- **Type Error: String literal passed to Enum-typed field in FidoAgent** — CONFIRMED-REAL: type-safety violation — Pydantic v2 coercion masks it at runtime but mypy strict flags `str` vs `GoNoGo`; brittle if coercion is ever disabled.
- **Unreachable Code: Impossible circularization action condition in FidoAgent** — CONFIRMED-REAL: the `periapsis < 70km` action condition is dominated by the same-threshold constraint check that forces an earlier NO_GO return, so the action never reaches a GO recommendation.
- **Unvalidated Command Parameters in CommandRequest Schema** — CONFIRMED-REAL: `parameters` dict has zero validation; newline/semicolon injection into kOS commands is proven workable and becomes exploitable the moment parameters come from any external source.
- **String literals used instead of GoNoGo enum values in flight controller agents** — CONFIRMED-REAL: type-safety violation flagged by mypy strict at fido.py:66,75 and eecom.py:71,80; runtime-masked by Pydantic coercion but inconsistent with the correct base-class pattern.
- **String literals used instead of GoNoGo enum values (eecom.py:71,80)** — CONFIRMED-REAL: same static type violation mypy catches; the base class's `.go()`/`.no_go()` helpers already demonstrate the correct enum usage.
- **Untyped dict parameter with type: ignore suppression** — CONFIRMED-REAL: `# type: ignore[type-arg]` hides the method from mypy strict and there's no runtime validation before unsafe key access — a latent missing-key failure path.
- **Command log array unbounded growth in CommandDispatcher** — CONFIRMED-REAL: `_command_log` grows without bound and is never read; a real (low-to-moderate severity) leak that matters for long/multi-day missions.
- **Decision cycle: resource iterated multiple times per frame** — REFUTED: real KSP vessels carry 4-8 resources (test data has 2), the membership check is O(1), and iteration cost is negligible; severity is mischaracterized.
- **Unhandled exceptions swallowed in telemetry bus subscribers** — REFUTED: the `return_exceptions=True` smell is in dead code — no subscribers are ever registered and the active path (`DecisionCycle.tick`) logs seat exceptions correctly.
- **Flight Director evaluation not wrapped in exception handling** — CONFIRMED-REAL: the Flight Director `evaluate()` call is unguarded (unlike seat eval's `gather(return_exceptions=True)`), so a future-enhanced FD failure crashes the whole cycle.
- **Command dispatch exceptions silently ignored in decision_cycle.py** — CONFIRMED-REAL: the dispatch loop has no try-except; `asyncio.TimeoutError` and other send_command failures propagate past the mission loop's `ConnectionError`-only handler.
- **Type mismatch in FIDO and EECOM agents - string vs GoNoGo enum** — CONFIRMED-REAL: mypy strict confirms type violations at both agents; tests pass only via Pydantic coercion, a latent risk if strict validation is enabled.
- **Incomplete command dispatch error handling (command_dispatch.py:54-73)** — CONFIRMED-REAL: `dispatch()` doesn't wrap `send_command()`; uncaught exceptions crash the loop and the unchecked `bool` return makes failures invisible to callers.
- **Missing timeout/retry for critical loop - no recovery mechanism** — CONFIRMED-REAL: the main loop catches only `ConnectionError`/`KeyboardInterrupt`; `TimeoutError`/`JSONDecodeError`/`KeyError`/`ValueError` all abort the mission with no backoff or retry.
- **MissionState property logic untested** — CONFIRMED-REAL: `overall_go`/`no_go_seats` are untested (also unused dead code, superseded by inline Flight Director logic) — a code-health gap.
- **FIDO conditional action generation logic untested** — CONFIRMED-REAL: no test sets all three trigger conditions (or their boundaries) to exercise the `lock_steering` action; `recommended_actions` is never asserted in any test.
- **EECOM solar panel deployment logic untested** — CONFIRMED-REAL: no test sets negative charge_rate + charge < 50% + panels-not-deployed simultaneously, so the failsafe deploy recommendation has zero coverage.
- **CommandDispatcher parameter validation missing** — REFUTED: the code already catches `KeyError` and returns `None` (handled downstream); `str.format()` doesn't raise `ValueError` for these templates — only the test-coverage gap is real, not a logic bug.

**Tally: 19 confirmed / 5 refuted.**
