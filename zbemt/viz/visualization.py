"""visualization.py
=================

3D via PyVista, isolated in this file. The ``pyvista`` import only
happens here, and only inside the functions
that actually draw (never at module level). The rest of the platform
(geometry, airfoil, BEMT, batch, 2D plots, GUI without the 3D tab) keeps
working normally even without PyVista installed.

Two layers, deliberately kept separate:

- **mesh builders** (``build_`` prefix): pure NumPy geometry (points +
  connectivity), with NO dependency on PyVista at all. They can be
  called and tested in isolation (including without PyVista installed),
  and are what ``plot_*`` uses underneath to assemble the PyVista
  objects.
- **plot_***: wrap the builders above into ``pyvista.PolyData`` /
  ``pyvista.StructuredGrid`` and draw on a ``pyvista.Plotter``. Only
  these actually call PyVista; they are the only ones that raise
  ``ImportError`` if the package is not installed.

Convention (mirrors ``plots.py``): every ``plot_*`` function accepts
``plotter=None, fname=None``. If ``plotter`` is supplied (for example,
the GUI embedded a PyVista ``QtInteractor`` in a tab), it draws on it and
returns the ``plotter`` itself. Whoever supplied the plotter decides
when to call ``.render()``/show it. If ``fname`` is supplied instead, it
creates an off-screen ``Plotter``, draws, saves a screenshot (``.png``)
to disk, and closes. This is the mode used by ``api.export_results``.

Axis convention (rotor "at rest", seen from outside): X,Y in the disk
plane, with azimuth ``psi=0`` along +X (same convention as the rest of
the platform, see ``bemt.element_state``, where ``Ut`` uses
``sin(psi)`` and X is the ``psi=0`` reference); Z along the rotor axis,
out of the disk plane."""

from __future__ import annotations

from typing import Optional, Sequence
import numpy as np


# =============================================================================
# PyVista availability (lazy check, cached)
# =============================================================================

_PYVISTA_AVAILABLE: Optional[bool] = None


def is_available() -> bool:
    """``True`` if the optional ``pyvista`` package is installed. The
    import check is done only once and cached, so subsequent calls are
    cheap. Used by the GUI to decide whether to show the full 3D tab or
    the schematic 2D fallback (see ``gui.ViewerTab``)."""
    global _PYVISTA_AVAILABLE
    if _PYVISTA_AVAILABLE is None:
        try:
            import pyvista  # noqa: F401
            _PYVISTA_AVAILABLE = True
        except ImportError:
            _PYVISTA_AVAILABLE = False
    return _PYVISTA_AVAILABLE


def _require_pyvista():
    if not is_available():
        raise ImportError(
            "visualization.py needs the optional 'pyvista' package to "
            "draw (pip install pyvista). The rest of the platform "
            "(geometry, airfoil, BEMT, batch, 2D plots, GUI without the "
            "3D tab) works normally without it -- see docs/plano.md Section 4."
        )
    import pyvista as pv
    return pv


# =============================================================================
# Mesh builders: 3D blade (pure NumPy, no PyVista)
# =============================================================================
#
# The blade is built at an azimuth station psi=0 (along +X), on a
# structured mesh (n_span radial stations x n_chord profile points).
# Each radial station is positioned as follows. (1) It is placed at
# (r,0,0) [r in meters]. (2) The 2D profile (x/c, y/c) is scaled by the
# local chord and ROTATED by the local twist around the radial (span)
# axis. (3) The whole blade (already with twist applied) is rotated
# around the Z axis (of the rotor) by the target azimuth. This last
# rotation is exactly what ``build_rotor_disk`` applies Nb times to
# assemble the full disk.

def _sorted_radial_table(geom):
    r_norm = np.asarray(geom.r_norm, dtype=float)
    chord_norm = np.asarray(geom.chord_norm, dtype=float)
    twist_deg = np.asarray(geom.twist_deg, dtype=float)
    order = np.argsort(r_norm)
    return r_norm[order], chord_norm[order], twist_deg[order]


def _profile_xy(profile) -> tuple[np.ndarray, np.ndarray]:
    """(x/c, y/c) of the profile, with x referenced to the quarter chord
    (x=0 at c/4, positive toward the trailing edge), the usual convention
    for the twist and structural reference axis. If ``profile`` is ``None``
    or has no generated coordinates, falls back to a thin flat plate
    (2 points, leading and trailing edge). That is enough to visualize
    planform and twist without depending on a 2D profile geometry having
    already been generated."""
    if profile is not None and getattr(profile, "x", None) and len(profile.x) >= 3:
        xc = np.asarray(profile.x, dtype=float) - 0.25
        yc = np.asarray(profile.y, dtype=float)
        return xc, yc
    return np.array([-0.25, 0.75]), np.array([0.0, 0.0])


def build_blade_surface(geom, profile=None, n_span: int = 40, azimuth_deg: float = 0.0):
    """Builds the blade's lofted mesh (a single blade) in meters, at
    azimuth ``azimuth_deg`` (default 0 = along +X).

    geom: ``models.RotorGeometryDef`` (radial table: r_norm, chord_norm,
        twist_deg, normalized, scaled here by ``geom.radius_m``).
    profile: optional ``models.ProfileGeometry``; without it, uses a
        thin flat plate (see ``_profile_xy``).
    n_span: number of radial stations interpolated along the table (the
        original table may have few points; this refines the mesh).

    Returns ``(points, faces)``:
        points: ``(n_span * n_chord, 3)`` float, in meters.
        faces:  "flat" list in PyVista format (``[4, i0,i1,i2,i3, 4,
            ...]``), one quad face per cell of the lofted grid, ready
            for ``pyvista.PolyData(points, faces)``.
    """
    r_norm, chord_norm, twist_deg = _sorted_radial_table(geom)
    if len(r_norm) < 2:
        raise ValueError("build_blade_surface: geometry needs at least 2 radial stations.")

    r_span = np.linspace(r_norm.min(), r_norm.max(), max(n_span, 2))
    chord_i = np.interp(r_span, r_norm, chord_norm)
    twist_i = np.deg2rad(np.interp(r_span, r_norm, twist_deg))

    xc, yc = _profile_xy(profile)
    n_chord = len(xc)

    psi = np.deg2rad(azimuth_deg)
    cos_psi, sin_psi = np.cos(psi), np.sin(psi)

    points = np.empty((len(r_span) * n_chord, 3), dtype=float)
    for i, (r, c, th) in enumerate(zip(r_span, chord_i, twist_i)):
        cos_th, sin_th = np.cos(th), np.sin(th)
        # --- twist: rotation about the radial axis (mixes chord/thickness) ---
        y_local = xc * c * cos_th - yc * c * sin_th   # "in the disk plane" component
        z_local = xc * c * sin_th + yc * c * cos_th   # "out of plane" component (rotor axis)
        x_span = np.full(n_chord, r)
        # --- azimuth: rotation about the Z axis (rotor's) ---
        x_g = x_span * cos_psi - y_local * sin_psi
        y_g = x_span * sin_psi + y_local * cos_psi
        z_g = z_local
        sl = slice(i * n_chord, (i + 1) * n_chord)
        points[sl, 0] = x_g
        points[sl, 1] = y_g
        points[sl, 2] = z_g

    points *= geom.radius_m

    faces = []
    n_r = len(r_span)
    for i in range(n_r - 1):
        for j in range(n_chord - 1):
            p00 = i * n_chord + j
            p01 = i * n_chord + (j + 1)
            p11 = (i + 1) * n_chord + (j + 1)
            p10 = (i + 1) * n_chord + j
            faces.extend([4, p00, p01, p11, p10])

    return points, faces


def build_rotor_disk(geom, profile=None, n_span: int = 40, phase_deg: float = 0.0):
    """Builds the rotor's ``geom.n_blades`` blades, evenly spaced in
    azimuth (``360/Nb`` degrees), from ``build_blade_surface``.

    Returns a list of ``(points, faces)`` (one per blade) instead of
    already combining them into a single mesh, so that the caller drawing
    it (``plot_rotor_3d``) can color/name each blade independently if
    desired."""
    n_blades = max(int(geom.n_blades), 1)
    step = 360.0 / n_blades
    return [
        build_blade_surface(geom, profile=profile, n_span=n_span, azimuth_deg=phase_deg + k * step)
        for k in range(n_blades)
    ]


# =============================================================================
# Mesh builders: disk maps and load distributions (pure NumPy)
# =============================================================================
#
# Unlike plots.plot_disk_map (which triangulates "loose" X,Y via
# ax.tricontourf because matplotlib has no easy native 2D structured
# grid), here we take advantage of the fact that R_DIM/PSI in `maps`
# (output of `bemt.solve_bemt`) are ALREADY a structured grid (Ne, Npsi),
# so it becomes a `pyvista.StructuredGrid` directly, with no triangulation.

def available_disk_fields(maps: dict) -> list[str]:
    """Lists the fields of ``maps`` (output of ``bemt.solve_bemt`` /
    ``Results.maps``) that have the same 2D shape (Ne,Npsi) as ``R_DIM``.
    That is, only the ones that make sense as a color or height field in
    a disk map. Useful for populating a selector in the GUI."""
    if "R_DIM" not in maps:
        return []
    shape = np.asarray(maps["R_DIM"]).shape
    return sorted(
        k for k, v in maps.items()
        if isinstance(v, np.ndarray) and v.shape == shape and k not in ("R_DIM", "PSI", "R_NORM")
    )


def _close_azimuth(PSI: np.ndarray, *fields_2d: np.ndarray):
    """Closes the disk in azimuth: ``PSI`` (and the other ``(Ne,Npsi)``
    fields passed in) come from the ``bemt.solve_bemt`` grid, which
    covers ``[0, 2*pi*(1-1/Npsi)]``. That is, the last psi node does NOT
    go all the way around to ``2*pi`` (the same angle as the ``psi=0``
    node, one revolution later). This is correct for integration/physics
    (closing the node there would duplicate an azimuthal station, see
    ``bemt._trapz_psi_periodic``), but for RENDERING the disk surface it
    leaves a slice with no coverage between the last sampled point and
    ``psi=0``, exactly the disk contour's "blank slice from
    discretization".

    Here it is safe (and necessary) to duplicate this column, since it
    is only for drawing: appends a copy of the ``psi=0`` column at
    ``psi=2*pi`` to the end of each field, closing the surface without
    changing any physical value (the new column is identical to the
    first, just shifted one full revolution in azimuth).

    Returns ``(PSI_closed, *closed_fields)``, all with one extra
    column: ``(Ne, Npsi+1)``."""
    psi0 = PSI[:, :1]
    PSI_closed = np.concatenate([PSI, psi0 + 2.0 * np.pi], axis=1)
    closed_fields = tuple(np.concatenate([f, f[:, :1]], axis=1) for f in fields_2d)
    return (PSI_closed,) + closed_fields


def build_disk_grid(maps: dict, field: str = "lambda_i",
                     z_field: Optional[str] = None, z_scale: float = 0.15,
                     close_azimuth: bool = True):
    """Builds the disk grid (X,Y,Z,values) from an already-solved ``maps``
    (``R_DIM``, ``PSI`` — always present in ``bemt.solve_bemt`` output).

    field: field used to color the surface (``point_data``).
    z_field: if provided, "extrudes" the surface out of the disk plane
        proportionally to this field (load visualization as a 3D relief;
        for example, ``z_field="Fn"`` shows the distributed thrust as
        height). If ``None`` (default), flat disk (Z=0), colored only.
    z_scale: extrusion scale, as a fraction of the blade radius (avoids
        the relief becoming disproportionate to the disk size).
    close_azimuth: if ``True`` (default), closes the circle by
        duplicating the ``psi=0`` column at ``psi=2*pi`` (see
        ``_close_azimuth``). Without this the raw ``(Ne,Npsi)`` grid
        from ``solve_bemt`` leaves a slice of width ``2*pi/Npsi`` with no
        coverage (the disk's "blank slice from discretization"). Use
        ``False`` only if you need the raw grid (for example to resample
        or post-process the data before drawing).

    Returns ``(X, Y, Z, values)``, 2D arrays, ``(Ne,Npsi+1)`` if
    ``close_azimuth`` (default) or ``(Ne,Npsi)`` otherwise, ready for
    ``pyvista.StructuredGrid``."""
    if "R_DIM" not in maps or "PSI" not in maps:
        raise KeyError(
            "build_disk_grid: 'maps' must have 'R_DIM' and 'PSI' (output from "
            "bemt.solve_bemt / Results.maps)."
        )
    if field == "Vi":
        lam_i = np.asarray(maps["lambda_i"], dtype=float)
        omega_r = maps.get("OmegaR")
        if omega_r is None:
            up = np.asarray(maps["Up"], dtype=float)
            lam_total = np.asarray(maps.get("lambda_total", maps["lambda_i"]), dtype=float)
            omega_r = float(np.nanmax(np.abs(up)) / max(np.nanmax(np.abs(lam_total)), 1e-12))
        values = lam_i * float(omega_r)
    elif field == "lambda_z_field":
        values = np.asarray(maps["lambda_total"], dtype=float)
    elif field == "q":
        values = 0.5 * float(maps["rho"]) * np.asarray(maps["W"], dtype=float) ** 2
    elif field not in maps:
        raise KeyError(
            f"Field '{field}' not found in maps. Available: {available_disk_fields(maps)}"
        )
    R_DIM, PSI = np.asarray(maps["R_DIM"]), np.asarray(maps["PSI"])
    if field in maps:
        values = np.asarray(maps[field], dtype=float)

    if z_field is not None:
        if z_field not in maps:
            raise KeyError(
                f"Field '{z_field}' (z_field) not found in maps. "
                f"Available: {available_disk_fields(maps)}"
            )
        z_raw = np.asarray(maps[z_field], dtype=float)
        peak = np.nanmax(np.abs(z_raw)) if z_raw.size else 0.0
        R_max = np.nanmax(R_DIM) if R_DIM.size else 1.0
        Z = (z_raw / peak) * z_scale * R_max if peak > 1e-12 else np.zeros_like(z_raw)
    else:
        Z = np.zeros_like(values)

    if close_azimuth:
        PSI, R_DIM, values, Z = _close_azimuth(PSI, R_DIM, values, Z)

    X = R_DIM * np.cos(PSI)
    Y = R_DIM * np.sin(PSI)
    return X, Y, Z, values


# =============================================================================
# plot_*: draw via PyVista (the only functions that actually import pyvista)
# =============================================================================

def _resolve_plotter(plotter, fname, window_size=(900, 700)):
    pv = _require_pyvista()
    if plotter is not None:
        return plotter, None, pv
    owned = pv.Plotter(off_screen=fname is not None, window_size=list(window_size))
    return owned, owned, pv


def _finish(plotter, owned_plotter, fname):
    if fname is not None and owned_plotter is not None:
        owned_plotter.show(screenshot=fname)
        owned_plotter.close()
    return plotter


def plot_rotor_3d(geom, profile=None, n_span: int = 40, plotter=None, fname=None,
                   color: str = "steelblue", show_hub: bool = True,
                   window_size=(900, 700)):
    """Draws the rotor's ``geom.n_blades`` blades in 3D (via
    ``build_rotor_disk``). ``geom``: ``models.RotorGeometryDef``.
    ``profile``: optional ``models.ProfileGeometry`` (otherwise, a
    schematic flat plate, see ``_profile_xy``)."""
    plotter_out, owned, pv = _resolve_plotter(plotter, fname, window_size)
    blades = build_rotor_disk(geom, profile=profile, n_span=n_span)
    for points, faces in blades:
        mesh = pv.PolyData(np.asarray(points), np.asarray(faces))
        plotter_out.add_mesh(mesh, color=color, smooth_shading=True, show_edges=False)
    if show_hub:
        hub_r = 0.03 * geom.radius_m
        hub = pv.Cylinder(center=(0, 0, 0), direction=(0, 0, 1), radius=hub_r, height=hub_r * 2)
        plotter_out.add_mesh(hub, color="dimgray")
    plotter_out.add_axes()
    if owned is not None:
        plotter_out.camera_position = "iso"
    return _finish(plotter_out, owned, fname)


def plot_disk_map_3d(maps: dict, field: str = "lambda_i", z_field: Optional[str] = None,
                      z_scale: float = 0.15, cmap: str = "viridis",
                      plotter=None, fname=None, scalar_bar: bool = True,
                      window_size=(900, 700)):
    """Draws the disk map ``field`` as a 3D structured surface (see
    ``build_disk_grid``). If ``z_field`` is provided, the surface is
    extruded out of the plane proportionally to this field (for example:
    ``field="Fn", z_field="Fn"`` — color AND height show the same load
    distribution; ``field="alpha_eff", z_field="Fn"`` shows the angle of
    attack colored over the thrust relief)."""
    plotter_out, owned, pv = _resolve_plotter(plotter, fname, window_size)
    X, Y, Z, values = build_disk_grid(maps, field=field, z_field=z_field, z_scale=z_scale)
    grid = pv.StructuredGrid(X, Y, Z)
    grid[field] = values.ravel(order="F")
    plotter_out.add_mesh(grid, scalars=field, cmap=cmap, show_edges=False,
                          scalar_bar_args={"title": field} if scalar_bar else None,
                          show_scalar_bar=scalar_bar)
    plotter_out.add_axes()
    if owned is not None:
        plotter_out.camera_position = "iso" if z_field is not None else "xy"
    return _finish(plotter_out, owned, fname)


def plot_load_distribution_3d(maps: dict, field: str = "Fn", z_scale: float = 0.2,
                               cmap: str = "plasma", plotter=None, fname=None,
                               window_size=(900, 700)):
    """Shortcut for ``plot_disk_map_3d(maps, field=field, z_field=field,
    ...)``, the most direct reading of "load distribution" requested
    in Section 8.5 of the plan: 3D relief colored by the field itself
    (``Fn`` default = normal load, that is, distributed thrust)."""
    return plot_disk_map_3d(maps, field=field, z_field=field, z_scale=z_scale,
                             cmap=cmap, plotter=plotter, fname=fname, window_size=window_size)


def plot_rotor_with_loads(geom, maps: dict, field: str = "Fn", profile=None, n_span: int = 40,
                           z_scale: float = 0.15, cmap: str = "plasma",
                           blade_color: str = "lightgray", plotter=None, fname=None,
                           window_size=(900, 700)):
    """Combined scene: 3D blade(s) (``plot_rotor_3d``) + extruded load
    map (``plot_load_distribution_3d``) in the same window, the
    overview requested for the "3D Viewer" tab (Section 8.5: "Rotor,
    blade, load distributions, wake (future)")."""
    plotter_out, owned, pv = _resolve_plotter(plotter, fname, window_size)
    plot_rotor_3d(geom, profile=profile, n_span=n_span, plotter=plotter_out, color=blade_color)
    plot_disk_map_3d(maps, field=field, z_field=field, z_scale=z_scale, cmap=cmap, plotter=plotter_out)
    return _finish(plotter_out, owned, fname)


# =============================================================================
# Light self-test (mesh builders only: pure NumPy, runs even without PyVista)
# =============================================================================
#
# Does not replace real tests (pytest — backlog item, along with the rest
# of the suite, see next phase). It only serves as a quick smoke-check of
# the geometric builders when running this file directly.

if __name__ == "__main__":
    from dataclasses import dataclass, field as dc_field

    @dataclass
    class _FakeGeom:
        r_norm: list = dc_field(default_factory=lambda: [0.2, 0.5, 0.8, 1.0])
        chord_norm: list = dc_field(default_factory=lambda: [0.08, 0.07, 0.05, 0.03])
        twist_deg: list = dc_field(default_factory=lambda: [12.0, 6.0, 2.0, 0.0])
        n_blades: int = 4
        radius_m: float = 1.4

    geom = _FakeGeom()
    pts, faces = build_blade_surface(geom, n_span=10)
    assert pts.shape == (10 * 2, 3), pts.shape
    assert len(faces) == (10 - 1) * (2 - 1) * 5
    print(f"build_blade_surface OK: {pts.shape[0]} points, {len(faces)//5} faces")

    blades = build_rotor_disk(geom, n_span=10)
    assert len(blades) == geom.n_blades
    print(f"build_rotor_disk OK: {len(blades)} blades")

    fake_maps = {
        "R_DIM": np.outer(np.linspace(0.3, 1.4, 5), np.ones(8)),
        "PSI": np.outer(np.ones(5), np.linspace(0, 2 * np.pi, 8, endpoint=False)),
        "Fn": np.random.rand(5, 8),
    }
    X, Y, Z, values = build_disk_grid(fake_maps, field="Fn", z_field="Fn")
    assert X.shape == Y.shape == Z.shape == values.shape == (5, 9)  # +1: closes the azimuth
    X_raw, *_ = build_disk_grid(fake_maps, field="Fn", z_field="Fn", close_azimuth=False)
    assert X_raw.shape == (5, 8)
    print("build_disk_grid OK:", X.shape, "(raw:", X_raw.shape, ")")
    print("available_disk_fields:", available_disk_fields(fake_maps))

    print(f"is_available() [pyvista installed?]: {is_available()}")
    print("Smoke-check of mesh builders completed without errors.")
