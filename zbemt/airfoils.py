"""Build and evaluate the aerodynamic models assigned to blade sections.

The module accepts airfoil definitions, profile geometry, polar tables, radial
profiles, local Reynolds and Mach values, and angles of attack. It returns analytical
or tabulated airfoil objects, aerodynamic coefficients, previews, and imported or
exported tables. Public builders and evaluators are consumed by ``models.py``,
``bemt.py``, ``api.py``, and the Airfoil GUI tab. Angles are degrees at file and GUI
boundaries and radians where numerical routines require them. Extrapolated and
semi-empirical models have limited validity outside their calibrated ranges. The
module does not invoke external polar engines implicitly; explicit integrations are
handled by ``external_solvers.py``.
"""

from __future__ import annotations

import warnings
import math
from pathlib import Path
from typing import Optional

import numpy as np
import pandas as pd

from .models import AirfoilDef, PolarSlice, ProfileGeometry, uses_full_range_extension

from .bemt import (
    AnalyticalAirfoil, TableAirfoil, MultiSectionTableAirfoil, ViternaExtendedAirfoil,
    HeterogeneousMultiSectionAirfoil,
)


# =============================================================================
# a) Aerodynamic model
# =============================================================================

#: Reference radial station for the Reynolds/Mach that selects the
#: tabulated polar. r/R=0.75 is the usual convention in rotors (it is
#: where the bulk of the load sits: the annulus area grows with r and so
#: does the velocity, so the contribution per unit radius weighs heaviest
#: around 3/4 of the blade).
REFERENCE_RADIUS_NORM = 0.75


def reference_reynolds_mach(rotor, cfg, mu_x: float = 0.0) -> tuple:
    """REPRESENTATIVE Reynolds and Mach of the blade, to choose which
    tabulated polar to use when the table has a Reynolds and/or Mach axis.

    Returns ``(reynolds, mach)`` evaluated at the ``REFERENCE_RADIUS_NORM``
    station with the tangential velocity ``Omega*r`` added to the advance
    ``mu_x*Omega*R`` -- i.e. the velocity that the reference section sees
    on average over the revolution.

    Use ``radial_reynolds_mach`` when what matters is the whole radial
    profile (that is what the engine uses): Reynolds grows nearly linearly
    with radius, so a single reference station underestimates the tip and
    overestimates the root.
    """
    r_norms, re, mach_arr = radial_reynolds_mach(
        rotor, cfg, mu_x=mu_x, r_norms=np.array([REFERENCE_RADIUS_NORM]))
    if re is None:
        return None, None
    return float(re[0]), (float(mach_arr[0]) if mach_arr is not None else None)


#: Number of radial stations used to sample Re/Mach when building the
#: table. Does not need to match `cfg.Ne`: `MultiSectionTableAirfoil`
#: interpolates over r_norm, so it just needs enough resolution to
#: capture the slice changes along the radius.
RADIAL_SAMPLES_FOR_TABLE = 24


def radial_reynolds_mach(rotor, cfg, mu_x: float = 0.0, r_norms=None) -> tuple:
    """RADIAL profile of Reynolds and Mach along the blade.

    Returns ``(r_norms, reynolds, mach)`` as arrays, evaluated with the
    tangential velocity ``Omega*r*R`` added to the advance ``mu_x*Omega*R``
    -- the velocity that each section sees on average over the revolution
    -- and with the dimensional chord of that section:

        Re(r) = U(r) * c(r) / nu_air        Mach(r) = U(r) / a_sound

    Why per section and not a single value for the whole blade: ``U`` and
    ``c`` vary with radius, so the tip Reynolds can reach an order of
    magnitude higher than the root's. A single polar chosen from an
    average Re misses at both ends of the range -- and the root is
    exactly where low Reynolds changes Cd the most.

    Remaining LIMITATION: this is one value per RADIAL SECTION, not per
    element (r, psi). The azimuthal variation of ``U`` (±mu_x in advance)
    does not enter the slice choice, because the airfoil object is built
    once per solve, before a solution exists; and the exact local
    Reynolds depends on the converged induced velocity -- a circular
    dependency. The radial component, which is the dominant one, is
    handled.
    """
    omega_R = float(rotor.OmegaR)
    if omega_R <= 1e-9:
        return None, None, None

    if r_norms is None:
        r_norms = np.linspace(float(rotor.r_root_norm_geom), float(rotor.r_tip_norm_geom),
                              RADIAL_SAMPLES_FOR_TABLE)
    r_norms = np.asarray(r_norms, dtype=float)

    # average velocity seen by each section over one revolution:
    # tangential (Omega*r) plus the advance (mu_x*Omega*R)
    U = omega_R * (r_norms + abs(float(mu_x)))

    chord = np.interp(r_norms, np.asarray(rotor.r_geom, dtype=float),
                      np.asarray(rotor.chord_geom, dtype=float))

    nu_air = float(getattr(cfg, "nu_air", 1.46e-5))
    reynolds = U * chord / nu_air if nu_air > 0 else None

    a_sound = float(getattr(cfg, "a_sound", 340.294))
    mach = U / a_sound if a_sound > 0 else None

    return r_norms, reynolds, mach


#: Radial stations used by `suggest_reynolds_mach_lists` to BRACKET the
#: operating point: useful root, reference (3/4) and tip. Not an
#: aesthetic choice -- Re and Mach grow monotonically with radius, so
#: these three stations are exactly the minimum, the representative
#: value, and the maximum of the envelope the blade sees.
SUGGESTION_STATIONS = (0.4, REFERENCE_RADIUS_NORM, 1.0)


def _arredondar_para_2_sig(v: float) -> float:
    """Rounds to 2 significant figures -- a suggestion is an ESTIMATE,
    and '1.9e5' communicates that better than '187342.7'."""
    if not math.isfinite(v) or v == 0.0:
        return 0.0
    expoente = math.floor(math.log10(abs(v)))
    fator = 10.0 ** (expoente - 1)
    return round(v / fator) * fator


def suggest_reynolds_mach_lists(geometry_def, rpm: float, nu_air: float = 1.46e-5,
                                 a_sound: float = 340.294,
                                 stations=SUGGESTION_STATIONS,
                                 mu_x: float = 0.0) -> dict:
    """CLOSED-FORM suggestion (without running the engine) of Reynolds and
    Mach lists to sweep with an external polar generator (NeuralFoil).

    The calculation is the same as `radial_reynolds_mach`, only from the
    raw table (`RotorGeometryDef`) and an RPM, without building a `Rotor`
    or `BEMTConfig`:

        U(r) = (rpm·2π/60)·R·(r/R + |mu_x|)   Re(r) = U·c(r)/ν   M(r) = U/a

    evaluated at the three stations of `stations` (useful root / 3/4 /
    tip), which makes the list BRACKET the operating point instead of
    pinning a single one. Returns ``{"reynolds": [...], "mach": [...]}``
    with sorted, unique values rounded to 2 significant figures. Returns
    empty lists when there is no geometry or the RPM is zero -- does not
    raise: it is a suggestion, and its absence must not prevent the GUI
    from opening.

    ``mu_x``: advance ratio of the reference condition. Enters through
    the same ``+|mu_x|`` term as `radial_reynolds_mach` -- it is the
    average velocity the section sees over a revolution, not just the
    tangential one. Without it the suggestion was the same in hover and
    at mu_x=0.4, where the advancing blade sees 40% more velocity (and
    therefore more Reynolds and Mach): the suggested list underestimated
    the envelope exactly in the condition where compressibility starts
    to matter."""
    if geometry_def is None or rpm is None:
        return {"reynolds": [], "mach": []}
    r_tab = [float(v) for v in getattr(geometry_def, "r_norm", []) or []]
    c_tab = [float(v) for v in getattr(geometry_def, "chord_norm", []) or []]
    radius_m = float(getattr(geometry_def, "radius_m", 0.0) or 0.0)
    omega = float(rpm) * 2.0 * math.pi / 60.0
    if len(r_tab) < 2 or len(c_tab) != len(r_tab) or radius_m <= 0 or omega <= 0:
        return {"reynolds": [], "mach": []}

    ordem = np.argsort(np.asarray(r_tab))
    r_arr = np.asarray(r_tab)[ordem]
    c_arr = np.asarray(c_tab)[ordem]

    reynolds: list[float] = []
    mach: list[float] = []
    avanco = abs(float(mu_x or 0.0))
    for r_norm in stations:
        U = omega * radius_m * (float(r_norm) + avanco)
        chord = float(np.interp(r_norm, r_arr, c_arr)) * radius_m
        if nu_air > 0:
            reynolds.append(_arredondar_para_2_sig(U * chord / nu_air))
        if a_sound > 0:
            mach.append(round(U / a_sound, 2))
    # We do not remove repeated values after rounding: the GUI promises
    # three operating points (useful root, reference and tip), even when
    # two stations land on the same displayed number in a low-velocity
    # condition. The physical position is still represented by the list
    # order.
    return {
        "reynolds": sorted(v for v in reynolds if v > 0),
        "mach": sorted(v for v in mach if v >= 0),
    }


def build_analytical(airfoil_def: AirfoilDef) -> AnalyticalAirfoil:
    """Builds the analytical model (linear/clip/enhanced) from the
    AirfoilDef parameters. Does not look at `table_slices`.

    `stall_model='viterna'` does not exist as an engine model in
    `bemt.AnalyticalAirfoil` (which only knows linear/clip/enhanced) -- it
    is an `AirfoilDef`-only option, resolved here to the 'linear' base
    curve (no clamp, keeps rising past stall -- see
    `bemt.ViternaExtendedAirfoil`), which is later wrapped by the
    Viterna-Corrigan extension in `to_airfoil()` via
    `models.uses_full_range_extension`.
    """
    engine_stall_model = "linear" if airfoil_def.stall_model == "viterna" else airfoil_def.stall_model
    return AnalyticalAirfoil(
        cl_alpha=airfoil_def.cl_alpha,
        alpha0_deg=airfoil_def.alpha0_deg,
        cd0=airfoil_def.cd0,
        k=airfoil_def.k,
        alpha_stall_pos_deg=airfoil_def.alpha_stall_pos_deg,
        alpha_stall_neg_deg=airfoil_def.alpha_stall_neg_deg,
        stall_model=engine_stall_model,
    )


def _slices_axes(slices: list[PolarSlice]) -> dict:
    """Detects which extra axes (besides alpha) are present in the list of
    PolarSlice: r_norm (multi-section) and/or reynolds/mach. Reynolds and
    Mach still have no dedicated solver in bemt.py; when present, the
    slice closest to the requested condition is chosen when building the
    TableAirfoil (see `_select_slice_for_condition`), and the axis is
    recorded here only so the GUI can show the user what was detected."""
    has_r = any(s.r_norm is not None for s in slices)
    has_re = any(s.reynolds is not None for s in slices)
    has_mach = any(s.mach is not None for s in slices)
    return {"r_norm": has_r, "reynolds": has_re, "mach": has_mach}


def build_table(airfoil_def: AirfoilDef, reynolds: Optional[float] = None,
                 mach: Optional[float] = None, radial: Optional[tuple] = None):
    """Builds a TableAirfoil (single polar) or MultiSectionTableAirfoil
    (several radial sections) from `airfoil_def.table_slices`.

    When the table has a Reynolds and/or Mach axis, the slice used is the
    one closest to the requested condition (`_select_slice_for_condition`).
    Real interpolation BETWEEN Reynolds/Mach slices remains future work;
    today it is nearest neighbour.

    There are two ways to inform the condition:

    - ``radial=(r_norms, reynolds_array, mach_array)`` -- PREFERRED, and
      what the engine uses. Each radial station picks ITS OWN slice, with
      the Reynolds and Mach of that section (see `radial_reynolds_mach`).
      Since Re grows nearly linearly with radius, root and tip end up on
      different polars, which is the physically correct behaviour.
    - scalar ``reynolds``/``mach`` -- a single pair for the whole blade.
      Used by the GUI preview and by anyone who just wants one
      representative polar.

    WARNING: if nothing is informed, EVERY slice scores 0.0 on the
    proximity criterion and the FIRST one is returned -- the table's
    extra axes get silently ignored. It was exactly this omission in
    `to_blade_airfoil` that made an N Re x M Mach NeuralFoil sweep
    collapse into a single polar.
    """
    slices = airfoil_def.table_slices
    if not slices:
        raise ValueError(f"AirfoilDef '{airfoil_def.name}' has no table_slices to build table.")

    axes = _slices_axes(slices)
    has_extra_axis = axes["reynolds"] or axes["mach"]
    radial_ok = radial is not None and radial[0] is not None

    if not axes["r_norm"]:
        # Table without its own radial axis. If it varies with Re/Mach
        # and we have the condition's radial profile, each station picks
        # its own slice and the result becomes multi-section -- the
        # radial variation of Reynolds starts to show up in Cl/Cd,
        # instead of a single polar for the whole blade.
        if has_extra_axis and radial_ok:
            sections = _sections_from_radial_profile(slices, radial)
            if len(sections) > 1:
                return MultiSectionTableAirfoil(sections)
            # a single slice covers the whole radius: nothing to interpolate
            s = _select_slice_for_condition(slices, *_radial_midpoint(radial))
            return TableAirfoil(s.alpha_deg, s.cl, s.cd)

        s = _select_slice_for_condition(slices, reynolds, mach)
        return TableAirfoil(s.alpha_deg, s.cl, s.cd)

    # Table WITH its own radial axis: the sections are the user's. For
    # each one, choose among the candidates at that r_norm using the
    # Re/Mach of that radial position (not a global value).
    r_norms = sorted({s.r_norm for s in slices if s.r_norm is not None})
    sections = {}
    for r in r_norms:
        candidates = [s for s in slices if s.r_norm == r]
        if radial_ok:
            re_r, mach_r = _interp_radial(radial, r)
        else:
            re_r, mach_r = reynolds, mach
        s = _select_slice_for_condition(candidates, re_r, mach_r)
        sections[r] = (s.alpha_deg, s.cl, s.cd)
    return MultiSectionTableAirfoil(sections)


def _interp_radial(radial: tuple, r_norm: float) -> tuple:
    """(Re, Mach) of the radial profile at position `r_norm`."""
    r_norms, re, mach = radial
    re_r = float(np.interp(r_norm, r_norms, re)) if re is not None else None
    mach_r = float(np.interp(r_norm, r_norms, mach)) if mach is not None else None
    return re_r, mach_r


def _radial_midpoint(radial: tuple) -> tuple:
    return _interp_radial(radial, REFERENCE_RADIUS_NORM)


def _sections_from_radial_profile(slices: list[PolarSlice], radial: tuple) -> dict:
    """Maps each radial station to the slice closest to that station's
    (Re, Mach).

    Only emits a section when the chosen slice CHANGES along the radius
    (plus the edges), instead of one per sampled station: the
    `MultiSectionTableAirfoil` interpolates between the sections it
    receives, and repeating the same polar at neighbouring stations adds
    no information -- only assembly cost."""
    r_norms = radial[0]
    sections: dict = {}
    anterior = None
    for i, r in enumerate(r_norms):
        re_r, mach_r = _interp_radial(radial, float(r))
        s = _select_slice_for_condition(slices, re_r, mach_r)
        if s is not anterior or i in (0, len(r_norms) - 1):
            sections[float(r)] = (s.alpha_deg, s.cl, s.cd)
            anterior = s
    return sections


def _select_slice_for_condition(slices: list[PolarSlice], reynolds: Optional[float],
                                 mach: Optional[float]) -> PolarSlice:
    if len(slices) == 1:
        return slices[0]

    def score(s: PolarSlice) -> float:
        d = 0.0
        if reynolds is not None and s.reynolds is not None:
            d += abs(s.reynolds - reynolds) / max(reynolds, 1.0)
        if mach is not None and s.mach is not None:
            d += abs(s.mach - mach)
        return d

    return min(slices, key=score)


def apply_viterna_extension(base_airfoil, airfoil_def: AirfoilDef) -> ViternaExtendedAirfoil:
    """Used for `source='analytical'` (or 'external'): there is no real
    table from which to detect CLmax/CLmin, so the stall angles come from
    `airfoil_def.alpha_stall_pos_deg/neg_deg` (the transition to Viterna
    is still smoothed by `viterna_blend_width_deg` -- see
    `bemt.ViternaExtendedAirfoil` -- only anchored on these informed
    angles, instead of detected ones)."""
    return ViternaExtendedAirfoil(
        base_airfoil,
        alpha_stall_pos_deg=airfoil_def.alpha_stall_pos_deg,
        alpha_stall_neg_deg=airfoil_def.alpha_stall_neg_deg,
        blend_width_deg=airfoil_def.viterna_blend_width_deg,
    )


def blend_table_with_viterna(table_airfoil, airfoil_def: AirfoilDef) -> ViternaExtendedAirfoil:
    """'Blend' = real table preserved ENTIRELY across its whole range
    (never overwritten) + Viterna-Corrigan smoothly fitted only beyond
    the last real data point on each side. CLmax/CLmin and the
    corresponding stall angles are detected automatically from the table
    itself (`alpha_stall_pos_deg=None, alpha_stall_neg_deg=None` forces
    the auto-detection mode in `ViternaExtendedAirfoil` -- see its
    docstring); the analytical fields `airfoil_def.alpha_stall_pos_deg/
    neg_deg` are deliberately NOT used here, since they make no sense
    for a real table (they only apply to `source='analytical'`, in
    `apply_viterna_extension`)."""
    return ViternaExtendedAirfoil(
        table_airfoil,
        alpha_stall_pos_deg=None,
        alpha_stall_neg_deg=None,
        blend_width_deg=airfoil_def.viterna_blend_width_deg,
    )


def _attach_dynamic_stall_params(airfoil, airfoil_def: AirfoilDef):
    """Attaches the dynamic-stall (Oye) parameters from the `AirfoilDef`
    as an attribute of the already-built engine object
    (`airfoil.dynamic_stall_params`).

    See docs/plano_v2.md Section 2.4/6.3 (Finding #1): this is the ONLY
    copy of these parameters -- `bemt.py` (`solve_bemt`/
    `apply_dynamic_stall`) reads from here when present, and only falls
    back to the like-named fields of `BEMTConfig` for backward
    compatibility with scripts that build `BEMTConfig` by hand without
    going through `to_airfoil`."""
    airfoil.dynamic_stall_params = {
        "use_dynamic_stall": airfoil_def.use_dynamic_stall,
        "method": airfoil_def.dynamic_stall_method,
        "A": airfoil_def.dynamic_stall_A,
        "fade_start_deg": airfoil_def.dynamic_stall_fade_start_deg,
        "fade_end_deg": airfoil_def.dynamic_stall_fade_end_deg,
        "time_march_revolutions": airfoil_def.dynamic_stall_time_march_revolutions,
        "time_march_avg_last": airfoil_def.dynamic_stall_time_march_avg_last,
    }
    return airfoil


def to_airfoil(airfoil_def: AirfoilDef, reynolds: Optional[float] = None,
                mach: Optional[float] = None, radial: Optional[tuple] = None):
    """Single bridge function: AirfoilDef -> object ready for bemt.py.

    Decides on its own, from `source`/`extend_full_range`, which
    combination of engine classes to instantiate -- "extend" (analytical)
    vs "paste/blend" (table) is derived from `source`, no longer a
    separate user choice (docs/plano_v2.md Section 2.4/Finding #3). Also
    attaches `dynamic_stall_params` to the returned object (Finding #1).
    """
    if airfoil_def.source == "analytical":
        base = build_analytical(airfoil_def)
    elif airfoil_def.source == "table":
        base = build_table(airfoil_def, reynolds=reynolds, mach=mach, radial=radial)
    elif airfoil_def.source == "external":
        raise NotImplementedError(
            "AirfoilDef.source='external' depends on external_solvers.run_polar(), "
            "not yet implemented (future scope). Run external polar generation "
            "first and import the result via table_slices."
        )
    else:
        raise ValueError(f"Unknown AirfoilDef.source: {airfoil_def.source!r}")

    if uses_full_range_extension(airfoil_def):
        if airfoil_def.source == "table":
            result = blend_table_with_viterna(base, airfoil_def)
        else:
            result = apply_viterna_extension(base, airfoil_def)
    else:
        result = base

    return _attach_dynamic_stall_params(result, airfoil_def)


#: Dynamic-stall parameters that belong to the BLADE, not the section:
#: the engine marches once per solve, so method and number of
#: revolutions apply to the whole blade. A, the fade angles and the
#: on/off switch remain per section (`dynamic_stall_section_field`).
_PARAMS_DE_PA = ("dynamic_stall_method", "dynamic_stall_time_march_revolutions",
                 "dynamic_stall_time_march_avg_last")


def _dynamic_stall_params_da_pa(ordered_defs: list) -> dict:
    """Resolves the blade's global dynamic-stall parameters.

    It used to always read ``ordered_defs[0]`` and hard-code
    ``method="frequency"``: a blade whose root does not use dynamic
    stall would hand back that root's parameters, and a project asking
    for ``time_march`` on every section got ``frequency`` with no
    warning. Now what counts is what the sections that actually TURN ON
    dynamic stall say; if they disagree among themselves, the first one
    wins and the conflict is warned about (the engine only knows how to
    march one way)."""
    ligadas = [d for d in ordered_defs if d.use_dynamic_stall]
    if not ligadas:
        return {"use_dynamic_stall": False, "method": "frequency",
                "time_march_revolutions": ordered_defs[0].dynamic_stall_time_march_revolutions,
                "time_march_avg_last": ordered_defs[0].dynamic_stall_time_march_avg_last}

    escolhida = ligadas[0]
    for campo in _PARAMS_DE_PA:
        valores = {getattr(d, campo) for d in ligadas}
        if len(valores) > 1:
            warnings.warn(
                f"to_blade_airfoil: sections with dynamic stall enabled disagree "
                f"on '{campo}' ({sorted(map(str, valores))}). This parameter is "
                f"PÁ, não da seção -- o motor marcha uma vez por solve. Valendo: "
                f"{getattr(escolhida, campo)!r} (seção {escolhida.name or 'r_norm='}"
                f"{escolhida.r_norm}).", UserWarning, stacklevel=3)
    return {
        "use_dynamic_stall": True,
        "method": escolhida.dynamic_stall_method,
        "time_march_revolutions": escolhida.dynamic_stall_time_march_revolutions,
        "time_march_avg_last": escolhida.dynamic_stall_time_march_avg_last,
    }


def to_blade_airfoil(airfoil_defs: list, reynolds: Optional[float] = None,
                      mach: Optional[float] = None, radial: Optional[tuple] = None):
    """Sister bridge function to ``to_airfoil()``, for the WHOLE BLADE
    instead of a single ``AirfoilDef`` (docs/plano.md Section 4, Phase D
    -- multi-section airfoil).

    ``reynolds``/``mach`` are the REFERENCE pair of the flight condition
    (see ``reference_reynolds_mach``), passed on to each ``to_airfoil()``
    so that tables with a Reynolds/Mach axis pick the right slice.
    Without them, ``_select_slice_for_condition`` ties everything at 0.0
    and always returns the first slice -- the table's extra axes would
    be silently ignored by the engine.

    - ``airfoil_defs`` with 0 or 1 element: delegates to the usual
      ``to_airfoil()`` (the single element, or a default ``AirfoilDef()``
      if empty) -- the old path, no change in behaviour or return type.
    - ``airfoil_defs`` with 2+ elements (ALL needing ``r_norm`` defined):
      builds, for EACH section, the "normal" airfoil via
      ``to_airfoil(section_def)`` -- each one free to be analytical,
      tabulated, etc., freely mixed -- and wraps the result in a
      ``bemt.HeterogeneousMultiSectionAirfoil``, which interpolates the
      RESULTING Cl/Cd by r_norm (not each section's input parameters).

    Dynamic stall (Oye) IS applied section by section on the composite
    object: each section turns its own dynamic stall on/off and
    parametrizes it (A, fade window) --
    ``composite.dynamic_stall_section_field`` carries these arrays by
    r_norm, read by
    ``bemt.apply_dynamic_stall``/``_dynamic_stall_section_param``. A
    section with ``use_dynamic_stall=False`` simply does not receive
    the correction (it stays on the pure static polar there); the
    sections do not all need to agree.
    """
    defs = list(airfoil_defs) if airfoil_defs else []
    if len(defs) <= 1:
        single = defs[0] if defs else AirfoilDef()
        return to_airfoil(single, reynolds=reynolds, mach=mach, radial=radial)

    ordered_defs = sorted(defs, key=lambda d: d.r_norm if d.r_norm is not None else 0.0)
    sections = []
    for section_def in ordered_defs:
        if section_def.r_norm is None:
            raise ValueError(
                "to_blade_airfoil: with 2+ sections, ALL must have r_norm defined "
                f"(section {section_def.name!r} has r_norm=None).")
        af = to_airfoil(section_def, reynolds=reynolds, mach=mach, radial=radial)
        sections.append((float(section_def.r_norm), af))

    composite = HeterogeneousMultiSectionAirfoil(sections)
    composite.dynamic_stall_params = _dynamic_stall_params_da_pa(ordered_defs)
    composite.dynamic_stall_section_field = {
        "r_norms": np.array([float(d.r_norm) for d in ordered_defs]),
        "enabled": np.array([1.0 if d.use_dynamic_stall else 0.0 for d in ordered_defs]),
        "A": np.array([d.dynamic_stall_A for d in ordered_defs], dtype=float),
        "fade_start_deg": np.array([d.dynamic_stall_fade_start_deg for d in ordered_defs], dtype=float),
        "fade_end_deg": np.array([d.dynamic_stall_fade_end_deg for d in ordered_defs], dtype=float),
    }
    return composite


def preview_polar(airfoil_def: AirfoilDef, alpha_deg_range=(-30, 30, 1.0),
                   reynolds: Optional[float] = None, mach: Optional[float] = None,
                   use_compressibility: bool = False,
                   config: Optional[dict] = None, reverse: bool = False):
    """Returns (alpha_deg, Cl, Cd) for the preview plot in the Airfoil tab,
    without needing to run the BEMT. Used directly by the GUI (a preview
    operation, does not go through api.py — see docs/plano.md Section 8,
    final note).

    When ``use_compressibility=True`` and ``mach`` is not None, applies
    the Prandtl-Glauert correction (Cl /= β, Cd /= β, β = sqrt(1−M²))
    identically to what ``bemt.py`` does in ``element_state`` — so the
    preview reflects the real compressibility effect visible on the
    polar. (For source='table', the correction is applied to the raw
    tabulated polar -- the table must NOT already have been corrected,
    since bemt.py also corrects it on the fly.)

    ``config`` (the ``project.config`` dict) turns on the REVERSE FLOW
    model -- calling the SAME two functions that `element_state` uses,
    not a reimplementation. There are two because the five models act in
    two places: `bemt.reverse_flow_alpha_eff` decides AT WHICH ANGLE the
    polar is queried (`viterna_full_range`, `alpha_blending`) and
    `bemt.apply_reverse_flow_to_polar` post-processes the returned Cl/Cd
    (`flat_plate`, `simple_flip`, `thin_plate_blend`). Calling only the
    second one -- which was the previous state -- the first two models
    changed NOTHING in the plot even though they changed what the engine
    computed.

    ``reverse=True`` draws the reverse-flow branch (Ut<0) instead of the
    direct one. Two readings to know:

    * for `thin_plate_blend` the two branches coincide (its blend is a
      function of |alpha| only, see that function's docstring) -- that is
      the model's design, not a preview defect;
    * `alpha_blending` is drawn at the SATURATED LIMIT of the reverse
      region (`bemt.UT_NORMALIZADO_DE_PREVIA`): its factor depends on Ut,
      and a polar, being a function of alpha alone, has no way to show
      the continuous transition right at the Ut=0 edge."""
    from .bemt import BEMTConfig, apply_reverse_flow_to_polar, reverse_flow_alpha_eff

    lo, hi, step = alpha_deg_range
    alpha_deg = np.arange(lo, hi + step / 2, step)
    alpha_rad = np.deg2rad(alpha_deg)
    af = to_airfoil(airfoil_def, reynolds=reynolds, mach=mach)
    mach_arr = np.full_like(alpha_rad, mach) if mach is not None else None

    cfg = None
    alpha_consulta = alpha_rad
    mascara_reversa = np.full(alpha_rad.shape, bool(reverse))
    if config is not None:
        from .studies import _build_config
        cfg = _build_config(config)
        alpha_consulta = np.asarray(
            reverse_flow_alpha_eff(alpha_rad, mascara_reversa, cfg), dtype=float)

    cl, cd = af.cl_cd(alpha_consulta, mach_arr)
    cl = np.asarray(cl, dtype=float)
    cd = np.asarray(cd, dtype=float)

    if cfg is not None:
        cl, cd = apply_reverse_flow_to_polar(cl, cd, alpha_rad, mascara_reversa, cfg)
        cl = np.asarray(cl, dtype=float)
        cd = np.asarray(cd, dtype=float)

    if use_compressibility and mach is not None and mach > 0.0:
        beta = float(np.sqrt(max(0.0, 1.0 - mach ** 2)))
        if beta > 1e-3:
            cl = cl / beta
            cd = cd / beta
    return alpha_deg, cl, cd


def unique_conditions(airfoil_def: AirfoilDef) -> list[dict]:
    """Returns the unique combinations of (r_norm, reynolds, mach, label)
    present in ``table_slices``, for the GUI to offer as overlay options
    in the Airfoil tab's polar preview (block 'd'). Empty list if
    ``source != 'table'`` or if no slices were imported."""
    if airfoil_def.source != "table":
        return []
    seen: list[dict] = []
    for s in airfoil_def.table_slices:
        key = {"r_norm": s.r_norm, "reynolds": s.reynolds, "mach": s.mach, "label": s.label}
        if key not in seen:
            seen.append(key)
    return seen


def axis_values(airfoil_def: AirfoilDef) -> dict:
    """Returns, for r_norm/reynolds/mach, the sorted list of distinct
    values present in `table_slices` -- used by the embedded canvas of
    the Airfoil tab (plano_v3.md Part 5) to decide which navigation
    controls to draw (progressive disclosure: an axis with <2 values
    generates no control) and to populate each one. Empty
    (`source != 'table'` or no slices) returns empty lists on every
    axis."""
    slices = airfoil_def.table_slices if airfoil_def.source == "table" else []
    return {
        axis: sorted({getattr(s, axis) for s in slices if getattr(s, axis) is not None})
        for axis in ("r_norm", "reynolds", "mach")
    }


def slice_table_at(airfoil_def: AirfoilDef, r_norm: Optional[float] = None,
                    reynolds: Optional[float] = None, mach: Optional[float] = None) -> PolarSlice:
    """Looks up the nearest polar on the fixed axes (nearest-neighbor per
    axis present in the table). Reuses the same selection logic actually
    used by the engine (`build_table`/`_select_slice_for_condition`), so
    the embedded canvas preview (plano_v3.md Part 5) is faithful to what
    BEMT actually consumes. An omitted axis (`None`) when the table DOES
    HAVE that axis falls back to the first available value (sorted), so
    it always returns a deterministic slice."""
    slices = airfoil_def.table_slices
    if not slices:
        raise ValueError(f"AirfoilDef '{airfoil_def.name}' has no table_slices.")

    candidates = slices
    r_values = sorted({s.r_norm for s in slices if s.r_norm is not None})
    if r_values:
        target_r = r_norm if r_norm is not None else r_values[0]
        nearest_r = min(r_values, key=lambda r: abs(r - target_r))
        candidates = [s for s in slices if s.r_norm == nearest_r]

    return _select_slice_for_condition(candidates, reynolds, mach)


def condition_label(cond: dict) -> str:
    """Legend label for ONE tabulated condition.

    The condition's (Re, Mach, r/R) ALWAYS comes first, and the slice's
    ``label`` (when it exists) sits in parentheses as the source
    identity. Previously, a non-empty ``label`` was returned alone and
    won over everything -- and slices generated by NeuralFoil share a
    single label ("neuralfoil:naca4 2412", built from the GEOMETRY, which
    is the same for all of them), so a whole Re×Mach sweep went to the
    plot with N curves sharing the same legend, with no way to tell which
    was which."""
    parts = []
    if cond.get("r_norm") is not None:
        parts.append(f"r/R={cond['r_norm']:.2f}")
    if cond.get("reynolds") is not None:
        parts.append(f"Re={cond['reynolds']:.3g}")
    if cond.get("mach") is not None:
        parts.append(f"M={cond['mach']:.2f}")
    condicao = ", ".join(parts)
    label = cond.get("label") or ""
    if condicao and label:
        return f"{condicao} ({label})"
    return condicao or label or "polar única"


#: Historical alias: the function was private before the GUI needed to
#: build the same label for the "selected" curve of the embedded canvas
#: (item 32).
_condition_label = condition_label


def preview_polar_multi(airfoil_def: AirfoilDef, conditions: Optional[list[dict]] = None,
                          mach_compare: Optional[list[float]] = None,
                          alpha_deg_range=(-30, 30, 1.0),
                          use_compressibility: bool = False) -> list[dict]:
    """Returns a list of curves ``{label, alpha_deg, cl, cd}`` for overlay
    in the Airfoil tab preview (Cl(alpha)/Cd(alpha) as a function of
    Reynolds and/or Mach — see docs/plano.md Section 8.3-d).

    - If ``airfoil_def.source == 'table'`` and ``conditions`` is given
      (one or more entries from ``unique_conditions``), returns one curve
      per condition, using the polar closest to that (Re, Mach) —
      exactly the same selection logic used in ``to_airfoil`` when
      actually running the BEMT, so the preview is faithful to what will
      be used.
    - Otherwise (analytical source, or table without an explicit
      selection): if ``mach_compare`` is given, returns one curve per
      Mach value (when ``use_compressibility=True``, applies
      Prandtl-Glauert to each curve, reflecting the real effect the way
      the BEMT would). Otherwise, returns a single curve with the current
      model.
    """
    curves: list[dict] = []

    if airfoil_def.source == "table" and conditions:
        for cond in conditions:
            alpha, cl, cd = preview_polar(airfoil_def, alpha_deg_range,
                                           reynolds=cond.get("reynolds"), mach=cond.get("mach"),
                                           use_compressibility=use_compressibility)
            curves.append({"label": _condition_label(cond), "alpha_deg": alpha, "cl": cl, "cd": cd})
        return curves

    if mach_compare:
        for m in mach_compare:
            alpha, cl, cd = preview_polar(airfoil_def, alpha_deg_range, mach=m,
                                          use_compressibility=use_compressibility)
            label = f"M={m:.2f}"
            if use_compressibility and m > 0:
                label += " (P-G)"
            curves.append({"label": label, "alpha_deg": alpha, "cl": cl, "cd": cd})
        return curves

    alpha, cl, cd = preview_polar(airfoil_def, alpha_deg_range,
                                   use_compressibility=use_compressibility)
    curves.append({"label": airfoil_def.name or "modelo atual", "alpha_deg": alpha, "cl": cl, "cd": cd})
    return curves


# =============================================================================
# Import / export of tabulated polar (CSV)
# =============================================================================

_COLUMN_ALIASES = {
    "alpha_deg": ["alpha_deg", "alpha", "aoa", "aoa_deg"],
    "cl": ["cl", "Cl", "CL"],
    "cd": ["cd", "Cd", "CD"],
    "r_norm": ["r_norm", "r/R", "rR", "radial_station"],
    "reynolds": ["reynolds", "Re", "re"],
    "mach": ["mach", "Mach", "M"],
}


def _match_column(df_columns, key: str) -> Optional[str]:
    cols_lower = {c.lower(): c for c in df_columns}
    for alias in _COLUMN_ALIASES[key]:
        if alias.lower() in cols_lower:
            return cols_lower[alias.lower()]
    return None


def detect_csv_axes(path: str) -> dict:
    """Reads only the header and returns which columns were recognized,
    for the GUI to display before confirming the import (and to allow
    manual remapping if the names do not match any known alias)."""
    df = pd.read_csv(path, nrows=5)
    return {key: _match_column(df.columns, key) for key in _COLUMN_ALIASES}


def import_polar_csv(path: str, column_map: Optional[dict] = None) -> list[PolarSlice]:
    """Imports a polar CSV, automatically detecting which axes (r_norm,
    reynolds, mach) are present, and returns a list of `PolarSlice` — one
    per unique combination of (r_norm, reynolds, mach) found in the file.
    `column_map`, if given, overrides the automatic detection
    (e.g.: {"alpha_deg": "AOA[deg]"})."""
    df = pd.read_csv(path)
    cols = dict((k, _match_column(df.columns, k)) for k in _COLUMN_ALIASES)
    if column_map:
        cols.update(column_map)

    for required in ("alpha_deg", "cl", "cd"):
        if cols[required] is None:
            raise ValueError(
                f"Could not identify column for '{required}' in {path}. "
                f"Available columns: {list(df.columns)}. Provide column_map explicitly."
            )

    group_keys = [cols[k] for k in ("r_norm", "reynolds", "mach") if cols[k] is not None]

    slices = []
    if group_keys:
        # dropna=False is essential here: `export_polar_csv` always writes
        # the r_norm/reynolds/mach columns (even when None -> NaN in the
        # CSV), and pandas' DEFAULT behavior is to drop groups whose key
        # has NaN -- without this, re-importing a CSV exported by this
        # very platform silently returned 0 slices whenever
        # reynolds/mach were not used (bug caught by the export->import
        # roundtrip test in tests/test_airfoils.py).
        for key_values, group in df.groupby(group_keys, dropna=False):
            if not isinstance(key_values, tuple):
                key_values = (key_values,)
            kv = dict(zip(group_keys, key_values))

            def _val(col):
                if col not in kv:
                    return None
                v = kv[col]
                return None if pd.isna(v) else float(v)

            slices.append(PolarSlice(
                alpha_deg=group[cols["alpha_deg"]].tolist(),
                cl=group[cols["cl"]].tolist(),
                cd=group[cols["cd"]].tolist(),
                r_norm=_val(cols["r_norm"]),
                reynolds=_val(cols["reynolds"]),
                mach=_val(cols["mach"]),
                label=Path(path).stem,
            ))
    else:
        slices.append(PolarSlice(
            alpha_deg=df[cols["alpha_deg"]].tolist(),
            cl=df[cols["cl"]].tolist(),
            cd=df[cols["cd"]].tolist(),
            label=Path(path).stem,
        ))
    return slices


def export_polar_slices_csv(slices: list[PolarSlice], path: str) -> Path:
    """Writes ``slices`` in the CSV format that ``detect_csv_axes``/
    ``import_polar_csv`` know how to read back (columns ``alpha_deg, Cl,
    Cd, r_norm, reynolds, mach``). Low-level function used both by
    ``export_polar_csv`` (below, from an already-built ``AirfoilDef``)
    and by ``api.export_polar_table`` (Phase 7, from the direct return of
    ``external_solvers.run_polar`` — without needing an
    ``AirfoilDef``/project to generate and export a table)."""
    rows = []
    for s in slices:
        for a, cl, cd in zip(s.alpha_deg, s.cl, s.cd):
            rows.append({
                "alpha_deg": a, "Cl": cl, "Cd": cd,
                "r_norm": s.r_norm, "reynolds": s.reynolds, "mach": s.mach,
            })
    df = pd.DataFrame(rows)
    out = Path(path)
    out.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(out, index=False)
    return out


def export_polar_csv(airfoil_def: AirfoilDef, path: str) -> Path:
    return export_polar_slices_csv(airfoil_def.table_slices, path)


# =============================================================================
# b) 2D profile geometry
# =============================================================================

def generate_naca4(code: str = "0012", n_points: int = 200) -> ProfileGeometry:
    """4-digit NACA: MPXX (M=max camber %chord, P=max camber
    position/10, XX=max thickness %chord)."""
    code = code.strip()
    if len(code) != 4 or not code.isdigit():
        raise ValueError(f"Invalid NACA4 code: {code!r} (expected 4 digits, e.g. '2412')")
    m = int(code[0]) / 100.0
    p = int(code[1]) / 10.0
    t = int(code[2:]) / 100.0

    beta = np.linspace(0, math.pi, n_points // 2)
    x = (1 - np.cos(beta)) / 2   # cosine spacing -> denser at the leading edge

    yt = 5 * t * (0.2969 * np.sqrt(x) - 0.1260 * x - 0.3516 * x ** 2
                  + 0.2843 * x ** 3 - 0.1015 * x ** 4)

    if m == 0 or p == 0:
        yc = np.zeros_like(x)
        dyc_dx = np.zeros_like(x)
    else:
        yc = np.where(x < p,
                       m / p ** 2 * (2 * p * x - x ** 2),
                       m / (1 - p) ** 2 * ((1 - 2 * p) + 2 * p * x - x ** 2))
        dyc_dx = np.where(x < p,
                            2 * m / p ** 2 * (p - x),
                            2 * m / (1 - p) ** 2 * (p - x))

    theta = np.arctan(dyc_dx)
    xu = x - yt * np.sin(theta)
    yu = yc + yt * np.cos(theta)
    xl = x + yt * np.sin(theta)
    yl = yc - yt * np.cos(theta)

    x_out = np.concatenate([xu[::-1], xl[1:]])
    y_out = np.concatenate([yu[::-1], yl[1:]])

    return ProfileGeometry(source="naca4", naca_code=code, n_points=n_points,
                            x=x_out.tolist(), y=y_out.tolist())


def generate_naca5(code: str = "23012", n_points: int = 200) -> ProfileGeometry:
    """5-digit NACA (standard series, camber). Simplified implementation:
    uses the same thickness distribution as the 4-digit series and the
    standard 5-digit camber line (LxPQ)."""
    code = code.strip()
    if len(code) != 5 or not code.isdigit():
        raise ValueError(f"Invalid NACA5 code: {code!r} (expected 5 digits, e.g. '23012')")
    cl_design = int(code[0]) * (3.0 / 2.0) / 10.0   # L: approximate design Cl
    p_code = int(code[1])
    t = int(code[3:]) / 100.0
    # the max camber position (0.05*P) does not enter as a number here: it
    # is already embedded in the `table_r`/`table_k1` tables, indexed by p_code

    # tabulated coefficients (standard series, "reflex" not supported here)
    table_r = {1: 0.0580, 2: 0.1260, 3: 0.2025, 4: 0.2900, 5: 0.3910}
    table_k1 = {1: 361.4, 2: 51.64, 3: 15.957, 4: 6.643, 5: 3.230}
    r = table_r.get(p_code, 0.2025)
    k1 = table_k1.get(p_code, 15.957)

    beta = np.linspace(0, math.pi, n_points // 2)
    x = (1 - np.cos(beta)) / 2

    yt = 5 * t * (0.2969 * np.sqrt(x) - 0.1260 * x - 0.3516 * x ** 2
                  + 0.2843 * x ** 3 - 0.1015 * x ** 4)

    yc = np.where(x < r,
                   (k1 / 6.0) * (x ** 3 - 3 * r * x ** 2 + r ** 2 * (3 - r) * x),
                   (k1 * r ** 3 / 6.0) * (1 - x))
    dyc_dx = np.where(x < r,
                        (k1 / 6.0) * (3 * x ** 2 - 6 * r * x + r ** 2 * (3 - r)),
                        -(k1 * r ** 3 / 6.0) * np.ones_like(x))
    scale = cl_design / 0.3 if cl_design > 0 else 1.0
    yc = yc * scale
    dyc_dx = dyc_dx * scale

    theta = np.arctan(dyc_dx)
    xu = x - yt * np.sin(theta)
    yu = yc + yt * np.cos(theta)
    xl = x + yt * np.sin(theta)
    yl = yc - yt * np.cos(theta)

    x_out = np.concatenate([xu[::-1], xl[1:]])
    y_out = np.concatenate([yu[::-1], yl[1:]])

    return ProfileGeometry(source="naca5", naca_code=code, n_points=n_points,
                            x=x_out.tolist(), y=y_out.tolist())


def _cst_shape(x: np.ndarray, coeffs: list[float]) -> np.ndarray:
    """Standard CST (Class-Shape Transformation) class/shape function for
    profiles: C(x) = sqrt(x) * (1-x); S(x) = Bernstein sum weighted by
    the coefficients."""
    if not coeffs:
        return np.zeros_like(x)
    n = len(coeffs) - 1
    C = np.sqrt(x) * (1 - x)
    S = np.zeros_like(x)
    for i, c in enumerate(coeffs):
        binom = math.comb(n, i)
        S += c * binom * x ** i * (1 - x) ** (n - i)
    return C * S


def generate_cst(upper: list[float], lower: list[float], n_points: int = 200) -> ProfileGeometry:
    if not upper or not lower:
        raise ValueError("generate_cst requires non-empty lists of upper and lower coefficients.")
    beta = np.linspace(0, math.pi, n_points // 2)
    x = (1 - np.cos(beta)) / 2
    yu = _cst_shape(x, upper)
    yl = -_cst_shape(x, lower)
    x_out = np.concatenate([x[::-1], x[1:]])
    y_out = np.concatenate([yu[::-1], yl[1:]])
    return ProfileGeometry(source="cst", cst_upper=list(upper), cst_lower=list(lower),
                            n_points=n_points, x=x_out.tolist(), y=y_out.tolist())


def _bezier_curve(control_points: np.ndarray, n_points: int) -> np.ndarray:
    n = len(control_points) - 1
    t = np.linspace(0, 1, n_points)
    curve = np.zeros((n_points, 2))
    for i, p in enumerate(control_points):
        binom = math.comb(n, i)
        curve += np.outer(binom * t ** i * (1 - t) ** (n - i), p)
    return curve


def generate_bezier(control_points: list[list[float]], n_points: int = 200) -> ProfileGeometry:
    """`control_points` is a single closed list (upper trailing edge ->
    leading edge -> lower trailing edge), the way a graphical
    control-point editor would produce it.

    Two normalizations happen here, and they are why the curve always
    comes out as a usable airfoil instead of "whatever the control points
    literally describe":

    1. ORIENTATION. The curve is CLOSED: it starts and ends at the same
       point, and that closing point is the TRAILING EDGE (the sharp
       end); the (blunt) leading edge is the opposite extreme in x. If
       the points come in reverse order -- closing at the leading edge,
       which is what a graphical editor produces when the user starts
       drawing from the nose -- the profile comes out backwards: blunt
       nose at the back, point at the front. Instead of requiring the
       user to guess the convention, we detect which side the closure
       landed on and mirror in x.
    2. UNIT CHORD. x is rescaled to run from 0 (leading edge) to 1
       (trailing edge), with y divided by the SAME factor -- scaling
       both together preserves the relative thickness t/c, which is what
       the polar sees. Without this, control points on an arbitrary
       interval generated a profile of arbitrary chord, inconsistent
       with the convention used by the rest of the module (see
       `load_profile_dat`/NeuralFoil, both in x ∈ [0,1]).
    """
    if len(control_points) < 3:
        raise ValueError("generate_bezier requires at least 3 control points.")
    pts = np.asarray(control_points, dtype=float)
    curve = _bezier_curve(pts, n_points)
    x, y = curve[:, 0], curve[:, 1]

    x_min, x_max = float(x.min()), float(x.max())
    corda = x_max - x_min
    if corda <= 1e-12:
        raise ValueError("generate_bezier: control points have zero chord in x.")

    # (1) closure at the leading edge -> inverted profile; mirror in x.
    if abs(float(x[0]) - x_min) < abs(float(x[0]) - x_max):
        x = x_max + x_min - x

    # (2) unit chord, y by the same factor (preserves t/c).
    x = (x - x_min) / corda
    y = y / corda

    return ProfileGeometry(source="bezier", bezier_control_points=[list(p) for p in control_points],
                            n_points=n_points, x=x.tolist(), y=y.tolist())


#: Outside this range, an "x" is not a chord-normalized contour
#: coordinate. The limit is deliberately generous (a legitimate contour
#: lives in 0..1; the slack covers rounding and some extended trailing
#: edges), and what it actually catches is the point-COUNT line of the
#: Lednicer format ("61. 61."), which the reader used to read as a point
#: at x=61 -- see `load_profile_dat`.
_X_MAXIMO_DE_CONTORNO = 1.5


def load_profile_dat(path: str) -> ProfileGeometry:
    """Reads (x,y) coordinates from a text file and returns the contour.

    Accepts ANY file whose data lines are two numbers (x then y)
    separated by space, tab, or comma -- the extension (.dat/.txt/.csv)
    changes nothing, the content is what decides. Any line that is not a
    pair of numbers (airfoil name, header, comment, blank line) is
    ignored, which is what lets the **Selig** format (the usual
    UIUC/airfoiltools download: a single loop, trailing edge -> upper
    surface -> leading edge -> lower surface -> trailing edge) go in as
    is.

    The **Lednicer** format does NOT go in as is, and that is why this
    function validates: it starts with a point-COUNT line ("61.  61."),
    which is a perfectly readable pair of numbers and used to be silently
    imported as a point at x=61 -- the contour came out with a spike 61
    chords long, and nothing warned about it. Since a chord-normalized
    contour lives in x ∈ [0,1], any x outside ±`_X_MAXIMO_DE_CONTORNO` now
    ERRORS LOUDLY, saying what to do.

    The points are used in the order they appear: no reordering, no
    closing, and no rescaling."""
    p = Path(path)
    lines = p.read_text(encoding="utf-8", errors="ignore").splitlines()
    data_lines = []
    for line in lines:
        parts = line.replace(",", " ").split()
        if len(parts) != 2:
            continue
        try:
            data_lines.append((float(parts[0]), float(parts[1])))
        except ValueError:
            continue
    if not data_lines:
        raise ValueError(f"No (x,y) coordinates recognized in {path}")
    x, y = zip(*data_lines)
    fora = [v for v in x if abs(v) > _X_MAXIMO_DE_CONTORNO]
    if fora:
        raise ValueError(
            f"{path}: x = {fora[0]:g} is outside the chord (a contour normalised "
            f"by the chord has x between 0 and 1). The usual cause is a Lednicer "
            f"file, whose first line is the number of points of each surface and "
            f"reads as a coordinate here. Delete that line — and note that "
            f"Lednicer lists the two surfaces separately, both from the leading "
            f"edge, so they also need to be joined into a single loop — or "
            f"download the Selig version of the same airfoil, which needs no "
            f"editing.")
    return ProfileGeometry(source="imported", imported_path=str(path),
                            n_points=len(x), x=list(x), y=list(y))


# =============================================================================
# c) Automatic generation from a simple specification (Phase 7 -- NeuralFoil)
# =============================================================================
# Catalog of TYPICAL blade/rotor section airfoils: all are NACA4/5 (the
# only family with closed-form geometry implemented here), chosen for
# documented use in rotor/propeller blades, with a short nickname so the
# user does not have to memorize the 4/5-digit code. Any arbitrary NACA4/5
# code (outside this catalog) also works directly -- see
# `resolve_geometry_spec`.
AIRFOIL_PRESETS: dict[str, dict] = {
    "naca0009": {"family": "naca4", "code": "0009",
                 "note": "Thin symmetric -- high-speed blade/propeller tip."},
    "naca0012": {"family": "naca4", "code": "0012",
                 "note": "Symmetric -- historically one of the most widely used rotor-blade airfoils "
                         "(root/tip sections of many helicopter rotors, e.g. UH-1/Bell)."},
    "naca0015": {"family": "naca4", "code": "0015",
                 "note": "Symmetric, thicker -- inner blade sections (greater structural robustness)."},
    "naca0018": {"family": "naca4", "code": "0018",
                 "note": "Thick symmetric -- blade root/small wind-turbine applications."},
    "naca23012": {"family": "naca5", "code": "23012",
                  "note": "Cambered -- used in tail-rotor blades and propeller applications."},
    "naca4412": {"family": "naca4", "code": "4412",
                 "note": "Classic cambered section -- educational reference, also used in propellers."},
}


def generate_preset(name: str, n_points: int = 200) -> ProfileGeometry:
    """Generates the geometry of an airfoil from the `AIRFOIL_PRESETS`
    catalog by its nickname (e.g. ``'naca0012'``)."""
    key = name.strip().lower()
    if key not in AIRFOIL_PRESETS:
        raise ValueError(
            f"Unknown airfoil preset: {name!r}. "
            f"Available presets: {', '.join(sorted(AIRFOIL_PRESETS))}."
        )
    entry = AIRFOIL_PRESETS[key]
    if entry["family"] == "naca4":
        return generate_naca4(entry["code"], n_points=n_points)
    return generate_naca5(entry["code"], n_points=n_points)


def resolve_geometry_spec(spec: str, n_points: int = 200) -> ProfileGeometry:
    """Single entry point for "generate geometry from a simple string" --
    used by the GUI (preset combo box in block 'e') and by the CLI
    (``--airfoil-geometry``, Phase 7). Accepts, in order:

    1. A nickname from the `AIRFOIL_PRESETS` catalog (e.g.
       ``'naca0012'``, a typical blade/rotor airfoil).
    2. A raw NACA4 code (e.g. ``'naca2412'`` or just ``'2412'``).
    3. A raw NACA5 code (e.g. ``'naca23012'`` or just ``'23012'``).

    Raises ``ValueError`` with the list of available presets if nothing
    matches (making explicit what IS supported without needing to read
    the code)."""
    key = spec.strip().lower()
    if key in AIRFOIL_PRESETS:
        return generate_preset(key, n_points=n_points)

    code = key[4:] if key.startswith("naca") else key
    if code.isdigit() and len(code) == 4:
        return generate_naca4(code, n_points=n_points)
    if code.isdigit() and len(code) == 5:
        return generate_naca5(code, n_points=n_points)

    raise ValueError(
        f"Unrecognized geometry specification: {spec!r}. Use a NACA4 code "
        f"(4 digits, e.g. 'naca2412'), NACA5 (5 digits, e.g. 'naca23012'), or a typical "
        f"blade/rotor preset: {', '.join(sorted(AIRFOIL_PRESETS))}."
    )


def normalize_profile(geom: ProfileGeometry) -> ProfileGeometry:
    """Normalizes chord to [0,1] (translates the leading edge to x=0 and
    scales by the chord), preserving the order of the points."""
    x = np.asarray(geom.x, dtype=float)
    y = np.asarray(geom.y, dtype=float)
    x0 = x.min()
    chord = x.max() - x0
    if chord <= 0:
        return geom
    geom.x = ((x - x0) / chord).tolist()
    geom.y = (y / chord).tolist()
    return geom


def resample_profile(geom: ProfileGeometry, n_points: int) -> ProfileGeometry:
    """Resamples the contour while preserving its shape, via
    parametrization by cumulative arc length (works for closed Selig
    contours, not just y(x) functions)."""
    x = np.asarray(geom.x, dtype=float)
    y = np.asarray(geom.y, dtype=float)
    ds = np.hypot(np.diff(x), np.diff(y))
    s = np.concatenate([[0], np.cumsum(ds)])
    s_new = np.linspace(0, s[-1], n_points)
    x_new = np.interp(s_new, s, x)
    y_new = np.interp(s_new, s, y)
    geom.x, geom.y = x_new.tolist(), y_new.tolist()
    geom.n_points = n_points
    return geom
