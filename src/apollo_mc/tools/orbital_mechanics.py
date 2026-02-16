"""Orbital mechanics calculations — tools available to FIDO and GUIDO agents."""

import math


# Gravitational parameters (mu = GM) in m^3/s^2
MU_KERBIN = 3.5316e12
MU_MUN = 6.5138e10
MU_KERBOL = 1.1723e18

# Body radii in meters
RADIUS_KERBIN = 600_000
RADIUS_MUN = 200_000

GRAVITATIONAL_PARAMS: dict[str, float] = {
    "Kerbin": MU_KERBIN,
    "Mun": MU_MUN,
    "Kerbol": MU_KERBOL,
}

BODY_RADII: dict[str, float] = {
    "Kerbin": RADIUS_KERBIN,
    "Mun": RADIUS_MUN,
}


def orbital_velocity(mu: float, r: float, a: float) -> float:
    """Vis-viva equation: velocity at distance r in orbit with semi-major axis a."""
    return math.sqrt(mu * (2 / r - 1 / a))


def hohmann_transfer_dv(
    mu: float,
    r1: float,
    r2: float,
) -> tuple[float, float]:
    """Calculate delta-v for a Hohmann transfer between two circular orbits.

    Returns (dv1, dv2) — the two burn magnitudes.
    r1 and r2 are orbital radii from center of body (not altitude).
    """
    # Transfer orbit semi-major axis
    a_transfer = (r1 + r2) / 2

    # Velocity in initial circular orbit
    v1_circular = math.sqrt(mu / r1)

    # Velocity at periapsis of transfer orbit
    v1_transfer = orbital_velocity(mu, r1, a_transfer)

    # First burn
    dv1 = v1_transfer - v1_circular

    # Velocity in final circular orbit
    v2_circular = math.sqrt(mu / r2)

    # Velocity at apoapsis of transfer orbit
    v2_transfer = orbital_velocity(mu, r2, a_transfer)

    # Second burn
    dv2 = v2_circular - v2_transfer

    return dv1, dv2


def circularization_dv(
    mu: float,
    current_apoapsis: float,
    current_periapsis: float,
    circularize_at: str = "apoapsis",
) -> float:
    """Delta-v to circularize at apoapsis or periapsis.

    Radii are from center of body.
    """
    a_current = (current_apoapsis + current_periapsis) / 2

    if circularize_at == "apoapsis":
        r = current_apoapsis
    else:
        r = current_periapsis

    v_current = orbital_velocity(mu, r, a_current)
    v_circular = math.sqrt(mu / r)

    return abs(v_circular - v_current)


def burn_time(delta_v: float, isp: float, mass: float, thrust: float) -> float:
    """Estimate burn time using the Tsiolkovsky rocket equation.

    Args:
        delta_v: Required delta-v in m/s
        isp: Specific impulse in seconds
        mass: Current vessel mass in kg
        thrust: Engine thrust in Newtons
    """
    if thrust <= 0 or isp <= 0:
        return float("inf")

    g0 = 9.80665  # standard gravity
    exhaust_velocity = isp * g0
    mass_ratio = math.exp(delta_v / exhaust_velocity)
    fuel_mass = mass * (1 - 1 / mass_ratio)
    mass_flow_rate = thrust / exhaust_velocity

    return fuel_mass / mass_flow_rate


def time_to_phase_angle(
    mu: float,
    r_current: float,
    r_target: float,
    current_angle_deg: float,
) -> float:
    """Time until the correct phase angle for a Hohmann transfer.

    Useful for planning transfers to the Mun.
    """
    a_transfer = (r_current + r_target) / 2
    transfer_time = math.pi * math.sqrt(a_transfer**3 / mu)

    # Angular velocity of target
    omega_target = math.sqrt(mu / r_target**3)

    # Phase angle needed
    phase_angle = math.pi - omega_target * transfer_time

    # Current phase angle in radians
    current_angle_rad = math.radians(current_angle_deg)

    # Angle to sweep
    angle_to_sweep = (phase_angle - current_angle_rad) % (2 * math.pi)

    # Angular velocity of vessel
    omega_vessel = math.sqrt(mu / r_current**3)

    # Relative angular velocity
    omega_rel = omega_vessel - omega_target

    if omega_rel <= 0:
        return float("inf")

    return angle_to_sweep / omega_rel
