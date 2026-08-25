"""Vectorized Blade Element Momentum Theory engine for rotors and propellers.

Purpose and objectives:
    Solve blade-element and momentum cases on a radial-azimuthal mesh,
    aggregate loads, and expose convergence data. This module is the physics
    layer. Therefore, it does not parse projects and it does not write files.

Inputs and outputs:
    Inputs are ``Rotor`` geometry and airfoil objects, ``BEMTConfig`` settings,
    and a flight condition. Outputs are element-state arrays, converged
    ``Results``, load coefficients, and optional solver history. Inputs use SI
    units and disk axes: ``mu_x`` is in-plane and ``Vz`` is along the shaft.

Public operations:
    - ``solve_bemt`` solves a case.
    - ``element_state`` evaluates the local quantities.
    - ``aggregate_results`` integrates the loads.
    - The solver helpers implement the configured numerical methods.

Conventions, limitations, and interactions:
    Code outside this module applies the rotor and propeller display labels.
    The model is quasi-steady, except for the dynamic-stall and time-marching
    options that you configure explicitly. It uses annular momentum theory.
    Therefore, it needs external validation in a strongly separated or highly
    unsteady regime. The neighboring modules are these:

    - ``models.py`` supplies the data.
    - ``airfoils.py`` supplies the polars.
    - ``studies.py`` prepares the cases.
    - ``api.py`` is the execution boundary for the GUI and the CLI.

The following notes define the numerical formulation implemented below.

--------------------------------------------------------------------------------
CORE IDEA OF BEMT
--------------------------------------------------------------------------------
The blade is discretized into Ne radial stations x Npsi azimuthal stations.
In each element (r,psi), two independent theories describe the same
aerodynamic load. The solver equates them to find the induced velocity:

  (1) Blade element theory. This computes the load directly from the local
      flow at the airfoil, using the angle of attack and the Cl and Cd from
      the airfoil polar. See `element_state`.
  (2) Momentum theory, applied to an elemental ring of the disk: the change
      in momentum of the air crossing that ring requires a certain induced
      velocity (lambda_i) to sustain the load computed in (1).

The coupling between the two is a fixed-point equation in lambda_i (the
induced velocity, non-dimensionalized by Omega*R): lambda_i = g(lambda_i),
solved numerically per element (Section 5, "ITERATIVE SOLVERS").

--------------------------------------------------------------------------------
ARCHITECTURE: FULL VECTORIZATION
--------------------------------------------------------------------------------
The fixed-point equation of each element (r,psi) is mathematically
independent of its neighbors. There is no spatial coupling within the
iteration. Coupling between elements exists only in the 'global' and
'pitt_peters' inflow modes, which solve a small number of global degrees of
freedom instead of one lambda_i per element. Because of this,
`element_state()` evaluates ALL Ne x Npsi elements at once with NumPy
operations, and each "solver iteration" is a single vectorized pass over
the entire mesh (typically 5 to 30 iterations to convergence, not thousands).

--------------------------------------------------------------------------------
AVAILABLE ITERATIVE METHODS (`BEMTConfig.solver`)
--------------------------------------------------------------------------------
  - 'fixed_point' : Picard iteration with relaxation. This is the simplest
                     and most robust method. However, it is the slowest to
                     converge.
  - 'newton'       : vectorized Newton-Raphson with numerical Jacobian
                      (central difference). Convergence is approximately
                      quadratic near the root. This is the default method.
  - 'bisection'    : vectorized bisection. It needs no derivative. The
                      solver uses it as a fallback in regions where
                      g(lambda)-lambda is not monotonic (post-stall).
  - 'aitken'       : Picard accelerated by Aitken Delta^2 extrapolation, a
                      good cost/robustness compromise.

An important numerical-correctness criterion: the convergence test is
always performed on the TRUE RESIDUAL g(lambda)-lambda (pre-relaxation),
never on the already-relaxed step . Near the root/tip/azimuth crossing the
relaxation factor drops significantly (see `_relax_map`), and testing the
relaxed step would give false convergence positives exactly where
convergence is hardest.

--------------------------------------------------------------------------------
OPTIONAL PHYSICAL MODELS (turned on/off via `BEMTConfig`)
--------------------------------------------------------------------------------
Each model below is detailed in the corresponding code block. Here is just
a map of where to find each one.

  a) `reverse_flow_model='thin_plate_blend'` . Reverse flow (Ut<0, the
     region where the blade "walks backwards" relative to the air, common
     on the retreating blade in forward flight) modeled by thin flat-plate
     theory (Cl=pi*sin(a)*cos(a), Cd=2*sin(a)^2), smoothly blended
     (smoothstep) with the direct airfoil polar. See Section 4
     (`element_state`). Other options: 'simple_flip', 'flat_plate'
     (fixed Cd=1.9 in reverse flow, with a discontinuity at Ut=0) and
     'alpha_blending'.

  a2) `reverse_flow_model='viterna_full_range'` . "industry standard"
     alternative (AeroDyn/OpenFAST, QBlade) to the previous ones: instead
     of blending two aerodynamic models near Ut=0, the airfoil's own
     Cl(alpha)/Cd(alpha) polar is extended continuously to -180..+180
     degrees via Viterna-Corrigan (`ViternaExtendedAirfoil`, Section 1b), and
     phi=atan2(Up,Ut) is used directly (no "reverse" branch) . Eliminates
     any Cl/Cd/force discontinuity at the reverse-flow boundary. Requires
     `airfoil` to be a `ViternaExtendedAirfoil`.

  b) `use_rotational_augmentation=True` . Himmelskamp effect / Snel
     correction: Cl increase near the root from centrifugal pumping and
     Coriolis force in the boundary layer, which delay separation. See
     Section 4.

  c) `use_radial_flow_correction=True` . Radial flow correction /
     "independence principle": in forward flight the spanwise (radial)
     flow component reduces the effective Cd . Zero at psi=90/270 deg,
     maximum at psi=0/180 deg.
     See Section 4.

  d) `inflow_field_model='pitt_peters_steady'` . Finite-state dynamic
     inflow (Pitt & Peters, 1981), which solves the induced velocity field
     from just 3 global degrees of freedom (nu0, nu_s, nu_c) instead of one
     lambda_i per element. See Section 6b.

  e) `geometry.dynamics` -- rigid-blade flapping and lead-lag (SC-11).
     The blade stays rigid; it gains rigid-body freedoms about a flap
     hinge (and optionally a lag hinge) with an offset and/or root
     springs. The response is periodic in azimuth and quasi-steady,
     solved by harmonic balance over N_h harmonics: see Section 4h
     (`solve_bemt_flapping`, `solve_blade_motion`). A resonant harmonic
     denominator is rejected by name (EN-8). The default remains the
     fully rigid disk of every project saved before this model existed.

  f) `use_dynamic_stall=True` . Øye dynamic stall (Øye, 1991): models the
     boundary-layer separation lag when the angle of attack varies fast
     with azimuth, via a 1st-order ODE on a separation function f. See
     Section 4g.

  g) `cfg.is_propeller` + `resolve_advance_velocity`/`solve_bemt_flight` --
     allows specifying the flight condition and reporting T/Q/P both in the
     classic helicopter-rotor convention (mu_x, CT/CQ/CP in
     rho*A*(Omega*R)^n) and in the classic airplane-propeller convention
     (J_x, CT_prop/CQ_prop/CP_prop in rho*n^2*D^4 and so on) . The solving
     engine (`solve_bemt`) is agnostic to this choice, which only affects
     the input/output non-dimensionalization. See Section 6c.

================================================================================
"""

from __future__ import annotations

import time
import warnings
from dataclasses import dataclass, field, replace, asdict
from typing import Optional, Callable

import numpy as np
import pandas as pd
from scipy.interpolate import interp1d
from scipy.linalg import expm

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

# Compat: numpy >=2.0 renamed trapz -> trapezoid (and drops trapz in
# recent versions). numpy <2.0 only has trapz. This keeps the code portable.
_trapz = getattr(np, "trapezoid", None) or np.trapz


def _trapz_psi_periodic(f_psi: np.ndarray, psi_nodes: np.ndarray) -> float:
    """Trapezoid rule for azimuthal integration around the WHOLE disk (0 to
    2*pi), treating the domain as PERIODIC.

    `psi_nodes` (see `_pitt_peters_geometry`/`solve_bemt`) covers
    [0, 2*pi*(1-1/Npsi)]. That is, it does NOT repeat the psi=0 node at
    psi=2*pi (on purpose: avoids the duplicate element that would count
    the same azimuthal station twice). But the plain (non-periodic)
    `_trapz` does not know this: it integrates only up to the last node and
    silently OMITS the closing panel between psi_nodes[-1] and 2*pi (==
    psi=0 on the next revolution) . A systematic bias of ~1/Npsi in EVERY
    disk integral (CT, CQ, Mx, My, ...), and it is exactly the same
    geometric "hole" that shows up as a blank wedge in the contour plot
    (see `build_disk_grid` / `plot_disk_map`).

    Fix: add the missing closing panel, (f[-1]+f[0])/2 * d_psi_closing --
    a NEW panel, between the last sampled point and the first point of
    "the next revolution". No data is counted twice. For the uniform grid
    used in this module, this is exactly equivalent to the rectangle rule
    (plain sum * 2*pi/Npsi), the correct periodic quadrature for an
    equally-spaced mesh."""
    d_close = (2.0 * np.pi) - float(psi_nodes[-1] - psi_nodes[0])
    closing_panel = 0.5 * (f_psi[..., -1] + f_psi[..., 0]) * d_close
    return _trapz(f_psi, psi_nodes, axis=-1) + closing_panel


# =============================================================================
# 0. CENTRAL SOLVER CONFIGURATION . ALL PHYSICAL MODEL VARIABLES
#    (ON/OFF), RIGHT AT THE START OF THE FILE
# =============================================================================
#
# Every optional physical model in this code is controlled by a field of
# this class, with the physics of each one documented in detail in the
# corresponding code block (numbered sections below) and in the file
# `zBEMT.md`. Keeping all variables concentrated here (instead of
# scattered/hard-coded in the middle of the logic) makes any combination of
# models reproducible from a single `BEMTConfig` object.

#
# ORGANIZATION OF THIS BLOCK (in this order):
#   1) Mesh and general physical conditions (Ne, Npsi, rho, a_sound)
#   2) Rotor/propeller mode and non-dimensionalization (mu_x vs J_x) . See
#      Section 6c
#   3) Linear inflow model + coupling (glauert/coleman/drees, local/
#      global/pitt_peters) , see Section 4d
#   4) Prandtl tip/root loss
#   5) Compressibility (Prandtl-Glauert)
#   6) Reverse flow model , see Section 4b
#   7) Himmelskamp/Snel rotational correction , see Section 4c
#   8) Radial flow correction (independence principle, ISAE) , see Section 4f
#   9) Pitt-Peters dynamic inflow (finite-state) , see Section 4d/6b
#  10) Øye dynamic stall , see Section 4g
#  11) Parameters of the iterative lambda_i solver(s) (not strictly
#      "physical models", but also kept here since they are equally
#      configurable via a variable, never hard-coded in the middle of the
#      code)
#
# Each group below has a "--- Model name (see SectionX) ---" comment right
# above the fields it controls, to make navigation easier.

@dataclass
class BEMTConfig:
    # --- 1) Mesh and general physical conditions ----------------------------
    # Ne/Npsi defaults aligned with zBEMT MATLAB (v30): the reference mesh
    # used in the script (params.Ne/params.Npsi, Section 1) is 120x180 . That
    # is the default here too, to reproduce by default the MATLAB
    # angular/radial resolution instead of a coarser mesh.
    Ne: int = 120                            # number of radial stations
    Npsi: int = 180                          # number of azimuthal stations (psi)
    rho: float = 1.225                       # air density [kg/m^3]
    a_sound: float = 340.294                 # speed of sound [m/s] (for Mach)
    # Kinematic viscosity of air [m^2/s] at sea level, ISA. Used only to
    # estimate the reference Reynolds number that selects the tabulated
    # polar (see `airfoils.reference_reynolds_mach`). It does not enter the
    # flow solution itself.
    nu_air: float = 1.46e-5
    integration_offset: float = 0.005        # offset from r/R=0 and r/R=1 in the mesh (avoids singularities)

    # --- 2) Rotor/propeller mode and non-dimensionalization (Section 6c) -------
    # is_propeller=False (default): ROTOR convention (helicopter/eVTOL on a
    # rotor disk), advance non-dimensionalized by mu_x=Vinf/(Omega*R) and
    # climb/descent by lambda_z=Vz/(Omega*R). is_propeller=True: PROPELLER
    # convention (airplane/eVTOL in cruise flight), advance
    # non-dimensionalized by J_x=Vinf/(n*D) (n in rev/s, D=2R) instead of
    # mu_x. The physics solved is identical in both cases. Only the
    # input/output non-dimensionalization changes (see
    # `resolve_advance_velocity`/`aggregate_results`, Section 6c).
    is_propeller: bool = False

    # --- 3) Inflow field model (Section 4d) --------------------------------------
    # SINGLE FIELD (docs/plano_v2.md Section 3.2), replaces the old
    # `inflow_model` (glauert|coleman|drees) + `inflow_coupling`
    # (local|global|pitt_peters): the combination of harmonic law and
    # coupling strategy never had 3x3=9 valid combinations . Pitt-Peters
    # was always exclusive with the empirical harmonic laws (see
    # `_INFLOW_FIELD_MODELS` right below `_inflow_harmonics`), so the only
    # 8 physically existing combinations become a single enum, and invalid
    # ones (for example "coleman_unsteady", "pitt_peters_coleman") become
    # unrepresentable.
    inflow_field_model: str = "coleman_local"
    # Valid values: glauert_local | glauert_global | coleman_local |
    # coleman_global | drees_local | drees_global | pitt_peters_steady |
    # pitt_peters_unsteady (this last one is not solved by `solve_bemt` --
    # see `run_sweep_unsteady_pitt_peters`).

    # --- 4) Prandtl tip/root loss --------------------------------------------
    # Replaces the old `use_prandtl_loss: bool` (docs/plano.md GUI v3,
    # Phase B): F_tip and F_root were already computed SEPARATELY before
    # multiplying (see block right below `_inflow_harmonics`) . This field
    # only decides which combination to use. Retroactive migration (bool ->
    # str) in studies._migrate_config_dict: True -> "both", False -> "off".
    prandtl_loss_mode: str = "both"   # "off" | "tip" | "root" | "both"

    # --- 5) Compressibility (Prandtl-Glauert correction on Cl/Cd) ----------
    use_compressibility: bool = True

    # --- 6) Reverse flow model (Section 4b) --------------------------------------
    # simple_flip | flat_plate | alpha_blending | thin_plate_blend | viterna_full_range
    # Default 'viterna_full_range' . Requires AirfoilDef.extend_full_range=True
    # (also the default now, see models.py) so the engine receives a
    # ViternaExtendedAirfoil. Continuous path -180..+180 with no "reverse"
    # branch and no blend (see Section 1b/4b above).
    reverse_flow_model: str = "viterna_full_range"
    reverse_flow_blend_factor: float = 5.0
    # --- thin_plate_blend (thin flat-plate theory + continuous blend, see Section 4b) ---
    thin_plate_blend_center_deg: float = 35.0   # |alpha_geom| where the blend is at 50%
    thin_plate_blend_width_deg: float = 20.0    # transition width (edge0=center-w/2, edge1=center+w/2)
    # --- viterna_full_range (Viterna-Corrigan -180..+180 extension, see Section 1b/4b) ---
    # Requires `airfoil` to be a `ViternaExtendedAirfoil` (Cl/Cd already
    # continuous over the full range). phi=atan2(Up,Ut) is used directly,
    # with no "reverse" branch and no blend . The only source of
    # continuity is the polar itself.

    # --- 6b) Reverse-flow masking IN THE PLOTS (does not affect the physics
    # nor the CSV/summary . Only the 2D disk maps in plots.py/GUI). Region
    # with Ut<0 becomes NaN only when drawing (same behavior as zBEMT
    # MATLAB v30, `params.mask_reverse_flow_plots`, Section 1/9): without this
    # the contour plots have very steep transitions/visual artifacts right
    # at the reverse-flow boundary.
    mask_reverse_flow_plots: bool = True

    # --- 7) Himmelskamp/Snel rotational augmentation (root stall delay, Section 4c) ---
    use_rotational_augmentation: bool = False

    # --- 8) Radial flow correction / independence principle (Section 4f, ISAE) ---
    use_radial_flow_correction: bool = False
    radial_flow_max_skew_deg: float = 60.0      # clip on lambda_y to avoid spurious Cd->0

    # --- 8b) Sideslip of the in-plane free stream (SC-14) ------------------------
    # Rotates the in-plane velocity direction by psi_w around the shaft:
    # U_T = Omega*r + V_inf*sin(psi - psi_w), and the radial component
    # carries cos(psi - psi_w). 0 deg reproduces every result computed
    # before this field existed.
    inflow_sideslip_deg: float = 0.0

    # --- 9) Pitt-Peters dynamic inflow (finite-state), see Section 4d/6b --------
    pitt_peters_states: int = 3             # 3 (nu0,nu_s,nu_c) | 5 (+ nu_2s,nu_2c, Peters-He)
    pitt_peters_outer_iter: int = 40
    pitt_peters_relax: float = 0.5
    pitt_peters_tol: float = 1e-6

    # --- 10) Øye dynamic stall (Øye, 1991), see Section 4g -----------------------
    use_dynamic_stall: bool = False
    dynamic_stall_model: str = "oye"        # only model supported for now
    dynamic_stall_method: str = "frequency"  # frequency (no time-march, default) | time_march (dedicated option)
    dynamic_stall_A: float = 8.0            # lag time constant: tau=A*c/(2*Vrel), A~8 (Øye/QBlade)
    dynamic_stall_fade_start_deg: float = 40.0  # |alpha_eff| where the correction starts fading out
    dynamic_stall_fade_end_deg: float = 50.0    # |alpha_eff| where the correction is 100% off (back to the static polar)
    dynamic_stall_f_reg: float = 1e-3       # regularization of (1-f_st) in the Cl_sep computation near f_st->1
    # --- only used if dynamic_stall_method='time_march' ---
    dynamic_stall_time_march_revolutions: int = 8   # number of revolutions marched over psi
    dynamic_stall_time_march_avg_last: int = 3      # how many of the last revolutions enter the final average (periodic regime)

    # --- 11) Parameters of the iterative lambda_i solver ---------------------
    solver: str = "newton"                  # fixed_point | newton | bisection | aitken
    max_iter: int = 200
    tol: float = 1e-7
    relax: float = 0.4
    relax_schedule: bool = True
    relax_root_factor: float = 0.25
    relax_root_threshold: float = 0.3
    relax_tip_threshold: float = 0.93
    relax_azimuth_factor: float = 0.5
    relax_azimuth_threshold: float = 0.3

    # Default True: the cost is TWO scalars per solver iteration (typically
    # 5-30 iterations), not one array per element . On the order of tens
    # of floats per solve, invisible next to the Ne*Npsi maps. With False,
    # `maps["frac_converged_history"]`/`residual_history` came out as EMPTY
    # LISTS and the report's (and Results tab's) convergence plot rendered
    # blank, with no error at all . An empty plot reads as "the solver did
    # not converge", which is the opposite of what actually happened.
    collect_history: bool = True
    early_exit_fraction: float = 0.999
    stagnation_patience: int = 15
    stagnation_min_frac: float = 0.95
    # Early-exit criteria for the vectorized loop. Reason: a tiny fraction
    # (typically <0.5%) of elements located exactly on the reverse-flow
    # boundary (Ut ~ 0) may never reach `tol` because the Cl/Cd model has a
    # very steep (or discontinuous, in the 'flat_plate' case) transition
    # there . A problem with the model's PHYSICS, not the solver. Without
    # this cutoff, the vectorized loop runs to max_iter EVERY time (since
    # "all converged" is never satisfied), spending ~30x more evaluations
    # for zero gain in T, Q, and so on (those elements have low W and contribute
    # almost nothing to the load integral). `early_exit_fraction` cuts off
    # once almost everything has converged. `stagnation_patience` cuts off
    # if the converged fraction does not improve for N consecutive
    # iterations (even below target), provided at least
    # `stagnation_min_frac` has already been reached.


# =============================================================================
# 0b. EXECUTION PLAN . WHICH SWEEPS/DEMOS TO RUN
# =============================================================================
#
# The `if __name__ == "__main__":` block (end of file, Section 11) is split into
# 10 independent numbered blocks . Each one demonstrates/validates ONE
# specific model or solver behavior (solver benchmark, mu_x sweep, reverse
# flow, Snel, radial flow, steady and unsteady Pitt-Peters, Øye dynamic
# stall, and the rotor<->propeller identities). Each block sets up its own
# `BEMTConfig` and runs in seconds to minutes. To avoid forcing a run of
# EVERYTHING every time you just want to test one thing (for example, iterating
# quickly on just dynamic stall alone), each block is guarded by a boolean
# field of this class. Just edit `RUN_PLAN` right below (or instantiate
# `RunPlan(run_09_dynamic_stall=True, ...)` with the rest set to False) to
# choose what runs on a call to `python zBEMT.py`.
#
# The "sweeps" themselves (the LISTS of mu_x/alpha/J_x swept in each block)
# are also centralized here, not scattered/hard-coded in the middle of the
# logic . Editing a sweep's grid means editing only one field here.

@dataclass
class RunPlan:
    # --- on/off switch for each __main__ demo block -------------------------
    run_01_solver_benchmark: bool = True       # Section 11.1: compares fixed_point/newton/bisection/aitken
    run_02_mu_sweep_local: bool = True         # Section 11.2: mu_x sweep, inflow_coupling='local'
    run_03_mu_sweep_global: bool = True        # Section 11.3: same sweep, 'global' mode (speed comparison)
    run_04_reverse_flow_compare: bool = True   # Section 11.4: flat_plate vs thin_plate_blend
    run_05_snel_rotational_aug: bool = True    # Section 11.5: Himmelskamp/Snel effect at the root
    run_06_radial_flow_correction: bool = True  # Section 11.6: radial flow correction (ISAE) at high mu_x
    run_07_pitt_peters_steady: bool = True     # Section 11.7: steady Pitt-Peters vs. Drees 'global'
    run_08_pitt_peters_unsteady: bool = True   # Section 11.8: unsteady Pitt-Peters (transition over time)
    run_09_dynamic_stall: bool = True          # Section 11.9: Øye dynamic stall, 'frequency' vs 'time_march'
    run_10_rotor_propeller_identities: bool = True  # Section 11.10: consistency tests mu_x<->J_x, CT<->CT_prop, and so on.
    run_11_viterna_full_range: bool = True     # Section 11.11: viterna_full_range vs flat_plate/thin_plate_blend

    # --- default mesh used in the "production" blocks (2,3,5,6,9) -----------
    Ne_default: int = 90
    Npsi_default: int = 144

    # --- main mu_x sweep grid (Section 11.2/11.3), alpha_rotor=0 -----------------
    mu_sweep_main: list = field(default_factory=lambda: [0, 0.05, 0.1, 0.13, 0.16, 0.19, 0.23, 0.3, 0.4])

    # --- condition used in the single-point comparison blocks ---------------
    mu_benchmark: float = 0.30       # Section 11.1 (solver benchmark) and 11.4 (reverse flow)
    mu_snel: float = 0.05            # Section 11.5 -- near-hover, where Himmelskamp/Snel is most visible
    mu_radial_flow: float = 0.40     # Section 11.6 -- high advance, where UR (radial component) is large
    mu_dynamic_stall: float = 0.30   # Section 11.9 -- moderate-high advance, stall crosses psi~270deg at the root

    # --- Pitt-Peters (Section 11.7/11.8) ----------------------------------------
    pitt_peters_mu_sweep: list = field(default_factory=lambda: [0.0, 0.05, 0.10, 0.16])
    # (t[s], mu_x, Vz) sequence marched over time . Hover -> mu_x=0.10 transition
    pitt_peters_unsteady_sequence: list = field(default_factory=lambda: [
        (0.00, 0.00, 0.0), (0.05, 0.03, 0.0), (0.10, 0.06, 0.0),
        (0.15, 0.08, 0.0), (0.25, 0.10, 0.0), (0.60, 0.10, 0.0)])

    # --- rotor<->propeller identities (Section 11.10) ----------------------------
    identities_mu: float = 0.22
    identities_mu_z: float = 0.05
    identities_alpha_deg: float = 5.0
    identities_mu_conversion: float = 0.20
    identities_Vv_conversion: float = 2.0
    identities_J_flight: float = 0.62

    outdir: str = "/mnt/user-data/outputs"


# Instance actually used by __main__ (Section 11) . EDIT HERE to choose which
# blocks run and with which parameters, without having to touch the body of
# the script.
RUN_PLAN = RunPlan()


#: Mach ceiling for the Prandtl-Glauert correction # see document sections 8.3.3
#: and 15). Prandtl-Glauert is a subsonic LINEARIZED correction: honest up
#: to M ~ 0.7, already optimistic near M ~ 0.8 (the flow is transonic, with
#: shock and wave drag that the model does not represent) and meaningless
#: above M ~ 0.9. The 1/beta factor is clamped to the value at this ceiling
#: (2.294) instead of diverging.
#:
#: The previous guard was `beta > 1e-3`, which corresponds to M > 0.9999995
#: . It only avoided the exact division by zero and nothing else: at
#: M = 0.99998 the Cl was multiplied by 159, and in a DISCONTINUOUS way at
#: that, because above the cutoff the correction was skipped entirely and
#: the factor dropped from 1000 to 1. Amplifying lift 240x is a numerical
#: artifact presented to the user as a result. This is how 2 out of 7776
#: elements of a supersonic case produced Cl = 599 against a 99th
#: percentile of 2.5, and four of the disk maps turned into a purple
#: rectangle with one lit pixel.
#:
#: The ceiling does NOT change any valid case: the thirteen example
#: projects reach at most M = 0.75, and below 0.9 the expression is
#: identical to the previous one. It only changes the range that was
#: already physically empty.
MACH_MAXIMO_DE_PRANDTL_GLAUERT = 0.9
BETA_MINIMO_DE_PRANDTL_GLAUERT = float(
    np.sqrt(1.0 - MACH_MAXIMO_DE_PRANDTL_GLAUERT ** 2))

#: Floor for (1 + sin alpha*) in the Pitt-Peters gain matrix L
#: (`_pitt_peters_L_V`). Three entries of L divide by this same quantity,
#: which goes to ZERO when alpha* -> -90 deg . Negative total inflow with
#: negligible edgewise flow. That is, OUTSIDE the range for which Pitt-Peters
#: was derived (wake between the edgewise and axial cases, alpha* in
#: [0 deg, 90 deg]).
#:
#: Without the floor, a single iterate that goes to lambda<0 near mu_x=0
#: . Which happens due to overshoot in HOVER, see the comment in
#: `_pitt_peters_L_V` . Produces inf and, on the next step, NaN
#: throughout the result: `run_case` in hover with
#: `inflow_field_model='pitt_peters_steady'` silently returned CT=nan,
#: with no exception and no warning.
#:
#: 1e-3 corresponds to alpha* >= -87.4 deg: never active in edgewise
#: flight, moderate climb or descent (where alpha* stays well above that),
#: so it does not change any already-valid result . It only prevents
#: overflow in the range the model does not describe.
DENOMINADOR_MINIMO_DE_PITT_PETERS = 1e-3


# =============================================================================
# 0c. INPUT DATA . EXAMPLE ROTOR GEOMETRY AND AIRFOIL POLAR
# =============================================================================
#
# ALL the concrete geometry/numbers used by the example rotor and airfoil
# (assembled by `build_example_rotor`/`build_example_airfoil`, near the end
# of the file) live here, alongside the rest of the editable configuration
# (BEMTConfig, RunPlan). To change blade or polar, edit only this section --
# the two builder functions only read these constants.

# --- Blade geometry --------------------------------------------------------
ROTOR_R: float = 2.8 / 2                 # rotor radius [m]
ROTOR_NB: int = 4                        # number of blades
ROTOR_OMEGA_RPM: float = 1200            # rotation speed [RPM]
ROTOR_R_ROOT_NORM: float = 0.2143        # geometric root cutout (r/R)
ROTOR_R_TIP_NORM: float = 1.0            # geometric tip (r/R)

# Radial stations (r/R), chord [m] and twist [deg] sampled along the
# blade . Interpolated linearly by `Rotor.chord_theta_at` for whatever
# mesh (Ne) the solver is using.
ROTOR_R_GEOM = np.array([.214, 0.27, 0.327, 0.383, 0.439, 0.495, 0.551, 0.607,
                          0.663, 0.719, 0.776, 0.832, 0.888, 0.944, 1.0])
ROTOR_CHORD_GEOM = np.array([0.154143, 0.145357, 0.137571, 0.130286, 0.123286, 0.116357,
                              0.109571, 0.102857, 0.096214, 0.089643, 0.083, 0.076429,
                              0.07, 0.063571, 0.057143]) * 1.4
ROTOR_THETA_GEOM_DEG = np.array([24.4631, 22.4499, 20.5977, 18.9432, 17.4312, 16.0448,
                                  14.7698, 13.5948, 12.51, 11.5078, 10.5645, 9.7074,
                                  8.9141, 8.1797, 7.5]) - 0.8

# --- Airfoil polar (linear analytical model + stall) -----------------------
AIRFOIL_CL_ALPHA: float = 2 * np.pi      # lift-curve slope [1/rad] (theoretical, thin plate)
AIRFOIL_ALPHA0_DEG: float = -4.5         # zero-lift angle [deg]
AIRFOIL_CD0: float = 0.0155              # profile drag at Cl=0
AIRFOIL_K: float = 0.0                   # profile induced-drag coefficient (Cd=Cd0+k*Cl^2)
AIRFOIL_STALL_POS_DEG: float = 15.0      # positive stall angle [deg]
AIRFOIL_STALL_NEG_DEG: float = -6.0      # negative stall angle [deg]
AIRFOIL_STALL_MODEL: str = "enhanced"    # linear | clip | enhanced (see `AnalyticalAirfoil.cl_cd`)


# =============================================================================
# 1. AIRFOIL MODELS
# =============================================================================

def _zero_crossing_alpha0(alpha_rad: np.ndarray, cl: np.ndarray) -> float:
    """Estimates alpha0 (zero-lift angle) by linear interpolation at the
    first sign crossing of Cl(alpha). Used as a fallback for tabulated
    airfoils in the Snel/Himmelskamp rotational correction."""
    sign_changes = np.where(np.diff(np.sign(cl)) != 0)[0]
    if len(sign_changes) == 0:
        return 0.0
    i0 = int(sign_changes[0])
    a1, a2 = alpha_rad[i0], alpha_rad[i0 + 1]
    c1, c2 = cl[i0], cl[i0 + 1]
    if abs(c2 - c1) < 1e-9:
        return 0.0
    return float(a1 - c1 * (a2 - a1) / (c2 - c1))


def _detect_stall_extremum(alpha_rad: np.ndarray, cl: np.ndarray, side: str) -> tuple:
    """Detects the tabulated stall point (real Cl extremum) on the 'pos'
    side (alpha>=0, looks for the MAXIMUM Cl) or 'neg' side (alpha<=0,
    looks for the MINIMUM/most negative Cl). Returns (index in the array,
    alpha_stall [rad], Cl_stall) . 100% derived from the table data, with
    no analytical parameter.

    If the table has no Cl reversal within that side (airfoil with no
    post-stall data . Cl still monotonically increasing/decreasing up to
    the edge), the detected "stall" IS the last real table point on that
    side. This is intentional: in that case there is, in fact, no real
    post-stall region to preserve, so the Viterna anchor coincides with the
    data edge and the extrapolation begins exactly where the real data
    ends . Consistent behavior, with no discontinuity."""
    mask = (alpha_rad >= 0) if side == "pos" else (alpha_rad <= 0)
    idx_side = np.where(mask)[0]
    if len(idx_side) == 0:
        # One-sided table (an external polar that only converged on one
        # side of alpha=0). Dying here turned a usable polar into a dead
        # "Error running case". The section is assumed MIRROR-symmetric
        # about the chord line for the missing side: the stall anchor is
        # the other side's extremum, sign-flipped, clamped to stay at or
        # beyond that side's data edge. The extrapolated region carries
        # the assumption; everything inside the table stays 100% data.
        other = "neg" if side == "pos" else "pos"
        mask_other = (alpha_rad >= 0) if other == "pos" else (alpha_rad <= 0)
        idx_other = np.where(mask_other)[0]
        if len(idx_other) == 0:
            raise ValueError(
                "Table has no alpha points at all -- cannot auto-detect "
                "stall. Regenerate or import a polar with a non-empty "
                "alpha sweep.")
        j_local = int(np.argmax(cl[idx_other])) if other == "pos" \
            else int(np.argmin(cl[idx_other]))
        j = int(idx_other[j_local])
        if side == "pos":
            # Missing positive side: anchor mirrored from the negative
            # extremum, clamped to at/after the last data point.
            alpha_anchor = max(-float(alpha_rad[j]), float(alpha_rad[-1]))
            cl_anchor = -float(cl[j])
            idx = int(np.argmax(alpha_rad))
        else:
            alpha_anchor = min(-float(alpha_rad[j]), float(alpha_rad[0]))
            cl_anchor = -float(cl[j])
            idx = int(np.argmin(alpha_rad))
        warnings.warn(
            f"Table covers only the '{other}' side of alpha=0; the "
            f"'{side}' stall anchor is MIRRORED from it "
            f"(alpha_stall={np.degrees(alpha_anchor):.2f} deg, "
            f"CL={cl_anchor:.3f}). Regenerate the polar with a wider "
            f"alpha range for real data on both sides.")
        return idx, float(alpha_anchor), float(cl_anchor)
    cl_side = cl[idx_side]
    local_idx = int(np.argmax(cl_side)) if side == "pos" else int(np.argmin(cl_side))
    idx = int(idx_side[local_idx])
    return idx, float(alpha_rad[idx]), float(cl[idx])


def _linear_region_fit(alpha_rad: np.ndarray, cl: np.ndarray, alpha0_guess: float,
                        idx_pos_stall: int, idx_neg_stall: int) -> tuple:
    """Least-squares fit of (Cl_alpha, alpha0) in a central window between
    the two detected stalls (60% of the interval between them, centered on
    `alpha0_guess`). Replaces the old 4-point finite-difference estimate
    around the array's central INDEX (which is fragile when the table is
    not symmetric around alpha=0 (a table from -5 deg to +25 deg: the
    central index falls near +10 deg, outside the truly linear region).
    Used both by the Snel/Himmelskamp rotational correction and by the Øye
    dynamic stall (`_airfoil_cl_alpha_alpha0`), which need the "fully
    attached" line."""
    a_pos = alpha_rad[idx_pos_stall]
    a_neg = alpha_rad[idx_neg_stall]
    half_span = 0.3 * (a_pos - a_neg)
    lo, hi = alpha0_guess - half_span, alpha0_guess + half_span
    sel = (alpha_rad >= lo) & (alpha_rad <= hi)
    if np.count_nonzero(sel) < 2:
        sel = np.ones_like(alpha_rad, dtype=bool)  # fallback: whole table
    A = np.vstack([alpha_rad[sel], np.ones(np.count_nonzero(sel))]).T
    cl_alpha, intercept = np.linalg.lstsq(A, cl[sel], rcond=None)[0]
    cl_alpha = max(float(cl_alpha), 0.5)
    alpha0 = -float(intercept) / cl_alpha if abs(cl_alpha) > 1e-9 else alpha0_guess
    return cl_alpha, alpha0


class AnalyticalAirfoil:
    """Linear Cl/Cd + stall analytical model, equivalent to
    lookup_airfoil_analytical with 'linear', 'clip' or 'enhanced' stall
    models."""

    def __init__(self, cl_alpha: float = 2 * np.pi, alpha0_deg: float = -4.5,
                 cd0: float = 0.0155, k: float = 0.0,
                 alpha_stall_pos_deg: float = 15.0, alpha_stall_neg_deg: float = -6.0,
                 stall_model: str = "linear"):
        self.cl_alpha = cl_alpha
        self.alpha0 = np.deg2rad(alpha0_deg)
        self.cd0 = cd0
        self.k = k
        self.alpha_stall_pos = np.deg2rad(alpha_stall_pos_deg)
        self.alpha_stall_neg = np.deg2rad(alpha_stall_neg_deg)
        self.stall_model = stall_model

    def cl_cd(self, alpha: np.ndarray, mach: Optional[np.ndarray] = None, r_norm=None):
        model = self.stall_model.lower()
        cl_lin = self.cl_alpha * (alpha - self.alpha0)
        cd_lin = self.cd0 + self.k * cl_lin ** 2
        cl_sp = self.cl_alpha * (self.alpha_stall_pos - self.alpha0)
        cl_sn = self.cl_alpha * (self.alpha_stall_neg - self.alpha0)
        cd_sp = self.cd0 + self.k * cl_sp ** 2
        cd_sn = self.cd0 + self.k * cl_sn ** 2

        if model == "linear":
            cl, cd = cl_lin, cd_lin

        elif model == "clip":
            cl = np.where(alpha > self.alpha_stall_pos, cl_sp,
                  np.where(alpha < self.alpha_stall_neg, cl_sn, cl_lin))
            cd = np.where(alpha > self.alpha_stall_pos, cd_sp,
                  np.where(alpha < self.alpha_stall_neg, cd_sn, cd_lin))

        elif model in ("enhanced", "dynamic"):
            cd_fp = 1.9
            rng = np.pi / 6.0

            beyond_pos = alpha - self.alpha_stall_pos
            scale_pos = np.cos(np.minimum(np.pi / 2, beyond_pos * (np.pi / 2 / rng)))
            cl_pos = np.maximum(cl_sp * scale_pos, 0.0)
            dscale_pos = np.sin(np.minimum(np.pi / 2, beyond_pos * (np.pi / 2 / (rng * 1.5)))) ** 2
            cd_pos = np.maximum(cd_sp + (cd_fp - cd_sp) * dscale_pos, cd_sp)

            beyond_neg = alpha - self.alpha_stall_neg
            scale_neg = np.cos(np.maximum(-np.pi / 2, beyond_neg * (np.pi / 2 / rng)))
            cl_neg = np.minimum(cl_sn * scale_neg, 0.0)
            dscale_neg = np.sin(np.maximum(-np.pi / 2, beyond_neg * (np.pi / 2 / (rng * 1.5)))) ** 2
            cd_neg = np.maximum(cd_sn + (cd_fp - cd_sn) * dscale_neg, cd_sn)

            cl = np.where(alpha > self.alpha_stall_pos, cl_pos,
                  np.where(alpha < self.alpha_stall_neg, cl_neg, cl_lin))
            cd = np.where(alpha > self.alpha_stall_pos, cd_pos,
                  np.where(alpha < self.alpha_stall_neg, cd_neg, cd_lin))
            cd = np.maximum(cd, self.cd0)
        else:
            raise ValueError(f"Unknown stall_model: {self.stall_model}")

        cd = np.maximum(cd, 0.0)
        return cl, cd


class TableAirfoil:
    """Generic tabulated polar (alpha_deg, Cl, Cd), linear interpolation.
    Optionally accepts multiple radial sections (list of tables + r_norm
    for each section), also interpolating along the radius."""

    def __init__(self, alpha_deg, cl, cd, r_norm_section: Optional[float] = None):
        self.alpha = np.deg2rad(np.asarray(alpha_deg, dtype=float))
        self.cl_tab = np.asarray(cl, dtype=float)
        self.cd_tab = np.asarray(cd, dtype=float)
        self.r_norm_section = r_norm_section
        alpha0_guess = _zero_crossing_alpha0(self.alpha, self.cl_tab)
        try:
            idx_p, _, _ = _detect_stall_extremum(self.alpha, self.cl_tab, "pos")
            idx_n, _, _ = _detect_stall_extremum(self.alpha, self.cl_tab, "neg")
            self.cl_alpha, self.alpha0 = _linear_region_fit(self.alpha, self.cl_tab, alpha0_guess, idx_p, idx_n)
        except ValueError:
            # table covers only one side of alpha=0 . Fallback to the old
            # method (local finite difference around the array's central index)
            mid = len(self.alpha) // 2
            lo, hi = max(mid - 2, 0), min(mid + 2, len(self.alpha) - 1)
            denom = (self.alpha[hi] - self.alpha[lo])
            self.cl_alpha = float((self.cl_tab[hi] - self.cl_tab[lo]) / denom) if abs(denom) > 1e-6 else 2 * np.pi
            self.cl_alpha = max(self.cl_alpha, 0.5)
            self.alpha0 = alpha0_guess

    @classmethod
    def from_csv(cls, path: str, alpha_col="alpha_deg", cl_col="Cl", cd_col="Cd"):
        df = pd.read_csv(path)
        return cls(df[alpha_col], df[cl_col], df[cd_col])

    def cl_cd(self, alpha: np.ndarray, mach: Optional[np.ndarray] = None, r_norm=None):
        cl = np.interp(alpha, self.alpha, self.cl_tab, left=self.cl_tab[0], right=self.cl_tab[-1])
        cd = np.interp(alpha, self.alpha, self.cd_tab, left=self.cd_tab[0], right=self.cd_tab[-1])
        return cl, np.maximum(cd, 0.0)


class MultiSectionTableAirfoil:
    """Several polars (one per radial section r/R), bilinear interpolation
    in (alpha, r_norm). Feed it a dictionary
    {r_norm: (alpha_deg, cl, cd)}."""

    def __init__(self, sections: dict):
        self.r_norms = np.array(sorted(sections.keys()))
        tables = [sections[r] for r in self.r_norms]
        alpha_ref = np.deg2rad(np.asarray(tables[0][0], dtype=float))
        self.alpha = alpha_ref
        self.cl_grid = np.array([np.interp(alpha_ref, np.deg2rad(t[0]), t[1]) for t in tables])  # (Nsec, Nalpha)
        self.cd_grid = np.array([np.interp(alpha_ref, np.deg2rad(t[0]), t[2]) for t in tables])
        # Cl_alpha/alpha0 PER SECTION (an independent linear fit per row of
        # `cl_grid`), used both by the Snel/Himmelskamp rotational
        # correction and by the Øye dynamic stall . See
        # `cl_alpha_alpha0_field` below, which interpolates this array by
        # r_norm instead of using a single representative pair (fixes what
        # used to be a documented limitation: "a single pair for the whole
        # blade"). `self.cl_alpha`/`self.alpha0` (scalars, median section)
        # still exist for compatibility with any code that still reads
        # these attributes directly.
        self._cl_alpha_per_section, self._alpha0_per_section = self._fit_cl_alpha_alpha0_per_row(
            alpha_ref, self.cl_grid)
        mid = len(self.r_norms) // 2
        self.cl_alpha = float(self._cl_alpha_per_section[mid])
        self.alpha0 = float(self._alpha0_per_section[mid])

    @staticmethod
    def _fit_cl_alpha_alpha0_per_row(alpha_ref, grid):
        cl_alphas = np.empty(grid.shape[0], dtype=float)
        alpha0s = np.empty(grid.shape[0], dtype=float)
        for i, row in enumerate(grid):
            alpha0_guess = _zero_crossing_alpha0(alpha_ref, row)
            try:
                idx_p, _, _ = _detect_stall_extremum(alpha_ref, row, "pos")
                idx_n, _, _ = _detect_stall_extremum(alpha_ref, row, "neg")
                cl_a, a0 = _linear_region_fit(alpha_ref, row, alpha0_guess, idx_p, idx_n)
            except ValueError:
                mid = len(alpha_ref) // 2
                lo, hi = max(mid - 2, 0), min(mid + 2, len(alpha_ref) - 1)
                denom = alpha_ref[hi] - alpha_ref[lo]
                cl_a = float((row[hi] - row[lo]) / denom) if abs(denom) > 1e-6 else 2 * np.pi
                cl_a = max(cl_a, 0.5)
                a0 = alpha0_guess
            cl_alphas[i] = cl_a
            alpha0s[i] = a0
        return cl_alphas, alpha0s

    def cl_alpha_alpha0_field(self, r_norm):
        """(Cl_alpha, alpha0) interpolated by r_norm from the linear fit of
        EACH section (no longer a single representative pair) . Used by
        `bemt._airfoil_cl_alpha_alpha0` for dynamic stall (Øye) and
        rotational correction (Snel) per section."""
        r = np.asarray(r_norm, dtype=float)
        cl_alpha = np.interp(r, self.r_norms, self._cl_alpha_per_section)
        alpha0 = np.interp(r, self.r_norms, self._alpha0_per_section)
        return cl_alpha, alpha0

    def cl_cd(self, alpha: np.ndarray, mach: Optional[np.ndarray] = None, r_norm=None):
        if r_norm is None:
            raise ValueError("MultiSectionTableAirfoil requires r_norm (same shape as alpha)")
        a = np.atleast_1d(alpha)
        r = np.atleast_1d(r_norm) * np.ones_like(a)
        cl = np.empty_like(a, dtype=float)
        cd = np.empty_like(a, dtype=float)
        # interpolation in alpha per section, then in r between neighboring sections
        cl_per_sec = np.array([np.interp(a.ravel(), self.alpha, row) for row in self.cl_grid])  # (Nsec, Npts)
        cd_per_sec = np.array([np.interp(a.ravel(), self.alpha, row) for row in self.cd_grid])
        for k in range(a.size):
            cl.flat[k] = np.interp(r.flat[k], self.r_norms, cl_per_sec[:, k])
            cd.flat[k] = np.interp(r.flat[k], self.r_norms, cd_per_sec[:, k])
        return cl.reshape(np.shape(alpha)), np.maximum(cd.reshape(np.shape(alpha)), 0.0)


# -----------------------------------------------------------------------------
# 1a-bis. HETEROGENEOUS MULTI-SECTION AIRFOIL (docs/plano.md GUI v3, Phase D)
# -----------------------------------------------------------------------------
#
# Key difference from MultiSectionTableAirfoil (above): that class
# interpolates DATA from a single tabulated representation (all sections
# must come from the same kind of table). This class interpolates the
# already-evaluated RESULT (Cl/Cd) of N independently constructed airfoil
# objects . Each section can be an AnalyticalAirfoil, a TableAirfoil, or
# even a section wrapped in ViternaExtendedAirfoil, freely mixed. This is
# what allows, for example, an analytical root + tabulated tip on the same
# blade. Built by airfoils.to_blade_airfoil() from
# Project.airfoil_sections. Never instantiated directly by the GUI.
class HeterogeneousMultiSectionAirfoil:
    """Combines N airfoil objects (any, as long as they share the same
    contract ``cl_cd(alpha, mach, r_norm) -> (cl, cd)``), one per r/R
    station, LINEARLY interpolating the already-evaluated Cl/Cd of each one
    (not the input parameters). Outside ``[min(r_norm), max(r_norm)]``, it
    "clamps" to the value of the nearest section (same constant
    extrapolation behavior as ``np.interp``/``MultiSectionTableAirfoil``).
    """

    def __init__(self, sections: list):
        if len(sections) < 2:
            raise ValueError(
                f"HeterogeneousMultiSectionAirfoil requires at least 2 sections (got {len(sections)}).")
        ordered = sorted(sections, key=lambda t: t[0])
        self.r_norms = np.array([r for r, _ in ordered], dtype=float)
        self.airfoils = [af for _, af in ordered]
        # Cl_alpha/alpha0 PER SECTION: each sub-airfoil already carries its
        # own (Cl_alpha, alpha0) (analytical: direct field, tabulated:
        # automatic fit). `cl_alpha_alpha0_field` interpolates this array
        # by r_norm instead of using a single representative median-section
        # pair (fixes the limitation previously documented here: "same
        # spirit/limitation as MultiSectionTableAirfoil"). Used both by the
        # Snel/Himmelskamp rotational correction and by the Øye dynamic
        # stall, now applicable per section.
        self._cl_alpha_per_section = np.array(
            [getattr(af, "cl_alpha", 2 * np.pi) for af in self.airfoils], dtype=float)
        self._alpha0_per_section = np.array(
            [getattr(af, "alpha0", 0.0) for af in self.airfoils], dtype=float)
        mid = len(self.airfoils) // 2
        self.cl_alpha = float(self._cl_alpha_per_section[mid])
        self.alpha0 = float(self._alpha0_per_section[mid])

    def cl_alpha_alpha0_field(self, r_norm):
        """(Cl_alpha, alpha0) interpolated by r_norm from each section's
        OWN value (see note above) . Used by
        `bemt._airfoil_cl_alpha_alpha0` to apply dynamic stall (Øye) and
        rotational correction (Snel) section by section."""
        r = np.asarray(r_norm, dtype=float)
        cl_alpha = np.interp(r, self.r_norms, self._cl_alpha_per_section)
        alpha0 = np.interp(r, self.r_norms, self._alpha0_per_section)
        return cl_alpha, alpha0

    def cl_cd(self, alpha: np.ndarray, mach: Optional[np.ndarray] = None, r_norm=None):
        if r_norm is None:
            raise ValueError("HeterogeneousMultiSectionAirfoil requires r_norm (same shape as alpha)")
        alpha_arr = np.asarray(alpha, dtype=float)
        r = np.broadcast_to(np.asarray(r_norm, dtype=float), alpha_arr.shape)

        # Evaluates EACH section at every point (a,mach) . N sections is
        # typically small (a few dozen at most), so this is cheap, and
        # linearly interpolates the result by r_norm, point by point
        # (equivalent to interpolating only between the two nearest
        # neighbors, since np.interp uses only the pair surrounding each
        # r. Computing all sections just simplifies the code).
        n_sec = len(self.airfoils)
        cl_per_sec = np.empty((n_sec,) + alpha_arr.shape, dtype=float)
        cd_per_sec = np.empty((n_sec,) + alpha_arr.shape, dtype=float)
        for i, af in enumerate(self.airfoils):
            cl_i, cd_i = af.cl_cd(alpha_arr, mach=mach)
            cl_per_sec[i] = np.broadcast_to(np.asarray(cl_i, dtype=float), alpha_arr.shape)
            cd_per_sec[i] = np.broadcast_to(np.asarray(cd_i, dtype=float), alpha_arr.shape)

        cl = np.empty_like(alpha_arr)
        cd = np.empty_like(alpha_arr)
        r_flat = r.ravel()
        cl_flat_per_sec = cl_per_sec.reshape(n_sec, -1)
        cd_flat_per_sec = cd_per_sec.reshape(n_sec, -1)
        for k in range(alpha_arr.size):
            cl.flat[k] = np.interp(r_flat[k], self.r_norms, cl_flat_per_sec[:, k])
            cd.flat[k] = np.interp(r_flat[k], self.r_norms, cd_flat_per_sec[:, k])
        return cl, np.maximum(cd, 0.0)


# -----------------------------------------------------------------------------
# 1b. VITERNA-CORRIGAN EXTENSION (continuous polar from -180 to +180 degrees)
# -----------------------------------------------------------------------------
#
# References:
#   Viterna, L.A. and Corrigan, R.D., "Fixed Pitch Rotor Performance of Large
#   Horizontal Axis Wind Turbines," DOE/NASA Workshop on Large HAWTs, 1981.
#   Viterna, L.A. and Janetzke, D.C., "Theoretical and Experimental Power from
#   Large Horizontal-Axis Wind Turbines," NASA TM-82944, 1982.
#   Formulation also documented in the AeroDyn Theory Manual (NREL) and used
#   as the standard extension in QBlade, AeroDyn/OpenFAST, and in ExBEMT
#   (Konuk, 2024/2026) for VTOL propellers/proprotors at high incidence.
#
# This is the "industry standard" alternative to the blend/branch reverse
# flow models above ('flat_plate', 'simple_flip', 'alpha_blending',
# 'thin_plate_blend'): instead of switching between (or blending) two
# different aerodynamic models near Ut=0, a SINGLE smooth, continuous
# Cl(alpha), Cd(alpha) function is built over the whole -180deg..+180deg
# interval, so that the same continuous phi=atan2(Up,Ut) (with no "reverse"
# branch) already produces continuous forces all the way around the disk,
# including inside and around the reverse-flow region. Used via
# `BEMTConfig.reverse_flow_model='viterna_full_range'` (see
# `element_state`, Section 4), which requires a base airfoil wrapped by this
# class.
class ViternaExtendedAirfoil:
    """Wraps any base airfoil model (valid up to stall) and extends Cl/Cd
    continuously up to +-180 degrees via Viterna-Corrigan.

    Two ways to anchor the extension, chosen automatically based on the
    arguments received:

    - **Manual mode** (`alpha_stall_pos_deg`/`alpha_stall_neg_deg` given
      explicitly, or an analytical base airfoil that already exposes its
      own stall angles): the Viterna anchor IS the data edge (there is no
      real post-stall table to preserve).
    - **Automatic mode** (`alpha_stall_pos_deg`/`neg_deg` == None and the
      base airfoil is a `TableAirfoil`): CLmax/CLmin and the corresponding
      stall angles are detected directly from the table itself (argmax/
      argmin of Cl , see `_detect_stall_extremum`), with no dependence on
      any analytical parameter. The Viterna anchor (the CLmax/CLmin point)
      and the REAL data edge (the last point actually tabulated on each
      side) are treated as two distinct things: the table is used in full
      and unaltered over its entire real interval . Even beyond CLmax, if
      the table already has points there . And only extrapolates via
      Viterna-Corrigan starting from where the real data actually ends.

    In EITHER mode, the transition into Viterna is smoothed by a
    C1-continuous blend (never an abrupt switch again) . But the
    DIRECTION of the blend depends on whether there is real data beyond
    the anchor or not (`has_gap_pos`/`has_gap_neg`, one per side):

    - **WITH gap** (table with real post-stall points beyond CLmax/CLmin,
      CLmax at 14deg but table measured up to 25deg): the blend
      happens "forward", AFTER the real edge (`alpha_edge`), mixing the
      line tangent to the last real data point with Viterna . See region
      (2a) below. Nothing within the real interval is touched.
    - **WITHOUT gap** (anchor == edge, an analytical/manual case, or table
      with no real Cl reversal): the blend happens "backward", BEFORE the
      anchor, ending exactly at alpha_stall . See region (2b) below.
      Important: a "forward" blend here would push the Cl peak (and the
      "effective" alpha_stall) beyond the defined angle, since the
      unclamped base model (for example `stall_model='linear'`) keeps rising with
      full slope right after the anchor. By ending the blend exactly at
      alpha_stall (weight -> 100% Viterna there, which by construction
      already equals Cl_stall at that point), the curve's peak falls where
      it was defined, not after it.

    Construction (always C0 and C1-continuous):
      1) "attached" region: uses the base model DIRECTLY (real tabulated
         data is never overwritten). Goes up to `alpha_edge` (with gap) or
         up to `alpha_edge - blend_width` (without gap, since the final
         stretch before the anchor is now part of the blend).
      2a) WITH gap, window [alpha_edge, alpha_edge+blend_width]: blends,
          via a smooth Hermite-type weight (`_smoothstep`, zero derivative
          at both ends), the line tangent to the base model at alpha_edge
          (value + derivative by finite difference, "continuing" the local
          trend of the real data) with Viterna-Corrigan.
      2b) WITHOUT gap, window [alpha_edge-blend_width, alpha_edge]: blends,
          with the same smooth weight, the base model evaluated DIRECTLY
          (always within its valid domain . No tangent line needed) with
          Viterna-Corrigan.
      In both cases, by mathematical construction (weight with zero
      derivative at the window's edges), the resulting curve matches value
      and slope EXACTLY with the base model on one end and with Viterna on
      the other . With no step nor "kink" on either side. This is the
      blend that smooths the stall (see the module docstring, Section 1b
      . Inspired by how QBlade lets you adjust the "Range of original
      polar" and smooth the transition instead of an abrupt switch at
      alpha_stall).
      3) Pure Viterna-Corrigan beyond the blend window, up to 90deg, and
         90deg < |alpha| <= 180deg: physical reflection about 90deg.

    Note on the Cl peak in the WITHOUT-gap case: since the interpolation is
    C1-continuous (matches value AND slope at both ends), and the Viterna
    formula typically already has a negative slope at alpha_stall. That is,
    Viterna itself is already "descending" there), the real peak of the
    combined curve falls slightly BEFORE alpha_stall (never after --
    unlike the "forward" blend problem this method replaces) and with a
    value slightly ABOVE Cl_stall. This is an unavoidable mathematical
    consequence of requiring C1-continuity with slopes of opposite signs
    at the two ends (by the mean value theorem, an intermediate peak must
    exist) . Not a bug. The typical deviation is small (~1-2% of the
    stall Cl for blend_width_deg=4deg) and scales roughly linearly with
    `blend_width_deg`: reduce this parameter for a peak closer to the
    defined value (at the cost of a more abrupt transition), or increase
    it for a smoother transition (at the cost of a slightly higher/
    earlier peak).
    """

    def __init__(self, base_airfoil, alpha_stall_pos_deg: Optional[float] = None,
                 alpha_stall_neg_deg: Optional[float] = None,
                 cd_max: Optional[float] = None, aspect_ratio: Optional[float] = None,
                 blend_width_deg: float = 4.0):
        self.base = base_airfoil
        self.cl_alpha = getattr(base_airfoil, "cl_alpha", 2 * np.pi)
        self.alpha0 = getattr(base_airfoil, "alpha0", 0.0)

        # Cd_max: Viterna & Janetzke (1982) for finite AR, or the 2D
        # flat-plate limit (~2.01) when AR is not given . Usual default in
        # blade-element BEMT (each station is effectively "2D").
        if cd_max is not None:
            self.cd_max = cd_max
        elif aspect_ratio is not None:
            self.cd_max = 1.11 + 0.018 * aspect_ratio
        else:
            self.cd_max = 2.01
        self.aspect_ratio = aspect_ratio
        self.blend_width_deg = blend_width_deg

        # --- Multi-section (MultiSectionTableAirfoil) ------------------------
        # Finding: a single tabulated Cl/Cd polar per radial section (r/R)
        # generally means a DIFFERENT Cl_stall/Cd_stall per section (the
        # table at r=0.3 and the table at r=0.9 have no reason to stall at
        # the same Cl). Anchoring a SINGLE Viterna extrapolation on the
        # values of just one section (or worse, trying to call
        # `base.cl_cd()` without `r_norm`, which is mandatory for
        # `MultiSectionTableAirfoil` and therefore raised `ValueError`
        # before this fix) produced an incorrect post-stall extension for
        # every section but one.
        # Fix: a child `ViternaExtendedAirfoil` is built PER section (each
        # one anchored on its own Cl_stall/Cd_stall, extracted from its own
        # table, automatically, in automatic mode), and evaluation in
        # `cl_cd` interpolates in r_norm between the results of neighboring
        # sections . Exactly the same radial interpolation mechanics
        # already used by `MultiSectionTableAirfoil.cl_cd` in the attached
        # region.
        self._multi_section = isinstance(base_airfoil, MultiSectionTableAirfoil)
        if self._multi_section:
            self._section_r_norms = base_airfoil.r_norms
            alpha_deg_ref = np.degrees(base_airfoil.alpha)
            auto = (alpha_stall_pos_deg is None) or (alpha_stall_neg_deg is None)
            self._section_children = [
                ViternaExtendedAirfoil(
                    TableAirfoil(alpha_deg_ref, cl_row, cd_row),
                    alpha_stall_pos_deg=None if auto else alpha_stall_pos_deg,
                    alpha_stall_neg_deg=None if auto else alpha_stall_neg_deg,
                    cd_max=cd_max, aspect_ratio=aspect_ratio,
                    blend_width_deg=blend_width_deg,
                )
                for cl_row, cd_row in zip(base_airfoil.cl_grid, base_airfoil.cd_grid)
            ]
            # scalar coefficients (_coef_pos/_coef_neg) do not apply
            # here . Each section has its own, inside _section_children.
            return

        is_table = isinstance(base_airfoil, TableAirfoil)
        # Only enters automatic-detection mode (table CLmax/CLmin) when
        # the angles were NOT passed explicitly AND the base airfoil
        # also does not expose them itself (AnalyticalAirfoil
        # exposes `alpha_stall_pos`/`alpha_stall_neg` directly . In
        # that case uses them, as always, even without explicit args;
        # see `build_example_viterna_airfoil`).
        base_has_stall_attrs = (getattr(base_airfoil, "alpha_stall_pos", None) is not None
                                 and getattr(base_airfoil, "alpha_stall_neg", None) is not None)
        auto_detect = (alpha_stall_pos_deg is None or alpha_stall_neg_deg is None) and not base_has_stall_attrs

        if auto_detect and not is_table:
            raise ValueError("ViternaExtendedAirfoil: alpha_stall_pos_deg and "
                              "alpha_stall_neg_deg can be None, for auto-detection, "
                              "only when the base airfoil is a TableAirfoil. An "
                              "analytical model has no tabulated CLmax or CLmin to "
                              "detect. Give the stall angles.")

        if auto_detect:
            idx_p, a_sp_rad, _ = _detect_stall_extremum(base_airfoil.alpha, base_airfoil.cl_tab, "pos")
            idx_n, a_sn_rad, _ = _detect_stall_extremum(base_airfoil.alpha, base_airfoil.cl_tab, "neg")
            self.alpha_s_pos = a_sp_rad
            self.alpha_s_neg = a_sn_rad
            # real data edge: LAST point actually tabulated on each
            # side . May lie beyond CLmax/CLmin (table with real
            # post-stall data), never short of it. Only from here on
            # does the Viterna extrapolation come into play. Everything
            # inside the table keeps coming 100% from the table, with
            # no alteration whatsoever.
            self.alpha_edge_pos = float(base_airfoil.alpha[-1])
            self.alpha_edge_neg = float(base_airfoil.alpha[0])
        else:
            # If the base airfoil already exposes its own stall angles
            # (AnalyticalAirfoil), use them. Otherwise, require them to
            # be passed explicitly.
            a_sp = alpha_stall_pos_deg if alpha_stall_pos_deg is not None else np.degrees(
                getattr(base_airfoil, "alpha_stall_pos", None))
            a_sn = alpha_stall_neg_deg if alpha_stall_neg_deg is not None else np.degrees(
                getattr(base_airfoil, "alpha_stall_neg", None))
            if a_sp is None or a_sn is None or np.isnan(a_sp) or np.isnan(a_sn):
                raise ValueError("ViternaExtendedAirfoil needs alpha_stall_pos_deg/"
                                  "alpha_stall_neg_deg (the base airfoil does not expose them).")
            self.alpha_s_pos = np.deg2rad(a_sp)
            self.alpha_s_neg = np.deg2rad(a_sn)  # negative
            # no real table beyond stall: the blend edge coincides with the anchor
            self.alpha_edge_pos = self.alpha_s_pos
            self.alpha_edge_neg = self.alpha_s_neg

        # Whether (or not) there is real data BEYOND the anchor (CLmax/
        # CLmin) determines which of the two blend forms to use . See
        # the class docstring, important Note right above `cl_cd`:
        #   - has_gap=True  (table with real post-stall points, alpha_edge >
        #     alpha_s): "forward" blend, after alpha_edge . Touches
        #     nothing within the real interval.
        #   - has_gap=False (anchor == edge, an analytical/manual case, or
        #     table with no real Cl reversal): "backward" blend, BEFORE the
        #     anchor, ending exactly at it. Essential: a "forward"
        #     blend here would push the Cl peak (and the "effective"
        #     alpha_stall) beyond the angle defined by the user, since the
        #     base model (unclamped line, in the 'linear' case) keeps
        #     rising with full slope right after the anchor . Exactly
        #     the reported problem: CLmax and alpha_stall coming out higher
        #     than parameterized. By ending the blend AT alpha_stall (weight
        #     -> 1, that is 100% Viterna, exactly there), the curve's peak falls
        #     where it was defined, by construction (Viterna is already
        #     adjusted to equal Cl_stall exactly at alpha_stall).
        self.has_gap_pos = (self.alpha_edge_pos - self.alpha_s_pos) > 1e-9
        self.has_gap_neg = (self.alpha_s_neg - self.alpha_edge_neg) > 1e-9

        # Blend window width (rad). For the side with a gap, subject to
        # the 90deg ceiling from the edge (never lets the window "leak"
        # beyond the point where the 90deg mirror symmetry already assumes
        # pure Viterna). For the side without a gap (backward blend),
        # subject to not passing alpha=0 (no sense for the window to
        # cross to the other side).
        bw = np.deg2rad(max(blend_width_deg, 0.0))
        if self.has_gap_pos:
            self.blend_width_pos = float(np.clip(bw, 0.0, max(np.pi / 2 - abs(self.alpha_edge_pos), 0.0)))
        else:
            self.blend_width_pos = float(np.clip(bw, 0.0, abs(self.alpha_edge_pos)))
        if self.has_gap_neg:
            self.blend_width_neg = float(np.clip(bw, 0.0, max(np.pi / 2 - abs(self.alpha_edge_neg), 0.0)))
        else:
            self.blend_width_neg = float(np.clip(bw, 0.0, abs(self.alpha_edge_neg)))

        # Line tangent to the base model at the real data edge (value +
        # derivative, BACKWARD finite difference . Always evaluating
        # `base.cl_cd` only "inward" of the real domain, never beyond it).
        # Used only on the side with a gap, as the "real data" end of the
        # blend window (see the Hermite block right below).
        if self.has_gap_pos:
            (self._edge_pos_cl, self._edge_pos_cd,
             self._edge_pos_dcl, self._edge_pos_dcd) = self._edge_tangent(self.alpha_edge_pos)
        if self.has_gap_neg:
            (self._edge_neg_cl, self._edge_neg_cd,
             self._edge_neg_dcl, self._edge_neg_dcd) = self._edge_tangent(self.alpha_edge_neg)

        cl_sp, cd_sp = self._base_cl_cd_scalar(self.alpha_s_pos)
        cl_sn, cd_sn = self._base_cl_cd_scalar(self.alpha_s_neg)
        self._coef_pos = self._viterna_coeffs(cl_sp, cd_sp, self.alpha_s_pos)
        # cl_sn is the base model's Cl at alpha_s_neg (typically negative).
        # The Viterna coefficients are derived for a "positive-side-type"
        # curve (anchored at sin(alpha)>0). That is why we use -cl_sn here,
        # and the sign is returned correctly in the evaluation loop (cl_cd),
        # which multiplies by -1 on the unmirrored negative branch.
        self._coef_neg = self._viterna_coeffs(-cl_sn, cd_sn, abs(self.alpha_s_neg))

        # --- Pre-computes (value, derivative WITH RESPECT TO MAGNITUDE a_eq)
        # at the two ends of the blend window, per side, for the cubic
        # Hermite interpolation used in `cl_cd`. Important: the "left"
        # end (smaller magnitude) is always the base model (real data or
        # tangent line). The "right" end (larger magnitude) is always the
        # pure Viterna formula . This holds for both the "forward" blend
        # (with gap) and the "backward" one (without gap), which is what
        # allows treating both cases with the SAME interpolation code in
        # `cl_cd`. See the class docstring for the explanation of why
        # Hermite (only value+slope at the ends) instead of a direct
        # weighted average of the two curves: a weighted average would
        # inject the "middle" shape of the Viterna formula inside the
        # window, which is not necessarily well-behaved before the
        # anchor point itself (it can produce an artificially higher
        # Cl_max than the one defined).
        if self.has_gap_pos:
            w_lo_pos = self.alpha_edge_pos
            self._hp_y0_cl, self._hp_y0_cd = self._edge_pos_cl, self._edge_pos_cd
            self._hp_m0_cl, self._hp_m0_cd = self._edge_pos_dcl, self._edge_pos_dcd
        else:
            w_lo_pos = self.alpha_edge_pos - self.blend_width_pos
            (self._hp_y0_cl, self._hp_y0_cd,
             self._hp_m0_cl, self._hp_m0_cd) = self._base_value_slope(w_lo_pos)
        w_hi_pos = w_lo_pos + self.blend_width_pos
        (self._hp_y1_cl, self._hp_y1_cd,
         self._hp_m1_cl, self._hp_m1_cd) = self._viterna_value_slope(w_hi_pos, self._coef_pos)

        if self.has_gap_neg:
            w_lo_neg_mag = -self.alpha_edge_neg
            self._hn_y0_cl, self._hn_y0_cd = self._edge_neg_cl, self._edge_neg_cd
            # self._edge_neg_dcl/dcd are d/dalpha (real alpha, negative);
            # we need d/dmag, with mag=-alpha -> factor -1 (chain rule).
            self._hn_m0_cl, self._hn_m0_cd = -self._edge_neg_dcl, -self._edge_neg_dcd
        else:
            w_lo_neg_mag = -self.alpha_edge_neg - self.blend_width_neg
            alpha_at_lo = -w_lo_neg_mag
            y0_cl, y0_cd, m_alpha_cl, m_alpha_cd = self._base_value_slope(alpha_at_lo)
            self._hn_y0_cl, self._hn_y0_cd = y0_cl, y0_cd
            self._hn_m0_cl, self._hn_m0_cd = -m_alpha_cl, -m_alpha_cd
        w_hi_neg_mag = w_lo_neg_mag + self.blend_width_neg
        cl_v1, cd_v1, dcl_v1, dcd_v1 = self._viterna_value_slope(w_hi_neg_mag, self._coef_neg)
        # Cl on the negative side has an inverted sign relative to the
        # "positive-side-type" formula (same convention used in the pure
        # Viterna branch of `cl_cd`). Cd does not invert.
        self._hn_y1_cl, self._hn_y1_cd = -cl_v1, cd_v1
        self._hn_m1_cl, self._hn_m1_cd = -dcl_v1, dcd_v1

    def _base_cl_cd_scalar(self, alpha):
        cl, cd = self.base.cl_cd(np.array([alpha]))
        return float(cl[0]), float(cd[0])

    def _edge_tangent(self, alpha_edge: float, eps: float = 1e-3):
        """(Cl, Cd, dCl/dalpha, dCd/dalpha) of the base model at `alpha_edge`,
        with the derivative estimated by a "backward" finite difference
        pointing inward of the real data domain (toward alpha=0) . Never
        evaluates `self.base` outside the interval where it is physically
        valid. Used for the "real data" end of the blend window with a gap."""
        step = -eps if alpha_edge >= 0 else eps
        cl0, cd0 = self._base_cl_cd_scalar(alpha_edge)
        cl1, cd1 = self._base_cl_cd_scalar(alpha_edge + step)
        dcl = (cl0 - cl1) / (-step)
        dcd = (cd0 - cd1) / (-step)
        return cl0, cd0, dcl, dcd

    def _base_value_slope(self, alpha: float, eps: float = 1e-3):
        """(Cl, Cd, dCl/dalpha, dCd/dalpha) of the base model at `alpha`, with
        central derivative . Only use at points provably INSIDE the valid
        domain of the base model (never at the real data edge. For the edge,
        see `_edge_tangent`, which uses a backward difference to never leave
        the domain)."""
        cl0, cd0 = self._base_cl_cd_scalar(alpha - eps)
        cl1, cd1 = self._base_cl_cd_scalar(alpha + eps)
        clc, cdc = self._base_cl_cd_scalar(alpha)
        return clc, cdc, (cl1 - cl0) / (2 * eps), (cd1 - cd0) / (2 * eps)

    def _viterna_value_slope(self, mag: float, coeffs, eps: float = 1e-3):
        """(Cl, Cd, dCl/dmag, dCd/dmag) of the PURE Viterna formula
        ("positive-side-type" convention, before any sign flip for the
        negative side) at `mag` (magnitude, always >=0). `mag` is the
        natural argument of `_viterna_eval`, so the derivative here has no
        alpha<->magnitude swap ambiguity (unlike the base model, which is a
        function of signed alpha)."""
        cl0, cd0 = self._viterna_eval(np.array([mag]), coeffs)
        cl1, cd1 = self._viterna_eval(np.array([mag + eps]), coeffs)
        cl_m1, cd_m1 = self._viterna_eval(np.array([max(mag - eps, 0.0)]), coeffs)
        denom = eps + (mag - max(mag - eps, 0.0))
        dcl = (cl1[0] - cl_m1[0]) / denom
        dcd = (cd1[0] - cd_m1[0]) / denom
        return float(cl0[0]), float(cd0[0]), dcl, dcd

    @staticmethod
    def _hermite(x, x0, y0: float, m0: float, x1, y1: float, m1: float):
        """Cubic Hermite interpolation between (x0,y0,m0) and (x1,y1,m1) --
        matches value and slope EXACTLY at both ends (C1-continuous by
        construction), using only these 4 scalar quantities at each end
        . Never evaluates either of the two "source" curves in the middle
        of the window, which avoids importing into the blend a shape that
        is not necessarily well-behaved there (see the note in `__init__`)."""
        h = x1 - x0
        h_safe = np.where(np.abs(h) > 1e-12, h, 1.0)
        t = np.clip((x - x0) / h_safe, 0.0, 1.0)
        t2 = t * t
        t3 = t2 * t
        h00 = 2 * t3 - 3 * t2 + 1
        h10 = t3 - 2 * t2 + t
        h01 = -2 * t3 + 3 * t2
        h11 = t3 - t2
        return h00 * y0 + h10 * h * m0 + h01 * y1 + h11 * h * m1

    def _viterna_coeffs(self, cl_s, cd_s, alpha_s):
        """alpha_s > 0 here (magnitude). See Viterna & Janetzke (1982) eqs.
        A1=Cdmax/2, B1=Cdmax, A2,B2 fitted to match (Cl_s,Cd_s) at alpha_s."""
        s, c = np.sin(alpha_s), np.cos(alpha_s)
        A1 = self.cd_max / 2.0
        B1 = self.cd_max
        A2 = (cl_s - self.cd_max * s * c) * s / max(c ** 2, 1e-6)
        # NOTE: secondary literature sometimes transcribes this formula
        # with "Cl_stall" instead of "Cd_stall" (a common transcription
        # error, including in some peer-reviewed papers). The physically
        # correct form . The one implemented here . Uses Cd_stall, since
        # it is the drag equation being fitted.
        B2 = (cd_s - self.cd_max * s ** 2) / max(c, 1e-6)
        return A1, A2, B1, B2

    @staticmethod
    def _viterna_eval(alpha_mag, coeffs):
        A1, A2, B1, B2 = coeffs
        s, c = np.sin(alpha_mag), np.cos(alpha_mag)
        cl = A1 * np.sin(2 * alpha_mag) + A2 * (c ** 2) / np.maximum(s, 1e-6)
        cd = B1 * s ** 2 + B2 * c
        return cl, cd

    def cl_cd(self, alpha: np.ndarray, mach: Optional[np.ndarray] = None, r_norm=None):
        if self._multi_section:
            return self._cl_cd_multi_section(alpha, mach, r_norm)

        scalar_input = np.ndim(alpha) == 0
        a = np.atleast_1d(np.asarray(alpha, dtype=float))
        # wrap to (-pi, pi]
        a = np.mod(a + np.pi, 2 * np.pi) - np.pi

        cl = np.zeros_like(a)
        cd = np.zeros_like(a)

        # Reduces any alpha in (-180,180] to an "equivalent angle" a_eq in
        # [0, 90] plus a sign, handling the mirror symmetry around
        # +-90 (geometric trailing edge turning to "face" the flow). This
        # guarantees the SAME attached-vs-Viterna criterion is applied both
        # near alpha=0 and near alpha=+-180, eliminating the discontinuity
        # that a naive Viterna formula would have near the "mirrored 0"
        # (1/sin(alpha) singularity).
        sign = np.sign(a)
        sign[sign == 0] = 1.0
        a_abs = np.abs(a)
        mirrored = a_abs > np.pi / 2
        a_eq = np.where(mirrored, np.pi - a_abs, a_abs)   # always in [0, 90]
        cl_extra_sign = np.where(mirrored, -1.0, 1.0)      # Cl inverts on mirroring

        is_pos_like = sign > 0
        edge_mag = np.where(is_pos_like, self.alpha_edge_pos, -self.alpha_edge_neg)
        width = np.where(is_pos_like, self.blend_width_pos, self.blend_width_neg)
        has_gap = np.where(is_pos_like, self.has_gap_pos, self.has_gap_neg)

        # Blend window: [edge_mag, edge_mag+width] when there is a gap
        # ("forward" blend, extrapolating beyond the last real data point --
        # see the Note above), or [edge_mag-width, edge_mag] when there is
        # no gap ("backward" blend, ending exactly at the anchor, so the Cl
        # peak falls at alpha_stall and not after it).
        window_lo = np.where(has_gap, edge_mag, edge_mag - width)
        window_hi = np.where(has_gap, edge_mag + width, edge_mag)

        # 1) attached / real data: uses the base model DIRECTLY (+a_eq or
        # -a_eq, per the original side, before mirroring) . Never
        # overwrites anything that actually exists in the table/base model.
        # With a gap, goes up to the real edge (window_lo==edge_mag);
        # without a gap, only up to the start of the blend window
        # (window_lo==edge_mag-width), since the final stretch before the
        # anchor is now part of the blend.
        attached = a_eq <= window_lo
        if np.any(attached):
            alpha_for_base = np.where(is_pos_like[attached], a_eq[attached], -a_eq[attached])
            cl_b, cd_b = self.base.cl_cd(alpha_for_base, mach, r_norm)
            cl[attached] = cl_extra_sign[attached] * cl_b
            cd[attached] = cd_b

        # 2) C1-continuous blend, inside [window_lo, window_hi]: cubic
        # HERMITE interpolation between the values/slopes pre-computed at
        # the two ends (`_hp_*`/`_hn_*`, see `__init__`) . Matches EXACTLY
        # value and slope with the base model at one end and with Viterna
        # at the other, without ever evaluating either of the two "source"
        # formulas in the middle of the window (which could import into
        # the blend a badly-behaved shape (for example "raw" Viterna before its
        # own anchor point , see the class docstring).
        blending = (~attached) & (a_eq <= window_hi)
        if np.any(blending):
            a_eq_b = a_eq[blending]
            is_pos_b = is_pos_like[blending]
            w_lo_b = window_lo[blending]
            w_hi_b = window_hi[blending]

            cl_local = np.empty_like(a_eq_b)
            cd_local = np.empty_like(a_eq_b)
            if np.any(is_pos_b):
                idx = is_pos_b
                cl_local[idx] = self._hermite(a_eq_b[idx], w_lo_b[idx], self._hp_y0_cl, self._hp_m0_cl,
                                               w_hi_b[idx], self._hp_y1_cl, self._hp_m1_cl)
                cd_local[idx] = self._hermite(a_eq_b[idx], w_lo_b[idx], self._hp_y0_cd, self._hp_m0_cd,
                                               w_hi_b[idx], self._hp_y1_cd, self._hp_m1_cd)
            if np.any(~is_pos_b):
                idx = ~is_pos_b
                cl_local[idx] = self._hermite(a_eq_b[idx], w_lo_b[idx], self._hn_y0_cl, self._hn_m0_cl,
                                               w_hi_b[idx], self._hn_y1_cl, self._hn_m1_cl)
                cd_local[idx] = self._hermite(a_eq_b[idx], w_lo_b[idx], self._hn_y0_cd, self._hn_m0_cd,
                                               w_hi_b[idx], self._hn_y1_cd, self._hn_m1_cd)

            cl[blending] = cl_extra_sign[blending] * cl_local
            cd[blending] = cd_local

        # 3) pure Viterna-Corrigan, beyond the blend window
        viscous = (~attached) & (~blending)
        if np.any(viscous):
            v_pos = viscous & is_pos_like
            v_neg = viscous & ~is_pos_like
            if np.any(v_pos):
                cl_v, cd_v = self._viterna_eval(a_eq[v_pos], self._coef_pos)
                cl[v_pos] = cl_extra_sign[v_pos] * cl_v
                cd[v_pos] = cd_v
            if np.any(v_neg):
                cl_v, cd_v = self._viterna_eval(a_eq[v_neg], self._coef_neg)
                cl[v_neg] = -cl_extra_sign[v_neg] * cl_v
                cd[v_neg] = cd_v

        cd = np.maximum(cd, 0.0)
        out_shape = np.shape(alpha) if not scalar_input else ()
        if scalar_input:
            return float(cl[0]), float(cd[0])
        return cl.reshape(out_shape), cd.reshape(out_shape)

    def _cl_cd_multi_section(self, alpha, mach, r_norm):
        """Evaluates each child `ViternaExtendedAirfoil` (one per radial
        section, each with its OWN Viterna extrapolation anchored on that
        section's Cl_stall/Cd_stall) and interpolates in r_norm between
        neighboring sections . Same mechanics as
        `MultiSectionTableAirfoil.cl_cd`."""
        if r_norm is None:
            raise ValueError("ViternaExtendedAirfoil (multi-section base) requires r_norm "
                              "(same shape as alpha).")
        scalar_input = np.ndim(alpha) == 0
        a = np.atleast_1d(np.asarray(alpha, dtype=float))
        r = np.atleast_1d(r_norm) * np.ones_like(a)
        mach_arr = None if mach is None else np.atleast_1d(mach) * np.ones_like(a)

        # Cl/Cd of each section, evaluated at the requested alpha (each
        # child already resolves attached-vs-Viterna-vs-mirrored on its own,
        # with its own stall anchor): shape (Nsec, Npts)
        cl_per_sec = np.empty((len(self._section_children), a.size))
        cd_per_sec = np.empty((len(self._section_children), a.size))
        for i, child in enumerate(self._section_children):
            cl_i, cd_i = child.cl_cd(a.ravel(), None if mach_arr is None else mach_arr.ravel())
            cl_per_sec[i] = cl_i
            cd_per_sec[i] = cd_i

        cl = np.empty(a.size)
        cd = np.empty(a.size)
        for k in range(a.size):
            cl.flat[k] = np.interp(r.flat[k], self._section_r_norms, cl_per_sec[:, k])
            cd.flat[k] = np.interp(r.flat[k], self._section_r_norms, cd_per_sec[:, k])
        cd = np.maximum(cd, 0.0)

        if scalar_input:
            return float(cl[0]), float(cd[0])
        out_shape = np.shape(alpha)
        return cl.reshape(out_shape), cd.reshape(out_shape)


# =============================================================================
# 2. ROTOR GEOMETRY
# =============================================================================

@dataclass
class Rotor:
    R: float                       # radius [m]
    Nb: int                        # number of blades
    Omega_rpm: float                # rotation [RPM]
    r_root_norm_geom: float         # geometric root cutout (r/R)
    r_tip_norm_geom: float          # geometric tip (r/R), usually 1.0
    r_geom: np.ndarray               # r/R sampled from the blade geometry
    chord_geom: np.ndarray           # chord [m] at r_geom
    theta_geom_deg: np.ndarray       # twist [deg] at r_geom

    @property
    def Omega(self) -> float:
        return self.Omega_rpm * 2 * np.pi / 60.0

    @property
    def OmegaR(self) -> float:
        return self.Omega * self.R

    def chord_theta_at(self, r_norm: np.ndarray):
        fc = interp1d(self.r_geom, self.chord_geom, kind="linear", fill_value="extrapolate")
        ft = interp1d(self.r_geom, self.theta_geom_deg, kind="linear", fill_value="extrapolate")
        return fc(r_norm), np.deg2rad(ft(r_norm))


# =============================================================================
# 3. (BEMT SOLVER CONFIGURATION , see `BEMTConfig` at the TOP of the file,
#    right after the imports. All physical-model variables (on/off)
#    are concentrated there.)
# =============================================================================

# =============================================================================
# 4. BLADE ELEMENT PHYSICS (fully vectorized over (Ne,Npsi))
# =============================================================================

def _inflow_harmonics(model: str, mu_x: float, lambda_total: np.ndarray):
    """Linear inflow coefficients (Coleman / Drees). mu_x is scalar (one
    flight condition per call to solve_bemt). Lambda_total can be an
    array ('local' mode) or scalar ('global' mode)."""
    model = model.lower()
    if model == "glauert":
        return np.zeros_like(lambda_total), np.zeros_like(lambda_total)
    if abs(mu_x) < 1e-5:
        return np.zeros_like(lambda_total), np.zeros_like(lambda_total)
    # Preserves the SIGN of lambda_total/mu_x (instead of using
    # |lambda_total/mu_x|): this keeps the physical asymmetry between climb
    # and descent in the wake angle: descent (lambda_total<0) and climb
    # have opposite wake tilts, and an absolute value would collapse that
    # difference.
    ratio = lambda_total / mu_x
    if model == "coleman":
        Kx = np.sqrt(1 + ratio ** 2) - ratio
        Ky = np.zeros_like(Kx)
        return Kx, Ky
    if model == "drees":
        Kx = (4.0 / 3.0) * ((1 - 1.8 * mu_x ** 2) * np.sqrt(1 + ratio ** 2) - ratio)
        Ky = np.full_like(Kx, -2.0 * mu_x)
        return Kx, Ky
    raise ValueError(f"Unknown inflow_model: {model}")


# =============================================================================
# 3b. RESOLUTION TABLE FOR `BEMTConfig.inflow_field_model` (Section 3.2 of
#     docs/plano_v2.md) . Single source of truth that translates the
#     public enum back to the two internal physical axes (harmonic +
#     coupling + whether it is the unsteady variant). `harmonic=None`
#     signals that Pitt-Peters solves its own harmonics (does not call
#     `_inflow_harmonics`). `unsteady=True` signals that `solve_bemt`
#     does not handle this case . It is solved by
#     `run_sweep_unsteady_pitt_peters`.
# =============================================================================
_INFLOW_FIELD_MODELS: dict[str, dict] = {
    "glauert_local":        dict(harmonic="glauert", coupling="local",       unsteady=False),
    "glauert_global":       dict(harmonic="glauert", coupling="global",      unsteady=False),
    "coleman_local":        dict(harmonic="coleman", coupling="local",       unsteady=False),
    "coleman_global":       dict(harmonic="coleman", coupling="global",      unsteady=False),
    "drees_local":          dict(harmonic="drees",   coupling="local",       unsteady=False),
    "drees_global":         dict(harmonic="drees",   coupling="global",      unsteady=False),
    "pitt_peters_steady":   dict(harmonic=None,       coupling="pitt_peters", unsteady=False),
    "pitt_peters_unsteady": dict(harmonic=None,       coupling="pitt_peters", unsteady=True),
}


def _resolve_inflow_field_model(name: str) -> dict:
    spec = _INFLOW_FIELD_MODELS.get(name)
    if spec is None:
        raise ValueError(
            f"Unknown inflow_field_model: {name!r}. Options: "
            f"{list(_INFLOW_FIELD_MODELS)}."
        )
    return spec


def _smoothstep(x, edge0, edge1):
    """C1-continuous Hermite smoothstep: 0 for x<=edge0, 1 for x>=edge1,
    smooth transition (zero derivative at the edges) between the two."""
    t = np.clip((x - edge0) / (edge1 - edge0), 0.0, 1.0)
    return t * t * (3.0 - 2.0 * t)


def _airfoil_cl_alpha_alpha0(airfoil, r_norm=None):
    """Extracts (Cl_alpha, alpha0) [rad] from the airfoil object, with a
    generic fallback for tabulated models that do not expose them
    explicitly. Used by the Himmelskamp/Snel rotational correction and by
    the Øye dynamic stall (both need the fully attached, stall-free lift
    line).

    For a multi-section airfoil (`r_norm` given AND the object exposes
    `cl_alpha_alpha0_field`, see `MultiSectionTableAirfoil`/
    `HeterogeneousMultiSectionAirfoil` above), returns arrays (same shape
    as `r_norm`) interpolated PER SECTION instead of a single
    representative scalar pair . This is what makes the dynamic stall
    and the rotational correction vary section by section."""
    field_fn = getattr(airfoil, "cl_alpha_alpha0_field", None)
    if r_norm is not None and field_fn is not None:
        cl_alpha, alpha0 = field_fn(r_norm)
        return np.asarray(cl_alpha, dtype=float), np.asarray(alpha0, dtype=float)
    cl_alpha = getattr(airfoil, "cl_alpha", 2 * np.pi)
    alpha0 = getattr(airfoil, "alpha0", 0.0)
    return float(cl_alpha), float(alpha0)


def apply_reverse_flow_to_polar(Cl, Cd, alpha_geom, reverse, cfg: BEMTConfig):
    """Cl/Cd post-processing that the reverse-flow model applies AFTER
    querying the airfoil polar.

    Extracted from `element_state` to be the ONLY implementation: the
    polar preview in the Airfoil tab (`airfoils.preview_polar`) calls
    exactly this function, so the Cl(alpha)/Cd(alpha) curve drawn on screen
    is the same one the engine consumes. Previously, the preview only
    called `airfoil.cl_cd()` and stopped there . Changing
    `reverse_flow_model` changed NOTHING in the plot, even though it
    changed what the BEMT computed, and there was no way to see on screen
    the difference between 'flat_plate' and 'thin_plate_blend'.

    `reverse` is the boolean map Ut<0 (reverse regime). Only
    `thin_plate_blend` does not use it: its blend weight is a smooth
    function of |alpha_geom| alone, which is precisely what makes it
    continuous at Ut=0 (see the note in `element_state`).

    `viterna_full_range` and `alpha_blending` do not appear here because
    they do not post-process Cl/Cd . They act only on `alpha_eff`/`Mach`,
    before the polar query."""
    rfm = cfg.reverse_flow_model.lower()
    if rfm == "flat_plate":
        Cl = np.where(reverse, 0.0, Cl)
        Cd = np.where(reverse, 1.9, Cd)
    elif rfm == "simple_flip":
        Cd = np.where(reverse, np.abs(Cd), Cd)
    elif rfm == "thin_plate_blend":
        Cl_fp = np.pi * np.sin(alpha_geom) * np.cos(alpha_geom)
        Cd_fp = 2.0 * np.sin(alpha_geom) ** 2
        edge0 = np.deg2rad(cfg.thin_plate_blend_center_deg - 0.5 * cfg.thin_plate_blend_width_deg)
        edge1 = np.deg2rad(cfg.thin_plate_blend_center_deg + 0.5 * cfg.thin_plate_blend_width_deg)
        w_fp = _smoothstep(np.abs(alpha_geom), edge0, edge1)
        Cl = (1.0 - w_fp) * Cl + w_fp * Cl_fp
        Cd = (1.0 - w_fp) * Cd + w_fp * Cd_fp
    return Cl, Cd


#: The reverse-flow models that `reverse_flow_alpha_eff` /
#: `apply_reverse_flow_to_polar` implement. This is the SINGLE SOURCE of the list.
#: The Airfoil tab populates the dropdown from here, and a test requires
#: that the field help explain all of them: the popup used to explain 3
#: of the 5 precisely because each surface kept its own list.
#: `viterna_full_range` is the only conditional one (requires the full
#: range extension enabled), and that condition lives in the GUI, not
#: here.
REVERSE_FLOW_MODELS = ("simple_flip", "flat_plate", "alpha_blending",
                        "thin_plate_blend", "viterna_full_range")

#: Value of ``Ut/(Omega*r)`` used by the polar PREVIEW (Airfoil tab)
#: to draw the reverse branch of `alpha_blending`. A static polar is a
#: function of alpha only, and the `alpha_blending` factor depends on
#: Ut . There is no single curve. -1 is the DEEPEST point of the reverse
#: region (the rotor axis, where |Ut| is already of order Omega*r): the
#: saturated limit, which is the worst case and the one compared against
#: the other models. Near the boundary (Ut->0) the factor tends to 0 and
#: so does alpha_eff . The preview has no way to show this, and it is
#: stated in the `airfoils.preview_polar` docstring.
UT_NORMALIZADO_DE_PREVIA = -1.0


def reverse_flow_alpha_eff(alpha_geom, reverse, cfg: BEMTConfig, ut_norm=None):
    """``alpha_eff`` (the angle at which the polar is queried) from
    ``alpha_geom = THETA - phi``, according to `cfg.reverse_flow_model`.

    Extracted from `element_state` for the same reason as
    `apply_reverse_flow_to_polar`: to be the ONLY implementation. The five
    models act in TWO different places: `flat_plate`/`simple_flip`/
    `thin_plate_blend` post-process Cl/Cd (that function),
    `viterna_full_range`/`alpha_blending` change the angle (this one) --,
    and the Airfoil tab preview only called the former. Consequence seen
    on screen: switching to `viterna_full_range` or `alpha_blending`
    changed NOTHING in the plot, even though it changed what the engine
    computed. Now the preview calls both, and the five models are
    distinguishable in the reverse branch.

    ``ut_norm``: ``Ut/(Omega*r)``, used only by `alpha_blending` (the only
    model whose angle depends on SPEED, not just alpha). If omitted,
    assumes the saturated limit of the reverse region
    (`UT_NORMALIZADO_DE_PREVIA`), which is what a static polar can
    represent."""
    rfm = cfg.reverse_flow_model.lower()
    if rfm == "viterna_full_range":
        # phi=atan2(Up,Ut) is already continuous over the WHOLE range
        # (including Ut<0). With a polar continuous over -180..180
        # (ViternaExtendedAirfoil) no branch is needed at all . See the
        # long comment in `element_state`, Section 1b.
        return np.mod(alpha_geom + np.pi, 2 * np.pi) - np.pi
    if rfm in ("simple_flip", "flat_plate"):
        return np.where(reverse, -alpha_geom, alpha_geom)
    if rfm == "alpha_blending":
        if ut_norm is None:
            ut_norm = np.where(reverse, UT_NORMALIZADO_DE_PREVIA, 1.0)
        return np.where(reverse, alpha_geom * np.tanh(cfg.reverse_flow_blend_factor * ut_norm),
                         alpha_geom)
    if rfm == "thin_plate_blend":
        # No np.where(reverse, ...) at ALL: alpha_geom is already
        # continuous through Ut=0, and it is `apply_reverse_flow_to_polar`
        # that blends in the flat plate, by |alpha_geom|.
        return alpha_geom
    raise ValueError(f"Unknown reverse_flow_model: {cfg.reverse_flow_model}")


def element_state(lambda_i, R_NORM, PSI, R_DIM, CHORD, THETA, mu_x, lambda_z,
                   Nb, Omega, OmegaR, airfoil, cfg: BEMTConfig,
                   r_root_norm_geom, r_tip_norm_geom, motion=None):
    """Evaluates the aerodynamic state/forces of ALL elements (Ne,Npsi)
    for a given lambda_i field, and also returns lambda_i_next (the
    fixed-point map of the momentum/BET equation) used by the solvers.

    ``motion`` (optional): the rigid-blade flap/lag state (SC-11), as a
    dictionary with the arrays ``beta``, ``beta_rate`` and ``zeta_rate``
    on the same (Ne,Npsi) grid, plus the scalars ``e_hinge_dim`` (hinge
    offset in metres), ``pitch_flap_K`` (= tan(delta_3)),
    ``cyclic_c_rad`` and ``cyclic_s_rad`` (the 1/rev cyclic pitch, in
    radians). ``None`` (the default) is the rigid disk, unchanged.

    The motion adds three terms to the local flow:

        U_P += (r - e*R)*beta_dot + V_inf*beta*cos(psi)
        U_T += (r - e*R)*zeta_dot
        theta_eff = theta(r) + theta_1c*cos(psi) + theta_1s*sin(psi)
                    - K_p*beta

    Small angles throughout: cos(beta) ~= 1 and sin(beta) ~= beta, so the
    blade element stays in the disk plane for area and arm. W, phi,
    reverse and every downstream model are built from Up/Ut AFTER these
    terms, so the motion reaches the whole aerodynamics with no other
    edit; the reverse-flow branch itself is untouched."""
    rho, a_sound = cfg.rho, cfg.a_sound
    Vinf = mu_x * OmegaR

    # Sideslip (SC-14): rotates the IN-PLANE free-stream direction; the
    # axial component is untouched. 0 deg keeps every legacy result.
    psi_w = np.deg2rad(float(getattr(cfg, "inflow_sideslip_deg", 0.0)))

    lambda_total = lambda_z + lambda_i
    Up = lambda_total * OmegaR
    Ut = Omega * R_DIM + Vinf * np.sin(PSI - psi_w)
    if motion is not None:
        arm = np.maximum(R_DIM - motion["e_hinge_dim"], 0.0)
        Up = Up + arm * motion["beta_rate"] + Vinf * motion["beta"] * np.cos(PSI)
        Ut = Ut + arm * motion["zeta_rate"]
        # Hub angular rates (SC-14): a pitching/rolling hub carries each
        # element out of the disk plane. r*(q*cos(psi) - p*sin(psi)),
        # with r the dimensional station radius.
        p_rate = float(motion.get("p_rate", 0.0))
        q_rate = float(motion.get("q_rate", 0.0))
        if p_rate != 0.0 or q_rate != 0.0:
            Up = Up + R_DIM * (q_rate * np.cos(PSI) - p_rate * np.sin(PSI))
        # Cyclic pitch varies with azimuth, so it cannot live on the
        # twist vector: it rebinds the LOCAL THETA here. Pitch-flap
        # coupling (delta-3): an up-flapping blade pitches down by
        # K_p*beta.
        THETA = (THETA
                 + motion["cyclic_c_rad"] * np.cos(PSI)
                 + motion["cyclic_s_rad"] * np.sin(PSI)
                 - motion["pitch_flap_K"] * motion["beta"])
    W = np.maximum(np.sqrt(Up ** 2 + Ut ** 2), 0.1)

    reverse = Ut < 0.0
    phi = np.arctan2(Up, Ut)
    phi_rev = np.arctan2(Up, -Ut)
    alpha_geom = THETA - phi

    # The effective ANGLE comes from `reverse_flow_alpha_eff` (the only
    # implementation, shared with the GUI's polar preview). MACH stays
    # here because only the two models with a Ut<0 branch swap the
    # reference speed (|Ut| instead of W) . The other three have no
    # branch at all, which is precisely what defines them.
    rfm = cfg.reverse_flow_model.lower()
    alpha_eff = reverse_flow_alpha_eff(
        alpha_geom, reverse, cfg, ut_norm=Ut / (Omega * R_DIM + 1e-6))
    if rfm in ("simple_flip", "flat_plate"):
        Mach = np.where(reverse, np.abs(Ut) / a_sound, W / a_sound)
    else:
        Mach = W / a_sound

    Cl, Cd = airfoil.cl_cd(alpha_eff, Mach, r_norm=R_NORM)
    Cl = np.asarray(Cl, dtype=float)
    Cd = np.asarray(Cd, dtype=float)

    Cl, Cd = apply_reverse_flow_to_polar(Cl, Cd, alpha_geom, reverse, cfg)

    # --- Himmelskamp / Snel: rotational stall delay (Cl only) ---------------
    # Near stall, blade rotation pumps the boundary layer radially outward;
    # the resulting Coriolis force delays separation and produces a higher
    # Cl than the airfoil's static 2D Cl . A stronger effect near the
    # root (where c/r is larger) and more noticeable at low mu_x/hover,
    # when the root operates near stall.
    # Formulation (Snel et al., 1993), affects only Cl (Cd does not change):
    #   Cl_3D = Cl_2D + 3.1*lam_r^2/(1+lam_r^2) * g(alpha) * (c/r)^2 *
    #           (Cl_alpha*(alpha-alpha0) - Cl_2D)
    # lam_r is the ratio of rotational speed (Omega*r) to the axial
    # "washing" speed of the boundary layer. Snel's original formulation
    # uses lam_r=Omega*r/V0 with V0 = uniform free wind (wind turbine, a
    # single global scalar). Here, without a single V0 (the rotor can be
    # in any advance/climb regime), lam_r=Omega*r/|Up| is used . Up is
    # the out-of-disk-plane flow component AT THAT element
    # (induced+climb), which is the direct physical analogue of the axial
    # wind that washes the radially pumped boundary layer. This
    # definition reduces exactly to the original one in purely
    # axisymmetric flight (hover/climb).
    if cfg.use_rotational_augmentation:
        cl_alpha_af, alpha0_af = _airfoil_cl_alpha_alpha0(airfoil, r_norm=R_NORM)
        lam_r = (Omega * R_DIM) / np.maximum(np.abs(Up), 1e-3 * OmegaR)
        c_over_r = CHORD / np.maximum(R_DIM, 1e-6)
        alpha_deg = np.degrees(np.abs(alpha_eff))
        g_blend = np.where(alpha_deg <= 30.0, 1.0,
                    np.where(alpha_deg <= 60.0,
                             0.5 * (1.0 + np.cos(np.deg2rad(6.0 * alpha_deg - 180.0))),
                             0.0))
        Cl_att = cl_alpha_af * (alpha_eff - alpha0_af)
        snel_term = (3.1 * lam_r ** 2 / (1.0 + lam_r ** 2)) * g_blend * c_over_r ** 2
        Cl = Cl + snel_term * (Cl_att - Cl)

    # --- Radial flow / independence principle (ISAE, Cd only) ---------------
    # In forward flight, besides the in-plane section flow (Up,Ut) there
    # is a flow component ALONG the blade span (radial),
    # UR = Vinf*cos(psi), MAXIMUM at psi=0/180deg (the blade points along
    # the free stream, which there is entirely radial) and ZERO at
    # psi=90/270deg, where the flow is all tangential and goes entirely
    # into Ut (which uses sin(psi)). The swept-wing "independence
    # principle" states that only the flow component NORMAL to the span
    # (here, the pair Up,Ut) determines lift, but profile drag is
    # sensitive to the total flow . So only Cd is corrected, evaluating
    # the polar at a "skewed" angle alpha*cos(lambda_y), where
    # lambda_y=atan(UR/Ut) is the angle between the radial and tangential
    # components. Cl remains unchanged.
    if cfg.use_radial_flow_correction:
        UR = Vinf * np.cos(PSI - psi_w)
        Ut_safe = np.where(np.abs(Ut) < 1e-3 * OmegaR, np.sign(Ut) * 1e-3 * OmegaR + 1e-6, Ut)
        max_skew = np.deg2rad(cfg.radial_flow_max_skew_deg)
        lambda_y = np.clip(np.arctan(UR / Ut_safe), -max_skew, max_skew)
        alpha_y = alpha_eff * np.cos(lambda_y)
        _, Cd_y = airfoil.cl_cd(alpha_y, Mach, r_norm=R_NORM)
        Cd = np.asarray(Cd_y, dtype=float)

    if cfg.use_compressibility:
        # Floor on beta, not a cutoff near zero. See
        # `MACH_MAXIMO_DE_PRANDTL_GLAUERT`: the 1/beta factor is clamped
        # to the value at the documented Mach ceiling, instead of
        # diverging.
        beta = np.maximum(np.sqrt(np.maximum(0.0, 1.0 - Mach ** 2)),
                          BETA_MINIMO_DE_PRANDTL_GLAUERT)
        Cl = Cl / beta
        Cd = Cd / beta
        if rfm == "simple_flip":
            Cd = np.where(reverse, np.abs(Cd), Cd)
    Cd = np.maximum(Cd, 0.0)

    Lift = 0.5 * rho * W ** 2 * CHORD * Cl
    Drag = 0.5 * rho * W ** 2 * CHORD * Cd

    if rfm == "viterna_full_range":
        # --- Single formulas, continuous over the whole disk (see Section 1b) --
        # phi=atan2(Up,Ut) already correctly covers reverse flow (Cl/Cd
        # already carry the correct physical sign via
        # ViternaExtendedAirfoil), so there is NO phi/phi_rev branch nor
        # sign_use here . The same 3 formulas hold in any regime, with no
        # discontinuity at Ut=0.
        Fn = Lift * np.cos(phi) - Drag * np.sin(phi)
        Ft_i = Lift * np.sin(phi)
        Ft_p = Drag * np.cos(phi)
        Ft = Ft_i + Ft_p
    else:
        # --- Normal force (thrust) ---
        Fn = np.where(reverse,
                      Lift * np.cos(phi_rev) + Drag * np.sin(phi_rev),
                      Lift * np.cos(phi) - Drag * np.sin(phi))

        # --- Tangential force: Ft = Ft_i + Ft_p ALWAYS ---------------------
        # Ft_i (induced part, tied to Lift*sin) and Ft_p (profile part,
        # tied to Drag*cos) must use the SAME angle phi_use that builds
        # Ft. Otherwise, Ft_i+Ft_p stops matching the Ft computed above
        # (the sum of the two parts must reconstruct exactly the total
        # force, in any regime, direct or reverse).
        phi_use = np.where(reverse, phi_rev, phi)
        sign_use = np.where(reverse, -1.0, 1.0)
        Ft_i = Lift * np.sin(phi_use)
        Ft_p = sign_use * Drag * np.cos(phi_use)
        Ft = Ft_i + Ft_p

    # --- Prandtl loss factor (tip + root) ---
    # f = (Nb/2)*(distance to the edge)/(x*|sin(phi)|). The x in the
    # denominator is the spacing between helical vortex sheets, which grows
    # with radius: s = 2*pi*x*sin(phi)/Nb.
    #
    # Both factors are always computed. `cfg.prandtl_loss_mode` only selects
    # which of them is applied.
    abs_sin_phi = np.maximum(np.abs(np.sin(phi)), 1e-6)
    espacamento = np.maximum(R_NORM, 1e-6) * abs_sin_phi
    f_tip = np.maximum(-(Nb / 2.0) * (r_tip_norm_geom - R_NORM) / espacamento, -50.0)
    F_tip = np.clip((2.0 / np.pi) * np.arccos(np.clip(np.exp(f_tip), -1.0, 1.0)), 0.01, 1.0)
    F_tip = np.nan_to_num(F_tip, nan=0.01)
    f_root = np.maximum(-(Nb / 2.0) * (R_NORM - r_root_norm_geom) / espacamento, -50.0)
    F_root = np.clip((2.0 / np.pi) * np.arccos(np.clip(np.exp(f_root), -1.0, 1.0)), 0.01, 1.0)
    F_root = np.nan_to_num(F_root, nan=0.01)
    F_ones = np.ones_like(R_NORM, dtype=float) if isinstance(R_NORM, np.ndarray) else 1.0
    _F_BY_MODE = {
        "off": F_ones,
        "tip": F_tip,
        "root": F_root,
        "both": np.nan_to_num(F_tip * F_root, nan=1.0),
    }
    F = _F_BY_MODE.get(cfg.prandtl_loss_mode, _F_BY_MODE["both"])

    # --- Momentum equation (ring), with optional harmonic correction ---
    # `harmonic_family` is None for the Pitt-Peters variants
    # (docs/plano_v2.md Section 3.2): that coupling solves its own
    # harmonics from the actuator-disk physics, so skipping
    # `_inflow_harmonics` here is not just an optimization . It is what
    # makes "Pitt-Peters ignores the empirical harmonic" true by
    # construction, not just by documentation (the computation used to be
    # done and discarded in that case before).
    harmonic_family = _resolve_inflow_field_model(cfg.inflow_field_model)["harmonic"]
    if harmonic_family is not None:
        Kx, Ky = _inflow_harmonics(harmonic_family, mu_x, lambda_total)
    else:
        Kx, Ky = np.zeros_like(lambda_total), np.zeros_like(lambda_total)
    # Sideslip (SC-14): the empirical fore-aft/lateral gains Kx/Ky follow
    # the WAKE skew, so their azimuthal pattern rotates with the free
    # stream -- cos(psi - psi_w)/sin(psi - psi_w). With psi_w = 0 this is
    # the unchanged legacy expression.
    psi_w = np.deg2rad(float(getattr(cfg, "inflow_sideslip_deg", 0.0)))
    harmonic = (1.0 + Kx * R_NORM * np.cos(PSI - psi_w)
                 + Ky * R_NORM * np.sin(PSI - psi_w))

    denom = rho * 4.0 * np.pi * R_DIM * np.sqrt(lambda_total ** 2 + mu_x ** 2 + 1e-6) * OmegaR ** 2 * F
    denom_safe = np.where(np.abs(denom) < 1e-8, 1.0, denom)
    raw_next = (Nb * Fn * harmonic) / denom_safe
    lambda_i_next = np.where((np.abs(denom) < 1e-8) | (F < 0.015), 0.0, raw_next)
    lambda_i_next = np.clip(lambda_i_next, -0.5, 0.5)

    out = dict(Up=Up, Ut=Ut, W=W, phi=phi, phi_rev=phi_rev, reverse=reverse,
                alpha_eff=alpha_eff, Mach=Mach, Cl=Cl, Cd=Cd, Lift=Lift, Drag=Drag,
                Fn=Fn, Ft=Ft, Ft_i=Ft_i, Ft_p=Ft_p, F=F, lambda_total=lambda_total,
                lambda_i_next=lambda_i_next)
    if motion is not None:
        # Echoed for `aggregate_results` and the plots: the blade state
        # that produced the loads, on the same (Ne,Npsi) grid. A rigid
        # run (motion=None) reports nothing new.
        out["beta"] = motion["beta"]
        out["beta_rate"] = motion["beta_rate"]
        out["zeta_rate"] = motion["zeta_rate"]
    return out


# =============================================================================
# 4g. ØYE DYNAMIC STALL (vectorized post-processing over an already
#     converged lambda_i)
# =============================================================================
#
# Physical motivation: near stall, boundary-layer separation does not
# respond instantaneously to a change in angle of attack . There is a
# lag (boundary-layer response time). In forward flight, the angle of
# attack of each blade element varies continuously with azimuth (psi), so
# the blade can be "crossing" the stall condition too fast for separation
# to keep up in quasi-steady regime . The real Cl ends up higher than the
# polar's static Cl (and the eventual separation, when it finally occurs,
# is more abrupt). The Øye model captures this with a single state
# variable per element, the "separation function" f (fraction of the
# chord still attached to the flow, between 0=fully separated and
# 1=fully attached), which relaxes toward its quasi-steady value
# f_st(alpha) with time constant tau proportional to the chord and
# inversely proportional to the relative speed (the faster the flow, the
# faster the boundary layer reacts).
#
# It is applied as post-processing ON TOP of the already converged
# lambda_i field (recomputes only Cl/Cd/forces from the final mesh,
# without feeding back into the momentum equation) . Standard engineering
# practice to avoid coupling a history state inside the inflow
# fixed-point solver.
#
# Reference: S. Øye, "Dynamic stall simulated as time lag of separation",
# 1991. Bergami's dynamic-Cd formulation, as documented at
# https://docs.qblade.org/src/theory/aerodynamics/dynamic_stall/OYE_stall.html
#
# Equations (all per element (r,psi), fully vectorized in NumPy):
#
#   Cl_att(alpha)   = Cl_alpha * (alpha - alpha0)         [attached line, no stall]
#   f_st            = clip( (2*sqrt(max(Cl_st/Cl_att,0)) - 1)^2 , 0, 1 )
#   df/dt           = (f_st - f) / tau                    [linear ODE in f]
#   tau             = A * c / (2*Vrel)                     [A~8, Øye/QBlade]
#   Cl_sep          = (Cl_st - f_st*Cl_att) / (1 - f_st)   [regularized near f_st->1]
#   Cl_dyn          = f*Cl_att + (1-f)*Cl_sep
#   Cd_dyn          = Cd_st + (Cd_st-Cd0)*[0.5*(sqrt(f_st)-sqrt(f)) - 0.25*(f-f_st)]
#
# where Cd0 is the static Cd at alpha=0 (same section/airfoil).
#
# The model is only valid for |alpha| approximately <=50 deg (QBlade
# "smoothly fades toward the static polar" in that range) . Reproduced
# here via `_dynamic_stall_fade_weight` (smoothstep between
# fade_start_deg and fade_end_deg).

def _oye_static_separation(alpha_eff: np.ndarray, Cl_st: np.ndarray,
                            cl_alpha: float, alpha0: float, reg: float):
    """Computes f_st(alpha) (static separation function) and Cl_att
    (fully attached, extrapolated lift line), following Hansen (2004) as
    cited in the Øye/QBlade doc. `reg` avoids a singularity in
    (1-f_st)->0 further downstream (in `_oye_cl_sep`)."""
    Cl_att = cl_alpha * (alpha_eff - alpha0)
    Cl_att_safe = np.where(np.abs(Cl_att) < 1e-6, np.sign(Cl_att) * 1e-6 + 1e-9, Cl_att)
    ratio = Cl_st / Cl_att_safe  # sign preserved, per the Øye/QBlade specification
    ratio_clipped = np.maximum(ratio, 0.0)  # ratio<0 (Cl_st and Cl_att with opposite signs) => full separation
    f_st = (2.0 * np.sqrt(ratio_clipped) - 1.0) ** 2
    f_st = np.where(np.abs(Cl_att) < 1e-6, 1.0, f_st)  # Cl_att~0: f_st=1 (explicit QBlade rule)
    f_st = np.clip(f_st, 0.0, 1.0)
    return f_st, Cl_att


def _oye_cl_sep(Cl_st: np.ndarray, f_st: np.ndarray, Cl_att: np.ndarray, reg: float):
    """Cl_sep = (Cl_st - f_st*Cl_att)/(1-f_st), regularized near
    f_st->1 (where 1-f_st->0) . In that region the flow is already
    attached and Cl_sep loses standalone physical meaning. We use Cl_att
    as the limit (f_st=1 implies Cl_dyn=Cl_att regardless of Cl_sep)."""
    denom = np.maximum(1.0 - f_st, reg)
    return (Cl_st - f_st * Cl_att) / denom


def _dynamic_stall_fade_weight(alpha_eff: np.ndarray, cfg: BEMTConfig):
    """Weight 1->0 that fades the dynamic-stall correction toward the
    pure static polar outside +-fade_end_deg (the Øye model is only valid
    near stall, not at reverse flow/extreme incidence , see the QBlade
    note "faded out toward the static polar near +-50 deg")."""
    alpha_deg = np.degrees(np.abs(alpha_eff))
    return 1.0 - _smoothstep(alpha_deg, cfg.dynamic_stall_fade_start_deg, cfg.dynamic_stall_fade_end_deg)


def _oye_frequency_domain_f(f_st: np.ndarray, W: np.ndarray, CHORD: np.ndarray,
                             Omega: float, cfg: BEMTConfig) -> np.ndarray:
    """Solves f(r,psi) in the periodic steady-state regime WITHOUT time
    marching, via a Fourier series along psi (axis 1). Exactly valid for
    tau CONSTANT per row (here: mean tau per radial station, from the
    mean Vrel over psi at that station) , see Section 4g. Default method
    (`dynamic_stall_method='frequency'`)."""
    Ne, Npsi = f_st.shape
    Vrel_bar = np.mean(W, axis=1)                              # (Ne,) mean over psi per station
    chord_r = CHORD[:, 0]                                      # (Ne,) chord does not vary with psi
    tau_r = cfg.dynamic_stall_A * chord_r / (2.0 * np.maximum(Vrel_bar, 1e-3))
    tau_psi_r = Omega * tau_r                                  # non-dimensional time [rad of azimuth]

    Fk = np.fft.rfft(f_st, axis=1)                              # (Ne, Npsi//2+1)
    n_harm = np.arange(Fk.shape[1])
    H = 1.0 / (1.0 + 1j * n_harm[None, :] * tau_psi_r[:, None])  # 1st-order transfer function
    f = np.fft.irfft(Fk * H, n=Npsi, axis=1)
    return np.clip(f, 0.0, 1.0)


def _oye_time_march_f(f_st: np.ndarray, W: np.ndarray, CHORD: np.ndarray,
                       Omega: float, cfg: BEMTConfig, f_init: np.ndarray = None
                       ) -> tuple:
    """Marches explicitly over the Npsi azimuth points, for several
    revolutions, using Øye's EXACT recursive formula for tau constant per
    step (but here tau is re-evaluated LOCALLY at every step, with the
    real Vrel(r, psi) . More accurate than the 'frequency' method, which
    uses mean Vrel). Since f depends on history, the first revolutions
    carry a transient from the initial guess. Those revolutions are
    discarded and the average of the last
    `dynamic_stall_time_march_avg_last` is taken, already in established
    periodic regime.

    ``f_init`` (optional): the separation state the march STARTS from --
    the previous sample's final values on a maneuver (SC-12), making the
    state continuous along the trajectory. Defaults to f_st at the last
    psi station."""
    Ne, Npsi = f_st.shape
    d_psi = 2.0 * np.pi / Npsi
    n_rev = max(int(cfg.dynamic_stall_time_march_revolutions), 1)
    n_avg = max(min(int(cfg.dynamic_stall_time_march_avg_last), n_rev), 1)

    chord_r = CHORD[:, 0]
    f_hist = np.empty((n_rev, Ne, Npsi), dtype=float)

    if f_init is None:
        f_prev = f_st[:, -1].copy()
    else:
        f_prev = np.clip(np.asarray(f_init, dtype=float), 0.0, 1.0)
    for rev in range(n_rev):
        for k in range(Npsi):
            f_st_k = f_st[:, k]
            W_k = np.maximum(W[:, k], 1e-3)
            tau_k = cfg.dynamic_stall_A * chord_r / (2.0 * W_k)
            dt_over_tau = d_psi / np.maximum(Omega * tau_k, 1e-9)
            f_prev = f_st_k + (f_prev - f_st_k) * np.exp(-dt_over_tau)
            f_hist[rev, :, k] = f_prev

    f_periodic = np.mean(f_hist[-n_avg:], axis=0)
    return np.clip(f_periodic, 0.0, 1.0), f_hist


def _dynamic_stall_section_param(airfoil, r_stations: np.ndarray, key: str, fallback):
    """Reads `airfoil.dynamic_stall_section_field` (attached by
    `airfoils.to_blade_airfoil` for a multi-section airfoil, radial
    Sections in the Airfoil tab) and interpolates the `key` parameter
    (`A`, `fade_start_deg`, `fade_end_deg`, `enabled`) by `r_stations` --
    returns `fallback` (scalar) unchanged when the object is not
    multi-section (single airfoil, the usual path)."""
    field = getattr(airfoil, "dynamic_stall_section_field", None)
    if field is None:
        return np.full_like(r_stations, float(fallback), dtype=float)
    return np.interp(r_stations, field["r_norms"], field[key])


def _resolve_dynamic_stall_config(cfg: BEMTConfig, airfoil) -> BEMTConfig:
    """Resolves the dynamic-stall (Øye) parameters from
    `airfoil.dynamic_stall_params` . An attribute attached by
    `airfoils.to_airfoil()` from the SINGLE copy of these fields, which
    lives in `AirfoilDef` (docs/plano_v2.md Section 2.4/6.3, Finding #1).
    This replaces the old duplicated (and never read) block of
    `AirfoilDef` in `BEMTConfig`: the `dynamic_stall_*` fields still exist
    here only as a backward-compatibility fallback, for scripts that
    build `BEMTConfig`/airfoil manually without going through
    `to_airfoil()`."""
    params = getattr(airfoil, "dynamic_stall_params", None)
    if not params:
        return cfg
    return replace(
        cfg,
        use_dynamic_stall=params.get("use_dynamic_stall", cfg.use_dynamic_stall),
        dynamic_stall_method=params.get("method", cfg.dynamic_stall_method),
        dynamic_stall_A=params.get("A", cfg.dynamic_stall_A),
        dynamic_stall_fade_start_deg=params.get("fade_start_deg", cfg.dynamic_stall_fade_start_deg),
        dynamic_stall_fade_end_deg=params.get("fade_end_deg", cfg.dynamic_stall_fade_end_deg),
        dynamic_stall_time_march_revolutions=params.get(
            "time_march_revolutions", cfg.dynamic_stall_time_march_revolutions),
        dynamic_stall_time_march_avg_last=params.get(
            "time_march_avg_last", cfg.dynamic_stall_time_march_avg_last),
    )


def apply_dynamic_stall(maps: dict, rotor: Rotor, airfoil, cfg: BEMTConfig,
                         R_NORM, PSI, R_DIM, CHORD, mu_x: float, lambda_z: float,
                         f_init: np.ndarray = None):
    """Applies the Øye dynamic-stall model to an already converged `maps`
    (output of `solve_bemt`), replacing Cl/Cd/Fn/Ft/Ft_i/Ft_p with the
    dynamic values. The original static Cl/Cd are preserved in
    `Cl_static`/`Cd_static` for diagnostics/plotting. See the assumptions
    in Section 4g of the module docstring (does not feed back into the
    momentum equation).

    ``f_init`` (optional): the separation state to start the time march
    from -- the previous sample's final values on a maneuver (SC-12).
    Ignored by the 'frequency' method."""
    if cfg.dynamic_stall_model.lower() != "oye":
        raise ValueError(f"Unknown dynamic_stall_model: {cfg.dynamic_stall_model}")

    alpha_eff = maps["alpha_eff"]
    Cl_st = maps["Cl"]
    Cd_st = maps["Cd"]
    W = maps["W"]
    reverse = maps["reverse"]
    phi, phi_rev = maps["phi"], maps["phi_rev"]

    # Cl_alpha/alpha0 per section (see `_airfoil_cl_alpha_alpha0` . Only
    # actually varies for a multi-section airfoil. A single airfoil
    # returns the same scalar pair as always, with no behavior change).
    cl_alpha, alpha0 = _airfoil_cl_alpha_alpha0(airfoil, r_norm=R_NORM)
    f_st, Cl_att = _oye_static_separation(alpha_eff, Cl_st, cl_alpha, alpha0, cfg.dynamic_stall_f_reg)

    # A / fade window also per section, when the airfoil is multi-section
    # (docs/plano.md Section 4): each section can have its own
    # `dynamic_stall_A`/`fade_start/end_deg`, and a section can opt out
    # of dynamic stall . In that case `enabled_r`=0 there, and further
    # below `w_fade` is zeroed there (falls back to the pure static
    # polar), making dynamic stall apply section by section, not
    # all-or-nothing over the whole blade.
    r_stations = R_NORM[:, 0] if getattr(R_NORM, "ndim", 1) == 2 else np.atleast_1d(R_NORM)
    A_r = _dynamic_stall_section_param(airfoil, r_stations, "A", cfg.dynamic_stall_A)
    fade_start_r = _dynamic_stall_section_param(airfoil, r_stations, "fade_start_deg", cfg.dynamic_stall_fade_start_deg)
    fade_end_r = _dynamic_stall_section_param(airfoil, r_stations, "fade_end_deg", cfg.dynamic_stall_fade_end_deg)
    enabled_r = _dynamic_stall_section_param(airfoil, r_stations, "enabled", 1.0)
    cfg_field = replace(cfg, dynamic_stall_A=A_r,
                         dynamic_stall_fade_start_deg=fade_start_r[:, None],
                         dynamic_stall_fade_end_deg=fade_end_r[:, None])

    method = cfg.dynamic_stall_method.lower()
    time_march_history = None
    if method == "frequency":
        f = _oye_frequency_domain_f(f_st, W, CHORD, rotor.Omega, cfg_field)
    elif method == "time_march":
        f, time_march_history = _oye_time_march_f(f_st, W, CHORD,
                                                   rotor.Omega, cfg_field,
                                                   f_init=f_init)
    else:
        raise ValueError(f"Unknown dynamic_stall_method: {cfg.dynamic_stall_method} "
                          f"(use 'frequency' or 'time_march')")

    # EN-9: report whether the march reached a periodic regime. The
    # residual is the largest change of the separation function between
    # the last two marched revolutions; a value that does not sit near
    # zero means the transient had not decayed, and the remedy is more
    # revolutions.
    periodic_residual = float("nan")
    n_rev_marched = 0
    stall_note = None
    if time_march_history is not None:
        n_rev_marched = int(time_march_history.shape[0])
        if n_rev_marched >= 2:
            periodic_residual = float(np.max(np.abs(
                time_march_history[-1] - time_march_history[-2])))
            if periodic_residual > 1e-3:
                stall_note = (
                    f"Dynamic stall 'time_march': periodic residual "
                    f"{periodic_residual:.2e} after {n_rev_marched} "
                    "revolutions -- the separation state had NOT settled. "
                    "Increase the revolutions marched before trusting the "
                    "dynamic Cl/Cd of this case.")

    Cl_sep = _oye_cl_sep(Cl_st, f_st, Cl_att, cfg.dynamic_stall_f_reg)
    Cl_dyn = f * Cl_att + (1.0 - f) * Cl_sep

    Cd0, _ = airfoil.cl_cd(np.zeros_like(alpha_eff), None, r_norm=R_NORM)
    Cd0 = np.asarray(Cd0, dtype=float)
    Cd_dyn = Cd_st + (Cd_st - Cd0) * (0.5 * (np.sqrt(f_st) - np.sqrt(f)) - 0.25 * (f - f_st))
    Cd_dyn = np.maximum(Cd_dyn, 0.0)

    w_fade = _dynamic_stall_fade_weight(alpha_eff, cfg_field) * enabled_r[:, None]
    Cl_final = w_fade * Cl_dyn + (1.0 - w_fade) * Cl_st
    Cd_final = w_fade * Cd_dyn + (1.0 - w_fade) * Cd_st

    rho = cfg.rho
    Lift = 0.5 * rho * W ** 2 * CHORD * Cl_final
    Drag = 0.5 * rho * W ** 2 * CHORD * Cd_final

    if cfg.reverse_flow_model.lower() == "viterna_full_range":
        # Same continuous reconstruction as `element_state` (Section 1b/4): no
        # phi/phi_rev branch, so as not to reintroduce the discontinuity
        # that the Viterna-Corrigan model was designed to eliminate.
        Fn = Lift * np.cos(phi) - Drag * np.sin(phi)
        Ft_i = Lift * np.sin(phi)
        Ft_p = Drag * np.cos(phi)
        Ft = Ft_i + Ft_p
    else:
        Fn = np.where(reverse,
                      Lift * np.cos(phi_rev) + Drag * np.sin(phi_rev),
                      Lift * np.cos(phi) - Drag * np.sin(phi))
        phi_use = np.where(reverse, phi_rev, phi)
        sign_use = np.where(reverse, -1.0, 1.0)
        Ft_i = Lift * np.sin(phi_use)
        Ft_p = sign_use * Drag * np.cos(phi_use)
        Ft = Ft_i + Ft_p

    maps.update(dict(
        Cl_static=Cl_st, Cd_static=Cd_st, Cl=Cl_final, Cd=Cd_final,
        Cl_dyn=Cl_dyn, Cd_dyn=Cd_dyn, f_oye=f, f_st_oye=f_st,
        dynamic_stall_fade_weight=w_fade, Lift=Lift, Drag=Drag,
        Fn=Fn, Ft=Ft, Ft_i=Ft_i, Ft_p=Ft_p,
        dynamic_stall_method=cfg.dynamic_stall_method,
        dynamic_stall_time_march_history=time_march_history,
        dynamic_stall_periodic_residual=periodic_residual,
        dynamic_stall_revolutions=n_rev_marched,
        dynamic_stall_warning=stall_note,
    ))
    return maps


# =============================================================================
# 4h. RIGID-BLADE FLAPPING AND LEAD-LAG (harmonic balance, SC-11)
# =============================================================================
#
# The blade is rigid. It rotates about a flap hinge (and optionally a lag
# hinge) at the same radial offset e, with optional root springs. The
# response is PERIODIC in azimuth and quasi-steady: the aerodynamics
# inside one azimuth station stays steady, only the blade motion adds
# terms to the local flow, and there is no transient (that is what keeps
# the model consistent with a blade-element momentum solution; a real
# flap transient is out of scope, see SC-12's limits).
#
# Assumptions (also stated in docs/documentation.html):
#   1. Small angles: cos(beta) ~= 1, sin(beta) ~= beta. The blade element
#      stays in the disk plane for area and arm.
#   2. The blade is rigid in bending and in torsion.
#   3. The response is periodic; there is no transient.
#   4. Flap and lag are solved from the converged aerodynamic field, and
#      the field is then re-solved with the new motion, until both agree
#      (`solve_bemt_flapping`).
#
# Equation of motion in psi = Omega*t, flap:
#
#     beta'' + nu_beta^2 * beta = M_beta(psi) / (I_beta*Omega^2)
#
# with nu_beta^2 = 1 + (3/2)*e/(1-e) + K_beta/(I_beta*Omega^2)
# (geometry.flap_frequency_ratio_squared). Harmonic balance: write both
# sides as truncated Fourier series with N_h harmonics,
#
#     beta(psi)   = beta_0 + sum_n [beta_nc cos(n psi) + beta_ns sin(n psi)]
#     Mbar(psi)   = M_0    + sum_n [M_nc   cos(n psi) + M_ns   sin(n psi)]
#     Mbar = M_beta/(I_beta*Omega^2)
#
# Because beta'' = -n^2*(...) for each harmonic, the solution is
# algebraic:
#
#     beta_0 = M_0/nu_beta^2,  beta_nc = M_nc/(nu_beta^2 - n^2), ...
#
# EN-8 applies: when |nu_beta^2 - n^2| < 1e-3 the denominator is declared
# resonant and a ValueError names the resonance instead of returning a
# large number. An articulated rotor (e = 0, no spring) gives
# nu_beta = 1 exactly, so its first harmonic is undefined -- a physical
# fact of the configuration, not a numerical failure.
#
# Lag adds a damper C_zeta, which couples the sine to the cosine part of
# each harmonic into a two-by-two solve:
#
#     (nu_zeta^2 - n^2)*zeta_nc + n*(C_zeta/(I_zeta*Omega))*zeta_ns = M_nc
#    -n*(C_zeta/(I_zeta*Omega))*zeta_nc + (nu_zeta^2 - n^2)*zeta_ns = M_ns
#     zeta_0 = M_0 / nu_zeta^2
#
# Sign conventions used in every output of this section:
#     beta(psi) = beta_0 + beta_1c*cos(psi) + beta_1s*sin(psi), positive UP;
#     each tip-path-plane tilt is the NEGATIVE of its first harmonic
#     (tpp_tilt_long_deg = -beta_1c_deg, tpp_tilt_lat_deg = -beta_1s_deg).

_FLAP_RESONANCE_GUARD = 1e-3


def _fourier_coefficients(field_psi: np.ndarray, psi_nodes: np.ndarray,
                          n_harm: int):
    """Returns (a0, a_c, a_s) of a periodic field sampled on ``psi_nodes``.

    ``a0`` is the azimuthal mean; ``a_c[n]``/``a_s[n]`` are the cosine and
    sine coefficients of harmonic n, for n = 1..n_harm. The mesh is
    uniform over [0, 2*pi), so the coefficients reduce to weighted means
    (the periodic trapezoid rule, exactly the rectangle rule on this
    grid)."""
    field_psi = np.asarray(field_psi, dtype=float)
    a0 = float(np.mean(field_psi))
    a_c = np.zeros(n_harm + 1)
    a_s = np.zeros(n_harm + 1)
    for n in range(1, n_harm + 1):
        a_c[n] = float(np.mean(field_psi * np.cos(n * psi_nodes)))
        a_s[n] = float(np.mean(field_psi * np.sin(n * psi_nodes)))
    return a0, 2.0 * a_c, 2.0 * a_s


def _flap_moment(maps: dict, rotor: "Rotor", e_hinge_dim: float) -> np.ndarray:
    """M_beta(psi): the radial integral of (r - e*R)*Fn over one blade.

    ``Fn`` is the normal force per unit span that `element_state` already
    returns, so whatever reached it (inflow model, reverse flow, dynamic
    stall, corrections) reaches the flap forcing too."""
    r_nodes = maps["r_norm_nodes"] * rotor.R
    arm = np.maximum(r_nodes - e_hinge_dim, 0.0)[:, None]
    return _trapz(arm * maps["Fn"], r_nodes, axis=0)


def _lag_moment(maps: dict, rotor: "Rotor", e_hinge_dim: float) -> np.ndarray:
    """M_zeta(psi): the radial integral of (r - e*R)*Ft over one blade."""
    r_nodes = maps["r_norm_nodes"] * rotor.R
    arm = np.maximum(r_nodes - e_hinge_dim, 0.0)[:, None]
    return _trapz(arm * maps["Ft"], r_nodes, axis=0)


def solve_blade_motion(moment_psi: np.ndarray, psi_nodes: np.ndarray,
                       nu_squared: float, inertia: float, Omega: float,
                       n_harm: int, damping: float = 0.0,
                       freedom: str = "flap", hinge_offset_norm: float = 0.0):
    """Harmonic balance for one rigid-body freedom.

    Solves the algebraic system described in Section 4h for the given
    normalized moment history ``moment_psi`` (one value per azimuth
    node). Returns ``(coeffs, angle_psi, rate_psi)`` where ``coeffs`` maps
    each harmonic to its cosine/sine pair (harmonic 0 -> the mean),
    ``angle_psi`` is the reconstructed angle [rad] on the psi grid and
    ``rate_psi`` its time derivative [rad/s] (angle' * Omega).

    ``damping`` is the NON-DIMENSIONAL damper C/(I*Omega); it couples the
    sine and cosine parts per harmonic into a two-by-two system. With
    zero damping the solve stays diagonal.

    Raises ValueError when the denominator of a harmonic is resonant
    (EN-8), naming the freedom, the harmonic and the configuration that
    produced it."""
    if not np.isfinite(nu_squared):
        raise ValueError(
            f"solve_blade_motion: the {freedom} frequency ratio is not finite. "
            "Check the hinge offset, the spring and the inertia.")
    if abs(nu_squared) < 1e-9:
        # Lag without offset or spring: nothing restores the angle, so
        # even the mean is undefined.
        raise ValueError(
            f"the {freedom} freedom has no restoring term: its frequency "
            "ratio is zero because the rotor has neither a hinge offset nor "
            f"a {freedom} spring. The periodic response is undefined. Give "
            f"the {freedom} hinge an offset or add a spring.")
    for n in range(1, n_harm + 1):
        if abs(nu_squared - n * n) < _FLAP_RESONANCE_GUARD:
            articulated = abs(hinge_offset_norm) < 1e-12
            physical = (" That is the ARTICULATED rotor: with no hinge "
                        "offset and no spring the flap frequency ratio is "
                        "exactly 1, equal to this harmonic, so the "
                        "periodic response has no finite solution."
                        if (freedom == "flap" and articulated) else "")
            raise ValueError(
                f"resonant {freedom} denominator: |nu_{freedom[0]}^2 - "
                f"{n}^2| = {abs(nu_squared - n * n):.2e} < "
                f"{_FLAP_RESONANCE_GUARD:g} (nu^2 = {nu_squared:.6f}, hinge "
                f"offset e = {hinge_offset_norm:g}). Harmonic {n} cannot be "
                "solved by harmonic balance; returning a large number would "
                "mean nothing." + physical + " Change the hinge offset, the "
                "spring, or drop the harmonic count below it.")
    inertia_term = max(float(inertia) * float(Omega) ** 2, 1e-12)
    m_bar = np.asarray(moment_psi, dtype=float) / inertia_term
    m0, mc, ms = _fourier_coefficients(m_bar, psi_nodes, n_harm)

    coeffs = {0: (m0 / nu_squared, 0.0)}
    for n in range(1, n_harm + 1):
        denom = nu_squared - n * n
        matrix = np.array([[denom, n * damping],
                           [-n * damping, denom]])
        det = float(matrix[0, 0] * matrix[1, 1] - matrix[0, 1] * matrix[1, 0])
        if abs(det) < (_FLAP_RESONANCE_GUARD ** 2):
            raise ValueError(
                f"resonant {freedom} denominator: the damped two-by-two "
                f"system of harmonic {n} is singular (nu^2 = "
                f"{nu_squared:.6f}, damping ratio C/(I*Omega) = "
                f"{damping:.6f}, hinge offset e = {hinge_offset_norm:g}). "
                "The periodic response is undefined (EN-8).")
        zc, zs = np.linalg.solve(matrix, np.array([mc[n], ms[n]]))
        coeffs[n] = (float(zc), float(zs))

    angle = np.full_like(psi_nodes, coeffs[0][0], dtype=float)
    rate_dpsi = np.zeros_like(psi_nodes, dtype=float)
    for n in range(1, n_harm + 1):
        zc, zs = coeffs[n]
        angle += zc * np.cos(n * psi_nodes) + zs * np.sin(n * psi_nodes)
        rate_dpsi += n * (-zc * np.sin(n * psi_nodes) + zs * np.cos(n * psi_nodes))
    return coeffs, angle, rate_dpsi * Omega


def build_motion_grid(rotor: "Rotor", cfg: "BEMTConfig", motion_scalars: dict,
                       beta_psi=None, beta_rate_psi=None, zeta_rate_psi=None):
    """Assembles the `motion` dictionary `element_state` consumes, from
    per-azimuth arrays (Npsi,) broadcast onto the (Ne,Npsi) mesh."""
    r_eff_root = rotor.r_root_norm_geom + cfg.integration_offset
    r_eff_tip = rotor.r_tip_norm_geom - cfg.integration_offset
    r_norm_nodes = np.linspace(r_eff_root, r_eff_tip, cfg.Ne)
    psi_nodes = np.linspace(0, 2 * np.pi * (1 - 1.0 / cfg.Npsi), cfg.Npsi)
    R_NORM, PSI = np.meshgrid(r_norm_nodes, psi_nodes, indexing="ij")

    def _grid(values):
        if values is None:
            return np.zeros_like(R_NORM)
        values = np.asarray(values, dtype=float)
        if values.ndim == 1:
            return np.repeat(values[None, :], cfg.Ne, axis=0)
        return values

    motion = {
        "beta": _grid(beta_psi),
        "beta_rate": _grid(beta_rate_psi),
        "zeta_rate": _grid(zeta_rate_psi),
        "e_hinge_dim": float(motion_scalars.get("e_hinge_dim", 0.0)),
        "pitch_flap_K": float(motion_scalars.get("pitch_flap_K", 0.0)),
        "cyclic_c_rad": float(motion_scalars.get("cyclic_c_rad", 0.0)),
        "cyclic_s_rad": float(motion_scalars.get("cyclic_s_rad", 0.0)),
        "p_rate": float(motion_scalars.get("p_rate", 0.0)),
        "q_rate": float(motion_scalars.get("q_rate", 0.0)),
    }
    return motion, r_norm_nodes, psi_nodes, R_NORM, PSI


def solve_bemt_flapping(rotor: "Rotor", airfoil, cfg: "BEMTConfig", mu_x: float,
                         Vz: float, dynamics, *, cyclic_c_deg: float = 0.0,
                         cyclic_s_deg: float = 0.0, p_rate: float = 0.0,
                         q_rate: float = 0.0, warm_start: Optional[dict] = None,
                         should_cancel=None):
    """Solves one case WITH the blade's rigid-body flap/lag freedoms
    (SC-11): the outer loop of Section 4h.

    ``p_rate``/``q_rate`` are the HUB angular rates [rad/s] about the
    roll and pitch axes (SC-14). They reach the aerodynamics as an
    out-of-disk-plane velocity of every element and enter the flap
    balance as a gyroscopic forcing Mbar_gyro = 2*(q*sin(psi) +
    p*cos(psi))/Omega, added to the aerodynamic flap moment before the
    harmonic balance. A rigid blade with a hub rate takes this path
    exactly like one with cyclic pitch, beta held at zero.

    Loop: `solve_bemt` with the current motion, then the flap/lag moments
    from the converged field, then the harmonic balance, relaxed into the
    next iterate, until the flap coefficients stop moving (below
    ``dynamics.outer_tol_deg``, at most ``dynamics.outer_max_iter``
    times). A flapping blade changes the inflow it produces, which is why
    the aerodynamic field and the motion must agree before the result is
    reported (assumption 4 of Section 4h).

    ``dynamics`` is the project's `BladeDynamicsDef`. With
    ``flap_model='rigid'`` (and no lag) there is no freedom to solve: a
    single pass runs the unchanged path with any cyclic pitch carried as
    an azimuthal pitch term and beta held at zero.

    ``warm_start`` optionally carries the previous case's converged blade
    state, as ``{"beta_psi": angle_on_psi_grid}``; projecting it onto the
    coefficient vector cuts the outer-loop iteration count in a sweep.

    Returns the same ``maps`` contract as `solve_bemt`, plus the flap
    keys (`beta_0_rad`, `beta_coeffs`, `nu_beta`, `nu_beta_squared`,
    `lock_number`, `flap_inertia_kg_m2`, `flap_outer_iterations`,
    `flap_outer_residual_deg`, `flap_outer_history`, and their lag
    counterparts). `aggregate_results` turns them into the summary
    columns; a caller downstream needs nothing new.

    ``should_cancel`` is honored once per outer iteration AND inside every
    inner `solve_bemt` iteration (PR-11): cancellation raises
    `SolveCancelled` and never returns a partial result."""
    from . import geometry as geometry_gen

    _check_rotor_rotation(rotor)
    rho = cfg.rho
    cl_alpha, _alpha0 = _airfoil_cl_alpha_alpha0(airfoil)
    chord_ref = float(np.interp(
        geometry_gen.REFERENCE_CHORD_STATION,
        np.asarray(rotor.r_geom, dtype=float),
        np.asarray(rotor.chord_geom, dtype=float) / rotor.R)) * rotor.R
    inertia = geometry_gen.resolve_flap_inertia(
        inertia_source=dynamics.inertia_source,
        lock_number=dynamics.lock_number,
        flap_inertia_kg_m2=dynamics.flap_inertia_kg_m2,
        blade_mass_kg=dynamics.blade_mass_kg,
        hinge_offset_norm=dynamics.hinge_offset_norm,
        radius_m=rotor.R, chord_ref_m=chord_ref, rho=rho, cl_alpha=cl_alpha)

    rigid = dynamics.flap_model == "rigid"
    if not rigid and not (np.isfinite(inertia) and inertia > 0.0):
        raise ValueError(
            f"solve_bemt_flapping: the resolved flap inertia I_beta is "
            f"{inertia} kg*m^2 (source '{dynamics.inertia_source}'). A "
            "flapping blade needs a positive inertia.")

    e_norm = 0.0 if rigid else float(dynamics.hinge_offset_norm)
    e_dim = e_norm * rotor.R
    k_flap = np.tan(np.deg2rad(0.0 if rigid else dynamics.pitch_flap_coupling_deg))
    scalars = {
        "e_hinge_dim": e_dim,
        "pitch_flap_K": k_flap,
        "cyclic_c_rad": np.deg2rad(cyclic_c_deg),
        "cyclic_s_rad": np.deg2rad(cyclic_s_deg),
        "p_rate": float(p_rate),
        "q_rate": float(q_rate),
    }
    omega = rotor.Omega
    nu_beta_sq = geometry_gen.flap_frequency_ratio_squared(
        e_norm, max(dynamics.flap_spring_nm_per_rad, 0.0), inertia, omega)
    lock_number = (float(dynamics.lock_number)
                   if dynamics.inertia_source == "lock"
                   else float(rho * cl_alpha * chord_ref * rotor.R ** 4 / max(inertia, 1e-12)))

    lag_on = bool(dynamics.lag_enabled) and not rigid
    lag_inertia = float(dynamics.lag_inertia_kg_m2)
    if lag_on and not (np.isfinite(lag_inertia) and lag_inertia > 0.0):
        raise ValueError(
            f"solve_bemt_flapping: lead-lag is enabled but its inertia "
            f"I_zeta is {lag_inertia} kg*m^2. A lagging blade needs a "
            "positive inertia.")
    nu_zeta_sq = (geometry_gen.lag_frequency_ratio_squared(
        e_norm, max(dynamics.lag_spring_nm_per_rad, 0.0), lag_inertia, omega)
        if lag_on else None)
    lag_feeds_back = lag_on and bool(dynamics.lag_feeds_back)

    n_harm = max(int(dynamics.harmonics), 1)

    def _reconstruct(coeffs, nodes):
        """Angle [rad] and rate [rad/s] on the psi grid from harmonic
        coefficients."""
        angle = np.full(cfg.Npsi, coeffs[0][0], dtype=float)
        rate = np.zeros(cfg.Npsi, dtype=float)
        for n in range(1, len(coeffs)):
            zc, zs = coeffs[n]
            angle += zc * np.cos(n * nodes) + zs * np.sin(n * nodes)
            rate += n * (-zc * np.sin(n * nodes) + zs * np.cos(n * nodes))
        return angle, rate * omega

    def _coeffs_vector(coeffs):
        """Flat [b0, b1c, b1s, b2c, ...] vector of a coefficient dict."""
        flat = [coeffs[0][0]]
        for n in range(1, len(coeffs)):
            flat.extend(coeffs[n])
        return np.asarray(flat, dtype=float)

    def _vector_coeffs(vec):
        n = len(vec)
        out = {0: (float(vec[0]), 0.0)}
        for k in range(1, (n + 1) // 2):
            out[k] = (float(vec[2 * k - 1]), float(vec[2 * k]))
        return out

    def _coeff_delta_deg(new_coeffs, old_coeffs):
        """Largest coefficient change [deg], over harmonics that carry a
        physical amplitude. Harmonics sitting under the noise gate in
        BOTH iterates are skipped: their solver-level jitter would
        otherwise keep the outer loop chasing differences smaller than
        any physical meaning, forever."""
        gate_rad = np.deg2rad(max(10.0 * tol_deg_hint, 1e-3))
        worst = 0.0
        for key in set(new_coeffs) | set(old_coeffs):
            cn = new_coeffs.get(key, (0.0, 0.0))
            co = old_coeffs.get(key, (0.0, 0.0))
            amp = max(np.hypot(cn[0], cn[1]), np.hypot(co[0], co[1]))
            if key != 0 and amp < gate_rad:
                continue
            worst = max(worst,
                        abs(cn[0] - co[0]), abs(cn[1] - co[1]))
        return float(np.degrees(worst))

    tol_deg = max(float(dynamics.outer_tol_deg), 1e-10)
    tol_deg_hint = tol_deg   # noise gate of _coeff_delta_deg, above
    max_iter = max(int(dynamics.outer_max_iter), 1)

    # -- outer loop ------------------------------------------------------
    # WHO CARRIES THE FLAP DAMPING, AND WHERE. The blade-rate term of
    # U_P is real physics: a flapping blade sees its incidence change in
    # proportion to beta_dot. Solving the balance with the raw algebraic
    # denominator while ALSO feeding that rate back through the field
    # makes the iteration gain ~ n*d/(nu^2-n^2) -- far above 1 for a
    # small offset hinge -- and no relaxation scheme survives it. The
    # scheme below is the textbook one:
    #
    #   1. The fields the outer loop iterates on are solved with the
    #      blade ANGLE only (rates held at zero), so their moments carry
    #      no rate feedback.
    #   2. The analytic flap damping d_beta =
    #      gamma*(1/8 - e/3 + e^2/4) -- gamma/8 at e = 0, the classic
    #      centrally hinged result (`geometry.flap_aero_damping`,
    #      derived from exactly the term that was removed) enters the
    #      harmonic balance as the two-by-two coupling of each harmonic,
    #      exactly like a lag damper.
    #   3. The map from blade angle to solved coefficients now has an
    #      O(mu) gain: plain under-relaxed fixed-point iteration
    #      converges in a few steps.
    #   4. One final solve rebuilds the field WITH the converged rates,
    #      so the reported loads include the rate terms consistently
    #      with the damped solution.
    relax = float(np.clip(dynamics.outer_relax, 0.05, 1.0))
    d_beta = geometry_gen.flap_aero_damping(lock_number, e_norm)
    zeta_rate_grid = np.zeros(cfg.Npsi)

    warm = warm_start or {}
    state = np.zeros(1 + 2 * n_harm)
    motion, _rn, psi_nodes, _RN, _PSI = build_motion_grid(
        rotor, cfg, scalars,
        beta_psi=warm.get("beta_psi"),
        zeta_rate_psi=warm.get("zeta_rate_psi"),
    )
    if warm.get("beta_psi") is not None:
        # The warm start arrives as a blade ANGLE on the psi grid (the
        # previous case's converged response); project it onto the
        # coefficient vector the outer loop iterates.
        a0, a_c, a_s = _fourier_coefficients(
            np.asarray(warm["beta_psi"], dtype=float), psi_nodes, n_harm)
        state[0] = a0
        for k in range(1, n_harm + 1):
            state[2 * k - 1] = a_c[k]
            state[2 * k] = a_s[k]

    residual_deg = float("inf")
    iterations = 0
    coeffs_flap = None
    coeffs_lag = None
    outer_history = []

    for iterations in range(1, max_iter + 1):
        if should_cancel is not None and should_cancel():
            raise SolveCancelled()
        maps = solve_bemt(rotor, airfoil, cfg, mu_x, Vz,
                          should_cancel=should_cancel, motion=motion)
        if rigid:
            break   # nothing to balance: the cyclic-only pass is done

        m_beta = _flap_moment(maps, rotor, e_dim)
        if p_rate != 0.0 or q_rate != 0.0:
            # Gyroscopic forcing of the hub rates (SC-14), in the same
            # Mbar = M/(I*Omega^2) units the harmonic balance consumes:
            # Mbar_gyro = 2*(q*sin(psi) + p*cos(psi))/Omega.
            m_beta = m_beta + 2.0 * inertia * omega * (
                q_rate * np.sin(psi_nodes) + p_rate * np.cos(psi_nodes))
        new_coeffs, _new_angle, _new_rate = solve_blade_motion(
            m_beta, psi_nodes, nu_beta_sq, inertia, omega,
            n_harm, damping=d_beta, freedom="flap", hinge_offset_norm=e_norm)

        if lag_on:
            m_zeta = _lag_moment(maps, rotor, e_dim)
            damping_ratio = dynamics.lag_damping_nms_per_rad / max(lag_inertia * omega, 1e-12)
            coeffs_lag, _za, _zr = solve_blade_motion(
                m_zeta, psi_nodes, nu_zeta_sq, lag_inertia, omega,
                n_harm, damping=damping_ratio, freedom="lag",
                hinge_offset_norm=e_norm)

        residual_deg = _coeff_delta_deg(new_coeffs, _vector_coeffs(state))
        outer_history.append(residual_deg)
        state = state + relax * (_coeffs_vector(new_coeffs) - state)
        beta_ang, _unused_rate = _reconstruct(_vector_coeffs(state), psi_nodes)
        motion, _rn, psi_nodes, _RN, _PSI = build_motion_grid(
            rotor, cfg, scalars,
            beta_psi=beta_ang,
            zeta_rate_psi=zeta_rate_grid,
        )
        if residual_deg < tol_deg:
            break

    if not rigid and coeffs_flap is not None:
        # Consistency pass: rebuild the FULL motion (angles AND rates)
        # from the converged coefficients and re-solve once, so every
        # reported field is exactly what the reported blade state
        # produces, with the rate terms of U_P included.
        beta_ang, beta_rate = _reconstruct(_vector_coeffs(state), psi_nodes)
        if lag_on:
            _za, _zr = _reconstruct(coeffs_lag or {0: (0.0, 0.0)}, psi_nodes)
            zeta_rate_grid = _zr if lag_feeds_back else np.zeros(cfg.Npsi)
        motion, _rn, psi_nodes, _RN, _PSI = build_motion_grid(
            rotor, cfg, scalars,
            beta_psi=beta_ang, beta_rate_psi=beta_rate,
            zeta_rate_psi=zeta_rate_grid)
        maps = solve_bemt(rotor, airfoil, cfg, mu_x, Vz,
                          should_cancel=should_cancel, motion=motion)

    maps["flap_outer_iterations"] = iterations
    maps["flap_outer_residual_deg"] = residual_deg
    maps["flap_outer_history"] = outer_history
    maps["nu_beta"] = float(np.sqrt(max(nu_beta_sq, 0.0)))
    maps["nu_beta_squared"] = float(nu_beta_sq)
    maps["lock_number"] = float(lock_number)
    maps["flap_inertia_kg_m2"] = float(inertia)
    maps["hinge_offset_norm"] = float(e_norm)
    if not rigid:
        # Report the STATE the final field was solved with, so the
        # summary and every map agree by construction.
        reported = state
        beta_dict = {0: (float(reported[0]), 0.0)}
        for k in range(1, (reported.size + 1) // 2):
            beta_dict[k] = (float(reported[2 * k - 1]), float(reported[2 * k]))
        maps["beta_coeffs"] = beta_dict
        maps["beta_0_rad"] = float(reported[0])
        maps["beta_1c_rad"] = float(reported[1]) if reported.size > 1 else 0.0
        maps["beta_1s_rad"] = float(reported[2]) if reported.size > 2 else 0.0
        if lag_on:
            maps["nu_zeta"] = float(np.sqrt(max(nu_zeta_sq, 0.0)))
            maps["lag_coeffs"] = {int(k): tuple(v)
                                   for k, v in (coeffs_lag or {}).items()}
    return maps


# =============================================================================
# 5. ITERATIVE SOLVERS (all vectorized over the Ne x Npsi grid)
# =============================================================================

def _check_early_stop(frac: float, frac_track: list, cfg: "BEMTConfig") -> bool:
    """Decides whether the iterative loop can already stop: either the
    converged-fraction target was reached, or the fraction has stagnated
    (no improvement for `stagnation_patience` iterations) while already
    reasonably high. This avoids spending the entire max_iter because of a
    tiny fraction of elements stuck at a physical singularity (Ut~0
    boundary)."""
    frac_track.append(frac)
    if frac >= cfg.early_exit_fraction:
        return True
    if frac >= cfg.stagnation_min_frac and len(frac_track) > cfg.stagnation_patience:
        window = frac_track[-cfg.stagnation_patience:]
        if (max(window) - min(window)) < 1e-6:
            return True
    return False


def _relax_map(cfg: BEMTConfig, R_NORM, PSI, mu_x):
    relax_map = np.full_like(R_NORM, cfg.relax, dtype=float)
    if not cfg.relax_schedule:
        return relax_map
    near_edge = (R_NORM < cfg.relax_root_threshold) | (R_NORM > cfg.relax_tip_threshold)
    relax_map = np.where(near_edge, relax_map * cfg.relax_root_factor, relax_map)
    if mu_x > 0.01:
        near_az = np.abs(np.cos(PSI)) < cfg.relax_azimuth_threshold
        relax_map = np.where(near_az, relax_map * cfg.relax_azimuth_factor, relax_map)
    if _resolve_inflow_field_model(cfg.inflow_field_model)["harmonic"] not in (None, "glauert"):
        relax_map = relax_map * 0.3
    return relax_map


class SolveCancelled(Exception):
    """The user requested cancellation in the middle of a solve.

    Not an error: it is the only way to exit a vectorized solver loop
    without returning a half-converged state that would look like a valid
    result. The orchestrator (``studies._run_conditions``) treats it as
    "stop here", not as a failed case.

    Exists because the previous semantics was "cancel BETWEEN cases": a
    single case on a production mesh did not respond to the button until
    it finished on its own, which is exactly when you want to cancel.
    """


def _abortar_se_cancelado(should_cancel, iteracao: int) -> None:
    """Checked once per solver iteration. The cost is one function call
    per pass over the whole mesh (5-30 per case), against tens of
    milliseconds per pass . Negligible."""
    if should_cancel is not None and should_cancel():
        raise SolveCancelled(
            f"solve cancelled by user at iteration {iteracao + 1}")


def solve_fixed_point(residual_fn, lambda0, cfg: BEMTConfig, R_NORM, PSI, mu_x,
                       should_cancel=None, **_):
    """Picard (fixed-point) iteration with relaxation: at each step,
    advances lambda_i by a `relax` fraction of the residual
    g(lambda)-lambda, instead of the full step . Avoids
    oscillation/divergence near strong nonlinearities (stall, reverse-flow
    boundary), at the cost of slower convergence than Newton."""
    lam = lambda0.copy()
    relax_map = _relax_map(cfg, R_NORM, PSI, mu_x)
    converged = np.zeros_like(lam, dtype=bool)
    n_iter = np.zeros_like(lam, dtype=int)
    history = []
    frac_hist = []
    _frac_track = []
    it = 0
    for it in range(cfg.max_iter):
        _abortar_se_cancelado(should_cancel, it)
        state = residual_fn(lam)
        resid = state["lambda_i_next"] - lam
        if cfg.collect_history:
            history.append(float(np.max(np.abs(resid))))
            frac_hist.append(float(np.mean(np.abs(resid) < cfg.tol)))
        active = ~converged
        if not np.any(active):
            break
        newly = active & (np.abs(resid) < cfg.tol)
        converged |= newly
        n_iter = np.where(active, it + 1, n_iter)
        lam_new = np.clip(lam + relax_map * resid, -0.5, 0.5)
        lam = np.where(converged, lam, lam_new)
        if _check_early_stop(float(np.mean(converged)), _frac_track, cfg):
            break
    state = residual_fn(lam)
    return lam, state, converged, n_iter, it + 1, history, frac_hist


def solve_newton(residual_fn, lambda0, cfg: BEMTConfig, should_cancel=None, **_):
    """Vectorized Newton-Raphson, Jacobian (diagonal, since each element is
    1 independent DOF) by central finite difference. Typically quadratic
    convergence . A few dozen iterations in total."""
    lam = lambda0.copy()
    eps = 1e-5
    max_step = 0.06
    converged = np.zeros_like(lam, dtype=bool)
    n_iter = np.zeros_like(lam, dtype=int)
    history = []
    frac_hist = []
    _frac_track = []
    it = 0
    for it in range(cfg.max_iter):
        _abortar_se_cancelado(should_cancel, it)
        state = residual_fn(lam)
        h = state["lambda_i_next"] - lam
        if cfg.collect_history:
            history.append(float(np.max(np.abs(h))))
            frac_hist.append(float(np.mean(np.abs(h) < cfg.tol)))
        active = ~converged
        newly = active & (np.abs(h) < cfg.tol)
        converged |= newly
        n_iter = np.where(active, it + 1, n_iter)
        if not np.any(~converged) or _check_early_stop(float(np.mean(converged)), _frac_track, cfg):
            break
        h_plus = residual_fn(lam + eps)["lambda_i_next"] - (lam + eps)
        h_minus = residual_fn(lam - eps)["lambda_i_next"] - (lam - eps)
        dh = (h_plus - h_minus) / (2 * eps)
        dh = np.where(np.abs(dh) < 1e-8, -1.0, dh)  # fallback: descent step
        step = np.clip(-h / dh, -max_step, max_step)
        lam_new = np.clip(lam + step, -0.5, 0.5)
        lam = np.where(converged, lam, lam_new)
    state = residual_fn(lam)
    return lam, state, converged, n_iter, it + 1, history, frac_hist


def solve_bisection(residual_fn, lambda0, cfg: BEMTConfig, R_NORM=None, PSI=None, mu_x=None,
                     lo=-0.5, hi=0.5, should_cancel=None, **_):
    """Vectorized bisection (no derivatives). Assumes h(lambda)=g(lambda)-lambda
    is monotonically decreasing (valid over most of the envelope. Near
    stall this can fail locally . Elements with an invalid bracket get
    the best candidate found and are marked not-converged).
    `lambda0` is not used as a guess (bisection does not need one), but is
    kept in the signature for uniformity with the other solvers."""
    shape = lambda0.shape
    a = np.full(shape, lo, dtype=float)
    b = np.full(shape, hi, dtype=float)
    ha = residual_fn(a)["lambda_i_next"] - a
    hb = residual_fn(b)["lambda_i_next"] - b
    bad_bracket = (ha * hb) > 0.0

    converged = np.zeros(shape, dtype=bool)
    n_iter = np.zeros(shape, dtype=int)
    lam = 0.5 * (a + b)

    # Boundary cases: if a or b is already an exact root (solution
    # saturated at -0.5/+0.5), accept directly . Avoids permanently
    # locking the bracket.
    exact_a = (np.abs(ha) < cfg.tol)
    exact_b = (np.abs(hb) < cfg.tol) & ~exact_a
    converged |= exact_a | exact_b
    lam = np.where(exact_a, a, np.where(exact_b, b, lam))

    history = []
    frac_hist = []
    _frac_track = []
    it = 0
    for it in range(cfg.max_iter):
        _abortar_se_cancelado(should_cancel, it)
        mid = 0.5 * (a + b)
        state = residual_fn(mid)
        hmid = state["lambda_i_next"] - mid
        if cfg.collect_history:
            valid = ~bad_bracket & ~converged
            history.append(float(np.max(np.abs(hmid[valid])) if np.any(valid) else 0.0))
            frac_hist.append(float(np.mean(converged | bad_bracket | (np.abs(hmid) < cfg.tol))))
        active = ~converged & ~bad_bracket
        if not np.any(active):
            break
        newly = active & (np.abs(hmid) < cfg.tol)
        converged |= newly
        n_iter = np.where(active, it + 1, n_iter)
        same_sign_as_a = np.sign(hmid) == np.sign(ha)
        a = np.where(active & same_sign_as_a, mid, a)
        ha = np.where(active & same_sign_as_a, hmid, ha)
        b = np.where(active & ~same_sign_as_a, mid, b)
        lam = np.where(converged | bad_bracket, lam, mid)
        if _check_early_stop(float(np.mean(converged | bad_bracket)), _frac_track, cfg):
            break
    lam = np.where(bad_bracket, 0.5 * (a + b), lam)
    state = residual_fn(lam)
    return lam, state, converged, n_iter, it + 1, history, frac_hist


def solve_aitken(residual_fn, lambda0, cfg: BEMTConfig, R_NORM=None, PSI=None, mu_x=None,
                  should_cancel=None, **_):
    """Picard accelerated by Aitken Delta^2 extrapolation (Anderson with
    memory 1). At every pair of Picard steps, extrapolates the sequence
    lambda_n, lambda_n+1, lambda_n+2 to the estimated fixed-point limit."""
    lam = lambda0.copy()
    relax = cfg.relax
    converged = np.zeros_like(lam, dtype=bool)
    n_iter = np.zeros_like(lam, dtype=int)
    history = []
    frac_hist = []
    _frac_track = []
    it = 0
    while it < cfg.max_iter:
        _abortar_se_cancelado(should_cancel, it)
        l0 = lam
        s0 = residual_fn(l0)
        h0 = s0["lambda_i_next"] - l0
        l1 = np.clip(l0 + relax * h0, -0.5, 0.5)
        it += 1
        s1 = residual_fn(l1)
        h1 = s1["lambda_i_next"] - l1
        l2 = np.clip(l1 + relax * h1, -0.5, 0.5)
        it += 1

        d1 = l1 - l0
        d2 = l2 - 2 * l1 + l0
        denom = np.where(np.abs(d2) < 1e-12, np.nan, d2)
        lam_aitken = l0 - d1 ** 2 / denom
        lam_aitken = np.where(np.isnan(lam_aitken), l2, lam_aitken)
        # Trust region: near stall/reverse flow, Cl(alpha) stops being
        # monotonic and d2 can become small without being spurious,
        # producing a huge extrapolated jump that lands on a spurious
        # fixed point of g(lambda)=lambda (see diagnosis: 2522/21600
        # elements, error up to 0.15 in lambda_i, passing the convergence
        # test). Same trust-region criterion as solve_newton
        # (max_step=0.06): outside the radius, discards the extrapolation
        # and uses the plain Picard l2 at that element.
        max_step = 0.06
        bad_jump = np.abs(lam_aitken - l2) > max_step
        lam_aitken = np.where(bad_jump, l2, lam_aitken)
        lam_aitken = np.clip(lam_aitken, -0.5, 0.5)

        state_chk = residual_fn(lam_aitken)
        h_chk = state_chk["lambda_i_next"] - lam_aitken
        if cfg.collect_history:
            history.append(float(np.max(np.abs(h_chk))))
            frac_hist.append(float(np.mean(np.abs(h_chk) < cfg.tol)))
        active = ~converged
        newly = active & (np.abs(h_chk) < cfg.tol)
        converged |= newly
        n_iter = np.where(active, it, n_iter)
        lam = np.where(converged, lam, lam_aitken)
        if _check_early_stop(float(np.mean(converged)), _frac_track, cfg):
            break
    state = residual_fn(lam)
    return lam, state, converged, n_iter, it, history, frac_hist


_SOLVERS: dict[str, Callable] = {
    "fixed_point": solve_fixed_point,
    "newton": solve_newton,
    "bisection": solve_bisection,
    "aitken": solve_aitken,
}


# =============================================================================
# 6. HIGH-LEVEL BEMT ENGINE
# =============================================================================

def _initial_guess(rotor: Rotor, airfoil, r_norm_nodes, Npsi):
    cl_alpha = getattr(airfoil, "cl_alpha", 2 * np.pi)
    chord_nodes, _ = rotor.chord_theta_at(r_norm_nodes)
    r_dim = np.maximum(r_norm_nodes * rotor.R, 1e-6)
    lam0_r = 0.5 * np.sqrt(np.maximum(
        rotor.Nb * chord_nodes * cl_alpha / (16 * np.pi * r_dim), 0.0))
    lam0_r = np.nan_to_num(lam0_r, nan=np.sqrt(0.007))
    lam0_r = np.clip(lam0_r, 0.01, 0.15)
    return np.repeat(lam0_r[:, None], Npsi, axis=1)


# =============================================================================
# 6b. PITT-PETERS DYNAMIC INFLOW (finite-state)
# =============================================================================
#
# Central idea: instead of solving lambda_i(r,psi) element by element
# (Ne x Npsi unknowns, like the 'local' solvers above), the entire inflow
# is PARAMETERIZED by just 3 numbers nu=(nu0,nu_s,nu_c):
#
#     lambda_i(r,psi) = nu0 + nu_c*r*cos(psi) + nu_s*r*sin(psi)
#
# and these 3 numbers are solved from the first 3 moments integrated over
# the disk (CT, and the 1/rev thrust harmonics, here CMx,CMy), via
# Peters' static gain matrix L(chi) (chi=wake angle), which gives the
# "elasticity" between aerodynamic load and inflow response, and the
# apparent-mass matrix M, which gives it INERTIA (used only in "unsteady"
# mode).
#
# This is cheaper than the 'local' mode (3 scalar unknowns per outer
# iteration vs. Ne*Npsi) and more physical than the 'global' mode (which
# uses empirical Coleman/Drees harmonics): here Kx,Ky "emerge" from
# Pitt-Peters' own unsteady actuator-disk physics, and the forcing is
# computed by the SAME blade aerodynamics (element_state) used throughout
# the rest of the code. That is, all corrections already implemented
# (reverse flow, Himmelskamp, radial flow, compressibility, Prandtl)
# automatically enter the forcing.

_PP_M3 = np.array([128.0 / (75.0 * np.pi), 16.0 / (45.0 * np.pi), 16.0 / (45.0 * np.pi)])
# Apparent mass of the 3-state model nu=(nu0,nu_s,nu_c).
# Source: Pitt (1980) / Pitt & Peters (1981). Values as consolidated in
# Peters & HaQuang (1988), checked against the thesis
# open.metu.edu.tr/bitstream/handle/11511/25959/index.pdf (ch.2, eq.2.11)
# and against the hover particular case in Chen, NASA TM-88327 (1986),
# eq.(4): CT = (128/75pi) dnu0/dtau + 2*VT*nu0.


def _pitt_peters_L_V(mu_x: float, nu0: float, lambda_z: float):
    """Matrices L (static gain) and V (mass-flow parameter, diag)
    of the 3-state Pitt-Peters model, as a function of the flight
    condition and the current state nu0 (uniform induced inflow).

    State order: (nu0, nu_s, nu_c). nu_c (the "fore-aft" harmonic, which
    multiplies r*cos(psi)) is the ONLY one coupled to nu0 (off-diagonal
    term) . Physically, it is the wake tilt (wake skew) in forward
    flight that creates this fore-aft asymmetry coupled to thrust. nu_s
    (the lateral harmonic, r*sin(psi)) stays decoupled. This is EXACTLY
    analogous to Kx (coupled to lambda_total/mu_x) and Ky (~-2*mu_x,
    nearly constant and decoupled) in the Coleman/Drees model already used
    in the rest of this code , see `_inflow_harmonics`.

    Source of the matrices: Pitt (1980)/Pitt & Peters (1981), form
    consolidated in Peters & HaQuang (1988). Checked against
    open.metu.edu.tr/bitstream/handle/11511/25959/index.pdf (ch.2).

    SIGN WARNING: the mapping nu_s<->CMy, nu_c<->CMx (used in
    `_pitt_peters_forcing`) was chosen by direct geometric correspondence
    (azimuthal weight cos<->Mx, sin<->My), not confirmed against the exact
    axis convention of the original Pitt-Peters paper. This does not
    affect CT/CQ (dominated by nu0), only the PHASE of the inflow
    distribution (whether the peak falls fore or aft on the disk). If
    CMx/CMy come out with an inverted physical sign when using this mode,
    just flip the sign of the off-diagonal term of L below.
    """
    lam = lambda_z + nu0  # mean total inflow (climb + uniform induced)
    VT = float(np.sqrt(mu_x ** 2 + lam ** 2 + 1e-9))
    Vbar = float((mu_x ** 2 + lam * (lam + nu0)) / max(VT, 1e-6))
    alpha_star = float(np.arctan2(lam, max(mu_x, 1e-6)))  # complement of the wake angle chi
    sin_a = np.sin(alpha_star)
    # (1 + sin alpha*) appears in the THREE entries below and goes to zero
    # at alpha* = -90deg. The previous version only protected the X term
    # (with a local `+1e-9`) and left the two divisions of L completely
    # unguarded . A single iterate with lambda<0 near mu_x=0 was enough
    # to turn into inf and, at the next step, NaN. See
    # `DENOMINADOR_MINIMO_DE_PITT_PETERS`: the same quantity, protected
    # once, across all three.
    denom = max(1.0 + sin_a, DENOMINADOR_MINIMO_DE_PITT_PETERS)
    X = float(np.sqrt(np.clip((1.0 - sin_a) / denom, 0.0, None)))  # =tan(chi/2)
    L = np.array([
        [0.5, 0.0, -(15.0 * np.pi / 64.0) * X],
        [0.0, 4.0 / denom, 0.0],
        [(15.0 * np.pi / 64.0) * X, 0.0, 4.0 * sin_a / denom],
    ])
    V = np.array([VT, Vbar, Vbar])
    return L, V


def _pitt_peters_geometry(rotor: Rotor, cfg: BEMTConfig):
    """Builds the (r,psi) mesh and the interpolated blade geometry --
    factored outside the time-integration loop so as not to recompute it
    at every RK4 sub-step in `run_sweep_unsteady_pitt_peters`."""
    r_eff_root = rotor.r_root_norm_geom + cfg.integration_offset
    r_eff_tip = rotor.r_tip_norm_geom - cfg.integration_offset
    if r_eff_root >= r_eff_tip:
        raise ValueError("integration_offset too large (or Ne too small).")
    r_norm_nodes = np.linspace(r_eff_root, r_eff_tip, cfg.Ne)
    psi_nodes = np.linspace(0, 2 * np.pi * (1 - 1.0 / cfg.Npsi), cfg.Npsi)
    R_NORM, PSI = np.meshgrid(r_norm_nodes, psi_nodes, indexing="ij")
    R_DIM = R_NORM * rotor.R
    chord_nodes, theta_nodes = rotor.chord_theta_at(r_norm_nodes)
    CHORD = np.repeat(chord_nodes[:, None], cfg.Npsi, axis=1)
    THETA = np.repeat(theta_nodes[:, None], cfg.Npsi, axis=1)
    return r_norm_nodes, psi_nodes, R_NORM, PSI, R_DIM, CHORD, THETA


def _pitt_peters_forcing(rotor: Rotor, airfoil, cfg: BEMTConfig, mu_x, lambda_z,
                          r_norm_nodes, psi_nodes, R_NORM, PSI, R_DIM, CHORD, THETA, nu,
                          motion=None):
    """Given nu=(nu0,nu_s,nu_c), builds lambda_i(r,psi) DIRECTLY (without
    solving BEMT element by element . This is Pitt-Peters' central
    simplification), evaluates `element_state` (reusing reverse flow,
    Himmelskamp, radial flow, compressibility, Prandtl) and integrates the
    3 "forcings" (CT, C_s=CMy, C_c=CMx) with the same definitions as
    `aggregate_results`. Also returns lambda_i (field) and the `state`
    from `element_state`, for reuse without re-evaluating the
    aerodynamics twice.

    ``motion`` (Section 4h, optional): forwarded into `element_state` so
    the blade's flap/lag state reaches the forcing too."""
    nu0, nu_s, nu_c = nu
    lambda_i = nu0 + nu_c * R_NORM * np.cos(PSI) + nu_s * R_NORM * np.sin(PSI)
    state = element_state(lambda_i, R_NORM, PSI, R_DIM, CHORD, THETA, mu_x, lambda_z,
                           rotor.Nb, rotor.Omega, rotor.OmegaR, airfoil, cfg,
                           rotor.r_root_norm_geom, rotor.r_tip_norm_geom,
                           motion=motion)
    Fn = state["Fn"]

    def disk_integral(field_2d):
        radial = _trapz(field_2d, r_norm_nodes * rotor.R, axis=0)
        return rotor.Nb * _trapz_psi_periodic(radial, psi_nodes) / (2 * np.pi)

    Thrust = disk_integral(Fn)
    Mx = disk_integral(-Fn * R_DIM * np.cos(PSI))
    My = disk_integral(-Fn * R_DIM * np.sin(PSI))
    qA = cfg.rho * np.pi * rotor.R ** 2 * rotor.OmegaR ** 2
    CT = Thrust / qA
    CMx = Mx / (qA * rotor.R)
    CMy = My / (qA * rotor.R)
    forcing = np.array([CT, CMy, CMx])  # order matched to (nu0,nu_s,nu_c)
    return forcing, lambda_i, state


def _solve_pitt_peters_steady(rotor: Rotor, airfoil, cfg: BEMTConfig, mu_x, lambda_z,
                               r_norm_nodes, psi_nodes, R_NORM, PSI, R_DIM, CHORD, THETA,
                               nu0_guess=None, motion=None):
    """OUTER fixed point (a few dozen iterations over just 3 scalars, not
    over the Ne x Npsi grid) for the steady state of the Pitt-Peters
    model: at equilibrium, M*dnu/dtau=0 => V*L^-1*nu=forcing(nu) =>
    nu = L*V^-1*forcing(nu). Since forcing depends on nu (via the blade
    aerodynamics) and L,V depend on nu (via nu0, in the wake angle),
    iterates with relaxation until nu stops changing.

    ``motion`` (Section 4h, optional): forwarded into every
    `_pitt_peters_forcing` call."""
    if cfg.pitt_peters_states != 3:
        raise NotImplementedError(
            "pitt_peters_states=5 (Peters-He with second harmonic) is not "
            "implemented in this version . Only the classic 3-state model "
            "(nu0,nu_s,nu_c) is available. Use pitt_peters_states=3.")
    nu = np.zeros(3) if nu0_guess is None else np.array(nu0_guess, dtype=float)
    if nu0_guess is None:
        # MOMENTUM-THEORY SEED, not nu=0.
        #
        # V = (VT, Vbar, Vbar) normalizes the forcing, and VT = sqrt(mu_x^2 +
        # lambda^2). Starting from nu=0 in HOVER (mu_x=0, lambda_z=0) both
        # quantities are zero: VT falls to the 1e-9 floor built into the
        # square root, the first `forcing/V` is divided by ~3e-5 and nu0
        # jumps to ~355 (against 0.12 for the solution). The relaxed
        # iteration comes back from that jump, but passes through
        # lambda<0 on the way, and there alpha* = -90deg, where the L
        # matrix is singular (see `DENOMINADOR_MINIMO_DE_PITT_PETERS`).
        # The result was CT=nan in hover, with no exception or warning.
        #
        # In edgewise flight none of this shows up because mu_x already
        # gives VT a nonzero scale . That is why the defect only existed
        # exactly at mu_x=0, and mu_x=0.001 converged normally.
        #
        # lambda_i = sqrt(CT/2) is the hover value from momentum theory
        # itself (Sec. 2.9.1), evaluated at the CT the blade produces with
        # zero inflow . One more iteration, and already in the right
        # order of magnitude.
        forcing_semente, _, _ = _pitt_peters_forcing(
            rotor, airfoil, cfg, mu_x, lambda_z, r_norm_nodes, psi_nodes,
            R_NORM, PSI, R_DIM, CHORD, THETA, nu, motion=motion)
        nu[0] = float(np.sqrt(max(float(forcing_semente[0]), 0.0) / 2.0))
    forcing = lambda_i = state = None
    n_it = 0
    # Sideslip (SC-14): the L matrix's fore-aft coupling follows the WAKE
    # skew, i.e. the free-stream direction -- not the hub's x axis. With
    # psi_w != 0 the harmonic pair (CMx->nu_c on cos(psi), CMy->nu_s on
    # sin(psi)) is rotated into wind axes before L acts and back after,
    # so the model turns with the flow exactly as the disk does. The two
    # maps below are exact inverses of each other.
    psi_w = np.deg2rad(float(getattr(cfg, "inflow_sideslip_deg", 0.0)))
    cw, sw = float(np.cos(psi_w)), float(np.sin(psi_w))

    def _to_wind(f_hub):
        # f_hub = [CT, CMy(sin slot), CMx(cos slot)] -> shifted by -psi_w.
        ct, s_sin, c_cos = f_hub
        return np.array([ct,
                          s_sin * cw + c_cos * sw,
                          c_cos * cw - s_sin * sw])

    def _to_hub(nu_wind):
        n0, s_sin, c_cos = nu_wind
        return np.array([n0,
                          s_sin * cw - c_cos * sw,
                          c_cos * cw + s_sin * sw])

    for n_it in range(1, cfg.pitt_peters_outer_iter + 1):
        forcing, lambda_i, state = _pitt_peters_forcing(
            rotor, airfoil, cfg, mu_x, lambda_z, r_norm_nodes, psi_nodes,
            R_NORM, PSI, R_DIM, CHORD, THETA, nu, motion=motion)
        L, V = _pitt_peters_L_V(mu_x, nu[0], lambda_z)
        nu_target = _to_hub(L @ (_to_wind(forcing) / np.maximum(V, 1e-6)))
        delta = nu_target - nu
        nu = nu + cfg.pitt_peters_relax * delta
        if np.max(np.abs(delta)) < cfg.pitt_peters_tol:
            break
    # re-evaluates once more at the converged nu to return consistent fields
    forcing, lambda_i, state = _pitt_peters_forcing(
        rotor, airfoil, cfg, mu_x, lambda_z, r_norm_nodes, psi_nodes,
        R_NORM, PSI, R_DIM, CHORD, THETA, nu, motion=motion)

    # --- Validity diagnostics -----------------------------------------------
    # The 3-state Pitt-Peters model is a LINEAR theory (1st-order
    # perturbation about the uniform actuator disk). Since this code does
    # not model flapping, the CMx/CMy moments are not "relieved" by
    # flapping as they would be on a real articulated rotor, and come out
    # larger . Feeding this large forcing back into Pitt-Peters' LINEAR
    # gain, nu_s/nu_c can grow enough that lambda_total=lambda_z+lambda_i
    # becomes NEGATIVE (local reversed flow/upflow) over a large fraction
    # of the disk, pushing the model outside the linear theory's validity
    # range . Observable symptom: CQ can even change sign (seen at
    # mu_x~0.16-0.19 with the example geometry). This is not numerically
    # clamped here on purpose (masking the physics would be worse than
    # reporting it) . Only flagged, for the user to decide (reduce mu_x,
    # use 'global'/'local', or implement flapping/cyclic trim in the
    # future).
    frac_reversed = float(np.mean(state["lambda_total"] < 0.0))
    pp_warning = None
    if frac_reversed > 0.02:
        pp_warning = (
            f"Pitt-Peters: {frac_reversed:.1%} do disco com lambda_total<0 "
            f"(local induced flow reversed) . The linear model is probably "
            f"outside its validity range for this condition (mu_x, no flapping). "
            f"CQ/CMx/CMy results may be physically unreliable.")
    state["pitt_peters_warning"] = pp_warning
    state["pitt_peters_frac_reversed"] = frac_reversed
    return nu, lambda_i, state, n_it


def _pitt_peters_rhs(nu, rotor, airfoil, cfg, mu_x, lambda_z, r_norm_nodes, psi_nodes,
                      R_NORM, PSI, R_DIM, CHORD, THETA):
    """Right-hand side of the ODE M*dnu/dtau = forcing(nu) - V(nu)*L(nu)^-1*nu,
    with tau=Omega*t (non-dimensional time . Consistent with the
    normalization of `_PP_M3`, see eq.(4) of the NASA TM-88327 cited
    above). Kept for clarity/debugging. The integrator used in
    `run_sweep_unsteady_pitt_peters` is the exponential one below
    (`_pitt_peters_exp_step`), not plain RK4 on this RHS , see the why
    in that function's docstring."""
    forcing, lambda_i, state = _pitt_peters_forcing(
        rotor, airfoil, cfg, mu_x, lambda_z, r_norm_nodes, psi_nodes,
        R_NORM, PSI, R_DIM, CHORD, THETA, nu)
    L, V = _pitt_peters_L_V(mu_x, nu[0], lambda_z)
    Linv = np.linalg.inv(L)
    rhs = (forcing - V * (Linv @ nu)) / _PP_M3
    return rhs, lambda_i, state


def _pitt_peters_exp_step(nu, dtau, rotor, airfoil, cfg, mu_x, lambda_z, r_norm_nodes,
                           psi_nodes, R_NORM, PSI, R_DIM, CHORD, THETA,
                           motion=None):
    """Advances nu by dtau (non-dimensional time, tau=Omega*t) via
    EXPONENTIAL integration ("exponential Euler"/integrating factor),
    treating forcing(nu), L(nu), V(nu) as FROZEN at the value of nu at
    the start of the sub-step (local linearization about the current
    state).

    WHY NOT PLAIN RK4: the natural time constant of Pitt-Peters inflow
    is tau_i ~ L_ii*M_ii ~ O(0.1-0.3) IN UNITS OF tau=Omega*t. That is, in
    real time, tau_i/Omega is typically ~ a few milliseconds (rotor
    spinning at hundreds/thousands of RPM). This is 1-2 orders of
    magnitude faster than a typical physical time step between flight
    conditions in a sweep (dt~0.1-1s). An EXPLICIT RK4 on this ODE is a
    conditionally stable method, and would need
    thousands of sub-steps to avoid diverging in this regime . This was
    exactly what caused NaN/divide-by-zero in a test with few sub-steps
    (RK4 "shooting" nu outside the physical domain in a single
    sub-iteration). The exponential form solves the LINEARIZED (frozen)
    ODE EXACTLY within the sub-step, so it is UNCONDITIONALLY STABLE:
    with few sub-steps (even 1), nu already relaxes smoothly (and
    correctly) toward equilibrium when dtau >> tau_i, with no
    NaN/overshoot . Exactly the expected physical behavior (the inflow
    response is "instantaneous" compared to the sweep's time scale).

    ``motion`` (Section 4h): forwarded into the forcing so the blade's
    flap state reaches the marched dynamics too.
    """
    forcing, lambda_i, state = _pitt_peters_forcing(
        rotor, airfoil, cfg, mu_x, lambda_z, r_norm_nodes, psi_nodes,
        R_NORM, PSI, R_DIM, CHORD, THETA, nu, motion=motion)
    L, V = _pitt_peters_L_V(mu_x, nu[0], lambda_z)
    Linv = np.linalg.inv(L)
    Minv_diag = 1.0 / _PP_M3
    A = -(Minv_diag[:, None] * (np.diag(V) @ Linv))   # dnu/dtau = A@nu + b (frozen)
    b = Minv_diag * forcing
    try:
        nu_eq = np.linalg.solve(A, -b)
    except np.linalg.LinAlgError:
        nu_eq = np.linalg.lstsq(A, -b, rcond=None)[0]
    nu_next = nu_eq + expm(A * dtau) @ (nu - nu_eq)
    return nu_next, lambda_i, state


def steady_pitt_peters_state(rotor: Rotor, airfoil, cfg: BEMTConfig,
                              mu_x: float, Vz: float) -> "np.ndarray":
    """Solves the algebraic equilibrium of the 3-state Pitt-Peters model
    at ONE condition and returns nu = (nu0, nu_s, nu_c). This is the
    'equilibrium' initial state of a maneuver (SC-12): the march then
    starts without an inflow start-up transient."""
    _check_rotor_rotation(rotor)
    (r_norm_nodes, psi_nodes, R_NORM, PSI, R_DIM,
     CHORD, THETA) = _pitt_peters_geometry(rotor, cfg)
    lambda_z = Vz / rotor.OmegaR
    nu, _lam, _state, _n = _solve_pitt_peters_steady(
        rotor, airfoil, cfg, mu_x, lambda_z, r_norm_nodes, psi_nodes,
        R_NORM, PSI, R_DIM, CHORD, THETA)
    return nu


def run_maneuver(rotor_builder, airfoil, cfg: BEMTConfig, samples: list, *,
                  dynamics=None, initial_nu=None, substeps_per_step: int = 8,
                  march_dynamic_stall: bool = False,
                  march_flapping: bool = False, on_sample_done=None,
                  should_cancel=None, verbose: bool = False):
    """Marches the 3-state Pitt-Peters inflow along a PRESCRIBED
    trajectory (SC-12). ``samples`` is a list of resolved maneuver points
    -- objects carrying ``t_s``, ``mu_x``, ``Vz``, ``cyclic_c_deg``,
    ``cyclic_s_deg`` and a CONCRETE ``rpm`` -- in strictly increasing
    time order; ``rotor_builder(point)`` returns the `Rotor` for that
    point, because rpm and collective live on it. Unlike the steady
    paths, each sample inherits the inflow state of the sample before
    it: the three inflow states ARE the marched degrees of freedom.

    Integration keeps the EXPONENTIAL step (`_pitt_peters_exp_step`):
    unconditionally stable for the inflow's stiff time constants, where
    plain Runge-Kutta diverges with few sub-steps. When the rpm changes
    between samples, ``dtau`` uses the rpm of the sample being ENTERED,
    because that is the rotation the incoming state evolves under.

    Coupled marched states (both default off):

    - ``march_dynamic_stall`` threads the Oye separation state from
      sample to sample -- each sample's march starts at the previous
      sample's final values -- so separation stays continuous along the
      trajectory. Requires dynamic stall enabled on the airfoil; the
      'time_march' method is used for the march itself.
    - ``march_flapping`` solves the periodic flap response at every
      sample from that sample's field and feeds the motion back into the
      loads. The response stays quasi-steady INSIDE each sample: this is
      NOT a flap transient, and it does not capture the flap mode.

    Per sample the result records the state vector, the marched interval
    and the sub-step count (EN-9's report requirements).

    Returns ``(pd.DataFrame, list[maps_dict])`` as everywhere else."""
    from . import geometry as geometry_gen

    if len(samples) == 0:
        raise ValueError("run_maneuver: samples is empty.")
    total = len(samples)

    def _cancel():
        if should_cancel is not None and should_cancel():
            raise SolveCancelled()

    f_prev = None
    rows: list[dict] = []
    maps_list: list[dict] = []
    nu = np.zeros(3) if initial_nu is None else np.array(initial_nu,
                                                          dtype=float)
    t_prev = float(samples[0].t_s)

    for index, point in enumerate(samples):
        _cancel()
        rotor = rotor_builder(point)
        _check_rotor_rotation(rotor)
        mu_x = float(point.mu_x)
        lambda_z = float(point.Vz) / rotor.OmegaR
        r_norm_nodes, psi_nodes, R_NORM, PSI, R_DIM, CHORD, THETA = \
            _pitt_peters_geometry(rotor, cfg)
        scalars = {
            "e_hinge_dim": 0.0,
            "pitch_flap_K": 0.0,
            "cyclic_c_rad": np.deg2rad(float(getattr(point,
                                                      "cyclic_c_deg", 0.0))),
            "cyclic_s_rad": np.deg2rad(float(getattr(point,
                                                      "cyclic_s_deg", 0.0))),
        }
        motion, _rn, psi_nodes, R_NORM, PSI = build_motion_grid(
            rotor, cfg, scalars)

        dt = max(float(point.t_s) - t_prev, 0.0) if index > 0 else 0.0
        n_sub = 0
        if index > 0 and dt > 0.0:
            # dtau uses the rpm OF THE SAMPLE BEING ENTERED (this one):
            # the incoming state evolves under the rotation it arrives at.
            n_sub = max(int(substeps_per_step), 1)
            dtau = (rotor.Omega * dt) / n_sub
            for _step in range(n_sub):
                _cancel()
                nu, _, _ = _pitt_peters_exp_step(
                    nu, dtau, rotor, airfoil, cfg, mu_x, lambda_z,
                    r_norm_nodes, psi_nodes, R_NORM, PSI, R_DIM, CHORD,
                    THETA, motion=motion)

        forcing, lambda_i, state = _pitt_peters_forcing(
            rotor, airfoil, cfg, mu_x, lambda_z, r_norm_nodes, psi_nodes,
            R_NORM, PSI, R_DIM, CHORD, THETA, nu, motion=motion)

        maps = dict(r_norm_nodes=r_norm_nodes, psi_nodes=psi_nodes,
                    R_DIM=R_DIM, R_NORM=R_NORM, PSI=PSI, lambda_i=lambda_i,
                    converged=np.ones_like(lambda_i, dtype=bool),
                    n_iter=np.ones_like(lambda_i, dtype=int),
                    total_iterations=1, elapsed=0.0,
                    residual_history=[], frac_converged_history=[],
                    mu_x=mu_x, Vz=float(point.Vz),
                    solver="pitt_peters_unsteady",
                    inflow_coupling="pitt_peters_unsteady",
                    pitt_peters_nu=nu.copy())
        maps.update(state)

        # --- coupled marched state 1: the Oye separation function ------
        if march_dynamic_stall:
            cfg_ds = _resolve_dynamic_stall_config(cfg, airfoil)
            if not cfg_ds.use_dynamic_stall:
                raise ValueError(
                    "run_maneuver: 'march dynamic stall' needs dynamic "
                    "stall enabled on the Airfoil tab.")
            if cfg_ds.dynamic_stall_method.lower() != "time_march":
                cfg_ds = replace(cfg_ds, dynamic_stall_method="time_march")
            maps = apply_dynamic_stall(maps, rotor, airfoil, cfg_ds,
                                        R_NORM, PSI, R_DIM, CHORD, mu_x,
                                        lambda_z, f_init=f_prev)
            history = maps.get("dynamic_stall_time_march_history")
            if history is not None:
                f_prev = np.array(history[-1][:, -1], copy=True)

        # --- coupled marched state 2: quasi-steady flap response -------
        beta_note = None
        if march_flapping and dynamics is not None \
                and dynamics.flap_model != "rigid":
            cl_alpha, _a0 = _airfoil_cl_alpha_alpha0(airfoil)
            chord_ref = float(np.interp(
                geometry_gen.REFERENCE_CHORD_STATION,
                np.asarray(rotor.r_geom, dtype=float),
                np.asarray(rotor.chord_geom, dtype=float) / rotor.R)) * rotor.R
            inertia = geometry_gen.resolve_flap_inertia(
                inertia_source=dynamics.inertia_source,
                lock_number=dynamics.lock_number,
                flap_inertia_kg_m2=dynamics.flap_inertia_kg_m2,
                blade_mass_kg=dynamics.blade_mass_kg,
                hinge_offset_norm=dynamics.hinge_offset_norm,
                radius_m=rotor.R, chord_ref_m=chord_ref,
                rho=cfg.rho, cl_alpha=cl_alpha)
            if not (np.isfinite(inertia) and inertia > 0.0):
                raise ValueError(
                    "run_maneuver: 'march flapping' resolved a non-positive "
                    "flap inertia; check the blade-dynamics block.")
            e_norm = float(dynamics.hinge_offset_norm)
            gamma_resolved = (cfg.rho * cl_alpha * chord_ref * rotor.R ** 4
                               / max(inertia, 1e-12))
            nu_beta_sq = geometry_gen.flap_frequency_ratio_squared(
                e_norm, max(dynamics.flap_spring_nm_per_rad, 0.0),
                inertia, rotor.Omega)
            try:
                coeffs, angle, rate = solve_blade_motion(
                    _flap_moment(maps, rotor, e_norm * rotor.R), psi_nodes,
                    nu_beta_sq, inertia, rotor.Omega,
                    max(int(dynamics.harmonics), 1),
                    damping=geometry_gen.flap_aero_damping(gamma_resolved,
                                                            e_norm),
                    freedom="flap", hinge_offset_norm=e_norm)
            except ValueError as exc:
                beta_note = str(exc)
            else:
                scalars["e_hinge_dim"] = e_norm * rotor.R
                scalars["pitch_flap_K"] = np.tan(np.deg2rad(
                    dynamics.pitch_flap_coupling_deg))
                motion, _rn, psi_nodes, R_NORM, PSI = build_motion_grid(
                    rotor, cfg, scalars, beta_psi=angle, beta_rate_psi=rate)
                forcing, lambda_i, state = _pitt_peters_forcing(
                    rotor, airfoil, cfg, mu_x, lambda_z, r_norm_nodes,
                    psi_nodes, R_NORM, PSI, R_DIM, CHORD, THETA, nu,
                    motion=motion)
                maps.update(state)
                maps["lambda_i"] = lambda_i
                maps["beta_coeffs"] = {int(k): tuple(v)
                                        for k, v in coeffs.items()}
                maps["beta_0_rad"] = float(coeffs[0][0])
                first = coeffs.get(1, (0.0, 0.0))
                maps["beta_1c_rad"] = float(first[0])
                maps["beta_1s_rad"] = float(first[1])

        row = aggregate_results(rotor, cfg, maps)
        row["t"] = float(point.t_s)
        # Echo the commanded controls so the time-history table (and the
        # report's control panel) shows what WAS commanded per sample.
        row.setdefault("collective_deg",
                        float(getattr(point, "collective_deg", 0.0)))
        row.setdefault("cyclic_c_deg",
                        float(getattr(point, "cyclic_c_deg", 0.0)))
        row.setdefault("cyclic_s_deg",
                        float(getattr(point, "cyclic_s_deg", 0.0)))
        row["nu0"], row["nu_s"], row["nu_c"] = nu
        row["marched_interval_s"] = dt
        row["substeps"] = n_sub
        if index == 0:
            row["initial_state"] = ("equilibrium"
                                     if initial_nu is not None else "zero")
        if beta_note:
            row["flap_error"] = beta_note
        rows.append(row)
        maps_list.append(maps)
        if on_sample_done is not None:
            on_sample_done(index + 1, total, row)
        if verbose:
            print(f"  t={float(point.t_s):6.3f}s  mu_x={mu_x:5.3f} "
                  f"CT={row['CT']:.5f} | nu=({nu[0]:+.4f},{nu[1]:+.4f},"
                  f"{nu[2]:+.4f})")
        t_prev = float(point.t_s)

    return pd.DataFrame(rows), maps_list


def run_sweep_unsteady_pitt_peters(rotor: Rotor, airfoil, cfg: BEMTConfig,
                                    time_mu_Vv, nu0=None,
                                    substeps_per_step: int = 8,
                                    verbose: bool = True):
    """Compatibility wrapper around `run_maneuver`: sweeps a TIME SEQUENCE
    of ``(t_seconds, mu_x, Vz)`` tuples at THIS rotor's fixed rpm,
    collective and twist, starting from the given (or zero) inflow state.
    New code should call `run_maneuver` directly, which also supports
    per-sample rpm/collective/cyclic and the coupled marched states
    (SC-12).

    The marched states are only the 3 scalars (nu0, nu_s, nu_c); the full
    Ne x Npsi field is reconstructed algebraically per sub-step, which is
    why an unsteady maneuver costs about one `element_state` evaluation
    per sub-step."""
    from types import SimpleNamespace
    if len(time_mu_Vv) == 0:
        raise ValueError("time_mu_Vv is empty.")
    samples = [SimpleNamespace(t_s=float(t), mu_x=float(mu_x), Vz=float(Vz),
                                cyclic_c_deg=0.0, cyclic_s_deg=0.0,
                                rpm=rotor.Omega_rpm)
               for (t, mu_x, Vz) in time_mu_Vv]
    return run_maneuver(
        lambda _point: rotor, airfoil, cfg, samples,
        initial_nu=(np.zeros(3) if nu0 is None else np.array(nu0,
                                                              dtype=float)),
        substeps_per_step=substeps_per_step, verbose=verbose)


def _check_rotor_rotation(rotor: Rotor) -> None:
    """Rejects zero/negative rotation BEFORE any division by ``OmegaR``.
    Without this, ``rpm=0`` (a value perfectly accepted by
    ``FlightCondition``) generates silent inf/nan instead of an error."""
    if not np.isfinite(rotor.Omega_rpm):
        raise ValueError(f"Rotor RPM invalid: {rotor.Omega_rpm!r}.")
    if rotor.OmegaR <= 1e-9:
        raise ValueError(
            f"Rotor rotation is zero or negative (RPM={rotor.Omega_rpm:g}, "
            f"R={rotor.R:g} m => Omega*R={rotor.OmegaR:g} m/s). BEMT "
            f"non-dimensionalizes by Omega*R. Therefore, the rotation must be "
            f"greater than zero.")


def solve_bemt(rotor: Rotor, airfoil, cfg: BEMTConfig, mu_x: float, Vz: float,
                should_cancel=None, motion=None):
    """Solves the inflow field lambda_i(r,psi) for a flight condition
    (mu_x, Vz) and returns a dictionary with all the per-element maps.

    ``should_cancel``: a no-argument callable, queried once per solver
    iteration. If it returns ``True``, the solve raises
    ``SolveCancelled`` . It does not return a partial result, which
    would pass for a valid result. Without it (default), nothing
    changes.

    ``motion`` (optional): the rigid-blade flap/lag state of Section 4h
    (SC-11), forwarded verbatim into `element_state`. ``None`` keeps the
    rigid disk; every caller that does not pass it sees no change."""
    r_eff_root = rotor.r_root_norm_geom + cfg.integration_offset
    r_eff_tip = rotor.r_tip_norm_geom - cfg.integration_offset
    if r_eff_root >= r_eff_tip:
        raise ValueError("integration_offset too large (or Ne too small).")

    # Without this guard, `lambda_z = Vz / rotor.OmegaR` right below
    # produces inf/nan that propagate through every map into a
    # normal-looking result, with no error at all. Zero rotation is not a
    # BEMT flight condition . It is invalid input.
    _check_rotor_rotation(rotor)

    r_norm_nodes = np.linspace(r_eff_root, r_eff_tip, cfg.Ne)
    psi_nodes = np.linspace(0, 2 * np.pi * (1 - 1.0 / cfg.Npsi), cfg.Npsi)
    R_NORM, PSI = np.meshgrid(r_norm_nodes, psi_nodes, indexing="ij")  # (Ne,Npsi)
    R_DIM = R_NORM * rotor.R

    chord_nodes, theta_nodes = rotor.chord_theta_at(r_norm_nodes)
    CHORD = np.repeat(chord_nodes[:, None], cfg.Npsi, axis=1)
    THETA = np.repeat(theta_nodes[:, None], cfg.Npsi, axis=1)

    lambda_z = Vz / rotor.OmegaR

    spec = _resolve_inflow_field_model(cfg.inflow_field_model)
    if spec["unsteady"]:
        raise ValueError(
            f"inflow_field_model={cfg.inflow_field_model!r} is the UNSTEADY variant "
            "of Pitt-Peters. `solve_bemt` resolves isolated flight conditions only, "
            "at algebraic equilibrium. It does not resolve a time sequence. Use "
            "`run_sweep_unsteady_pitt_peters(rotor, airfoil, cfg, time_mu_Vv=...)` to "
            "march the inflow in time, or change to 'pitt_peters_steady'."
        )
    coupling = spec["coupling"]

    def residual_fn(lam):
        return element_state(lam, R_NORM, PSI, R_DIM, CHORD, THETA, mu_x, lambda_z,
                              rotor.Nb, rotor.Omega, rotor.OmegaR, airfoil, cfg,
                              rotor.r_root_norm_geom, rotor.r_tip_norm_geom,
                              motion=motion)

    t0 = time.perf_counter()

    if coupling == "global":
        # --- Fast mode: mean axisymmetric inflow + linear harmonic variation ---
        # 1) solves a 1D BEMT (effective Npsi = 1, Ut = Omega*r, no advance
        #    component) to get lambda0(r) . Much cheaper.
        #    inflow_sideslip_deg is FORCED to 0 here: this solve defines the
        #    AXISYMMETRIC mean; the sideslip belongs to the harmonic that
        #    modulates it below (SC-14).
        cfg_1d = replace(cfg, Npsi=1, inflow_field_model="glauert_local",
                          inflow_sideslip_deg=0.0, collect_history=False)
        R_NORM_1d, PSI_1d = np.meshgrid(r_norm_nodes, np.array([0.0]), indexing="ij")
        R_DIM_1d = R_NORM_1d * rotor.R
        CHORD_1d = chord_nodes[:, None]
        THETA_1d = theta_nodes[:, None]

        def residual_1d(lam):
            # IMPORTANT: `mu_x` (not 0.0) must be passed here even at
            # fixed psi=0 . Ut=Omega*r+Vinf*sin(0) does not change with
            # mu_x, but the mass-flow term of the momentum equation in
            # `element_state` uses sqrt(lambda_total**2+mu_x**2), which
            # ALWAYS depends on mu_x. Zeroing mu_x made this 1D BEMT
            # compute a hover-order lambda0(r) even in forward flight
            # (mu_x=0.4 gave lambda0~0.14 near the tip, about 7x the
            # physical value ~0.02 the converged 'local' mode produces
            # there), because the mass flow increased by forward speed
            # (which reduces the mean inflow) never entered the equation.
            return element_state(lam, R_NORM_1d, PSI_1d, R_DIM_1d, CHORD_1d, THETA_1d,
                                  mu_x, lambda_z, rotor.Nb, rotor.Omega, rotor.OmegaR,
                                  airfoil, cfg_1d, rotor.r_root_norm_geom, rotor.r_tip_norm_geom)

        lam0_guess = _initial_guess(rotor, airfoil, r_norm_nodes, 1)
        lam0, _, _, _, _, _, _ = solve_newton(residual_1d, lam0_guess, cfg_1d)
        lam0_r = lam0[:, 0]

        # 2) global wake angle from the lambda mean weighted by r dr
        w = r_norm_nodes
        lam_mean = float(_trapz(lam0_r * w, r_norm_nodes) / _trapz(w, r_norm_nodes))
        Kx_g, Ky_g = _inflow_harmonics(spec["harmonic"], mu_x, np.array([lam_mean]))
        Kx_g, Ky_g = float(Kx_g[0]), float(Ky_g[0])
        # Sideslip (SC-14): the gains' azimuthal pattern follows the wake
        # skew -- rotate it with the free stream (legacy when psi_w = 0).
        psi_w_g = np.deg2rad(float(getattr(cfg, "inflow_sideslip_deg", 0.0)))
        harmonic = (1.0 + Kx_g * R_NORM * np.cos(PSI - psi_w_g)
                     + Ky_g * R_NORM * np.sin(PSI - psi_w_g))
        LAMBDA0 = np.repeat(lam0_r[:, None], cfg.Npsi, axis=1)
        lam = np.clip(LAMBDA0 * harmonic, -0.5, 0.5)

        state = residual_fn(lam)
        converged = np.ones_like(lam, dtype=bool)  # direct evaluation, not iterative
        n_iter = np.ones_like(lam, dtype=int)
        total_it = 1
        history = []
        frac_hist = []
        pp_nu = None
    elif coupling == "pitt_peters":
        # --- Finite-state dynamic inflow (Pitt-Peters), see Section 6b ---
        nu, lam, state, n_outer = _solve_pitt_peters_steady(
            rotor, airfoil, cfg, mu_x, lambda_z, r_norm_nodes, psi_nodes,
            R_NORM, PSI, R_DIM, CHORD, THETA, motion=motion)
        converged = np.ones_like(lam, dtype=bool)
        n_iter = np.full_like(lam, n_outer, dtype=int)
        total_it = n_outer
        history = []
        frac_hist = []
        pp_nu = nu
    else:
        lam_guess = _initial_guess(rotor, airfoil, r_norm_nodes, cfg.Npsi)
        solver_fn = _SOLVERS.get(cfg.solver)
        if solver_fn is None:
            raise ValueError(f"Unknown solver: {cfg.solver}. Options: {list(_SOLVERS)}")
        lam, state, converged, n_iter, total_it, history, frac_hist = solver_fn(
            residual_fn, lam_guess, cfg, R_NORM=R_NORM, PSI=PSI, mu_x=mu_x,
            should_cancel=should_cancel)
        pp_nu = None

    elapsed = time.perf_counter() - t0

    maps = dict(r_norm_nodes=r_norm_nodes, psi_nodes=psi_nodes, R_DIM=R_DIM, R_NORM=R_NORM,
                PSI=PSI, lambda_i=lam, converged=converged, n_iter=n_iter,
                total_iterations=total_it, elapsed=elapsed, residual_history=history,
                frac_converged_history=frac_hist, pitt_peters_nu=pp_nu,
                mu_x=mu_x, Vz=Vz, solver=cfg.solver, inflow_coupling=coupling, rho=cfg.rho)
    maps.update(state)

    cfg_ds = _resolve_dynamic_stall_config(cfg, airfoil)
    if cfg_ds.use_dynamic_stall:
        maps = apply_dynamic_stall(maps, rotor, airfoil, cfg_ds, R_NORM, PSI, R_DIM, CHORD, mu_x, lambda_z)

    return maps


# =============================================================================
# 6c. ROTOR/PROPELLER MODE AND FLEXIBLE NON-DIMENSIONALIZATION
# =============================================================================
#
# THE SOLVING ENGINE (`solve_bemt`, `element_state`) IS AGNOSTIC to the
# rotor/propeller convention: it only sees the pair (mu_x, Vz), where:
#   - mu_x  = the advance component that varies with azimuth (enters as
#           Vinf*sin(psi) in Ut) . ALWAYS non-dimensionalized by
#           Omega*R, regardless of `cfg.is_propeller`.
#   - Vz  = the advance component uniform over the disk (enters as
#           lambda_z=Vz/(Omega*R) in Up) . ALWAYS dimensional [m/s].
# We call the `mu_x` component "longitudinal" here (varies with psi, the
# classic forward-flight component of a helicopter rotor) and the `Vz`
# one "vertical/axial" (uniform over the disk, the classic climb/descent
# component of a rotor . And also the classic cruise-flight component of
# a propeller, whose axis is aligned with the flight direction).
#
# `is_propeller` does NOT change the solver physics (which is already
# general enough for any combination of the two components, in any
# proportion). It changes ONLY two things, both "interface"/reporting,
# never solution:
#   (1) the NON-DIMENSIONALIZATION used to report advance (mu_x/mu_z, rotor
#       convention, vs. J_x/J_z, propeller convention) . See
#       `resolve_advance_velocity` below;
#   (2) the NON-DIMENSIONALIZATION used to report T/Q/P (CT/CQ/CP in
#       rho*A*(Omega R)^n, rotor convention, vs. CT/CQ/CP in
#       rho*n^2*D^4, propeller convention) , see `aggregate_results`.
#
# KEY IDENTITY (used in both conversions above): since n=Omega/(2*pi)
# [rev/s] and D=2*R, we ALWAYS have Omega*R = pi*n*D, regardless of
# rotor/propeller size. Hence:
#     J_x   = Vinf/(n*D) = Vinf*pi/(Omega*R) = pi*mu_x     <=>   mu_x   = J_x/pi
#     J_z = Vz/(n*D)   = Vz*pi/(Omega*R)   = pi*mu_z    <=>   mu_z = J_z/pi
# (mu_z is a synonym for lambda_z=Vz/(Omega*R), the non-dimensional axial
# component in rotor convention.) The same constant pi holds for both
# components . It does not depend on R, Omega, or which component is
# "the main one" for the real physical vehicle. That physical distinction
# (on an airplane propeller in level flight, the "main" advance is
# usually AXIAL (along the axis), not in-plane. On a helicopter rotor
# in cruise flight, the "main" advance is usually IN-PLANE) is a matter
# of HOW the user sets up/interprets the disk, not a restriction of the
# code: the code accepts any combination of mu_x(J_x) and Vz(mu_z/J_z),
# simultaneously if needed.

# AXES: WHICH COMPONENT GETS THE LETTER "x"
# ------------------------------------------
# The pair (mu_x, Vz) above is defined relative to the DISK, and that is
# how the internal nomenclature and the ROTOR mode write it: x in the
# disk plane (V_inf,x = mu_x*OmegaR) and z along the axis (V_inf,z = Vz).
# On a helicopter in forward flight this coincides with the vehicle axes
# -- x forward, z up.
#
# On a PROPELLER it does not coincide: the rotor axis is what points
# forward. In cruise the airplane's speed is entirely AXIAL, and calling
# that component "z" (with the in-plane component, zero, called "x")
# inverts the reading for anyone looking at the airplane. That's why,
# with `is_propeller=True`, the INTERFACE rotates the letters: x becomes
# the rotor axis and z the airplane's vertical --
#     V_inf,x = Vz (internal)          mu_x = mu_z (internal)   J_x = J_z
#     V_inf,z = Vx     mu_z = mu_x   (internal)   J_z = J_x
# NOMENCLATURE OF THE TWO ANGLES: there are exactly two, one per mode:
#   `alpha_rotor` (key `alpha_rotor_deg`) is measured from the disk
#       PLANE. It is the alpha OF ROTOR mode: ~0 on a helicopter in level
#       forward flight.
#   `alpha_disk`  (key `alpha_disk_deg`) is measured from the AXIS. It is
#       the alpha OF PROPELLER mode: 0 in straight cruise.
# They are complementary (`alpha_rotor + alpha_disk = 90`, mod 360) and
# both are ALWAYS computed . But each mode shows and requests only ITS
# OWN. Each is zero at its vehicle's normal condition, and that is what
# makes the number readable. Offering both in either mode was the
# confusion to avoid.
#
# THIS IS NOMENCLATURE, NOT PHYSICS: the solver still sees (mu_x, Vz) and
# no equation changes. What changes is which screen field feeds which
# component , see `nomenclature.py::_SLOT_LABELS` . And which
# letter each output column carries . See
# `api.summary_symbols(is_propeller)`.

def resolve_advance_velocity(rotor: Rotor, cfg: BEMTConfig, *,
                              mu_x: Optional[float] = None,
                              J_x: Optional[float] = None,
                              alpha_disk_deg: Optional[float] = None,
                              Vz: Optional[float] = None,
                              mu_z: Optional[float] = None, J_z: Optional[float] = None,
                              alpha_deg: Optional[float] = None,
                              alpha_rotor_deg: Optional[float] = None):
    """Resolves ANY valid combination of flight-condition parameters
    (rotor OR propeller convention) into the internal canonical pair
    (mu_x, Vz) required by `solve_bemt`. See Section 6c above for the
    formulas.

    LONGITUDINAL COMPONENT (in-plane, maps to internal `mu_x`) . Supply
    EXACTLY ONE of: `mu_x`, `mu_x` (synonyms, rotor convention), `J_x`,
    `J_x` (synonyms, propeller convention, J_x=pi*mu_x) or
    `alpha_disk_deg` (angle between the free stream and the rotor AXIS,
    degrees . The in-plane component IS DERIVED from the axial one via
    Vx=tan(alpha_disk_deg)*Vz).

    VERTICAL/AXIAL COMPONENT (uniform over the disk, maps to internal
    `Vz`) . Supply AT MOST ONE of: `Vz`/`Vz` (dimensional, m/s,
    synonyms), `mu_z` (non-dimensional, rotor convention), `J_z`
    (non-dimensional, propeller convention, J_z=pi*mu_z), or `alpha_deg`
    (disk/propeller angle of attack, degrees . Vz IS DERIVED from the
    already-resolved longitudinal component via Vz=tan(alpha_deg)*Vx). If
    none is given, assumes level flight (Vz=0).

    THE TWO ANGLES ARE MUTUALLY EXCLUSIVE. `alpha_deg` resolves the axial
    from the in-plane one and `alpha_disk_deg` does the reverse. Given
    both, no component has an origin and the condition is indeterminate
    (any multiple of the same vector satisfies both angles). With
    `alpha_disk_deg`, the AXIAL component must come in dimensional or
    non-dimensional form . It is the one that fixes the scale.

    Returns (mu_x, Vz, meta), where `meta` is a dict with ALL equivalent
    representations of the resolved condition (mu_x, mu_z, J_x, J_z,
    alpha_rotor_deg, alpha_disk_deg, Vx) . Allows reporting the result
    in whichever convention the user prefers, regardless of which one
    they supplied.

    BOUNDARY: `meta["Vz"]` is a synonym for `meta["Vz"]` (the axial
    component of the FREE stream), because that is what `Vz=` means as
    INPUT here. In the results row from `aggregate_results` the `Vz` key
    has a different meaning . The TOTAL axial velocity through the disk
    (Vz + v_i) . And that is why `aggregate_results` discards this `Vz`
    from `meta` before building the row. Do not assume the two are the
    same.
    """
    long_specs = {"mu_x": mu_x, "J_x": J_x,
                  "alpha_disk_deg": alpha_disk_deg}
    given_long = {k: v for k, v in long_specs.items() if v is not None}
    if len(given_long) != 1:
        raise ValueError(
            f"resolve_advance_velocity: give EXACTLY ONE of mu_x, J_x or "
            f"alpha_disk_deg, which is the longitudinal component. "
            f"Received: {list(given_long)}")
    (long_kind, long_val), = given_long.items()

    # `alpha_rotor_deg` is an EXACT synonym of `alpha_deg`: the same
    # angle, and it is the standardized name . That is what the output
    # column is called, and input and output writing the same quantity
    # under different names was half of the confusion this
    # standardization removes.
    if alpha_rotor_deg is not None:
        if alpha_deg is not None:
            raise ValueError(
                "resolve_advance_velocity: alpha_deg and alpha_rotor_deg are "
                "the SAME quantity, the angle from the disk plane. Give only "
                "one of them.")
        alpha_deg = alpha_rotor_deg
    axial_specs = {"Vz": Vz, "mu_z": mu_z, "J_z": J_z, "alpha_deg": alpha_deg}
    given_axial = {k: v for k, v in axial_specs.items() if v is not None}
    if len(given_axial) > 1:
        raise ValueError(
            f"resolve_advance_velocity: give AT MOST ONE of Vz, mu_z, J_z or "
            f"alpha_deg, which is the vertical or axial component. "
            f"Received: {list(given_axial)}")

    # RESOLUTION ORDER: normally the in-plane component comes first and
    # the axial one can derive from it (`alpha_deg`). With
    # `alpha_disk_deg` the dependency reverses . It is the in-plane one
    # that derives from the axial --, so the axial must be resolved
    # first. The two angles together do not close (see docstring).
    if long_kind == "alpha_disk_deg" and "alpha_deg" in given_axial:
        raise ValueError(
            "resolve_advance_velocity: alpha_deg, measured from the PLANE, and "
            "alpha_disk_deg, measured from the SHAFT, are the same angle written "
            "two ways (alpha_disk = 90 - alpha_rotor). If you give both, no "
            "component fixes the velocity scale. Give one angle and one "
            "dimensional or non-dimensional component.")

    def _axial_de(spec: dict, Vinf_long_conhecido: float) -> float:
        if not spec:
            return 0.0
        if "Vz" in spec:
            return float(spec["Vz"])
        if "mu_z" in spec:
            return float(spec["mu_z"]) * rotor.OmegaR
        if "J_z" in spec:
            return (float(spec["J_z"]) / np.pi) * rotor.OmegaR
        return float(np.tan(np.deg2rad(spec["alpha_deg"]))) * Vinf_long_conhecido

    if long_kind == "alpha_disk_deg":
        Vv_val = _axial_de(given_axial, 0.0)
        # |Vz|, not Vz: `alpha_disk` is the flow's tilt relative to the
        # axis LINE, and with Vz<0 (axial descent, windmill) the raw sign
        # would flip the side the cross-flow points to . The reported
        # angle would stop matching the geometry. With the absolute
        # value, the angle that comes out in `alpha_disk_deg` is always
        # the real angle between the free stream and the +axis direction:
        # `alpha_disk` for Vz>0, and `180 - alpha_disk` for Vz<0 (the flow
        # arrives from the front of the disk, and that is what an obtuse
        # angle says).
        Vinf_long = float(np.tan(np.deg2rad(float(long_val)))) * abs(Vv_val)
        mu_val = Vinf_long / rotor.OmegaR
    else:
        if long_kind == "mu_x":
            mu_val = float(long_val)
        else:  # "J_x" or "J_x"
            mu_val = float(long_val) / np.pi
        Vinf_long = mu_val * rotor.OmegaR
        Vv_val = _axial_de(given_axial, Vinf_long)

    mu_z_val = Vv_val / rotor.OmegaR
    alpha_rotor_deg = (float(np.degrees(np.arctan2(Vv_val, Vinf_long)))
                        if abs(Vinf_long) > 1e-6 else (90.0 if Vv_val > 0 else (-90.0 if Vv_val < 0 else 0.0)))

    meta = dict(
        mu_x=mu_val, J_x=np.pi * mu_val,
        Vz=Vv_val, mu_z=mu_z_val, J_z=np.pi * mu_z_val,
        alpha_rotor_deg=alpha_rotor_deg,
        alpha_disk_deg=_angle_from_axis(alpha_rotor_deg),
        Vx=Vinf_long,
    )
    return mu_val, Vv_val, meta


def _angle_from_axis(alpha_rotor_deg: float) -> float:
    """Complement of `alpha_rotor_deg`: the same angle measured from the
    rotor AXIS instead of the disk plane.

    Purely axial flight (propeller in cruise) is 0deg here and 90deg
    there. Purely edgewise flight (helicopter in level forward flight) is
    90deg here and 0deg there. Axial descent (`Vz<0`, `alpha_rotor=-90deg`)
    gives 180deg: the flow arrives from the FRONT of the disk, and that is
    what 180deg says.

    The propeller in cruise is the case motivating this column . There
    `alpha_rotor` reads 90deg on a flight the pilot calls "aligned", and
    no reader would spot a 2deg misalignment by reading "88deg".

    NORMALIZED to (-180deg, 180deg]: the identity is `90 - alpha_rotor`
    MODULO 360, not the raw subtraction. With negative cross-flow AND
    axial descent (`mu_x<0`, `Vz<0`) the raw value gives 190deg, whose
    ABSOLUTE VALUE is no longer the angle between the free stream and the
    axis . 170deg is. Normalized, |alpha_disk| is always that angle,
    which is what one reads in an angle column."""
    bruto = 90.0 - float(alpha_rotor_deg)
    normalizado = (bruto + 180.0) % 360.0 - 180.0        # [-180, 180)
    if normalizado == -180.0:
        normalizado = 180.0        # pure axial descent reads 180, not -180
    return normalizado + 0.0        # kills the -0.0


def solve_bemt_flight(rotor: Rotor, airfoil, cfg: BEMTConfig, **flight_kwargs):
    """Wrapper around `solve_bemt` that accepts the flight condition in
    ANY convention (rotor or propeller, see `resolve_advance_velocity`),
    and attaches to the returned `maps` all equivalent representations
    (mu_x, mu_z, J_x, J_z, alpha_rotor_deg). Recommended use when
    `cfg.is_propeller=True`, or whenever it is more natural to specify the
    condition by J_x/J_z/alpha instead of the raw pair (mu_x, Vz)
    required by `solve_bemt`."""
    mu_x, Vz, meta = resolve_advance_velocity(rotor, cfg, **flight_kwargs)
    maps = solve_bemt(rotor, airfoil, cfg, mu_x, Vz)
    maps.update(meta)
    return maps


# =============================================================================
# 7. RESULTS AGGREGATION (forces, moments, coefficients)
# =============================================================================

def aggregate_results(rotor: Rotor, cfg: BEMTConfig, maps: dict,
                       alpha_rotor: Optional[float] = None,
                       meta: Optional[dict] = None,
                       export_settings: bool = True) -> dict:
    """Integrates the 2D disk fields (Fn, Ft, Ft_i, Ft_p . Already
    solved by `solve_bemt`) into ONE row of "global" results (forces,
    moments, and ALL possible non-dimensionalizations), plus the input
    conditions and the run's full "data sheet" (rotor + solver
    configuration).

    PHILOSOPHY OF THIS FUNCTION: the row returned here is normally what
    becomes one CSV row after a `run_sweep`. To never lose information in
    a future post-processing step, IT ALWAYS CONTAINS:
      (a) both coefficient "vocabularies" . ROTOR convention
          (CT,CQ,CP,... in rho*A*(Omega R)^n, mu_x, mu_z, FM) AND
          PROPELLER convention (CT_prop,CQ_prop,CP_prop, J_x, J_z,
          eta_prop) . At the same time, INDEPENDENT of
          `cfg.is_propeller`. That flag does not decide what is
          computed/exported (that is always everything). It is only used
          elsewhere (when PLOTTING, or in `run_sweep`'s defaults) to
          choose which of the two families is "natural" for that case.
      (b) the input flight conditions resolved in every equivalent
          representation (mu_x/mu_x/J_x/J_x, Vz/mu_z/J_z,
          alpha_rotor_deg) . If a `meta` (returned by
          `resolve_advance_velocity`) is passed, it is used. Otherwise,
          these columns are rebuilt right here from (mu_x,Vz,OmegaR),
          guaranteeing they are NEVER missing. WATCH the boundary: `Vz`
          is the axial component of the FREE stream (symbol V_inf,z in
          the report/GUI). `Vz` is NOT a synonym for it here . It is the
          TOTAL axial velocity through the disk, Vz + v_i =
          lambda*Omega*R (the manual's U_P). The `Vz` that
          `resolve_advance_velocity` accepts as INPUT is still a synonym
          for `Vz`. It is discarded from `meta` at this point.
      (b') the RESOLVED axial flow: `lambda_i` (induced inflow ratio),
          `lambda_total` (= lambda_z + lambda_i), `Vi` (induced velocity)
          and `Vz` . Averages weighted by ring area over the meshed
          span of the disk.
      (c) the full "settings sheet": every field of `BEMTConfig` (mesh,
          physical models on/off, solver parameters) with prefix `cfg_`,
          and the rotor geometry/condition (R, Nb, Omega, OmegaR, rho)
          with prefix `rotor_` . So that any CSV row is
          SELF-SUFFICIENT: you can know exactly what setup produced it
          without consulting the script that generated it. Can be turned
          off with `export_settings=False` (inside benchmark loops
          where the config is already known to be fixed and constant),
          but the default is always to export everything.

    FOR PLOTTING: each plot function (Section 9) receives this complete
    DataFrame and chooses, internally, either the rotor columns
    (mu_x,CT,CQ,FM,...) OR the propeller ones
    (J_x,CT_prop,CQ_prop,eta_prop,...) according to the requested mode --
    never the other way around (the export is never filtered by mode).
    """
    r_nodes = maps["r_norm_nodes"] * rotor.R
    psi_nodes = maps["psi_nodes"]
    R_DIM, PSI = maps["R_DIM"], maps["PSI"]
    Fn, Ft, Ft_i, Ft_p = maps["Fn"], maps["Ft"], maps["Ft_i"], maps["Ft_p"]
    Nb, Omega, OmegaR, R = rotor.Nb, rotor.Omega, rotor.OmegaR, rotor.R
    rho = cfg.rho
    mu_x, Vz = maps["mu_x"], maps["Vz"]

    # --- Disk integration: sum over blades (Nb) and azimuthal average ------
    # Each 2D field (Ne,Npsi) is the load of ONE blade at a given
    # radial/azimuthal station. It is integrated first over r (trapezoid,
    # axis 0) to get the per-blade load as a function of psi only, then
    # over psi (trapezoid, remaining axis) and divided by 2*pi to get the
    # azimuthal AVERAGE (not the sum) . Physically, this is the value
    # "seen" by a non-rotating observer (hub reference frame), which is
    # what enters the global T/Q/H/Y/Mx/My equations. Multiplied by Nb
    # since all blades contribute equally (same load at every psi, offset
    # by 360/Nb . One blade's azimuthal average already represents the
    # average of all of them).
    def disk_integral(field_2d):
        radial = _trapz(field_2d, r_nodes, axis=0)
        return Nb * _trapz_psi_periodic(radial, psi_nodes) / (2 * np.pi)

    # --- Global forces and moments in the disk (non-rotating) frame --------
    # Thrust: force normal to the disk (rotor axis), direct sum of Fn.
    # Torque: moment about the rotor axis = integral of Ft*r. Split
    #   into an INDUCED part (Ft_i, tied to induced drag/inflow) and
    #   a PROFILE part (Ft_p, tied to the airfoil's profile Cd) . Useful
    #   to diagnose how much of the power is "necessary aerodynamic
    #   cost" (induced) vs. "profile friction" (profile).
    # Mx,My: tilting moments (equivalent flapping moment, useful as
    #   input to a trim model even without explicit flapping) . Mx about
    #   the axis pointing to psi=0, My about the perpendicular axis
    #   (psi=90deg).
    # H,Y: in-plane forces (disk drag/side force). H also
    #   split into induced/profile for the same reason as Torque.
    Thrust = disk_integral(Fn)
    Torque_i = disk_integral(Ft_i * R_DIM)
    Torque_p = disk_integral(Ft_p * R_DIM)
    Torque = Torque_i + Torque_p
    Mx = disk_integral(-Fn * R_DIM * np.cos(PSI))
    My = disk_integral(-Fn * R_DIM * np.sin(PSI))
    Hi = disk_integral(Ft_i * np.sin(PSI))
    Hp = disk_integral(Ft_p * np.sin(PSI))
    H = Hi + Hp
    Y = -disk_integral(Ft * np.cos(PSI))

    # Power = Torque * angular speed (basic definition of rotating-shaft
    # power). Split into induced/profile for the same reason as above.
    Power, Power_i, Power_p = Torque * Omega, Torque_i * Omega, Torque_p * Omega

    # =========================================================================
    # NON-DIMENSIONALIZATION 1: ROTOR (helicopter) CONVENTION, in rho*A*(Omega R)^n
    # =========================================================================
    # qA = "blade-tip dynamic pressure" x disk area, the natural force
    # scale of a rotor (the blade tip, (Omega R), is the reference
    # speed). CT=T/qA (force non-dimensional), CQ=Q/(qA R)
    # (moment non-dimensional, extra 1/R unit since torque=force x arm),
    # CP=P/(qA*OmegaR) (power non-dimensional, extra 1/(Omega R) unit
    # since power=torque x Omega = force x arm x Omega, and qA*(OmegaR)
    # has power units). CPi/CPp: same scale, but only the
    # induced/profile part of power . Useful to see how much of the
    # total CP is "unavoidable aerodynamic cost" (induced, ~T^1.5) vs.
    # "profile friction" (nearly independent of T).
    qA = rho * np.pi * R ** 2 * OmegaR ** 2
    CT = Thrust / qA
    CQ = Torque / (qA * R)
    CP = Power / (qA * OmegaR)
    CPi = Power_i / (qA * OmegaR)
    CPp = Power_p / (qA * OmegaR)
    CH, CHi, CHp = H / qA, Hi / qA, Hp / qA
    CY = Y / qA
    CMx, CMy = Mx / (qA * R), My / (qA * R)
    # FM (Figure of Merit): ratio between the ideal power of an actuator
    # disk in hover (CT^1.5/sqrt(2), Rankine-Froude) and the REAL power
    # (CQ, which already includes profile + other losses). FM=1 would be
    # a perfect rotor. Classic efficiency metric ONLY defined/relevant in
    # hover/near-hover (low mu_x) . That's why it has no direct
    # propeller-side analogue (there, eta_prop plays that role, defined
    # below for axial advance).
    FM = (CT ** 1.5 / np.sqrt(2)) / CQ if (CT > 0 and CQ > 1e-9) else 0.0

    # =========================================================================
    # NON-DIMENSIONALIZATION 2: PROPELLER (airplane) CONVENTION, in rho*n^2*D^4 and so on.
    # =========================================================================
    # ALWAYS computed here (not only when cfg.is_propeller=True) . It is
    # cheap (a few scalar computations) and allows comparing both
    # conventions side by side without re-running the solver. Does NOT
    # overwrite CT/CQ/CP above (rotor convention, computed in parallel).
    # The speed reference is now n*D (n=revolutions per second,
    # D=diameter), the classic airplane-propeller convention. Exact
    # identity (follows from Omega*R = pi*n*D, independent of the
    # rotor's physical size . Checked numerically in the __main__ test
    # block, Section 10c):
    #     CT_prop = CT * pi^3/4          CQ_prop = CQ * pi^3/8
    #     CP_prop = CP * pi^4/4          CP_prop = 2*pi*CQ_prop  (classic propeller identity: P=2*pi*n*Q)
    n_rps = Omega / (2.0 * np.pi)               # revolutions per second
    D = 2.0 * R                                  # diameter
    qD4 = rho * n_rps ** 2 * D ** 4
    CT_prop = Thrust / max(qD4, 1e-300)
    CQ_prop = Torque / max(rho * n_rps ** 2 * D ** 5, 1e-300)
    CP_prop = Power / max(rho * n_rps ** 3 * D ** 5, 1e-300)
    J_adv = np.pi * mu_x                           # longitudinal advance ratio, J_x = pi*mu_x (Section 6c)
    Jz_adv = np.pi * (Vz / OmegaR)                # axial/vertical advance ratio, J_z = pi*mu_z
    # eta_prop = T*V/P, propulsive efficiency. The V that matters is the
    # AXIAL component's (along the thrust axis), so the formula uses
    # J_z, not J_x.
    #
    # Previously used J_x (longitudinal), and that was contradictory
    # with its own accompanying comment: it said the quantity is only
    # meaningful with "PURELY AXIAL advance (V=Vz, longitudinal mu_x ~
    # 0)", which is exactly the case where J_x = 0 and the formula
    # returned zero. A propeller specified CORRECTLY (Vz = flight speed,
    # mu_x = 0) reported zero efficiency over the whole sweep. Specified
    # incorrectly (flight speed in mu_x, which makes the blade see +-V
    # over azimuth, something no propeller ever sees) reported plausible
    # but false values, including above 1.
    #
    # The CT_prop > 0 guard matters: while windmilling, both thrust and
    # power become negative and the ratio turns positive again, which
    # would give a high "efficiency" precisely where the propeller is
    # consuming energy from the flow instead of propelling. Propulsive
    # efficiency is not defined there, so we return 0.
    eta_prop = ((Jz_adv * CT_prop / CP_prop)
                if (CP_prop > 1e-9 and CT_prop > 0.0) else 0.0)

    # =========================================================================
    # INPUT (flight) CONDITIONS . All equivalent representations -----------
    # =========================================================================
    # If the caller already resolved the condition via
    # `resolve_advance_velocity` (which returns `meta` with all forms
    # mu_x/mu_x/J_x/J_x/Vz/Vz/mu_z/J_z/alpha_rotor_deg), reuses that
    # dictionary . Guarantees bit-for-bit consistency with what was
    # actually resolved. Otherwise (a direct call to `solve_bemt`
    # without going through `resolve_advance_velocity`), rebuilds it right
    # here from (mu_x,Vz,OmegaR) so the columns are NEVER missing from
    # the exported CSV.
    if meta is not None:
        flight_cols = dict(meta)
    else:
        mu_z_val = Vz / OmegaR
        alpha_rotor_calc = (float(np.degrees(np.arctan2(Vz, mu_x * OmegaR)))
                             if abs(mu_x * OmegaR) > 1e-6
                             else (90.0 if Vz > 0 else (-90.0 if Vz < 0 else 0.0)))
        flight_cols = dict(mu_x=mu_x, J_x=J_adv,
                            Vz=Vz, mu_z=mu_z_val, J_z=Jz_adv,
                            alpha_rotor_deg=alpha_rotor if alpha_rotor is not None else alpha_rotor_calc,
                            Vx=mu_x * OmegaR)
    # An explicit `alpha_rotor` (if passed by the caller) always takes
    # display priority over the reconstructed value, for backward
    # compatibility.
    if alpha_rotor is not None:
        flight_cols["alpha_rotor_deg"] = alpha_rotor
    # The angle from the AXIS ALWAYS follows whatever ended up in
    # `alpha_rotor_deg` (including when the explicit `alpha_rotor` above
    # overwrote the resolved one) . Two columns that contradicted each
    # other would be worse than just one.
    flight_cols["alpha_disk_deg"] = _angle_from_axis(
        flight_cols["alpha_rotor_deg"])

    # =========================================================================
    # RESOLVED AXIAL FLOW: v_i, lambda_i, lambda (disk averages) ------------
    # =========================================================================
    # The manual (docs/documentation.html, Sections 2.4.2 and 2.6.2)
    # presents the three inflow ratios ALWAYS together: lambda_z (input
    # data), lambda_i (the fixed-point unknown) and lambda = lambda_z +
    # lambda_i, and the corresponding dimensional pair, U_P = V_v + v_i
    # = lambda*Omega*R. Until now the summary only carried lambda_z: the
    # other two existed only as a 2D field in `maps`. Only someone
    # opening a disk map would see them. A table that shows lambda_z alone
    # names one part as if it were the whole.
    #
    # AREA-WEIGHTED AVERAGE over the ring (r dr dpsi), not the arithmetic
    # average of the nodes: the mesh is uniform in r, so a plain average
    # weighs the root (narrow ring, little area) as much as the tip.
    # BOUNDARY to document: the average covers only the MESHED span (from
    # the root cutout to the tip), not the whole geometric disk . The
    # piece inside the cutout has no blade and therefore has no defined
    # lambda_i.
    lambda_i_map = maps.get("lambda_i")
    if lambda_i_map is None:
        lambda_i_mean = 0.0
    else:
        peso = _trapz_psi_periodic(_trapz(R_DIM, r_nodes, axis=0), psi_nodes)
        integral = _trapz_psi_periodic(
            _trapz(np.asarray(lambda_i_map, dtype=float) * R_DIM, r_nodes, axis=0),
            psi_nodes)
        lambda_i_mean = float(integral / peso) if abs(peso) > 1e-300 else 0.0
    lambda_c_val = Vz / OmegaR
    # lambda = lambda_z + lambda_i BY CONSTRUCTION (not the average of
    # `maps["lambda_total"]`, which would give the same number up to
    # rounding error): the manual's identity has to close EXACTLY when
    # the reader checks it by adding two table cells.
    lambda_total_mean = lambda_c_val + lambda_i_mean
    Vi_mean = lambda_i_mean * OmegaR

    # `Vz` stops being an echo of the INPUT alias (it was literally `Vz`
    # again . Two columns, one number, and the reader looking for a
    # difference that did not exist) and becomes the TOTAL axial
    # velocity through the disk, the manual's U_P. The input alias `Vz=`
    # from `resolve_advance_velocity` still means the axial component of
    # the FREE stream . Read in the summary as `Vz` (symbol V_inf,z).
    # See that function's docstring.
    flight_cols.pop("Vz_total", None)

    out = dict(
        # --- input condition (all representations, Section 6c) ----------------
        **flight_cols,
        lambda_z=lambda_c_val,
        # --- resolved axial flow (induced + total) -------------------------
        lambda_i=lambda_i_mean, lambda_total=lambda_total_mean,
        Vi=Vi_mean, Vz_total=Vz + Vi_mean,
        # --- dimensional forces and moments (SI) ----------------------------
        Thrust=Thrust, Torque=Torque, Power=Power, Power_i=Power_i, Power_p=Power_p,
        H=H, Hi=Hi, Hp=Hp, Y=Y, Mx=Mx, My=My,
        # --- coefficients, ROTOR convention --------------------------------
        CT=CT, CQ=CQ, CP=CP, CPi=CPi, CPp=CPp, CH=CH, CHi=CHi, CHp=CHp,
        CY=CY, CMx=CMx, CMy=CMy, FM=FM,
        # --- coefficients, PROPELLER convention ----------------------------
        CT_prop=CT_prop, CQ_prop=CQ_prop, CP_prop=CP_prop, eta_prop=eta_prop,
        # --- solver diagnostics (always useful for auditing convergence) ---
        convergence_pct=100.0 * float(np.mean(maps["converged"])),
        solver=maps["solver"], inflow_coupling=maps["inflow_coupling"],
        mean_iter=float(np.mean(maps["n_iter"])), elapsed_s=maps["elapsed"],
    )

    # --- blade dynamics outputs (Section 4h, SC-11) ----------------------
    # Present ONLY when the run actually solved a flapping/lagging blade;
    # a rigid run reports nothing new. Sign convention (stated wherever a
    # column of these appears): beta(psi) = beta_0 + beta_1c*cos(psi) +
    # beta_1s*sin(psi), positive up, and each tip-path-plane tilt is the
    # NEGATIVE of its first harmonic.
    if maps.get("beta_coeffs"):
        coeffs = maps["beta_coeffs"]
        deg = np.degrees
        out["beta_0_deg"] = float(deg(coeffs[0][0]))
        first = coeffs.get(1, (0.0, 0.0))
        out["beta_1c_deg"] = float(deg(first[0]))
        out["beta_1s_deg"] = float(deg(first[1]))
        out["tpp_tilt_long_deg"] = -out["beta_1c_deg"]
        out["tpp_tilt_lat_deg"] = -out["beta_1s_deg"]
        n_harm_out = max(coeffs.keys())
        for n in range(2, n_harm_out + 1):
            cn, sn = coeffs.get(n, (0.0, 0.0))
            out[f"beta_{n}c_deg"] = float(deg(cn))
            out[f"beta_{n}s_deg"] = float(deg(sn))
        out["nu_beta"] = maps["nu_beta"]
        out["lock_number"] = maps["lock_number"]
        out["flap_inertia_kg_m2"] = maps["flap_inertia_kg_m2"]
        out["flap_outer_iterations"] = maps["flap_outer_iterations"]
        out["flap_outer_residual_deg"] = maps["flap_outer_residual_deg"]

        # Hub moment carried through the offset hinge/root spring: the
        # structural path that a hinged (or spring-restrained) blade adds
        # to the tilting moments computed from the thrust distribution
        # alone. The totals are what a hub would actually feel.
        nu_sq_minus_1 = maps.get("nu_beta_squared", 1.0) - 1.0
        i_beta = maps["flap_inertia_kg_m2"]
        gain = (rotor.Nb / 2.0) * i_beta * Omega ** 2 * nu_sq_minus_1
        mx_hub = gain * first[0]
        my_hub = gain * first[1]
        out["Mx_hub"] = float(mx_hub)
        out["My_hub"] = float(my_hub)
        out["Mx_total"] = float(Mx + mx_hub)
        out["My_total"] = float(My + my_hub)

        if maps.get("lag_coeffs"):
            lag_coeffs = maps["lag_coeffs"]
            out["zeta_0_deg"] = float(deg(lag_coeffs[0][0]))
            lag_first = lag_coeffs.get(1, (0.0, 0.0))
            out["zeta_1c_deg"] = float(deg(lag_first[0]))
            out["zeta_1s_deg"] = float(deg(lag_first[1]))
            out["nu_zeta"] = maps["nu_zeta"]

    # --- dynamic-stall time-march diagnostics (EN-9) ---------------------
    # Present only when the time-march method ran; a 'frequency' run
    # reports nothing new.
    if maps.get("dynamic_stall_periodic_residual") is not None:
        out["dynamic_stall_periodic_residual"] = \
            float(maps["dynamic_stall_periodic_residual"])
        out["dynamic_stall_revolutions"] = int(maps.get(
            "dynamic_stall_revolutions", 0))
        if maps.get("dynamic_stall_warning"):
            out["dynamic_stall_warning"] = maps["dynamic_stall_warning"]

    if export_settings:
        # --- run's full "data sheet" -----------------------------------------
        # Every field of BEMTConfig (mesh, rotor/propeller mode, physical
        # models on/off, solver parameters) with prefix `cfg_`, and the
        # rotor's reference geometry/condition with prefix `rotor_`.
        # Goal: every CSV row is self-describing . The run can be
        # reproduced just by looking at the row itself, without needing
        # the original script.
        cfg_dict = {f"cfg_{k}": v for k, v in asdict(cfg).items()}
        rotor_dict = dict(rotor_R=R, rotor_Nb=Nb, rotor_Omega=Omega,
                           rotor_OmegaR=OmegaR, rotor_rpm=rotor.Omega_rpm,
                           rotor_D=D, cfg_rho_used=rho)
        out.update(cfg_dict)
        out.update(rotor_dict)

    return out


# =============================================================================
# 8. FLIGHT CONDITION SWEEP
# =============================================================================

_SECONDARY_KIND_TO_KWARG = {
    "alpha": "alpha_deg", "Vz": "Vz", "mu_z": "mu_z", "J_z": "J_z", "Jz": "J_z",
}
_ADVANCE_KIND_TO_KWARG = {"mu_x": "mu_x", "J_x": "J_x",
                          "alpha_disk": "alpha_disk_deg"}


def run_sweep(rotor: Rotor, airfoil, cfg: BEMTConfig, advance_sweep, secondary_sweep=None,
              advance_kind="mu_x", secondary_kind=None,
              alpha_sweep=None, Vv_sweep=None, sweep_choice="alpha", verbose=True):
    """Flight condition sweep. Accepts the longitudinal component in ANY
    convention via `advance_kind` in {'mu_x','mu_x','J_x','J_x'}, and the
    vertical/axial component via `secondary_kind` in
    {'alpha','Vz','Vz','mu_z','J_z'} (see `resolve_advance_velocity`,
    Section 6c). `mu_sweep`/`alpha_sweep`/`Vv_sweep`/`sweep_choice` are the
    ORIGINAL names (rotor convention), kept for backward compatibility --
    if used, they take priority and populate `advance_sweep`/
    `secondary_sweep`/`secondary_kind` automatically."""
    if secondary_kind is None:
        secondary_kind = sweep_choice
    if secondary_sweep is None:
        secondary_sweep = alpha_sweep if secondary_kind == "alpha" else Vv_sweep
    if secondary_sweep is None:
        secondary_sweep = [0.0]

    # cfg.is_propeller only switches the DEFAULT of `advance_kind` (mu_x
    # -> J_x) when the caller did not specify anything explicitly. It
    # never forces the convention if `advance_kind` was already passed
    # deliberately (even if it is an explicit 'mu_x' on a rotor with
    # is_propeller=True, which is a valid combination: nothing prevents
    # reporting a propeller in mu_x, or a rotor in J_x). This is the ONLY
    # function where `cfg.is_propeller` has an automatic behavioral
    # effect . Everywhere else in the code, the name of the argument
    # supplied already disambiguates the convention (Section 6c).
    if advance_kind == "mu_x" and cfg.is_propeller:
        advance_kind = "J_x"

    long_kwarg = _ADVANCE_KIND_TO_KWARG.get(advance_kind)
    sec_kwarg = _SECONDARY_KIND_TO_KWARG.get(secondary_kind)
    if long_kwarg is None:
        raise ValueError(f"Unknown advance_kind: {advance_kind}. Options: {list(_ADVANCE_KIND_TO_KWARG)}")
    if sec_kwarg is None:
        raise ValueError(f"Unknown secondary_kind: {secondary_kind}. Options: {list(_SECONDARY_KIND_TO_KWARG)}")

    rows, maps_list = [], []
    for sv in secondary_sweep:
        for av in advance_sweep:
            mu_x, Vz, meta = resolve_advance_velocity(rotor, cfg, **{long_kwarg: av, sec_kwarg: sv})
            alpha_rotor = meta["alpha_rotor_deg"]

            maps = solve_bemt(rotor, airfoil, cfg, mu_x, Vz)
            # `meta` carries ALL equivalent representations of the
            # resolved flight condition
            # (mu_x/mu_x/J_x/J_x/Vz/Vz/mu_z/J_z/alpha_rotor_deg), passed
            # through to aggregate_results so the exported row never
            # loses any input non-dimensionalization.
            row = aggregate_results(rotor, cfg, maps, alpha_rotor, meta=meta)
            row["sweep_value"] = sv
            row["sweep_kind"] = secondary_kind
            row["advance_kind"] = advance_kind
            rows.append(row)
            maps_list.append(maps)
            if verbose:
                adv_label = f"{advance_kind}={av:5.3f}"
                print(f"  {adv_label}  alpha={alpha_rotor:6.2f}deg | "
                      f"CT={row['CT']:.5f} CQ={row['CQ']:.6f} FM={row['FM']:.3f} | "
                      f"conv={row['convergence_pct']:5.1f}%  it~{row['mean_iter']:5.1f}  "
                      f"t={row['elapsed_s']*1000:6.1f}ms  [{cfg.solver}/{cfg.inflow_field_model}]")
                pp_warn = maps.get("pitt_peters_warning")
                if pp_warn:
                    print(f"    [WARNING] {pp_warn}")
    return pd.DataFrame(rows), maps_list


def benchmark_solvers(rotor: Rotor, airfoil, cfg_base: BEMTConfig, mu_x: float, Vz: float,
                       solvers=("fixed_point", "newton", "bisection", "aitken")):
    """Compares the available iterative methods at the same flight
    condition: result consistency (CT,CQ), mean number of iterations,
    and time."""
    out = []
    harmonic = _resolve_inflow_field_model(cfg_base.inflow_field_model)["harmonic"] or "glauert"
    for s in solvers:
        cfg = replace(cfg_base, solver=s, inflow_field_model=f"{harmonic}_local")
        maps = solve_bemt(rotor, airfoil, cfg, mu_x, Vz)
        row = aggregate_results(rotor, cfg, maps)
        out.append(dict(solver=s, CT=row["CT"], CQ=row["CQ"], FM=row["FM"],
                         convergence_pct=row["convergence_pct"],
                         mean_iter=row["mean_iter"], time_ms=row["elapsed_s"] * 1000))
    return pd.DataFrame(out).set_index("solver")


# =============================================================================
# 9. PLOTTING (minimal, extensible)
# =============================================================================

def plot_airfoil_polar(airfoil, fname, alpha_range_deg=(-25, 25)):
    alpha_deg = np.linspace(*alpha_range_deg, 300)
    cl, cd = airfoil.cl_cd(np.deg2rad(alpha_deg))
    fig, axs = plt.subplots(1, 3, figsize=(12, 4))
    axs[0].plot(alpha_deg, cl); axs[0].set_xlabel(r"$\alpha$ (deg)"); axs[0].set_ylabel(r"$C_L$"); axs[0].grid(True)
    axs[1].plot(alpha_deg, cd); axs[1].set_xlabel(r"$\alpha$ (deg)"); axs[1].set_ylabel(r"$C_D$"); axs[1].grid(True)
    axs[2].plot(cd, cl); axs[2].set_xlabel(r"$C_D$"); axs[2].set_ylabel(r"$C_L$"); axs[2].grid(True)
    fig.suptitle("Polar of the selected airfoil")
    fig.tight_layout()
    fig.savefig(fname, dpi=130)
    plt.close(fig)


def plot_disk_map(maps, key, title, fname, mask_reverse=True):
    R_NORM, PSI = maps["R_NORM"], maps["PSI"]
    data = maps[key].copy()
    if mask_reverse:
        data = np.where(maps["Ut"] < 0, np.nan, data)
    # Closes the azimuth (see `visualization._close_azimuth`/docstring of
    # `_trapz_psi_periodic`): the (Ne,Npsi) grid from `solve_bemt` does
    # not repeat psi=0 at psi=2*pi (correct for integration), which would
    # leave an uncovered wedge between the last node and the full turn in
    # this polar pcolormesh . For drawing only, the psi=0 column is
    # duplicated.
    psi0 = PSI[:, :1]
    PSI = np.concatenate([PSI, psi0 + 2.0 * np.pi], axis=1)
    R_NORM = np.concatenate([R_NORM, R_NORM[:, :1]], axis=1)
    data = np.concatenate([data, data[:, :1]], axis=1)
    fig = plt.figure(figsize=(6, 5.5))
    ax = fig.add_subplot(projection="polar")
    pc = ax.pcolormesh(PSI, R_NORM, data, shading="auto", cmap="turbo")
    ax.set_theta_zero_location("S")
    fig.colorbar(pc, ax=ax, shrink=0.8, label=title)
    ax.set_title(f"{title}  (mu_x={maps['mu_x']:.3f})")
    fig.tight_layout()
    fig.savefig(fname, dpi=130)
    plt.close(fig)


def plot_summary_vs_advance(df: pd.DataFrame, fname, mode: str = "auto"):
    """Plots the performance summary vs. advance ratio, CHOOSING the
    coefficient family (the export always carries everything, but the
    plot shows only what makes sense for the case):

    - mode='rotor'      -> x-axis = mu_x, panels with CT,CQ,FM,CH,CY,CMx
                            (classic helicopter/eVTOL rotor convention,
                            FM is only physically meaningful here --
                            hover/near-hover).
    - mode='propeller'  -> x-axis = J_x, panels with CT_prop,CQ_prop,CP_prop,
                            eta_prop,CY,CMx (classic airplane-propeller
                            convention, while eta_prop is the efficiency metric
                            corresponding to FM on the rotor side).
    - mode='auto'       -> uses `cfg_is_propeller` from the FIRST row of
                            the DataFrame (always present, since
                            `aggregate_results` exports the whole config)
                            to decide. The data itself carries the
                            information of which convention is "natural"
                            for it, without needing to pass `mode`
                            explicitly in most cases.

    The DataFrame `df` (coming from `run_sweep`) always contains BOTH
    coefficient families side by side . This function only decides which
    columns to draw, never filters what was exported.
    """
    if mode == "auto":
        is_prop = bool(df["cfg_is_propeller"].iloc[0]) if "cfg_is_propeller" in df.columns else False
        mode = "propeller" if is_prop else "rotor"

    if mode == "rotor":
        x_col, x_label = "mu_x", r"$\mu_x$"
        pairs = [("CT", "C_T"), ("CQ", "C_Q"), ("FM", "FM"),
                 ("CH", "C_H"), ("CY", "C_Y"), ("CMx", "C_{Mx}")]
        suptitle = "Rotor performance vs advance ratio (rotor convention)"
    elif mode == "propeller":
        x_col, x_label = "J_x", r"$J_x$"
        pairs = [("CT_prop", "C_{T,prop}"), ("CQ_prop", "C_{Q,prop}"), ("eta_prop", r"\eta_{prop}"),
                 ("CP_prop", "C_{P,prop}"), ("CY", "C_Y"), ("CMx", "C_{Mx}")]
        suptitle = "Propeller performance vs advance ratio (propeller convention)"
    else:
        raise ValueError(f"Unknown mode: {mode}. Use 'rotor', 'propeller', or 'auto'.")

    fig, axs = plt.subplots(2, 3, figsize=(14, 8))
    for ax, (col, label) in zip(axs.ravel(), pairs):
        ax.plot(df[x_col], df[col], "-o")
        ax.set_xlabel(x_label); ax.set_ylabel(f"${label}$"); ax.grid(True)
    fig.suptitle(suptitle)
    fig.tight_layout()
    fig.savefig(fname, dpi=130)
    plt.close(fig)


def plot_summary_vs_mu(df: pd.DataFrame, fname):
    """Backward-compatible alias for
    `plot_summary_vs_advance(df, fname, mode='rotor')` . Kept with the
    original name/signature so as not to break existing calls. Prefer
    `plot_summary_vs_advance` in new code."""
    plot_summary_vs_advance(df, fname, mode="rotor")


def plot_solver_convergence(histories: dict, frac_histories: dict, fname):
    fig, axs = plt.subplots(1, 2, figsize=(13, 5))
    for name, hist in histories.items():
        if len(hist):
            axs[0].semilogy(np.arange(1, len(hist) + 1), hist, "-o", ms=3, label=name)
    axs[0].set_xlabel("iteration"); axs[0].set_ylabel(r"max$|$residual $\lambda_i|$ (entire disk)")
    axs[0].set_title("Worst case (dominated by elements near\nreverse-flow boundary, Ut≈0)")
    axs[0].grid(True, which="both"); axs[0].legend()

    for name, fh in frac_histories.items():
        if len(fh):
            axs[1].plot(np.arange(1, len(fh) + 1), np.array(fh) * 100, "-o", ms=3, label=name)
    axs[1].set_xlabel("iteration"); axs[1].set_ylabel("% of converged elements")
    axs[1].set_title("Converged disk fraction (more representative\nview of each method's effectiveness)")
    axs[1].grid(True); axs[1].legend(); axs[1].set_ylim(0, 101)

    fig.suptitle("Convergence of iterative methods")
    fig.tight_layout()
    fig.savefig(fname, dpi=130)
    plt.close(fig)


# =============================================================================
# 10. EXAMPLE ROTOR . Built from the input data (Section 0c)
# =============================================================================

def build_example_rotor() -> Rotor:
    return Rotor(R=ROTOR_R, Nb=ROTOR_NB, Omega_rpm=ROTOR_OMEGA_RPM,
                 r_root_norm_geom=ROTOR_R_ROOT_NORM, r_tip_norm_geom=ROTOR_R_TIP_NORM,
                 r_geom=ROTOR_R_GEOM, chord_geom=ROTOR_CHORD_GEOM,
                 theta_geom_deg=ROTOR_THETA_GEOM_DEG)


def build_example_airfoil(stall_model: str = AIRFOIL_STALL_MODEL) -> AnalyticalAirfoil:
    return AnalyticalAirfoil(cl_alpha=AIRFOIL_CL_ALPHA, alpha0_deg=AIRFOIL_ALPHA0_DEG,
                              cd0=AIRFOIL_CD0, k=AIRFOIL_K,
                              alpha_stall_pos_deg=AIRFOIL_STALL_POS_DEG,
                              alpha_stall_neg_deg=AIRFOIL_STALL_NEG_DEG,
                              stall_model=stall_model)


def build_example_viterna_airfoil(stall_model: str = AIRFOIL_STALL_MODEL) -> ViternaExtendedAirfoil:
    """Wraps the example airfoil (`build_example_airfoil`) in a
    Viterna-Corrigan -180..+180 degree extension, for use with
    `reverse_flow_model='viterna_full_range'` (Section 1b/4b)."""
    return ViternaExtendedAirfoil(build_example_airfoil(stall_model=stall_model))


if __name__ == "__main__":
    # =========================================================================
    # 11. MAIN SCRIPT . 10 independent demonstration/validation blocks
    # =========================================================================
    # WHICH blocks run and WITH WHAT PARAMETERS is controlled entirely by
    # the `RUN_PLAN` instance (RunPlan, Section 0b, top of the file) . Edit
    # there, not here, to choose what to run. Each block below is guarded
    # by a corresponding `if RUN_PLAN.run_NN_xxx:` and is independent of
    # the others: the rotor/airfoil setup and the base `BEMTConfig`
    # objects are always built (cost nothing, solve no BEMT) so that any
    # combination of enabled blocks works with no missing-variable error.
    import os
    outdir = RUN_PLAN.outdir
    os.makedirs(outdir, exist_ok=True)

    rotor = build_example_rotor()
    airfoil = build_example_airfoil(stall_model="enhanced")

    # --- base configurations reused by several blocks -----------------------
    # cfg_bench: coarser mesh (Ne=70,Npsi=100), used in the blocks that
    #   compare SOLVER METHODS against each other (1,4) . Smaller mesh =
    #   faster comparison, what matters there is solver behavior, not
    #   final mesh accuracy.
    # cfg_run: "production" mesh (RUN_PLAN.Ne_default/Npsi_default),
    #   Newton solver, Drees inflow + Prandtl + 'flat_plate' reverse flow
    #   -- configuration used as the STARTING POINT (via `replace(...)`)
    #   in blocks 2,3,5,6,9,10, each one turning on/off only what that
    #   block wants to demonstrate.
    cfg_bench = BEMTConfig(Ne=70, Npsi=100, solver="newton", inflow_field_model="drees_local",
                            prandtl_loss_mode="both", reverse_flow_model="flat_plate",
                            tol=1e-7, max_iter=150, collect_history=True)
    cfg_run = BEMTConfig(Ne=RUN_PLAN.Ne_default, Npsi=RUN_PLAN.Npsi_default,
                          solver="newton", inflow_field_model="drees_local",
                          prandtl_loss_mode="both", use_compressibility=False,
                          reverse_flow_model="flat_plate", tol=1e-7, max_iter=150)
    mu_sweep = RUN_PLAN.mu_sweep_main

    df_local = None  # populated by block 2, reused by block 3 (speedup)

    # =====================================================================
    # BLOCK 1 -- BENCHMARK OF THE lambda_i ITERATIVE METHODS
    # =====================================================================
    # Compares fixed_point/newton/bisection/aitken (Section 3) at the SAME
    # flight condition: all should converge to the same (CT,CQ) . What
    # changes is the number of iterations and time. Serves both as a
    # performance benchmark and as a regression test (if one method
    # diverges from the rest, it signals a bug in that solver's
    # formulation).
    if RUN_PLAN.run_01_solver_benchmark:
        print("=" * 78)
        print(f"1) BENCHMARK OF THE ITERATIVE METHODS (mu_x={RUN_PLAN.mu_benchmark}, forward flight, "
              f"Ne={cfg_bench.Ne},Npsi={cfg_bench.Npsi})")
        print("=" * 78)
        bench = benchmark_solvers(rotor, airfoil, cfg_bench, mu_x=RUN_PLAN.mu_benchmark, Vz=0.0,
                                   solvers=("fixed_point", "newton", "bisection", "aitken"))
        print(bench.to_string(float_format=lambda x: f"{x:.6g}"))

        histories, frac_histories = {}, {}
        for s in ("fixed_point", "newton", "bisection", "aitken"):
            cfg_h = replace(cfg_bench, solver=s)
            maps_h = solve_bemt(rotor, airfoil, cfg_h, mu_x=RUN_PLAN.mu_benchmark, Vz=0.0)
            histories[s] = maps_h["residual_history"]
            frac_histories[s] = maps_h["frac_converged_history"]
        plot_solver_convergence(histories, frac_histories, os.path.join(outdir, "solver_convergence.png"))
        bench.to_csv(os.path.join(outdir, "zbemt_py_solver_benchmark.csv"))
        print()

    # =====================================================================
    # BLOCK 2 -- mu_x SWEEP (alpha_rotor=0), 'local' coupling
    # =====================================================================
    # "Reference" sweep: inflow solved element by element (more
    # expensive, more accurate , see Section 4d) over the whole
    # `RUN_PLAN.mu_sweep_main` grid, in level flight (alpha_rotor=0,
    # Vz=0). Every row of the returned `df_local` already contains ALL
    # non-dimensionalizations (rotor AND propeller) and the full config
    # , see `aggregate_results`.
    if RUN_PLAN.run_02_mu_sweep_local:
        print("=" * 78)
        print("2) MU SWEEP (alpha_rotor=0 deg). Local iterative method (Newton)")
        print("=" * 78)
        df_local, maps_local = run_sweep(rotor, airfoil, cfg_run, mu_sweep,
                                          alpha_sweep=[0.0], sweep_choice="alpha")
        df_local.to_csv(os.path.join(outdir, "zbemt_py_summary_local.csv"), index=False)

        # Plots: airfoil polar (does not depend on mu_x), performance
        # summary (mode='auto' -> picks 'rotor' since
        # cfg_run.is_propeller is False) and two disk maps at the last
        # swept condition (highest mu_x in the grid).
        plot_airfoil_polar(airfoil, os.path.join(outdir, "airfoil_polar.png"))
        plot_summary_vs_advance(df_local, os.path.join(outdir, "summary_vs_mu.png"), mode="auto")
        plot_disk_map(maps_local[-1], "alpha_eff", r"effective $\alpha$ (rad)",
                      os.path.join(outdir, "disk_map_alpha_mu04.png"))
        plot_disk_map(maps_local[-1], "Cl", r"$C_L$",
                      os.path.join(outdir, "disk_map_CL_mu04.png"))
        print()

    # =====================================================================
    # BLOCK 3 -- SAME SWEEP, fast 'global' mode (Section 4d)
    # =====================================================================
    # Same mu_x grid, but first solving a mean axisymmetric inflow
    # lambda0(r) and only then applying the linear harmonic variation
    # (Coleman/Drees) as post-processing . Much cheaper. Compared
    # against block 2 (if it also ran) to measure the real speedup.
    if RUN_PLAN.run_03_mu_sweep_global:
        print("=" * 78)
        print("3) THE SAME SWEEP. Fast 'global' mode (mean inflow + linear harmonic)")
        print("=" * 78)
        cfg_fast = replace(cfg_run, inflow_field_model="drees_global")
        df_global, maps_global = run_sweep(rotor, airfoil, cfg_fast, mu_sweep,
                                            alpha_sweep=[0.0], sweep_choice="alpha")
        df_global.to_csv(os.path.join(outdir, "zbemt_py_summary_global.csv"), index=False)

        if df_local is not None:
            speedup = df_local["elapsed_s"].sum() / max(df_global["elapsed_s"].sum(), 1e-9)
            print(f"\nSpeedup of the 'global' mode versus 'local' in this sweep: {speedup:.1f}x "
                  f"(local={df_local['elapsed_s'].sum()*1000:.1f}ms, "
                  f"global={df_global['elapsed_s'].sum()*1000:.1f}ms)")
        else:
            print("  (block 2 is off in RUN_PLAN. The 'local vs global' speedup is not computed.)")
        print()

    # =====================================================================
    # BLOCK 4 -- REVERSE FLOW: 'flat_plate' vs 'thin_plate_blend' (Section 4b)
    # =====================================================================
    # Compares the fixed Cd=1.9 formulation (discontinuous at Ut=0) with
    # the smoothly blended thin flat-plate one (continuous) at the same
    # high-advance flight condition . Where the reverse-flow region is
    # larger and more relevant.
    if RUN_PLAN.run_04_reverse_flow_compare:
        print("=" * 78)
        print("4) REVERSE FLOW: 'flat_plate' (fixed Cd=1.9) vs 'thin_plate_blend' (Section 4b)")
        print("=" * 78)
        cfg_tp = replace(cfg_bench, reverse_flow_model="thin_plate_blend", collect_history=True)
        maps_fp = solve_bemt(rotor, airfoil, cfg_bench, mu_x=RUN_PLAN.mu_benchmark, Vz=0.0)
        maps_tp = solve_bemt(rotor, airfoil, cfg_tp, mu_x=RUN_PLAN.mu_benchmark, Vz=0.0)
        print(f"  flat_plate       : it_max={maps_fp['total_iterations']:3d}  "
              f"conv={100*np.mean(maps_fp['converged']):5.1f}%  CT={aggregate_results(rotor, cfg_bench, maps_fp)['CT']:.5f}")
        print(f"  thin_plate_blend : it_max={maps_tp['total_iterations']:3d}  "
              f"conv={100*np.mean(maps_tp['converged']):5.1f}%  CT={aggregate_results(rotor, cfg_tp, maps_tp)['CT']:.5f}")
        print()

    # =====================================================================
    # BLOCK 5 -- HIMMELSKAMP/SNEL: rotational stall delay at the root (Section 4c)
    # =====================================================================
    # At low mu_x (near-hover), the root region operates near stall. The
    # Snel correction increases Cl there (centrifugal pumping/Coriolis
    # delay separation), which should raise CT slightly for the same
    # geometry/twist.
    if RUN_PLAN.run_05_snel_rotational_aug:
        print("=" * 78)
        print("5) HIMMELSKAMP/SNEL: effect of the rotational correction at the root (low mu_x, near hover)")
        print("=" * 78)
        cfg_snel_off = replace(cfg_run, use_rotational_augmentation=False)
        cfg_snel_on = replace(cfg_run, use_rotational_augmentation=True)
        maps_off = solve_bemt(rotor, airfoil, cfg_snel_off, mu_x=RUN_PLAN.mu_snel, Vz=0.0)
        maps_on = solve_bemt(rotor, airfoil, cfg_snel_on, mu_x=RUN_PLAN.mu_snel, Vz=0.0)
        ct_off = aggregate_results(rotor, cfg_snel_off, maps_off)["CT"]
        ct_on = aggregate_results(rotor, cfg_snel_on, maps_on)["CT"]
        cl_root_off = float(np.mean(maps_off["Cl"][0, :]))
        cl_root_on = float(np.mean(maps_on["Cl"][0, :]))
        print(f"  without Snel: CT={ct_off:.5f}  mean Cl at the first radial station={cl_root_off:.4f}")
        print(f"  with Snel: CT={ct_on:.5f}  mean Cl at the first radial station={cl_root_on:.4f}  "
              f"(expected above the case without Snel, because of centrifugal pumping and Coriolis effects)")
        print()

    # =====================================================================
    # BLOCK 6 -- RADIAL FLOW / independence principle (ISAE, Section 4f)
    # =====================================================================
    # At high mu_x, the radial component UR=Vinf*cos(psi) becomes large
    # near psi=0/180deg (and is zero at 90/270). The correction
    # re-evaluates Cd at an alpha "skewed" by that skew, typically
    # REDUCING Cd there (hence reducing CQ at ~constant CT).
    if RUN_PLAN.run_06_radial_flow_correction:
        print("=" * 78)
        print("6) RADIAL FLOW (ISAE): effect on Cd in high-advance forward flight")
        print("=" * 78)
        cfg_rad_off = replace(cfg_run, use_radial_flow_correction=False)
        cfg_rad_on = replace(cfg_run, use_radial_flow_correction=True)
        maps_rad_off = solve_bemt(rotor, airfoil, cfg_rad_off, mu_x=RUN_PLAN.mu_radial_flow, Vz=0.0)
        maps_rad_on = solve_bemt(rotor, airfoil, cfg_rad_on, mu_x=RUN_PLAN.mu_radial_flow, Vz=0.0)
        row_rad_off = aggregate_results(rotor, cfg_rad_off, maps_rad_off)
        row_rad_on = aggregate_results(rotor, cfg_rad_on, maps_rad_on)
        print(f"  without radial correction: CT={row_rad_off['CT']:.5f}  CQ={row_rad_off['CQ']:.6f}")
        print(f"  with radial correction: CT={row_rad_on['CT']:.5f}  CQ={row_rad_on['CQ']:.6f}  "
              f"(Cd reduced where |UR| is maximum: psi=0/180)")
        print()

    # =====================================================================
    # BLOCK 7 -- STEADY PITT-PETERS vs 'global' (Drees), Section 4d/6b
    # =====================================================================
    # Cross-validation: the finite-state dynamic inflow, solved in the
    # STEADY regime (outer fixed point), should reasonably agree with the
    # 'global' mode (empirical Coleman/Drees) for low-moderate mu_x --
    # both solve the SAME type of linear harmonic in r,psi, just via
    # different modeling paths (empirical gains vs. Peters' L(chi) matrix
    # derived from low-aspect-ratio wing theory).
    if RUN_PLAN.run_07_pitt_peters_steady:
        print("=" * 78)
        print("7) STEADY PITT-PETERS vs 'global' (Drees): cross-validation (Section 6b)")
        print("=" * 78)
        print("   WARNING: without flapping, CMx/CMy grow large. Linear Pitt-Peters can leave")
        print("   its validity range at moderate mu_x (see the automatic warning in the output).")
        cfg_pp = BEMTConfig(Ne=60, Npsi=90, inflow_field_model="pitt_peters_steady",
                             reverse_flow_model="flat_plate", pitt_peters_outer_iter=60,
                             pitt_peters_relax=0.5, pitt_peters_tol=1e-7)
        cfg_drees_g = replace(cfg_pp, inflow_field_model="drees_global")
        print(f"  {'mu_x':>5} | {'CT (PP)':>9} {'CT (Drees)':>10} | {'CQ (PP)':>10} {'CQ (Drees)':>10}")
        for mu_v in RUN_PLAN.pitt_peters_mu_sweep:
            m_pp = solve_bemt(rotor, airfoil, cfg_pp, mu_x=mu_v, Vz=0.0)
            m_dr = solve_bemt(rotor, airfoil, cfg_drees_g, mu_x=mu_v, Vz=0.0)
            r_pp = aggregate_results(rotor, cfg_pp, m_pp)
            r_dr = aggregate_results(rotor, cfg_drees_g, m_dr)
            flag = "  <, see the warning" if m_pp.get("pitt_peters_warning") else ""
            print(f"  {mu_v:5.2f} | {r_pp['CT']:9.5f} {r_dr['CT']:10.5f} | "
                  f"{r_pp['CQ']:10.6f} {r_dr['CQ']:10.6f}{flag}")
            if m_pp.get("pitt_peters_warning"):
                print(f"          [WARNING] {m_pp['pitt_peters_warning']}")
        print()

    # =====================================================================
    # BLOCK 8 -- UNSTEADY PITT-PETERS: transition over time (Section 6b)
    # =====================================================================
    # Marches the states nu(t) along a SEQUENCE of flight conditions
    # (hover -> mu_x=0.10), and checks that, in the final stretch (where
    # mu_x has already been constant for a time >> the inflow's time
    # constant), the marched nu converges to the steady EQUILIBRIUM nu
    # solved in isolation at the same condition . Physical consistency
    # test of the dynamic model.
    if RUN_PLAN.run_08_pitt_peters_unsteady:
        print("=" * 78)
        print("8) UNSTEADY PITT-PETERS: simulated transition from hover to mu_x=0.10")
        print("=" * 78)
        cfg_unsteady = BEMTConfig(Ne=50, Npsi=72, inflow_field_model="drees_local", reverse_flow_model="flat_plate")
        seq = RUN_PLAN.pitt_peters_unsteady_sequence
        df_unsteady, _ = run_sweep_unsteady_pitt_peters(rotor, airfoil, cfg_unsteady, seq,
                                                          substeps_per_step=6)
        nu_final_unsteady = df_unsteady.iloc[-1][["nu0", "nu_s", "nu_c"]].to_numpy(dtype=float)
        r_norm_nodes_u, psi_nodes_u, R_NORM_u, PSI_u, R_DIM_u, CHORD_u, THETA_u = _pitt_peters_geometry(rotor, cfg_unsteady)
        nu_steady_eq, _, _, _ = _solve_pitt_peters_steady(
            rotor, airfoil, cfg_unsteady, mu_x=seq[-1][1], lambda_z=0.0,
            r_norm_nodes=r_norm_nodes_u, psi_nodes=psi_nodes_u, R_NORM=R_NORM_u, PSI=PSI_u,
            R_DIM=R_DIM_u, CHORD=CHORD_u, THETA=THETA_u)
        print(f"  nu at the end of the time-marched transition (t={df_unsteady.iloc[-1]['t']:.2f}s): "
              f"{np.round(nu_final_unsteady, 4)}")
        print(f"  steady-state equilibrium nu (same final mu_x, solved in isolation): "
              f"{np.round(nu_steady_eq, 4)}")
        print("  (the two values must stay close, because the last segment of the sequence holds mu_x constant "
              "for far longer than the inflow time constant , see Section 6b)")
        df_unsteady.to_csv(os.path.join(outdir, "zbemt_py_pitt_peters_unsteady.csv"), index=False)
        print()

    # =====================================================================
    # BLOCK 9 -- ØYE DYNAMIC STALL: static vs 'frequency' vs 'time_march'
    # =====================================================================
    # Compares CT/CQ without dynamic stall, with the fast 'frequency'
    # method (Fourier, no time marching) and with 'time_march' (explicit
    # marching in psi, more accurate/expensive). Includes a built-in
    # regression test: in pure hover (mu_x=0, pure 0th harmonic) the two
    # methods are MATHEMATICALLY identical . If they diverge there, it
    # signals an implementation bug.
    if RUN_PLAN.run_09_dynamic_stall:
        print("=" * 78)
        print("9) OYE DYNAMIC STALL: static vs 'frequency' vs 'time_march' (Section 4g)")
        print("=" * 78)
        cfg_ds_off = replace(cfg_run, use_dynamic_stall=False)
        cfg_ds_freq = replace(cfg_run, use_dynamic_stall=True, dynamic_stall_method="frequency")
        cfg_ds_tm = replace(cfg_run, use_dynamic_stall=True, dynamic_stall_method="time_march",
                             dynamic_stall_time_march_revolutions=8, dynamic_stall_time_march_avg_last=3)

        mu_ds = RUN_PLAN.mu_dynamic_stall
        maps_ds_off = solve_bemt(rotor, airfoil, cfg_ds_off, mu_x=mu_ds, Vz=0.0)
        t0 = time.perf_counter()
        maps_ds_freq = solve_bemt(rotor, airfoil, cfg_ds_freq, mu_x=mu_ds, Vz=0.0)
        t_freq = time.perf_counter() - t0
        t0 = time.perf_counter()
        maps_ds_tm = solve_bemt(rotor, airfoil, cfg_ds_tm, mu_x=mu_ds, Vz=0.0)
        t_tm = time.perf_counter() - t0

        row_off = aggregate_results(rotor, cfg_ds_off, maps_ds_off)
        row_freq = aggregate_results(rotor, cfg_ds_freq, maps_ds_freq)
        row_tm = aggregate_results(rotor, cfg_ds_tm, maps_ds_tm)

        cfg_ds_freq_hover = replace(cfg_ds_freq, Npsi=cfg_ds_freq.Npsi)
        cfg_ds_tm_hover = replace(cfg_ds_tm, Npsi=cfg_ds_tm.Npsi)
        maps_hover_freq = solve_bemt(rotor, airfoil, cfg_ds_freq_hover, mu_x=0.0, Vz=0.0)
        maps_hover_tm = solve_bemt(rotor, airfoil, cfg_ds_tm_hover, mu_x=0.0, Vz=0.0)
        err_hover = float(np.max(np.abs(maps_hover_freq["f_oye"] - maps_hover_tm["f_oye"])))

        print(f"  CT  : without DS={row_off['CT']:.5f}  DS(frequency)={row_freq['CT']:.5f}  "
              f"DS(time_march)={row_tm['CT']:.5f}")
        print(f"  CQ  : without DS={row_off['CQ']:.6f}  DS(frequency)={row_freq['CQ']:.6f}  "
              f"DS(time_march)={row_tm['CQ']:.6f}")
        print(f"  relative CT difference (frequency vs time_march): "
              f"{100*abs(row_freq['CT']-row_tm['CT'])/max(abs(row_tm['CT']),1e-9):.2f}%  "
              f"(expected small: 'frequency' uses a mean tau per station, 'time_march' uses local tau)")
        print(f"  time: frequency={t_freq*1000:.1f}ms  time_march={t_tm*1000:.1f}ms  "
              f"(speedup {t_tm/max(t_freq,1e-9):.1f}x)")
        print(f"  [regression test] hover (mu_x=0): max|f_frequency - f_time_march| = {err_hover:.2e} "
              f"(expected approximately zero, because at pure zeroth harmonic both methods are mathematically identical)")
        assert err_hover < 1e-6, "Øye: frequency and time_march must coincide in pure hover!"
        print("  [OK] frequency == time_march in hover (zeroth harmonic), as expected analytically.")

        r_idx_root = 2  # station near the root, where stall is most likely on this example rotor
        plt.figure(figsize=(7, 4))
        plt.plot(np.degrees(maps_ds_freq["psi_nodes"]), maps_ds_freq["Cl_static"][r_idx_root, :],
                  "--", label="static Cl", color="gray")
        plt.plot(np.degrees(maps_ds_freq["psi_nodes"]), maps_ds_freq["Cl"][r_idx_root, :],
                  "-", label="dynamic Cl (frequency)")
        plt.plot(np.degrees(maps_ds_tm["psi_nodes"]), maps_ds_tm["Cl"][r_idx_root, :],
                  ":", label="dynamic Cl (time_march)")
        plt.xlabel("psi [deg]"); plt.ylabel("Cl"); plt.legend(); plt.grid(alpha=0.3)
        plt.title(f"Oye dynamic stall. r/R={maps_ds_freq['r_norm_nodes'][r_idx_root]:.2f}, mu_x={mu_ds}")
        plt.tight_layout()
        plt.savefig(os.path.join(outdir, "oye_dynamic_stall_Cl_vs_psi.png"), dpi=130)
        plt.close()
        print()

    # =====================================================================
    # BLOCK 10 -- ROTOR vs PROPELLER MODE: non-dimensionalization identities
    # =====================================================================
    # Four consistency tests (Section 6c): (a) mu_x<->J_x and mu_z<->J_z are
    # exactly invertible. (b) alpha_deg reproduces the expected Vz.
    # (c) the identities CT_prop=CT*pi^3/4 match numerically.
    # (d) `solve_bemt_flight` with `is_propeller=True` works end-to-end
    # specifying the condition in J_x/J_z. It also demonstrates
    # "mode-aware" export and plotting: a sweep in J_x (propeller mode)
    # is exported with ALL columns (rotor and propeller, same
    # `aggregate_results`) and plotted with the PROPELLER columns.
    if RUN_PLAN.run_10_rotor_propeller_identities:
        print("=" * 78)
        print("10) ROTOR vs PROPELLER MODE: non-dimensionalization identities (Section 6c)")
        print("=" * 78)

        # --- 10a) mu_x<->J_x and mu_z<->J_z must reproduce EXACTLY the same (mu_x,Vz) ---
        mu_r, Vv_r, meta_r = resolve_advance_velocity(
            rotor, cfg_run, mu_x=RUN_PLAN.identities_mu, mu_z=RUN_PLAN.identities_mu_z)
        mu_p, Vv_p, meta_p = resolve_advance_velocity(rotor, cfg_run, J_x=meta_r["J_x"], J_z=meta_r["J_z"])
        print(f"  input (mu_x={RUN_PLAN.identities_mu}, mu_z={RUN_PLAN.identities_mu_z}) -> "
              f"mu_x={mu_r:.6f}  Vz={Vv_r:.6f}  (J_x equiv.={meta_r['J_x']:.6f}, J_z equiv.={meta_r['J_z']:.6f})")
        print(f"  the same condition through the equivalent (J_x,J_z) -> mu_x={mu_p:.6f}  Vz={Vv_p:.6f}")
        assert abs(mu_r - mu_p) < 1e-12 and abs(Vv_r - Vv_p) < 1e-9, \
            "mu_x<->J_x and mu_z<->J_z must be exactly invertible!"
        print("  [OK] mu_x<->J_x and mu_z<->J_z are exactly invertible (J_x=pi*mu_x, Section 6c).")

        # --- 10b) alpha_deg must reproduce the same Vz as the original run_sweep ---
        mu_a, Vv_a, meta_a = resolve_advance_velocity(
            rotor, cfg_run, mu_x=RUN_PLAN.identities_mu, alpha_deg=RUN_PLAN.identities_alpha_deg)
        Vv_manual = np.tan(np.deg2rad(RUN_PLAN.identities_alpha_deg)) * (RUN_PLAN.identities_mu * rotor.OmegaR)
        print(f"  alpha_deg={RUN_PLAN.identities_alpha_deg}deg (mu_x={RUN_PLAN.identities_mu}) -> Vz={Vv_a:.6f}  "
              f"(expected={Vv_manual:.6f}, recovered alpha_rotor={meta_a['alpha_rotor_deg']:.3f}deg)")
        assert abs(Vv_a - Vv_manual) < 1e-9 and abs(meta_a["alpha_rotor_deg"] - RUN_PLAN.identities_alpha_deg) < 1e-6

        # --- 10c) identities CT_prop=CT*pi^3/4, CQ_prop=CQ*pi^3/8, CP_prop=CP*pi^4/4, CP_prop=2*pi*CQ_prop ---
        maps_conv = solve_bemt(rotor, airfoil, cfg_run,
                                mu_x=RUN_PLAN.identities_mu_conversion, Vz=RUN_PLAN.identities_Vv_conversion)
        row_conv = aggregate_results(rotor, cfg_run, maps_conv)
        ct_pred = row_conv["CT"] * np.pi ** 3 / 4
        cq_pred = row_conv["CQ"] * np.pi ** 3 / 8
        cp_pred = row_conv["CP"] * np.pi ** 4 / 4
        print(f"  CT={row_conv['CT']:.6f}  CT_prop={row_conv['CT_prop']:.6f}  predicted(CT*pi^3/4)={ct_pred:.6f}")
        print(f"  CQ={row_conv['CQ']:.6f}  CQ_prop={row_conv['CQ_prop']:.6f}  predicted(CQ*pi^3/8)={cq_pred:.6f}")
        print(f"  CP={row_conv['CP']:.6f}  CP_prop={row_conv['CP_prop']:.6f}  predicted(CP*pi^4/4)={cp_pred:.6f}")
        print(f"  classical propeller identity CP_prop=2*pi*CQ_prop: "
              f"{row_conv['CP_prop']:.6f} vs {2*np.pi*row_conv['CQ_prop']:.6f}")
        for name, got, pred in (("CT_prop", row_conv["CT_prop"], ct_pred),
                                  ("CQ_prop", row_conv["CQ_prop"], cq_pred),
                                  ("CP_prop", row_conv["CP_prop"], cp_pred)):
            rel_err = abs(got - pred) / max(abs(pred), 1e-12)
            assert rel_err < 1e-9, f"{name}: rotor-to-propeller identity failed (relative error {rel_err:.2e})"
        assert abs(row_conv["CP_prop"] - 2 * np.pi * row_conv["CQ_prop"]) / max(abs(row_conv["CP_prop"]), 1e-12) < 1e-9
        print("  [OK] every rotor-to-propeller conversion identity holds within 1e-9 relative error.")

        # --- 10d) solve_bemt_flight with is_propeller=True, condition specified in J_x/J_z ---
        cfg_prop = replace(cfg_run, is_propeller=True)
        maps_flight = solve_bemt_flight(rotor, airfoil, cfg_prop, J_x=RUN_PLAN.identities_J_flight, J_z=0.0)
        row_flight = aggregate_results(rotor, cfg_prop, maps_flight, maps_flight["alpha_rotor_deg"])
        print(f"  solve_bemt_flight(J_x={RUN_PLAN.identities_J_flight}, J_z=0.0): "
              f"mu_x resolvido={maps_flight['mu_x']:.5f}  "
              f"CT_prop={row_flight['CT_prop']:.5f}  eta_prop={row_flight['eta_prop']:.4f}")

        # --- 10e) sweep + export + plot in "propeller mode" ---
        # Same advance sweep as the main grid, but in PROPELLER
        # CONVENTION (advance_kind='J_x'): the exported CSV has exactly the
        # SAME columns as block 2 (rotor AND propeller, full settings) --
        # only the plotting picks the 'propeller' family (x-axis=J_x,
        # panels CT_prop/CQ_prop/eta_prop/CP_prop).
        df_prop, _ = run_sweep(rotor, airfoil, cfg_prop, [np.pi * v for v in mu_sweep],
                                advance_kind="J_x", secondary_kind="alpha", secondary_sweep=[0.0])
        df_prop.to_csv(os.path.join(outdir, "zbemt_py_summary_propeller.csv"), index=False)
        plot_summary_vs_advance(df_prop, os.path.join(outdir, "summary_vs_J_propeller.png"), mode="propeller")
        print("  [OK] propeller-mode sweep exported (all columns) and plotted (mode='propeller').")
        print()

    # =====================================================================
    # BLOCK 11 -- REVERSE FLOW: 'viterna_full_range' (Viterna-Corrigan, Section 1b/4b)
    # =====================================================================
    # Extends block 4: compares the 3 reverse-flow models at the same
    # forward-flight condition (mu_benchmark). 'viterna_full_range' needs
    # an airfoil WRAPPED by `ViternaExtendedAirfoil` (the continuous
    # -180 to +180 degree polar is itself the continuity mechanism, not
    # a blend/branch like the other two) . That's why it uses
    # `airfoil_viterna` instead of the standard `airfoil`. Also plots
    # Cl(alpha) and Cd(alpha) of the extended airfoil over the whole
    # range for visual inspection of continuity at +-alpha_stall and
    # +-90 degrees.
    if RUN_PLAN.run_11_viterna_full_range:
        print("=" * 78)
        print("11) REVERSE FLOW: 'viterna_full_range' (Viterna-Corrigan) vs 'flat_plate'/'thin_plate_blend'")
        print("=" * 78)
        airfoil_viterna = build_example_viterna_airfoil(stall_model="enhanced")

        cfg_vfr = replace(cfg_bench, reverse_flow_model="viterna_full_range", collect_history=True)
        maps_fp2 = solve_bemt(rotor, airfoil, cfg_bench, mu_x=RUN_PLAN.mu_benchmark, Vz=0.0)
        maps_tp2 = solve_bemt(rotor, airfoil, replace(cfg_bench, reverse_flow_model="thin_plate_blend",
                                                        collect_history=True),
                               mu_x=RUN_PLAN.mu_benchmark, Vz=0.0)
        maps_vfr = solve_bemt(rotor, airfoil_viterna, cfg_vfr, mu_x=RUN_PLAN.mu_benchmark, Vz=0.0)
        ct_fp = aggregate_results(rotor, cfg_bench, maps_fp2)["CT"]
        ct_tp = aggregate_results(rotor, replace(cfg_bench, reverse_flow_model="thin_plate_blend"), maps_tp2)["CT"]
        ct_vfr = aggregate_results(rotor, cfg_vfr, maps_vfr)["CT"]
        print(f"  flat_plate        : it_max={maps_fp2['total_iterations']:3d}  "
              f"conv={100*np.mean(maps_fp2['converged']):5.1f}%  CT={ct_fp:.5f}")
        print(f"  thin_plate_blend  : it_max={maps_tp2['total_iterations']:3d}  "
              f"conv={100*np.mean(maps_tp2['converged']):5.1f}%  CT={ct_tp:.5f}")
        print(f"  viterna_full_range: it_max={maps_vfr['total_iterations']:3d}  "
              f"conv={100*np.mean(maps_vfr['converged']):5.1f}%  CT={ct_vfr:.5f}")

        alpha_deg_full = np.linspace(-180, 180, 721)
        cl_full, cd_full = airfoil_viterna.cl_cd(np.deg2rad(alpha_deg_full))
        fig, axs = plt.subplots(1, 2, figsize=(11, 4.2))
        axs[0].plot(alpha_deg_full, cl_full)
        axs[0].axvline(np.degrees(airfoil_viterna.alpha_s_pos), color="gray", ls="--", lw=0.8)
        axs[0].axvline(np.degrees(airfoil_viterna.alpha_s_neg), color="gray", ls="--", lw=0.8)
        axs[0].set_xlabel(r"$\alpha$ (deg)"); axs[0].set_ylabel(r"$C_L$"); axs[0].grid(True)
        axs[1].plot(alpha_deg_full, cd_full)
        axs[1].set_xlabel(r"$\alpha$ (deg)"); axs[1].set_ylabel(r"$C_D$"); axs[1].grid(True)
        fig.suptitle("Viterna-Corrigan extension (-180..+180 degrees)")
        fig.tight_layout()
        fig.savefig(os.path.join(outdir, "viterna_full_range_polar.png"), dpi=130)
        plt.close(fig)
        print("  [OK] extended polar (-180..+180) saved to viterna_full_range_polar.png")
        print()

    print("Complete. Files saved in", outdir)
