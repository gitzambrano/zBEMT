"""Orchestrate in-memory BEMT cases, sweeps, batches, and trim operations.

Purpose and objectives:
    Convert project data into engine inputs, execute one or more flight
    conditions, apply cancellation and progress callbacks, and return results.

Inputs and outputs:
    Inputs are ``Project``, ``FlightCondition``, ``BatchDefinition``, and
    optional callbacks. Outputs are ``Results`` or ordered result lists. This
    module never writes project or result files.

Functions and interactions:
    Public operations execute cases, generate batches, trim conditions, and
    benchmark solvers. ``api.py`` is the GUI/CLI caller; ``bemt.py`` performs
    the solve and ``airfoils.py`` builds polar models.

Conventions and limitations:
    RPM is required because it defines the nondimensional velocity scale.
    Conditions use engine disk axes. Display conversion belongs to
    ``nomenclature.py``. Returned results do not imply experimental accuracy.
"""

from __future__ import annotations

import itertools
import math
import time
from dataclasses import fields, replace
from typing import Callable, Optional, Sequence

import numpy as np

from .models import (Project, RotorGeometryDef, FlightCondition,
                     BatchDefinition, Results, OptimizationDefinition,
                     OptimizationOutcome, DesignVariable, GEOMETRY_PARAMS,
                     INTEGER_PARAMS)
from . import airfoils
from . import geometry as geometry_gen
from . import nomenclature
from .bemt import BEMTConfig, Rotor, solve_bemt, aggregate_results, SolveCancelled

# Fixed-point solvers available in bemt.py (see bemt._SOLVERS), used
# as the default for benchmark_solvers().
_KNOWN_SOLVERS = ("fixed_point", "newton", "bisection", "aitken")


# =============================================================================
# Model -> engine conversions (unique to this file, api.py does not duplicate them)
# =============================================================================

def _require_rpm(rpm, context: str = "the flight condition") -> float:
    """RPM is REQUIRED for every flight condition.

    There is no reasonable default: BEMT nondimensionalizes everything by
    ``Omega*R``, so rotation speed sets the entire scale of the problem:
    thrust, torque, Reynolds, and tip Mach. There used to be a 1000 RPM
    placeholder here for conditions without rpm, and it produced
    plausible-looking results from a made-up rotation speed, with nothing
    to give it away. Failing loudly is the only honest option."""
    if rpm is None:
        raise ValueError(
            f"RPM not provided in {context}. BEMT adimensionalizes by "
            "Omega*R, so rotation is required. There is no physically "
            "defensible default. Fill in `FlightCondition.rpm`.")
    rpm_value = float(rpm)
    if not np.isfinite(rpm_value) or rpm_value <= 0.0:
        raise ValueError(
            f"Invalid RPM in {context}: {rpm_value!r}. Must be a "
            "finite number greater than zero.")
    return rpm_value


def _to_rotor(geom: RotorGeometryDef, collective_deg: float = 0.0,
               rpm: Optional[float] = None) -> Rotor:
    """Builds the engine's ``Rotor`` from the project's radial table.

    ``collective_deg`` is added as a RIGID offset (uniform across the
    whole radius) on top of the geometric twist (`geom.twist_deg`, which
    already carries the built-in root->tip washout). This is exactly what
    a collective command does physically. Without this, a
    ``FlightCondition.collective_deg`` change has no effect at all on the
    result, which is the bug fixed here.

    ``rpm`` is required (see ``_require_rpm``); it is only optional in
    the signature so that callers who need just the geometry (unit
    conversions that use ``R`` and nothing else) can omit it."""
    theta = np.asarray(geom.twist_deg, dtype=float) + collective_deg
    return Rotor(
        R=geom.radius_m,
        Nb=geom.n_blades,
        Omega_rpm=float(rpm) if rpm is not None else 1.0,
        r_root_norm_geom=geom.root_cutout_norm,
        r_tip_norm_geom=1.0,
        r_geom=np.asarray(geom.r_norm, dtype=float),
        chord_geom=np.asarray(geom.chord_norm, dtype=float) * geom.radius_m,
        theta_geom_deg=theta,
    )


_OLD_INFLOW_MODEL_TO_FIELD = {
    ("glauert", "local"): "glauert_local", ("glauert", "global"): "glauert_global",
    ("coleman", "local"): "coleman_local", ("coleman", "global"): "coleman_global",
    ("drees", "local"): "drees_local", ("drees", "global"): "drees_global",
    ("glauert", "pitt_peters"): "pitt_peters_steady", ("coleman", "pitt_peters"): "pitt_peters_steady",
    ("drees", "pitt_peters"): "pitt_peters_steady",
}


def _migrate_config_dict(config_dict: dict) -> dict:
    """Migrates a config dict saved under the old schema (separate
    ``inflow_model``/``inflow_coupling`` fields and/or ``use_compressibility``
    inside ``AirfoilDef``, and/or a ``use_prandtl_loss`` bool) to the current
    ``BEMTConfig`` schema (single ``inflow_field_model`` field, and
    ``prandtl_loss_mode`` str, see docs/plano.md GUI v3 Phase B).
    Idempotent: a dict already in the current schema passes through unchanged."""
    migrated = dict(config_dict)

    if "prandtl_loss_mode" not in migrated and "use_prandtl_loss" in migrated:
        old_bool = migrated.pop("use_prandtl_loss")
        migrated["prandtl_loss_mode"] = "both" if old_bool else "off"

    if "inflow_field_model" in migrated:
        return migrated
    if "inflow_model" not in migrated and "inflow_coupling" not in migrated:
        return migrated
    old_model = migrated.pop("inflow_model", "glauert")
    old_coupling = migrated.pop("inflow_coupling", "local")
    migrated["inflow_field_model"] = _OLD_INFLOW_MODEL_TO_FIELD.get(
        (old_model, old_coupling), "glauert_local")
    return migrated


def _build_config(config_dict: dict, airfoil_def=None) -> BEMTConfig:
    """Builds the engine's BEMTConfig from the dict saved in config.bemt.

    No longer copies dynamic-stall fields from ``airfoil_def`` into the
    BEMTConfig (docs/plano_v2.md Section 2.4/6.3, Finding #1): now
    ``airfoils.to_airfoil()`` already attaches ``dynamic_stall_params``
    directly to the airfoil object, and that is what ``bemt.solve_bemt``
    reads (with a fallback to the like-named BEMTConfig fields only for
    backward compatibility). ``airfoil_def`` is still accepted here just
    to keep the function's signature stable; it no longer has any effect
    on the returned cfg."""
    config_dict = _migrate_config_dict(config_dict)
    valid = {f.name for f in fields(BEMTConfig)}
    cfg = BEMTConfig(**{k: v for k, v in config_dict.items() if k in valid})
    return cfg


# =============================================================================
# Single case
# =============================================================================

def run_single_case(project: Project, condition: FlightCondition,
                     should_cancel=None) -> Results:
    """Runs a single flight condition over the project's
    geometry/airfoil/config. Applies ``condition.collective_deg`` (see
    ``_to_rotor``).

    ``condition.rpm`` is REQUIRED. See ``_require_rpm`` for why there
    is no default."""
    cfg = _build_config(project.config, airfoil_def=project.airfoil)
    rpm = _require_rpm(condition.rpm, f"condition {condition.name!r}")
    rotor = _to_rotor(project.geometry, collective_deg=condition.collective_deg, rpm=rpm)

    # RADIAL profile of Reynolds and Mach numbers for the flight condition.
    # Each blade
    # station picks its own polar: Re grows nearly linearly with radius, so
    # root and tip fall into different slices when the table has that axis.
    # Without this, the whole table collapsed onto the FIRST slice, silently
    # ignoring the entire sweep (see `airfoils.radial_reynolds_mach`).
    radial = airfoils.radial_reynolds_mach(rotor, cfg, mu_x=condition.mu_x)
    airfoil_obj = airfoils.to_blade_airfoil(
        project.airfoil_sections or [project.airfoil], radial=radial)

    maps = solve_bemt(rotor, airfoil_obj, cfg, mu_x=condition.mu_x, Vz=condition.Vz,
                       should_cancel=should_cancel)
    summary = aggregate_results(rotor, cfg, maps)

    # Convenience aliases for the 2 factorial variables (Part 4.2) that
    # `aggregate_results` does not natively expose ("mu_x"/"alpha_rotor_deg"
    # already come from there). `plots.plot_coefficients_vs_axis` (Results
    # hub, "Coefficients vs axis") reads `summary["collective_deg"]`/
    # `summary["rpm"]` directly. `setdefault` avoids colliding with any
    # future key of the same name coming from `aggregate_results`.
    summary.setdefault("collective_deg", condition.collective_deg)
    summary.setdefault("rpm", summary.get("rotor_rpm", condition.rpm))

    # The CONDITION also goes into `maps`, not just `summary`: `viz.plots`
    # functions receive only `maps` and it is their job to build the figure
    # title. Without this, a disk map's title could only say "mu_x=0.000",
    # and in hover, where mu_x=0, that identifies no case at all: two
    # different collectives produced figures with the same title.
    maps.setdefault("collective_deg", condition.collective_deg)
    maps.setdefault("rpm", summary.get("rotor_rpm", condition.rpm))
    maps.setdefault("alpha_rotor_deg", summary.get("alpha_rotor_deg"))
    maps.setdefault("CT", summary.get("CT"))

    return Results(summary=summary, dataframe=None, maps=maps, condition_name=condition.name)


# =============================================================================
# "Trimmed" case (fixes RPM and collective by default. Here one of them
# is fixed and the other is solved by bisection until a thrust or CT
# target is hit)
# =============================================================================

_TRIM_MODES = ("solve_collective", "solve_rpm")
_TRIM_TARGET_KINDS = ("thrust", "CT")
_DEFAULT_TRIM_BRACKET = {"solve_collective": (-10.0, 30.0), "solve_rpm": (10.0, 20000.0)}


def run_case_trimmed(project: Project, condition: FlightCondition, *,
                      trim_mode: str, target_kind: str, target_value: float,
                      bracket: Optional[tuple[float, float]] = None,
                      tol: float = 1e-4, max_iter: int = 40,
                      should_cancel: Optional[Callable[[], bool]] = None) -> Results:
    """Runs ``condition`` but OVERRIDES one of the two trim DOFs
    (collective or RPM) by bisection until ``Results.summary[<Thrust|CT>]``
    matches ``target_value``. The other DOF stays fixed at the value
    already present in ``condition``.

    ``trim_mode``: "solve_collective" (RPM fixed at ``condition.rpm``,
    solves ``collective_deg``) or "solve_rpm" (collective fixed at
    ``condition.collective_deg``, solves ``rpm``). Bisection, not
    Newton/secant: robust even if CT(collective)/CT(rpm) is not perfectly
    smooth near stall. The same `bisection` solver already exists in
    `bemt.py` for each element's inner loop, for an analogous reason.
    Requires ``target_value`` to lie BETWEEN the two extremes of
    ``bracket`` (opposite signs of ``summary[key] - target_value``).
    Otherwise it raises ``ValueError`` explaining how to widen the bracket,
    instead of converging outside the physically plausible interval.

    ``should_cancel`` is checked between iterations of the trim loop AND,
    inside each `run_single_case`, once per engine solver iteration (same
    convention as `_run_conditions`). It raises ``SolveCancelled``, which
    propagates to the caller (there is no list of partial cases here, it
    is a single case)."""
    if trim_mode not in _TRIM_MODES:
        raise ValueError(f"run_case_trimmed: trim_mode must be one of {_TRIM_MODES}, got {trim_mode!r}")
    if target_kind not in _TRIM_TARGET_KINDS:
        raise ValueError(f"run_case_trimmed: target_kind must be one of {_TRIM_TARGET_KINDS}, got {target_kind!r}")
    summary_key = "Thrust" if target_kind == "thrust" else "CT"
    target_value = float(target_value)

    def _eval(x: float) -> Results:
        if should_cancel is not None and should_cancel():
            raise SolveCancelled()
        cond = replace(condition, collective_deg=x) if trim_mode == "solve_collective" \
            else replace(condition, rpm=x)
        return run_single_case(project, cond, should_cancel=should_cancel)

    lo, hi = bracket if bracket is not None else _DEFAULT_TRIM_BRACKET[trim_mode]
    lo, hi = float(lo), float(hi)

    res_lo, res_hi = _eval(lo), _eval(hi)
    f_lo = res_lo.summary[summary_key] - target_value
    f_hi = res_hi.summary[summary_key] - target_value
    if f_lo == 0.0:
        return res_lo
    if f_hi == 0.0:
        return res_hi
    if f_lo * f_hi > 0.0:
        dof = "collective_deg" if trim_mode == "solve_collective" else "rpm"
        raise ValueError(
            f"run_case_trimmed: target {summary_key}={target_value!r} is not bracketed between "
            f"{dof}={lo!r} ({summary_key}={res_lo.summary[summary_key]!r}) and "
            f"{dof}={hi!r} ({summary_key}={res_hi.summary[summary_key]!r}). Widen `bracket`.")

    best = res_lo if abs(f_lo) < abs(f_hi) else res_hi
    for _ in range(max_iter):
        mid = 0.5 * (lo + hi)
        res_mid = _eval(mid)
        f_mid = res_mid.summary[summary_key] - target_value
        best = res_mid
        if abs(f_mid) <= tol * max(abs(target_value), 1e-9) or (hi - lo) < 1e-6:
            return res_mid
        if (f_lo < 0.0) == (f_mid < 0.0):
            lo, f_lo = mid, f_mid
        else:
            hi, f_hi = mid, f_mid
    return best


# =============================================================================
# Running a list of conditions with optional progress and cancellation
# (docs/plano_v3.md Part 2, worker thread). Knows nothing about Qt: it
# receives only plain callables, so gui.py can feed them from a
# QThread/worker without studies.py needing to import PyQt6. Non-invasive
# change: ``on_case_done``/``should_cancel`` defaulting to ``None``
# preserves EXACTLY the previous behavior (synchronous list comprehension,
# any case's exception propagates immediately) for all existing
# script/API/CLI usage.
# =============================================================================

def _run_conditions(project: Project, conditions: Sequence[FlightCondition], *,
                     on_case_done: Optional[Callable[[int, int, object], None]] = None,
                     should_cancel: Optional[Callable[[], bool]] = None,
                     runner: Optional[Callable[[FlightCondition], Results]] = None) -> list[Results]:
    """Runs ``conditions`` in order, returning the successful ``Results``.

    - Without ``on_case_done``: behavior identical to
      ``[run_single_case(project, c) for c in conditions]``. Any case's
      exception propagates immediately (backward compatibility).
    - With ``on_case_done``: each case is isolated in a ``try/except``, so a
      failure does not bring down the whole batch. ``on_case_done(index,
      total, result_or_exception)`` is called after EVERY case (success or
      error), in order, so the GUI can emit incremental progress
      ("case 7: OK, CT=..." / "case 8: ERROR — see log").
    - ``should_cancel``: checked before each case AND, inside the engine,
      once per solver iteration. If it returns ``True``, the sweep stops
      right there: the cases already completed are returned, with no
      error, and the case in progress is discarded (an interrupted solve
      does not converge, and returning it would hand over half a solution
      dressed up as a result). Without the internal check, a single case
      inside a production mesh ignored the "Cancel" button until it
      finished on its own, which is exactly when it gets cancelled."""
    total = len(conditions)
    results: list[Results] = []
    for i, cond in enumerate(conditions):
        if should_cancel is not None and should_cancel():
            break
        if on_case_done is None:
            try:
                results.append((runner(cond) if runner is not None else
                                run_single_case(project, cond, should_cancel=should_cancel)))
            except SolveCancelled:
                break
            continue
        try:
            res = (runner(cond) if runner is not None else
                   run_single_case(project, cond, should_cancel=should_cancel))
        except SolveCancelled:
            # cancellation is not a case failure: it does not go to
            # `on_case_done` as an error, does not enter the problem log,
            # it just stops the sweep
            break
        except Exception as exc:  # noqa: BLE001: isolates each error per case, see docstring
            on_case_done(i, total, exc)
            continue
        results.append(res)
        on_case_done(i, total, res)
    return results


# =============================================================================
# Sweeps
# =============================================================================

def run_mu_sweep(project: Project, mu_values: Sequence[float], *,
                  name_prefix: str = "mu_x", collective_deg: float = 8.0,
                  Vz: float = 0.0, rpm: Optional[float] = None,
                  on_case_done: Optional[Callable[[int, int, object], None]] = None,
                  should_cancel: Optional[Callable[[], bool]] = None) -> list[Results]:
    """Sweeps the advance ratio ``mu_x`` at fixed collective/Vz/rpm."""
    conditions = [
        FlightCondition(name=f"{name_prefix}_{mu_x:g}", mu_x=mu_x, Vz=Vz,
                         collective_deg=collective_deg, rpm=rpm)
        for mu_x in mu_values
    ]
    return _run_conditions(project, conditions, on_case_done=on_case_done, should_cancel=should_cancel)


def run_alpha_sweep(project: Project, alpha_deg_values: Sequence[float], *,
                     mu_x: float, name_prefix: str = "alpha",
                     collective_deg: float = 8.0, rpm: Optional[float] = None,
                     on_case_done: Optional[Callable[[int, int, object], None]] = None,
                     should_cancel: Optional[Callable[[], bool]] = None) -> list[Results]:
    """Sweeps the disk angle of attack (``alpha_rotor_deg``) at fixed
    ``mu_x``, deriving ``Vz = tan(alpha) * Vx``, with the same
    convention as ``bemt.resolve_advance_velocity``."""
    # (no BEMTConfig is built here: `run_single_case` builds its own for
    # each condition, from `project.config`)
    # rpm enters the alpha -> Vz conversion (via OmegaR), so it is
    # required here for the same reason as `run_single_case`.
    rpm = _require_rpm(rpm, "run_alpha_sweep")
    rotor = _to_rotor(project.geometry, collective_deg=collective_deg, rpm=rpm)
    Vinf_long = mu_x * rotor.OmegaR

    conditions = [
        FlightCondition(name=f"{name_prefix}_{a:g}", mu_x=mu_x,
                         Vz=float(np.tan(np.deg2rad(a)) * Vinf_long),
                         collective_deg=collective_deg, rpm=rpm)
        for a in alpha_deg_values
    ]
    return _run_conditions(project, conditions, on_case_done=on_case_done, should_cancel=should_cancel)


def run_collective_sweep(project: Project, collective_deg_values: Sequence[float], *,
                          mu_x: float = 0.0, Vz: float = 0.0,
                          name_prefix: str = "collective",
                          rpm: Optional[float] = None,
                          on_case_done: Optional[Callable[[int, int, object], None]] = None,
                          should_cancel: Optional[Callable[[], bool]] = None) -> list[Results]:
    """Sweeps collective at fixed mu_x/Vz/rpm."""
    conditions = [
        FlightCondition(name=f"{name_prefix}_{c:g}", mu_x=mu_x, Vz=Vz,
                         collective_deg=c, rpm=rpm)
        for c in collective_deg_values
    ]
    return _run_conditions(project, conditions, on_case_done=on_case_done, should_cancel=should_cancel)


# =============================================================================
# Factorial analysis (docs/plano.md Section 7 / 9 item 7, Phase C, Phase 8,
# see docs/CHANGELOG.md, extended to accept the interchangeable
# conventions mu_x/J_x and alpha_deg/Vz): 1 to 3 axes chosen among
# {mu_x, J_x, alpha_deg, Vz, collective_deg, rpm}, Cartesian product of
# each axis's values. Generalizes run_mu_sweep/run_alpha_sweep/
# run_collective_sweep (one axis each) to N axes.
# =============================================================================

# `mu_x`/`J_x`/`V` are THREE REPRESENTATIONS of the same physical quantity
# (longitudinal advance ratio: mu_x dimensionless, J_x=pi*mu_x propeller
# convention, V = mu_x*OmegaR dimensional velocity [m/s]). `alpha_deg`/`Vz`
# are likewise for the axial component. Each pair/trio occupies a single "slot".
#
# Each slot ALSO accepts the representation that is natural in the other
# mode: in a PROPELLER the main component is the axial one, and it is
# written as an advance ratio (`mu_z`/`J_z`, shown on screen as mu_x/J_x,
# see `api.summary_symbols`). The cross component is the one
# written as an angle, but measured from the SHAFT (`alpha_disk`), not
# from the plane. The names here are the ENGINE's (disk axes). The
# translation to propeller letters is the interface's job.
_INPLANE_VARIABLES = ("mu_x", "J_x", "Vx", "alpha_disk")
_AXIAL_VARIABLES = ("alpha_deg", "Vz", "mu_z", "J_z")
_OTHER_FACTORIAL_VARIABLES = ("collective_deg", "rpm")
_FACTORIAL_VARIABLES = _INPLANE_VARIABLES + _AXIAL_VARIABLES + _OTHER_FACTORIAL_VARIABLES

# WHICH representations a factorial axis accepts is this module's business
# (above). WHICH physical component each one describes is not, because that is
# `nomenclature.slot_of`, shared with the GUI and the report. The two lists
# above are checked against it, so a variable added to one and forgotten in
# the other fails here instead of grouping silently wrong.
assert all(nomenclature.slot_of(v) == "inplane" for v in _INPLANE_VARIABLES)
assert all(nomenclature.slot_of(v) == "axial" for v in _AXIAL_VARIABLES)


#: The condition NAME comes from `nomenclature`, in the axis letters of the
#: MODE. The name is what appears in the "Choose condition to plot" combo, in
#: the label column of the Results table and in the report, where a raw
#: `mu_x=0_alpha_deg=-10` would be a field name rather than a quantity. And
#: it has to be in the mode's letters: a propeller case named "μ_x=0.4" for
#: its CROSS flow would name the cross-flow as if it were the advance ratio.
#:
#: `FlightCondition.name` is still free text. `api.sanitize_filename`
#: transcribes these symbols back to ASCII when the name becomes a file name.
condition_name = nomenclature.condition_label


def _factorial_slot(variable: str) -> str:
    """The logical slot a factorial variable belongs to: `mu_x`/`J_x`/`Vx`
    and `alpha_disk` are all the same in-plane component, and `alpha_deg`/`Vz`/
    `mu_z`/`J_z` are the same axial one. Used to detect a conflict between two
    axes, and between an axis and a fixed value of the same quantity.

    The membership comes from `nomenclature`, which is also what names the
    slot's row in the GUI. A variable cannot be grouped one way here and
    labeled another way on screen."""
    if variable in _FACTORIAL_VARIABLES and variable not in _OTHER_FACTORIAL_VARIABLES:
        return nomenclature.slot_of(variable)
    return variable


def run_factorial_batch(project: Project, axes: list[dict], fixed: Optional[dict] = None, *,
                         on_case_done: Optional[Callable[[int, int, object], None]] = None,
                         should_cancel: Optional[Callable[[], bool]] = None) -> list[Results]:
    """Runs ALL combinations of the Cartesian product (see
    ``build_factorial_conditions``, which builds the list)."""
    conditions = build_factorial_conditions(project, axes, fixed)
    return _run_conditions(project, conditions, on_case_done=on_case_done,
                            should_cancel=should_cancel)


def build_factorial_conditions(project: Project, axes: list[dict],
                                fixed: Optional[dict] = None) -> list[FlightCondition]:
    """Builds all combinations (Cartesian product) of the ``values`` of
    each axis in ``axes``, WITHOUT RUNNING them.

    Kept separate from ``run_factorial_batch`` so the GUI can SHOW the
    cases that will be run before running them: a 3x4x2 factorial is 24
    solves, and seeing the list before firing is the difference between
    reviewing and hoping.

    ``axes``: list of 1 to 3 dicts ``{"variable": <name>, "values": [...]}``,
    with ``variable`` in ``_FACTORIAL_VARIABLES`` and no two axes in the
    same slot (``mu_x``+``J_x`` together, or ``alpha_deg``+``Vz`` together,
    are both an error). See ``_factorial_slot``.

    ``fixed``: values for the variables NOT chosen as an axis. Accepts
    both the native ``FlightCondition`` fields (``mu_x``, ``Vz``,
    ``collective_deg``, ``rpm``) and the alternative representations of
    the same slot: ``J_x``/``V``/``alpha_disk`` in place of ``mu_x``,
    and ``mu_z``/``J_z``/``alpha_deg`` in place of ``Vz``, at most one
    per slot.

    ANGLES ARE DERIVED, THE OTHER REPRESENTATIONS ARE CONVERTED. If
    ``alpha_deg`` (measured from the disk PLANE) is the axis or the axial
    fixed value, ``Vz`` is derived in each combination from the ``mu_x``
    already resolved for that combination (same formula as
    ``run_alpha_sweep``). If ``alpha_disk`` (measured from the SHAFT,
    the propeller convention) is the axis or the longitudinal fixed value,
    the dependency INVERTS: the axial component is resolved first and
    ``mu_x`` comes from it. Both angles at once are an error: no component
    would set the scale of the velocity.
    """
    if not (1 <= len(axes) <= 3):
        raise ValueError(f"run_factorial_batch: provide 1 to 3 axes (got {len(axes)}).")
    variables = [ax["variable"] for ax in axes]
    if len(set(variables)) != len(variables):
        raise ValueError(f"run_factorial_batch: repeated variables among axes: {variables}")
    for v in variables:
        if v not in _FACTORIAL_VARIABLES:
            raise ValueError(
                f"run_factorial_batch: unknown axis variable {v!r}. "
                f"Options: {_FACTORIAL_VARIABLES}")
    axis_slots = [_factorial_slot(v) for v in variables]
    if len(set(axis_slots)) != len(axis_slots):
        raise ValueError(
            f"run_factorial_batch: mu_x/J_x (or alpha_deg/Vz) are the same quantity. "
            f"They cannot be two axes at the same time: {variables}")

    fixed = dict(fixed or {})
    inplane_fixed = {k: fixed[k] for k in _INPLANE_VARIABLES if k in fixed}
    axial_fixed = {k: fixed[k] for k in _AXIAL_VARIABLES if k in fixed}
    if len(inplane_fixed) > 1:
        raise ValueError(
            f"run_factorial_batch: specify at most one of "
            f"{'/'.join(_INPLANE_VARIABLES)} as fixed: {list(inplane_fixed)}")
    if len(axial_fixed) > 1:
        raise ValueError(
            f"run_factorial_batch: specify at most one of "
            f"{'/'.join(_AXIAL_VARIABLES)} as fixed: {list(axial_fixed)}")
    if inplane_fixed and "inplane" in axis_slots:
        raise ValueError(
            f"run_factorial_batch: {list(inplane_fixed)} cannot be fixed at the same time "
            f"the in-plane component is chosen as an axis.")
    if axial_fixed and "axial" in axis_slots:
        raise ValueError(
            f"run_factorial_batch: {list(axial_fixed)} cannot be fixed at the same time "
            f"the axial component is chosen as an axis.")

    # Auxiliary rotor ONLY to obtain OmegaR in the V->mu_x and
    # alpha_deg->Vz conversions. Created BEFORE any use (the `base_mu`
    # block below already needs it when "Vx" is the longitudinal fixed
    # value). Only this auxiliary rotor's radius is used (see `_omega_R`),
    # never its OmegaR. That is why it does not need rpm.
    rotor_for_omega = _to_rotor(project.geometry)
    is_propeller = bool((project.config or {}).get("is_propeller", False))

    def _omega_R(rpm_value) -> float:
        """OmegaR corresponding to a specific rpm. Each combination
        resolves ITS OWN rpm before converting, with no mutation of a
        shared rotor inside the loop. Otherwise a combo's conversion would
        end up using
        the previous combo's rpm and the result would depend on the order
        of the values on the axis (same formula as `Rotor.OmegaR`)."""
        rpm_value = _require_rpm(rpm_value, "run_factorial_batch (rpm axis or fixed value)")
        return rpm_value * 2.0 * np.pi / 60.0 * rotor_for_omega.R

    # The TWO angles together do not close the condition: `alpha_deg`/
    # `alpha_rotor` (from the disk PLANE) derives the axial from the
    # in-plane component, and `alpha_disk` (from the SHAFT) does the
    # opposite. So neither one sets the scale of the velocity. Same
    # rule as `bemt.resolve_advance_velocity`, checked here because this
    # path builds the conditions without going through there.
    uses_disk_angle = ("alpha_disk" in inplane_fixed) or ("alpha_disk" in variables)
    uses_plane_angle = ("alpha_deg" in axial_fixed) or ("alpha_deg" in variables)
    if uses_disk_angle and uses_plane_angle:
        raise ValueError(
            "run_factorial_batch: alpha_disk (from the shaft, the propeller-mode "
            "angle) and alpha_rotor (from the disk plane, the rotor-mode one) are "
            "the same angle written two ways. With both, neither velocity "
            "component sets the scale. Use one angle plus a dimensional or "
            "non-dimensional component.")

    base_mu = 0.0
    base_rpm = fixed.get("rpm", None)
    if "mu_x" in inplane_fixed:
        base_mu = float(inplane_fixed["mu_x"])
    elif "J_x" in inplane_fixed:
        base_mu = float(inplane_fixed["J_x"]) / np.pi
    elif "Vx" in inplane_fixed and base_rpm is not None:
        # With rpm fixed, a fixed `V` gives a fixed mu_x. If rpm is an
        # AXIS, base_rpm is None and there is no base mu_x to compute:
        # each combination recomputes its own (the loop below handles
        # `"Vx" in inplane_fixed` explicitly).
        om = _omega_R(base_rpm)
        base_mu = float(inplane_fixed["Vx"]) / om if om > 1e-9 else 0.0

    base_axial_kind, base_axial_value = None, 0.0
    for _k in ("Vz", "mu_z", "J_z", "alpha_deg"):
        if _k in axial_fixed:
            base_axial_kind, base_axial_value = _k, float(axial_fixed[_k])
            break

    base_collective = float(fixed.get("collective_deg", 8.0))

    conditions: list[FlightCondition] = []
    for combo in itertools.product(*(ax["values"] for ax in axes)):
        overrides = dict(zip(variables, combo))

        # rpm FIRST: everything that converts (V->mu_x, alpha_deg->Vz)
        # depends on THIS combination's OmegaR, not the previous one.
        rpm = overrides.get("rpm", base_rpm)
        omega_R = _omega_R(rpm)

        collective_deg = float(overrides.get("collective_deg", base_collective))

        def _axial(Vinf_long: float) -> float:
            """Axial component of this combination. ``Vinf_long`` is only
            used by the disk-angle branch (the only one that DERIVES from
            the in-plane component)."""
            kind, value = base_axial_kind, base_axial_value
            for k in _AXIAL_VARIABLES:
                if k in overrides:
                    kind, value = k, float(overrides[k])
                    break
            if kind == "Vz":
                return float(value)
            if kind == "mu_z":
                return float(value) * omega_R
            if kind == "J_z":
                return (float(value) / np.pi) * omega_R
            if kind == "alpha_deg":
                return float(np.tan(np.deg2rad(value)) * Vinf_long)
            return 0.0

        # ORDER: with `alpha_disk` the dependency inverts, because it is
        # the in-plane component that derives from the axial one. The
        # axial component therefore has to come out first. See
        # `bemt.resolve_advance_velocity`, which resolves the same inversion.
        if "alpha_disk" in overrides or "alpha_disk" in inplane_fixed:
            alpha_disk = float(overrides.get("alpha_disk", inplane_fixed.get("alpha_disk", 0.0)))
            Vz = _axial(0.0)
            # |Vz|: see `bemt.resolve_advance_velocity`. With Vz<0 the
            # raw sign would flip the side of the cross flow and the
            # reported angle would stop matching the geometry.
            mu_x = ((float(np.tan(np.deg2rad(alpha_disk))) * abs(Vz)) / omega_R
                  if omega_R > 1e-9 else 0.0)
        else:
            if "mu_x" in overrides:
                mu_x = float(overrides["mu_x"])
            elif "J_x" in overrides:
                mu_x = float(overrides["J_x"]) / np.pi
            elif "Vx" in overrides:
                mu_x = float(overrides["Vx"]) / omega_R if omega_R > 1e-9 else 0.0
            elif "Vx" in inplane_fixed:
                # A fixed `V` is a dimensional velocity: the equivalent mu_x
                # changes with the combination's rpm, so recompute here
                # instead of using `base_mu` (which was resolved with the
                # base rpm).
                mu_x = float(inplane_fixed["Vx"]) / omega_R if omega_R > 1e-9 else 0.0
            else:
                mu_x = base_mu
            Vz = _axial(mu_x * omega_R)

        name = condition_name(overrides, is_propeller)
        conditions.append(FlightCondition(name=name, mu_x=mu_x, collective_deg=collective_deg, Vz=Vz, rpm=rpm))

    return conditions


# =============================================================================
# Batch (reads BatchDefinition and decides which sweep to run)
# =============================================================================

def run_batch(project: Project, batch: BatchDefinition, *,
              on_case_done: Optional[Callable[[int, int, object], None]] = None,
              should_cancel: Optional[Callable[[], bool]] = None,
              trim_mode: Optional[str] = None,
              target_kind: Optional[str] = None,
              target_value: Optional[float] = None) -> list[Results]:
    """If ``batch.conditions`` already comes populated (explicit list, the
    common case coming from the GUI or from a saved ``batch.bemt``),
    runs it directly, IGNORING ``sweep_kind``. Only uses ``sweep_kind`` +
    ``sweep_params`` to generate the conditions when ``conditions`` is
    empty (programmatic use: a script builds a ``BatchDefinition`` with
    just the sweep type and the parameters, without listing condition by
    condition).

    ``on_case_done``/``should_cancel`` (docs/plano_v3.md Part 2): optional,
    passed through to the actual execution path (``_run_conditions``
    directly for an explicit list; each ``run_*_sweep``/
    ``run_factorial_batch`` for the others). Defaulting both to ``None``
    preserves the previous behavior."""
    trim_spec = (batch.sweep_params or {}).get("trim")
    if trim_mode is None and trim_spec:
        trim_mode = trim_spec.get("trim_mode")
        target_kind = trim_spec.get("target_kind")
        target_value = trim_spec.get("target_value")
    trim = trim_mode is not None
    if trim and (target_kind not in _TRIM_TARGET_KINDS or target_value is None):
        raise ValueError("trimmed batch requires trim_mode, target_kind and target_value")
    if batch.conditions:
        if trim:
            runner = lambda c: run_case_trimmed(
                project, c, trim_mode=trim_mode, target_kind=target_kind,
                target_value=target_value, should_cancel=should_cancel)
            return _run_conditions(project, batch.conditions,
                                    on_case_done=on_case_done,
                                    should_cancel=should_cancel, runner=runner)
        return _run_conditions(project, batch.conditions,
                                on_case_done=on_case_done, should_cancel=should_cancel)

    if trim:
        params = dict(batch.sweep_params)
        params.pop("trim", None)
        if batch.sweep_kind == "factorial":
            conditions = build_factorial_conditions(
                project, params.get("axes", []), params.get("fixed"))
        elif batch.sweep_kind == "mu_sweep":
            conditions = [FlightCondition(name=f"mu_{v:g}", mu_x=v,
                                          collective_deg=params.get("collective_deg", 8.0),
                                          Vz=params.get("Vz", 0.0), rpm=params.get("rpm"))
                          for v in params.get("mu_values", [])]
        elif batch.sweep_kind == "alpha_sweep":
            rpm = _require_rpm(params.get("rpm"), "run_batch trimmed alpha sweep")
            rotor = _to_rotor(project.geometry,
                              collective_deg=params.get("collective_deg", 8.0), rpm=rpm)
            mu_x = params.get("mu_x", 0.0)
            Vinf_long = mu_x * rotor.OmegaR
            conditions = [FlightCondition(name=f"alpha_{v:g}", mu_x=mu_x,
                                          collective_deg=params.get("collective_deg", 8.0),
                                          Vz=float(np.tan(np.deg2rad(v)) * Vinf_long), rpm=rpm)
                          for v in params.get("alpha_deg_values", [])]
        elif batch.sweep_kind == "collective_sweep":
            conditions = [FlightCondition(name=f"collective_{v:g}", mu_x=params.get("mu_x", 0.0),
                                          collective_deg=v, Vz=params.get("Vz", 0.0),
                                          rpm=params.get("rpm"))
                          for v in params.get("collective_deg_values", [])]
        else:
            conditions = []
        runner = lambda c: run_case_trimmed(
            project, c, trim_mode=trim_mode, target_kind=target_kind,
            target_value=target_value, should_cancel=should_cancel)
        return _run_conditions(project, conditions, on_case_done=on_case_done,
                                should_cancel=should_cancel, runner=runner)

    kind = batch.sweep_kind
    params = dict(batch.sweep_params)
    if kind == "mu_sweep":
        return run_mu_sweep(project, on_case_done=on_case_done, should_cancel=should_cancel, **params)
    if kind == "alpha_sweep":
        return run_alpha_sweep(project, on_case_done=on_case_done, should_cancel=should_cancel, **params)
    if kind == "collective_sweep":
        return run_collective_sweep(project, on_case_done=on_case_done, should_cancel=should_cancel, **params)
    if kind == "factorial":
        return run_factorial_batch(project, on_case_done=on_case_done, should_cancel=should_cancel, **params)
    if kind == "custom":
        if trim_spec:
            conditions = list(batch.conditions)
            return _run_conditions(project, conditions,
                                   on_case_done=on_case_done,
                                   should_cancel=should_cancel,
                                   runner=lambda c: run_case_trimmed(
                                       project, c, should_cancel=should_cancel,
                                       **trim_spec))
        return []
    raise ValueError(
        f"Unknown sweep_kind: {kind!r}. Options: mu_sweep, alpha_sweep, "
        f"collective_sweep, factorial, custom (or fill batch.conditions directly)."
    )


# =============================================================================
# Comparison between methods (BEMT fixed-point solvers)
# =============================================================================

def benchmark_solvers(project: Project, condition: FlightCondition,
                       solvers: Sequence[str] = _KNOWN_SOLVERS) -> list[Results]:
    """Runs the SAME flight condition with different fixed-point solvers
    (``BEMTConfig.solver``, see ``bemt._SOLVERS``), keeping geometry,
    airfoil, and the rest of the config identical. Used by the "between
    methods" comparison from plan Section 7 (``plots.plot_solver_comparison``).
    Each ``Results`` comes out with ``condition_name`` suffixed by the
    solver name and ``maps['benchmark_solver']``,
    ``maps['benchmark_elapsed']``
    filled in, to distinguish them in export and plot."""
    results = []
    for solver_name in solvers:
        cfg_dict = dict(project.config)
        cfg_dict["solver"] = solver_name
        sub_project = replace(project, config=cfg_dict)
        cond = replace(condition, name=f"{condition.name}_{solver_name}")

        t0 = time.perf_counter()
        res = run_single_case(sub_project, cond)
        res.maps["benchmark_elapsed"] = time.perf_counter() - t0
        res.maps["benchmark_solver"] = solver_name
        results.append(res)
    return results


# =============================================================================
# Design tools: geometry comparison and design optimization
# =============================================================================

_DIRECT_GEOMETRY_PARAMS = ("n_blades", "radius_m", "root_cutout_norm")
_PARAMETRIC_KINDS = ("rectangular", "tapered", "elliptic")
_OPTIMIZATION_METHODS = ("powell", "nelder-mead")


def _blade_planform_metrics(geometry: RotorGeometryDef) -> dict:
    """Classic planform comparison metrics from the radial table.

    With c(x) the chord distribution in units of R over x = r/R, the
    blade integral is I = ∫c dx; the blade aspect ratio (alongamento)
    is AR = 1/I and the rotor solidity is σ = n_blades·I/π. Every
    geometry is a table, so these apply to generated, imported and
    edited blades alike.
    """
    r = np.asarray(geometry.r_norm, dtype=float)
    c = np.asarray(geometry.chord_norm, dtype=float)
    trapezoid = getattr(np, "trapezoid", None)
    integral = float(trapezoid(c, r)) if (trapezoid is not None and r.size >= 2) else 0.0
    aspect = 1.0 / integral if integral > 1e-9 else float("nan")
    return {"aspect_ratio": float(aspect),
            "solidity": float(geometry.n_blades * integral / np.pi)}


def _apply_table_space_planform(geom: RotorGeometryDef,
                                overrides: dict) -> RotorGeometryDef:
    """Applies planform overrides IN TABLE SPACE to a geometry that has
    no parametric generator (origin 'table'/'editor'/'imported').

    Every geometry, however it was born, IS a radial table (r_norm,
    chord_norm, twist_deg) -- generators merely produce that table from
    parameters. So the planform parameters keep meaning here, read as
    targets on the table instead of generator inputs:

    - ``root_chord_norm`` / ``tip_chord_norm``: affine rescale of the
      chord distribution so its endpoints hit the requested values
      (give only one and the other endpoint stays; a linear input stays
      linear);
    - ``twist_root_deg`` / ``twist_tip_deg``: affine shift of the twist
      distribution to the requested endpoint values;
    - ``chord_norm``: uniform scale so the MEAN chord equals the value
      (the rectangular generator's reading);
    - ``max_chord_norm``: uniform scale so the PEAK chord equals the
      value.
    """
    r = np.asarray(geom.r_norm, dtype=float)
    chord = np.asarray(geom.chord_norm, dtype=float)
    twist = np.asarray(geom.twist_deg, dtype=float)
    span = max(float(r[-1] - r[0]), 1e-9)

    if "root_chord_norm" in overrides or "tip_chord_norm" in overrides:
        c_root = float(overrides.get("root_chord_norm", chord[0]))
        c_tip = float(overrides.get("tip_chord_norm", chord[-1]))
        chord = c_root + (c_tip - c_root) * (r - r[0]) / span
    if "chord_norm" in overrides:
        mean = max(float(np.mean(chord)), 1e-12)
        chord = chord * (float(overrides["chord_norm"]) / mean)
    if "max_chord_norm" in overrides:
        peak = max(float(np.max(chord)), 1e-12)
        chord = chord * (float(overrides["max_chord_norm"]) / peak)
    if "twist_root_deg" in overrides or "twist_tip_deg" in overrides:
        t_root = float(overrides.get("twist_root_deg", twist[0]))
        t_tip = float(overrides.get("twist_tip_deg", twist[-1]))
        twist = t_root + (t_tip - t_root) * (r - r[0]) / span
    return replace(geom, chord_norm=chord.tolist(), twist_deg=twist.tolist())


def variant_geometry(base_geometry: RotorGeometryDef,
                     overrides: dict) -> RotorGeometryDef:
    """Build one geometry variant by applying named parameter overrides.

    Planform parameters (``root_chord_norm``, ``tip_chord_norm``,
    ``twist_root_deg``, ``twist_tip_deg``, ``max_chord_norm``,
    ``chord_norm``) are generator inputs for PARAMETRIC origins: they
    regenerate the parametric table from ``origin_params`` and keep the
    station count. For a geometry WITHOUT a generator (origin 'table',
    'editor', an imported blade), the SAME parameters are applied in
    TABLE SPACE instead -- every geometry is a radial table, so the
    parameters are read as targets on that table (endpoint rescale for
    chord/twist, uniform scale for chord_norm/max_chord_norm; see
    `_apply_table_space_planform`). The direct fields ``n_blades``,
    ``radius_m`` and ``root_cutout_norm`` apply to any geometry.
    Unknown parameters raise ``ValueError``.
    """
    unknown = sorted(set(overrides) - set(GEOMETRY_PARAMS))
    if unknown:
        raise ValueError(
            f"Unknown geometry parameter(s): {unknown}. "
            f"Allowed parameters: {list(GEOMETRY_PARAMS)}.")
    planform = {k: v for k, v in overrides.items()
                if k not in _DIRECT_GEOMETRY_PARAMS}
    direct = {k: v for k, v in overrides.items()
              if k in _DIRECT_GEOMETRY_PARAMS}
    kind = str(base_geometry.origin_params.get("kind", ""))
    if planform and kind not in _PARAMETRIC_KINDS:
        geom = _apply_table_space_planform(base_geometry, planform)
    else:
        geom = replace(base_geometry)
    if planform and kind in _PARAMETRIC_KINDS:
        gen_kwargs = dict(base_geometry.origin_params)
        gen_kwargs.update(planform)
        gen_kwargs["n_stations"] = len(base_geometry.r_norm)
        gen_kwargs.setdefault("root_cutout_norm", base_geometry.root_cutout_norm)
        gen_kwargs.setdefault("radius_m", base_geometry.radius_m)
        gen_kwargs.setdefault("n_blades", base_geometry.n_blades)
        gen_kwargs.setdefault("airfoil_name", base_geometry.airfoil_name)
        gen_kwargs.pop("kind")
        builders = {
            "rectangular": geometry_gen.generate_rectangular,
            "tapered": geometry_gen.generate_tapered,
            "elliptic": geometry_gen.generate_elliptic,
        }
        try:
            geom = builders[kind](**gen_kwargs)
        except TypeError as exc:
            raise ValueError(
                f"Parameter(s) {sorted(planform)} are not valid for the "
                f"{kind!r} generator: {exc}") from exc
    if direct:
        geom = replace(geom, **direct)
    return geom


def compare_geometries(project: Project,
                       variants: dict,
                       conditions: Optional[Sequence[FlightCondition]] = None,
                       *,
                       trim: str = "none",
                       on_case_done=None,
                       should_cancel=None) -> list:
    """Run the same flight conditions across several geometries.

    ``variants`` maps a display label to a ``RotorGeometryDef``. Every
    variant runs the same ordered conditions (``conditions`` when given,
    otherwise the project's saved cases, otherwise one default hover-like
    case). Returns a flat ``list[Results]`` in variant order; each summary
    carries ``geometry_label`` so plots, tables and reports can group the
    series. Results stay in memory (AR-2).

    ``trim`` extends the comparison from equal CONTROLS to equal LOADING:
    ``"thrust"`` (or ``"CT"``) holds the absolute thrust (or the
    coefficient) CONSTANT across every variant, which is the fair basis
    for comparing efficiency. The FIRST variant label is the reference:
    it runs every condition untrimmed, and its ``Thrust``/``CT`` at each
    condition becomes the target every other variant must hit.
    ``run_case_trimmed`` supplies the mechanics: bisection over ONE degree
    of freedom, chosen automatically from the project convention --
    ``solve_rpm`` for propellers (fixed-pitch machines throttle with rpm),
    ``solve_collective`` for rotors (rpm governed, collective free). A
    variant whose target lies outside the default bracket raises
    ``ValueError`` naming the variant, the condition and the remedy
    instead of converging outside the plausible interval. Trimmed
    summaries record what was traded: ``trim_target``, ``trim_dof`` and
    ``trim_dof_value``; reference summaries carry ``trim_reference``.
    Trimming multiplies the cost of every non-reference case by the
    bisection iteration count (typically ~10--20 solves).
    """
    if not variants:
        raise ValueError("compare_geometries needs at least one variant.")
    if conditions is None:
        conditions = list(project.saved_cases) or [FlightCondition()]
    conditions = list(conditions)
    if trim != "none" and trim not in _TRIM_TARGET_KINDS:
        raise ValueError(
            f"compare_geometries: trim must be 'none', 'thrust' or 'CT' "
            f"(got {trim!r}).")
    # Fail fast with context instead of letting the first solve die deep
    # inside _require_rpm: every condition here must carry an rpm.
    for condition in conditions:
        _require_rpm(condition.rpm,
                     f"geometry comparison (condition {condition.name!r})")

    summary_key = "Thrust" if trim == "thrust" else "CT"
    labels = list(variants)
    total = len(labels) * len(conditions)
    done = 0

    def _emit(res) -> None:
        nonlocal done
        done += 1
        if on_case_done is not None:
            on_case_done(done, total, res)

    def _tag(res, label: str, condition: FlightCondition) -> None:
        res.summary["geometry_label"] = label
        res.condition_name = condition.name

    # Reference pass: the first label defines, per condition, the
    # thrust/CT every other variant is trimmed to. Its own results ARE
    # the final ones -- they are never re-run.
    base_label = labels[0]
    base_project = replace(project, geometry=variants[base_label])
    targets: dict[int, float] = {}
    trim_mode: Optional[str] = None
    results: list[Results] = []
    for index, condition in enumerate(conditions):
        res = run_single_case(base_project, condition,
                              should_cancel=should_cancel)
        _tag(res, base_label, condition)
        res.summary.update(_blade_planform_metrics(variants[base_label]))
        if trim != "none":
            res.summary["trim_reference"] = True
            targets[index] = float(res.summary[summary_key])
            if trim_mode is None:
                propeller = bool(res.summary.get("cfg_is_propeller"))
                trim_mode = "solve_rpm" if propeller else "solve_collective"
        results.append(res)
        _emit(res)

    for label in labels[1:]:
        variant_project = replace(project, geometry=variants[label])
        for index, condition in enumerate(conditions):
            if trim == "none":
                res = run_single_case(variant_project, condition,
                                      should_cancel=should_cancel)
            else:
                try:
                    res = run_case_trimmed(
                        variant_project, condition,
                        trim_mode=trim_mode, target_kind=trim,
                        target_value=targets[index],
                        should_cancel=should_cancel)
                except ValueError as exc:
                    raise ValueError(
                        f"Geometry comparison trimmed to constant "
                        f"{summary_key}: variant {label!r} at condition "
                        f"{condition.name!r} could not reach the reference "
                        f"{summary_key}={targets[index]!r}. {exc}") from exc
                dof = "rpm" if trim_mode == "solve_rpm" else "collective_deg"
                res.summary["trim_target"] = targets[index]
                res.summary["trim_dof"] = dof
                res.summary["trim_dof_value"] = float(res.summary[dof])
            _tag(res, label, condition)
            res.summary.update(_blade_planform_metrics(variants[label]))
            results.append(res)
            _emit(res)
    return results


def optimize_design(project: Project, definition: OptimizationDefinition,
                    *, on_progress=None, should_cancel=None) -> OptimizationOutcome:
    """Drive bounded geometry parameters toward the best objective value.

    Each evaluation regenerates the geometry through ``variant_geometry``
    and solves ONE flight condition (``definition.condition`` when given,
    otherwise the first saved case). The objective reads a single summary
    key. The search uses ``scipy.optimize.minimize`` with a derivative-free
    method (Powell or Nelder-Mead), started from the center of the bounds;
    it is deterministic for a fixed project and definition. Raises
    ``ValueError`` for an invalid definition and ``SolveCancelled`` when
    ``should_cancel`` fires between evaluations.
    """
    from scipy.optimize import minimize  # local import: optional at engine level

    if definition.objective_kind not in ("maximize", "minimize"):
        raise ValueError(
            f"objective_kind must be 'maximize' or 'minimize' "
            f"(got {definition.objective_kind!r}).")
    if definition.method not in _OPTIMIZATION_METHODS:
        raise ValueError(
            f"method must be one of {_OPTIMIZATION_METHODS} "
            f"(got {definition.method!r}).")
    if definition.max_evals < 5:
        raise ValueError("max_evals must be at least 5.")
    if not definition.variables:
        raise ValueError("The optimization needs at least one variable.")
    names = []
    lower = []
    upper = []
    for var in definition.variables:
        if var.param not in GEOMETRY_PARAMS:
            raise ValueError(
                f"Unknown variable parameter {var.param!r}; "
                f"allowed: {list(GEOMETRY_PARAMS)}.")
        if not (math.isfinite(var.lower) and math.isfinite(var.upper)
                and var.lower < var.upper):
            raise ValueError(
                f"Variable {var.param!r} needs finite bounds with "
                f"lower < upper (got {var.lower}, {var.upper}).")
        names.append(var.param)
        lower.append(float(var.lower))
        upper.append(float(var.upper))

    condition = definition.condition or (
        project.saved_cases[0] if project.saved_cases else FlightCondition())
    rpm = _require_rpm(condition.rpm,
                       f"optimization {definition.name!r} (set rpm on the "
                       f"definition's condition)")
    sign = -1.0 if definition.objective_kind == "maximize" else 1.0
    penalty = 1e6 * abs(sign)

    outcome = OptimizationOutcome(
        objective_key=definition.objective_key,
        objective_kind=definition.objective_kind)
    best_finite = math.inf  # in minimized space
    state = {"evals": 0}

    def evaluate(x) -> float:
        nonlocal best_finite
        params = {}
        for name, value in zip(names, x):
            params[name] = int(round(value)) if name in INTEGER_PARAMS \
                else float(value)
        state["evals"] += 1
        variant = variant_geometry(project.geometry, params)
        sub_project = replace(project, geometry=variant)
        try:
            res = run_single_case(sub_project, condition,
                                  should_cancel=should_cancel)
            raw = float(res.summary.get(definition.objective_key, float("nan")))
        except SolveCancelled:
            raise
        except Exception:
            res = None
            raw = float("nan")
        if not math.isfinite(raw):
            f_value = penalty + state["evals"]
            res = None
        else:
            f_value = sign * raw
            outcome.history.append({"eval": state["evals"], **params,
                                    definition.objective_key: raw})
        if f_value < best_finite:
            best_finite = f_value
            outcome.best_params = dict(params)
            outcome.best_value = raw
            outcome.best_results = res
        if on_progress is not None:
            on_progress(state["evals"], definition.max_evals, outcome.best_value)
        return f_value

    def check_cancel():
        if should_cancel is not None and should_cancel():
            raise SolveCancelled()

    x0 = np.array([0.5 * (lo + hi) for lo, hi in zip(lower, upper)])
    try:
        minimize(evaluate, x0, method="Powell" if definition.method == "powell"
                 else "Nelder-Mead",
                 bounds=list(zip(lower, upper)),
                 callback=lambda _: check_cancel(),
                 options=({"maxfev": definition.max_evals}
                          if definition.method == "powell"
                          else {"maxiter": definition.max_evals}))
        outcome.message = (f"finished after {state['evals']} evaluations")
    except SolveCancelled:
        outcome.message = "cancelled"
    except ValueError as exc:
        # Powell/Nelder-Mead can stop early on degenerate bounds; keep what
        # was evaluated instead of losing the whole study.
        outcome.message = f"stopped early: {exc}"
    outcome.n_evals = state["evals"]
    return outcome
