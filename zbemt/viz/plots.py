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

from ..viz import style as plot_style
plot_style.apply()

# Light-grey color used to "fill" (never leave empty/white) the regions
# masked by reverse flow, both in the disk contour plots and in the line
# plots (vs. span / vs. azimuth) -- see `_shade_reverse_regions` and the
# masking block in `plot_disk_map`.
_REVERSE_MASK_COLOR = "0.85"

# DPI used only when a function saves a figure. The GUI can change this
# value for a whole export without affecting the interactive canvases.
_EXPORT_DPI = 150


def set_export_dpi(dpi: int) -> None:
    """Sets the resolution of the figures saved by the exporter."""
    global _EXPORT_DPI
    _EXPORT_DPI = max(48, int(dpi))


def _nova_figura(figsize, nrows: int = 1, ncols: int = 1):
    """Creates a ``Figure`` OUTSIDE pyplot's global registry.

    `plt.subplots` keeps the figure in pyplot's manager, and it only
    leaves it via `plt.close`. The functions in this module that RETURN
    the figure (for the GUI to embed in a canvas) could never close it --
    so every redraw of the Results tab leaked an 11/16-panel figure, which
    pyplot kept alive forever ("More than 20 figures have been opened"
    after ~20 plot changes, with memory/time growing with session use). A
    `Figure` built directly does not enter any registry: Python's garbage
    collector reclaims it once nothing references it anymore, and
    `fig.savefig` still works the same way.
    """
    fig = Figure(figsize=figsize)
    axes = fig.subplots(nrows, ncols) if (nrows, ncols) != (1, 1) else fig.add_subplot(111)
    return fig, axes


def _resolve_ax(ax, fname, figsize=(6, 4)):
    if ax is not None:
        return ax, None
    fig, ax = _nova_figura(figsize)
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
    rotor — leading edge + trailing edge + closure at the root and at the
    tip of each blade — in the same azimuth convention as the rest of the
    platform (psi=0 along +X, blades equally spaced at
    ``360/n_blades`` degrees; see ``bemt.element_state``/``visualization.py``).

    Unlike ``plot_geometry`` (which only shows the chord MAGNITUDE as a
    function of r/R, a single curve regardless of how many blades exist),
    this plot draws the actual outline of each blade — so
    ``geom.n_blades`` visibly changes the drawing (2 blades -> 2 opposite
    outlines; 4 blades -> 4 outlines at 90°; etc.), useful for checking
    interference/overlap between neighboring blades in rotors with large
    chord or few blades."""
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
    ax.set_title(f"Planform — {n_blades} blade(s)")
    return _finish(ax, fig, fname)


def plot_chord_twist_distribution(geom, ax=None, fname=None):
    """geom: models.RotorGeometryDef

    Normalized chord (left) and twist in degrees (right), two Y axes
    sharing the X axis (r/R) -- read directly from
    ``geom.r_norm``/``chord_norm``/``twist_deg``, without recomputing
    anything (docs/plano_v3.md Part 6.1). Used by the "Chord/Twist" tab of
    the embedded Geometry canvas; equivalent in content to
    ``plot_geometry``, but with a name/use dedicated to the live canvas
    (``plot_geometry`` still exists, used by the exportable report and by
    legacy calls)."""
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
    for pontos, faces in visualization.build_rotor_disk(geom, n_span=32):
        vertices = np.asarray(pontos)[np.asarray(faces).reshape(-1, 5)[:, 1:]]
        ax.add_collection3d(Poly3DCollection(vertices, alpha=0.85,
                                               facecolor="steelblue",
                                               edgecolor="none"))
    raio = float(geom.radius_m)
    ax.set_xlim(-raio, raio); ax.set_ylim(-raio, raio); ax.set_zlim(-raio * .25, raio * .25)
    ax.set_xlabel("x [m]"); ax.set_ylabel("y [m]"); ax.set_zlabel("z [m]", labelpad=-8)
    ax.set_title("Rotor blade geometry — 3D")
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
    single polar -- used by the embedded canvas of the Airfoil tab
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
        partes = []
        if reynolds is not None:
            partes.append(f"Re={float(reynolds):.3g}")
        if mach is not None:
            partes.append(f"M={float(mach):.3g}")
        condicao = ", ".join(partes)
        label = f"{label} ({condicao})" if label else condicao
    line, = ax.plot(alpha_deg, cl, "-", label=f"Cl · {label}" if label else r"$C_L$")
    ax.plot(alpha_deg, cd, "--", color=line.get_color(), alpha=0.6,
            label=f"Cd · {label}" if label else r"$C_D$")
    ax.set_xlabel(r"$\alpha$ [deg]")
    ax.set_ylabel(r"$C_L$, $C_D$")
    ax.set_title(r"Polar $C_L(\alpha)$ / $C_D(\alpha)$")
    ax.legend(fontsize=8)
    return _finish(ax, fig, fname)


def plot_cl_alpha(alpha_deg, cl, ax=None, fname=None, label=None):
    """C_L(alpha) alone -- one of the 3 mini plot tabs of the Airfoil tab
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
    """C_D(alpha) alone -- see `plot_cl_alpha`."""
    ax, fig = _resolve_ax(ax, fname)
    ax.plot(alpha_deg, cd, "-", label=label)
    ax.set_xlabel(r"$\alpha$ [deg]")
    ax.set_ylabel(r"$C_D$")
    ax.set_title(r"$C_D \times \alpha$")
    if label:
        ax.legend(fontsize=8)
    return _finish(ax, fig, fname)


def plot_cd_cl(cl, cd, ax=None, fname=None, label=None):
    """Drag polar C_D x C_L alone -- see `plot_cl_alpha`."""
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
    # field in maps -> (label in mathtext/LaTeX -- MATLAB style, with
    # superscript/subscript and Greek letters --, unit, is_angle?)
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


#: Same symbol as `_DISK_FIELD_META`, in HTML instead of mathtext -- for
#: whoever does NOT draw with matplotlib (the "Field" combo of the Results
#: tab, which paints the item with a `QTextDocument`; see
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
    matplotlib -- the 2D maps already read `_DISK_FIELD_META` directly,
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
    def _num(chave):
        valor = maps.get(chave)
        if not isinstance(valor, (int, float)) or isinstance(valor, bool):
            return None
        valor = float(valor)
        return None if np.isnan(valor) else valor

    partes = []
    mu_x = _num("mu_x")
    if mu_x is not None:
        partes.append(rf"$\mu_x$={mu_x:.3f}")
    # Vz and alpha describe the SAME axial component via two paths; they
    # only enter when nonzero, otherwise they clutter every hover title.
    vv = _num("Vz")
    if vv is not None and abs(vv) > 1e-9:
        partes.append(rf"$V_v$={vv:.3g} m/s")
    alpha = _num("alpha_rotor_deg")
    if alpha is not None and abs(alpha) > 1e-9:
        partes.append(rf"$\alpha$={alpha:.2f}°")
    # Collective and RPM enter WHENEVER they exist: they are the two
    # controls the user actually moved, and without them the title of a
    # hover case was just "mu_x=0.000" -- identical for every hover in
    # the project, which made it impossible to say which sweep the
    # figure came from.
    coletivo = _num("collective_deg")
    if coletivo is not None:
        partes.append(rf"$\theta_0$={coletivo:.2f}°")
    rpm = _num("rpm")
    if rpm is not None:
        partes.append(rf"{rpm:.0f} rpm")
    # In a trimmed case, the target is what defines the condition (the
    # collective/RPM above is a RESULT of the trim, not an input) -- saying
    # what the target was prevents reading a resolved collective as if it
    # had been chosen.
    ct = _num("CT")
    if ct is not None and maps.get("trim_mode"):
        partes.append(rf"$C_T$={ct:.5f}")
    return ", ".join(partes)


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
#: radius guide circles need to stay ABOVE it -- drawn below, they existed
#: in the figure and did not appear on any disk: the filled contour paints
#: over anything at a lower zorder.
_ZORDER_CAMPO = 2
_ZORDER_GUIAS = _ZORDER_CAMPO + 1


def _add_r_guides(ax, r_max, fractions=(0.25, 0.5, 0.75)):
    """DASHED guide circles, thin and unlabeled, at r/R=0.25/0.5/0.75
    (visual orientation only: they say at what radius a field feature is,
    with no legend or annotation).

    They live at `_ZORDER_GUIAS`, i.e. ABOVE the field's `tricontourf` --
    previously they were drawn at zorder 1, below the contour, and the
    fill covered them completely on EVERY disk (the `show_r_guides`
    parameter existed but had no visible effect). They are artists of the
    disk's axis: they do not enter the color bar nor touch the data
    range."""
    theta = np.linspace(0, 2 * np.pi, 200)
    for frac in fractions:
        rr = frac * r_max
        ax.plot(rr * np.cos(theta), rr * np.sin(theta),
                linestyle=(0, (4, 3)), linewidth=0.6, color="0.30", alpha=0.40,
                zorder=_ZORDER_GUIAS)


def _shade_reverse_regions(ax, x: np.ndarray, reverse_mask: np.ndarray,
                            color: str = _REVERSE_MASK_COLOR, alpha: float = 0.6,
                            zorder: float = 0.0):
    """Shades in light grey the stretches of ``x`` (assumed sorted, not
    necessarily uniform) where ``reverse_mask`` is True -- used to mark
    reverse flow (``Ut<0``) in LINE plots (vs. span / vs. azimuth), in the
    same spirit as the masking of the disk contour plots (see
    ``plot_disk_map``): the "masked" region is filled with light grey,
    never left empty/white. Detects the contiguous stretches of
    ``reverse_mask`` and draws a grey ``axvspan`` for each one (low
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
    slice with no data point there -- producing the "white gap"/incorrect
    interpolation artifact that can appear in that slice or spread to
    neighboring slices depending on the local aspect ratio of the mesh
    triangulated by Delaunay."""
    psi0 = PSI[:, :1]
    PSI_closed = np.concatenate([PSI, psi0 + 2.0 * np.pi], axis=1)
    closed = tuple(np.concatenate([f, f[:, :1]], axis=1) for f in fields_2d)
    return (PSI_closed,) + closed


#: How many times the tail needs to exceed the body of the data for the
#: color scale to be clipped. 5x is deliberately generous: a field with a
#: strong but continuous gradient (Ut, W) passes through untouched; only
#: the pathological case triggers it, where half a dozen singular
#: elements push the maximum to another order of magnitude.
_FATOR_DE_CAUDA_EXTREMA = 5.0

#: Percentiles that define the "body" of the data.
_PERCENTIL_BAIXO, _PERCENTIL_ALTO = 0.5, 99.5


def _faixa_de_cor_robusta(z_finite, lo: float, hi: float):
    """Clips the color scale when a few singular elements dominate it.
    Returns ``(lo, hi, extend)``.

    Reason, seen on screen: in a case whose tip Mach exceeds 1 on the
    advancing blade, the compressibility correction divides Cl by
    sqrt(1-M^2) -> ~0 in TWO elements out of 7776. The maximum Cl jumped
    from 2.5 (99th percentile) to 599, and the color scale stretched by
    these two points painted the ENTIRE disk in the same color: four of
    the sixteen grid panels turned into a uniform purple rectangle with
    one yellow pixel. The data was not wrong in the file -- it was
    illegible on screen.

    Clipping here is a DRAWING decision, not a data one: ``maps`` is not
    touched, and the color bar gets the "continues beyond this value"
    arrow (``extend``), so the clipping is visible rather than silent.
    Whoever wants the full range supplies ``vmin``/``vmax``.
    """
    if z_finite.size < 20:
        return lo, hi, ""
    p_lo, p_alto = np.percentile(z_finite, [_PERCENTIL_BAIXO, _PERCENTIL_ALTO])
    corpo = p_alto - p_lo
    if not np.isfinite(corpo) or corpo <= 0:
        return lo, hi, ""
    corta_alto = (hi - p_alto) > _FATOR_DE_CAUDA_EXTREMA * corpo
    corta_baixo = (p_lo - lo) > _FATOR_DE_CAUDA_EXTREMA * corpo
    if not (corta_alto or corta_baixo):
        return lo, hi, ""
    novo_lo = float(p_lo) if corta_baixo else lo
    novo_hi = float(p_alto) if corta_alto else hi
    extend = ("both" if (corta_alto and corta_baixo)
              else ("max" if corta_alto else "min"))
    return novo_lo, novo_hi, extend


def _eixo_de_barra_de_cor(ax, r_max: float, compact: bool):
    """Creates the color bar's axis (``cax``) WITHIN the right margin of
    the disk's own axis, with the SAME HEIGHT as the disk.

    Why not `fig.colorbar(..., ax=ax, shrink=...)`: `shrink` is a
    fraction of the axis's ORIGINAL box (the subplot's), not the box
    already adjusted by `set_aspect("equal", adjustable="box")`. The disk
    occupies only part of that box (the x range is larger than the y one,
    to fit the azimuth label and the bar), so the bar came out visibly
    taller than the disk drawing -- the reported defect: "the color bar
    is much taller than the disk and wastes height".

    `Axes.inset_axes` solves this because it positions the child via a
    locator evaluated AT DRAW TIME, as a fraction of the box already
    adjusted by the aspect ratio: asking for the y range from -r_max to
    +r_max returns exactly the disk's height, whatever the figsize or the
    grid cell.

    The bar lives in the gap between the right azimuth label and the
    axis limit, and the bar's numbers grow to the right within that same
    gap (see `margem_direita` in `plot_disk_map`).
    """
    x0, x1 = ax.get_xlim()
    y0, y1 = ax.get_ylim()
    def fx(x):
        return (x - x0) / (x1 - x0)
    def fy(y):
        return (y - y0) / (y1 - y0)
    # In the grid, the "Adv." legend ends near 1.35R. The bar used to
    # start at 1.40R and the two texts overlapped on the resized canvas.
    esquerda = (1.55 if compact else 1.50) * r_max
    largura = (0.10 if compact else 0.09) * r_max
    return ax.inset_axes([fx(esquerda), fy(-r_max),
                          fx(x0 + largura) - fx(x0), fy(r_max) - fy(-r_max)])


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
    to the LEFT -- equivalent to rotating the polar angle by -90
    degrees before converting to Cartesian (same
    `theta_for_pol2cart = PSI - pi/2` as MATLAB).

    Closes the azimuthal periodicity (see `_close_azimuth_2d`) before
    triangulating -- without this, `tricontourf` produced a "white slice"
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
    The masked region is filled with a light grey (`_REVERSE_MASK_COLOR`)
    instead of being left empty/white, so it is not confused with
    "no data".

    `log_color`/`vmin`/`vmax`: the COLOR scale (not the x/y axes -- those
    are already zoomable via `NavigationToolbar2QT`, see `gui.CanvasHost`).
    `NavigationToolbar2QT` does not know how to edit the range/scale of the
    color of a `tricontourf` (it only handles `AxesImage`, not
    `QuadContourSet`), so this control is explicitly exposed here and in
    the GUI (Results, "Disk map" block). `log_color=True` silently falls
    back to linear if the field has no positive value at all (LogNorm
    requires vmin>0).

    `show_r_guides` (default True): three thin dashed circles at
    r/R=0.25/0.5/0.75, with no label or legend, to say at a glance at
    what radius a field feature is -- see `_add_r_guides`. They are
    artists of the axis: they do not appear in the color bar nor change
    the data range.

    `cbar_label`: bar label text, for when the default ("symbol
    [unit]" from `_DISK_FIELD_META`) does not fit -- this is the case for
    DIAGNOSTIC fields, which are not physical quantities cataloged there
    (the iteration count of `plot_convergence`). `levels`: explicit
    contour levels, for discrete fields (same origin).

    The color bar has the HEIGHT OF THE DISK and lives in the right
    margin of the axis itself -- see `_eixo_de_barra_de_cor`.
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
        lo, hi, auto_extend = _faixa_de_cor_robusta(z_finite, lo, hi)
    if hi <= lo:
        hi = lo + 1e-9
    norm = None
    niveis_pedidos = levels
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
    if niveis_pedidos is not None:
        # Explicit levels from the caller override everything: they exist
        # for DISCRETE fields (iteration count in the convergence figure),
        # where 21 linear levels produce bands of "3.45 iterations".
        levels = niveis_pedidos
        extend = "neither"

    contour_kwargs = dict(levels=levels, cmap=cmap, norm=norm, extend=extend)
    if reverse_c is not None:
        triang = mtri.Triangulation(X.ravel(), Y.ravel())
        node_reverse = reverse_c.ravel()
        # Masks the triangle if ANY of its 3 vertices are in reverse
        # flow -- leaves a clean "hole" in the region, like MATLAB's
        # NaN, without requiring NaN in the Z array itself (which
        # matplotlib's tricontourf rejects).
        tri_mask = np.any(node_reverse[triang.triangles], axis=1)

        # Before drawing the data field, fills the SAME masked region
        # (triangles in reverse flow) with light grey -- via the
        # COMPLEMENTARY mask on the same triangulation -- so the "hole"
        # in the main contour is never left empty/white.
        if np.any(tri_mask):
            triang_reverse = mtri.Triangulation(X.ravel(), Y.ravel(), triangles=triang.triangles)
            triang_reverse.set_mask(~tri_mask)
            ax.tripcolor(triang_reverse, facecolors=np.zeros(triang.triangles.shape[0]),
                         cmap=ListedColormap([_REVERSE_MASK_COLOR]),
                         zorder=_ZORDER_CAMPO - 1)

        triang.set_mask(tri_mask)
        cf = ax.tricontourf(triang, Z_c.ravel(), zorder=_ZORDER_CAMPO, **contour_kwargs)
    else:
        cf = ax.tricontourf(X.ravel(), Y.ravel(), Z_c.ravel(),
                            zorder=_ZORDER_CAMPO, **contour_kwargs)
    ax.set_aspect("equal", adjustable="box")
    label, unit, _ = _DISK_FIELD_META.get(field, (field, "-", False))
    # NO title per disk (see `describe_condition`): with many disks on the
    # same page, one title would touch the disk above it. What the
    # variable is moved to the top LEFT corner of the color bar and the
    # unit to the top RIGHT corner (below, alongside the bar); the
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
    # sector name is worth it -- the angle is already implicit in the
    # position.
    if compact:
        label_kwargs = dict(fontsize=7, color="0.35")
        direita, cima, esquerda, baixo = "Adv.", "Front", "Ret.", "Back"
    else:
        label_kwargs = dict(fontsize=8, color="0.15")
        direita, cima = r"90° (Adv.)", r"180° (Front)"
        esquerda, baixo = r"270° (Ret.)", r"0° (Back)"
    ax.text(r_max * 1.06, 0, direita, ha="left", va="center", **label_kwargs)
    ax.text(0, r_max * 1.06, cima, ha="center", va="bottom", **label_kwargs)
    ax.text(-r_max * 1.06, 0, esquerda, ha="right", va="center", **label_kwargs)
    ax.text(0, -r_max * 1.06, baixo, ha="center", va="top", **label_kwargs)
    # Reference cross limited to the disk (+10%): with `axhline`/`axvline`
    # it crossed the ENTIRE axis width, and the right margin now
    # hosts the color bar -- the line would go right under it.
    cruz = 1.10 * r_max
    ax.plot([-cruz, cruz], [0, 0], color="0.6", linestyle=":", linewidth=0.6,
            zorder=_ZORDER_GUIAS)
    ax.plot([0, 0], [-cruz, cruz], color="0.6", linestyle=":", linewidth=0.6,
            zorder=_ZORDER_GUIAS)
    # The right margin now hosts the ENTIRE color bar (see
    # `_eixo_de_barra_de_cor`), not just the azimuth label: it needs to
    # fit the label ("90° (Adv.)"), the bar and its numbers. With the old
    # margin the bar's numbers spilled out of the axis -- and, in a grid,
    # invaded the neighboring cell. Widening in x does not shrink the disk
    # while the cell is limited by HEIGHT (which is the case both in the
    # grid and in the individual figure); what is gained is the bar no
    # longer stealing width.
    margem_direita = 2.25 if compact else 1.95
    # The vertical margin has to fit the TEXT, not just the point where it
    # starts: "Front" begins at 1.06 with `va="bottom"`, so it rises
    # above that. With the old 1.22 it left the axis and ended up inside
    # the cell above -- in the 16-disk grid the "Front" of one row
    # appeared stuck to the "Back" of the previous row, both cut in half.
    margem_vertical = 1.34 if compact else 1.28
    ax.set_xlim(-r_max * 1.25, r_max * margem_direita)
    ax.set_ylim(-r_max * margem_vertical, r_max * margem_vertical)
    ax.set_aspect("equal", adjustable="box")
    ax.set_xticks([]); ax.set_yticks([])
    for spine in ax.spines.values():
        spine.set_visible(False)

    fig_to_use = fig if fig is not None else ax.figure
    if fig_to_use is not None:
        # The bar has the HEIGHT OF THE DISK and lives in the right margin
        # of the axis itself -- see `_eixo_de_barra_de_cor` for why it is
        # not `colorbar(ax=..., shrink=...)`.
        cax = _eixo_de_barra_de_cor(ax, r_max, compact)
        cb = fig_to_use.colorbar(cf, cax=cax)
        cb.ax.tick_params(labelsize=7 if compact else 8)
        # Bar label: ALWAYS "symbol [unit]" in a single piece.
        rotulo = cbar_label if cbar_label is not None else (
            f"{label} [{unit}]" if unit and unit != "-" else label)
        if compact:
            # The label used to sit to the left of the bar and fall ON
            # the disk on compact screens. Above the bar itself there is
            # space between the grid rows, reserved by the figure layout.
            cb.ax.text(0.0, 1.02, rotulo, transform=cb.ax.transAxes,
                        ha="left", va="bottom", fontsize=7)
        else:
            # Single disk: there is no cell above to collide with, and
            # the top of the bar is the natural place for the label.
            cb.ax.text(0.0, 1.04, rotulo, transform=cb.ax.transAxes,
                        ha="left", va="bottom", fontsize=11)

    # Figure with a SINGLE disk (individual export or GUI canvas): the
    # condition is the figure's title -- in a grid panel (`compact`) the
    # one setting the title is `plot_disk_map_grid`, once for all disks.
    if not compact and fig_to_use is not None:
        condicao = describe_condition(maps)
        if condicao:
            fig_to_use.suptitle(condicao, fontsize=11, fontweight="bold")
    return _finish(ax, fig, fname)


# Fixed order/grouping of the fields requested for the full disk grid:
# forces, section aerodynamics, flow kinematics, angles, and the
# tangential-force decomposition + Mach/dynamic pressure -- always in
# this order for visual comparability between runs. The last 4 (Ft_i,
# Ft_p, Mach, q) were added after the original 12 so as not to disturb
# the order/position for whoever was already comparing the first 12
# panels between runs.
_DISK_GRID_FIELDS = ["Fn", "Ft", "Cl", "Cd", "Vi", "Up",
                     "Ut", "W", "alpha_eff", "phi", "lambda_z_field", "lambda_i",
                     "Ft_i", "Ft_p", "Mach", "q"]


def plot_disk_map_grid(maps: dict, fields=None, fname=None, ncols: int = 4,
                        cmap: str = "viridis", figsize_per_panel: float = 3.2,
                        mask_reverse: bool = True):
    """Grid with ALL the important disk variables in a single panel:
    Fn, Ft, Cl, Cd, Vi, Up, Ut, W, alpha (deg), phi (deg), lambda (total),
    lambda_i (induced) -- see `_DISK_GRID_FIELDS`. Angles are always in
    degrees. Each subplot gets thin, unlabeled dotted guide circles
    at r/R=0.25/0.5/0.75 (visual orientation only).

    `fields`: custom list of fields (default: the 12 from
    `_DISK_GRID_FIELDS`). `fname`: if supplied, saves the figure and
    closes it; otherwise returns the `Figure` for interactive/embedded use.
    `mask_reverse`: passed through to each panel's `plot_disk_map` (see
    its docstring) -- default True, same default as `BEMTConfig.
    mask_reverse_flow_plots`.
    """
    fields = list(fields) if fields is not None else list(_DISK_GRID_FIELDS)
    n = len(fields)
    ncols = min(ncols, n)
    nrows = int(np.ceil(n / ncols))
    # Cell wider than tall: the disk's axis has equal aspect and the x
    # range is larger than the y one (extra room on the right for label
    # and bar), so a square cell left empty bands between the rows.
    fig, axes = _nova_figura((figsize_per_panel * ncols,
                               figsize_per_panel * 0.86 * nrows), nrows, ncols)
    axes = np.atleast_1d(axes).ravel()

    # ONE condition title for the whole figure (not one per disk): each
    # disk identifies its variable in its own color bar -- see
    # `plot_disk_map`/`describe_condition`.
    condicao = describe_condition(maps)
    title = f"Disk maps — {condicao}" if condicao else "Disk maps"
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
    # exactly at that size and comes out as planned -- that is why the
    # same plot looked good in the report and broken in the GUI. In the
    # Results tab the figure goes into a `FigureCanvasQTAgg`, which
    # stretches it to the widget's size (~8x4.6 in, a different aspect
    # ratio); the margins stay the ones computed for 12.8x11, but the
    # fonts stay in POINTS and do not shrink along with it -- result: the
    # field label falling inside the disk and "Ret."/"Adv." colliding
    # with the color bar.
    #
    # The "constrained" engine reruns the calculation on every `draw`, so
    # the figure recomposes itself on every canvas resize.
    # The GUI canvas is shorter/narrower than the report's PNG. A minimal
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
_CMAP_ITERACOES = "YlOrRd"

#: Color of the elements that did NOT converge, marked on top of the map.
_COR_NAO_CONVERGIDO = "#1f4ed8"


def _resumo_de_convergencia(results: "Results") -> dict:
    """Header numbers of the convergence figure, taken from `summary`
    when they exist and recomputed from the maps when they do not (old
    exports and hand-built `Results` have one or the other, it never
    fails for lack of a key)."""
    maps = results.maps or {}
    summary = results.summary or {}
    convergido = np.asarray(maps["converged"], dtype=bool) if "converged" in maps else None
    n_iter = np.asarray(maps["n_iter"], dtype=float) if "n_iter" in maps else None

    pct = summary.get("convergence_pct")
    if pct is None and convergido is not None and convergido.size:
        pct = 100.0 * float(np.mean(convergido))
    media = summary.get("mean_iter")
    if media is None and n_iter is not None and n_iter.size:
        media = float(np.mean(n_iter))
    return dict(
        pct=None if pct is None else float(pct),
        media=None if media is None else float(media),
        maximo=None if n_iter is None or not n_iter.size else int(np.max(n_iter)),
        n_elementos=None if convergido is None else int(convergido.size),
        n_falhos=None if convergido is None else int(np.count_nonzero(~convergido)),
        solver=summary.get("solver") or maps.get("solver"),
        varreduras=maps.get("total_iterations"),
        elapsed=summary.get("elapsed_s", maps.get("elapsed")),
    )


def _formatar_tempo(segundos) -> str:
    """Time in ms/s according to the order of magnitude (a solver that
    runs in 5 ms should not appear as "0.005 s")."""
    try:
        s = float(segundos)
    except (TypeError, ValueError):
        return "—"
    return f"{s * 1e3:.0f} ms" if s < 1.0 else f"{s:.2f} s"


def _cartoes_de_numero(ax, cartoes):
    """Row of "cards" (large value on top, small label below) on a
    frameless axis -- where the convergence figure's header numbers live.

    Replaces the two percentage BARS that used to take up the whole
    figure: a "98.5%" bar next to a "7 iterations" one compares
    nothing (different quantities, different scales), spends the whole
    figure and says less than the number itself written out."""
    from matplotlib.patches import FancyBboxPatch

    ax.set_axis_off()
    ax.set_xlim(0, 1); ax.set_ylim(0, 1)
    n = max(len(cartoes), 1)
    largura = 1.0 / n
    # Font proportional to the REAL width of each card: the same figure
    # is generated at 11 inches (report) and at 6 (GUI canvas), and at a
    # fixed size the labels of neighboring cards overlapped in the GUI.
    pol_por_cartao = ax.figure.get_figwidth() * ax.get_position().width / n
    fonte_valor = float(np.clip(13.0 * pol_por_cartao / 1.6, 8.0, 13.0))
    fonte_rotulo = float(np.clip(7.5 * pol_por_cartao / 1.6, 5.5, 7.5))
    for i, (valor, rotulo, cor) in enumerate(cartoes):
        x0 = i * largura
        ax.add_patch(FancyBboxPatch(
            (x0 + 0.012, 0.10), largura - 0.024, 0.80,
            boxstyle="round,pad=0,rounding_size=0.04",
            transform=ax.transAxes, facecolor="0.965", edgecolor="0.86",
            linewidth=0.8, clip_on=False, zorder=0))
        centro = x0 + largura / 2
        ax.text(centro, 0.56, valor, ha="center", va="center",
                fontsize=fonte_valor, fontweight="bold", color=cor, zorder=1)
        ax.text(centro, 0.26, rotulo, ha="center", va="center",
                fontsize=fonte_rotulo, color="0.35", zorder=1)


def _layout_de_convergencia(ax, fname, com_disco: bool, com_historico: bool):
    """Assembles the convergence figure (disk | history / numbers) from
    the `ax` the caller supplied, or from a new figure.

    The GUI and the report call `plot_convergence` the usual way --
    `ax=fig.add_subplot(111)` or `fname=...` --, and this signature does
    not change. Since the figure now has more than one panel, the
    received `ax` is replaced by panels created in the SAME grid spot
    (`get_subplotspec().subgridspec`), instead of requiring every caller
    to know how to assemble the layout (it would be the same code
    repeated in the GUI, in the report and in the tests). An `ax` with no
    `subplotspec` (created via `fig.add_axes`) falls back to the
    whole-figure path.
    """
    if ax is None:
        largura = 11.0 if com_disco else 7.0
        # Without a disk and without history, all that is left is the
        # card row: a tall figure would be almost all empty space.
        altura = 4.4 if (com_disco or com_historico) else 2.2
        fig = Figure(figsize=(largura, altura))
        spec = fig.add_gridspec(1, 1)[0, 0]
    else:
        fig = ax.figure
        spec = ax.get_subplotspec()
        ax.remove()
        if spec is None:
            spec = fig.add_gridspec(1, 1)[0, 0]

    if com_disco:
        externo = spec.subgridspec(1, 2, width_ratios=[1.0, 1.25], wspace=0.30)
        ax_disco = fig.add_subplot(externo[0, 0])
        coluna = externo[0, 1]
    else:
        ax_disco = None
        coluna = spec

    if com_historico:
        interno = coluna.subgridspec(2, 1, height_ratios=[3.2, 1.0], hspace=0.55)
        ax_hist = fig.add_subplot(interno[0, 0])
        ax_num = fig.add_subplot(interno[1, 0])
    else:
        # Without history, the card row remains a ROW: if it occupied
        # the whole column, four giant rectangles with one number each
        # would take up half the figure.
        interno = coluna.subgridspec(3, 1, height_ratios=[1.0, 1.1, 1.0])
        ax_hist = None
        ax_num = fig.add_subplot(interno[1, 0])
    return fig, ax_disco, ax_hist, ax_num


def _desenhar_disco_de_convergencia(ax, maps: dict):
    """Disk map of the NUMBER OF ITERATIONS per element, with the
    non-converged elements marked on top.

    This is the actionable diagnostic: the difficult elements are not
    scattered at random -- they concentrate at the root, at the tip and
    at the reverse-flow boundary, and that is what tells you where to act
    (mesh, relaxation, model). A global percentage does not localize
    anything.

    Without `mask_reverse`: precisely the reverse-flow region is one of
    the ones that costs the solver most, and hiding it here would erase
    half the answer.
    """
    n_iter = np.asarray(maps["n_iter"], dtype=float)
    # Iteration count is DISCRETE: one color band per integer value,
    # and bar ticks on the integers themselves -- with the default's 21
    # linear levels the bar announced "3.45 iterations".
    n_lo = int(np.floor(np.nanmin(n_iter))) if n_iter.size else 0
    n_hi = int(np.ceil(np.nanmax(n_iter))) if n_iter.size else 1
    niveis = np.arange(n_lo - 0.5, n_hi + 1.0, 1.0)
    plot_disk_map(maps, field="n_iter", ax=ax, cmap=_CMAP_ITERACOES,
                  mask_reverse=False, compact=True,
                  cbar_label="iterations",
                  levels=niveis if niveis.size >= 2 else None)
    ax.set_title("Iterations per element", fontsize=9, color="0.25")
    if ax.child_axes:
        ax.child_axes[0].set_yticks(np.arange(n_lo, n_hi + 1, max(1, (n_hi - n_lo) // 8 + 1)))

    convergido = np.asarray(maps["converged"], dtype=bool) if "converged" in maps else None
    if convergido is None or convergido.all():
        return
    R_NORM = np.asarray(maps["R_NORM"], dtype=float)
    PSI = np.asarray(maps["PSI"], dtype=float)
    theta = PSI - np.pi / 2
    falhos = ~convergido
    ax.plot(R_NORM[falhos] * np.cos(theta[falhos]),
            R_NORM[falhos] * np.sin(theta[falhos]),
            linestyle="none", marker="o", markersize=2.6,
            color=_COR_NAO_CONVERGIDO, zorder=_ZORDER_GUIAS + 1,
            label="not converged")
    ax.legend(loc="upper left", fontsize=7, frameon=True, framealpha=0.85,
              borderpad=0.3, handletextpad=0.3)


def plot_convergence(results: "Results", ax=None, fname=None):
    """Convergence diagnostic of the inflow solver, in three pieces:

    1. WHERE the solver struggled -- disk map of the number of iterations
       per element, with the non-converged elements marked
       (`_desenhar_disco_de_convergencia`). Only appears when the result
       carries the maps (`n_iter`/`R_NORM`/`PSI`).
    2. HOW it progressed -- converged-mesh fraction and true maximum
       residual per sweep. Needs `BEMTConfig.collect_history=
       True` (default); with it off, `maps["frac_converged_history"]`
       comes back EMPTY and the panel is replaced by a warning saying so
       -- previously the figure came out blank, which reads as "did not
       converge" instead of "did not record the history".
    3. HOW MUCH it cost -- the header numbers in cards
       (`_cartoes_de_numero`).

    Each piece appears if and only if the data exists: a `Results` that
    only has `summary` (old export, no maps or history) still produces
    the card row, with no empty axis or meaningless bar.
    """
    maps = results.maps or {}
    hist = list(maps.get("frac_converged_history") or [])
    resid = list(maps.get("residual_history") or [])
    com_disco = all(k in maps for k in ("R_NORM", "PSI", "n_iter"))
    com_historico = bool(hist or resid)
    resumo = _resumo_de_convergencia(results)

    fig, ax_disco, ax_hist, ax_num = _layout_de_convergencia(
        ax, fname, com_disco, com_historico)

    if ax_disco is not None:
        _desenhar_disco_de_convergencia(ax_disco, maps)

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
            linhas = (ax_hist.get_lines() if hist else []) + ax_res.get_lines()
            ax_hist.legend(linhas, [l.get_label() for l in linhas],
                           loc="center right", fontsize=7.5)
        ax_hist.set_xlabel("solver sweep", fontsize=8)
        ax_hist.tick_params(axis="x", labelsize=8)
        ax_hist.grid(True, alpha=0.3)

    pct = resumo["pct"]
    cartoes = []
    if pct is not None:
        cor = "#1a7f37" if pct >= 99.999 else ("#b45309" if pct >= 95.0 else "#b91c1c")
        cartoes.append((f"{pct:.1f}%", "converged", cor))
    if resumo["n_falhos"]:
        cartoes.append((f"{resumo['n_falhos']}/{resumo['n_elementos']}", "elements left",
                        _COR_NAO_CONVERGIDO))
    if resumo["media"] is not None:
        cartoes.append((f"{resumo['media']:.1f}", "mean iters", "0.15"))
    if resumo["maximo"] is not None:
        cartoes.append((f"{resumo['maximo']}", "max iters", "0.15"))
    if resumo["elapsed"] is not None:
        cartoes.append((_formatar_tempo(resumo["elapsed"]), "solver time", "0.15"))
    if not cartoes:
        ax_num.set_axis_off()
        ax_num.text(0.5, 0.5, "No convergence data available", ha="center",
                    va="center", fontsize=11, color="0.35", transform=ax_num.transAxes)
    if not com_historico and cartoes:
        # Without history the right panel would be an empty rectangle: the
        # cards rise to its middle and the reason for the emptiness gets written.
        ax_num.text(0.5, -0.04,
                    'Iteration history not recorded — enable "collect_history" and run again.',
                    ha="center", va="top", fontsize=7.5, color="0.45",
                    transform=ax_num.transAxes)

    partes = ["Solver convergence"]
    if resumo["solver"]:
        partes.append(str(resumo["solver"]))
    if resumo["n_elementos"]:
        partes.append(f"{resumo['n_elementos']} elements")
    if resumo["varreduras"]:
        partes.append(f"{int(resumo['varreduras'])} sweeps")
    fig.suptitle(partes[0] + (f"  ({', '.join(partes[1:])})" if len(partes) > 1 else ""),
                 fontsize=11, fontweight="bold")
    fig.tight_layout(rect=[0, 0, 1, 0.94])
    # The cards are drawn AFTER the layout: their font size depends on
    # the panel's final width (see `_cartoes_de_numero`), and before
    # `tight_layout` that width will still change.
    if cartoes:
        _cartoes_de_numero(ax_num, cartoes)
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
#: different names -- it is a different nondimensionalization (rho*n^2*D^4
#: instead of rho*A*(Omega*R)^2, see `bemt.aggregate_results` Sec.6c) and a
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


def _paineis_de_varredura(results_list) -> list:
    """Chooses the panel set by the result's CONVENTION.

    `aggregate_results` records `cfg_is_propeller` in each `Results`'s
    `summary`, so the choice comes from what was actually run -- not
    from an extra parameter the caller would have to remember to pass
    (and that the GUI, the CLI, and the report would forget in
    different places)."""
    if results_list:
        primeiro = results_list[0].summary
        if primeiro.get("cfg_is_propeller") or primeiro.get("is_propeller"):
            return _PROP_SWEEP_PANELS
    return _MU_SWEEP_PANELS


# Maps each factorial variable (`studies._FACTORIAL_VARIABLES`) to the
# `Results.summary` key that carries its resolved value, and to a
# friendly axis/title label -- Part 4.2 ("Coefficients vs axis"
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
def _chave_de_agrupamento(valor):
    """Rounds a value before using it as a grouping KEY for series
    (``plot_coefficients_vs_axis``/``plot_xy``).

    Several ``Results.summary`` columns used for grouping (in
    particular ``alpha_rotor_deg``, which an ``alpha_deg`` sweep
    resolves via ``Vz=tan(alpha)*V`` and then reconstructs via
    ``atan2(Vz, V)``) are the result of a floating-point calculation,
    not a typed-in value -- comparing by EXACT EQUALITY sliced a single
    nominal sweep (e.g. alpha = -3, -2, ..., 3) into several
    near-duplicate series because of ~1e-4 noise, one per combination
    with the other axis (seen on screen: ~20 alpha curves where the
    user asked for 7). Rounding to 3 decimal places preserves any
    sweep with an actual step larger than 0.001 (the vast majority)
    and merges the floating-point noise into the same series."""
    if isinstance(valor, float):
        arredondado = round(valor, 3)
        # round(-0.0002, 3) == -0.0: numerically equal to 0.0, but
        # formats as "-0" instead of "0" (`f"{-0.0:g}"`) -- two
        # combinations of the same nominal value near zero, one coming
        # from positive noise and the other from negative noise, kept
        # turning into DIFFERENT labels (and therefore series) after
        # the very rounding that was supposed to unite them.
        return arredondado + 0.0
    return valor


#: DEFAULT tolerance (in the quantity's own units) for deciding whether two
#: grouping values are "the same value". Adjustable by the user via the
#: "Group tolerance" control on the Results tab.
TOLERANCIA_DE_AGRUPAMENTO_PADRAO = 0.01


def _ordem_de_grupo(chave):
    """Orders the series by grouping key: numeric in ascending order,
    non-numeric afterwards, in alphabetical order. The legend used to
    come out in the results' APPEARANCE order, which for a factorial is
    the order of the cartesian product -- ``alpha = 0, -10, -5, 5, 10``
    on screen, with the reader having to hunt for the right curve
    instead of reading it off."""
    if isinstance(chave, (int, float)) and not isinstance(chave, bool):
        return (0, float(chave), "")
    return (1, 0.0, str(chave))


def mapa_de_agrupamento(valores, tol: float = TOLERANCIA_DE_AGRUPAMENTO_PADRAO) -> dict:
    """Map ``raw value -> canonical series key``, merging values that
    are less than ``tol`` apart from each other.

    Why a TOLERANCE and not just the rounding from
    `_chave_de_agrupamento`: rounding is a fixed grid, and two values
    of the SAME nominal value can fall into neighboring cells of it.
    That is what was seen on screen -- a sweep of alpha = -10, -5, 0,
    5, 10 (whose alpha is reconstructed via ``atan2(Vz, V)``, with
    error of ~1e-3 depending on the mu_x of each combination) produced
    the series ``-10.002``, ``-10.001``, ``-10``, ``-9.999``,
    ``-9.997``: five curves of one or two points where the user asked
    for ONE. Rounding does not fix this because the noise crosses the
    grid boundary; grouping by PROXIMITY does.

    Gap-based grouping (1D single-linkage): sorted values, cut where
    the next neighbor is more than ``tol`` away. A legitimate sweep
    with a step larger than ``tol`` remains separate -- that is
    exactly what the tolerance means, and why it belongs to the user,
    not fixed.

    The canonical key is the group average rounded to ``tol`` itself
    (with ``tol=0.01``, a group around -9.9995 becomes ``-10.0``, not
    a ``-9.9995`` that would give away in the legend the noise that
    was just merged). Non-numeric values (and NaN) are their own key.
    """
    numericos: list[float] = []
    mapa: dict = {}
    for v in valores:
        if isinstance(v, (int, float)) and not isinstance(v, bool):
            fv = float(v)
            if np.isnan(fv):
                mapa[v] = v
                continue
            numericos.append(fv)
        else:
            mapa[v] = v

    if not numericos:
        return mapa

    try:
        tol = float(tol)
    except (TypeError, ValueError):
        tol = TOLERANCIA_DE_AGRUPAMENTO_PADRAO
    if not np.isfinite(tol) or tol <= 0.0:
        # Null/invalid tolerance = previous behavior (3-decimal grid),
        # never an exception in the middle of a plot refresh.
        for v in numericos:
            mapa[v] = _chave_de_agrupamento(v)
        return mapa

    ordenados = sorted(set(numericos))
    grupo = [ordenados[0]]
    grupos = [grupo]
    for anterior, atual in zip(ordenados, ordenados[1:]):
        if atual - anterior <= tol:
            grupo.append(atual)
        else:
            grupo = [atual]
            grupos.append(grupo)

    for g in grupos:
        canonica = round(float(np.mean(g)) / tol) * tol
        # +0.0 kills the "-0" (same trap as `_chave_de_agrupamento`);
        # the second rounding removes the binary residue from
        # `x/tol*tol` (0.1*3 = 0.30000000000000004 would render as
        # label "0.3" but a distinct key from a 0.3 arriving another way).
        canonica = round(canonica, 12) + 0.0
        for v in g:
            mapa[v] = canonica
    return mapa


_AXIS_LABELS = {
    "mu_x": (r"$\mu_x$", "advance ratio ($\\mu_x$)"),
    "alpha_deg": (r"$\alpha_{rotor}$ (deg)", "rotor disk angle of attack"),
    "collective_deg": (r"$\theta_{col}$ (deg)", "collective pitch"),
    "rpm": ("RPM", "rotation"),
}

# =============================================================================
# Axis/mathtext labels shared by ANY `Results.summary` key -- used by
# `plot_xy` (the "Custom X-Y" part, requested by the user: plot any
# quantity vs any other, in a single panel, grouped by a third one).
# Builds on `_AXIS_LABELS`/`_SHORT_SYMBOLS`/`_MU_SWEEP_PANELS`/
# `_PROP_SWEEP_PANELS` (which already covered the 4 factorial axes and
# the 11+9 panel coefficients) instead of duplicating -- see CLAUDE.md
# "a new field needs to be wired into the right surfaces": here the
# surface is only labeling, not .bemt/CLI, so a local table is enough.
# Each entry: summary key -> mathtext label READY for the axis
# (symbol + unit in brackets when dimensional, "[-]" when not).
_SUMMARY_KEY_LABELS = {
    # --- flight condition / input ---------------------------------------
    "mu_x": r"$\mu_x$ [-]", "mu_z": r"$\mu_z$ [-]",
    "J_x": r"$J_x$ [-]", "J_z": r"$J_z$ [-]",
    "Vz": r"$V_z$ [m/s]", "Vz_total": r"$V_{z,total}$ [m/s]",
    "Vx": r"$V_x$ [m/s]",
    "alpha_rotor_deg": r"$\alpha_{rotor}$ [deg]",
    "collective_deg": r"$\theta_{col}$ [deg]",
    "rpm": "RPM [-]", "lambda_z": r"$\lambda_z$ [-]",
    "lambda_i": r"$\lambda_i$ [-]", "lambda_total": r"$\lambda_{total}$ [-]",
    # --- dimensional forces/moments --------------------------------------
    "Thrust": r"$T$ [N]", "Torque": r"$Q$ [N$\cdot$m]",
    "Power": r"$P$ [W]", "Power_i": r"$P_i$ [W]", "Power_p": r"$P_p$ [W]",
    "H": r"$H$ [N]", "Hi": r"$H_i$ [N]", "Hp": r"$H_p$ [N]",
    "Y": r"$Y$ [N]", "Mx": r"$M_x$ [N$\cdot$m]", "My": r"$M_y$ [N$\cdot$m]",
    # --- coefficients, rotor convention -----------------------------------
    "CT": r"$C_T$ [-]", "CQ": r"$C_Q$ [-]", "CP": r"$C_P$ [-]",
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


#: The same labels in a PROPELLER's axis letters: x is the rotor's axis
#: (see `bemt.py`, Sec.6c, and `api._SIMBOLO_DE_COLUNA_HELICE`, which does
#: the same swap in its table). A plot of CT vs. J_x with "J_x" being the
#: IN-PLANE ratio -- zero throughout straight cruise -- would be a
#: vertical curve with nothing to explain why.
_SUMMARY_KEY_LABELS_HELICE = {
    # axial component: in propeller axes, the one with index x
    "Vz": r"$V_x$ [m/s]", "mu_z": r"$\mu_x$ [-]", "J_z": r"$J_x$ [-]",
    "Vz_total": r"$V_{x,total}$ [m/s]", "lambda_z": r"$\lambda_x$ [-]",
    # in-plane component: the cross-flow, in z
    "Vx": r"$V_z$ [m/s]",
    "mu_x": r"$\mu_z$ [-]",
    "J_x": r"$J_z$ [-]",
    # The TWO ANGLES are deliberately left out of this swap: each has
    # ONE symbol only, the same in both modes, and each mode shows only
    # ITS OWN -- `alpha_rotor` (from the disk plane) for the rotor,
    # `alpha_disk` (from the shaft) for the propeller. See
    # `api._COLUNAS_SUPRIMIDAS_EM_HELICE`/`_EM_ROTOR`.
}

_SUMMARY_KEY_LABELS["alpha_disk_deg"] = r"$\alpha_{disk}$ [deg]"
_SUMMARY_KEY_LABELS["Vi"] = r"$v_i$ [m/s]"


def _summary_axis_label(key: str, is_propeller: bool = False) -> str:
    """Mathtext axis label for any ``Results.summary`` key (see
    `_SUMMARY_KEY_LABELS`); falls back to the key's own name (unformatted)
    when unknown -- never fails, even for a new key or a
    ``cfg_*``/``rotor_*`` with no dedicated entry.

    ``is_propeller`` swaps the axis letters (`_SUMMARY_KEY_LABELS_HELICE`)
    without touching the value or the key."""
    if is_propeller and key in _SUMMARY_KEY_LABELS_HELICE:
        return _SUMMARY_KEY_LABELS_HELICE[key]
    return _SUMMARY_KEY_LABELS.get(key, key)


# =============================================================================
# Mathtext -> Unicode
# =============================================================================
# `_SUMMARY_KEY_LABELS` is matplotlib mathtext: whatever DRAWS renders
# `$\mu_x$` as μ. Whatever just DISPLAYS TEXT -- a QComboBox on the
# Results tab, a table header -- shows the raw LaTeX source, and that is
# what was seen on screen: "mu_x  ($\mu_x$ [-])", "CT  ($C_T$ [-])". Here
# the same table becomes plain text, so a SECOND label list does not
# exist (which would silently go stale -- CLAUDE.md, "don't create a
# third list").
_GREGAS_UNICODE = {
    r"\alpha": "α", r"\beta": "β", r"\gamma": "γ", r"\delta": "δ",
    r"\theta": "θ", r"\lambda": "λ", r"\mu": "μ", r"\nu": "ν",
    r"\pi": "π", r"\rho": "ρ", r"\sigma": "σ", r"\phi": "φ",
    r"\psi": "ψ", r"\omega": "ω", r"\Omega": "Ω", r"\eta": "η",
    r"\infty": "∞", r"\cdot": "·", r"\times": "×", r"\pm": "±",
    r"\circ": "°",
}
#: Only the letters/digits that EXIST as a subscript in Unicode. "T" (from
#: C_T) does not exist -- it becomes plain "T", which reads well ("CT")
#: and is infinitely better than "$C_T$".
_SUBSCRITOS_UNICODE = {
    "0": "₀", "1": "₁", "2": "₂", "3": "₃", "4": "₄", "5": "₅",
    "6": "₆", "7": "₇", "8": "₈", "9": "₉",
    "a": "ₐ", "e": "ₑ", "h": "ₕ", "i": "ᵢ", "j": "ⱼ", "k": "ₖ",
    "l": "ₗ", "m": "ₘ", "n": "ₙ", "o": "ₒ", "p": "ₚ", "r": "ᵣ",
    "s": "ₛ", "t": "ₜ", "u": "ᵤ", "v": "ᵥ", "x": "ₓ",
}


def _subscrito_unicode(texto: str) -> str:
    """Converts to Unicode subscript when ALL characters have a
    subscript form; otherwise returns the text as is (a half-converted
    subscript -- "Cᵢnf" -- reads worse than "Cinf")."""
    if texto and all(c in _SUBSCRITOS_UNICODE for c in texto):
        return "".join(_SUBSCRITOS_UNICODE[c] for c in texto)
    return texto


def rotulo_em_texto(mathtext: str) -> str:
    """Plain-text (Unicode) version of a mathtext label.

    ``r"$C_{T,prop}$ [-]"`` -> ``"CT,prop [-]"``; ``r"$\\mu_x$ [-]"`` ->
    ``"μₓ [-]"``; ``r"$Q$ [N$\\cdot$m]"`` -> ``"Q [N·m]"``. Used by the GUI
    (X/Y/grouping combos on the Results tab) and by any surface that
    shows the label as TEXT, not as a drawing."""
    if not mathtext:
        return ""
    if "$" not in mathtext and "\\" not in mathtext:
        # Not mathtext: it is the key's own name (`_summary_axis_label`
        # falls back to it for keys with no entry). Passes through
        # unchanged -- without this, the `_x` of `cfg_solver` would
        # become a subscript ("cfgₛolver").
        return mathtext
    texto = mathtext
    for macro, simbolo in _GREGAS_UNICODE.items():
        texto = texto.replace(macro + " ", simbolo).replace(macro, simbolo)
    texto = texto.replace(r"\,", " ").replace(r"\ ", " ")
    # subscripts: `_{...}` (with braces) and `_x` (a single character)
    texto = re.sub(r"_\{([^}]*)\}", lambda m: _subscrito_unicode(m.group(1)), texto)
    texto = re.sub(r"_(\w)", lambda m: _subscrito_unicode(m.group(1)), texto)
    texto = texto.replace("$", "").replace("{", "").replace("}", "")
    return texto.strip()


def rotulo_de_summary_em_texto(key: str, is_propeller: bool = False) -> str:
    """`_summary_axis_label` already in plain text -- what the GUI shows."""
    return rotulo_em_texto(_summary_axis_label(key, is_propeller))


#: HTML entities for the Greek letters, for `rotulo_em_html`. Kept
#: separate from `_GREGAS_UNICODE` on purpose: Qt renders both forms, but
#: the entity survives a `QTextDocument` built from an HTML source
#: without depending on the encoding of the file that loaded it.
_GREGAS_HTML = {
    r"\alpha": "&alpha;", r"\beta": "&beta;", r"\gamma": "&gamma;",
    r"\delta": "&delta;", r"\theta": "&theta;", r"\lambda": "&lambda;",
    r"\mu_x": "&mu;<sub>x</sub>", r"\mu": "&mu;",
    r"\nu": "&nu;", r"\pi": "&pi;", r"\rho": "&rho;",
    r"\sigma": "&sigma;", r"\phi": "&phi;", r"\psi": "&psi;",
    r"\omega": "&omega;", r"\Omega": "&Omega;", r"\eta": "&eta;",
    r"\infty": "&infin;", r"\cdot": "&middot;", r"\times": "&times;",
    r"\pm": "&plusmn;", r"\circ": "&deg;",
}


def rotulo_em_html(mathtext: str) -> str:
    """HTML version of a mathtext label, with a real subscript.

    ``r"$C_T$ [-]"`` -> ``"C<sub>T</sub> [-]"``; ``r"$\\mu_x$ [-]"`` ->
    ``"&mu;<sub>x</sub> [-]"``. Used by the combos that paint the item
    with a `QTextDocument` (`_ComboDeSimbolos`, on the Results tab) --
    it is what lets "C_T" render with the T BELOW the line, instead of
    as plain text. Complements `rotulo_em_texto` (plain Unicode), for
    when the destination is a plain Qt label, without rich text."""
    if not mathtext:
        return ""
    if "$" not in mathtext and "\\" not in mathtext:
        # not mathtext: it is the key's raw name (see `rotulo_em_texto`)
        return mathtext
    texto = mathtext
    for macro, entidade in _GREGAS_HTML.items():
        texto = texto.replace(macro + " ", entidade).replace(macro, entidade)
    texto = texto.replace(r"\,", " ").replace(r"\ ", " ")
    texto = re.sub(r"_\{([^}]*)\}", lambda m: f"<sub>{m.group(1)}</sub>", texto)
    texto = re.sub(r"_(\w)", lambda m: f"<sub>{m.group(1)}</sub>", texto)
    texto = texto.replace("$", "").replace("{", "").replace("}", "")
    return texto.strip()


def rotulo_de_summary_em_html(key: str, is_propeller: bool = False) -> str:
    """`_summary_axis_label` already in HTML -- what the Results tab's
    combos paint."""
    return rotulo_em_html(_summary_axis_label(key, is_propeller))


#: PROSE description of each disk map field -- what the field MEANS,
#: without a code variable name. It is the text shown on hovering over
#: an item in the Results tab's combos (user request: "the extended
#: name, in prose, not the internal representation").
#: `_DISK_FIELD_META` remains the source of the field SET: a key with
#: no entry here simply gets no description.
_DISK_FIELD_DESCRICAO = {
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
    return _DISK_FIELD_DESCRICAO.get(field, "")


def flatten_selection(entries) -> list:
    """Flattens a heterogeneous selection of ``models.ResultEntry``
    (single cases + batches, docs/plano_v3.md Part 4.2) into a flat
    list of ``Results``, in the order they appear in ``entries``. A
    ``kind="case"`` entry contributes 1 element (``entry.results`` is
    the ``Results`` itself); a ``kind="batch"`` entry contributes all
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
                                group_tol: float = TOLERANCIA_DE_AGRUPAMENTO_PADRAO):
    """Grid with the 11 global coefficients (CT, CQ, FM, CY, CMx, CMy, CH,
    CHp, CHi, CPp, CPi) as a function of ``axis`` -- generalizes the old
    `plot_coefficients_vs_mu` (kept below as a shortcut) to any of the 4
    factorial variables in `studies._FACTORIAL_VARIABLES` ("mu_x",
    "alpha_deg", "collective_deg", "rpm") -- Part 4.2, "Coefficients vs
    axis".

    ``series_labels``: optional, parallel to ``results_list`` (same
    length). When omitted (default), all results are combined into a
    SINGLE curve per panel, sorted by increasing ``axis`` ("combine"
    mode). When provided with 2+ distinct labels, draws one curve PER
    label, overlaid on the same panel ("overlay" mode, useful for
    comparing 2+ selections from the Results history side by side) --
    see `ResultsTab._refresh_batch` in gui.py.

    ``group_tol``: tolerance for series auto-detection (values closer
    than this are the same nominal value -- `mapa_de_agrupamento`).
    """
    key = _AXIS_TO_SUMMARY_KEY.get(axis, axis)
    axis_label, axis_title = _AXIS_LABELS.get(axis, (axis, axis))
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
        # propeller sweep -- `mu_x` locked at ~0 (atan2 denominator ~0)
        # while `Vz` sweeps through zero. Treating it as a "second axis
        # varying" in this specific case split the sweep into TWO
        # spurious series -- the V=0 point alone in one curve, the rest
        # in another.
        #
        # The PREVIOUS condition ("exclude alpha_deg whenever mu_x OR Vz
        # have more than one value across the whole list") was too
        # broad: `mu_x` varies in practically ANY mu_x sweep (it is the
        # X axis!), so it suppressed grouping by alpha even in a
        # legitimate 2-axis factorial (mu_x x alpha_deg) -- the entire
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
        avanco_axial_degenerado = (
            len(mu_vals) <= 1 and (not mu_vals or abs(next(iter(mu_vals))) < 1e-9)
            and len(vv_vals) > 1)
        if avanco_axial_degenerado:
            other_keys = [(sk, ax) for sk, ax in other_keys if ax != "alpha_deg"]

        # One tolerance per quantity: two values closer than
        # `group_tol` are THE SAME nominal value, both for deciding
        # whether the quantity VARIED and for labeling the series (see
        # `mapa_de_agrupamento`).
        swept_other_vars = []
        chaves_por_grandeza: dict = {}
        for skey, ax_name in other_keys:
            vals = [r.summary.get(skey, None) for r in results_list]
            chave_de = mapa_de_agrupamento(
                [v for v in vals
                 if v is not None and not (isinstance(v, float) and np.isnan(v))], group_tol)
            chaves_por_grandeza[skey] = chave_de
            if len(set(chave_de.values())) > 1:
                swept_other_vars.append((skey, ax_name))

        _SHORT_SYMBOLS = {
            "mu_x": r"$\mu_x$",
            "alpha_deg": r"$\alpha_{rotor}$",
            "collective_deg": r"$\theta_{col}$",
            "rpm": "RPM",
        }

        ordem_por_label: dict = {}
        for i, r in enumerate(results_list):
            label_parts = []
            ordem = []
            for skey, ax_name in swept_other_vars:
                bruto = r.summary.get(skey)
                val = chaves_por_grandeza[skey].get(bruto, _chave_de_agrupamento(bruto))
                if val is not None and not (isinstance(val, float) and np.isnan(val)):
                    symbol = _SHORT_SYMBOLS.get(ax_name, ax_name)
                    label_parts.append(f"{symbol}={val:g}" if isinstance(val, (int, float)) else f"{symbol}={val}")
                    ordem.append(_ordem_de_grupo(val))

            lbl = ", ".join(label_parts)
            ordem_por_label.setdefault(lbl, tuple(ordem))
            groups.setdefault(lbl, []).append(i)
        # Legend in value order, not appearance order (see `_ordem_de_grupo`).
        groups = {k: groups[k] for k in sorted(groups, key=lambda k: ordem_por_label.get(k, ()))}

    overlay = len(groups) > 1 or (series_labels is not None and len(set(series_labels)) > 1)

    paineis = _paineis_de_varredura(results_list)
    n = len(paineis)
    ncols = min(ncols, n)
    nrows = int(np.ceil(n / ncols))
    fig, axes = _nova_figura((4.0 * ncols, 3.0 * nrows), nrows, ncols)
    axes = np.atleast_1d(axes).ravel()

    for i, (ax, (field_key, ylabel, title)) in enumerate(zip(axes, paineis)):
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
        limite_y = max(abs(float(v)) for v in ax.get_ylim())
        if 0.0 < limite_y < 1e-3:
            # The global offset (e.g. ``1e-5``) sits above the axis and
            # can collide with the title of the panel on the next row.
            ax.yaxis.set_major_formatter(
                FuncFormatter(lambda valor, _pos: f"{valor:.1e}"))
    if overlay:
        axes[0].legend(fontsize=7)
    for j in range(n, len(axes)):
        axes[j].axis("off")

    modo = "Propeller" if paineis is _PROP_SWEEP_PANELS else "Rotor"
    fig.suptitle(rf"{modo} performance vs {axis_title}", fontsize=12, fontweight="bold")
    fig.tight_layout(rect=[0, 0, 1, 0.95], h_pad=3.0, w_pad=1.5)
    return _finish_fig(fig, fname)


def plot_coefficients_vs_mu(results_list, fname=None, ncols: int = 4):
    """Backward-compatible: shortcut for
    ``plot_coefficients_vs_axis(results_list, axis="mu_x", ...)``, same
    signature/behavior as always."""
    return plot_coefficients_vs_axis(results_list, axis="mu_x", fname=fname, ncols=ncols)


def plot_xy(results_list, x_key: str, y_key: str, group_by: str | None = None,
            ax=None, fname=None,
            group_tol: float = TOLERANCIA_DE_AGRUPAMENTO_PADRAO,
            is_propeller: bool = False):
    """Free plot: ANY ``Results.summary`` key on the X axis, ANY other
    on the Y axis, optionally grouped into one curve per distinct value
    of ``group_by`` (also a summary key, e.g. "collective_deg" for a
    curve per collective/alpha/etc.) -- user request: "plot anything
    against anything from the whole batch, several curves, one per
    grouping variable". Complements (does not replace)
    `plot_coefficients_vs_axis`, which remains the fixed 11/9-panel
    grid used in the report.

    Points with missing or NaN ``x_key``/``y_key`` are simply ignored
    (never brings down the whole plot for 1 incomplete result). Within
    each curve, points are sorted by increasing X -- same convention as
    `plot_coefficients_vs_axis`.

    ``group_tol``: ``group_by`` values closer than this fall into the
    SAME curve (see `mapa_de_agrupamento`).
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
        brutos = [r.summary.get(group_by, None) for r in results_list]
        chave_de = mapa_de_agrupamento(
            [v for v in brutos if v is not None
             and not (isinstance(v, float) and np.isnan(v))], group_tol)
        for r, gv in zip(results_list, brutos):
            if gv is None or (isinstance(gv, float) and np.isnan(gv)):
                continue
            groups.setdefault(chave_de.get(gv, gv), []).append(r)
        groups = {k: groups[k] for k in sorted(groups, key=_ordem_de_grupo)}
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
    titulo_y = _summary_axis_label(y_key, is_propeller).split(" [")[0]
    titulo_x = _summary_axis_label(x_key, is_propeller).split(" [")[0]
    ax.set_title(f"{titulo_y} vs {titulo_x}")
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
    fixed azimuths (one curve per azimuth) -- equivalent to
    `plot_blade_loads` from zBEMT MATLAB. Angles always in degrees.

    `mask_reverse` (default True, same as `mask_reverse_flow_plots` in
    `plot_disk_map`): for each curve (one fixed azimuth), the r/R
    stretches where `Ut<0` (reverse flow) are shaded in light gray
    (`_REVERSE_MASK_COLOR`, via `_shade_reverse_regions`) and the curve
    itself is interrupted (NaN) over that stretch -- it never ends up
    empty/white, and never draws the field's (possibly nonsensical)
    value there.
    """
    r_norm = np.asarray(maps["r_norm_nodes"], dtype=float)
    psi_nodes_deg = np.degrees(np.asarray(maps["psi_nodes"], dtype=float))
    Ut = np.asarray(maps["Ut"], dtype=float) if "Ut" in maps else None

    n = len(_BLADE_LOAD_FIELDS)
    ncols = min(ncols, n)
    nrows = int(np.ceil(n / ncols))
    fig, axes = _nova_figura((3.6 * ncols, 2.6 * nrows), nrows, ncols)
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
    a set of fixed radial stations (one curve per r/R) -- equivalent to
    `plot_loads_vs_azimuth` from zBEMT MATLAB. Angles always in degrees.

    `mask_reverse` (default True, same as `mask_reverse_flow_plots` in
    `plot_disk_map`): for each curve (one fixed radial station), the
    azimuth stretches where `Ut<0` (reverse flow) are shaded in light
    gray (`_REVERSE_MASK_COLOR`, via `_shade_reverse_regions`) and the
    curve itself is interrupted (NaN) over that stretch -- it never
    ends up empty/white, and never draws the field's (possibly
    nonsensical) value there.
    """
    r_norm = np.asarray(maps["r_norm_nodes"], dtype=float)
    psi_nodes_deg = np.degrees(np.asarray(maps["psi_nodes"], dtype=float))
    Ut = np.asarray(maps["Ut"], dtype=float) if "Ut" in maps else None

    n = len(_BLADE_LOAD_FIELDS)
    ncols = min(ncols, n)
    nrows = int(np.ceil(n / ncols))
    fig, axes = _nova_figura((3.6 * ncols, 2.6 * nrows), nrows, ncols)
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
