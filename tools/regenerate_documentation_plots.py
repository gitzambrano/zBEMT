"""Regenerates the 18 figures under ``docs/img/`` that zBEMT produces on its own.

The "external" figures (``docs/img/externas/``) are third-party and are NOT
touched here -- only the ones the engine itself generates.

Each figure reproduces the CONTENT of the original figure (the one the
caption in ``docs/documentation.html`` describes), with two deliberate
adjustments:

  * all on-screen text in English (rule 7 of CLAUDE.md: user-facing text is
    English; comments and docstrings stay in pt-BR, like this one);
  * the reference rotor is now the current ``projects/starter_rotor``,
    instead of the embedded ``build_example_rotor()`` the old figures used.

Each figure's caption in the HTML is the specification: if a figure here
stops matching the caption, the figure is the one that's wrong. Several
captions cite rotor/airfoil numbers (``alpha_stall``, ``mu_x``, ...); when
changing a condition here, update the corresponding caption in the HTML.

Usage (zero arguments, like every script in the project)::

    python tools/regenerate_documentation_plots.py
"""
from __future__ import annotations

import sys
from copy import deepcopy
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

from zbemt import airfoils, api, bemt, studies
from zbemt.models import FlightCondition
from zbemt.viz import style

style.apply()

#: Reference project for the whole documentation.
PROJECT = REPO / "projects" / "starter_rotor"
OUTPUT_DIR = REPO / "docs" / "img"

# Colors from the original figures (not `style`'s tab10 palette): steel
# blue, dark red and green, which is what the old figures used.
BLUE = "#2e6e9e"
RED = "#9e3033"
GREEN = "#2e9e52"
GRAY = "0.45"

#: Mesh for the DISK figures (map/contour): needs to resolve the gradient
#: near the tip and the reverse-flow boundary. Not the project's production
#: mesh (150x360) because each figure runs several cases.
NE_DISK, NPSI_DISK = 80, 144
#: Mesh for the SWEEPS: only integrated coefficients go into the figure,
#: and the integral converges well before the map does.
NE_SWEEP, NPSI_SWEEP = 40, 72


# =============================================================================
# Infrastructure
# =============================================================================

def _project(ne: int, npsi: int, **config):
    """Copy of starter_rotor with mesh and config overrides applied."""
    proj = deepcopy(api.open_project(str(PROJECT)))
    proj.config.update({"Ne": ne, "Npsi": npsi})
    proj.config.update(config)
    return proj


def _run_case(proj, *, mu_x: float, collective_deg: float = 8.0, rpm: float = 1200.0,
          Vz: float = 0.0, name: str = "case"):
    return api.run_case(proj, FlightCondition(
        name=name, mu_x=mu_x, Vz=Vz, collective_deg=collective_deg, rpm=rpm))


def _save_figure(fig, name: str, *, tight: bool = True):
    if tight:
        fig.tight_layout()
    path = OUTPUT_DIR / name
    fig.savefig(path, dpi=150, bbox_inches="tight")
    plt.close(fig)
    print(f"  ok  {name}")


def _radial_index(maps, target: float) -> int:
    """Index of the radial station closest to ``target`` (in r/R)."""
    return int(np.argmin(np.abs(np.asarray(maps["r_norm_nodes"]) - target)))


#: Below this fraction of the largest positive value, a negative excursion
#: is solver numerical noise, not a real negative inflow.
_RELEVANT_SIGNAL_FRACTION = 0.02


def _norm_centered_on_zero(Z):
    """`TwoSlopeNorm` at 0 for a field that REALLY changes sign.

    A DIVERGING colormap (RdBu_r) only communicates something if white
    falls exactly on zero: without this, white falls in the middle of the
    data range (an arbitrary value), and "blue" stops meaning "negative
    inflow".

    But centering on zero a field whose minimum is -0.001 is even worse:
    `TwoSlopeNorm` stretches that -0.001 over HALF the colormap, and a
    numerically negligible excursion turns into a saturated navy-blue
    patch (seen in `glauert_local`/`coleman_local`, whose minimum is
    solver noise near the root). Hence the threshold: only center when the
    negative part is large enough to be physical."""
    import matplotlib.colors as mcolors
    zmin, zmax = float(np.nanmin(Z)), float(np.nanmax(Z))
    if zmin < 0.0 < zmax and abs(zmin) > _RELEVANT_SIGNAL_FRACTION * abs(zmax):
        return mcolors.TwoSlopeNorm(vmin=zmin, vcenter=0.0, vmax=zmax)
    return None


def _draw_disk_map(ax, maps, field, *, cmap="viridis", levels=24, vmin=None, vmax=None,
                   norm=None, with_orientation=False):
    """Draws a (Ne,Npsi) field on the disk, in the ENGINE's convention.

    ψ=0 pointing DOWN (aft), ψ=90° to the RIGHT (advancing blade), ψ=180°
    pointing UP (nose), ψ=270° to the LEFT (retreating) -- that is,
    ``theta = PSI - pi/2``, exactly what `viz.plots.plot_disk_map` (and
    therefore the GUI) draws.

    The OLD figures in this documentation used forward-flight-up, a
    convention different from the program's own: someone reading the
    documentation and then opening the Results tab would see the same
    field mirrored, with nothing saying the orientation had changed.
    Aligned here with the engine.
    """
    R = np.asarray(maps["R_NORM"])
    PSI = np.asarray(maps["PSI"])
    Z = np.asarray(maps[field]) if isinstance(field, str) else np.asarray(field)
    X = R * np.sin(PSI)
    Y = -R * np.cos(PSI)
    # Closes the disk in ψ: without repeating the first column at the end,
    # a blank slice is left between the last ψ and 2π (visible as a "cut"
    # in the disk in the old figures).
    X = np.concatenate([X, X[:, :1]], axis=1)
    Y = np.concatenate([Y, Y[:, :1]], axis=1)
    Z = np.concatenate([Z, Z[:, :1]], axis=1)
    if norm is not None:
        cf = ax.contourf(X, Y, Z, levels=levels, cmap=cmap, norm=norm)
    else:
        cf = ax.contourf(X, Y, Z, levels=levels, cmap=cmap, vmin=vmin, vmax=vmax)
    root_radius = float(np.min(R))
    ang = np.linspace(0, 2 * np.pi, 200)
    ax.add_patch(plt.Circle((0, 0), root_radius, facecolor="white", edgecolor="none", zorder=3))
    ax.plot(np.cos(ang), np.sin(ang), "-", color="black", lw=1.0, zorder=4)
    ax.set_aspect("equal")
    ax.set_xlim(-1.08, 1.08)
    ax.set_ylim(-1.08, 1.08)
    ax.grid(False)
    if with_orientation:
        # Same labels as `plots.plot_disk_map`, so the documentation
        # figure reads the same as the one in the Results tab.
        for x, y, txt, ha, va in ((1.02, 0, "Adv.", "left", "center"),
                                   (-1.02, 0, "Ret.", "right", "center"),
                                   (0, 1.02, "Front", "center", "bottom"),
                                   (0, -1.02, "Back", "center", "top")):
            ax.text(x, y, txt, ha=ha, va=va, fontsize=8, color="0.35")
    return cf


# =============================================================================
# 2.3 -- Radial-azimuthal mesh (fig. 11-1)
# =============================================================================

def fig_mesh():
    """Disk mesh in a REDUCED example (Ne=12, Npsi=24).

    Ne/Npsi here are for visualization, not the project's own: with the
    production mesh the points turn into a solid smear and the figure
    stops showing what it exists to show -- that the discretization is
    (r, ψ)."""
    proj = api.open_project(str(PROJECT))
    root_radius = float(proj.geometry.root_cutout_norm)
    ne, npsi = 12, 24

    r = np.linspace(root_radius, 1.0, ne)
    psi = np.linspace(0.0, 2 * np.pi, npsi, endpoint=False)
    ang = np.linspace(0, 2 * np.pi, 400)

    fig, ax = plt.subplots(figsize=(6.4, 6.4))
    for ri in r:                                   # rings
        ax.plot(ri * np.cos(ang), ri * np.sin(ang), "-", color=BLUE, lw=0.5, alpha=0.55)
    for pj in psi:                                 # spokes
        ax.plot([root_radius * np.cos(pj), np.cos(pj)], [root_radius * np.sin(pj), np.sin(pj)],
                "-", color=BLUE, lw=0.5, alpha=0.55)
    RR, PP = np.meshgrid(r, psi, indexing="ij")
    ax.plot((RR * np.cos(PP)).ravel(), (RR * np.sin(PP)).ravel(),
            linestyle="none", marker="o", markersize=2.6, color="#1f5c86")
    ax.plot(np.cos(ang), np.sin(ang), "-", color="black", lw=1.6)
    ax.plot(root_radius * np.cos(ang), root_radius * np.sin(ang), "-", color="black", lw=1.6)

    ax.set_aspect("equal")
    ax.set_xticks([]); ax.set_yticks([])
    ax.grid(False)
    ax.set_title(f"Actual radial-azimuthal mesh ($N_e$={ne}, $N_\\psi$={npsi})\n"
                 "(reduced example; production runs use larger $N_e$, $N_\\psi$)")
    _save_figure(fig, "11-disk-discretization-radial-azimuthal-mesh-1.png")


# =============================================================================
# 7.1.1 -- Inflow field of the four models (fig. 17-1)
# =============================================================================

MU_INFLOW = 0.28

def fig_inflow_models():
    models = [
        ("glauert_local", "Uniform (Glauert). No harmonic"),
        ("coleman_local", "Coleman. Longitudinal harmonic ($K_y=0$)"),
        ("drees_local", "Drees. Longitudinal + lateral harmonic"),
        ("pitt_peters_steady", "Pitt-Peters (steady, 3 states)"),
    ]
    # A SINGLE COLOR SCALE for the four panels. The old figure gave each
    # panel its own colorbar, and that made the panels not comparable:
    # Coleman's dark red (0.25) and Drees's (0.18) looked the same despite
    # differing by ~1/3 -- exactly the comparison the figure exists to
    # allow ("same flight condition, four models"). With a shared scale,
    # the difference BETWEEN models becomes legible, which is the caption's
    # point.
    panels = []
    for model, title in models:
        proj = _project(NE_DISK, NPSI_DISK, inflow_field_model=model)
        res = _run_case(proj, mu_x=MU_INFLOW, name=model)
        panels.append((title, res))

    all_values = np.concatenate([np.asarray(r.maps["lambda_i"]).ravel() for _t, r in panels])
    norm = _norm_centered_on_zero(all_values)

    fig, axes = plt.subplots(1, 4, figsize=(16.5, 4.6))
    cf = None
    for ax, (title, res) in zip(axes, panels):
        cf = _draw_disk_map(ax, res.maps, "lambda_i", cmap="RdBu_r", levels=22, norm=norm,
                            with_orientation=True)
        ax.set_xlim(-1.22, 1.22)
        ax.set_ylim(-1.18, 1.18)
        ax.set_title(title, fontsize=9)
        ax.set_xticks([]); ax.set_yticks([])
    cb = fig.colorbar(cf, ax=axes.tolist(), fraction=0.020, pad=0.02)
    cb.set_label(r"$\lambda_i$  (shared scale)", fontsize=9)
    fig.suptitle(r"Induced inflow field $\lambda_i(r,\psi)$, "
                 rf"$\mu_x={MU_INFLOW}$, same flight condition, four models",
                 fontsize=11)
    _save_figure(fig, "17-inflow-models-and-zbemt-solvers-1.png", tight=False)


# =============================================================================
# 7.1.2 -- Actual convergence of the four solvers (fig. 17-2)
# =============================================================================

MU_SOLVERS = 0.25

def fig_solver_convergence():
    """Residual per iteration of the 4 solvers under the SAME condition.

    `collect_history=True` is what makes the engine keep
    `residual_history`; without it the figure would come out empty."""
    proj = _project(NE_DISK, NPSI_DISK, collect_history=True)
    results = api.benchmark_solvers(
        proj, FlightCondition(name="bench", mu_x=MU_SOLVERS, Vz=0.0,
                              collective_deg=8.0, rpm=1200.0),
        solvers=("fixed_point", "aitken", "newton", "bisection"))

    colors = {"fixed_point": RED, "aitken": GREEN, "newton": BLUE, "bisection": "#e08a1e"}
    # TWO panels. The MAXIMUM residual alone is misleading: it is the worst
    # element on the whole disk, and a few nodes at the reverse-flow
    # boundary hold it on a plateau (~1e-2) even once 99.9% of the mesh has
    # already converged -- read on the plot as "Newton stalled", which is
    # the opposite of what happens. The converged fraction next to it shows
    # what actually matters: Newton reaches ~100% in a few iterations, and
    # it is `early_exit_fraction` (not a failure) that ends the sweep
    # there.
    fig, (ax_r, ax_f) = plt.subplots(1, 2, figsize=(13.0, 5.0))
    for res in results:
        name = str(res.maps.get("solver", "?"))
        color = colors.get(name)
        hist = np.asarray(res.maps.get("residual_history", []), dtype=float)
        frac = np.asarray(res.maps.get("frac_converged_history", []), dtype=float)
        if hist.size:
            ax_r.semilogy(np.arange(1, hist.size + 1), hist, "-o", markersize=2.4,
                          lw=1.2, color=color, label=name)
        if frac.size:
            ax_f.plot(np.arange(1, frac.size + 1), 100.0 * frac, "-o", markersize=2.4,
                      lw=1.2, color=color, label=name)
    ax_r.set_xlabel("iteration")
    ax_r.set_ylabel(r"maximum residual $\max|\lambda_i^{(k+1)}-\lambda_i^{(k)}|$")
    ax_r.set_title("Worst element on the disk")
    ax_r.grid(True, which="both", alpha=0.3)
    ax_r.legend()

    ax_f.set_xlabel("iteration")
    ax_f.set_ylabel("converged elements [%]")
    ax_f.set_title("Fraction of the mesh already converged")
    ax_f.set_xscale("log")
    ax_f.legend()
    fig.suptitle(rf"Actual convergence of the 4 solvers, same rotor, $\mu_x={MU_SOLVERS}$",
                 fontsize=11)
    _save_figure(fig, "17-inflow-models-and-zbemt-solvers-2.png")


# =============================================================================
# 2.9.3 -- Universal induced velocity curve (fig. 18-1)
# =============================================================================

def fig_universal_curve():
    """Purely analytical: it is the momentum theory solution, not a case.

    The two VALID branches come from the momentum equations; the range
    -2 < Vc/vh < 0 (vortex ring) has no simple momentum solution and is
    entered as an empirical fit -- which is exactly what the figure
    shows."""
    fig, ax = plt.subplots(figsize=(7.2, 5.2))

    vc_climb = np.linspace(0.0, 4.0, 400)                 # climb/hover
    vi_climb = -vc_climb / 2 + np.sqrt((vc_climb / 2) ** 2 + 1)
    ax.plot(vc_climb, vi_climb, "-", color=BLUE, lw=2.2,
            label="Climb / hover (momentum theory)")

    vc_windmill = np.linspace(-4.0, -2.0, 300)             # windmill brake
    vi_windmill = -vc_windmill / 2 - np.sqrt((vc_windmill / 2) ** 2 - 1)
    ax.plot(vc_windmill, vi_windmill, "--", color=BLUE, lw=2.2,
            label="Fast descent: windmill brake (momentum theory)")

    # Vortex ring range: empirical fit anchored at the two extremes
    # (vi/vh = 1 at Vc=0 and the windmill branch's value at Vc/vh=-2).
    vc_ring = np.linspace(-2.0, 0.0, 300)
    x = vc_ring / 2.0
    vi_ring = 1.0 + 1.10 * np.sin(np.pi * (vc_ring + 2.0) / 2.0) ** 1.6 * (1 - 0.18 * (x + 1) ** 2)
    ax.plot(vc_ring, vi_ring, ":", color=RED, lw=2.4,
            label="Vortex ring / turbulent wake\n(empirical fit where simple momentum is invalid)")
    ax.axvspan(-2.0, 0.0, color=RED, alpha=0.06)

    ax.axhline(0, color="0.5", lw=0.8)
    ax.axvline(0, color="0.5", lw=0.8)
    ax.set_xlim(-4, 4)
    ax.set_ylim(-1, 3)
    ax.set_xlabel(r"Normalized climb velocity, $V_c/v_h$   (negative = descent)")
    ax.set_ylabel(r"Normalized induced velocity, $v_i/v_h$")
    ax.set_title("Universal induced velocity curve\n(hover → climb → descent)")
    ax.legend(loc="upper right", fontsize=8)
    _save_figure(fig, "18-momentum-theory-1.png")


# =============================================================================
# 2.8.2 -- Analytical stall models (figs. 19-1, 19-2, 19-3)
# =============================================================================

def _airfoil_definition():
    return deepcopy(api.open_project(str(PROJECT)).airfoil)


def _analitico(defn, stall_model: str):
    return airfoils.AnalyticalAirfoil(
        cl_alpha=defn.cl_alpha, alpha0_deg=defn.alpha0_deg, cd0=defn.cd0, k=defn.k,
        alpha_stall_pos_deg=defn.alpha_stall_pos_deg,
        alpha_stall_neg_deg=defn.alpha_stall_neg_deg,
        stall_model=stall_model)


def fig_stall_models():
    defn = _airfoil_definition()
    alpha_deg = np.linspace(-40, 40, 601)
    alpha = np.deg2rad(alpha_deg)

    models = [
        ("linear", "linear (no stall)", GRAY, "--"),
        ("clip", "clip (abrupt saturation)", BLUE, "-"),
        ("enhanced", "enhanced (smooth decay)", RED, "-"),
    ]
    fig, (ax_l, ax_d) = plt.subplots(1, 2, figsize=(12.6, 4.8))
    for model, label, color, linestyle in models:
        cl, cd = _analitico(defn, model).cl_cd(alpha)
        ax_l.plot(alpha_deg, cl, linestyle, color=color, lw=1.8, label=label)
        ax_d.plot(alpha_deg, cd, linestyle, color=color, lw=1.8, label=label.split(" (")[0])
    for ax in (ax_l, ax_d):
        for a in (defn.alpha_stall_pos_deg, defn.alpha_stall_neg_deg):
            ax.axvline(a, color="0.5", ls=":", lw=0.9)
        ax.set_xlabel(r"$\alpha$ [deg]")
        ax.legend()
    ax_l.set_ylabel(r"$C_l$")
    ax_d.set_ylabel(r"$C_d$")
    ax_l.set_title(r"AnalyticalAirfoil: linear vs. clipped vs. enhanced, $C_l$")
    ax_d.set_title(r"$C_d$")
    _save_figure(fig, "19-blade-element-theory-1.png")


def fig_table_airfoil():
    """TableAirfoil: "measured" points with noise + linear interpolation.

    Fixed seed: the figure goes into the repository, and a different noise
    on every regeneration would produce a binary diff on every run without
    anything actually having changed."""
    rng = np.random.default_rng(20240517)
    defn = _airfoil_definition()
    base = _analitico(defn, "enhanced")

    alpha_deg = np.linspace(-40, 40, 601)
    cl_ref, cd_ref = base.cl_cd(np.deg2rad(alpha_deg))

    # "Test campaign" sampling: dense near stall, sparse away from it.
    alpha_tab = np.unique(np.concatenate([
        np.arange(-20.0, -8.0, 5.0),
        np.arange(-8.0, 20.1, 2.0),
        np.arange(20.0, 30.1, 5.0),
    ]))
    cl_tab, cd_tab = base.cl_cd(np.deg2rad(alpha_tab))
    cl_tab = cl_tab + rng.normal(0.0, 0.012, cl_tab.shape)
    cd_tab = np.maximum(cd_tab + rng.normal(0.0, 0.0015, cd_tab.shape), 0.0)

    table = airfoils.TableAirfoil(alpha_tab, cl_tab, cd_tab)
    cl_int, cd_int = table.cl_cd(np.deg2rad(alpha_deg))

    fig, (ax_l, ax_d) = plt.subplots(1, 2, figsize=(12.6, 4.8))
    for ax, ref, pts, interp, symbol in (
            (ax_l, cl_ref, cl_tab, cl_int, "C_l"),
            (ax_d, cd_ref, cd_tab, cd_int, "C_d")):
        ax.plot(alpha_deg, ref, "-", color="#c98a8a", lw=1.6,
                label="analytical model (enhanced)")
        ax.plot(alpha_tab, pts, "o", color="#1f5c86", markersize=5,
                label="measured points" + (" (input data)" if symbol == "C_l" else ""))
        ax.plot(alpha_deg, interp, "-", color=BLUE, lw=1.6,
                label="TableAirfoil" + (" (linear interpolation)" if symbol == "C_l" else ""))
        ax.set_xlabel(r"$\alpha$ [deg]")
        ax.set_ylabel(rf"${symbol}$")
        ax.legend()
    ax_l.set_title("TableAirfoil: linear interpolation between measured points")
    ax_d.set_title(r"$C_d$")
    _save_figure(fig, "19-blade-element-theory-2.png")


def fig_viterna():
    defn = _airfoil_definition()
    base = _analitico(defn, "enhanced")
    extended = airfoils.ViternaExtendedAirfoil(
        base,
        alpha_stall_pos_deg=defn.alpha_stall_pos_deg,
        alpha_stall_neg_deg=defn.alpha_stall_neg_deg,
        blend_width_deg=defn.viterna_blend_width_deg)

    alpha_deg = np.linspace(-180, 180, 1441)
    alpha = np.deg2rad(alpha_deg)
    cl_v, cd_v = extended.cl_cd(alpha)
    # "Naive" extrapolation: the base model evaluated outside the range it
    # was built for -- exactly what the figure exists to discourage.
    cl_n, cd_n = base.cl_cd(alpha)

    fig, (ax_l, ax_d) = plt.subplots(1, 2, figsize=(13.4, 4.8))
    for ax, naive, vit, symbol in ((ax_l, cl_n, cl_v, "C_l"), (ax_d, cd_n, cd_v, "C_d")):
        ax.plot(alpha_deg, naive, "--", color=GRAY, lw=1.5,
                label="enhanced, naively extrapolated")
        ax.plot(alpha_deg, vit, "-", color=RED, lw=1.8,
                label="Viterna-Corrigan" + (" (-180° to 180°)" if symbol == "C_l" else ""))
        ax.axvspan(defn.alpha_stall_neg_deg, defn.alpha_stall_pos_deg,
                   color=BLUE, alpha=0.10,
                   label="blended region (base model)" if symbol == "C_l" else None)
        ax.set_xlabel(r"$\alpha$ [deg]")
        ax.set_ylabel(rf"${symbol}$")
        ax.legend(fontsize=8)
    ax_l.set_title(r"Viterna-Corrigan extension, $C_l$ all around")
    ax_d.set_title(r"$C_d$. Note the physical peak near $\pm90°$ (flat plate)")
    _save_figure(fig, "19-blade-element-theory-3.png")


# =============================================================================
# 2.8.4 -- Fn/Ft load over the disk (fig. 19-4)
# =============================================================================

MU_LOADS = 0.30

def fig_disk_loads():
    proj = _project(NE_DISK, NPSI_DISK)
    res = _run_case(proj, mu_x=MU_LOADS, name="loads")

    fig, axes = plt.subplots(1, 2, figsize=(12.6, 5.4))
    for ax, field, cmap, title in (
            (axes[0], "Fn", "viridis", r"$F_n$ (N/m, thrust)"),
            (axes[1], "Ft", "magma", r"$F_t$ (N/m, torque)")):
        # `Ft` changes sign (negative inside the reverse-flow region,
        # where the blade pushes instead of dragging): a diverging
        # colormap centered on zero, otherwise the sign -- which is the
        # caption's point -- disappears.
        norm = _norm_centered_on_zero(np.asarray(res.maps[field])) if field == "Ft" else None
        cf = _draw_disk_map(ax, res.maps, field,
                            cmap=("RdBu_r" if norm is not None else cmap),
                            levels=28, norm=norm, with_orientation=True)
        ax.set_title(title)
        ax.set_xlabel(r"$x/R$")
        ax.set_ylabel(r"$y/R$")
        fig.colorbar(cf, ax=ax, fraction=0.046, pad=0.10)
    fig.suptitle(rf"Aerodynamic loading over the disk, $\mu_x={MU_LOADS}$ "
                 r"(advancing side $\psi=90°$ to the right)", fontsize=11)
    _save_figure(fig, "19-blade-element-theory-4.png")


# =============================================================================
# 8.1 -- Prandtl tip loss factor (fig. 21-1)
# =============================================================================

def fig_prandtl():
    """Analytical: it is the formula the engine applies, swept over Nb and phi.

    Without the 1/x factor that Leishman/Johnson carry -- the same
    omission as the engine (see `help_blocks.tip_root_loss`), so the
    figure describes what zBEMT computes, not what the literature
    writes."""
    r = np.linspace(0.60, 1.0, 400)
    cases = [
        (2, 6.0, BLUE, "-"),
        (4, 6.0, "#e08a1e", "--"),
        (2, 12.0, GREEN, ":"),
    ]
    fig, ax = plt.subplots(figsize=(7.0, 4.6))
    for nb, phi_deg, color, linestyle in cases:
        f = (nb / 2.0) * (1.0 - r) / abs(np.sin(np.deg2rad(phi_deg)))
        F = (2.0 / np.pi) * np.arccos(np.clip(np.exp(-f), 0.0, 1.0))
        ax.plot(r, F, linestyle, color=color, lw=2.0,
                label=rf"$N_b$={nb}, $\phi$={phi_deg:.0f}°")
    ax.set_xlabel(r"$r/R$")
    ax.set_ylabel(r"Tip loss factor $F_{tip}$")
    ax.set_title("Prandtl factor: tip loss from finite blade count")
    ax.legend(loc="lower left")
    _save_figure(fig, "21-prandtl-tip-and-root-loss-1.png")


# =============================================================================
# 8.2 -- Reverse flow (figs. 22-1, 22-2)
# =============================================================================

MU_UT = 0.35

def fig_ut_map():
    """Analytical: U_T/ΩR = r + μ·sin ψ, and the U_T=0 circle that follows from it."""
    r = np.linspace(0.0, 1.0, 260)
    psi = np.linspace(0.0, 2 * np.pi, 361)
    RR, PP = np.meshgrid(r, psi, indexing="ij")
    UT = RR + MU_UT * np.sin(PP)
    # Same convention as `_draw_disk_map` (the engine's): psi=90° to the RIGHT.
    X, Y = RR * np.sin(PP), -RR * np.cos(PP)

    fig, ax = plt.subplots(figsize=(7.6, 5.4))
    cf = ax.contourf(X, Y, UT, levels=22, cmap="RdBu_r",
                     norm=_norm_centered_on_zero(UT))
    ax.contour(X, Y, UT, levels=[0.0], colors="black", linewidths=1.8)
    ang = np.linspace(0, 2 * np.pi, 400)
    ax.plot(np.cos(ang), np.sin(ang), "-", color="black", lw=1.4)
    ax.plot([0], [0], marker="o", color="white", markersize=7, zorder=5)

    # The reverse-flow region (a circle of diameter mu tangent to the hub)
    # falls where sin psi < 0, that is, on the RETREATING side -- to the
    # left in this convention.
    ax.annotate("reverse flow region\n($U_T<0$)", xy=(-0.20, 0.10), xytext=(-0.52, 0.42),
                ha="center", fontsize=9,
                arrowprops=dict(arrowstyle="->", lw=1.0, color="black"))
    ax.text(1.03, 0, "advancing blade\n($\\psi=90°$)", ha="left", va="center", fontsize=9)
    ax.text(-1.03, 0, "retreating blade\n($\\psi=270°$)", ha="right", va="center", fontsize=9)

    cb = fig.colorbar(cf, ax=ax, fraction=0.040, pad=0.02, shrink=0.86)
    cb.set_label(r"$U_T/\Omega R$")
    ax.set_aspect("equal")
    ax.set_xlim(-1.62, 1.62); ax.set_ylim(-1.12, 1.12)
    ax.set_xticks([]); ax.set_yticks([])
    ax.grid(False)
    # No frame: the advancing/retreating blade labels live OUTSIDE the
    # disk, and the axis box around them turns into an empty rectangle.
    ax.set_frame_on(False)
    ax.set_title(rf"$U_T/\Omega R = r + \mu_x\sin\psi$   ($\mu_x={MU_UT}$)")
    _save_figure(fig, "22-reverse-flow-five-models-1.png")


MU_REVERSE, R_REVERSE = 0.55, 0.30

def fig_reverse_flow_models():
    """The 5 models on the SAME element and SAME condition.

    One full case per model (instead of calling `element_state` by hand):
    it is the real engine deciding, and the only difference between the
    curves becomes the `reverse_flow_model`."""
    models = ["simple_flip", "flat_plate", "alpha_blending",
               "thin_plate_blend", "viterna_full_range"]
    colors = [RED, "#e08a1e", BLUE, GREEN, "#6a4c93"]

    fig, axes = plt.subplots(1, 3, figsize=(16.5, 4.8))
    shading = None
    for model, color in zip(models, colors):
        proj = _project(NE_DISK, NPSI_DISK, reverse_flow_model=model)
        res = _run_case(proj, mu_x=MU_REVERSE, name=model)
        i = _radial_index(res.maps, R_REVERSE)
        psi_deg = np.rad2deg(np.asarray(res.maps["psi_nodes"]))
        for ax, field, escala in ((axes[0], "Cl", 1.0), (axes[1], "Cd", 1.0),
                                   (axes[2], "alpha_eff", np.rad2deg(1.0))):
            ax.plot(psi_deg, np.asarray(res.maps[field])[i, :] * escala,
                    "-", color=color, lw=1.5, label=model)
        if shading is None:
            ut = np.asarray(res.maps["Ut"])[i, :]
            reversed_mask = ut < 0
            if reversed_mask.any():
                shading = (psi_deg[reversed_mask].min(), psi_deg[reversed_mask].max())

    for ax, label, title in ((axes[0], r"$C_l$", r"$C_l(\psi)$"),
                                (axes[1], r"$C_d$", r"$C_d(\psi)$"),
                                (axes[2], r"$\alpha_{eff}$ [deg]", r"$\alpha_{eff}(\psi)$")):
        if shading:
            ax.axvspan(*shading, color="0.85", zorder=0)
        ax.set_xlabel(r"Azimuth $\psi$ [deg]")
        ax.set_ylabel(label)
        ax.set_title(title)
    axes[0].set_title(rf"$C_l(\psi)$, $r/R={R_REVERSE}$, $\mu_x={MU_REVERSE}$")
    axes[0].legend(fontsize=8)
    fig.suptitle("Comparison of the 5 reverse-flow models, same element, same flight condition\n"
                 r"(shaded region: $U_T<0$, reverse flow)", fontsize=11)
    _save_figure(fig, "22-reverse-flow-five-models-2.png")


# =============================================================================
# 8.3 -- Local physical corrections (figs. 23-1, 23-2, 23-3)
# =============================================================================

MU_SNEL, COLLECTIVE_SNEL = 0.05, 24.0

def fig_snel():
    """Himmelskamp/Snel: Cl averaged over ψ along the span, on/off.

    HIGH collective (24°) on purpose: the Snel term is proportional to the
    lift DEFICIT the static polar has already lost to separation, so it is
    identically zero while the flow is attached. At starter_rotor's cruise
    collective (8°) the root does not stall and the figure would come out
    with ΔCl = 0 along the whole span -- correct, and showing nothing. The
    Himmelskamp effect IS the delay of root stall; seeing it requires a
    stalled root."""
    without = _run_case(_project(NE_DISK, NPSI_DISK, use_rotational_augmentation=False),
                mu_x=MU_SNEL, collective_deg=COLLECTIVE_SNEL, name="no_snel")
    with_correction = _run_case(_project(NE_DISK, NPSI_DISK, use_rotational_augmentation=True),
                mu_x=MU_SNEL, collective_deg=COLLECTIVE_SNEL, name="snel")

    r = np.asarray(without.maps["r_norm_nodes"])
    cl_without = np.asarray(without.maps["Cl"]).mean(axis=1)
    cl_with = np.asarray(with_correction.maps["Cl"]).mean(axis=1)

    fig, (ax_a, ax_b) = plt.subplots(1, 2, figsize=(12.6, 4.6))
    ax_a.plot(r, cl_without, "-o", color=BLUE, markersize=3.4, lw=1.4,
              label=r"without Snel ($C_{l,2D}$)")
    ax_a.plot(r, cl_with, "-s", color=RED, markersize=3.4, lw=1.4,
              label=r"with Snel ($C_{l,3D}$)")
    ax_a.set_xlabel(r"$r/R$")
    ax_a.set_ylabel(r"$C_l$ (mean over $\psi$)")
    ax_a.set_title(rf"Himmelskamp/Snel effect at $\mu_x={MU_SNEL}$, "
                   rf"$\theta_0={COLLECTIVE_SNEL:.0f}°$ (near hover, stalled root)")
    ax_a.legend()

    ax_b.plot(r, cl_with - cl_without, "-^", color=GREEN, markersize=3.4, lw=1.4)
    ax_b.axhline(0.0, color="black", lw=0.9)
    ax_b.set_xlabel(r"$r/R$")
    ax_b.set_ylabel(r"$\Delta C_l = C_{l,3D} - C_{l,2D}$")
    ax_b.set_title("Effect concentrated near the root")
    _save_figure(fig, "23-local-physics-corrections-1.png")


#: Station OUTSIDE the reverse-flow region. At r/R=0.26 (the one from the
#: old figures) the element passes through U_T<0, and there the radial
#: correction re-evaluates Cd at an alpha near ±180°. The difference
#: between on/off turns into a jump of +1.7 coming from the REVERSE-flow
#: model, not the radial flow, and the figure ended up showing the
#: opposite of what the caption claims (an increase, not a reduction).
#: Outside reverse flow the effect shows up clean: purely negative, as the
#: physics of the independence principle predicts.
MU_RADIAL, R_RADIAL = 0.40, 0.45

def fig_radial_flow():
    without = _run_case(_project(NE_DISK, NPSI_DISK, use_radial_flow_correction=False),
                mu_x=MU_RADIAL, name="no_radial")
    with_correction = _run_case(_project(NE_DISK, NPSI_DISK, use_radial_flow_correction=True),
                mu_x=MU_RADIAL, name="radial")

    i = _radial_index(without.maps, R_RADIAL)
    r_actual = float(np.asarray(without.maps["r_norm_nodes"])[i])
    psi_deg = np.rad2deg(np.asarray(without.maps["psi_nodes"]))
    cd_without = np.asarray(without.maps["Cd"])[i, :]
    cd_with = np.asarray(with_correction.maps["Cd"])[i, :]

    fig, (ax_a, ax_b) = plt.subplots(1, 2, figsize=(12.6, 4.6))
    ax_a.plot(psi_deg, cd_without, "-o", color=BLUE, markersize=3.0, lw=1.4,
              label="without radial correction")
    ax_a.plot(psi_deg, cd_with, "-s", color=RED, markersize=3.0, lw=1.4,
              label="with radial correction")
    ax_a.set_ylabel(r"$C_d$")
    ax_a.set_title(rf"$C_d(\psi)$ at $r/R\approx{r_actual:.2f}$, $\mu_x={MU_RADIAL}$")
    ax_a.legend()

    ax_b.plot(psi_deg, cd_with - cd_without, "-^", color=GREEN, markersize=3.0, lw=1.4)
    ax_b.axhline(0.0, color="black", lw=0.9)
    ax_b.set_ylabel(r"$\Delta C_d$")
    ax_b.set_title(r"Reduction vanishes at $\psi=90°/270°$ ($U_R=0$)")
    # Marks at 90/270: with U_R = V_x·cos psi, that is where the flow is
    # entirely TANGENTIAL, U_R=0 and the two curves coincide exactly -- the
    # notch at 270° in the ΔC_d curve. The reduction itself is larger on
    # the retreating side, where alpha_eff (and therefore C_d itself) is
    # large and there is more to reduce; not at 90°/270°, as claimed by
    # this figure's old caption, `help_blocks.rotational_augmentation`, and
    # the comment on `bemt.py`'s UR line -- all three say |U_R| is maximum
    # at 90°/270°, which contradicts the formula's own cos(psi) (maximum at
    # 0°/180°, where the blade points along the flow).
    for ax in (ax_a, ax_b):
        for p in (90, 270):
            ax.axvline(p, color="0.5", ls="--", lw=0.9)
        ax.set_xlabel(r"$\psi$ [deg]")
    _save_figure(fig, "23-local-physics-corrections-2.png")


def fig_prandtl_glauert():
    """Analytical: the pure 1/sqrt(1-M^2) factor.

    The caption in the HTML explicitly says the tail on the right is only
    for reference (the engine saturates at M=0.9); that's why the curve
    goes beyond where the engine applies it, with a mark for the usual
    incompressible regime."""
    M = np.linspace(0.0, 0.85, 400)
    fig, ax = plt.subplots(figsize=(7.0, 4.6))
    ax.plot(M, 1.0 / np.sqrt(1.0 - M ** 2), "-", color=RED, lw=2.0)
    ax.axvline(0.3, color="0.5", ls=":", lw=1.0)
    ax.text(0.305, 1.32, "usual incompressible\nregime ($M<0.3$)",
            fontsize=8.5, color="0.35", va="center")
    ax.set_xlabel(r"Local Mach number, $M = W/a$")
    ax.set_ylabel(r"Correction factor $1/\sqrt{1-M^2}$")
    ax.set_title("Prandtl-Glauert compressibility correction")
    _save_figure(fig, "23-local-physics-corrections-3.png")


# =============================================================================
# 7.2.4 -- Transiente de Pitt-Peters (fig. 24-1)
# =============================================================================

MU_STEP = 0.22
#: Initial state: true HOVER (mu_x=0). Until this version this
#: returned NaN -- `_solve_pitt_peters_steady` started from nu=0, where
#: VT=sqrt(mu_x^2+lambda^2) is zero at hover, and iteration passed through
#: a lambda<0 that makes the L gain matrix singular. Fixed in the engine
#: (momentum theory seed + guard in
#: `PITT_PETERS_DENOMINATOR_MIN`), with regression in
#: `tests/regression/test_physics_toggles.py`.
MU_HOVER = 0.0

def fig_transiente_pitt_peters():
    """Response of (nu0, nus, nuc) to a step in mu_x, with the engine's
    REAL exponential integrator (`_pitt_peters_exp_step`).

    Starts from HOVER equilibrium (nu solved at mu_x=0) and advances to
    the new condition's equilibrium -- the dotted lines are that
    equilibrium, obtained via `_solve_pitt_peters_steady`."""
    proj = _project(NE_DISK, NPSI_DISK, inflow_field_model="pitt_peters_steady")
    cfg = studies._build_config(proj.config, airfoil_def=proj.airfoil)
    rotor = studies._to_rotor(proj.geometry, collective_deg=8.0, rpm=1200.0)
    radial = airfoils.radial_reynolds_mach(rotor, cfg, mu_x=MU_STEP)
    airfoil_profile = airfoils.to_blade_airfoil(proj.airfoil_sections or [proj.airfoil], radial=radial)

    mesh_tuple = bemt._pitt_peters_geometry(rotor, cfg)
    r_nodes, psi_nodes, R_NORM, PSI, R_DIM, CHORD, THETA = mesh_tuple

    nu_hover, *_ = bemt._solve_pitt_peters_steady(
        rotor, airfoil_profile, cfg, MU_HOVER, 0.0,
        r_nodes, psi_nodes, R_NORM, PSI, R_DIM, CHORD, THETA)
    nu_final, *_ = bemt._solve_pitt_peters_steady(
        rotor, airfoil_profile, cfg, MU_STEP, 0.0, r_nodes, psi_nodes, R_NORM, PSI, R_DIM, CHORD, THETA)

    dtau, n_steps = 0.02, 390
    nu = np.array(nu_hover, dtype=float)
    tau, hist = [0.0], [nu.copy()]
    for k in range(n_steps):
        nu, _, _ = bemt._pitt_peters_exp_step(
            nu, dtau, rotor, airfoil_profile, cfg, MU_STEP, 0.0,
            r_nodes, psi_nodes, R_NORM, PSI, R_DIM, CHORD, THETA)
        tau.append((k + 1) * dtau)
        hist.append(nu.copy())
    tau = np.asarray(tau)
    hist = np.asarray(hist)

    labels = [(0, r"$\nu_0$ (uniform)", RED),
               (1, r"$\nu_s$ (lateral)", BLUE),
               (2, r"$\nu_c$ (longitudinal)", GREEN)]
    fig, ax = plt.subplots(figsize=(7.6, 5.2))
    for idx, label, color in labels:
        ax.plot(tau, hist[:, idx], "-", color=color, lw=1.9, label=label)
        ax.axhline(nu_final[idx], color=color, ls=":", lw=1.2)
    ax.axvline(0.0, color="0.5", lw=0.9)
    ax.set_xlabel(r"Dimensionless time $\tau = \Omega t$ [rad]")
    ax.set_ylabel(r"Inflow state $\nu$")
    ax.set_title("Pitt-Peters transient response to a step in advance ratio\n"
                 rf"($\mu_x$: {MU_HOVER} → {MU_STEP}, "
                 "zBEMT's actual exponential integrator)")
    ax.legend(loc="center right")
    _save_figure(fig, "24-non-uniform-inflow-1.png")


# =============================================================================
# 8.4.3 -- Øye dynamic stall hysteresis loop (fig. 25-1)
# =============================================================================

def fig_oye_hysteresis():
    """Hysteresis loop and separation function for three c/R ratios.

    Uses the engine's REAL functions (`_oye_static_separation`, `_oye_cl_sep`):
    what changes among the three curves is only the time constant tau*Omega,
    which is the parameter this figure exists to explain."""
    defn = _airfoil_definition()
    base = _analitico(defn, "enhanced")

    psi = np.linspace(0.0, 2 * np.pi, 721)
    alpha_deg = 9.0 + 9.0 * np.sin(psi)              # crosses into stall once per revolution
    alpha = np.deg2rad(alpha_deg)
    cl_st, _cd_st = base.cl_cd(alpha)
    # `base.alpha0` is ALREADY in radians (the constructor takes degrees and
    # converts); passing through deg2rad again would zero the zero-lift angle
    # and shift the entire loop.
    reg = 1e-3
    f_st, cl_att = bemt._oye_static_separation(
        alpha, cl_st, base.cl_alpha, base.alpha0, reg)
    cl_sep = bemt._oye_cl_sep(cl_st, f_st, cl_att, reg)

    cases = [(0.12, "low $c/R$ (quasi-steady)", GREEN),
             (0.50, "medium $c/R$ (representative)", BLUE),
             (1.25, "high $c/R$ (strongly dynamic)", RED)]

    fig, (ax_l, ax_f) = plt.subplots(1, 2, figsize=(14.0, 5.2))
    ax_l.plot(alpha_deg, cl_st, "--", color="black", lw=1.6, label=r"static $C_l$")
    ax_f.plot(np.rad2deg(psi), f_st, "--", color="black", lw=1.6,
              label=r"$f_{st}$ (quasi-steady)")

    for tau_omega, label, color in cases:
        # df/dpsi = (f_st - f)/(tau*Omega): same ODE as the engine, integrated
        # over psi (tau=Omega*t) to steady state -- 6 revolutions suffice
        # so that the initial transient dies out.
        f = np.full_like(psi, f_st[0])
        dpsi = psi[1] - psi[0]
        for _rev in range(6):
            for i in range(1, psi.size):
                f[i] = f[i - 1] + dpsi * (f_st[i - 1] - f[i - 1]) / tau_omega
            f[0] = f[-1]
        cl_dyn = f * cl_att + (1.0 - f) * cl_sep
        ax_l.plot(alpha_deg, cl_dyn, "-", color=color, lw=1.6,
                  label=rf"{label} ($\tau\Omega$={tau_omega:.2f} rad)")
        ax_f.plot(np.rad2deg(psi), f, "-", color=color, lw=1.6, label=label)

    ax_l.set_xlabel(r"$\alpha_{eff}$ [deg]")
    ax_l.set_ylabel(r"$C_l$")
    ax_l.set_title(r"Øye hysteresis. Effect of the time constant $\tau = Ac/2W$")
    ax_l.legend(fontsize=8, loc="upper left")

    ax_f.set_xlabel(r"Azimuth $\psi$ [deg]")
    ax_f.set_ylabel(r"$f$ (attached fraction)")
    ax_f.set_title(r"Separation function $f(\psi)$: relaxation toward $f_{st}$")
    ax_f.legend(fontsize=8, loc="lower right")
    _save_figure(fig, "25-oye-dynamic-stall-1.png")


# =============================================================================
# 12.2 / 12.3 -- mu_x sweeps (figures 28-1, 29-1)
# =============================================================================

def _sweep(mu_max: float, n: int):
    proj = _project(NE_SWEEP, NPSI_SWEEP)
    mus = np.linspace(0.01, mu_max, n)
    return mus, [_run_case(proj, mu_x=float(m), name=f"mu_{m:.3f}").summary for m in mus]


def fig_sweep_ct_cq_fm():
    mus, summaries = _sweep(0.45, 20)
    ct = [s["CT"] for s in summaries]
    cq = [s["CQ"] for s in summaries]
    fm = [s.get("FM", np.nan) for s in summaries]

    fig, axes = plt.subplots(1, 3, figsize=(14.5, 4.3))
    for ax, y, color, label, title in (
            (axes[0], ct, "#1f77b4", r"$C_T$", r"$C_T(\mu_x)$: fixed pitch, no trim"),
            (axes[1], cq, "#d62728", r"$C_Q$", r"$C_Q(\mu_x)$"),
            (axes[2], fm, "#2ca02c", "Figure of Merit", r"FM($\mu_x$)")):
        ax.plot(mus, y, "-o", color=color, markersize=4, lw=1.4)
        ax.set_xlabel(r"$\mu_x$")
        ax.set_ylabel(label)
        ax.set_title(title)
    _save_figure(fig, "28-results-aggregation-1.png")


def fig_sweep_ct_cp_fm():
    mus, summaries = _sweep(0.35, 24)
    ct = [s["CT"] for s in summaries]
    cp = [s["CP"] for s in summaries]
    fm = [s.get("FM", np.nan) for s in summaries]

    fig, (ax_c, ax_f) = plt.subplots(1, 2, figsize=(12.6, 4.6))
    ax_c.plot(mus, ct, "-o", color=RED, markersize=3.6, lw=1.5, label=r"$C_T$")
    ax_c.plot(mus, cp, "-o", color=BLUE, markersize=3.6, lw=1.5, label=r"$C_P$")
    ax_c.set_xlabel(r"$\mu_x$")
    ax_c.set_ylabel("coefficient")
    ax_c.set_title(r"Actual sweep in $\mu_x$ (fixed pitch, no trim)")
    ax_c.legend()

    ax_f.plot(mus, fm, "-o", color=GREEN, markersize=3.6, lw=1.5)
    ax_f.set_xlabel(r"$\mu_x$")
    ax_f.set_ylabel(r"$FM$")
    ax_f.set_title("Figure of merit along the sweep")
    _save_figure(fig, "29-flight-condition-sweeps-1.png")


# =============================================================================

FIGURES = [
    ("11-1 mesh", fig_mesh),
    ("17-1 inflow models", fig_inflow_models),
    ("17-2 solver convergence", fig_solver_convergence),
    ("18-1 universal inflow curve", fig_universal_curve),
    ("19-1 stall models", fig_stall_models),
    ("19-2 table airfoil", fig_table_airfoil),
    ("19-3 viterna", fig_viterna),
    ("19-4 disk loads", fig_disk_loads),
    ("21-1 prandtl loss", fig_prandtl),
    ("22-1 Ut map", fig_ut_map),
    ("22-2 reverse flow models", fig_reverse_flow_models),
    ("23-1 snel", fig_snel),
    ("23-2 radial flow", fig_radial_flow),
    ("23-3 prandtl-glauert", fig_prandtl_glauert),
    ("24-1 pitt-peters transient", fig_transiente_pitt_peters),
    ("25-1 oye hysteresis", fig_oye_hysteresis),
    ("28-1 sweep CT/CQ/FM", fig_sweep_ct_cq_fm),
    ("29-1 sweep CT/CP + FM", fig_sweep_ct_cp_fm),
]


def main():
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    for label, func in FIGURES:
        print(f"[{label}]")
        func()
    print(f"\n{len(FIGURES)} figures written to {OUTPUT_DIR}")


if __name__ == "__main__":
    main()
