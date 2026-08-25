"""
plots.py
========

2D plots. Each function receives data that is already prepared (it does
not call api.py or bemt.py) and draws into a supplied ``ax`` (used by the
GUI, embedded in a canvas) OR saves to ``fname`` (used by
``api.export_results``).

Convention: every function accepts ``ax=None, fname=None``. If ``ax`` is
supplied, it draws into it and returns that same ``ax`` (the GUI decides
when to call ``canvas.draw()``). If ``fname`` is supplied instead, it
creates a new figure, draws, saves to disk and closes the figure.
"""

from __future__ import annotations

import re
from typing import TYPE_CHECKING

if TYPE_CHECKING:   # annotation only: a real import here would be circular
    from ..models import Results

import numpy as np
import matplotlib
matplotlib.use("Agg")  # safe backend for headless/export use; the GUI uses its own Qt canvas
import matplotlib.pyplot as plt
import matplotlib.tri as mtri
from matplotlib.colors import ListedColormap, LogNorm
from matplotlib.figure import Figure
from matplotlib.ticker import FuncFormatter

from .. import nomenclature
from ..viz import style as plot_style
plot_style.apply()

# Light-gray color used to "fill" (never leave empty or white) the regions
# masked by reverse flow, both in the disk contour plots and in the line
# plots against span or azimuth. See `_shade_reverse_regions` and the
# masking block in `plot_disk_map`.
_REVERSE_MASK_COLOR = "0.85"

# DPI used only when a function saves a figure. The GUI can change this
# value for a whole export without affecting the interactive canvases.
_EXPORT_DPI = 150


def set_export_dpi(dpi: int) -> None:
    """Sets the resolution of the figures saved by the exporter."""
    global _EXPORT_DPI
    _EXPORT_DPI = max(48, int(dpi))


def _new_figure(figsize, nrows: int = 1, ncols: int = 1):
    """Creates a ``Figure`` OUTSIDE pyplot's global registry.

    `plt.subplots` keeps the figure in pyplot's manager, and it only
    leaves it via `plt.close`. The functions in this module that RETURN
    the figure (for the GUI to embed in a canvas) could never close it.
    Therefore every redraw of the Results tab leaked an 11- or 16-panel
    figure, which pyplot kept alive forever ("More than 20 figures have
    been opened" after approximately 20 plot changes, with memory and
    time growing with session use). A `Figure` built directly does not
    enter any registry: Python's garbage collector reclaims it once
    nothing references it anymore, and `fig.savefig` still works the
    same way.
    """
    fig = Figure(figsize=figsize)
    axes = fig.subplots(nrows, ncols) if (nrows, ncols) != (1, 1) else fig.add_subplot(111)
    return fig, axes


def _resolve_ax(ax, fname, figsize=(6, 4)):
    if ax is not None:
        return ax, None
    fig, ax = _new_figure(figsize)
    return ax, fig


def _finish(ax, fig, fname):
    if fname is not None and fig is not None:
        fig.tight_layout()
        fig.savefig(fname, dpi=_EXPORT_DPI)
    return ax


def plot_geometry(geom, ax=None, fname=None):
    """geom: models.RotorGeometryDef"""
    ax, fig = _resolve_ax(ax, fname)
    ax.plot(geom.r_norm, geom.chord_norm, "o-", label="chord (c/R)")
    ax2 = ax.twinx()
    ax2.plot(geom.r_norm, geom.twist_deg, "s--", color="tab:orange", label="twist (°)")
    ax.set_xlabel("r/R")
    ax.set_ylabel("chord c/R")
    ax2.set_ylabel("twist [deg]")
    ax.set_title("Blade geometry")
    lines1, labels1 = ax.get_legend_handles_labels()
    lines2, labels2 = ax2.get_legend_handles_labels()
    ax.legend(lines1 + lines2, labels1 + labels2, loc="best", fontsize=8)
    return _finish(ax, fig, fname)


def plot_planform(geom, ax=None, fname=None, show_hub=True, show_tip_circle=True):
    """geom: models.RotorGeometryDef

    Planform outline (top view) of ALL ``geom.n_blades`` blades of the
    rotor, with leading edge and trailing edge plus closure at the root
    and at the tip of each blade. It uses the same azimuth convention as
    the rest of the platform (psi=0 along +X, blades equally spaced at
    ``360/n_blades`` degrees; see ``bemt.element_state``/
    ``visualization.py``).

    Unlike ``plot_geometry`` (which only shows the chord MAGNITUDE as a
    function of r/R, a single curve regardless of how many blades exist),
    this plot draws the actual outline of each blade. Therefore,
    ``geom.n_blades`` visibly changes the drawing (2 blades give 2
    opposite outlines, 4 blades give 4 outlines at 90°, and so on), which
    is useful for checking interference or overlap between neighboring
    blades in rotors with large chord or few blades."""
    ax, fig = _resolve_ax(ax, fname, figsize=(5, 5))
    r = np.asarray(geom.r_norm, dtype=float)
    chord = np.asarray(geom.chord_norm, dtype=float)
    n_blades = max(int(geom.n_blades), 1)
    thetas = np.linspace(0, 2 * np.pi, n_blades, endpoint=False)

    for i, th in enumerate(thetas):
        x_le = r * np.cos(th) - chord / 2 * np.sin(th)
        y_le = r * np.sin(th) + chord / 2 * np.cos(th)
        x_te = r * np.cos(th) + chord / 2 * np.sin(th)
        y_te = r * np.sin(th) - chord / 2 * np.cos(th)
        color = f"C{i % 10}"
        ax.plot(x_le, y_le, "-", color=color, linewidth=1.5)
        ax.plot(x_te, y_te, "-", color=color, linewidth=1.5)
        ax.plot([x_le[0], x_te[0]], [y_le[0], y_te[0]], "-", color=color, linewidth=1.5)   # closes at the root
        ax.plot([x_le[-1], x_te[-1]], [y_le[-1], y_te[-1]], "-", color=color, linewidth=1.5)  # closes at the tip

    circle = np.linspace(0, 2 * np.pi, 100)
    if show_tip_circle:
        ax.plot(np.cos(circle), np.sin(circle), "--", color="gray", linewidth=0.7)
    if show_hub and r.min() > 1e-6:
        ax.plot(r.min() * np.cos(circle), r.min() * np.sin(circle), ":", color="lightgray", linewidth=0.7)

    ax.set_aspect("equal", adjustable="box")
    ax.set_xlabel("x/R")
    ax.set_ylabel("y/R")
    ax.set_title(f"Planform. {n_blades} blade(s)")
    return _finish(ax, fig, fname)


def plot_chord_twist_distribution(geom, ax=None, fname=None):
    """geom: models.RotorGeometryDef

    Normalized chord (left) and twist in degrees (right), two Y axes
    sharing the X axis (r/R), read directly from
    ``geom.r_norm``/``chord_norm``/``twist_deg``, without recomputing
    anything (docs/plano_v3.md Part 6.1). Used by the "Chord/Twist" tab of
    the embedded Geometry canvas. It is equivalent in content to
    ``plot_geometry``, but with a name and use dedicated to the live
    canvas (``plot_geometry`` still exists, used by the exportable report
    and by legacy calls)."""
    ax, fig = _resolve_ax(ax, fname)
    ax.plot(geom.r_norm, geom.chord_norm, "o-", color="tab:blue", label="chord (c/R)")
    ax2 = ax.twinx()
    ax2.plot(geom.r_norm, geom.twist_deg, "s--", color="tab:orange", label="twist (°)")
    ax.set_xlabel("r/R")
    ax.set_ylabel("chord c/R", color="tab:blue")
    ax2.set_ylabel("twist [deg]", color="tab:orange")
    ax.set_title("Chord / Twist vs r/R")
    lines1, labels1 = ax.get_legend_handles_labels()
    lines2, labels2 = ax2.get_legend_handles_labels()
    ax.legend(lines1 + lines2, labels1 + labels2, loc="best", fontsize=8)
    return _finish(ax, fig, fname)


def plot_rotor_3d(geom, ax=None, fname=None):
    """Draws the rotor's three-dimensional geometry without depending on PyVista."""
    if ax is None:
        fig = Figure(figsize=(6, 5))
        ax = fig.add_subplot(111, projection="3d")
    else:
        fig = None
    from mpl_toolkits.mplot3d.art3d import Poly3DCollection
    from . import visualization
    for points, faces in visualization.build_rotor_disk(geom, n_span=32):
        vertices = np.asarray(points)[np.asarray(faces).reshape(-1, 5)[:, 1:]]
        ax.add_collection3d(Poly3DCollection(vertices, alpha=0.85,
                                               facecolor="steelblue",
                                               edgecolor="none"))
    radius = float(geom.radius_m)
    ax.set_xlim(-radius, radius); ax.set_ylim(-radius, radius); ax.set_zlim(-radius * .25, radius * .25)
    ax.set_xlabel("x [m]"); ax.set_ylabel("y [m]"); ax.set_zlabel("z [m]", labelpad=-8)
    ax.set_title("Rotor blade geometry in 3D")
    return _finish(ax, fig, fname)


def plot_profile(profile_geometry, ax=None, fname=None):
    """profile_geometry: models.ProfileGeometry"""
    ax, fig = _resolve_ax(ax, fname, figsize=(6, 2.5))
    ax.plot(profile_geometry.x, profile_geometry.y, "-")
    ax.set_aspect("equal", adjustable="box")
    ax.set_xlabel("x/c")
    ax.set_ylabel("y/c")
    ax.set_title(f"Profile ({profile_geometry.source})")
    return _finish(ax, fig, fname)


def plot_polar(alpha_deg, cl, cd, ax=None, fname=None, label=None,
               reynolds=None, mach=None):
    """Cl(alpha) (solid line) and Cd(alpha) (dashed, same color) on a
    single polar, used by the embedded canvas of the Airfoil tab
    (docs/plano_v3.md Part 5) for the currently browsed condition."""
    ax, fig = _resolve_ax(ax, fname)
    # NeuralFoil exports one curve per (Re, Mach) pair. Accepting this
    # metadata here spares the GUI from having to build a generic legend
    # and guarantees that each curve carries its own aerodynamic condition.
    if isinstance(label, dict):
        reynolds = label.get("reynolds", reynolds)
        mach = label.get("mach", mach)
        label = label.get("label")
    elif isinstance(label, tuple) and len(label) == 3:
        label, reynolds, mach = label
    if reynolds is not None or mach is not None:
        parts = []
        if reynolds is not None:
            parts.append(f"Re={float(reynolds):.3g}")
        if mach is not None:
            parts.append(f"M={float(mach):.3g}")
        condition = ", ".join(parts)
        label = f"{label} ({condition})" if label else condition
    line, = ax.plot(alpha_deg, cl, "-", label=f"Cl · {label}" if label else r"$C_L$")
    ax.plot(alpha_deg, cd, "--", color=line.get_color(), alpha=0.6,
            label=f"Cd · {label}" if label else r"$C_D$")
    ax.set_xlabel(r"$\alpha$ [deg]")
    ax.set_ylabel(r"$C_L$, $C_D$")
    ax.set_title(r"Polar $C_L(\alpha)$ / $C_D(\alpha)$")
    ax.legend(fontsize=8)
    return _finish(ax, fig, fname)


def plot_cl_alpha(alpha_deg, cl, ax=None, fname=None, label=None):
    """C_L(alpha) alone, one of the 3 mini plot tabs of the Airfoil tab
    (docs/plano_v3.md Part 7, item 4: Cl x alpha / Cd x alpha / Cd x Cl
    in separate plots, with zoom via NavigationToolbar2QT)."""
    ax, fig = _resolve_ax(ax, fname)
    ax.plot(alpha_deg, cl, "-", label=label)
    ax.axhline(0, color="gray", linewidth=0.6, alpha=0.5)
    ax.set_xlabel(r"$\alpha$ [deg]")
    ax.set_ylabel(r"$C_L$")
    ax.set_title(r"$C_L \times \alpha$")
    if label:
        ax.legend(fontsize=8)
    return _finish(ax, fig, fname)


def plot_cd_alpha(alpha_deg, cd, ax=None, fname=None, label=None):
    """C_D(alpha) alone, see `plot_cl_alpha`."""
    ax, fig = _resolve_ax(ax, fname)
    ax.plot(alpha_deg, cd, "-", label=label)
    ax.set_xlabel(r"$\alpha$ [deg]")
    ax.set_ylabel(r"$C_D$")
    ax.set_title(r"$C_D \times \alpha$")
    if label:
        ax.legend(fontsize=8)
    return _finish(ax, fig, fname)


def plot_cd_cl(cl, cd, ax=None, fname=None, label=None):
    """Drag polar C_D x C_L alone, see `plot_cl_alpha`."""
    ax, fig = _resolve_ax(ax, fname)
    ax.plot(cl, cd, "-", label=label)
    ax.set_xlabel(r"$C_L$")
    ax.set_ylabel(r"$C_D$")
    ax.set_title(r"$C_D \times C_L$ (drag polar)")
    if label:
        ax.legend(fontsize=8)
    return _finish(ax, fig, fname)


def plot_performance(results_list, ax=None, fname=None):
    ax, fig = _resolve_ax(ax, fname)
    mu_x = [r.summary.get("mu_x", np.nan) for r in results_list]
    ct = [r.summary.get("CT", np.nan) for r in results_list]
    ax.plot(mu_x, ct, "o-")
    ax.set_xlabel(r"$\mu_x$")
    ax.set_ylabel(r"$C_T$")
    ax.set_title(r"Performance: $C_T$ x $\mu_x$")
    return _finish(ax, fig, fname)


_DISK_FIELD_META = {
    # field in maps -> (label in mathtext/LaTeX, MATLAB style, with
    # superscript and subscript and Greek letters, unit, is_angle?)
    "Fn":          (r"$F_n$", "N/m", False),
    "Ft":          (r"$F_t$", "N/m", False),
    "Cl":          (r"$C_L$", "-", False),
    "Cd":          (r"$C_D$", "-", False),
    "Vi":          (r"$V_i$", "m/s", False),
    "Up":          (r"$U_p$", "m/s", False),
    "Ut":          (r"$U_t$", "m/s", False),
    "W":           (r"$W$", "m/s", False),
    "alpha_eff":   (r"$\alpha$", "deg", True),
    "phi":         (r"$\phi$", "deg", True),
    "lambda_z_field": (r"$\lambda$", "-", False),
    "lambda_i":    (r"$\lambda_i$", "-", False),
    "Mach":        (r"$M$", "-", False),
    "Ft_i":        (r"$F_{t,i}$", "N/m", False),
    "Ft_p":        (r"$F_{t,p}$", "N/m", False),
    "q":           (r"$q$", "Pa", False),
}


#: Same symbol as `_DISK_FIELD_META`, in HTML instead of mathtext, for
#: whoever does NOT draw with matplotlib (the "Field" combo of the Results
#: tab, which paints the item with a `QTextDocument`, see
#: `gui/tabs/results.py`). It exists separately because converting
#: mathtext back to HTML is a source of silent bugs; the source of truth
#: for the SET of fields is still `_DISK_FIELD_META` (a new key with no
#: entry here falls back to its own name).
_DISK_FIELD_HTML = {
    "Fn": "F<sub>n</sub>", "Ft": "F<sub>t</sub>",
    "Cl": "C<sub>L</sub>", "Cd": "C<sub>D</sub>",
    "Vi": "V<sub>i</sub>", "Up": "U<sub>p</sub>", "Ut": "U<sub>t</sub>",
    "W": "W", "alpha_eff": "&alpha;", "phi": "&phi;",
    "lambda_z_field": "&lambda;", "lambda_i": "&lambda;<sub>i</sub>",
    "Mach": "M", "Ft_i": "F<sub>t,i</sub>", "Ft_p": "F<sub>t,p</sub>",
    "q": "q",
}


def disk_field_symbol_html(field: str) -> str:
    """Short HTML symbol of a disk-map field (``"F<sub>n</sub>"``
    for ``"Fn"``); the field's own name when not cataloged."""
    return _DISK_FIELD_HTML.get(field, field)


def disk_field_label(field: str) -> str:
    """MATHTEXT symbol of a disk-map field (``r"$\\lambda_i$"``
    for ``"lambda_i"``); the field's own name when not cataloged.

    Companion to `disk_field_symbol_html` for whoever DRAWS with
    matplotlib. The 2D maps already read `_DISK_FIELD_META` directly,
    the 3D view did not, and so it showed `snake_case` where the rest of
    the tab shows the symbol."""
    return _DISK_FIELD_META.get(field, (field, "-", False))[0]


def disk_field_unit(field: str) -> str:
    """Unit of a disk-map field (``"-"`` when dimensionless)."""
    return _DISK_FIELD_META.get(field, (field, "-", False))[1]


def describe_condition(maps: dict) -> str:
    """Short description of the FLIGHT CONDITION from ``maps`` (mathtext).

    Exists because the condition title started appearing ONCE per
    figure, no longer once per disk (user request: with 16 disks on a
    single page, one title would touch the disk above it). Each
    individual disk map now only identifies its variable in the color
    bar; the condition becomes the figure's overall title.
    """
    def _num(key):
        value = maps.get(key)
        if not isinstance(value, (int, float)) or isinstance(value, bool):
            return None
        value = float(value)
        return None if np.isnan(value) else value

    parts = []
    mu_x = _num("mu_x")
    if mu_x is not None:
        parts.append(rf"$\mu_x$={mu_x:.3f}")
    # Vz and alpha describe the SAME axial component via two paths. They
    # only enter when nonzero, otherwise they clutter every hover title.
    vv = _num("Vz")
    if vv is not None and abs(vv) > 1e-9:
        parts.append(rf"$V_v$={vv:.3g} m/s")
    alpha = _num("alpha_rotor_deg")
    if alpha is not None and abs(alpha) > 1e-9:
        parts.append(rf"$\alpha$={alpha:.2f}°")
    # Collective and RPM enter WHENEVER they exist: they are the two
    # controls the user actually moved, and without them the title of a
    # hover case was just "mu_x=0.000", identical for every hover in
    # the project, which made it impossible to say which sweep the
    # figure came from.
    collective = _num("collective_deg")
    if collective is not None:
        parts.append(rf"$\theta_0$={collective:.2f}°")
    rpm = _num("rpm")
    if rpm is not None:
        parts.append(rf"{rpm:.0f} rpm")
    # In a trimmed case, the target is what defines the condition (the
    # collective/RPM above is a RESULT of the trim, not an input). Saying
    # what the target was prevents reading a resolved collective as if it
    # had been chosen.
    ct = _num("CT")
    if ct is not None and maps.get("trim_mode"):
        parts.append(rf"$C_T$={ct:.5f}")
    return ", ".join(parts)


def _disk_field_array(maps: dict, field: str) -> np.ndarray:
    """Resolves a plot field from `maps`, covering the ones that do not
    exist as a direct array (Vi=dimensional induced velocity,
    lambda_z_field=lambda_total, already present as `lambda_total`)."""
    if field == "Vi":
        lam_i = np.asarray(maps["lambda_i"], dtype=float)
        OmegaR = maps.get("OmegaR")
        if OmegaR is None:
            Up = np.asarray(maps["Up"], dtype=float)
            lam_c = float(maps.get("lambda_z", 0.0))
            denom = lam_i + lam_c
            OmegaR = Up / np.where(np.abs(denom) < 1e-9, 1.0, denom)
        return lam_i * OmegaR
    if field == "lambda_z_field":
        return np.asarray(maps["lambda_total"], dtype=float)
    if field == "q":
        W = np.asarray(maps["W"], dtype=float)
        rho = float(maps["rho"])
        return 0.5 * rho * W ** 2
    return np.asarray(maps[field], dtype=float)


#: `zorder` of the field drawing (`tricontourf`) in a disk map. The
#: radius guide circles need to stay ABOVE it: drawn below, they existed
#: in the figure and did not appear on any disk, because the filled
#: contour paints over anything at a lower zorder.
_ZORDER_FIELD = 2
_ZORDER_GUIDES = _ZORDER_FIELD + 1


def _add_r_guides(ax, r_max, fractions=(0.25, 0.5, 0.75)):
    """DASHED guide circles, thin and unlabeled, at r/R=0.25/0.5/0.75
    (visual orientation only: they say at what radius a field feature is,
    with no legend or annotation).

    They live at `_ZORDER_GUIDES`, that is, ABOVE the field's
    `tricontourf`. Previously they were drawn at zorder 1, below the
    contour, and the fill covered them completely on EVERY disk (the `show_r_guides`
    parameter existed but had no visible effect). They are artists of the
    disk's axis: they do not enter the color bar nor touch the data
    range."""
    theta = np.linspace(0, 2 * np.pi, 200)
    for frac in fractions:
        rr = frac * r_max
        ax.plot(rr * np.cos(theta), rr * np.sin(theta),
                linestyle=(0, (4, 3)), linewidth=0.6, color="0.30", alpha=0.40,
                zorder=_ZORDER_GUIDES)


def _shade_reverse_regions(ax, x: np.ndarray, reverse_mask: np.ndarray,
                            color: str = _REVERSE_MASK_COLOR, alpha: float = 0.6,
                            zorder: float = 0.0):
    """Shades in light gray the stretches of ``x`` (assumed sorted, not
    necessarily uniform) where ``reverse_mask`` is True. It is used to
    mark reverse flow (``Ut<0``) in LINE plots against span or azimuth,
    in the same spirit as the masking of the disk contour plots (see
    ``plot_disk_map``): the "masked" region is filled with light gray,
    never left empty or white. Detects the contiguous stretches of
    ``reverse_mask`` and draws a gray ``axvspan`` for each one (low
    zorder, so it stays behind the data curve)."""
    idx = np.where(reverse_mask)[0]
    if idx.size == 0:
        return
    splits = np.where(np.diff(idx) > 1)[0] + 1
    for seg in np.split(idx, splits):
        if seg.size == 0:
            continue
        i0, i1 = int(seg[0]), int(seg[-1])
        ax.axvspan(x[i0], x[i1], color=color, alpha=alpha, zorder=zorder, linewidth=0)


def _close_azimuth_2d(PSI: np.ndarray, *fields_2d: np.ndarray):
    """Closes the azimuth periodicity by duplicating the psi=0 column at
    psi=2*pi (see the full rationale in visualization._close_azimuth).
    Without this, tricontourf triangulates through the [psi_last, 2*pi)
    slice with no data point there, producing the "white gap" and
    incorrect interpolation artifact that can appear in that slice or
    spread to neighboring slices depending on the local aspect ratio of
    the mesh triangulated by Delaunay."""
    psi0 = PSI[:, :1]
    PSI_closed = np.concatenate([PSI, psi0 + 2.0 * np.pi], axis=1)
    closed = tuple(np.concatenate([f, f[:, :1]], axis=1) for f in fields_2d)
    return (PSI_closed,) + closed


#: How many times the tail needs to exceed the body of the data for the
#: color scale to be clipped. 5x is deliberately generous: a field with a
#: strong but continuous gradient (Ut, W) passes through untouched; only
#: the pathological case triggers it, where half a dozen singular
#: elements push the maximum to another order of magnitude.
_EXTREME_TAIL_FACTOR = 5.0

#: Percentiles that define the "body" of the data.
_PERCENTILE_LOW, _PERCENTILE_HIGH = 0.5, 99.5


def _robust_color_range(z_finite, lo: float, hi: float):
    """Clips the color scale when a few singular elements dominate it.
    Returns ``(lo, hi, extend)``.

    Reason, seen on screen: in a case whose tip Mach exceeds 1 on the
    advancing blade, the compressibility correction divides Cl by
    sqrt(1-M^2) -> ~0 in TWO elements out of 7776. The maximum Cl jumped
    from 2.5 (99th percentile) to 599, and the color scale stretched by
    these two points painted the ENTIRE disk in the same color: four of
    the sixteen grid panels turned into a uniform purple rectangle with
    one yellow pixel. The data was not wrong in the file. It was
    illegible on screen.

    Clipping here is a DRAWING decision, not a data one: ``maps`` is not
    touched, and the color bar gets the "continues beyond this value"
    arrow (``extend``), so the clipping is visible rather than silent.
    Whoever wants the full range supplies ``vmin``/``vmax``.
    """
    if z_finite.size < 20:
        return lo, hi, ""
    p_lo, p_high = np.percentile(z_finite, [_PERCENTILE_LOW, _PERCENTILE_HIGH])
    body = p_high - p_lo
    if not np.isfinite(body) or body <= 0:
        return lo, hi, ""
    clip_high = (hi - p_high) > _EXTREME_TAIL_FACTOR * body
    clip_low = (p_lo - lo) > _EXTREME_TAIL_FACTOR * body
    if not (clip_high or clip_low):
        return lo, hi, ""
    new_lo = float(p_lo) if clip_low else lo
    new_hi = float(p_high) if clip_high else hi
    extend = ("both" if (clip_high and clip_low)
              else ("max" if clip_high else "min"))
    return new_lo, new_hi, extend


def _colorbar_axis(ax, r_max: float, compact: bool):
    """Creates the color bar's axis (``cax``) WITHIN the right margin of
    the disk's own axis, with the SAME HEIGHT as the disk.

    Why not `fig.colorbar(..., ax=ax, shrink=...)`: `shrink` is a
    fraction of the axis's ORIGINAL box (the subplot's), not the box
    already adjusted by `set_aspect("equal", adjustable="box")`. The disk
    occupies only part of that box (the x range is larger than the y one,
    to fit the azimuth label and the bar), so the bar came out visibly
    taller than the disk drawing. The reported defect: "the color bar
    is much taller than the disk and wastes height".

    `Axes.inset_axes` solves this because it positions the child via a
    locator evaluated AT DRAW TIME, as a fraction of the box already
    adjusted by the aspect ratio: asking for the y range from -r_max to
    +r_max returns exactly the disk's height, whatever the figsize or the
    grid cell.

    The bar lives in the gap between the right azimuth label and the
    axis limit, and the bar's numbers grow to the right within that same
    gap (see `right_margin` in `plot_disk_map`).
    """
    x0, x1 = ax.get_xlim()
    y0, y1 = ax.get_ylim()
    def fx(x):
        return (x - x0) / (x1 - x0)
    def fy(y):
        return (y - y0) / (y1 - y0)
    # In the grid, the "Adv." legend ends near 1.35R. The bar used to
    # start at 1.40R and the two texts overlapped on the resized canvas.
    left = (1.55 if compact else 1.50) * r_max
    width = (0.10 if compact else 0.09) * r_max
    return ax.inset_axes([fx(left), fy(-r_max),
                          fx(x0 + width) - fx(x0), fy(r_max) - fy(-r_max)])


def plot_disk_map(maps: dict, field: str = "lambda_i", ax=None, fname=None,
                   cmap: str = "viridis", show_r_guides: bool = True,
                   mask_reverse: bool = True, log_color: bool = False,
                   vmin: float | None = None, vmax: float | None = None,
                   compact: bool = False, cbar_label: str | None = None,
                   levels=None):
    """Disk map in the SAME visual reference frame as the zBEMT MATLAB
    (v30): psi=0 (Ut=Omega*r, no advance contribution) plotted DOWN
    ("Back"/aft), psi=90 (max Ut, advancing blade) to the RIGHT
    ("Adv"), psi=180 UP ("Front"/nose) and psi=270 (retreating)
    to the LEFT, equivalent to rotating the polar angle by -90
    degrees before converting to Cartesian (same
    `theta_for_pol2cart = PSI - pi/2` as MATLAB).

    Closes the azimuthal periodicity (see `_close_azimuth_2d`) before
    triangulating: without this, `tricontourf` produced a "white slice"
    artifact from missing data coverage in the last sampled slice of the
    (Ne,Npsi) grid, which does not repeat the node at psi=2*pi.

    `mask_reverse` (default True, same behavior as the zBEMT MATLAB
    `params.mask_reverse_flow_plots`): masks ONLY THE DRAWING (never the
    data in `maps`) in the regions where `Ut<0` (reverse flow), because
    the Cl/Cd model changes abruptly there and the contour ends up with
    visually crazy transitions. Implemented by masking the
    TRIANGLES of the triangulation that touch any node in reverse flow
    (via `matplotlib.tri`), instead of simply throwing NaN into the Z
    array (which matplotlib's `tricontourf` does not accept directly).
    The masked region is filled with a light gray (`_REVERSE_MASK_COLOR`)
    instead of being left empty or white, so it is not confused with
    "no data".

    `log_color`/`vmin`/`vmax`: the COLOR scale (not the x/y axes; those
    are already zoomable via `NavigationToolbar2QT`, see `gui.CanvasHost`).
    `NavigationToolbar2QT` does not know how to edit the range/scale of the
    color of a `tricontourf` (it only handles `AxesImage`, not
    `QuadContourSet`), so this control is explicitly exposed here and in
    the GUI (Results, "Disk map" block). `log_color=True` silently falls
    back to linear if the field has no positive value at all (LogNorm
    requires vmin>0).

    `show_r_guides` (default True): three thin dashed circles at
    r/R=0.25/0.5/0.75, with no label or legend, to say at a glance at
    what radius a field feature is, see `_add_r_guides`. They are
    artists of the axis: they do not appear in the color bar nor change
    the data range.

    `cbar_label`: bar label text, for when the default ("symbol
    [unit]" from `_DISK_FIELD_META`) does not fit. This is the case for
    DIAGNOSTIC fields, which are not physical quantities cataloged there
    (the iteration count of `plot_convergence`). `levels`: explicit
    contour levels, for discrete fields (same origin).

    The color bar has the HEIGHT OF THE DISK and lives in the right
    margin of the axis itself, see `_colorbar_axis`.
    """
    ax, fig = _resolve_ax(ax, fname, figsize=(5.5, 5.5))
    R_NORM, PSI = np.asarray(maps["R_NORM"], dtype=float), np.asarray(maps["PSI"], dtype=float)
    Z = _disk_field_array(maps, field)
    is_angle = _DISK_FIELD_META.get(field, (None, None, False))[2]
    if is_angle:
        Z = np.degrees(Z)

    do_mask = mask_reverse and ("Ut" in maps)
    if do_mask:
        reverse_node = (np.asarray(maps["Ut"], dtype=float) < 0.0).astype(float)
        PSI_c, R_NORM_c, Z_c, reverse_c = _close_azimuth_2d(PSI, R_NORM, Z, reverse_node)
        reverse_c = reverse_c > 0.5
    else:
        PSI_c, R_NORM_c, Z_c = _close_azimuth_2d(PSI, R_NORM, Z)
        reverse_c = None

    theta_plot = PSI_c - np.pi / 2
    X = R_NORM_c * np.cos(theta_plot)
    Y = R_NORM_c * np.sin(theta_plot)

    # Resolves the color scale's levels/norm (linear by default, same as
    # before; explicit log or vmin/vmax override it).
    z_finite = Z_c[np.isfinite(Z_c)]
    lo = float(vmin) if vmin is not None else (float(np.min(z_finite)) if z_finite.size else 0.0)
    hi = float(vmax) if vmax is not None else (float(np.max(z_finite)) if z_finite.size else 1.0)
    auto_extend = ""
    if vmin is None and vmax is None:
        lo, hi, auto_extend = _robust_color_range(z_finite, lo, hi)
    if hi <= lo:
        hi = lo + 1e-9
    norm = None
    requested_levels = levels
    levels = 20
    extend = "neither"
    if log_color and lo <= 0.0:
        positive = z_finite[z_finite > 0] if z_finite.size else np.array([])
        lo = float(np.min(positive)) if positive.size else None
        log_color = log_color and lo is not None
    if log_color:
        lo = max(lo, 1e-12)
        norm = LogNorm(vmin=lo, vmax=hi)
        levels = np.geomspace(lo, hi, 21)
        extend = "both" if (vmin is not None or vmax is not None) else "neither"
    elif vmin is not None or vmax is not None:
        levels = np.linspace(lo, hi, 21)
        extend = "both"
    elif auto_extend:
        levels = np.linspace(lo, hi, 21)
        extend = auto_extend
    if requested_levels is not None:
        # Explicit levels from the caller override everything: they exist
        # for DISCRETE fields (iteration count in the convergence figure),
        # where 21 linear levels produce bands of "3.45 iterations".
        levels = requested_levels
        extend = "neither"

    contour_kwargs = dict(levels=levels, cmap=cmap, norm=norm, extend=extend)
    if reverse_c is not None:
        triang = mtri.Triangulation(X.ravel(), Y.ravel())
        node_reverse = reverse_c.ravel()
        # Masks the triangle if ANY of its 3 vertices are in reverse
        # flow. This leaves a clean "hole" in the region, like MATLAB's
        # NaN, without requiring NaN in the Z array itself (which
        # matplotlib's tricontourf rejects).
        tri_mask = np.any(node_reverse[triang.triangles], axis=1)

        # Before drawing the data field, fills the SAME masked region
        # (triangles in reverse flow) with light gray via the
        # COMPLEMENTARY mask on the same triangulation, so the "hole"
        # in the main contour is never left empty or white.
        if np.any(tri_mask):
            triang_reverse = mtri.Triangulation(X.ravel(), Y.ravel(), triangles=triang.triangles)
            triang_reverse.set_mask(~tri_mask)
            ax.tripcolor(triang_reverse, facecolors=np.zeros(triang.triangles.shape[0]),
                         cmap=ListedColormap([_REVERSE_MASK_COLOR]),
                         zorder=_ZORDER_FIELD - 1)

        triang.set_mask(tri_mask)
        cf = ax.tricontourf(triang, Z_c.ravel(), zorder=_ZORDER_FIELD, **contour_kwargs)
    else:
        cf = ax.tricontourf(X.ravel(), Y.ravel(), Z_c.ravel(),
                            zorder=_ZORDER_FIELD, **contour_kwargs)
    ax.set_aspect("equal", adjustable="box")
    label, unit, _ = _DISK_FIELD_META.get(field, (field, "-", False))
    # NO title per disk (see `describe_condition`): with many disks on the
    # same page, one title would touch the disk above it. The name of the
    # variable moves to the top LEFT corner of the color bar and the
    # unit to the top RIGHT corner (below, alongside the bar). The
    # condition becomes the figure's single title.

    r_max = float(np.nanmax(R_NORM))
    if show_r_guides:
        _add_r_guides(ax, r_max)
    # The azimuth labels sit OUTSIDE the disk, and the right one ("90° Adv")
    # grows toward the color bar. With the old margin (1.2*r_max
    # for text starting at 1.05) it touched the bar. The margin becomes
    # asymmetric: more slack on the right, where there is text and the
    # bar, and tight on the other sides, so the disk does not shrink for
    # no reason.
    # `compact`: in a grid panel the text occupies a much larger fraction
    # of the width, and "90° (Adv)" invaded the color bar. There, only the
    # sector name is worth it, because the angle is already implicit in
    # the position.
    if compact:
        label_kwargs = dict(fontsize=7, color="0.35")
        right, top, left, bottom = "Adv.", "Front", "Ret.", "Back"
    else:
        label_kwargs = dict(fontsize=8, color="0.15")
        right, top = r"90° (Adv.)", r"180° (Front)"
        left, bottom = r"270° (Ret.)", r"0° (Back)"
    ax.text(r_max * 1.06, 0, right, ha="left", va="center", **label_kwargs)
    ax.text(0, r_max * 1.06, top, ha="center", va="bottom", **label_kwargs)
    ax.text(-r_max * 1.06, 0, left, ha="right", va="center", **label_kwargs)
    ax.text(0, -r_max * 1.06, bottom, ha="center", va="top", **label_kwargs)
    # Reference cross limited to the disk (+10%): with `axhline`/`axvline`
    # it crossed the ENTIRE axis width, and the right margin now
    # hosts the color bar, so the line would go right under it.
    cross_len = 1.10 * r_max
    ax.plot([-cross_len, cross_len], [0, 0], color="0.6", linestyle=":", linewidth=0.6,
            zorder=_ZORDER_GUIDES)
    ax.plot([0, 0], [-cross_len, cross_len], color="0.6", linestyle=":", linewidth=0.6,
            zorder=_ZORDER_GUIDES)
    # The right margin now hosts the ENTIRE color bar (see
    # `_colorbar_axis`), not just the azimuth label: it needs to
    # fit the label ("90° (Adv.)"), the bar and its numbers. With the old
    # margin the bar's numbers spilled out of the axis and, in a grid,
    # invaded the neighboring cell. Widening in x does not shrink the disk
    # while the cell is limited by HEIGHT (which is the case both in the
    # grid and in the individual figure). What is gained is that the bar
    # no longer steals width.
    right_margin = 2.25 if compact else 1.95
    # The vertical margin has to fit the TEXT, not just the point where it
    # starts: "Front" begins at 1.06 with `va="bottom"`, so it rises
    # above that. With the old 1.22 it left the axis and ended up inside
    # the cell above. In the 16-disk grid the "Front" of one row
    # appeared stuck to the "Back" of the previous row, both cut in half.
    vertical_margin = 1.34 if compact else 1.28
    ax.set_xlim(-r_max * 1.25, r_max * right_margin)
    ax.set_ylim(-r_max * vertical_margin, r_max * vertical_margin)
    ax.set_aspect("equal", adjustable="box")
    ax.set_xticks([]); ax.set_yticks([])
    for spine in ax.spines.values():
        spine.set_visible(False)

    fig_to_use = fig if fig is not None else ax.figure
    if fig_to_use is not None:
        # The bar has the HEIGHT OF THE DISK and lives in the right margin
        # of the axis itself, see `_colorbar_axis` for why it is
        # not `colorbar(ax=..., shrink=...)`.
        cax = _colorbar_axis(ax, r_max, compact)
        cb = fig_to_use.colorbar(cf, cax=cax)
        cb.ax.tick_params(labelsize=7 if compact else 8)
        # Bar label: ALWAYS "symbol [unit]" in a single piece.
        bar_label = cbar_label if cbar_label is not None else (
            f"{label} [{unit}]" if unit and unit != "-" else label)
        if compact:
            # The label used to sit to the left of the bar and fall ON
            # the disk on compact screens. Above the bar itself there is
            # space between the grid rows, reserved by the figure layout.
            cb.ax.text(0.0, 1.02, bar_label, transform=cb.ax.transAxes,
                        ha="left", va="bottom", fontsize=7)
        else:
            # Single disk: there is no cell above to collide with, and
            # the top of the bar is the natural place for the label.
            cb.ax.text(0.0, 1.04, bar_label, transform=cb.ax.transAxes,
                        ha="left", va="bottom", fontsize=11)

    # Figure with a SINGLE disk (individual export or GUI canvas): the
    # condition is the figure's title. In a grid panel (`compact`) the
    # one setting the title is `plot_disk_map_grid`, once for all disks.
    if not compact and fig_to_use is not None:
        condition = describe_condition(maps)
        if condition:
            fig_to_use.suptitle(condition, fontsize=11, fontweight="bold")
    return _finish(ax, fig, fname)


# Fixed order/grouping of the fields requested for the full disk grid:
# forces, section aerodynamics, flow kinematics, angles, and the
# tangential-force decomposition + Mach/dynamic pressure, always in
# this order for visual comparability between runs. The last 4 (Ft_i,
# Ft_p, Mach, q) were added after the original 12 so as not to disturb
# the order or position for whoever was already comparing the first 12
# panels between runs.
_DISK_GRID_FIELDS = ["Fn", "Ft", "Cl", "Cd", "Vi", "Up",
                     "Ut", "W", "alpha_eff", "phi", "lambda_z_field", "lambda_i",
                     "Ft_i", "Ft_p", "Mach", "q"]


def plot_disk_map_grid(maps: dict, fields=None, fname=None, ncols: int = 4,
                        cmap: str = "viridis", figsize_per_panel: float = 3.2,
                        mask_reverse: bool = True):
    """Grid with ALL the important disk variables in a single panel:
    Fn, Ft, Cl, Cd, Vi, Up, Ut, W, alpha (deg), phi (deg), lambda (total),
    lambda_i (induced), see `_DISK_GRID_FIELDS`. Angles are always in
    degrees. Each subplot gets thin, unlabeled dotted guide circles
    at r/R=0.25/0.5/0.75 (visual orientation only).

    `fields`: custom list of fields (default: the 12 from
    `_DISK_GRID_FIELDS`). `fname`: if supplied, saves the figure and
    closes it; otherwise returns the `Figure` for interactive/embedded use.
    `mask_reverse`: passed through to each panel's `plot_disk_map` (see
    its docstring). Default True, the same default as `BEMTConfig.
    mask_reverse_flow_plots`.
    """
    fields = list(fields) if fields is not None else list(_DISK_GRID_FIELDS)
    n = len(fields)
    ncols = min(ncols, n)
    nrows = int(np.ceil(n / ncols))
    # Cell wider than tall: the disk's axis has equal aspect and the x
    # range is larger than the y one (extra room on the right for label
    # and bar), so a square cell left empty bands between the rows.
    fig, axes = _new_figure((figsize_per_panel * ncols,
                               figsize_per_panel * 0.86 * nrows), nrows, ncols)
    axes = np.atleast_1d(axes).ravel()

    # ONE condition title for the whole figure (not one per disk): each
    # disk identifies its variable in its own color bar, see
    # `plot_disk_map`/`describe_condition`.
    condition = describe_condition(maps)
    title = f"Disk maps — {condition}" if condition else "Disk maps"
    if mask_reverse:
        title += "  (reverse flow masked in plots)"
    fig.suptitle(title, fontsize=12, fontweight="bold")

    for i, field in enumerate(fields):
        try:
            plot_disk_map(maps, field=field, ax=axes[i], cmap=cmap,
                          mask_reverse=mask_reverse, compact=True)
        except (KeyError, ValueError):
            # Old results or specific models may not carry every optional
            # field. The consolidated panel should still be exported with
            # whatever fields are available, instead of disappearing
            # along with the individual maps.
            axes[i].axis("off")
    for j in range(n, len(axes)):
        axes[j].axis("off")

    # Layout RESOLVED ON EVERY DRAW, not just once.
    #
    # `tight_layout` computes the margins once, for the size in INCHES the
    # figure has at that instant (here, 12.8x11). The report saves
    # exactly at that size and comes out as planned. That is why the
    # same plot looked good in the report and broken in the GUI. In the
    # Results tab the figure goes into a `FigureCanvasQTAgg`, which
    # stretches it to the widget's size (~8x4.6 in, a different aspect
    # ratio); the margins stay the ones computed for 12.8x11, but the
    # fonts stay in POINTS and do not shrink along with it. Result: the
    # field label falling inside the disk and "Ret."/"Adv." colliding
    # with the color bar.
    #
    # The "constrained" engine reruns the calculation on every `draw`, so
    # the figure recomposes itself on every canvas resize.
    # The GUI canvas is shorter and narrower than the report's PNG. A minimal
    # gap made the suptitle invade the first row and the side labels
    # touch the color bar when the window was resized.
    fig.set_layout_engine("constrained")
    fig.get_layout_engine().set(h_pad=0.10, w_pad=0.06, hspace=0.10, wspace=0.06)
    if fname is not None:
        fig.savefig(fname, dpi=_EXPORT_DPI)
        plt.close(fig)
        return None
    return fig


def plot_solver_comparison(results_list, ax=None, fname=None):
    """results_list: output of studies.benchmark_solvers — each Results has
    maps['benchmark_solver'] and maps['benchmark_elapsed'] filled in.
    Compares execution time between solvers, side by side."""
    ax, fig = _resolve_ax(ax, fname)
    labels = [r.maps.get("benchmark_solver", r.condition_name) for r in results_list]
    elapsed = [r.maps.get("benchmark_elapsed", r.maps.get("elapsed", np.nan)) for r in results_list]
    ax.bar(labels, elapsed, color="tab:blue")
    ax.set_ylabel("execution time [s]")
    ax.set_title("Solver comparison")
    ax.tick_params(axis="x", rotation=30)
    return _finish(ax, fig, fname)


#: Color scale of the iteration map in the convergence figure. Sequential
#: and deliberately distinct from the `viridis` of the field maps: the
#: convergence disk is a solver DIAGNOSTIC, not a physical result, and the
#: reading "the hotter, the more it cost" is immediate.
_CMAP_ITERATIONS = "YlOrRd"

#: Color of the elements that did NOT converge, marked on top of the map.
_COLOR_NOT_CONVERGED = "#1f4ed8"


def _convergence_summary(results: "Results") -> dict:
    """Header numbers of the convergence figure, taken from `summary`
    when they exist and recomputed from the maps when they do not (old
    exports and hand-built `Results` have one or the other, it never
    fails for lack of a key)."""
    maps = results.maps or {}
    summary = results.summary or {}
    converged = np.asarray(maps["converged"], dtype=bool) if "converged" in maps else None
    n_iter = np.asarray(maps["n_iter"], dtype=float) if "n_iter" in maps else None

    pct = summary.get("convergence_pct")
    if pct is None and converged is not None and converged.size:
        pct = 100.0 * float(np.mean(converged))
    mean = summary.get("mean_iter")
    if mean is None and n_iter is not None and n_iter.size:
        mean = float(np.mean(n_iter))
    return dict(
        pct=None if pct is None else float(pct),
        mean=None if mean is None else float(mean),
        max=None if n_iter is None or not n_iter.size else int(np.max(n_iter)),
        n_elements=None if converged is None else int(converged.size),
        n_failed=None if converged is None else int(np.count_nonzero(~converged)),
        solver=summary.get("solver") or maps.get("solver"),
        sweeps=maps.get("total_iterations"),
        elapsed=summary.get("elapsed_s", maps.get("elapsed")),
    )


def _format_time(seconds) -> str:
    """Time in ms/s according to the order of magnitude (a solver that
    runs in 5 ms should not appear as "0.005 s")."""
    try:
        s = float(seconds)
    except (TypeError, ValueError):
        return "—"
    return f"{s * 1e3:.0f} ms" if s < 1.0 else f"{s:.2f} s"


def _number_cards(ax, cards):
    """Row of "cards" (large value on top, small label below) on a
    frameless axis -- where the convergence figure's header numbers live.

    Replaces the two percentage BARS that used to take up the whole
    figure: a "98.5%" bar next to a "7 iterations" one compares
    nothing (different quantities, different scales). It spends the
    whole figure and says less than the number itself written out."""
    from matplotlib.patches import FancyBboxPatch

    ax.set_axis_off()
    ax.set_xlim(0, 1); ax.set_ylim(0, 1)
    n = max(len(cards), 1)
    card_width = 1.0 / n
    # Font proportional to the REAL width of each card: the same figure
    # is generated at 11 inches (report) and at 6 (GUI canvas), and at a
    # fixed size the labels of neighboring cards overlapped in the GUI.
    inch_per_card = ax.figure.get_figwidth() * ax.get_position().width / n
    font_value = float(np.clip(13.0 * inch_per_card / 1.6, 8.0, 13.0))
    font_label = float(np.clip(7.5 * inch_per_card / 1.6, 5.5, 7.5))
    for i, (value, label_text, color) in enumerate(cards):
        x0 = i * card_width
        ax.add_patch(FancyBboxPatch(
            (x0 + 0.012, 0.10), card_width - 0.024, 0.80,
            boxstyle="round,pad=0,rounding_size=0.04",
            transform=ax.transAxes, facecolor="0.965", edgecolor="0.86",
            linewidth=0.8, clip_on=False, zorder=0))
        center = x0 + card_width / 2
        ax.text(center, 0.56, value, ha="center", va="center",
                fontsize=font_value, fontweight="bold", color=color, zorder=1)
        ax.text(center, 0.26, label_text, ha="center", va="center",
                fontsize=font_label, color="0.35", zorder=1)


def _convergence_layout(ax, fname, with_disk: bool, with_history: bool):
    """Assembles the convergence figure (disk | history / numbers) from
    the `ax` the caller supplied, or from a new figure.

    The GUI and the report call `plot_convergence` the usual way
    (`ax=fig.add_subplot(111)` or `fname=...`), and this signature does
    not change. Since the figure now has more than one panel, the
    received `ax` is replaced by panels created in the SAME grid spot
    (`get_subplotspec().subgridspec`), instead of requiring every caller
    to know how to assemble the layout (it would be the same code
    repeated in the GUI, in the report and in the tests). An `ax` with no
    `subplotspec` (created via `fig.add_axes`) falls back to the
    whole-figure path.
    """
    if ax is None:
        fig_width = 11.0 if with_disk else 7.0
        # Without a disk and without history, all that is left is the
        # card row: a tall figure would be almost all empty space.
        fig_height = 4.4 if (with_disk or with_history) else 2.2
        fig = Figure(figsize=(fig_width, fig_height))
        spec = fig.add_gridspec(1, 1)[0, 0]
    else:
        fig = ax.figure
        spec = ax.get_subplotspec()
        ax.remove()
        if spec is None:
            spec = fig.add_gridspec(1, 1)[0, 0]

    if with_disk:
        outer = spec.subgridspec(1, 2, width_ratios=[1.0, 1.25], wspace=0.30)
        ax_disk = fig.add_subplot(outer[0, 0])
        column = outer[0, 1]
    else:
        ax_disk = None
        column = spec

    if with_history:
        inner = column.subgridspec(2, 1, height_ratios=[3.2, 1.0], hspace=0.55)
        ax_hist = fig.add_subplot(inner[0, 0])
        ax_num = fig.add_subplot(inner[1, 0])
    else:
        # Without history, the card row remains a ROW: if it occupied
        # the whole column, four giant rectangles with one number each
        # would take up half the figure.
        inner = column.subgridspec(3, 1, height_ratios=[1.0, 1.1, 1.0])
        ax_hist = None
        ax_num = fig.add_subplot(inner[1, 0])
    return fig, ax_disk, ax_hist, ax_num


def _draw_convergence_disk(ax, maps: dict):
    """Disk map of the NUMBER OF ITERATIONS per element, with the
    non-converged elements marked on top.

    This is the actionable diagnostic: the difficult elements are not
    scattered at random. They concentrate at the root, at the tip and
    at the reverse-flow boundary, and that is what tells you where to act
    (mesh, relaxation, model). A global percentage does not localize
    anything.

    Without `mask_reverse`: precisely the reverse-flow region is one of
    the ones that costs the solver most, and hiding it here would erase
    half the answer.
    """
    n_iter = np.asarray(maps["n_iter"], dtype=float)
    # Iteration count is DISCRETE: one color band per integer value,
    # and bar ticks on the integers themselves. With the default's 21
    # linear levels the bar announced "3.45 iterations".
    n_lo = int(np.floor(np.nanmin(n_iter))) if n_iter.size else 0
    n_hi = int(np.ceil(np.nanmax(n_iter))) if n_iter.size else 1
    level_grid = np.arange(n_lo - 0.5, n_hi + 1.0, 1.0)
    plot_disk_map(maps, field="n_iter", ax=ax, cmap=_CMAP_ITERATIONS,
                  mask_reverse=False, compact=True,
                  cbar_label="iterations",
                  levels=level_grid if level_grid.size >= 2 else None)
    ax.set_title("Iterations per element", fontsize=9, color="0.25")
    if ax.child_axes:
        ax.child_axes[0].set_yticks(np.arange(n_lo, n_hi + 1, max(1, (n_hi - n_lo) // 8 + 1)))

    converged = np.asarray(maps["converged"], dtype=bool) if "converged" in maps else None
    if converged is None or converged.all():
        return
    R_NORM = np.asarray(maps["R_NORM"], dtype=float)
    PSI = np.asarray(maps["PSI"], dtype=float)
    theta = PSI - np.pi / 2
    failed = ~converged
    ax.plot(R_NORM[failed] * np.cos(theta[failed]),
            R_NORM[failed] * np.sin(theta[failed]),
            linestyle="none", marker="o", markersize=2.6,
            color=_COLOR_NOT_CONVERGED, zorder=_ZORDER_GUIDES + 1,
            label="not converged")
    ax.legend(loc="upper left", fontsize=7, frameon=True, framealpha=0.85,
              borderpad=0.3, handletextpad=0.3)


def plot_convergence(results: "Results", ax=None, fname=None):
    """Convergence diagnostic of the inflow solver, in three pieces:

    1. WHERE the solver struggled: disk map of the number of iterations
       per element, with the non-converged elements marked
       (`_draw_convergence_disk`). Only appears when the result
       carries the maps (`n_iter`/`R_NORM`/`PSI`).
    2. HOW it progressed: converged-mesh fraction and true maximum
       residual per sweep. Needs `BEMTConfig.collect_history=
       True` (default). With it off, `maps["frac_converged_history"]`
       comes back EMPTY and the panel is replaced by a warning saying so.
       Previously the figure came out blank, which reads as "did not
       converge" instead of "did not record the history".
    3. HOW MUCH it cost: the header numbers in cards
       (`_number_cards`).

    Each piece appears if and only if the data exists: a `Results` that
    only has `summary` (old export, no maps or history) still produces
    the card row, with no empty axis or meaningless bar.
    """
    maps = results.maps or {}
    hist = list(maps.get("frac_converged_history") or [])
    resid = list(maps.get("residual_history") or [])
    has_disk = all(k in maps for k in ("R_NORM", "PSI", "n_iter"))
    has_history = bool(hist or resid)
    conv_summary = _convergence_summary(results)

    fig, ax_disk, ax_hist, ax_num = _convergence_layout(
        ax, fname, has_disk, has_history)

    if ax_disk is not None:
        _draw_convergence_disk(ax_disk, maps)

    if ax_hist is not None:
        if hist:
            ax_hist.plot(range(1, len(hist) + 1), 100.0 * np.asarray(hist, dtype=float),
                         "-", color="tab:blue", linewidth=1.6,
                         label="converged mesh")
            ax_hist.set_ylabel("converged mesh [%]", fontsize=8, color="tab:blue")
            ax_hist.tick_params(axis="y", labelcolor="tab:blue", labelsize=8)
            ax_hist.set_ylim(-2, 102)
        # Maximum residual on the right axis, in log scale: it is what
        # says HOW FAR the remaining elements still are, information
        # that the fraction alone (which saturates at 100%) hides.
        if resid:
            ax_res = ax_hist.twinx()
            ax_res.semilogy(range(1, len(resid) + 1), resid, "--", color="tab:red",
                            linewidth=1.4, label=r"max $|g(\lambda)-\lambda|$")
            ax_res.set_ylabel(r"max $|g(\lambda_i)-\lambda_i|$", color="tab:red", fontsize=8)
            ax_res.tick_params(axis="y", labelcolor="tab:red", labelsize=8)
            lines = (ax_hist.get_lines() if hist else []) + ax_res.get_lines()
            ax_hist.legend(lines, [l.get_label() for l in lines],
                           loc="center right", fontsize=7.5)
        ax_hist.set_xlabel("solver sweep", fontsize=8)
        ax_hist.tick_params(axis="x", labelsize=8)
        ax_hist.grid(True, alpha=0.3)

    pct = conv_summary["pct"]
    cards = []
    if pct is not None:
        color = "#1a7f37" if pct >= 99.999 else ("#b45309" if pct >= 95.0 else "#b91c1c")
        cards.append((f"{pct:.1f}%", "converged", color))
    if conv_summary["n_failed"]:
        cards.append((f"{conv_summary['n_failed']}/{conv_summary['n_elements']}", "elements left",
                      _COLOR_NOT_CONVERGED))
    if conv_summary["mean"] is not None:
        cards.append((f"{conv_summary['mean']:.1f}", "mean iters", "0.15"))
    if conv_summary["max"] is not None:
        cards.append((f"{conv_summary['max']}", "max iters", "0.15"))
    if conv_summary["elapsed"] is not None:
        cards.append((_format_time(conv_summary["elapsed"]), "solver time", "0.15"))
    if not cards:
        ax_num.set_axis_off()
        ax_num.text(0.5, 0.5, "No convergence data available", ha="center",
                    va="center", fontsize=11, color="0.35", transform=ax_num.transAxes)
    if not has_history and cards:
        # Without history the right panel would be an empty rectangle: the
        # cards rise to its middle and the reason for the emptiness gets written.
        ax_num.text(0.5, -0.04,
                    'Iteration history not recorded — enable "collect_history" and run again.',
                    ha="center", va="top", fontsize=7.5, color="0.45",
                    transform=ax_num.transAxes)

    parts = ["Solver convergence"]
    if conv_summary["solver"]:
        parts.append(str(conv_summary["solver"]))
    if conv_summary["n_elements"]:
        parts.append(f"{conv_summary['n_elements']} elements")
    if conv_summary["sweeps"]:
        parts.append(f"{int(conv_summary['sweeps'])} sweeps")
    fig.suptitle(parts[0] + (f"  ({', '.join(parts[1:])})" if len(parts) > 1 else ""),
                 fontsize=11, fontweight="bold")
    fig.tight_layout(rect=[0, 0, 1, 0.94])
    # The cards are drawn AFTER the layout: their font size depends on
    # the panel's final width (see `_number_cards`), and before
    # `tight_layout` that width will still change.
    if cards:
        _number_cards(ax_num, cards)
    if fname is not None:
        fig.savefig(fname, dpi=_EXPORT_DPI)
        return None
    return fig


# =============================================================================
# Coefficients vs mu_x (11 panels, equivalent to MATLAB's plot_summary_vs_mu)
# =============================================================================

_MU_SWEEP_PANELS = [
    ("CT",  r"$C_T$",             "Thrust Coefficient"),
    ("CQ",  r"$C_Q$ ($C_P$)",     "Torque/Power Coefficient"),
    ("FM",  r"$FM$",              "Figure of Merit (hover def.)"),
    ("CY",  r"$C_Y$",             "Y-Force Coeff (+ right)"),
    ("CMx", r"$C_{Mx}$",          "Pitch Moment Coeff (+ nose up)"),
    ("CMy", r"$C_{My}$",          "Roll Moment Coeff (+ roll right)"),
    ("CH",  r"$C_H$",             "H-Force Coeff (+ aft)"),
    ("CHp", r"$C_{Hp}$",          "H-Force, profile component"),
    ("CHi", r"$C_{Hi}$",          "H-Force, induced component"),
    ("CPp", r"$C_{Pp}$",          "Profile Power"),
    ("CPi", r"$C_{Pi}$",          "Induced Power"),
]

#: Panels for PROPELLER mode. Not the same set as the rotor with
#: different names: it is a different nondimensionalization (rho*n^2*D^4
#: instead of rho*A*(Omega*R)^2, see `bemt.aggregate_results` Section 6c) and a
#: different figure of merit (eta_prop instead of FM). Showing the rotor
#: panels for a propeller filled the figure with physically meaningless
#: plots there (FM outside of hover, CMx/CMy/CY, which for a propeller in
#: axial flight are ~0 by symmetry) and OMITTED exactly
#: CT_prop/CQ_prop/CP_prop/eta_prop, which are the curves presented in a
#: propeller report.
_PROP_SWEEP_PANELS = [
    ("CT_prop",  r"$C_T$",           "Thrust Coeff (prop: $T/\\rho n^2 D^4$)"),
    ("CQ_prop",  r"$C_Q$",           "Torque Coeff (prop: $Q/\\rho n^2 D^5$)"),
    ("CP_prop",  r"$C_P$",           "Power Coeff (prop: $P/\\rho n^3 D^5$)"),
    ("eta_prop", r"$\eta_{prop}$",   "Propulsive Efficiency"),
    ("J_z",      r"$J_z$",           "Axial Advance Ratio"),
    ("CT",       r"$C_{T,rotor}$",   "Thrust Coeff (rotor nondim.)"),
    ("CP",       r"$C_{P,rotor}$",   "Power Coeff (rotor nondim.)"),
    ("CPp",      r"$C_{Pp}$",        "Profile Power"),
    ("CPi",      r"$C_{Pi}$",        "Induced Power"),
]


def _sweep_panels(results_list) -> list:
    """Chooses the panel set by the result's CONVENTION.

    `aggregate_results` records `cfg_is_propeller` in each `Results`'s
    `summary`, so the choice comes from what was actually run, not
    from an extra parameter the caller would have to remember to pass
    (and that the GUI, the CLI, and the report would forget in
    different places)."""
    if results_list:
        first = results_list[0].summary
        if first.get("cfg_is_propeller") or first.get("is_propeller"):
            return _PROP_SWEEP_PANELS
    return _MU_SWEEP_PANELS


# Maps each factorial variable (`studies._FACTORIAL_VARIABLES`) to the
# `Results.summary` key that carries its resolved value, and to a
# friendly axis/title label. Part 4.2 ("Coefficients vs axis"
# generalizes the old "Polar (batch)", which only knew how to plot vs
# mu_x). "mu_x" and "alpha_deg" already had native columns from
# `bemt.aggregate_results` (`mu_x`, `alpha_rotor_deg`); "collective_deg"/
# "rpm" got an alias in `studies.run_single_case` specifically to feed
# this combo (see studies.py, same commit).
_AXIS_TO_SUMMARY_KEY = {
    "mu_x": "mu_x",
    "alpha_deg": "alpha_rotor_deg",
    "collective_deg": "collective_deg",
    "rpm": "rpm",
}
def _grouping_key(value):
    """Rounds a value before using it as a grouping KEY for series
    (``plot_coefficients_vs_axis``/``plot_xy``).

    Several ``Results.summary`` columns used for grouping (in
    particular ``alpha_rotor_deg``, which an ``alpha_deg`` sweep
    resolves via ``Vz=tan(alpha)*V`` and then reconstructs via
    ``atan2(Vz, V)``) are the result of a floating-point calculation,
    not a typed-in value. Comparing by EXACT EQUALITY sliced a single
    nominal sweep (for example alpha = -3, -2, ..., 3) into several
    near-duplicate series because of ~1e-4 noise, one per combination
    with the other axis (seen on screen: ~20 alpha curves where the
    user asked for 7). Rounding to 3 decimal places preserves any
    sweep with an actual step larger than 0.001 (the vast majority)
    and merges the floating-point noise into the same series."""
    if isinstance(value, float):
        rounded = round(value, 3)
        # round(-0.0002, 3) == -0.0: numerically equal to 0.0, but
        # formats as "-0" instead of "0" (`f"{-0.0:g}"`). Two
        # combinations of the same nominal value near zero, one coming
        # from positive noise and the other from negative noise, kept
        # turning into DIFFERENT labels (and therefore series) after
        # the very rounding that was supposed to unite them.
        return rounded + 0.0
    return value


#: DEFAULT tolerance (in the quantity's own units) for deciding whether two
#: grouping values are "the same value". Adjustable by the user via the
#: "Group tolerance" control on the Results tab.
DEFAULT_GROUP_TOLERANCE = 0.01


def _group_order(key):
    """Orders the series by grouping key: numeric in ascending order,
    non-numeric afterwards, in alphabetical order. The legend used to
    come out in the results' APPEARANCE order, which for a factorial is
    the order of the cartesian product: ``alpha = 0, -10, -5, 5, 10``
    on screen, with the reader having to hunt for the right curve
    instead of reading it off."""
    if isinstance(key, (int, float)) and not isinstance(key, bool):
        return (0, float(key), "")
    return (1, 0.0, str(key))


def grouping_map(values, tol: float = DEFAULT_GROUP_TOLERANCE) -> dict:
    """Map ``raw value -> canonical series key``, merging values that
    are less than ``tol`` apart from each other.

    Why a TOLERANCE and not just the rounding from
    `_grouping_key`: rounding is a fixed grid, and two values
    of the SAME nominal value can fall into neighboring cells of it.
    That is what was seen on screen: a sweep of alpha = -10, -5, 0,
    5, 10 (whose alpha is reconstructed via ``atan2(Vz, V)``, with
    error of ~1e-3 depending on the mu_x of each combination) produced
    the series ``-10.002``, ``-10.001``, ``-10``, ``-9.999``,
    ``-9.997``: five curves of one or two points where the user asked
    for ONE. Rounding does not fix this because the noise crosses the
    grid boundary. Grouping by PROXIMITY does.

    Gap-based grouping (1D single-linkage): sorted values, cut where
    the next neighbor is more than ``tol`` away. A legitimate sweep
    with a step larger than ``tol`` remains separate. That is
    exactly what the tolerance means, and why it belongs to the user,
    not fixed.

    The canonical key is the group average rounded to ``tol`` itself
    (with ``tol=0.01``, a group around -9.9995 becomes ``-10.0``, not
    a ``-9.9995`` that would give away in the legend the noise that
    was just merged). Non-numeric values (and NaN) are their own key.
    """
    numeric_values: list[float] = []
    mapping: dict = {}
    for v in values:
        if isinstance(v, (int, float)) and not isinstance(v, bool):
            fv = float(v)
            if np.isnan(fv):
                mapping[v] = v
                continue
            numeric_values.append(fv)
        else:
            mapping[v] = v

    if not numeric_values:
        return mapping

    try:
        tol = float(tol)
    except (TypeError, ValueError):
        tol = DEFAULT_GROUP_TOLERANCE
    if not np.isfinite(tol) or tol <= 0.0:
        # Null/invalid tolerance = previous behavior (3-decimal grid),
        # never an exception in the middle of a plot refresh.
        for v in numeric_values:
            mapping[v] = _grouping_key(v)
        return mapping

    sorted_values = sorted(set(numeric_values))
    current_group = [sorted_values[0]]
    groups_list = [current_group]
    for previous, current in zip(sorted_values, sorted_values[1:]):
        if current - previous <= tol:
            current_group.append(current)
        else:
            current_group = [current]
            groups_list.append(current_group)

    for g in groups_list:
        canonical = round(float(np.mean(g)) / tol) * tol
        # +0.0 kills the "-0" (same trap as `_grouping_key`).
        # The second rounding removes the binary residue from
        # `x/tol*tol` (0.1*3 = 0.30000000000000004 would render as
        # label "0.3" but a distinct key from a 0.3 arriving another way).
        canonical = round(canonical, 12) + 0.0
        for v in g:
            mapping[v] = canonical
    return mapping


#: The PROSE half of a sweep-panel axis: what the quantity is called in a
#: sentence. The symbol half is not here, it comes from `nomenclature`, per
#: mode, via `_sweep_axis_label`. A propeller batch swept over the
#: cross-flow used to be titled "advance ratio (mu_x)" in BOTH modes, which
#: names the cross-flow as if it were the advance ratio.
_AXIS_TITLES = {
    "mu_x": ("advance ratio", "cross-flow ratio"),
    "alpha_deg": ("rotor disk angle of attack", "rotor disk angle of attack"),
    "alpha_disk": ("disk angle of attack", "disk angle of attack"),
    "collective_deg": ("collective pitch", "collective pitch"),
    "rpm": ("rotation", "rotation"),
}


def results_propeller_mode(results_list) -> bool:
    """Whether these results were run in propeller mode, from the
    `cfg_is_propeller` echo `bemt.aggregate_results` writes into every
    `Results.summary`.

    Read here instead of being passed in: every plotting entry point already
    receives the results, and a figure whose axis letters disagree with the
    table beside it is exactly what this refactor removes.
    `api.propeller_mode` is the same criterion, for callers that also hold the
    project."""
    for r in results_list or ():
        value = r.summary.get("cfg_is_propeller")
        if value is not None:
            return bool(value)
    return False


def _sweep_axis_label(axis: str, is_propeller: bool = False) -> tuple:
    """``(axis label, prose title)`` for a sweep panel, in the mode's own
    axis letters."""
    titles = _AXIS_TITLES.get(axis)
    if titles is None:
        return axis, axis
    prose = titles[1] if is_propeller else titles[0]
    label = _summary_axis_label(_AXIS_TO_SUMMARY_KEY.get(axis, axis), is_propeller)
    return label, f"{prose} ({nomenclature.symbol_text(axis, is_propeller)})"

# =============================================================================
# Axis/mathtext labels shared by ANY `Results.summary` key, used by
# `plot_xy` (the "Custom X-Y" part, requested by the user: plot any
# quantity vs any other, in a single panel, grouped by a third one).
# Builds on `_AXIS_TITLES`/`_MU_SWEEP_PANELS`/
# `_PROP_SWEEP_PANELS` (which already covered the 4 factorial axes and
# the 11+9 panel coefficients) instead of duplicating, see CLAUDE.md
# "a new field needs to be wired into the right surfaces": here the
# surface is only labeling, not .bemt/CLI, so a local table is enough.
# Each entry: summary key -> mathtext label READY for the axis
# (symbol + unit in brackets when dimensional, "[-]" when not).
_SUMMARY_KEY_LABELS = {
    # --- flight condition / input ---------------------------------------
    # NOT HERE. Every key whose symbol depends on the axis convention comes
    # from `zbemt.nomenclature`, which `_summary_axis_label` consults first.
    # This used to be a second copy of `api._COLUMN_SYMBOL`, and the two
    # had already drifted: the report's table said theta_0 in [rev/min]
    # where the chart printed beside it, in the SAME report, said theta_col
    # in [-].
    # --- dimensional forces/moments --------------------------------------
    "Thrust": r"$T$ [N]", "Torque": r"$Q$ [N$\cdot$m]",
    "Power": r"$P$ [W]", "Power_i": r"$P_i$ [W]", "Power_p": r"$P_p$ [W]",
    "H": r"$H$ [N]", "Hi": r"$H_i$ [N]", "Hp": r"$H_p$ [N]",
    "Y": r"$Y$ [N]", "Mx": r"$M_x$ [N$\cdot$m]", "My": r"$M_y$ [N$\cdot$m]",
    # --- coefficients, rotor convention -----------------------------------
    "CT": r"$C_T$ [-]", "CQ": r"$C_Q$ [-]", "CP": r"$C_P$ [-]",
    "aspect_ratio": r"$AR$ [-]", "solidity": r"$\sigma$ [-]",
    "CPi": r"$C_{Pi}$ [-]", "CPp": r"$C_{Pp}$ [-]",
    "CH": r"$C_H$ [-]", "CHi": r"$C_{Hi}$ [-]", "CHp": r"$C_{Hp}$ [-]",
    "CY": r"$C_Y$ [-]", "CMx": r"$C_{Mx}$ [-]", "CMy": r"$C_{My}$ [-]",
    "FM": r"$FM$ [-]",
    # --- coefficients, propeller convention --------------------------------
    "CT_prop": r"$C_{T,prop}$ [-]", "CQ_prop": r"$C_{Q,prop}$ [-]",
    "CP_prop": r"$C_{P,prop}$ [-]", "eta_prop": r"$\eta_{prop}$ [-]",
    # --- solver diagnostics -------------------------------------------------
    "convergence_pct": "convergence [%]", "mean_iter": "mean iterations [-]",
    "elapsed_s": "elapsed [s]",
    # --- rotor (spec sheet) --------------------------------------------------
    "rotor_R": r"$R$ [m]", "rotor_Nb": r"$N_b$ [-]", "rotor_Omega": r"$\Omega$ [rad/s]",
    "rotor_OmegaR": r"$\Omega R$ [m/s]", "rotor_rpm": "RPM [-]", "rotor_D": r"$D$ [m]",
}


def _summary_axis_label(key: str, is_propeller: bool = False) -> str:
    """Mathtext axis label for any ``Results.summary`` key (see
    `_SUMMARY_KEY_LABELS`); falls back to the key's own name (unformatted)
    when unknown. It never fails, even for a new key or a
    ``cfg_*``/``rotor_*`` with no dedicated entry.

    ``is_propeller`` swaps the axis letters without touching the value or the
    key. The swap itself lives in `zbemt.nomenclature`, shared with the
    report's table headers and the GUI's combos, so a chart and the table
    beside it cannot name the same column differently."""
    if nomenclature.quantity(key) is not None:
        return nomenclature.symbol_mathtext(key, is_propeller)
    return _SUMMARY_KEY_LABELS.get(key, key)


# =============================================================================
# Mathtext -> Unicode / HTML
# =============================================================================
# The conversions themselves live in `zbemt.nomenclature`, next to the LaTeX
# they convert: whatever DRAWS renders `$\mu_x$` as mu; whatever just
# DISPLAYS TEXT (a QComboBox on the Results tab, a table header) would
# show the raw source ("mu_x  ($\mu_x$ [-])" was on screen). Re-exported
# under the names this module has always used, so the GUI keeps calling
# `plots.label_to_text`, and no second label list has to exist.
label_to_text = nomenclature.to_unicode
label_to_html = nomenclature.to_html


def summary_label_text(key: str, is_propeller: bool = False) -> str:
    """`_summary_axis_label` already in plain text, what the GUI shows."""
    return label_to_text(_summary_axis_label(key, is_propeller))


def summary_label_html(key: str, is_propeller: bool = False) -> str:
    """`_summary_axis_label` already in HTML, what the Results tab's
    combos paint."""
    return label_to_html(_summary_axis_label(key, is_propeller))



#: PROSE description of each disk map field: what the field MEANS,
#: without a code variable name. It is the text shown on hovering over
#: an item in the Results tab's combos (user request: "the extended
#: name, in prose, not the internal representation").
#: `_DISK_FIELD_META` remains the source of the field SET: a key with
#: no entry here simply gets no description.
_DISK_FIELD_DESCRIPTIONS = {
    "Fn": "Thrust per unit span: the force each metre of blade pushes along the rotor axis.",
    "Ft": "In-plane force per unit span: what resists the rotation, and therefore what sets the torque.",
    "Ft_i": "Induced part of the in-plane force: the share that comes from tilting the lift vector back, the unavoidable cost of making thrust.",
    "Ft_p": "Profile part of the in-plane force: the share that comes from the section's own drag.",
    "Cl": "Lift coefficient of the section at the angle of attack it actually sees.",
    "Cd": "Drag coefficient of the section at the angle of attack it actually sees.",
    "Vi": "Induced velocity: how fast the rotor pushes air through the disc at that point.",
    "Up": "Component of the local flow perpendicular to the disc.",
    "Ut": "Component of the local flow in the plane of rotation. It goes negative inboard on the retreating side, which is the reverse-flow region.",
    "W": "Total speed of the air relative to the section.",
    "alpha_eff": "Angle of attack the section actually sees, once the induced flow has tilted the oncoming stream.",
    "phi": "Inflow angle between the oncoming stream and the plane of rotation.",
    "lambda_z_field": "Total inflow ratio: climb plus induced flow, as a fraction of tip speed.",
    "lambda_i": "Induced inflow ratio: the induced part alone, as a fraction of tip speed.",
    "Mach": "Local Mach number of the section.",
    "q": "Dynamic pressure the section sees.",
}


def disk_field_description(field: str) -> str:
    """Prose description of a disk map field; empty string when not
    cataloged (the combo simply shows no tooltip)."""
    return _DISK_FIELD_DESCRIPTIONS.get(field, "")


def flatten_selection(entries) -> list:
    """Flattens a heterogeneous selection of ``models.ResultEntry``
    (single cases + batches, docs/plano_v3.md Part 4.2) into a flat
    list of ``Results``, in the order they appear in ``entries``. A
    ``kind="case"`` entry contributes 1 element (``entry.results`` is
    the ``Results`` itself). A ``kind="batch"`` entry contributes all
    of its ``Results`` (``entry.results`` is already the list), in
    saved order."""
    flat = []
    for entry in entries:
        if entry.kind == "batch":
            flat.extend(entry.results)
        else:
            flat.append(entry.results)
    return flat


def plot_coefficients_vs_axis(results_list, axis: str = "mu_x", fname=None, ncols: int = 4,
                                series_labels=None,
                                group_tol: float = DEFAULT_GROUP_TOLERANCE):
    """Grid with the 11 global coefficients (CT, CQ, FM, CY, CMx, CMy, CH,
    CHp, CHi, CPp, CPi) as a function of ``axis``. It generalizes the old
    `plot_coefficients_vs_mu` (kept below as a shortcut) to any of the 4
    factorial variables in `studies._FACTORIAL_VARIABLES` ("mu_x",
    "alpha_deg", "collective_deg", "rpm"), per Part 4.2, "Coefficients vs
    axis".

    ``series_labels``: optional, parallel to ``results_list`` (same
    length). When omitted (default), all results are combined into a
    SINGLE curve per panel, sorted by increasing ``axis`` ("combine"
    mode). When provided with 2+ distinct labels, draws one curve PER
    label, overlaid on the same panel ("overlay" mode, useful for
    comparing 2+ selections from the Results history side by side),
    see `ResultsTab._refresh_batch` in gui.py.

    ``group_tol``: tolerance for series auto-detection (values closer
    than this are the same nominal value, see `grouping_map`).
    """
    key = _AXIS_TO_SUMMARY_KEY.get(axis, axis)
    axis_label, axis_title = _sweep_axis_label(
        axis, results_propeller_mode(results_list))
    x_all = np.array([r.summary.get(key, np.nan) for r in results_list], dtype=float)

    # Identifies the other factorial variables that also varied across the results
    groups = {}
    if series_labels is not None:
        for i, lbl in enumerate(series_labels):
            groups.setdefault(lbl, []).append(i)
    else:
        other_keys = [(_AXIS_TO_SUMMARY_KEY[ax], ax) for ax in _AXIS_TO_SUMMARY_KEY.keys() if ax != axis]

        # `alpha_rotor_deg` is DERIVED from `atan2(Vz, mu_x*OmegaR)`: it
        # is only DEGENERATE (discontinuous, jumps from 0 to 90 at a
        # single point) in the specific case of a PURELY axial
        # propeller sweep, with `mu_x` locked at ~0 (atan2
        # denominator ~0) while `Vz` sweeps through zero. Treating it
        # as a "second axis varying" in this specific case split the
        # sweep into TWO spurious series: the V=0 point alone in one
        # curve, the rest in another.
        #
        # The PREVIOUS condition ("exclude alpha_deg whenever mu_x OR Vz
        # have more than one value across the whole list") was too
        # broad: `mu_x` varies in practically ANY mu_x sweep (it is the
        # X axis!), so it suppressed grouping by alpha even in a
        # legitimate 2-axis factorial (mu_x x alpha_deg). The entire
        # batch collapsed into a single curve, hiding the alphas the
        # user asked to compare. The real degenerate case requires
        # `mu_x` CONSTANT and near zero (not "varying"); with `mu_x`
        # actually varying (2+ nonzero values), `Vz=tan(alpha)*mu_x*
        # OmegaR` is continuous and alpha_rotor_deg is a perfectly good
        # grouping quantity.
        mu_vals = {v for v in (r.summary.get("mu_x") for r in results_list)
                   if v is not None and not (isinstance(v, float) and np.isnan(v))}
        vv_vals = {v for v in (r.summary.get("Vz") for r in results_list)
                   if v is not None and not (isinstance(v, float) and np.isnan(v))}
        axial_advance_degenerate = (
            len(mu_vals) <= 1 and (not mu_vals or abs(next(iter(mu_vals))) < 1e-9)
            and len(vv_vals) > 1)
        if axial_advance_degenerate:
            other_keys = [(sk, ax) for sk, ax in other_keys if ax != "alpha_deg"]

        # One tolerance per quantity: two values closer than
        # `group_tol` are THE SAME nominal value, both for deciding
        # whether the quantity VARIED and for labeling the series (see
        # `grouping_map`).
        swept_other_vars = []
        keys_by_quantity: dict = {}
        for skey, ax_name in other_keys:
            vals = [r.summary.get(skey, None) for r in results_list]
            key_of = grouping_map(
                [v for v in vals
                 if v is not None and not (isinstance(v, float) and np.isnan(v))], group_tol)
            keys_by_quantity[skey] = key_of
            if len(set(key_of.values())) > 1:
                swept_other_vars.append((skey, ax_name))


        order_by_label: dict = {}
        for i, r in enumerate(results_list):
            label_parts = []
            order_keys = []
            for skey, ax_name in swept_other_vars:
                raw_value = r.summary.get(skey)
                val = keys_by_quantity[skey].get(raw_value, _grouping_key(raw_value))
                if val is not None and not (isinstance(val, float) and np.isnan(val)):
                    symbol = nomenclature.symbol_name(
                        ax_name, results_propeller_mode(results_list))
                    label_parts.append(f"{symbol}={val:g}" if isinstance(val, (int, float)) else f"{symbol}={val}")
                    order_keys.append(_group_order(val))

            lbl = ", ".join(label_parts)
            order_by_label.setdefault(lbl, tuple(order_keys))
            groups.setdefault(lbl, []).append(i)
        # Legend in value order, not appearance order (see `_group_order`).
        groups = {k: groups[k] for k in sorted(groups, key=lambda k: order_by_label.get(k, ()))}

    overlay = len(groups) > 1 or (series_labels is not None and len(set(series_labels)) > 1)

    panels = _sweep_panels(results_list)
    n = len(panels)
    ncols = min(ncols, n)
    nrows = int(np.ceil(n / ncols))
    fig, axes = _new_figure((4.0 * ncols, 3.0 * nrows), nrows, ncols)
    axes = np.atleast_1d(axes).ravel()

    for i, (ax, (field_key, ylabel, title)) in enumerate(zip(axes, panels)):
        for lbl, idxs in groups.items():
            xs = x_all[idxs]
            order = np.argsort(xs)
            xs_sorted = xs[order]
            vals = np.array([results_list[idxs[o]].summary.get(field_key, np.nan) for o in order],
                             dtype=float)
            ax.plot(xs_sorted, vals, "o-", markersize=3.5, linewidth=1.3, label=(lbl or None))
        ax.axhline(0, color="0.6", linestyle=":", linewidth=0.6)
        if i >= n - ncols:
            ax.set_xlabel(axis_label)
        ax.set_ylabel(ylabel)
        ax.set_title(title, fontsize=9)
        ax.grid(True, alpha=0.3)
        y_limit = max(abs(float(v)) for v in ax.get_ylim())
        if 0.0 < y_limit < 1e-3:
            # The global offset (for example ``1e-5``) sits above the axis and
            # can collide with the title of the panel on the next row.
            ax.yaxis.set_major_formatter(
                FuncFormatter(lambda value, _pos: f"{value:.1e}"))
    if overlay:
        axes[0].legend(fontsize=7)
    for j in range(n, len(axes)):
        axes[j].axis("off")

    mode_label = "Propeller" if panels is _PROP_SWEEP_PANELS else "Rotor"
    fig.suptitle(rf"{mode_label} performance vs {axis_title}", fontsize=12, fontweight="bold")
    fig.tight_layout(rect=[0, 0, 1, 0.95], h_pad=3.0, w_pad=1.5)
    return _finish_fig(fig, fname)


def plot_coefficients_vs_mu(results_list, fname=None, ncols: int = 4):
    """Backward-compatible: shortcut for
    ``plot_coefficients_vs_axis(results_list, axis="mu_x", ...)``, same
    signature and behavior as always."""
    return plot_coefficients_vs_axis(results_list, axis="mu_x", fname=fname, ncols=ncols)


def plot_xy(results_list, x_key: str, y_key: str, group_by: str | None = None,
            ax=None, fname=None,
            group_tol: float = DEFAULT_GROUP_TOLERANCE,
            is_propeller: bool = False):
    """Free plot: ANY ``Results.summary`` key on the X axis, ANY other
    on the Y axis, optionally grouped into one curve per distinct value
    of ``group_by`` (also a summary key, for example "collective_deg",
    which gives a curve per collective, per angle of attack, and so
    on). User request: "plot anything
    against anything from the whole batch, several curves, one per
    grouping variable". Complements (does not replace)
    `plot_coefficients_vs_axis`, which remains the fixed 11/9-panel
    grid used in the report.

    Points with missing or NaN ``x_key``/``y_key`` are simply ignored
    (never brings down the whole plot for 1 incomplete result). Within
    each curve, points are sorted by increasing X, the same convention as
    `plot_coefficients_vs_axis`.

    ``group_tol``: ``group_by`` values closer than this fall into the
    SAME curve (see `grouping_map`).
    """
    ax, fig = _resolve_ax(ax, fname)

    def _val(r, key):
        v = r.summary.get(key, None)
        try:
            v = float(v)
        except (TypeError, ValueError):
            return np.nan
        return v

    groups: dict = {}
    if group_by:
        raw_values = [r.summary.get(group_by, None) for r in results_list]
        key_of = grouping_map(
            [v for v in raw_values if v is not None
             and not (isinstance(v, float) and np.isnan(v))], group_tol)
        for r, gv in zip(results_list, raw_values):
            if gv is None or (isinstance(gv, float) and np.isnan(gv)):
                continue
            groups.setdefault(key_of.get(gv, gv), []).append(r)
        groups = {k: groups[k] for k in sorted(groups, key=_group_order)}
    else:
        groups[None] = list(results_list)

    overlay = len([g for g in groups.values() if g]) > 1
    group_symbol = (_summary_axis_label(group_by, is_propeller).split(" [")[0]
                    if group_by else None)

    any_point = False
    for gv, items in groups.items():
        xs = np.array([_val(r, x_key) for r in items], dtype=float)
        ys = np.array([_val(r, y_key) for r in items], dtype=float)
        valid = np.isfinite(xs) & np.isfinite(ys)
        if not np.any(valid):
            continue
        xs_v, ys_v = xs[valid], ys[valid]
        order = np.argsort(xs_v)
        label = None
        if gv is not None:
            label = f"{group_symbol}={gv:g}" if isinstance(gv, (int, float)) else f"{group_symbol}={gv}"
        ax.plot(xs_v[order], ys_v[order], "o-", markersize=3.5, linewidth=1.3, label=label)
        any_point = True

    ax.set_xlabel(_summary_axis_label(x_key, is_propeller))
    ax.set_ylabel(_summary_axis_label(y_key, is_propeller))
    ax.axhline(0, color="0.6", linestyle=":", linewidth=0.6)
    ax.grid(True, alpha=0.3)
    title_y = _summary_axis_label(y_key, is_propeller).split(" [")[0]
    title_x = _summary_axis_label(x_key, is_propeller).split(" [")[0]
    ax.set_title(f"{title_y} vs {title_x}")
    if overlay:
        ax.legend(fontsize=8)
    if not any_point:
        ax.text(0.5, 0.5, "No valid data points\n(x/y missing or NaN for all results)",
                ha="center", va="center", fontsize=10, color="0.35", transform=ax.transAxes)
    return _finish(ax, fig, fname)


def _finish_fig(fig, fname):
    if fname is not None:
        fig.savefig(fname, dpi=_EXPORT_DPI)
        return None
    return fig


# =============================================================================
# Blade loads vs span (fixed psi) / vs azimuth (fixed r)
# =============================================================================

_BLADE_LOAD_FIELDS = [
    ("alpha_eff", r"$\alpha$ (deg)", True),
    ("phi",       r"$\phi$ (deg)",   True),
    ("Vi",        r"$V_i$ (m/s)",    False),
    ("Ut",        r"$U_t$ (m/s)",    False),
    ("Up",        r"$U_p$ (m/s)",    False),
    ("lambda_z_field", r"$\lambda$", False),
    ("Mach",      r"$M$",            False),
    ("Cl",        r"$C_L$",          False),
    ("Cd",        r"$C_D$",          False),
    ("F",         r"$F$ (Prandtl loss)", False),
    ("Fn",        r"$dT/dr$ (N/m)",  False),
    ("Ft",        r"$dQ/dr$ (N/m, /r)",   False),
]


def plot_blade_loads_vs_span(maps: dict, psi_targets_deg=(0, 90, 180, 270),
                              fname=None, ncols: int = 4, mask_reverse: bool = True):
    """Blade aerodynamic loads/state as a function of r/R, for a set of
    fixed azimuths (one curve per azimuth), equivalent to
    `plot_blade_loads` from zBEMT MATLAB. Angles always in degrees.

    `mask_reverse` (default True, same as `mask_reverse_flow_plots` in
    `plot_disk_map`): for each curve (one fixed azimuth), the r/R
    stretches where `Ut<0` (reverse flow) are shaded in light gray
    (`_REVERSE_MASK_COLOR`, via `_shade_reverse_regions`) and the curve
    itself is interrupted (NaN) over that stretch. It never ends up
    empty or white, and never draws the field's (possibly nonsensical)
    value there.
    """
    r_norm = np.asarray(maps["r_norm_nodes"], dtype=float)
    psi_nodes_deg = np.degrees(np.asarray(maps["psi_nodes"], dtype=float))
    Ut = np.asarray(maps["Ut"], dtype=float) if "Ut" in maps else None

    n = len(_BLADE_LOAD_FIELDS)
    ncols = min(ncols, n)
    nrows = int(np.ceil(n / ncols))
    fig, axes = _new_figure((3.6 * ncols, 2.6 * nrows), nrows, ncols)
    axes = np.atleast_1d(axes).ravel()
    colors = plt.get_cmap("tab10")

    for k, psi_deg in enumerate(psi_targets_deg):
        idx_psi = int(np.argmin(np.abs(psi_nodes_deg - psi_deg)))
        actual = psi_nodes_deg[idx_psi]
        color = colors(k % 10)
        reverse_mask = (Ut[:, idx_psi] < 0.0) if (mask_reverse and Ut is not None) else None
        for i, (field, ylabel, is_angle) in enumerate(_BLADE_LOAD_FIELDS):
            data = _disk_field_array(maps, field)[:, idx_psi]
            if is_angle:
                data = np.degrees(data)
            if reverse_mask is not None:
                _shade_reverse_regions(axes[i], r_norm, reverse_mask)
                data = np.where(reverse_mask, np.nan, data)
            axes[i].plot(r_norm, data, "-", linewidth=1.4, color=color, zorder=2,
                         label=rf"$\psi$={actual:.0f}°")
            axes[i].set_ylabel(ylabel, fontsize=8)
            axes[i].grid(True, alpha=0.3)
            axes[i].axhline(0, color="0.6", linestyle=":", linewidth=0.5)
    for j in range(n, len(axes)):
        axes[j].axis("off")
    for i in range(n):
        if i >= n - ncols:
            axes[i].set_xlabel("r/R", fontsize=8)
    axes[0].legend(fontsize=7, loc="best")

    mu_x = maps.get("mu_x", float("nan"))
    fig.suptitle(rf"Blade loads vs span — $\mu_x$={mu_x:.3f}", fontsize=12, fontweight="bold")
    fig.tight_layout(rect=[0, 0, 1, 0.96])
    return _finish_fig(fig, fname)


def plot_loads_vs_azimuth(maps: dict, r_norm_targets=(0.25, 0.5, 0.75, 0.95),
                           fname=None, ncols: int = 4, mask_reverse: bool = True):
    """Blade aerodynamic loads/state as a function of azimuth (psi), for
    a set of fixed radial stations (one curve per r/R), equivalent to
    `plot_loads_vs_azimuth` from zBEMT MATLAB. Angles always in degrees.

    `mask_reverse` (default True, same as `mask_reverse_flow_plots` in
    `plot_disk_map`): for each curve (one fixed radial station), the
    azimuth stretches where `Ut<0` (reverse flow) are shaded in light
    gray (`_REVERSE_MASK_COLOR`, via `_shade_reverse_regions`) and the
    curve itself is interrupted (NaN) over that stretch. It never
    ends up empty or white, and never draws the field's (possibly
    nonsensical) value there.
    """
    r_norm = np.asarray(maps["r_norm_nodes"], dtype=float)
    psi_nodes_deg = np.degrees(np.asarray(maps["psi_nodes"], dtype=float))
    Ut = np.asarray(maps["Ut"], dtype=float) if "Ut" in maps else None

    n = len(_BLADE_LOAD_FIELDS)
    ncols = min(ncols, n)
    nrows = int(np.ceil(n / ncols))
    fig, axes = _new_figure((3.6 * ncols, 2.6 * nrows), nrows, ncols)
    axes = np.atleast_1d(axes).ravel()
    colors = plt.get_cmap("tab10")

    for k, r_target in enumerate(r_norm_targets):
        idx_r = int(np.argmin(np.abs(r_norm - r_target)))
        actual = r_norm[idx_r]
        color = colors(k % 10)
        reverse_mask = (Ut[idx_r, :] < 0.0) if (mask_reverse and Ut is not None) else None
        for i, (field, ylabel, is_angle) in enumerate(_BLADE_LOAD_FIELDS):
            data = _disk_field_array(maps, field)[idx_r, :]
            if is_angle:
                data = np.degrees(data)
            if reverse_mask is not None:
                _shade_reverse_regions(axes[i], psi_nodes_deg, reverse_mask)
                data = np.where(reverse_mask, np.nan, data)
            axes[i].plot(psi_nodes_deg, data, "-", linewidth=1.4, color=color, zorder=2,
                         label=f"r/R={actual:.2f}")
            axes[i].set_ylabel(ylabel, fontsize=8)
            axes[i].grid(True, alpha=0.3)
            axes[i].axhline(0, color="0.6", linestyle=":", linewidth=0.5)
    for j in range(n, len(axes)):
        axes[j].axis("off")
    for i in range(n):
        if i >= n - ncols:
            axes[i].set_xlabel(r"azimuth $\psi$ [deg]", fontsize=8)
    axes[0].legend(fontsize=7, loc="best")

    mu_x = maps.get("mu_x", float("nan"))
    fig.suptitle(rf"Blade loads vs azimuth — $\mu_x$={mu_x:.3f}", fontsize=12, fontweight="bold")
    fig.tight_layout(rect=[0, 0, 1, 0.96])
    return _finish_fig(fig, fname)


# =============================================================================
# Design tools: geometry comparison and optimization convergence
# =============================================================================

#: Default summary quantities of `plot_geometry_comparison`, in panel
#: order. A quantity enters the figure only when at least one summary
#: carries it, so a partial export still produces its remaining panels.
_GEOMETRY_COMPARISON_FIELDS = ("CT", "FM", "CP", "eta_prop")


def _summary_float(value) -> float:
    """Coerces a summary entry to ``float``, NaN when it cannot be read."""
    try:
        value = float(value)
    except (TypeError, ValueError):
        return np.nan
    return value


def _group_by_geometry_label(results_list) -> dict:
    """Maps each ``geometry_label`` to the positions of its results in
    ``results_list``, in input order.

    The input is variant-major, the order produced by
    ``studies.compare_geometries``. A result without a label joins no
    series, the same policy `plot_xy` applies to a missing grouping
    value."""
    groups: dict = {}
    for position, result in enumerate(results_list):
        label = (result.summary or {}).get("geometry_label")
        if label is None:
            continue
        groups.setdefault(label, []).append(position)
    return groups


def plot_geometry_comparison(results_list, fields=None, *,
                             ax=None, fname=None):
    """Overlay figure that compares geometry variants.

    ``results_list`` is a flat list of ``Results`` whose summaries carry
    ``geometry_label`` plus the normal summary keys (``CT``, ``FM``,
    ``eta_prop`` and so on). Several conditions may exist per label. One
    line with markers is drawn per distinct label, and the list is
    variant-major, the order produced by ``studies.compare_geometries``.

    The figure holds one panel per requested quantity. By default the
    candidates are the entries of ``_GEOMETRY_COMPARISON_FIELDS``, kept
    only when at least one summary carries them. When none survives, the
    figure falls back to ``CT`` so a partial export still produces its
    panel. Explicit ``fields`` are honored as given.

    The X axis follows the data. When more than one distinct ``mu_x``
    value exists, every curve is plotted against ``mu_x``. Otherwise,
    every curve is plotted against the case index, and each tick names
    its case. Tick names longer than 12 characters rotate by 30 degrees.

    All panels share one color per label and one common legend. The
    overall title states the scope read from the data, the number of
    variants and the number of conditions.

    ``ax`` hosts the drawing when a single panel results. With several
    panels, the new axes take the slot of ``ax`` in its gridspec, the
    same reuse performed by ``plot_convergence``. Without ``ax``, a new
    figure is created. ``fname`` saves the figure created here, and the
    figure of a caller is never written to. The return value is the
    single axis, or the array of panel axes.
    """
    results_list = list(results_list or [])
    groups = _group_by_geometry_label(results_list)

    if fields is not None:
        available_fields = list(fields)
    else:
        available_fields = [key for key in _GEOMETRY_COMPARISON_FIELDS
                            if any(key in (r.summary or {})
                                   for r in results_list)]
    if not available_fields:
        available_fields = ["CT"]
    n_panels = len(available_fields)
    ncols = min(2, n_panels)
    nrows = int(np.ceil(n_panels / ncols))

    if ax is None:
        fig, axes_grid = _new_figure((4.0 * ncols, 3.0 * nrows), nrows, ncols)
        owned_fig = fig
    else:
        fig = ax.figure
        owned_fig = None   # a figure the caller owns is never saved here
        if n_panels == 1:
            axes_grid = [ax]
        else:
            # Same layout reuse as `_convergence_layout`: the supplied
            # axis gives up its slot, and the panel grid takes the slot.
            spec = ax.get_subplotspec()
            ax.remove()
            if spec is None:
                spec = fig.add_gridspec(1, 1)[0, 0]
            outer = spec.subgridspec(nrows, ncols)
            axes_grid = [fig.add_subplot(outer[i]) for i in range(nrows * ncols)]
    axes_grid = np.atleast_1d(axes_grid).ravel()

    mu_values = set()
    for result in results_list:
        value = _summary_float((result.summary or {}).get("mu_x"))
        if np.isfinite(value):
            mu_values.add(value)
    vs_mu_x = len(mu_values) > 1

    # ONE color map, built before any drawing: the same label must wear
    # the same color in every panel, or the panels cannot be compared.
    colors = {label: f"C{k % 10}" for k, label in enumerate(groups)}

    # Index mode resolves the tick names once, from the first group that
    # reaches each position. compare_geometries runs the same ordered
    # conditions for every variant, so position p names the same case in
    # every group.
    n_positions = max((len(idxs) for idxs in groups.values()), default=0)
    tick_names = []
    if not vs_mu_x:
        for position in range(n_positions):
            name = ""
            for idxs in groups.values():
                if position < len(idxs):
                    candidate = str(results_list[idxs[position]].condition_name or "")
                    if candidate:
                        name = candidate
                        break
            tick_names.append(name)

    any_point = False
    for panel, field_key in zip(axes_grid, available_fields):
        for label, idxs in groups.items():
            xs = []
            ys = []
            for position, i in enumerate(idxs):
                summary = results_list[i].summary or {}
                xv = (_summary_float(summary.get("mu_x")) if vs_mu_x
                      else float(position))
                yv = _summary_float(summary.get(field_key))
                if np.isfinite(xv) and np.isfinite(yv):
                    xs.append(xv)
                    ys.append(yv)
            if not xs:
                continue
            order = np.argsort(np.asarray(xs, dtype=float), kind="stable")
            panel.plot(np.asarray(xs, dtype=float)[order],
                       np.asarray(ys, dtype=float)[order],
                       "o-", markersize=3.5, linewidth=1.3,
                       color=colors[label], label=label)
            any_point = True
        panel.axhline(0, color="0.6", linestyle=":", linewidth=0.6)
        panel.set_ylabel(_summary_axis_label(field_key))
        panel.grid(True, alpha=0.3)
        if vs_mu_x:
            panel.set_xlabel(_summary_axis_label("mu_x"))
        else:
            panel.set_xlabel("Case")
            panel.set_xticks(range(n_positions))
            panel.set_xticklabels(tick_names, fontsize=8)
            if max((len(name) for name in tick_names), default=0) > 12:
                for tick in panel.get_xticklabels():
                    tick.set_rotation(30)
                    tick.set_ha("right")

    # ONE legend for the whole figure, assembled from every panel so it
    # stays complete even when the first panel holds no data.
    handles = []
    seen_labels = set()
    for panel in axes_grid:
        for handle, label_text in zip(*panel.get_legend_handles_labels()):
            if label_text not in seen_labels:
                seen_labels.add(label_text)
                handles.append(handle)
    if handles:
        axes_grid[0].legend(handles, [h.get_label() for h in handles],
                            fontsize=7, title="Geometry", loc="best")
    if not any_point:
        message = ("No geometry-labeled results to compare" if not groups
                   else "No valid data points for the selected fields")
        axes_grid[0].text(0.5, 0.5, message, ha="center", va="center",
                          fontsize=10, color="0.35",
                          transform=axes_grid[0].transAxes)

    condition_names = {str(getattr(r, "condition_name", "") or "")
                       for r in results_list}
    condition_names.discard("")
    n_conditions = len(condition_names) or n_positions
    fig.suptitle(f"Geometry comparison ({len(groups)} variants, "
                 f"{n_conditions} conditions)", fontsize=12, fontweight="bold")
    if owned_fig is not None:
        fig.tight_layout(rect=[0, 0, 1, 0.94], h_pad=2.0, w_pad=1.2)

    result_axes = axes_grid[0] if n_panels == 1 else axes_grid
    return _finish(result_axes, owned_fig, fname)


#: Summary keys whose LOWER value wins a ranking. Every other key ranks
#: with the largest value first. The set stays local to this module: it
#: describes how a quantity is READ in a comparison, not how it is
#: produced.
_RANKING_LOWER_IS_BETTER = frozenset({"CP", "Power", "CQ"})


#: Below this magnitude a base value counts as zero for a percent
#: change: dividing by it would explode the scale, so the figure falls
#: back to the plain difference and says so on the labels.
_DELTA_BASE_EPSILON = 1e-12


def plot_geometry_delta(results_list, field: str, *, ax=None, fname=None,
                        base_label: str = "base"):
    """Percent change of every geometry variant against ONE base
    variant.

    ``results_list`` is the variant-major list produced by
    ``studies.compare_geometries``, and ``field`` is a
    ``Results.summary`` key. Every variant whose label differs from
    ``base_label`` gets one series per condition, expressing its value
    as ``100*(v - v_base)/abs(v_base)`` against the base variant AT THE
    SAME condition (the same case position of the ordered list). A
    variant position without a base result at that position leaves the
    figure.

    When the magnitude of a base value falls below
    ``_DELTA_BASE_EPSILON``, the percent form would explode, so the
    plain difference is drawn instead and both the axis label and the
    title carry an "(absolute)" suffix.

    The X axis mirrors `plot_geometry_comparison`: more than one
    distinct ``mu_x`` value draws one polyline per variant against
    ``mu_x``; otherwise grouped bars sit per case position and each tick
    names its case (rotated by 30 degrees when longer than 12
    characters). One color per variant label, consistent within this
    figure. An emphasized zero line marks "equal to base".

    Empty or degenerate input draws a centered explanation instead of
    staying blank. The ``ax`` and ``fname`` parameters follow the
    module convention stated at the top of this file. The axis is
    returned.
    """
    results_list = list(results_list or [])
    if ax is None:
        fig, ax = _new_figure((6.5, 4))
        owned_fig = fig
    else:
        fig = ax.figure
        owned_fig = None   # a figure the caller owns is never saved here
    groups = _group_by_geometry_label(results_list)

    def _explain(message: str):
        ax.set_axis_off()
        ax.text(0.5, 0.5, message, ha="center", va="center",
                fontsize=10, color="0.35", transform=ax.transAxes)
        return _finish(ax, owned_fig, fname)

    if not groups:
        return _explain("No geometry-labeled results to compare")
    base_idxs = groups.get(base_label)
    if not base_idxs:
        return _explain(
            f"No geometry named {base_label!r} to use as the base")

    mu_values = set()
    for result in results_list:
        value = _summary_float((result.summary or {}).get("mu_x"))
        if np.isfinite(value):
            mu_values.add(value)
    vs_mu_x = len(mu_values) > 1

    # Index mode resolves the tick names once, from the first group that
    # reaches each position -- same rationale as plot_geometry_comparison.
    n_positions = max((len(idxs) for idxs in groups.values()), default=0)
    tick_names = []
    if not vs_mu_x:
        for position in range(n_positions):
            name = ""
            for idxs in groups.values():
                if position < len(idxs):
                    candidate = str(
                        results_list[idxs[position]].condition_name or "")
                    if candidate:
                        name = candidate
                        break
            tick_names.append(name)

    # ONE local color map per figure: colormap state must not be shared
    # across figures, or two open figures would recolor each other.
    colors = {label: f"C{k % 10}" for k, label in enumerate(groups)
              if label != base_label}

    series: dict = {}
    absolute_used = False
    for label in colors:
        for position, idx in enumerate(groups[label]):
            if position >= len(base_idxs):
                continue   # no base result ran this condition
            summary = results_list[idx].summary or {}
            base_summary = results_list[base_idxs[position]].summary or {}
            xv = (_summary_float(summary.get("mu_x")) if vs_mu_x
                  else float(position))
            value = _summary_float(summary.get(field))
            base_value = _summary_float(base_summary.get(field))
            if not (np.isfinite(xv) and np.isfinite(value)
                    and np.isfinite(base_value)):
                continue
            if abs(base_value) < _DELTA_BASE_EPSILON:
                yv = value - base_value
                absolute_used = True
            else:
                yv = 100.0 * (value - base_value) / abs(base_value)
            series.setdefault(label, []).append((xv, yv))

    if not any(points for points in series.values()):
        return _explain("No valid data points for the selected fields")

    if vs_mu_x:
        for label, points in series.items():
            arr = np.asarray(points, dtype=float)
            order = np.argsort(arr[:, 0], kind="stable")
            ax.plot(arr[order, 0], arr[order, 1], "o-", markersize=3.5,
                    linewidth=1.3, color=colors[label], label=label)
        ax.set_xlabel(_summary_axis_label("mu_x"))
    else:
        n_variants = max(len(series), 1)
        width = 0.8 / n_variants
        for k, (label, points) in enumerate(series.items()):
            xs = np.asarray([p[0] for p in points], dtype=float)
            ys = np.asarray([p[1] for p in points], dtype=float)
            offset = (k - (n_variants - 1) / 2.0) * width
            ax.bar(xs + offset, ys, width * 0.9,
                   color=colors[label], label=label)
        ax.set_xlabel("Case")
        ax.set_xticks(range(n_positions))
        ax.set_xticklabels(tick_names, fontsize=8)
        if max((len(name) for name in tick_names), default=0) > 12:
            for tick in ax.get_xticklabels():
                tick.set_rotation(30)
                tick.set_ha("right")

    ax.axhline(0, color="0.25", linestyle="--", linewidth=1.0)
    suffix = " (absolute)" if absolute_used else ""
    ax.set_ylabel(rf"{_summary_axis_label(field)} $\Delta$ vs base [%]"
                  f"{suffix}")
    ax.grid(True, axis="y", alpha=0.3)
    ax.legend(fontsize=7, title="Geometry", loc="best")

    condition_names = {str(getattr(r, "condition_name", "") or "")
                       for r in results_list}
    condition_names.discard("")
    n_conditions = len(condition_names) or n_positions
    fig.suptitle(rf"$\Delta$ vs base — {_summary_axis_label(field)} "
                 f"relative to {base_label} ({n_conditions} conditions)"
                 f"{suffix}",
                 fontsize=12, fontweight="bold")
    if owned_fig is not None:
        fig.tight_layout(rect=[0, 0, 1, 0.92])
    return _finish(ax, owned_fig, fname)


def plot_geometry_ranking(results_list, field: str, *,
                          ax=None, fname=None, ref_index: int = 0):
    """Horizontal bar ranking of the geometry variants for ONE summary
    quantity.

    ``results_list`` is the variant-major list produced by
    ``studies.compare_geometries``: every variant runs the same ordered
    conditions. ``ref_index`` selects which case of that ordered list
    supplies the ranked value (0, the default, ranks at the reference
    condition, that is, the first case each variant ran).

    ``field`` is a ``Results.summary`` key (``"FM"``, ``"CT"``,
    ``"eta_prop"`` and so on). Variants without a finite value for the
    field leave the ranking and do not draw a bar. The best side of the
    quantity comes first: descending for most coefficients, ascending for
    power-type keys (see ``_RANKING_LOWER_IS_BETTER``), so the top bar of
    the figure always carries the winner. The winner bar receives the
    highlight color; every bar receives its numeric annotation.

    The ``ax`` and ``fname`` parameters follow the module convention
    stated at the top of this file. The axis is returned.
    """
    results_list = list(results_list or [])
    ax, fig = _resolve_ax(ax, fname, figsize=(6, 4))
    groups = _group_by_geometry_label(results_list)

    entries = []
    for label, idxs in groups.items():
        position = int(min(max(int(ref_index), 0), len(idxs) - 1))
        result = results_list[idxs[position]]
        value = _summary_float((result.summary or {}).get(field))
        if np.isfinite(value):
            entries.append((str(label), float(value), idxs[position]))

    if not entries:
        ax.set_axis_off()
        message = ("No geometry-labeled results to rank" if not groups
                   else f"No finite {field} value to rank")
        ax.text(0.5, 0.5, message, ha="center", va="center",
                fontsize=10, color="0.35", transform=ax.transAxes)
        return _finish(ax, fig, fname)

    lower_is_better = field in _RANKING_LOWER_IS_BETTER
    entries.sort(key=lambda entry: entry[1], reverse=not lower_is_better)
    winner_label, winner_value, _ = entries[0]

    # `barh` draws the first name at the BOTTOM, so the reversed order
    # puts the winner (first after the sort) at the TOP of the figure.
    names = [entry[0] for entry in entries][::-1]
    values = [entry[1] for entry in entries][::-1]
    colors = ["#1a7f37" if name == winner_label else "tab:blue"
              for name in names]
    bars = ax.barh(names, values, color=colors, alpha=0.9)
    ax.margins(x=0.15)
    for bar_rect, value in zip(bars, values):
        ax.text(bar_rect.get_width(), bar_rect.get_y() + bar_rect.get_height() / 2,
                f"{value:.4g}", va="center", ha="left", fontsize=8)
    ax.set_xlabel(_summary_axis_label(field))
    ax.grid(True, axis="x", alpha=0.3)

    direction = "lowest" if lower_is_better else "highest"
    condition_name = str(getattr(results_list[entries[0][2]],
                                 "condition_name", "") or "")
    title = f"Geometry ranking ({condition_name})" if condition_name \
        else "Geometry ranking"
    ax.set_title(f"{title} — {direction} {_summary_axis_label(field)} "
                 f"wins: {winner_label}", fontsize=10)
    return _finish(ax, fig, fname)


def plot_optimization_convergence(history, objective_key: str, *,
                                  ax=None, fname=None,
                                  mode: str = "minimize"):
    """Convergence view of one design optimization.

    ``history`` is a list of dicts with at least an integer ``"eval"``
    entry and one entry keyed by ``objective_key``, in the format
    recorded by ``studies.optimize_design``. Rows without the objective
    key, and rows whose value is not finite, are skipped. A failed
    evaluation is absent from the record, and one bad point must not
    erase the good ones.

    Every evaluation is drawn as a marker joined into a line. A step
    line overlays the running best value. ``mode`` selects what the best
    value means: under ``"minimize"`` the step line follows the
    cumulative minimum, and under ``"maximize"`` it follows the
    cumulative maximum. The default is ``"minimize"``. Pass the
    ``objective_kind`` of the study that produced the history.

    The ``ax`` and ``fname`` parameters follow the module convention
    stated at the top of this file. The axis is returned.
    """
    if mode not in ("minimize", "maximize"):
        raise ValueError(
            f"mode must be 'minimize' or 'maximize' (got {mode!r}).")

    ax, fig = _resolve_ax(ax, fname)

    evals = []
    values = []
    for row in history or []:
        try:
            eval_number = int(row["eval"])
            value = float(row[objective_key])
        except (KeyError, TypeError, ValueError):
            continue
        if not np.isfinite(value):
            continue
        evals.append(eval_number)
        values.append(value)
    order = np.argsort(np.asarray(evals, dtype=float), kind="stable")
    evals = np.asarray(evals, dtype=float)[order]
    values = np.asarray(values, dtype=float)[order]

    if evals.size:
        ax.plot(evals, values, "o-", color="tab:blue",
                markersize=3.5, linewidth=1.3, label="evaluation")
        best = (np.minimum.accumulate(values) if mode == "minimize"
                else np.maximum.accumulate(values))
        ax.step(evals, best, where="post", color="tab:red",
                linestyle="--", linewidth=1.4, label=f"best so far ({mode})")
        ax.legend(fontsize=8)
    else:
        ax.text(0.5, 0.5, "No finite evaluation recorded", ha="center",
                va="center", fontsize=10, color="0.35", transform=ax.transAxes)
    ax.set_xlabel("Evaluation")
    ax.set_ylabel(_summary_axis_label(objective_key))
    ax.grid(True, alpha=0.3)
    ax.set_title("Optimization convergence")
    return _finish(ax, fig, fname)


# =============================================================================
# 12. BLADE DYNAMICS PLOTS (SC-11)
# =============================================================================

def _beta_angle_history(maps: dict) -> "np.ndarray | None":
    """Reconstructs beta(psi) [deg] on the psi grid from the flap
    coefficients stored in ``maps``; None on a rigid run."""
    coeffs = maps.get("beta_coeffs")
    psi_nodes = maps.get("psi_nodes")
    if not coeffs or psi_nodes is None:
        return None
    psi = np.asarray(psi_nodes, dtype=float)
    angle = np.full_like(psi, float(coeffs[0][0]), dtype=float)
    for n, (cn, sn) in coeffs.items():
        if n == 0:
            continue
        angle = angle + cn * np.cos(n * psi) + sn * np.sin(n * psi)
    return np.degrees(angle)


def plot_flap_response(maps: dict, ax=None, fname=None):
    """Polar plot of the flap angle over the azimuth, harmonics annotated.

    The curve is beta(psi) = beta_0 + sum_n [b_nc cos(n psi) + b_ns
    sin(n psi)] reconstructed from `maps['beta_coeffs']`; each harmonic's
    amplitude is annotated beside the legend, so the reader sees which
    orders the balance kept. A rigid run has nothing to draw."""
    beta_deg = _beta_angle_history(maps)
    if beta_deg is None:
        raise ValueError(
            "This result carries no blade-dynamics solution. Run a case "
            "with a flap model other than 'rigid' first.")
    psi = np.asarray(maps["psi_nodes"], dtype=float)
    psi_closed = np.concatenate([psi, [2.0 * np.pi]])
    beta_closed = np.concatenate([beta_deg, beta_deg[:1]])

    if ax is None:
        fig, ax = _new_figure((5.4, 4.6))
        ax.remove()
        ax = fig.add_subplot(111, projection="polar")
        fig_out = fig
    else:
        fig_out = ax.figure
    if not hasattr(ax, "set_theta_zero_location"):
        # A non-polar axes was passed in (embedded canvas): replace its
        # content with a polar subplot of the same figure.
        fig_out = ax.figure
        fig_out.clear()
        ax = fig_out.add_subplot(111, projection="polar")
    ax.plot(psi_closed, beta_closed, color="tab:blue", linewidth=1.6)
    ax.fill(psi_closed, beta_closed, color="tab:blue", alpha=0.15)
    ax.set_theta_zero_location("E")
    ax.set_theta_direction(1)
    ax.set_ylabel(r"$\beta$ [deg]", fontsize=9)

    parts = [rf"$\beta_0$={float(maps['beta_coeffs'][0][0]):.3f}$^\circ$"]
    from math import hypot
    for n in sorted(k for k in maps["beta_coeffs"] if k):
        cn, sn = maps["beta_coeffs"][n]
        parts.append(rf"$|\beta_{n}|$={hypot(cn, sn):.3f}$^\circ$")
    ax.legend([r"$\beta(\psi)$"], loc="lower left", fontsize=8,
              bbox_to_anchor=(-0.1, -0.12))
    ax.set_title(", ".join(parts), fontsize=8, pad=14)
    condition = describe_condition(maps)
    fig_out.suptitle(("Flap response — " + condition)
                     if condition else "Flap response",
                     fontsize=11, fontweight="bold")
    return _finish(ax, fig_out, fname)


def plot_flap_effect_map(maps_on: dict, maps_off: dict, field: str = "alpha_eff",
                          ax=None, fname=None):
    """Two disk maps of one field side by side, flapping OFF and ON.

    This is the figure that shows what the blade motion changes: the same
    condition solved twice, once with a rigid disk and once with the
    blade's flap response. The overall title states the flight condition,
    as always."""
    fig, axes = _new_figure((11.0, 4.6), 1, 2)
    axes = np.atleast_1d(axes).ravel()
    for ax_i, (maps, label) in zip(axes, ((maps_off, "flapping OFF"),
                                           (maps_on, "flapping ON"))):
        plt.sca(ax_i)
        plot_disk_map(maps, field=field, ax=ax_i, compact=True)
        ax_i.set_title(label, fontsize=10, pad=26)
    condition = describe_condition(maps_on)
    fig.suptitle((f"Effect of flapping on {disk_field_label(field)} — "
                  + condition) if condition else "Effect of flapping",
                 fontsize=12, fontweight="bold")
    fig.tight_layout(rect=[0, 0, 1, 0.92])
    return _finish_fig(fig, fname)


def plot_flap_convergence(history, tol_deg: float | None = None,
                           ax=None, fname=None):
    """Outer-loop trace: largest coefficient change [deg] per iteration."""
    history = [float(v) for v in (history or [])]
    ax, fig = _resolve_ax(ax, fname, figsize=(6, 4))
    if not history:
        ax.text(0.5, 0.5, "No outer-loop history recorded\n(rigid run?)",
                ha="center", va="center", fontsize=10, color="0.35",
                transform=ax.transAxes)
    else:
        ax.semilogy(range(1, len(history) + 1),
                    [max(v, 1e-12) for v in history],
                    marker="o", markersize=3.5, linewidth=1.3,
                    color="tab:purple")
        if tol_deg is not None and tol_deg > 0:
            ax.axhline(tol_deg, color="tab:red", linestyle="--",
                       linewidth=1.0)
            ax.annotate(f"tolerance {tol_deg:g}°", xy=(len(history), tol_deg),
                        fontsize=7, color="tab:red",
                        xytext=(2, 4), textcoords="offset points")
    ax.set_xlabel("Outer iteration")
    ax.set_ylabel(r"max $|\Delta\beta_n|$ [deg]")
    ax.grid(True, alpha=0.3)
    ax.set_title("Flapping outer-loop convergence")
    return _finish(ax, fig, fname)
