"""Generate, validate, interpolate, and edit radial blade geometry.

Purpose: maintain the spanwise chord and twist representation consumed by the
engine and previewed by the GUI. Inputs are radius, blade count, root cutout,
radial stations, chord, twist, and preset parameters. Outputs are validated
geometry definitions and interpolated arrays. Public generators and editors
interact with ``models.py``, ``api.py``, ``bemt.py``, and the Geometry tab.
zBEMT normalizes the stations by the radius. The interpolation is piecewise
linear. It does not model structural deformation or three-dimensional airfoil
geometry.

geometry.py
===========

Generation and editing of the rotor and blade 3D geometry (the radial
chord and twist table). Nothing here is 2D (airfoil). That work belongs
to ``airfoils.py``. Nothing here runs the BEMT engine either. That work
belongs to ``bemt.py``/``studies.py`` via ``api.py``.

All functions take and return ``RotorGeometryDef`` (models.py), which is
always the radial table "underneath". Even parametric geometries turn
into a table immediately after being generated, so the GUI's graphical
editor always edits the same representation.
"""

from __future__ import annotations

import numpy as np

from .models import BladeDynamicsDef, RotorGeometryDef


def _r_grid(n_stations: int, root_cutout_norm: float) -> np.ndarray:
    return np.linspace(root_cutout_norm, 1.0, n_stations)


def _validate_and_sort_table(r_norm, chord_norm, twist_deg, *, context: str
                              ) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Validate a radial table (r_norm, chord_norm, twist_deg) before any
    use with ``np.interp`` (Q3, production-plan.md): ``np.interp`` requires
    ``x`` sorted and increasing, and nothing in the previous code
    guaranteed that. A table pasted out of order silently produced wrong
    chord and twist values, with no error or warning.

    Decision: REORDER (not error) by increasing ``r_norm``, dragging
    ``chord_norm``/``twist_deg`` along as a unit, because it is common to
    paste a tip->root table from a spreadsheet. This neither loses nor
    corrupts information (each row keeps its correct trio). Only ERROR
    when sorting is not enough to make the table usable: duplicate
    ``r_norm`` values (ambiguous for ``np.interp``, since which chord
    applies at that radius would be unclear) or lists of different lengths.
    """
    r = np.asarray(r_norm, dtype=float)
    c = np.asarray(chord_norm, dtype=float)
    t = np.asarray(twist_deg, dtype=float)

    if not (len(r) == len(c) == len(t)):
        raise ValueError(
            f"{context}: r_norm ({len(r)}), chord_norm ({len(c)}) and twist_deg "
            f"({len(t)}) must have the same length."
        )
    if len(r) == 0:
        raise ValueError(f"{context}: radial table is empty.")
    if np.any(~np.isfinite(r)):
        raise ValueError(f"{context}: r_norm contains non-finite values (NaN/inf).")

    order = np.argsort(r, kind="stable")
    r_sorted, c_sorted, t_sorted = r[order], c[order], t[order]

    dup = np.diff(r_sorted) == 0.0
    if np.any(dup):
        values = sorted(set(r_sorted[np.r_[dup, False] | np.r_[False, dup]].tolist()))
        raise ValueError(
            f"{context}: r_norm has duplicate values {values}. "
            "This is ambiguous for interpolation (two control points at the same radius)."
        )
    return r_sorted, c_sorted, t_sorted


def generate_rectangular(root_cutout_norm: float = 0.15, radius_m: float = 1.0,
                          chord_norm: float = 0.08, twist_root_deg: float = 12.0,
                          twist_tip_deg: float = 4.0, n_blades: int = 2,
                          n_stations: int = 25, airfoil_name: str = "") -> RotorGeometryDef:
    r = _r_grid(n_stations, root_cutout_norm)
    chord = np.full_like(r, chord_norm)
    twist = np.linspace(twist_root_deg, twist_tip_deg, n_stations)
    return RotorGeometryDef(
        r_norm=r.tolist(), chord_norm=chord.tolist(), twist_deg=twist.tolist(),
        origin="parametric",
        origin_params={"kind": "rectangular", "chord_norm": chord_norm,
                        "twist_root_deg": twist_root_deg, "twist_tip_deg": twist_tip_deg},
        n_blades=n_blades, radius_m=radius_m, root_cutout_norm=root_cutout_norm,
        airfoil_name=airfoil_name,
    )


def generate_tapered(root_cutout_norm: float = 0.15, radius_m: float = 1.0,
                      root_chord_norm: float = 0.10, tip_chord_norm: float = 0.04,
                      twist_root_deg: float = 14.0, twist_tip_deg: float = 2.0,
                      n_blades: int = 2, n_stations: int = 25,
                      airfoil_name: str = "") -> RotorGeometryDef:
    r = _r_grid(n_stations, root_cutout_norm)
    chord = np.linspace(root_chord_norm, tip_chord_norm, n_stations)
    twist = np.linspace(twist_root_deg, twist_tip_deg, n_stations)
    return RotorGeometryDef(
        r_norm=r.tolist(), chord_norm=chord.tolist(), twist_deg=twist.tolist(),
        origin="parametric",
        origin_params={"kind": "tapered", "root_chord_norm": root_chord_norm,
                        "tip_chord_norm": tip_chord_norm,
                        "twist_root_deg": twist_root_deg, "twist_tip_deg": twist_tip_deg},
        n_blades=n_blades, radius_m=radius_m, root_cutout_norm=root_cutout_norm,
        airfoil_name=airfoil_name,
    )


def generate_elliptic(root_cutout_norm: float = 0.15, radius_m: float = 1.0,
                       max_chord_norm: float = 0.10, twist_root_deg: float = 14.0,
                       twist_tip_deg: float = 2.0, n_blades: int = 2,
                       n_stations: int = 25, airfoil_name: str = "") -> RotorGeometryDef:
    """Blade with elliptic planform: chord(r) = max_chord_norm*sqrt(1-r_norm²).

    The peak sits at the ROOT (small r_norm), not at mid-span. This is
    INTENTIONAL (Q3, production-plan.md), not a bug: the convention here
    is single-blade (root->tip), analogous to the classic elliptic
    distribution of a two-blade rotor viewed as a single disk. The two
    blades, side by side, form a complete ellipse with the peak at the hub
    (r=0) tapering to zero at both tips. Each isolated blade is half of
    that ellipse. This is also the shape used in classic references for
    minimum induced-loss propellers (elliptic loading). Do not confuse this
    with the ellipse of a WHOLE WING (peak at the center or mid-span, two
    symmetric sides). That is not the convention adopted here. Changing
    this would change the blade shape for existing users of the generator,
    so it stays as is. See ``tests/test_geometry.py::
    test_generate_elliptic_chord_never_zero_at_tip``, which locks in this
    behavior.
    """
    r = _r_grid(n_stations, root_cutout_norm)
    chord = max_chord_norm * np.sqrt(np.maximum(0.0, 1.0 - r ** 2))
    # Q3 (production-plan.md): the ellipse peak at r=0 (root/hub) is
    # DELIBERATE, not a bug. See the function docstring. But since the
    # table only starts at r=root_cutout_norm (>0), the value AT THE FIRST
    # POINT already comes out smaller than max_chord_norm (sqrt(1-r^2) < 1
    # for r>0), and the GUI labels this field "Max chord (c/R)": the user
    # enters the value expecting it to actually be the peak of the
    # generated table. Rescale so that chord[0] (the true peak, at the
    # root) matches max_chord_norm exactly, preserving the elliptical shape.
    peak = max_chord_norm * np.sqrt(max(0.0, 1.0 - root_cutout_norm ** 2))
    if peak > 1e-12:
        chord = chord * (max_chord_norm / peak)
    chord = np.maximum(chord, 0.15 * max_chord_norm)   # avoid zero chord at the tip
    twist = np.linspace(twist_root_deg, twist_tip_deg, n_stations)
    return RotorGeometryDef(
        r_norm=r.tolist(), chord_norm=chord.tolist(), twist_deg=twist.tolist(),
        origin="parametric",
        origin_params={"kind": "elliptic", "max_chord_norm": max_chord_norm,
                        "twist_root_deg": twist_root_deg, "twist_tip_deg": twist_tip_deg},
        n_blades=n_blades, radius_m=radius_m, root_cutout_norm=root_cutout_norm,
        airfoil_name=airfoil_name,
    )


def generate_custom(r_norm: list[float], chord_norm: list[float], twist_deg: list[float],
                     radius_m: float = 1.0, n_blades: int = 2,
                     airfoil_name: str = "") -> RotorGeometryDef:
    """Build the geometry directly from user-supplied lists (for example
    lists pasted from a spreadsheet). The table is reordered by increasing
    ``r_norm`` if it comes out of order (see ``_validate_and_sort_table``)."""
    r, c, t = _validate_and_sort_table(r_norm, chord_norm, twist_deg, context="generate_custom")
    return RotorGeometryDef(
        r_norm=r.tolist(), chord_norm=c.tolist(), twist_deg=t.tolist(),
        origin="table", origin_params={},
        n_blades=n_blades, radius_m=radius_m,
        root_cutout_norm=float(r.min()),
        airfoil_name=airfoil_name,
    )


def resample_geometry(geom: RotorGeometryDef, n_stations: int) -> RotorGeometryDef:
    """Resample the radial table at ``n_stations`` points evenly spaced
    between the root cutout and the tip, via linear interpolation.
    Used by the graphical editor when adding or removing control points."""
    if len(geom.r_norm) < 2:
        return geom
    r_old, chord_old, twist_old = _validate_and_sort_table(
        geom.r_norm, geom.chord_norm, geom.twist_deg, context="resample_geometry")
    r_new = np.linspace(r_old.min(), r_old.max(), n_stations)
    chord_new = np.interp(r_new, r_old, chord_old)
    twist_new = np.interp(r_new, r_old, twist_old)
    out = RotorGeometryDef(
        r_norm=r_new.tolist(), chord_norm=chord_new.tolist(), twist_deg=twist_new.tolist(),
        origin="editor", origin_params=dict(geom.origin_params),
        n_blades=geom.n_blades, radius_m=geom.radius_m,
        root_cutout_norm=float(r_new.min()), airfoil_name=geom.airfoil_name,
    )
    return out


def interpolate_geometry(geom: RotorGeometryDef, r_query_norm: list[float]) -> tuple[list[float], list[float]]:
    """Return (chord_norm, twist_deg) interpolated at the requested radial
    positions. Used both by the conversion to ``Rotor`` (engine) and by
    the graphical preview when dragging an editor point."""
    r_old, chord_old, twist_old = _validate_and_sort_table(
        geom.r_norm, geom.chord_norm, geom.twist_deg, context="interpolate_geometry")
    chord = np.interp(r_query_norm, r_old, chord_old)
    twist = np.interp(r_query_norm, r_old, twist_old)
    return chord.tolist(), twist.tolist()


def edit_point(geom: RotorGeometryDef, index: int, chord_norm: float | None = None,
               twist_deg: float | None = None) -> RotorGeometryDef:
    """Edit a single control point of the table (direct use by the
    graphical editor when dragging a marker) and return an updated copy."""
    chords = list(geom.chord_norm)
    twists = list(geom.twist_deg)
    if chord_norm is not None:
        chords[index] = chord_norm
    if twist_deg is not None:
        twists[index] = twist_deg
    geom.chord_norm = chords
    geom.twist_deg = twists
    geom.origin = "editor"
    return geom


# =============================================================================
# Blade dynamics conversions (SC-11)
# =============================================================================
# The formulas of the rigid-blade flap and lag model live HERE, once, so
# that the validation, the GUI's live preview panel and the engine cannot
# drift apart. ``models.py`` holds no physics (AR-3); this module is the
# one the requirements name for the inertia conversion.

#: Radial station (r/R) where the reference chord c_ref of the Lock number
#: is read from the radial table.
REFERENCE_CHORD_STATION = 0.75


def reference_chord_m(geom: RotorGeometryDef) -> float:
    """The blade chord [m] interpolated at ``r/R = 0.75``, the classic
    representative station of the Lock number."""
    r_old, chord_old, _twist_old = _validate_and_sort_table(
        geom.r_norm, geom.chord_norm, geom.twist_deg,
        context="reference_chord_m")
    return float(np.interp(REFERENCE_CHORD_STATION, r_old, chord_old) * geom.radius_m)


def resolve_flap_inertia(*, inertia_source: str, lock_number: float,
                          flap_inertia_kg_m2: float, blade_mass_kg: float,
                          hinge_offset_norm: float, radius_m: float,
                          chord_ref_m: float, rho: float,
                          cl_alpha: float) -> float:
    """Resolved flap inertia I_beta [kg*m^2] of one blade about its flap
    hinge, from the source the user chose.

    - ``"lock"``       -- from the Lock number gamma, inverted:
      I_beta = rho*a*c_ref*R^4 / gamma, with `a` the lift-curve slope and
      `c_ref` the chord at r/R = 0.75.
    - ``"inertia"``    -- the value given in ``flap_inertia_kg_m2``.
    - ``"blade_mass"`` -- a uniform mass per unit length over the flapping
      part of the blade: I_beta = m_b*(R - e*R)^2 / 3.

    An unknown source returns NaN, which the validation turns into an
    error; it never silently falls back to another source.
    """
    if inertia_source == "lock":
        denominator = float(lock_number)
        if not np.isfinite(denominator) or abs(denominator) < 1e-9:
            return float("nan")
        return float(rho * cl_alpha * chord_ref_m * radius_m ** 4 / denominator)
    if inertia_source == "inertia":
        return float(flap_inertia_kg_m2)
    if inertia_source == "blade_mass":
        arm = max(radius_m * (1.0 - hinge_offset_norm), 1e-9)
        return float(blade_mass_kg * arm ** 2 / 3.0)
    return float("nan")


def flap_inertia_from(dynamics: BladeDynamicsDef, geom: RotorGeometryDef,
                      rho: float, cl_alpha: float) -> float:
    """``resolve_flap_inertia`` fed straight from the project's dataclasses.
    This is the entry point the validation and the GUI use."""
    return resolve_flap_inertia(
        inertia_source=dynamics.inertia_source,
        lock_number=dynamics.lock_number,
        flap_inertia_kg_m2=dynamics.flap_inertia_kg_m2,
        blade_mass_kg=dynamics.blade_mass_kg,
        hinge_offset_norm=dynamics.hinge_offset_norm,
        radius_m=geom.radius_m,
        chord_ref_m=reference_chord_m(geom),
        rho=rho, cl_alpha=cl_alpha,
    )


def _offset_spring_term(hinge_offset_norm: float) -> float:
    """(3/2)*e/(1-e): the frequency contribution of an offset hinge,
    shared by the flap and the lag ratios."""
    e = float(hinge_offset_norm)
    if not np.isfinite(e):
        return float("nan")
    if abs(e) >= 1.0:
        return float("nan")
    return 1.5 * e / (1.0 - e)


def flap_frequency_ratio_squared(hinge_offset_norm: float, spring_nm_per_rad: float,
                                  inertia_kg_m2: float, omega_rad_s: float) -> float:
    """nu_beta^2 = 1 + (3/2)*e/(1-e) + K_beta/(I_beta*Omega^2), for a
    uniform blade with an offset hinge and a root spring.

    The leading 1 is the rigid-blade bending mode's own restoring term.
    With e = 0 and no spring the ratio is exactly 1, which is why an
    articulated rotor resonates with the first harmonic (EN-8)."""
    spring_term = 0.0
    if inertia_kg_m2 and omega_rad_s:
        spring_term = float(spring_nm_per_rad) / (float(inertia_kg_m2) * float(omega_rad_s) ** 2)
    return 1.0 + _offset_spring_term(hinge_offset_norm) + spring_term


def lag_frequency_ratio_squared(hinge_offset_norm: float, lag_spring_nm_per_rad: float,
                                 lag_inertia_kg_m2: float, omega_rad_s: float) -> float:
    """nu_zeta^2 = (3/2)*e/(1-e) + K_zeta/(I_zeta*Omega^2).

    The lag freedom gets no restoring term from the thrust, so unlike the
    flap ratio the leading 1 is absent: with no offset and no spring the
    ratio is exactly zero and the lag angle is undefined."""
    spring_term = 0.0
    if lag_inertia_kg_m2 and omega_rad_s:
        spring_term = (float(lag_spring_nm_per_rad)
                       / (float(lag_inertia_kg_m2) * float(omega_rad_s) ** 2))
    return _offset_spring_term(hinge_offset_norm) + spring_term


def flap_aero_damping(lock_number: float, hinge_offset_norm: float) -> float:
    """Aerodynamic flap damping coefficient d_beta of the harmonic
    balance, in the same normalization as the flap equation:

        beta'' + nu_beta^2 * beta + d_beta * beta' = Mbar(psi)

    Derived from the ``(r - e*R)*beta_dot`` term of U_P. A section moving
    with the flap rate sees its incidence change by ``-(r - eR)*beta_dot
    / U_T``; multiplying by the lift slope and the local dynamic
    pressure, taking the moment about the hinge and dividing by the Lock
    inertia leaves an integral that closes in elementary terms:

        d_beta = (gamma/2) * INT_e^1 x*(x - e)^2 dx
               = (gamma/2) * [ (1-e)^4/4 + e*(1-e)^3/3 ]

    with ``gamma`` the RESOLVED Lock number (whatever inertia source the
    user chose). At e = 0 this is gamma/8, the classic flap damping of
    the centrally hinged blade.

    The second-order expansion of the same expression, gamma*(1/8 - e/3
    + e^2/4), was used here before. It agrees to four figures for the
    small offsets a real articulated rotor uses, and drifts to 0.7 % at
    e = 0.3, so the exact form costs nothing and removes a needless
    approximation. This is the term the solver must treat implicitly --
    see `bemt.solve_bemt_flapping` -- because keeping it on the
    right-hand side makes the outer iteration unstable."""
    e = float(hinge_offset_norm)
    return 0.5 * float(lock_number) * ((1.0 - e) ** 4 / 4.0
                                        + e * (1.0 - e) ** 3 / 3.0)
