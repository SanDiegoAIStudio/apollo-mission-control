"""Mutation gate: prove the test suite goes red when a guarded fix is reverted.

Each entry reverts one fix in a temporary copy of the repo and runs the test that
claims to cover it. A mutation that leaves the test green is a gap in the test, not
in the code. Run from the repo root with the project interpreter:

    python tests/mutation_gate.py

Exit 0 means every selector passes on the clean tree, every mutation was caught, and
no target string went stale.
"""

from __future__ import annotations

import pathlib
import shutil
import subprocess
import sys
import tempfile

REPO = pathlib.Path(__file__).resolve().parent.parent

# (name, file, text to find exactly once, replacement, pytest selector)
MUTATIONS: list[tuple[str, str, str, str, str]] = [
    (
        "throttle range check",
        "src/apollo_mc/core/command_dispatch.py",
        "    if raw < 0.0 or raw > 1.0:\n",
        "    if False:\n",
        "tests/test_command_dispatch.py::test_translate_rejects_invalid",
    ),
    (
        "throttle finite check",
        "src/apollo_mc/core/command_dispatch.py",
        "    if not math.isfinite(raw):\n",
        "    if False:\n",
        "tests/test_command_dispatch.py::test_translate_rejects_invalid",
    ),
    (
        "send failure returns False",
        "src/apollo_mc/core/command_dispatch.py",
        "                return False\n\n        logger.info(",
        "                return True\n\n        logger.info(",
        "tests/test_command_dispatch.py::test_dispatch_timeout_leaves_log_empty",
    ),
    (
        "parameter string validator",
        "src/apollo_mc/schemas/commands.py",
        "            if isinstance(item, str) and "
        "_PARAMETER_TOKEN.fullmatch(item) is None:\n",
        "            if False:\n",
        "tests/test_command_dispatch.py::test_parameters_reject_injected_direction",
    ),
    (
        "steering allowlist",
        "src/apollo_mc/core/command_dispatch.py",
        "    if direction not in STEERING_DIRECTIONS:\n",
        "    if False:\n",
        "tests/test_command_dispatch.py::test_translate_rejects_invalid",
    ),
    (
        "steering allowlist shrink",
        "src/apollo_mc/core/command_dispatch.py",
        '        "NORTH",\n    }\n)',
        '        "NORTH",\n        "NORMAL",\n    }\n)',
        "tests/test_command_dispatch.py::test_translate_rejects_invalid",
    ),
    (
        "warp integral check",
        "src/apollo_mc/core/command_dispatch.py",
        "    if not math.isfinite(raw) or not float(raw).is_integer():\n",
        "    if not math.isfinite(raw):\n",
        "tests/test_command_dispatch.py::test_translate_rejects_invalid",
    ),
    (
        "command log bound",
        "src/apollo_mc/core/command_dispatch.py",
        "deque(maxlen=COMMAND_LOG_SIZE)",
        "deque()",
        "tests/test_command_dispatch.py::test_command_log_keeps_last_1000",
    ),
    (
        "KeyError becomes TelemetryError",
        "src/apollo_mc/bridge/kos_client.py",
        "        except KeyError as exc:\n"
        '            raise TelemetryError(f"missing telemetry key: {exc}") from exc\n',
        "        except KeyError as exc:\n            raise\n",
        "tests/test_kos_client.py::test_parse_missing_power_names_key",
    ),
    (
        "JSON decode becomes TelemetryError",
        "src/apollo_mc/bridge/kos_client.py",
        "        except (ValueError, RecursionError) as exc:\n"
        '            raise TelemetryError(f"telemetry JSON decode failed: '
        '{raw[:80]}") from exc\n',
        "        except ValueError as exc:\n            raise\n",
        "tests/test_kos_client.py::test_read_telemetry_rejects_non_json",
    ),
    (
        "EOF closes the connection",
        "src/apollo_mc/bridge/kos_client.py",
        '        if response == b"":\n'
        "            await self._drop_connection()\n"
        '            raise ConnectionError("kOS closed the connection")\n',
        "        if False:\n"
        "            await self._drop_connection()\n"
        '            raise ConnectionError("kOS closed the connection")\n',
        "tests/test_kos_client.py::test_send_command_eof_raises_connection_error",
    ),
    (
        "allow_inf_nan on vessel mass",
        "src/apollo_mc/schemas/telemetry.py",
        "    model_config = ConfigDict(allow_inf_nan=False)\n\n"
        "    mission_time: float  # seconds since launch\n",
        "    model_config = ConfigDict(allow_inf_nan=True)\n\n"
        "    mission_time: float  # seconds since launch\n",
        "tests/test_kos_client.py::test_parse_rejects_non_finite_mass",
    ),
    (
        "flight director guard",
        "src/apollo_mc/orchestrator/decision_cycle.py",
        "        except Exception as exc:\n"
        '            logger.error("flight_evaluation_error", error=str(exc))\n',
        "        except Exception as exc:\n            raise\n",
        "tests/test_decision_cycle.py::test_tick_flight_failure_becomes_no_go",
    ),
    (
        "dispatch guard",
        "src/apollo_mc/orchestrator/decision_cycle.py",
        "            except Exception as exc:\n"
        "                sent = False\n"
        "                failure = str(exc)\n",
        "            except Exception as exc:\n"
        "                raise\n",
        "tests/test_decision_cycle.py::test_dispatch_error_does_not_abort_tick",
    ),
    (
        "batch abort",
        "src/apollo_mc/orchestrator/decision_cycle.py",
        "                break\n",
        "                continue\n",
        "tests/test_decision_cycle.py::test_dispatch_raise_aborts_the_batch",
    ),
    (
        "seat fail closed",
        "src/apollo_mc/orchestrator/decision_cycle.py",
        "                recommendations[seat.seat_name] = seat.no_go(\n"
        '                    "evaluation failed",\n'
        "                    [str(result)],\n"
        "                )\n",
        "                continue\n",
        "tests/test_decision_cycle.py::test_tick_failed_seat_is_no_go",
    ),
    (
        "seat exception isolation",
        "src/apollo_mc/orchestrator/decision_cycle.py",
        "            if isinstance(result, BaseException):\n",
        "            if False:\n",
        "tests/test_decision_cycle.py::test_tick_failed_seat_is_no_go",
    ),
    (
        "telemetry error limit",
        "src/apollo_mc/orchestrator/mission_loop.py",
        "MAX_CONSECUTIVE_TELEMETRY_ERRORS = 5",
        "MAX_CONSECUTIVE_TELEMETRY_ERRORS = 50",
        "tests/test_mission_loop.py::test_five_telemetry_errors_stop_the_loop",
    ),
    (
        "nested JSON becomes TelemetryError",
        "src/apollo_mc/bridge/kos_client.py",
        "        except (ValueError, RecursionError) as exc:\n",
        "        except ValueError as exc:\n",
        "tests/test_kos_client.py::test_read_telemetry_rejects_deeply_nested_json",
    ),
    (
        "silent banner becomes ConnectionError",
        "src/apollo_mc/bridge/kos_client.py",
        "        except (TimeoutError, OSError, ValueError) as exc:\n"
        "            await self._drop_connection()\n",
        "        except (TimeoutError, OSError, ValueError) as exc:\n"
        "            raise\n",
        "tests/test_kos_client.py::test_connect_silent_banner_raises_connection_error",
    ),
    (
        "connect failure is caught by the loop",
        "src/apollo_mc/orchestrator/mission_loop.py",
        "\n    except OSError as exc:\n",
        "\n    except ConnectionRefusedError as exc:\n",
        "tests/test_mission_loop.py::test_connect_failure_returns_without_raising",
    ),
    (
        "overlong banner becomes ConnectionError",
        "src/apollo_mc/bridge/kos_client.py",
        "        except (TimeoutError, OSError, ValueError) as exc:\n"
        "            await self._drop_connection()\n",
        "        except TimeoutError as exc:\n"
        "            await self._drop_connection()\n",
        "tests/test_kos_client.py::test_connect_overlong_banner_raises_connection_error",
    ),
    (
        "transport OSError stops the loop",
        "src/apollo_mc/orchestrator/mission_loop.py",
        "                except OSError as exc:\n",
        "                except ConnectionError as exc:\n",
        "tests/test_mission_loop.py::test_transport_oserror_stops_the_loop",
    ),
]


def run_one(name: str, rel: str, old: str, new: str, selector: str) -> str:
    with tempfile.TemporaryDirectory() as tmp:
        root = pathlib.Path(tmp)
        for folder in ("src", "tests"):
            shutil.copytree(
                REPO / folder,
                root / folder,
                ignore=shutil.ignore_patterns("__pycache__", ".pytest_cache"),
            )
        shutil.copy(REPO / "pyproject.toml", root / "pyproject.toml")
        target = root / rel
        text = target.read_text()
        if text.count(old) != 1:
            return f"STALE    {name}: target found {text.count(old)} times"
        target.write_text(text.replace(old, new))
        env = {
            "PATH": "/usr/bin:/bin",
            "PYTHONPATH": f"{root / 'src'}:{root}",
            "HOME": tmp,
        }
        result = subprocess.run(
            [sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider", selector],
            cwd=root,
            env=env,
            capture_output=True,
            text=True,
            check=False,
        )
        if result.returncode == 1:
            return f"CAUGHT   {name}"
        if result.returncode == 0:
            return f"SURVIVED {name}: test stayed green against broken code"
        return (
            f"BROKEN   {name}: pytest exit {result.returncode}, "
            "selector missing or collection error"
        )


def baseline_passes() -> bool:
    """Every selector must pass on the unmutated tree, or a renamed test hides a gap."""
    selectors = [mutation[4] for mutation in MUTATIONS]
    result = subprocess.run(
        [sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider", *selectors],
        cwd=REPO,
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        print("BASELINE FAILED: a selector did not pass on the unmutated tree")
        print(result.stdout[-2000:])
    return result.returncode == 0


def main() -> int:
    if not baseline_passes():
        return 1
    lines = [run_one(*mutation) for mutation in MUTATIONS]
    print("\n".join(lines))
    caught = sum(line.startswith("CAUGHT") for line in lines)
    print(f"\n{caught}/{len(MUTATIONS)} mutations caught")
    return 0 if caught == len(MUTATIONS) else 1


if __name__ == "__main__":
    raise SystemExit(main())
