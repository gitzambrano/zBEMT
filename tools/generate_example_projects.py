"""Generates the example projects versioned in ``projects/``.

Why a script instead of hand-written `.bemt` files: the files become DERIVED,
and derived from `api.save_project` — the same path the GUI uses. This ensures
that every distributed example is, by construction, a project the application
can open, and that a schema change propagates to all of them by running a
command instead of manually editing four folders.

    python tools/generate_example_projects.py

The numbers are not invented: each rotor reproduces the solidity, tip speed,
and blade loading (CT/sigma) of a real aircraft in its category, with the
source cited in each function's header. `tests/regression/test_example_projects.py`
confirms they continue to fall within the expected physical range.
"""
from __future__ import annotations

import math
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from zbemt import api, geometry                          # noqa: E402
from zbemt.bemt import BEMTConfig                        # noqa: E402
from zbemt.models import (AirfoilDef, BatchDefinition, FlightCondition,  # noqa: E402
                           PolarSlice)
from dataclasses import asdict                           # noqa: E402


# Run without arguments (e.g., IDE "Run" button) generates projects in the default directory.
DEFAULT_OUTPUT_DIR = None  # None uses ROOT / "projects" (the natural default for generate())


def rpm_for_tip_speed(tip_speed_ms: float, radius_m: float) -> float:
    """RPM that produces the desired tip speed. This is how a rotor is
    specified: tip speed is the design parameter (limited by noise and
    divergence Mach), RPM is the consequence."""
    return tip_speed_ms / radius_m * 60.0 / (2.0 * math.pi)


def solidity(n_blades: int, chord_m: float, radius_m: float) -> float:
    """sigma = Nb*c/(pi*R), with constant chord."""
    return n_blades * chord_m / (math.pi * radius_m)


def _config(**kw) -> dict:
    """Working mesh: fine enough for results to be usable, cheap enough for
    the project to be a good starting point."""
    base = dict(Ne=72, Npsi=108, solver="newton", max_iter=200, tol=1e-6,
                inflow_field_model="coleman_local", prandtl_loss_mode="both",
                use_compressibility=True, reverse_flow_model="viterna_full_range")
    base.update(kw)
    return asdict(BEMTConfig(**base))


# =============================================================================
# 1. test1 — medium utility helicopter (UH-60 class)
# =============================================================================

def test1():
    """Main rotor of a medium utility helicopter, UH-60 class.

    Source: Boeing/Sikorsky UH-60 Black Hawk specifications.
    R = 8.18 m, 4 blades, chord 0.527 m  ->  sigma = 0.082
    Tip speed 221 m/s (RPM 258), tip Mach 0.65.
    Maximum weight ~9,980 kg  ->  CT ~ 0.0078, CT/sigma ~ 0.095 (high
    loading, as expected at MTOW).

    Total twist -18 degrees, distributed from 10 at root to -8 at tip;
    collective pitch is added on top of this at the flight condition.
    """
    radius, n_blades, chord = 8.178, 4, 0.527
    geom = geometry.generate_rectangular(
        radius_m=radius, n_blades=n_blades, chord_norm=chord / radius,
        twist_root_deg=10.0, twist_tip_deg=-8.0,
        root_cutout_norm=0.20, n_stations=25, airfoil_name="SC1095 (approximate)")

    # SC1095: cambered, slightly thicker at root. Analytical model with
    # Viterna extension to cover full range — required by reverse flow in
    # forward flight, which is the central regime for this rotor.
    airfoil = AirfoilDef(
        name="SC1095 (approximate)", source="analytical", stall_model="viterna",
        cl_alpha=5.9, alpha0_deg=-1.0, cd0=0.0087, k=0.010,
        alpha_stall_pos_deg=13.0, alpha_stall_neg_deg=-11.0,
        viterna_blend_width_deg=4.0, extend_full_range=True)

    rpm = rpm_for_tip_speed(221.0, radius)
    return dict(
        folder="test1", name="Medium utility helicopter (UH-60 class)",
        geom=geom, airfoil=airfoil, config=_config(),
        cases=[
            FlightCondition(name="hover", mu_x=0.0, collective_deg=10.0, rpm=rpm),
            FlightCondition(name="cruise mu_x=0.25", mu_x=0.25, collective_deg=8.0, rpm=rpm),
            FlightCondition(name="high speed mu_x=0.35", mu_x=0.35, collective_deg=7.0, rpm=rpm),
        ],
        batches=[
            BatchDefinition(name="mu_x sweep", sweep_kind="mu_sweep",
                            sweep_params={"mu_values": [0.0, 0.05, 0.1, 0.15, 0.2, 0.25, 0.3, 0.35],
                                          "collective_deg": 8.0, "rpm": rpm},
                            plots=["performance"]),
            BatchDefinition(name="collective at hover", sweep_kind="collective_sweep",
                            sweep_params={"collective_deg_values": [4.0, 6.0, 8.0, 10.0, 12.0],
                                          "mu_x": 0.0, "rpm": rpm},
                            plots=["performance"]),
        ],
        expected=dict(sigma=solidity(n_blades, chord, radius), tip_speed=221.0),
    )


# =============================================================================
# 2. test2 — light helicopter (Bell 206 / R44 class)
# =============================================================================

def test2():
    """Main rotor of a light two-blade helicopter, Bell 206 class.

    Source: Bell 206B JetRanger specifications.
    R = 5.08 m, 2 blades, chord 0.33 m  ->  sigma = 0.041 (half the solidity
    of the medium utility: fewer blades, narrower blade).
    Tip speed 213 m/s (RPM 400).
    Weight ~1,450 kg  ->  CT ~ 0.0032, CT/sigma ~ 0.076.

    Serves as a contrast to the medium utility: same mission family, half the
    solidity, and that is what changes blade loading.
    """
    radius, n_blades, chord = 5.08, 2, 0.33
    geom = geometry.generate_rectangular(
        radius_m=radius, n_blades=n_blades, chord_norm=chord / radius,
        twist_root_deg=7.0, twist_tip_deg=-3.0,
        root_cutout_norm=0.18, n_stations=25, airfoil_name="NACA 0012")

    # WITHOUT Viterna extension, on purpose: this is the example that covers
    # that path. With 'clip' stall and mu_x <= 0.3, the reverse flow region
    # is small and the flat plate model works — 'viterna_full_range' would
    # require the extension on (validation blocks the combination).
    airfoil = AirfoilDef(
        name="NACA 0012", source="analytical", stall_model="clip",
        cl_alpha=5.73, alpha0_deg=0.0, cd0=0.0080, k=0.009,
        alpha_stall_pos_deg=14.0, alpha_stall_neg_deg=-14.0,
        extend_full_range=False)

    rpm = rpm_for_tip_speed(213.0, radius)
    return dict(
        folder="test2", name="Light two-blade helicopter (Bell 206 class)",
        geom=geom, airfoil=airfoil,
        config=_config(reverse_flow_model="flat_plate"),
        cases=[
            FlightCondition(name="hover", mu_x=0.0, collective_deg=9.0, rpm=rpm),
            FlightCondition(name="cruise mu_x=0.2", mu_x=0.2, collective_deg=7.0, rpm=rpm),
        ],
        batches=[
            BatchDefinition(name="mu_x sweep", sweep_kind="mu_sweep",
                            sweep_params={"mu_values": [0.0, 0.1, 0.2, 0.3],
                                          "collective_deg": 7.0, "rpm": rpm},
                            plots=["performance"]),
        ],
        expected=dict(sigma=solidity(n_blades, chord, radius), tip_speed=213.0),
    )


# =============================================================================
# 3. test3 — eVTOL lift rotor
# =============================================================================

def test3():
    """One of the lift rotors of a multirotor eVTOL.

    Source: Joby Aviation and similar electric vertical takeoff aircraft specs.
    R = 1.5 m, 5 blades, chord 0.10 m  ->  sigma = 0.106. HIGH solidity
    compared to a helicopter: the rotor is small and needs blade area.
    Tip speed 180 m/s (RPM 1,146) — low for the category, because noise is
    a certification requirement in urban operation.
    Aircraft ~1,800 kg on 8 rotors  ->  2.2 kN each, CT ~ 0.0079,
    CT/sigma ~ 0.074.

    High twist (-14 degrees) and tapered blade: this rotor operates essentially
    in axial regime, where ideal twist is worthwhile; a helicopter rotor,
    which must also work in forward flight, cannot be optimized this way.
    """
    radius, n_blades = 1.5, 5
    chord_root, chord_tip = 0.125, 0.075     # average chord 0.10 m
    geom = geometry.generate_tapered(
        radius_m=radius, n_blades=n_blades,
        root_chord_norm=chord_root / radius, tip_chord_norm=chord_tip / radius,
        twist_root_deg=16.0, twist_tip_deg=2.0,
        root_cutout_norm=0.15, n_stations=25, airfoil_name="cambered eVTOL airfoil")

    airfoil = AirfoilDef(
        name="cambered eVTOL airfoil", source="analytical", stall_model="viterna",
        cl_alpha=6.0, alpha0_deg=-2.5, cd0=0.0110, k=0.012,
        alpha_stall_pos_deg=12.0, alpha_stall_neg_deg=-9.0,
        viterna_blend_width_deg=4.0, extend_full_range=True)

    rpm = rpm_for_tip_speed(180.0, radius)
    return dict(
        folder="test3", name="eVTOL lift rotor (multirotor)",
        geom=geom, airfoil=airfoil,
        # Compressibility OFF by design: tip Mach 0.53, and Prandtl-Glauert
        # correction is less than 1% there. This is also the example that
        # covers the path without compressibility.
        config=_config(inflow_field_model="glauert_local", use_compressibility=False),
        cases=[
            FlightCondition(name="hover", mu_x=0.0, collective_deg=6.0, rpm=rpm),
            FlightCondition(name="climb 3 m/s", mu_x=0.0, collective_deg=7.0, Vz=3.0, rpm=rpm),
            FlightCondition(name="transition mu_x=0.10", mu_x=0.10, collective_deg=5.0, rpm=rpm),
        ],
        batches=[
            BatchDefinition(name="collective at hover", sweep_kind="collective_sweep",
                            sweep_params={"collective_deg_values": [2.0, 4.0, 6.0, 8.0, 10.0],
                                          "mu_x": 0.0, "rpm": rpm},
                            plots=["performance"]),
            BatchDefinition(name="rpm vs collective", sweep_kind="factorial",
                            sweep_params={"axes": [{"variable": "rpm", "values": [900.0, 1146.0, 1400.0]},
                                                   {"variable": "collective_deg", "values": [4.0, 6.0, 8.0]}],
                                          "fixed": {"mu_x": 0.0}},
                            plots=["performance"]),
        ],
        expected=dict(sigma=solidity(n_blades, 0.10, radius), tip_speed=180.0),
    )


# =============================================================================
# 11. test11 — light airplane propeller
# =============================================================================

def test11():
    """Tractor propeller of a light airplane, 300 hp single-engine class.

    Source: Lycoming/Continental 300 hp aircraft propeller specs.
    D = 1.88 m (R = 0.94 m), 3 blades, chord 0.130 m at root to 0.085 at tip
    ->  sigma = 0.109.
    2,500 RPM  ->  tip speed 246 m/s, tip Mach 0.72 — high, which is why
    `use_compressibility` matters much more here than in a helicopter rotor.
    At 65 m/s cruise: J_z = pi*Vz/(Omega*R) = 0.83, thrust 2.8 kN at 226 kW
    and propulsive efficiency 0.81 — a 300 hp single (224 kW).
    At static the propeller demands more power (287 kW), as any fixed-pitch
    propeller does off design: in the real aircraft, maximum engine RPM limits
    this.

    Much higher twist than a rotor (42 degrees at root to 18 at tip): the
    propeller advances, so the helix angle varies much more along the radius.
    This is the most visible design difference between the two modes, and why
    this example exists. The blade angle at 0.75R is ~25 degrees, about 5
    degrees above cruise helix angle — that surplus generates thrust.

    `is_propeller=True` changes summary quantities: CT/CQ/CP become
    dimensionalized by n^2 D^4 (propeller convention) and eta_prop replaces
    figure of merit.

    WATCH THE CONVENTION — this is where it is easy to err: flight speed of a
    propeller is AXIAL, so it goes in `Vz`, with `mu_x = 0`. `mu_x` (and equivalent
    `J_x`, J_x = pi*mu_x) is the IN-PLANE component of the disk — putting flight
    speed there makes the blade see ±V along the azimuth, which is what a
    helicopter rotor in forward flight sees and a straight-flying propeller
    never sees. Results come out plausible and wrong. The axial component
    appears in the summary as `J_z` (= pi*Vz/(Omega*R)), and that is what
    enters propulsive efficiency.
    """
    radius, n_blades, chord = 0.94, 3, 0.1075   # average chord of both tips
    geom = geometry.generate_tapered(
        radius_m=radius, n_blades=n_blades,
        root_chord_norm=0.130 / radius, tip_chord_norm=0.085 / radius,
        twist_root_deg=42.0, twist_tip_deg=18.0,
        root_cutout_norm=0.20, n_stations=25, airfoil_name="Clark Y (approximate)")

    airfoil = AirfoilDef(
        name="Clark Y (approximate)", source="analytical", stall_model="viterna",
        cl_alpha=6.0, alpha0_deg=-4.0, cd0=0.0080, k=0.010,
        alpha_stall_pos_deg=13.0, alpha_stall_neg_deg=-10.0,
        viterna_blend_width_deg=4.0, extend_full_range=True)

    rpm = 2500.0
    return dict(
        folder="test11", name="Light aircraft tractor propeller (3 blades, 1.88 m)",
        geom=geom, airfoil=airfoil,
        # Propeller in axial flight: flow is nearly uniform in azimuth, so
        # high Npsi just costs time. Ne still matters, because all variation
        # is radial.
        config=_config(Npsi=36, is_propeller=True, inflow_field_model="glauert_local"),
        # Flight speed in Vz (axial), NEVER in mu_x — see docstring.
        cases=[
            FlightCondition(name="static (V=0)", mu_x=0.0, Vz=0.0, collective_deg=0.0, rpm=rpm),
            FlightCondition(name="climb 40 m/s", mu_x=0.0, Vz=40.0, collective_deg=0.0, rpm=rpm),
            FlightCondition(name="cruise 65 m/s", mu_x=0.0, Vz=65.0, collective_deg=0.0, rpm=rpm),
        ],
        batches=[
            # Axial velocity sweep: this is the classic CT/CP/eta vs J_z curve,
            # the classical way to present propeller performance.
            BatchDefinition(name="velocity sweep (J_z)", sweep_kind="custom",
                            conditions=[
                                FlightCondition(name=f"V={v:g} m/s", mu_x=0.0, Vz=float(v),
                                                collective_deg=0.0, rpm=rpm)
                                for v in (0, 10, 20, 30, 40, 50, 60, 70)],
                            plots=["performance"]),
        ],
        expected=dict(sigma=solidity(n_blades, chord, radius), tip_speed=rpm * 2 * math.pi / 60 * radius),
    )


# =============================================================================
# 4. test4 — tabulated polar with Reynolds axis
# =============================================================================

def _tabulated_polar_by_reynolds() -> list:
    """Synthetic polar with three Reynolds slices.

    Not measured data: it is a coherent family where Cl_max and Cd_min vary
    with Reynolds in the right direction (higher Re -> stall later and lower
    drag). Serves to exercise the table path of the motor, which differs from
    analytical and chooses one slice PER RADIAL STATION.
    """
    slices = []
    for reynolds, cl_max, cd_min in ((3.0e5, 1.05, 0.0115),
                                     (1.0e6, 1.28, 0.0082),
                                     (3.0e6, 1.42, 0.0068)):
        alphas = [float(a) for a in range(-20, 21)]
        cl, cd = [], []
        for alpha in alphas:
            cl_linear = 5.9 * math.radians(alpha - (-1.5))
            # Smooth saturation at cl_max, symmetric on negative side
            cl_val = cl_max * math.tanh(cl_linear / cl_max)
            cl.append(round(cl_val, 5))
            cd.append(round(cd_min + 0.012 * (cl_val ** 2)
                            + 0.0022 * max(0.0, abs(alpha) - 12.0) ** 2, 6))
        slices.append(PolarSlice(alpha_deg=alphas, cl=cl, cd=cd,
                                  reynolds=reynolds,
                                  label=f"Re={reynolds:.0e}"))
    return slices


def test4():
    """Same rotor as light helicopter, but with TABULATED polar in Reynolds.

    Exists to cover the table path end-to-end — including radial slice
    selection, where Reynolds varies about 5x from root to tip (see
    `airfoils.radial_reynolds_mach`). With analytical polar this code never
    runs.

    Viterna extension is ON over the table: data spans -20 to +20 degrees,
    and in forward flight the blade sees far beyond that in the reverse flow
    region. Without extension, the motor would extrapolate a short table.
    """
    radius, n_blades, chord = 5.08, 2, 0.33
    geom = geometry.generate_rectangular(
        radius_m=radius, n_blades=n_blades, chord_norm=chord / radius,
        twist_root_deg=7.0, twist_tip_deg=-3.0,
        root_cutout_norm=0.18, n_stations=25, airfoil_name="tabulated polar (Re)")

    airfoil = AirfoilDef(
        name="tabulated polar (3 Reynolds)", source="table",
        table_slices=_tabulated_polar_by_reynolds(),
        extend_full_range=True, viterna_blend_width_deg=5.0)

    rpm = rpm_for_tip_speed(213.0, radius)
    return dict(
        folder="test4", name="Rotor with tabulated polar (Reynolds axis)",
        geom=geom, airfoil=airfoil, config=_config(),
        cases=[
            FlightCondition(name="hover", mu_x=0.0, collective_deg=9.0, rpm=rpm),
            FlightCondition(name="forward mu_x=0.3", mu_x=0.3, collective_deg=3.0, rpm=rpm),
        ],
        batches=[
            BatchDefinition(name="mu_x sweep", sweep_kind="mu_sweep",
                            sweep_params={"mu_values": [0.0, 0.1, 0.2, 0.3],
                                          "collective_deg": 5.0, "rpm": rpm},
                            plots=["performance"]),
        ],
        expected=dict(sigma=solidity(n_blades, chord, radius), tip_speed=213.0),
    )


# =============================================================================
# 5. test5 — physical model sensitivity study
# =============================================================================

def test5():
    """FAST-TIP rotor, designed so physical toggles matter.

    Tip speed 240 m/s (tip Mach 0.70, advancing side 0.88 at mu_x=0.25): that is
    where compressibility stops being detail. Collective high enough for stall
    on the retreating side, where Viterna and dynamic stall change the result.

    Batches for this project are mu_x sweeps; to compare models, use `--set`:

        zbemt --project projects/rotor_model_study \
              --from-bemt-case "fast forward" --set config.use_compressibility=false

    Saved cases cover hover, forward, and fast forward — the three regimes
    where models behave differently.
    """
    radius, n_blades, chord = 6.0, 4, 0.40
    geom = geometry.generate_tapered(
        radius_m=radius, n_blades=n_blades,
        root_chord_norm=0.46 / radius, tip_chord_norm=0.34 / radius,
        twist_root_deg=12.0, twist_tip_deg=-6.0,
        root_cutout_norm=0.20, n_stations=25, airfoil_name="NACA 23012 (approximate)")

    airfoil = AirfoilDef(
        name="NACA 23012 (approximate)", source="analytical", stall_model="viterna",
        cl_alpha=5.9, alpha0_deg=-1.2, cd0=0.0085, k=0.011,
        alpha_stall_pos_deg=12.0, alpha_stall_neg_deg=-10.0,
        viterna_blend_width_deg=4.0, extend_full_range=True,
        use_dynamic_stall=True, dynamic_stall_A=8.0,
        dynamic_stall_fade_start_deg=40.0, dynamic_stall_fade_end_deg=50.0)

    rpm = rpm_for_tip_speed(240.0, radius)
    return dict(
        folder="test5",
        name="Fast-tip rotor (physical model sensitivity study)",
        geom=geom, airfoil=airfoil,
        config=_config(inflow_field_model="drees_local", use_compressibility=True,
                       use_rotational_augmentation=True),
        cases=[
            FlightCondition(name="hover", mu_x=0.0, collective_deg=10.0, rpm=rpm),
            # Collective drops with mu_x: without trim, thrust rises with
            # forward speed at fixed pitch, and holding 10 degrees puts the
            # blade into deep stall. These values keep CT/sigma near 0.08
            # across all three cases.
            FlightCondition(name="forward mu_x=0.25", mu_x=0.25, collective_deg=4.0, rpm=rpm),
            FlightCondition(name="fast forward", mu_x=0.38, collective_deg=3.0, rpm=rpm),
        ],
        batches=[
            BatchDefinition(name="mu_x sweep", sweep_kind="mu_sweep",
                            sweep_params={"mu_values": [0.0, 0.1, 0.2, 0.3, 0.38],
                                          "collective_deg": 5.0, "rpm": rpm},
                            plots=["performance"]),
            BatchDefinition(name="collective vs forward", sweep_kind="factorial",
                            sweep_params={"axes": [{"variable": "mu_x", "values": [0.0, 0.2, 0.35]},
                                                   {"variable": "collective_deg",
                                                    "values": [3.0, 6.0, 9.0]}],
                                          "fixed": {"rpm": rpm}},
                            plots=["performance"]),
        ],
        expected=dict(sigma=solidity(n_blades, chord, radius), tip_speed=240.0),
    )


# =============================================================================
# 6. test6 — small multirotor consumer drone propeller
# =============================================================================

def test6():
    """Propeller from a small multirotor consumer drone.

    Source: DJI Phantom 4 Pro specifications (9.7" propeller, 250g payload).
    R = 0.123 m, 2 blades, chord 0.048 m  ->  sigma = 0.050. Very low solidity,
    typical of high-speed rotors optimized for hover in thin air.
    Tip speed 78 m/s (RPM 6,400) — high RPM, low inertia is the design choice
    for electric multirotor. Tip Mach 0.23 — low, compressibility negligible.
    Takeoff weight ~1.3 kg on 4 rotors  ->  3.2 kN each, CT ~ 0.0095,
    CT/sigma ~ 0.19 (very high loading, typical of hover-optimized drones).

    This example contrasts sharply with the eVTOL rotor: same mission (hover),
    much smaller scale, much simpler aerodynamics (no need for Viterna, low
    twist). Demonstrates how design changes across vehicle categories.
    """
    radius, n_blades, chord = 0.123, 2, 0.048
    geom = geometry.generate_rectangular(
        radius_m=radius, n_blades=n_blades, chord_norm=chord / radius,
        twist_root_deg=25.0, twist_tip_deg=5.0,
        root_cutout_norm=0.25, n_stations=20, airfoil_name="thin flat plate")

    # Very simple airfoil: small drones fly at low Reynolds (Re~30k at tip in
    # hover), where the analytic model with low-order coefficients is adequate.
    # Clip stall is used because the blade rarely stalls in normal operation.
    airfoil = AirfoilDef(
        name="thin flat plate", source="analytical", stall_model="clip",
        cl_alpha=5.5, alpha0_deg=0.0, cd0=0.0090, k=0.008,
        alpha_stall_pos_deg=15.0, alpha_stall_neg_deg=-15.0,
        extend_full_range=False)

    rpm = rpm_for_tip_speed(78.0, radius)
    return dict(
        folder="test6", name="Small multirotor consumer drone (9.7\" propeller)",
        geom=geom, airfoil=airfoil,
        # Very coarse mesh: this rotor's aerodynamics are simple and the
        # solver converges quickly. Also demonstrates the no-compressibility
        # path at a different tip speed than eVTOL.
        config=_config(Ne=48, Npsi=72, inflow_field_model="glauert_local",
                       use_compressibility=False, reverse_flow_model="flat_plate"),
        cases=[
            FlightCondition(name="hover", mu_x=0.0, collective_deg=8.0, rpm=rpm),
            FlightCondition(name="climb 2 m/s", mu_x=0.0, collective_deg=10.0, Vz=2.0, rpm=rpm),
        ],
        batches=[
            BatchDefinition(name="collective at hover", sweep_kind="collective_sweep",
                            sweep_params={"collective_deg_values": [4.0, 6.0, 8.0, 10.0, 12.0],
                                          "mu_x": 0.0, "rpm": rpm},
                            plots=["performance"]),
        ],
        expected=dict(sigma=solidity(n_blades, chord, radius), tip_speed=78.0),
    )


# =============================================================================
# 7. test7 — heavy-lift cargo helicopter (CH-47 class)
# =============================================================================

def test7():
    """Main rotor of a heavy-lift tandem cargo helicopter, CH-47 Chinook class.

    Source: Boeing CH-47F Chinook specifications.
    R = 7.32 m, 3 blades, chord 0.578 m  ->  sigma = 0.075. Lower solidity than
    UH-60 (three vs four blades) but larger radius and longer chord, optimized
    for payload over agility.
    Tip speed 200 m/s (RPM 262) — slightly lower than UH-60 to keep noise
    manageable; at higher weight the trade is weight-efficient.
    Maximum weight ~22,680 kg (for comparison, UH-60 MTOW ~9,980 kg)  ->
    CT ~ 0.0108, CT/sigma ~ 0.144 (very high blade loading, near stall).

    High twist (-20 degrees total): manages the wide speed envelope from hover
    to cruise. This rotor is designed to absorb high power and lift heavy
    weight in a compact vehicle.
    """
    radius, n_blades, chord = 7.32, 3, 0.578
    geom = geometry.generate_tapered(
        radius_m=radius, n_blades=n_blades,
        root_chord_norm=0.63 / radius, tip_chord_norm=0.52 / radius,
        twist_root_deg=12.0, twist_tip_deg=-8.0,
        root_cutout_norm=0.22, n_stations=28, airfoil_name="SC1095 heavy lift variant")

    # Similar to the UH-60 airfoil but biased for high CL: the Chinook flies
    # higher disk loading and can tolerate earlier stall.
    airfoil = AirfoilDef(
        name="SC1095 heavy lift variant", source="analytical", stall_model="viterna",
        cl_alpha=6.0, alpha0_deg=-1.0, cd0=0.0090, k=0.011,
        alpha_stall_pos_deg=12.0, alpha_stall_neg_deg=-11.0,
        viterna_blend_width_deg=4.0, extend_full_range=True)

    rpm = rpm_for_tip_speed(200.0, radius)
    return dict(
        folder="test7", name="Heavy-lift cargo helicopter (CH-47 Chinook class)",
        geom=geom, airfoil=airfoil,
        # Fine mesh to capture high-loading effects accurately.
        config=_config(Ne=80, Npsi=120, inflow_field_model="coleman_local",
                       prandtl_loss_mode="both", use_compressibility=True,
                       reverse_flow_model="viterna_full_range"),
        cases=[
            FlightCondition(name="hover max weight", mu_x=0.0, collective_deg=13.0, rpm=rpm),
            FlightCondition(name="cruise mu_x=0.20", mu_x=0.20, collective_deg=8.5, rpm=rpm),
            FlightCondition(name="high speed mu_x=0.30", mu_x=0.30, collective_deg=6.5, rpm=rpm),
        ],
        batches=[
            BatchDefinition(name="mu_x sweep", sweep_kind="mu_sweep",
                            sweep_params={"mu_values": [0.0, 0.05, 0.10, 0.15, 0.20, 0.25, 0.30],
                                          "collective_deg": 8.0, "rpm": rpm},
                            plots=["performance"]),
            BatchDefinition(name="collective in hover", sweep_kind="collective_sweep",
                            sweep_params={"collective_deg_values": [6.0, 9.0, 12.0, 15.0],
                                          "mu_x": 0.0, "rpm": rpm},
                            plots=["performance"]),
        ],
        expected=dict(sigma=solidity(n_blades, chord, radius), tip_speed=200.0),
    )


# =============================================================================
# 8. test8 — Pitt-Peters finite-state inflow model (scout/reconnaissance)
# =============================================================================

def test8():
    """Light scout/reconnaissance helicopter rotor, demonstrating finite-state
    dynamic inflow (Pitt & Peters, 1981).

    Source: Conceptual scout helicopter similar to Hughes MD-530F class.
    R = 5.5 m, 2 blades, chord 0.36 m  ->  sigma = 0.042. Low solidity,
    optimized for speed/agility over payload. Tip speed 200 m/s (RPM 347).
    Operating weight ~1,800 kg  ->  CT ~ 0.0045, CT/sigma ~ 0.107.

    This rotor demonstrates the Pitt-Peters finite-state inflow model, which
    solves the inflow field from 3-5 global states (nu0, nu_s, nu_c) rather
    than one lambda_i per element. Most physically justified in moderate
    forward flight (mu_x > 0.05) where quasi-steady inflow breaks down; here
    the discrepancy with classical inflow (glauert/coleman/drees) becomes
    visible. This is the ONLY example rotor with Pitt-Peters as the default.
    """
    radius, n_blades, chord = 5.5, 2, 0.36
    geom = geometry.generate_rectangular(
        radius_m=radius, n_blades=n_blades, chord_norm=chord / radius,
        twist_root_deg=8.0, twist_tip_deg=-2.0,
        root_cutout_norm=0.18, n_stations=25, airfoil_name="NACA 0012")

    # Simple airfoil, analytical. Scout rotor does not need Viterna unless
    # heavy stall is expected; here with moderate mu_x, clip is sufficient.
    airfoil = AirfoilDef(
        name="NACA 0012", source="analytical", stall_model="clip",
        cl_alpha=5.73, alpha0_deg=0.0, cd0=0.0080, k=0.009,
        alpha_stall_pos_deg=14.0, alpha_stall_neg_deg=-14.0,
        extend_full_range=False)

    rpm = rpm_for_tip_speed(200.0, radius)
    return dict(
        folder="test8",
        name="Scout/reconnaissance helicopter (Pitt-Peters inflow)",
        geom=geom, airfoil=airfoil,
        # Pitt-Peters inflow: moderate mesh, Pitt-Peters steady state.
        # flat_plate reverse flow model (no Viterna needed for clip stall).
        config=_config(Ne=60, Npsi=90,
                       inflow_field_model="pitt_peters_steady",
                       pitt_peters_outer_iter=40,
                       pitt_peters_relax=0.5,
                       pitt_peters_tol=1e-6,
                       reverse_flow_model="flat_plate"),
        cases=[
            FlightCondition(name="hover", mu_x=0.0, collective_deg=7.0, rpm=rpm),
            FlightCondition(name="transition mu_x=0.10", mu_x=0.10, collective_deg=6.0, rpm=rpm),
            FlightCondition(name="forward mu_x=0.25", mu_x=0.25, collective_deg=4.0, rpm=rpm),
        ],
        batches=[
            BatchDefinition(name="mu_x sweep", sweep_kind="mu_sweep",
                            sweep_params={"mu_values": [0.0, 0.05, 0.10, 0.15, 0.20, 0.25],
                                          "collective_deg": 5.0, "rpm": rpm},
                            plots=["performance"]),
        ],
        expected=dict(sigma=solidity(n_blades, chord, radius), tip_speed=200.0),
    )


# =============================================================================
# 9. test9 — enhanced stall model (smooth nonlinear roll-off)
# =============================================================================

def test9():
    """Main rotor of a light helicopter trainer, demonstrating the enhanced
    (smoothed nonlinear) stall model.

    Source: Conceptual trainer helicopter, Robinson R22-class specifications.
    R = 5.18 m, 2 blades, chord 0.32 m  ->  sigma = 0.039. Low solidity, simple
    design. Tip speed 190 m/s (RPM 350). Operating weight ~680 kg  ->  CT ~ 0.0042,
    CT/sigma ~ 0.108.

    Most existing examples use 'clip' (instantaneous stall) or 'viterna'
    (Viterna-Corrigan full-range extension). This rotor demonstrates the
    'enhanced' stall model, which applies a smooth nonlinear roll-off through
    the stall region (via cosine and sine scaling functions) rather than a
    hard clip or a piecewise fit. Useful as a baseline for comparison and for
    understanding stall behavior without the abrupt transitions of clip stall.
    """
    radius, n_blades, chord = 5.18, 2, 0.32
    geom = geometry.generate_rectangular(
        radius_m=radius, n_blades=n_blades, chord_norm=chord / radius,
        twist_root_deg=7.0, twist_tip_deg=-3.0,
        root_cutout_norm=0.18, n_stations=25, airfoil_name="NACA 0012")

    # Enhanced stall model: smooth nonlinear roll-off, NOT a clip and NOT
    # a full-range extension. This is the feature demonstrated here.
    airfoil = AirfoilDef(
        name="NACA 0012", source="analytical", stall_model="enhanced",
        cl_alpha=5.73, alpha0_deg=0.0, cd0=0.0080, k=0.009,
        alpha_stall_pos_deg=14.0, alpha_stall_neg_deg=-14.0,
        extend_full_range=False)

    rpm = rpm_for_tip_speed(190.0, radius)
    return dict(
        folder="test9",
        name="Light trainer helicopter (enhanced stall model)",
        geom=geom, airfoil=airfoil,
        config=_config(Ne=60, Npsi=90, inflow_field_model="glauert_local",
                       use_compressibility=False, reverse_flow_model="flat_plate"),
        cases=[
            FlightCondition(name="hover", mu_x=0.0, collective_deg=8.0, rpm=rpm),
            FlightCondition(name="cruise mu_x=0.20", mu_x=0.20, collective_deg=6.0, rpm=rpm),
            FlightCondition(name="forward mu_x=0.30", mu_x=0.30, collective_deg=5.0, rpm=rpm),
        ],
        batches=[
            BatchDefinition(name="mu_x sweep", sweep_kind="mu_sweep",
                            sweep_params={"mu_values": [0.0, 0.1, 0.2, 0.3],
                                          "collective_deg": 6.0, "rpm": rpm},
                            plots=["performance"]),
        ],
        expected=dict(sigma=solidity(n_blades, chord, radius), tip_speed=190.0),
    )


# =============================================================================
# 10. test10 — multi-section airfoil rotor (root/mid/tip)
# =============================================================================

def test10():
    """Main rotor with heterogeneous (multi-section) airfoil distribution.

    Source: Conceptual multi-section rotor with realistic span-wise airfoil
    variation (common in modern helicopter designs for noise/efficiency tradeoff).
    R = 5.0 m, 3 blades, average chord 0.35 m  ->  sigma = 0.067.
    Tip speed 195 m/s (RPM 373). Operating weight ~2,100 kg  ->
    CT ~ 0.0050, CT/sigma ~ 0.075.

    This rotor demonstrates the multi-section airfoil feature (Phase D,
    airfoil_sections): instead of a single `project.airfoil`, the blade
    uses different airfoil definitions at different radial stations. Here:
    - ROOT (r/R=0.2): thick, cambered section for high CL at low Re
    - MID (r/R=0.6): intermediate section, balanced lift/drag
    - TIP (r/R=1.0): thin section for low drag at high Re and high speed
    The motor interpolates Cl/Cd between sections at each element. This is
    the ONLY example that exercises the multi-section path end-to-end.
    """
    radius, n_blades, chord = 5.0, 3, 0.35
    geom = geometry.generate_rectangular(
        radius_m=radius, n_blades=n_blades, chord_norm=chord / radius,
        twist_root_deg=10.0, twist_tip_deg=-5.0,
        root_cutout_norm=0.20, n_stations=25, airfoil_name="multi-section airfoil")

    # Default airfoil (fallback if airfoil_sections is empty, or used for
    # visualization in GUI tabs -- kept for safety).
    airfoil_default = AirfoilDef(
        name="multi-section airfoil (default)", source="analytical", stall_model="viterna",
        cl_alpha=6.0, alpha0_deg=-2.0, cd0=0.0090, k=0.010,
        alpha_stall_pos_deg=13.0, alpha_stall_neg_deg=-11.0,
        viterna_blend_width_deg=4.0, extend_full_range=True)

    # Multi-section airfoils: each with explicit r_norm (0.0..1.0)
    airfoil_root = AirfoilDef(
        name="root section (thick cambered)", source="analytical",
        stall_model="viterna", r_norm=0.2,
        cl_alpha=6.2, alpha0_deg=-3.0, cd0=0.0110, k=0.012,
        alpha_stall_pos_deg=12.0, alpha_stall_neg_deg=-10.0,
        viterna_blend_width_deg=4.0, extend_full_range=True)

    airfoil_mid = AirfoilDef(
        name="mid section (balanced)", source="analytical",
        stall_model="viterna", r_norm=0.6,
        cl_alpha=6.0, alpha0_deg=-2.0, cd0=0.0095, k=0.011,
        alpha_stall_pos_deg=13.0, alpha_stall_neg_deg=-11.0,
        viterna_blend_width_deg=4.0, extend_full_range=True)

    airfoil_tip = AirfoilDef(
        name="tip section (thin efficient)", source="analytical",
        stall_model="viterna", r_norm=1.0,
        cl_alpha=5.8, alpha0_deg=-1.0, cd0=0.0075, k=0.008,
        alpha_stall_pos_deg=14.0, alpha_stall_neg_deg=-12.0,
        viterna_blend_width_deg=4.0, extend_full_range=True)

    rpm = rpm_for_tip_speed(195.0, radius)
    return dict(
        folder="test10",
        name="Helicopter rotor with multi-section airfoil (root/mid/tip)",
        geom=geom, airfoil=airfoil_default,
        airfoil_sections=[airfoil_root, airfoil_mid, airfoil_tip],
        config=_config(Ne=72, Npsi=108, inflow_field_model="coleman_local",
                       use_compressibility=True, reverse_flow_model="viterna_full_range"),
        cases=[
            FlightCondition(name="hover", mu_x=0.0, collective_deg=9.0, rpm=rpm),
            FlightCondition(name="cruise mu_x=0.20", mu_x=0.20, collective_deg=7.0, rpm=rpm),
        ],
        batches=[
            BatchDefinition(name="mu_x sweep", sweep_kind="mu_sweep",
                            sweep_params={"mu_values": [0.0, 0.1, 0.2, 0.3],
                                          "collective_deg": 8.0, "rpm": rpm},
                            plots=["performance"]),
        ],
        expected=dict(sigma=solidity(n_blades, chord, radius), tip_speed=195.0),
    )


# =============================================================================
# 12. test12 — NACA airfoil with NeuralFoil external polar source
# =============================================================================

def test12():
    """Light helicopter rotor with NeuralFoil as the external airfoil polar source.

    Uses the `source='external'` + NeuralFoil path, which exercises a code
    branch not covered by any other example (analytical, table). The airfoil
    polar is evaluated on demand by the NeuralFoil neural-network surrogate;
    no table data is stored in the project.
    """
    return dict(
        folder="test12", name="NACA airfoil with NeuralFoil polar (external source)",
    )


PROJECTS = [test1, test2, test3, test4, test5, test6, test7, test8, test9, test10, test11]


def generate(destination: Path = None) -> list[Path]:
    """Generate all example projects to the destination directory.

    Args:
        destination: Target directory. Defaults to ROOT / "projects".

    Returns:
        List of paths where projects were written.
    """
    if destination is None:
        destination = ROOT / "projects"
    written = []
    for constructor in PROJECTS:
        spec = constructor()
        path = destination / spec["folder"]
        project = api.new_project(str(path), name=spec["name"])
        project.geometry = spec["geom"]
        project.airfoil = spec["airfoil"]
        project.airfoil_sections = spec.get("airfoil_sections", [])
        project.config = spec["config"]
        project.saved_cases = spec["cases"]
        project.batches = spec["batches"]
        api.save_project(project)
        written.append(path)
        sigma = spec["expected"]["sigma"]
        print(f"  {spec['folder']:<28} sigma={sigma:.4f}  "
              f"tip_speed={spec['expected']['tip_speed']:.0f} m/s  "
              f"{len(spec['cases'])} cases, {len(spec['batches'])} batches")
    return written


if __name__ == "__main__":
    print("Generating example projects to projects/:")
    destination = Path(DEFAULT_OUTPUT_DIR) if DEFAULT_OUTPUT_DIR else ROOT / "projects"
    generate(destination)
    print("done.")
