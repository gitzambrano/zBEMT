from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def patch(path: str, replacements: list[tuple[str, str]]) -> None:
    target = ROOT / path
    text = target.read_text(encoding="utf-8")
    original = text
    for old, new in replacements:
        count = text.count(old)
        if count != 1:
            raise RuntimeError(f"{path}: expected exactly one match, found {count}: {old[:80]!r}")
        text = text.replace(old, new, 1)
    if text != original:
        target.write_text(text, encoding="utf-8")
        print(f"patched {path}")
    else:
        print(f"unchanged {path}")


def patch_plots() -> None:
    helper_old = '''def _finish(ax, fig, fname):
    if fname is not None and fig is not None:
        fig.tight_layout()
        fig.savefig(fname, dpi=_EXPORT_DPI)
    return ax
'''
    helper_new = '''def _finish(ax, fig, fname):
    if fname is not None and fig is not None:
        fig.tight_layout()
        fig.savefig(fname, dpi=_EXPORT_DPI)
    return ax


#: Dense legends are information, not decoration. Once a single-panel
#: figure carries many series, squeezing it to the current viewport makes
#: the legend unreadable even though the data axis itself could shrink.
#: The figure may therefore declare an explicit pixel floor, consumed by
#: `figure_minimum_pixels`/`CanvasHost` exactly like a multi-panel grid.
_DENSE_LEGEND_MAX_ROWS = 10
_DENSE_LEGEND_BASE_WIDTH_PX = 780
_DENSE_LEGEND_COLUMN_WIDTH_PX = 180
_DENSE_LEGEND_MIN_HEIGHT_PX = 520
_DENSE_LEGEND_ROW_HEIGHT_PX = 24


def set_figure_minimum_pixels(figure, width: int = 0, height: int = 0) -> tuple[int, int]:
    """Adds an explicit readability floor to a figure.

    Multi-panel figures already derive one from their axes. This hook is
    for a single plot whose non-data artists need space -- most notably a
    legend with dozens of series. It is monotonic: independent callers can
    only increase the floor, never accidentally remove another need.
    """
    old = getattr(figure, "_zbemt_minimum_pixels", (0, 0))
    floor = (max(int(old[0]), max(0, int(width))),
             max(int(old[1]), max(0, int(height))))
    figure._zbemt_minimum_pixels = floor
    return floor


def adaptive_legend(ax, handles=None, labels=None, *, fontsize: float = 8,
                    title: str | None = None, loc: str = "best"):
    """Draws a legend that stays readable as the number of series grows.

    Small legends keep the familiar in-plot placement. Dense legends move
    to the right, split into enough columns to cap the row count, and give
    the figure an explicit minimum size. In a small Results/Tools viewport
    that minimum is handled by the existing scroll area -- horizontal and
    vertical scroll are preferable to tiny text or clipped entries.
    """
    if handles is None or labels is None:
        handles, labels = ax.get_legend_handles_labels()
    pairs = [(handle, label) for handle, label in zip(handles, labels)
             if label and not str(label).startswith("_")]
    if not pairs:
        return None
    handles = [pair[0] for pair in pairs]
    labels = [pair[1] for pair in pairs]
    n_items = len(labels)
    if n_items <= _DENSE_LEGEND_MAX_ROWS:
        return ax.legend(handles, labels, fontsize=fontsize, title=title, loc=loc)

    ncols = min(4, int(np.ceil(n_items / _DENSE_LEGEND_MAX_ROWS)))
    nrows = int(np.ceil(n_items / ncols))
    width = (_DENSE_LEGEND_BASE_WIDTH_PX
             + ncols * _DENSE_LEGEND_COLUMN_WIDTH_PX)
    height = max(_DENSE_LEGEND_MIN_HEIGHT_PX,
                 150 + nrows * _DENSE_LEGEND_ROW_HEIGHT_PX)
    set_figure_minimum_pixels(ax.figure, width, height)

    # A layout engine that runs at draw time can reserve the right margin
    # again after the Qt canvas is resized. Do not replace an engine the
    # caller already chose (for example MplCanvas' TightLayoutEngine).
    if ax.figure.get_layout_engine() is None:
        ax.figure.set_layout_engine("constrained")
    return ax.legend(handles, labels, fontsize=max(6.5, fontsize - 0.5),
                     title=title, loc="upper left", bbox_to_anchor=(1.02, 1.0),
                     borderaxespad=0.0, ncols=ncols, columnspacing=0.8,
                     handletextpad=0.4)
'''

    floor_old = '''    nrows, ncols = figure_grid_shape(figure)
    if nrows * ncols <= 1:
        return (0, 0)
    width_in, height_in = figure.get_size_inches()
'''
    floor_new = '''    explicit_width, explicit_height = getattr(
        figure, "_zbemt_minimum_pixels", (0, 0))
    explicit_width = max(0, int(explicit_width))
    explicit_height = max(0, int(explicit_height))

    nrows, ncols = figure_grid_shape(figure)
    if nrows * ncols <= 1:
        return (explicit_width, explicit_height)
    width_in, height_in = figure.get_size_inches()
'''

    return_old = '''    scale = max(required_width / width_in, required_height / height_in)
    return (int(np.ceil(width_in * scale)), int(np.ceil(height_in * scale)))
'''
    return_new = '''    scale = max(required_width / width_in, required_height / height_in)
    width = int(np.ceil(width_in * scale))
    height = int(np.ceil(height_in * scale))
    return (max(width, explicit_width), max(height, explicit_height))
'''

    coeff_legend_old = '''    if overlay:
        axes[0].legend(fontsize=7)
'''
    coeff_legend_new = '''    if overlay:
        adaptive_legend(axes[0], fontsize=7)
'''

    xy_legend_old = '''    if overlay:
        ax.legend(fontsize=8)
'''
    xy_legend_new = '''    if overlay:
        adaptive_legend(ax, fontsize=8)
'''

    geom_legend_old = '''    if handles:
        axes_grid[0].legend(handles, [h.get_label() for h in handles],
                            fontsize=7, title="Geometry", loc="best")
'''
    geom_legend_new = '''    if handles:
        adaptive_legend(axes_grid[0], handles, [h.get_label() for h in handles],
                        fontsize=7, title="Geometry")
'''

    geom_layout_old = '''    if owned_fig is not None:
        fig.tight_layout(rect=[0, 0, 1, 0.94], h_pad=2.0, w_pad=1.2)

    result_axes = axes_grid[0] if n_panels == 1 else axes_grid
'''
    geom_layout_new = '''    # Recompute margins whenever an embedded canvas changes size. Dense
    # legends can also sit outside the first axis; constrained layout keeps
    # them inside the figure while the CanvasHost scrolls if necessary.
    if fig.get_layout_engine() is None:
        fig.set_layout_engine("constrained")
    if hasattr(fig.get_layout_engine(), "set"):
        fig.get_layout_engine().set(h_pad=0.14, w_pad=0.18,
                                    hspace=0.10, wspace=0.10)

    result_axes = axes_grid[0] if n_panels == 1 else axes_grid
'''

    delta_legend_old = '''    ax.grid(True, axis="y", alpha=0.3)
    ax.legend(fontsize=7, title="Geometry", loc="best")

    condition_names = {str(getattr(r, "condition_name", "") or "")
'''
    delta_legend_new = '''    ax.grid(True, axis="y", alpha=0.3)
    adaptive_legend(ax, fontsize=7, title="Geometry")

    condition_names = {str(getattr(r, "condition_name", "") or "")
'''

    delta_layout_old = '''    if owned_fig is not None:
        fig.tight_layout(rect=[0, 0, 1, 0.92])
    return _finish(ax, owned_fig, fname)
'''
    delta_layout_new = '''    if fig.get_layout_engine() is None:
        fig.set_layout_engine("constrained")
    return _finish(ax, owned_fig, fname)
'''

    stall_old = '''        ax.plot(np.degrees(psi_closed), f_closed, linewidth=1.3,
                color=color, label=f"rev {k + 1}")
        if k == n_rev - 1:
            # Label only the ends: one legend entry per revolution turns
            # into a wall of text for long marches.
            ax.annotate(f"rev {k + 1}", xy=(360, float(f_closed[-1])),
                        fontsize=7, color=color, xytext=(3, 0),
                        textcoords="offset points", va="center")
    ax.legend(fontsize=7, loc="best")
'''
    stall_new = '''        # The color progression shows the intermediate revolutions. Only
        # the first and last need legend entries: one entry per revolution
        # becomes a wall of text and can cover the entire plot.
        label = f"rev {k + 1}" if k in {0, n_rev - 1} else "_nolegend_"
        ax.plot(np.degrees(psi_closed), f_closed, linewidth=1.3,
                color=color, label=label)
        if k == n_rev - 1:
            ax.annotate(f"rev {k + 1}", xy=(360, float(f_closed[-1])),
                        fontsize=7, color=color, xytext=(3, 0),
                        textcoords="offset points", va="center")
    adaptive_legend(ax, fontsize=7)
'''

    flap_effect_old = '''    fig.tight_layout(rect=[0, 0, 1, 0.92])
    return _finish_fig(fig, fname)
'''
    flap_effect_new = '''    fig.set_layout_engine("constrained")
    fig.get_layout_engine().set(h_pad=0.16, w_pad=0.18, hspace=0.08, wspace=0.08)
    return _finish_fig(fig, fname)
'''

    maneuver_old = '''    fig.suptitle("Maneuver time history", fontsize=12, fontweight="bold")
    fig.tight_layout(rect=[0, 0, 1, 0.97])
    return _finish_fig(fig, fname)
'''
    maneuver_new = '''    fig.suptitle("Maneuver time history", fontsize=12, fontweight="bold")
    fig.set_layout_engine("constrained")
    fig.get_layout_engine().set(h_pad=0.14, w_pad=0.16, hspace=0.08, wspace=0.08)
    return _finish_fig(fig, fname)
'''

    patch("zbemt/viz/plots.py", [
        (helper_old, helper_new),
        (floor_old, floor_new),
        (return_old, return_new),
        (coeff_legend_old, coeff_legend_new),
        (xy_legend_old, xy_legend_new),
        (geom_legend_old, geom_legend_new),
        (geom_layout_old, geom_layout_new),
        (delta_legend_old, delta_legend_new),
        (delta_layout_old, delta_layout_new),
        (stall_old, stall_new),
        (flap_effect_old, flap_effect_new),
        (maneuver_old, maneuver_new),
    ])


def patch_designer() -> None:
    import_old = '''from ..common import (
    in_scroll_area,
    AppState,
    CanvasHost,
    equalize_button_widths,
'''
    import_new = '''from ..common import (
    in_scroll_area,
    AppState,
    CanvasHost,
    apply_figure_minimum_size,
    equalize_button_widths,
'''
    legend_old = '''            if proxies:
                ax.legend(handles=proxies, fontsize=7, loc="upper right")
        except Exception as exc:
'''
    legend_new = '''            if proxies:
                plots.adaptive_legend(ax, handles=proxies,
                                      labels=[p.get_label() for p in proxies],
                                      fontsize=7, title="Variant")
        except Exception as exc:
'''
    draw_old = '''        canvas.draw()

    # =====================================================================
    # Page 2 -- conditions
'''
    draw_new = '''        # A dense variant legend can give this otherwise single-panel
        # preview a readability floor. Keep that floor inside the plot's
        # own scroll area, exactly like the Results grids.
        apply_figure_minimum_size(canvas, canvas.fig)
        canvas.draw()

    # =====================================================================
    # Page 2 -- conditions
'''
    patch("zbemt/gui/tools/geometry_designer.py", [
        (import_old, import_new),
        (legend_old, legend_new),
        (draw_old, draw_new),
    ])


def patch_plot_tests() -> None:
    helper_old = '''def _visible_labels_outside_figure(fig):
    """Returns visible tick labels that would clip in an embedded canvas."""
    width, height = plots.figure_minimum_pixels(fig)
    fig.set_dpi(100)
    fig.set_size_inches(width / 100, height / 100, forward=True)
    canvas = FigureCanvasAgg(fig)
    canvas.draw()
    renderer = canvas.get_renderer()
    outside = []
    for axis in fig.axes:
        if not axis.axison:
            continue
        for label in axis.get_xticklabels() + axis.get_yticklabels():
            if not label.get_visible() or not label.get_text():
                continue
            box = label.get_window_extent(renderer)
            if box.x0 < 0 or box.y0 < 0 or box.x1 > width or box.y1 > height:
                outside.append((axis.get_title(), label.get_text()))
    return outside
'''
    helper_new = '''def _render_at_readable_floor(fig):
    """Draws at the GUI readability floor (or nominal size for a single plot)."""
    width, height = plots.figure_minimum_pixels(fig)
    fig.set_dpi(100)
    if width <= 0:
        width = int(round(fig.get_figwidth() * 100))
    if height <= 0:
        height = int(round(fig.get_figheight() * 100))
    fig.set_size_inches(width / 100, height / 100, forward=True)
    canvas = FigureCanvasAgg(fig)
    canvas.draw()
    return width, height, canvas.get_renderer()


def _visible_labels_outside_figure(fig):
    """Returns visible tick labels that would clip in an embedded canvas."""
    width, height, renderer = _render_at_readable_floor(fig)
    outside = []
    for axis in fig.axes:
        if not axis.axison:
            continue
        for label in axis.get_xticklabels() + axis.get_yticklabels():
            if not label.get_visible() or not label.get_text():
                continue
            box = label.get_window_extent(renderer)
            if box.x0 < 0 or box.y0 < 0 or box.x1 > width or box.y1 > height:
                outside.append((axis.get_title(), label.get_text()))
    return outside


def _visible_non_tick_artists_outside_figure(fig):
    """Checks titles, axis labels, annotations, color-bar text and legends.

    Tick labels have their own helper above. The old clipping regression
    test inspected only ticks, so a title, legend or annotation could leave
    the canvas while the test still reported a perfect figure.
    """
    width, height, renderer = _render_at_readable_floor(fig)
    outside = []

    def check(name, artist):
        if artist is None or not artist.get_visible():
            return
        text = getattr(artist, "get_text", lambda: "")()
        if hasattr(artist, "get_text") and not text:
            return
        box = artist.get_window_extent(renderer)
        if box.width <= 0 or box.height <= 0:
            return
        if box.x0 < -1 or box.y0 < -1 or box.x1 > width + 1 or box.y1 > height + 1:
            outside.append((name, text or type(artist).__name__))

    check("suptitle", getattr(fig, "_suptitle", None))
    for axis in fig.axes:
        if not axis.get_visible():
            continue
        check("title", axis.title)
        check("xlabel", axis.xaxis.label)
        check("ylabel", axis.yaxis.label)
        check("xoffset", axis.xaxis.get_offset_text())
        check("yoffset", axis.yaxis.get_offset_text())
        for text in axis.texts:
            check("annotation", text)
        check("legend", axis.get_legend())
    return outside
'''

    coeff_test_old = '''    def test_labels_stay_inside_the_figure_at_the_readable_floor(self):
        """A tick label outside the figure clips in the Results canvas."""
        fig = plots.plot_coefficients_vs_axis(self._results(), axis="mu_x")
        outside = _visible_labels_outside_figure(fig)
        self.assertEqual(outside, [], f"labels outside figure: {outside}")
'''
    coeff_test_new = '''    def test_labels_stay_inside_the_figure_at_the_readable_floor(self):
        """A tick label outside the figure clips in the Results canvas."""
        fig = plots.plot_coefficients_vs_axis(self._results(), axis="mu_x")
        outside = _visible_labels_outside_figure(fig)
        self.assertEqual(outside, [], f"labels outside figure: {outside}")

    def test_titles_axis_labels_and_legends_stay_inside_the_figure(self):
        fig = plots.plot_coefficients_vs_axis(self._results(), axis="mu_x")
        outside = _visible_non_tick_artists_outside_figure(fig)
        self.assertEqual(outside, [], f"artists outside figure: {outside}")
'''

    insert_anchor = '''class TestPlotXY(unittest.TestCase):
'''
    dense_tests = '''class TestDensePlotLegends(unittest.TestCase):
    def test_custom_xy_many_groups_gets_a_scroll_floor(self):
        results = []
        for group in range(30):
            for mu_x in (0.10, 0.20):
                results.append(_fake_result(
                    mu_x=mu_x, alpha_rotor_deg=0.0,
                    collective_deg=float(group), rpm=600.0,
                    CT=0.01 + 0.0001 * group + 0.001 * mu_x))
        ax = plots.plot_xy(results, x_key="mu_x", y_key="CT",
                           group_by="collective_deg")
        fig = ax.figure
        width, height = plots.figure_minimum_pixels(fig)
        self.assertGreaterEqual(width, 900)
        self.assertGreaterEqual(height, 500)
        outside = _visible_non_tick_artists_outside_figure(fig)
        self.assertEqual(outside, [], f"dense X-Y artists outside: {outside}")

    def test_geometry_comparison_many_variants_gets_a_scroll_floor(self):
        results = []
        for group in range(30):
            result = _fake_result(mu_x=0.1, CT=0.01 + group * 1e-4)
            result.summary["geometry_label"] = f"variant {group + 1}"
            results.append(result)
        ax = plots.plot_geometry_comparison(results, fields=["CT"])
        fig = ax.figure
        width, height = plots.figure_minimum_pixels(fig)
        self.assertGreaterEqual(width, 900)
        self.assertGreaterEqual(height, 500)
        outside = _visible_non_tick_artists_outside_figure(fig)
        self.assertEqual(outside, [], f"dense comparison artists outside: {outside}")

    def test_dynamic_stall_history_labels_only_first_and_last_revolution(self):
        import numpy as np
        n_rev, n_r, n_psi = 30, 3, 24
        base = np.linspace(0.2, 0.9, n_psi)
        history = np.empty((n_rev, n_r, n_psi), dtype=float)
        for k in range(n_rev):
            history[k, :, :] = base + 0.001 * k
        maps = {
            "dynamic_stall_time_march_history": history,
            "r_norm_nodes": np.array([0.25, 0.75, 0.95]),
        }
        fig = plots.plot_dynamic_stall_history(maps, r_norm=0.75)
        legend = fig.axes[0].get_legend()
        labels = [text.get_text() for text in legend.get_texts()]
        self.assertEqual(labels, ["rev 1", "rev 30"])


class TestPlotXY(unittest.TestCase):
'''

    patch("tests/regression/test_plots.py", [
        (helper_old, helper_new),
        (coeff_test_old, coeff_test_new),
        (insert_anchor, dense_tests),
    ])


def patch_scaling_tests() -> None:
    anchor_old = '''    def test_the_host_can_still_be_made_small(self):
        host = CanvasHost()
        grid, _axes = plots._new_figure((12.8, 11.0), 4, 4)
        host.show_figure(grid)
        host.resize(320, 240)
        self.assertEqual(host.width(), 320)
        self.assertEqual(host.height(), 240)
'''
    anchor_new = '''    def test_the_host_can_still_be_made_small(self):
        host = CanvasHost()
        grid, _axes = plots._new_figure((12.8, 11.0), 4, 4)
        host.show_figure(grid)
        host.resize(320, 240)
        self.assertEqual(host.width(), 320)
        self.assertEqual(host.height(), 240)

    def test_a_small_viewport_scrolls_both_directions_instead_of_squeezing(self):
        host = CanvasHost()
        grid, _axes = plots._new_figure((12.8, 11.0), 4, 4)
        host.resize(320, 240)
        host.show()
        host.show_figure(grid)
        self.app.processEvents()
        self.assertGreater(host._scroll.horizontalScrollBar().maximum(), 0)
        self.assertGreater(host._scroll.verticalScrollBar().maximum(), 0)
        host.hide()

    def test_dense_single_panel_can_opt_into_the_same_scroll_policy(self):
        host = CanvasHost()
        fig = Figure(figsize=(6, 5))
        ax = fig.add_subplot(111)
        for i in range(30):
            ax.plot([0, 1], [i, i + 1], label=f"series {i + 1}")
        plots.adaptive_legend(ax)
        width, height = plots.figure_minimum_pixels(fig)
        self.assertGreater(width, 0)
        self.assertGreater(height, 0)
        host.resize(320, 240)
        host.show()
        host.show_figure(fig)
        self.app.processEvents()
        self.assertGreater(host._scroll.horizontalScrollBar().maximum(), 0)
        self.assertGreater(host._scroll.verticalScrollBar().maximum(), 0)
        host.hide()
'''
    patch("tests/regression/test_plot_scaling.py", [(anchor_old, anchor_new)])


def patch_workflow() -> None:
    path = ROOT / ".github/workflows/tests.yml"
    text = path.read_text(encoding="utf-8")
    old_engine = '''      - name: Tests (the GUI ones skip themselves without Qt; one process per file)
        run: python tests/run_all_tests.py
'''
    new_engine = '''      - name: Tests (the GUI ones skip themselves without Qt; one process per file)
        run: |
          python tests/run_all_tests.py || { cat tests/test_results.txt; exit 1; }
'''
    old_gui = '''        env:
          QT_QPA_PLATFORM: offscreen
        run: python tests/run_all_tests.py

  installation:
'''
    new_gui = '''        env:
          QT_QPA_PLATFORM: offscreen
        run: |
          python tests/run_all_tests.py || { cat tests/test_results.txt; exit 1; }

  gui-layout-matrix:
    name: GUI layout at ${{ matrix.scale }}x scale
    runs-on: ubuntu-24.04
    strategy:
      fail-fast: false
      matrix:
        scale: ["1", "1.25", "1.5", "2"]
    env:
      QT_QPA_PLATFORM: offscreen
      QT_SCALE_FACTOR: ${{ matrix.scale }}
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.12"
          cache: pip
      - name: Qt system dependencies
        run: |
          sudo apt-get update
          sudo apt-get install -y libegl1 libgl1 libxkbcommon-x11-0 \
            libxcb-icccm4 libxcb-image0 libxcb-keysyms1 libxcb-randr0 \
            libxcb-render-util0 libxcb-shape0 libxcb-xinerama0 libxcb-cursor0
      - name: Install GUI test dependencies
        run: |
          python -m pip install --upgrade pip
          pip install -e ".[gui,dev]"
      - name: Responsive layout regression subset
        run: |
          pytest -q tests/regression/test_plot_scaling.py \
                    tests/regression/test_small_screen.py \
                    tests/regression/test_gui_layout.py \
                    tests/regression/test_tools_window_layout.py \
                    tests/regression/test_plots.py

  installation:
'''
    for old, new, name in ((old_engine, new_engine, "engine diagnostics"),
                           (old_gui, new_gui, "GUI matrix")):
        count = text.count(old)
        if count != 1:
            raise RuntimeError(f"workflow: expected one {name} anchor, found {count}")
        text = text.replace(old, new, 1)
    path.write_text(text, encoding="utf-8")
    print("patched .github/workflows/tests.yml")


def patch_screenshots() -> None:
    path = ROOT / "tools/gui_screenshots.py"
    text = path.read_text(encoding="utf-8")
    original = text
    pairs = [
        ('''#: The Stability Derivatives window (Tools button, SC-14).
STABILITY_SHOT = "stability.png"
''', '''#: The Stability Derivatives window (Tools button, SC-14).
STABILITY_SHOT = "stability.png"

#: The Transient Simulation window (Tools button, SC-12).
TRANSIENT_SHOT = "transient.png"
'''),
        ('''    written.append(_capture_stability(app, window,
                                       api.open_project(str(PROJECT)),
                                       destination))

    window.close()
''', '''    written.append(_capture_stability(app, window,
                                       api.open_project(str(PROJECT)),
                                       destination))
    written.append(_capture_transient(app, window,
                                      api.open_project(str(PROJECT)),
                                      destination))

    window.close()
'''),
        ('''def check_existing(destination: Path = OUTPUT_DIR) -> int:
    names = [f for f, _i, _h in SHOTS] + [DESIGNER_SHOT, OPTIMIZER_SHOT, STABILITY_SHOT]
''', '''def _capture_transient(app, window, project, destination: Path) -> Path:
    """Captures Transient Simulation, which was the only Tools window
    absent from the generated documentation screenshots."""
    window.state.set_project(project)
    transient = window.transient_window
    transient.resize(WIDTH, HEIGHT)
    transient.show()
    transient.raise_()
    transient.activateWindow()
    _settle(app)

    target = destination / TRANSIENT_SHOT
    _crop(transient.grab(), transient).save(str(target))
    if not target.exists() or target.stat().st_size == 0:
        raise SystemExit(f"gui_screenshots: failed to write {target}")
    print(f"  {TRANSIENT_SHOT:<26} {target.stat().st_size // 1024:>5} KB")
    return target


def check_existing(destination: Path = OUTPUT_DIR) -> int:
    names = [f for f, _i, _h in SHOTS] + [DESIGNER_SHOT, OPTIMIZER_SHOT,
                                          STABILITY_SHOT, TRANSIENT_SHOT]
'''),
    ]
    for old, new in pairs:
        count = text.count(old)
        if count != 1:
            raise RuntimeError(f"gui_screenshots.py: expected one anchor, found {count}: {old[:60]!r}")
        text = text.replace(old, new, 1)
    if text != original:
        path.write_text(text, encoding="utf-8")
        print("patched tools/gui_screenshots.py")


def main() -> None:
    patch_plots()
    patch_designer()
    patch_plot_tests()
    patch_scaling_tests()
    patch_workflow()
    patch_screenshots()


if __name__ == "__main__":
    main()
