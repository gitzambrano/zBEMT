"""plots_interactive.py
=====================

Plotly charts (native browser zoom, pan, and color) for the GUI, via
`gui/common.py::PlotlyCanvasHost`. Complements (does not replace)
`viz/plots.py`: the matplotlib functions there remain the path for the
CLI, the HTML report, and any exported PNG (`fname=`). These exist only
for the interactive window, when the `interactive` extra is installed
(`gui/common.py::HAS_INTERACTIVE_PLOTS`).

Convention: every function returns a ready `plotly.graph_objects.Figure`
(no `ax`/`fname`, `PlotlyCanvasHost.set_figure(fig)` handles the rest).

Labels here are PLAIN TEXT, not matplotlib mathtext (`$C_T$` and so on):
Plotly does not interpret that syntax at all in the browser. Without
MathJax loaded (which we deliberately do not load, to stay fully
offline) it renders the raw `$...$` string literally. Field codes
(`CT`, `CQ`, ...) read fine on their own and match what the field
already looks like in the summary table.

Initial coverage (the most used view in the Results tab): only
`coefficients_vs_axis`. The other three views (disk map, azimuth and
span, planform and profile preview) still use matplotlib for now."""
from __future__ import annotations

import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots

from .. import nomenclature
from . import plots
from .plots import (_AXIS_TO_SUMMARY_KEY, _grouping_key, _group_order,
                     grouping_map, DEFAULT_GROUP_TOLERANCE)

def _xy_label(key: str, is_propeller: bool = False) -> str:
    """Plain-text axis label for any `Results.summary` key.

    There used to be a whole second copy of `plots._SUMMARY_KEY_LABELS` here,
    hand-transcribed into Unicode and, having no mode argument, it labeled
    a propeller's CROSS-flow "mu_x" on every custom X-Y plot. Both problems go
    away by rendering the one label source into the target this file needs.
    """
    return plots.summary_label_text(key, is_propeller)


#: Plotly gets PLAIN TEXT, not mathtext: MathJax is deliberately not loaded
#: (the report has to open offline), so a r"$\mu_x$" would show literally.
#: `nomenclature.symbol_text` is that same plain-text rendering of the one
#: symbol source, so this file no longer keeps its own copy of the letters --
#: it only picks the render target.
def _sweep_axis_label(axis: str, is_propeller: bool = False) -> tuple:
    """``(axis label, prose title)`` for a sweep panel, in plain text and in
    the mode's own axis letters."""
    titles = plots._AXIS_TITLES.get(axis)
    if titles is None:
        return axis, axis
    symbol = nomenclature.symbol_text(axis, is_propeller)
    unit = nomenclature.unit(axis)
    label = f"{symbol} ({unit})" if unit and unit != "-" else symbol
    return label, f"{titles[1] if is_propeller else titles[0]} ({symbol})"


#: (summary key, y-axis label): plain text, no mathtext (see module
#: docstring). Same 11 panels as `plots._MU_SWEEP_PANELS`, English titles.
_COEFFICIENT_PANELS = [
    ("CT",  "CT",  "Thrust coefficient"),
    ("CQ",  "CQ (CP)", "Torque/power coefficient"),
    ("FM",  "FM",  "Figure of merit (hover def.)"),
    ("CY",  "CY",  "Y-force coeff. (+ right)"),
    ("CMx", "CMx", "Pitch moment coeff."),
    ("CMy", "CMy", "Roll moment coeff."),
    ("CH",  "CH",  "H-force coeff. (+ aft)"),
    ("CHp", "CHp", "H-force, profile part"),
    ("CHi", "CHi", "H-force, induced part"),
    ("CPp", "CPp", "Profile power"),
    ("CPi", "CPi", "Induced power"),
]


def coefficients_vs_axis(results_list, axis: str = "mu_x", ncols: int = 4, series_labels=None,
                          group_tol: float = DEFAULT_GROUP_TOLERANCE):
    """Panel with the 11 global coefficients (CT, CQ, FM, ...) vs.
    ``axis``, the interactive equivalent of
    ``plots.plot_coefficients_vs_axis``.

    Supports two modes:
    - Combine mode (series_labels=None, default): auto-detects other factorial
      axes that vary and draws one curve per unique combination, exactly like
      the matplotlib version. This is correct for factorial batches with 2+ axes.
    - Overlay mode (series_labels provided): draws one curve per label (used
      when GUI explicitly selects "overlay by series"). Note: overlay by
      _selection_ differs from auto-detected grouping by _secondary axes_.
    """
    key = _AXIS_TO_SUMMARY_KEY.get(axis, axis)
    axis_label, axis_title = _sweep_axis_label(
        axis, plots.results_propeller_mode(results_list))
    x_all = np.array([r.summary.get(key, np.nan) for r in results_list], dtype=float)

    # Group the results by label (if provided) or by secondary factorial
    # variables that also varied (auto-detection).
    groups = {}
    if series_labels is not None:
        # Overlay mode: the user provided explicit labels (for example an A/B selection)
        for i, lbl in enumerate(series_labels):
            groups.setdefault(lbl, []).append(i)
    else:
        # Combine mode: detect other factorial variables that varied and
        # group by them (same behavior as matplotlib).
        other_keys = [(_AXIS_TO_SUMMARY_KEY[ax], ax) for ax in _AXIS_TO_SUMMARY_KEY.keys() if ax != axis]
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
                        ax_name, plots.results_propeller_mode(results_list))
                    label_parts.append(f"{symbol}={val:g}" if isinstance(val, (int, float)) else f"{symbol}={val}")
                    order_keys.append(_group_order(val))

            lbl = ", ".join(label_parts) if label_parts else None
            order_by_label.setdefault(lbl, tuple(order_keys))
            groups.setdefault(lbl, []).append(i)
        groups = {k: groups[k] for k in sorted(groups, key=lambda k: order_by_label.get(k, ()))}

    overlay = len(groups) > 1 or (series_labels is not None and len(set(series_labels)) > 1)

    n = len(_COEFFICIENT_PANELS)
    nrows = int(np.ceil(n / ncols))
    titles = [title for _, _, title in _COEFFICIENT_PANELS]
    fig = make_subplots(rows=nrows, cols=ncols, subplot_titles=titles,
                        vertical_spacing=0.6 / nrows, horizontal_spacing=0.06)

    for i, (field_key, ylabel, _title) in enumerate(_COEFFICIENT_PANELS):
        row, col = i // ncols + 1, i % ncols + 1
        for lbl, idxs in groups.items():
            xs = x_all[idxs]
            order = np.argsort(xs)
            xs_sorted = xs[order]
            vals = np.array([results_list[idxs[o]].summary.get(field_key, np.nan) for o in order],
                            dtype=float)
            # Show legend only if there is overlay (multiple series).
            show_legend = (overlay and i == 0)  # Legend only on the first panel
            fig.add_trace(
                go.Scatter(x=xs_sorted, y=vals, mode="lines+markers",
                          name=lbl or "data", legendgroup=lbl or "data",
                          showlegend=show_legend,
                          marker=dict(size=6), line=dict(width=1.6)),
                row=row, col=col)
        fig.update_yaxes(title_text=ylabel, title_standoff=4, row=row, col=col)
        if row == nrows:
            fig.update_xaxes(title_text=axis_label, row=row, col=col)

    fig.update_layout(
        title=f"Rotor performance vs {axis_title}",
        height=280 * nrows, margin=dict(t=90, l=55, r=25, b=45),
        template="plotly_white")
    # Panel titles small enough not to collide with the neighboring
    # panel's y-axis label. Plotly's `subplot_titles` don't wrap on
    # their own, and the default annotation font is too large for a
    # 4-column grid.
    for ann in fig.layout.annotations:
        ann.font.size = 12
    return fig


def xy_plot(results_list, x_key: str, y_key: str, group_by: str | None = None,
             group_tol: float = DEFAULT_GROUP_TOLERANCE):
    """Interactive twin of ``plots.plot_xy``: single-panel free-form X/Y
    plot from any two ``Results.summary`` keys, optionally grouped into one
    curve per distinct value of a third key. Same semantics as the
    matplotlib version: NaN/missing points skipped, curves sorted by X."""
    is_propeller = plots.results_propeller_mode(results_list)

    def _val(r, key):
        v = r.summary.get(key, None)
        try:
            return float(v)
        except (TypeError, ValueError):
            return np.nan

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

    group_symbol = (_xy_label(group_by, is_propeller).split(" [")[0]
                    if group_by else None)
    overlay = len([g for g in groups.values() if g]) > 1

    fig = go.Figure()
    any_point = False
    for gv, items in groups.items():
        xs = np.array([_val(r, x_key) for r in items], dtype=float)
        ys = np.array([_val(r, y_key) for r in items], dtype=float)
        valid = np.isfinite(xs) & np.isfinite(ys)
        if not np.any(valid):
            continue
        xs_v, ys_v = xs[valid], ys[valid]
        order = np.argsort(xs_v)
        name = None
        if gv is not None:
            name = f"{group_symbol}={gv:g}" if isinstance(gv, (int, float)) else f"{group_symbol}={gv}"
        fig.add_trace(go.Scatter(x=xs_v[order], y=ys_v[order], mode="lines+markers",
                                  name=name or "data", showlegend=overlay,
                                  marker=dict(size=6), line=dict(width=1.6)))
        any_point = True

    fig.update_layout(
        title=f"{y_key} vs {x_key}",
        xaxis_title=_xy_label(x_key, is_propeller),
        yaxis_title=_xy_label(y_key, is_propeller),
        template="plotly_white", height=520, margin=dict(t=60, l=60, r=25, b=50))
    if not any_point:
        fig.add_annotation(text="No valid data points (x/y missing or NaN for all results)",
                            showarrow=False, xref="paper", yref="paper", x=0.5, y=0.5,
                            font=dict(size=13, color="gray"))
    return fig
