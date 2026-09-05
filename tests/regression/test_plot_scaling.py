"""`PR-12` — a figure keeps a readable size, or it scrolls.

Text in a matplotlib figure is measured in POINTS. Shrink a sixteen-panel
grid to fit a small laptop screen and the panels shrink but the azimuth
names, the color-bar numbers and the titles do not: they climb over the
data and over each other. Below roughly two hundred pixels a cell the
grid stops carrying information at all.

So a multi-panel figure gets a floor and the drawing area scrolls under
it, while a single-panel figure keeps the old behaviour and fills
whatever area the window gives it — one plot has nothing to gain from a
scroll bar.

The last class is the one that keeps the fix safe: a minimum size that
escaped the drawing area would push the whole Results tab wider than the
screen, which is a worse defect than the one being fixed.
"""
import unittest

from tests.helpers import HAS_QT as _HAS_QT

if not _HAS_QT:                                  # pragma: no cover
    raise unittest.SkipTest("PyQt6 is not installed (the engine and CLI run "
                            "without it on purpose)")

from matplotlib.figure import Figure
from PyQt6.QtWidgets import QApplication, QScrollArea

from zbemt.gui.common import CanvasHost, apply_figure_minimum_size
from zbemt.viz import plots


class TestTheFloorIsPerPanel(unittest.TestCase):
    """`plots.figure_minimum_pixels` — pure geometry, no GUI."""

    def test_a_single_panel_has_no_floor(self):
        fig = Figure(figsize=(6, 5))
        fig.add_subplot(111)
        self.assertEqual(plots.figure_minimum_pixels(fig), (0, 0))

    def test_a_grid_asks_for_the_panel_minimum_in_each_column(self):
        fig, _axes = plots._new_figure((12.8, 11.0), 4, 4)
        width, height = plots.figure_minimum_pixels(fig)
        self.assertGreaterEqual(width, 4 * plots.PANEL_MINIMUM_PX)
        self.assertGreater(height, 0)

    def test_the_floor_keeps_each_row_at_the_panel_minimum(self):
        """A tall grid must not lose its vertical floor to its aspect ratio."""
        fig, _axes = plots._new_figure((12.8, 11.0), 4, 4)
        _width, height = plots.figure_minimum_pixels(fig)
        self.assertGreaterEqual(height, 4 * plots.PANEL_MINIMUM_PX)

    def test_the_floor_keeps_each_row_at_the_panel_minimum_in_a_wide_figure(self):
        """A wide three-row figure must still reserve 240 pixels per row."""
        fig, _axes = plots._new_figure((16.0, 9.0), 3, 4)
        _width, height = plots.figure_minimum_pixels(fig)
        self.assertGreaterEqual(height, 3 * plots.PANEL_MINIMUM_PX)

    def test_the_floor_keeps_each_rendered_axis_at_the_panel_minimum(self):
        """Margins and gaps must not consume the panel minimum."""
        fig, _axes = plots._new_figure((16.0, 9.0), 3, 4)
        width, height = plots.figure_minimum_pixels(fig)
        fig.set_dpi(100)
        fig.set_size_inches(width / 100, height / 100, forward=True)
        fig.draw_without_rendering()
        sizes = [(axis.get_position().width * width,
                  axis.get_position().height * height)
                 for axis in fig.axes]
        self.assertTrue(all(panel_width >= plots.PANEL_MINIMUM_PX
                            and panel_height >= plots.PANEL_MINIMUM_PX
                            for panel_width, panel_height in sizes), sizes)

    def test_a_wider_grid_asks_for_more_width(self):
        narrow, _ = plots._new_figure((6.4, 5.5), 2, 2)     # 2 columns
        wide, _ = plots._new_figure((12.8, 5.5), 2, 4)      # 4 columns
        self.assertGreater(plots.figure_minimum_pixels(wide)[0],
                            plots.figure_minimum_pixels(narrow)[0])

    def test_a_colour_bar_inset_is_not_counted_as_a_panel(self):
        """An inset axes has no grid specification. Counting axes instead
        of reading the specification would make every disk map look like
        a two-panel figure."""
        fig = Figure(figsize=(6, 5))
        ax = fig.add_subplot(111)
        ax.inset_axes([1.02, 0.0, 0.04, 1.0])
        self.assertEqual(plots.figure_grid_shape(fig), (1, 1))
        self.assertEqual(plots.figure_minimum_pixels(fig), (0, 0))

    def test_the_real_disk_grid_gets_a_floor(self):
        maps = _disk_maps()
        fig = plots.plot_disk_map_grid(maps, fields=["Fn", "Ft", "Cl", "Cd"])
        width, height = plots.figure_minimum_pixels(fig)
        self.assertGreaterEqual(width, 2 * plots.PANEL_MINIMUM_PX)
        self.assertGreater(height, 0)

    def test_a_single_disk_map_gets_none(self):
        maps = _disk_maps()
        fig = Figure(figsize=(6, 5))
        plots.plot_disk_map(maps, field="Fn", ax=fig.add_subplot(111))
        self.assertEqual(plots.figure_minimum_pixels(fig), (0, 0))


def _disk_maps() -> dict:
    """The smallest payload `plot_disk_map` accepts."""
    import numpy as np

    r = np.linspace(0.2, 1.0, 6)
    psi = np.linspace(0.0, 2.0 * np.pi, 8, endpoint=False)
    R, PSI = np.meshgrid(r, psi, indexing="ij")
    field = np.cos(PSI) * R
    return {"R_NORM": R, "PSI": PSI, "Fn": field, "Ft": field,
            "Cl": field, "Cd": field, "reverse": R < 0.0}


class TestTheCanvasHostScrolls(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def test_the_drawing_area_is_a_scroll_area(self):
        host = CanvasHost()
        self.assertIsInstance(host._scroll, QScrollArea)
        self.assertTrue(host._scroll.widgetResizable(),
                        "a non-resizable scroll area would stop the figure "
                        "from growing when there IS room")

    def test_the_canvas_lives_inside_the_scroll_area(self):
        host = CanvasHost()
        self.assertIs(host._scroll.widget(), host._current)

    def test_a_grid_canvas_carries_the_floor_and_a_single_one_does_not(self):
        host = CanvasHost()
        grid, _axes = plots._new_figure((12.8, 11.0), 4, 4)
        host.show_figure(grid)
        grid_minimum = host._current.minimumSize()
        self.assertGreaterEqual(grid_minimum.width(), 4 * plots.PANEL_MINIMUM_PX)

        single = Figure(figsize=(6, 5))
        single.add_subplot(111)
        host.show_figure(single)
        self.assertEqual(host._current.minimumSize().width(), 0)
        self.assertEqual(host._current.minimumSize().height(), 0)

    def test_apply_figure_minimum_size_reports_what_it_set(self):
        host = CanvasHost()
        fig, _axes = plots._new_figure((12.8, 11.0), 4, 4)
        width, height = apply_figure_minimum_size(host._current, fig)
        self.assertEqual((host._current.minimumSize().width(),
                          host._current.minimumSize().height()), (width, height))


class TestTheFloorStaysInsideTheDrawingArea(unittest.TestCase):
    """The firewall. A figure minimum that reached the tab would make the
    window itself unusable on the very screen the fix is for."""

    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def test_the_host_minimum_does_not_follow_the_figure(self):
        host = CanvasHost()
        before = host.minimumSizeHint().width()
        grid, _axes = plots._new_figure((12.8, 11.0), 4, 4)
        host.show_figure(grid)
        self.assertLess(host.minimumSizeHint().width(),
                        4 * plots.PANEL_MINIMUM_PX,
                        "the grid's floor escaped the scroll area and is now "
                        "the whole tab's minimum width")
        self.assertLessEqual(abs(host.minimumSizeHint().width() - before), 200)

    def test_the_host_can_still_be_made_small(self):
        host = CanvasHost()
        grid, _axes = plots._new_figure((12.8, 11.0), 4, 4)
        host.show_figure(grid)
        host.resize(320, 240)
        self.assertEqual(host.width(), 320)
        self.assertEqual(host.height(), 240)


if __name__ == "__main__":
    unittest.main()
