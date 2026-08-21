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

Generation and editing of the rotor/blade 3D geometry (radial chord and
twist table). Nothing here is 2D (airfoil) — that's ``airfoils.py``.
Nothing here runs the BEMT engine — that's ``bemt.py``/``studies.py`` via
``api.py``.

All functions take/return ``RotorGeometryDef`` (models.py), which is
always the radial table "underneath" — even parametric geometries turn
into a table immediately after being generated, so the GUI's graphical
editor always edits the same representation.
"""

from __future__ import annotations

import numpy as np

from .models import RotorGeometryDef


def _r_grid(n_stations: int, root_cutout_norm: float) -> np.ndarray:
    return np.linspace(root_cutout_norm, 1.0, n_stations)


def _validate_and_sort_table(r_norm, chord_norm, twist_deg, *, context: str
                              ) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Validate a radial table (r_norm, chord_norm, twist_deg) before any
    use with ``np.interp`` (Q3, production-plan.md): ``np.interp`` requires
    ``x`` sorted and increasing, and nothing in the previous code
    guaranteed that -- a table pasted out of order silently produced wrong
    chord/twist, with no error or warning.

    Decision: REORDER (not error) by increasing ``r_norm``, dragging
    ``chord_norm``/``twist_deg`` along as a unit -- it's common to paste a
    tip->root table from a spreadsheet, and this neither loses nor
    corrupts information (each row keeps its correct trio). Only ERROR
    when sorting isn't enough to make the table usable: duplicate
    ``r_norm`` values (ambiguous for ``np.interp`` -- which chord applies
    at that radius?) or lists of different lengths.
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
        valores = sorted(set(r_sorted[np.r_[dup, False] | np.r_[False, dup]].tolist()))
        raise ValueError(
            f"{context}: r_norm has duplicate values {valores} -- "
            "ambiguous for interpolation (two control points at the same radius)."
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

    The peak sits at the ROOT (small r_norm), not at mid-span -- this is
    INTENTIONAL (Q3, production-plan.md), not a bug: the convention here
    is single-blade (root->tip), analogous to the classic elliptic
    distribution of a two-blade rotor viewed as a single disc -- the two
    blades, side by side, form a complete ellipse with the peak at the hub
    (r=0) tapering to zero at both tips; each isolated blade is half of
    that ellipse. This is also the shape used in classic references for
    minimum induced-loss propellers (elliptic loading). Don't confuse this
    with the ellipse of a WHOLE WING (peak at center/mid-span, two
    symmetric sides) -- that is not the convention adopted here. Changing
    this would change the blade shape for existing users of the generator,
    so it stays as is; see ``tests/test_geometry.py::
    test_generate_elliptic_chord_never_zero_at_tip`` which locks in this
    behavior.
    """
    r = _r_grid(n_stations, root_cutout_norm)
    chord = max_chord_norm * np.sqrt(np.maximum(0.0, 1.0 - r ** 2))
    # Q3 (production-plan.md): the ellipse peak at r=0 (root/hub) is
    # DELIBERATE, not a bug -- see the function docstring. But since the
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
    """Build the geometry directly from user-supplied lists (e.g. pasted
    from a spreadsheet). The table is reordered by increasing ``r_norm``
    if it comes out of order (see ``_validate_and_sort_table``)."""
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
    Used by the graphical editor when adding/removing control points."""
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
    positions — used both by the conversion to ``Rotor`` (engine) and by
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
