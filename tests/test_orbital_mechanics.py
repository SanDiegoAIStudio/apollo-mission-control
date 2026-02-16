"""Tests for orbital mechanics calculations."""

import math

from apollo_mc.tools.orbital_mechanics import (
    RADIUS_KERBIN,
    MU_KERBIN,
    burn_time,
    circularization_dv,
    hohmann_transfer_dv,
    orbital_velocity,
)


def test_circular_orbit_velocity() -> None:
    """Vis-viva for circular orbit (r == a) should give sqrt(mu/r)."""
    r = RADIUS_KERBIN + 80_000  # 80km orbit
    v = orbital_velocity(MU_KERBIN, r, r)
    expected = math.sqrt(MU_KERBIN / r)
    assert abs(v - expected) < 0.01


def test_hohmann_transfer_positive_dv() -> None:
    """Hohmann transfer to higher orbit should require positive delta-v."""
    r1 = RADIUS_KERBIN + 80_000  # 80km
    r2 = RADIUS_KERBIN + 200_000  # 200km
    dv1, dv2 = hohmann_transfer_dv(MU_KERBIN, r1, r2)
    assert dv1 > 0
    assert dv2 > 0


def test_hohmann_transfer_symmetry() -> None:
    """Total delta-v should be the same regardless of direction."""
    r1 = RADIUS_KERBIN + 80_000
    r2 = RADIUS_KERBIN + 200_000
    dv1_up, dv2_up = hohmann_transfer_dv(MU_KERBIN, r1, r2)
    dv1_down, dv2_down = hohmann_transfer_dv(MU_KERBIN, r2, r1)
    total_up = abs(dv1_up) + abs(dv2_up)
    total_down = abs(dv1_down) + abs(dv2_down)
    assert abs(total_up - total_down) < 1.0  # within 1 m/s


def test_circularization_at_apoapsis() -> None:
    """Circularizing at apoapsis should require prograde burn."""
    r_apo = RADIUS_KERBIN + 200_000
    r_peri = RADIUS_KERBIN + 80_000
    dv = circularization_dv(MU_KERBIN, r_apo, r_peri, "apoapsis")
    assert dv > 0
    assert dv < 500  # should be reasonable for Kerbin


def test_burn_time_calculation() -> None:
    """Burn time should be positive and finite for valid inputs."""
    t = burn_time(
        delta_v=100,  # m/s
        isp=320,  # seconds
        mass=10_000,  # kg
        thrust=200_000,  # N (200kN)
    )
    assert t > 0
    assert t < 60  # should be a short burn


def test_burn_time_zero_thrust() -> None:
    """Zero thrust should give infinite burn time."""
    t = burn_time(delta_v=100, isp=320, mass=10_000, thrust=0)
    assert t == float("inf")
