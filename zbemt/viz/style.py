"""
style.py
========

Single source of ``matplotlib.rcParams`` (font, grid, multi-series
palette) -- critical now that there are several live canvases (Airfoil,
Geometry, Results) that need to be visually consistent with each other.
Imported by ``plots.py`` (applied once on import, covering both the GUI
and CLI/report export) and optionally reapplied by
``zbemt.gui.app.main()``.
"""

from __future__ import annotations

import matplotlib as mpl

_PALETTE = [
    "#1f77b4", "#ff7f0e", "#2ca02c", "#d62728", "#9467bd",
    "#8c564b", "#e377c2", "#7f7f7f", "#bcbd22", "#17becf",
]


def apply():
    mpl.rcParams.update({
        "font.size": 9,
        "font.family": "sans-serif",
        "axes.titlesize": 10,
        "axes.labelsize": 9,
        "axes.grid": True,
        "grid.alpha": 0.3,
        "grid.linestyle": "--",
        "legend.fontsize": 8,
        "figure.autolayout": False,
        "axes.prop_cycle": mpl.cycler(color=_PALETTE),
        "savefig.dpi": 150,
    })


apply()
