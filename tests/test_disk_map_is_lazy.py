"""The heaviest views are produced when they are ASKED for (`PR-11`).

`PR-11` says no user action may freeze the interface. Two views broke it
by doing their most expensive work before the user had said what to look
at.

THE DISK MAP DREW THE WHOLE GRID ON THE WAY PAST. The field dropdown's
first item was "(grid with all fields)", so it was also the default:
merely selecting the Disk map view produced sixteen contoured discs.
Measured cold on a six-case batch, that was 9.9 s before the
triangulation fix and 1.9 s after it. The dropdown now opens on a
placeholder that draws nothing; the grid is one click away, chosen
rather than arrived at. Opening the view costs 53 ms, and a single disc
110 ms.

THE 3D PREVIEW DREW THE SOLVER'S MESH. `plot_surface` with `facecolors`
converts one colour per QUAD through matplotlib's slow per-element path,
so the cost is the face count and nothing else. The solver's grid is
150 x 360 on a typical project: 53,640 faces onto a canvas about 400
pixels across, more than one face per pixel in both directions. Drawn at
preview resolution the view went from 1861 ms to 305 ms.
"""
import os
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import numpy as np

from tests.helpers import HAS_QT


@unittest.skipUnless(HAS_QT, "PyQt6 is not installed")
class TestTheDiskMapWaitsToBeAsked(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        from PyQt6.QtWidgets import QApplication

        cls._app = QApplication.instance() or QApplication([])
        from zbemt.gui.app import MainWindow

        cls.window = MainWindow()
        # Captured BEFORE any test touches the combo: what is being
        # asserted is the state the tab is born in, and a later test that
        # picks a field would otherwise be what the assertion reads.
        cls.initial_choice = (
            cls.window.tabs.widget(6).disk_field_combo.currentText())

    def setUp(self):
        self.tab = self.window.tabs.widget(6)

    def test_the_placeholder_is_the_default(self):
        from zbemt.gui.tabs.results import _DISK_PROMPT

        self.assertEqual(
            self.tab.disk_field_combo.itemText(0), _DISK_PROMPT,
            "the first item is the default, and the grid of every field "
            "is the most expensive thing the tab can draw")
        self.assertEqual(self.initial_choice, _DISK_PROMPT)

    def test_opening_the_view_draws_nothing(self):
        from zbemt.gui.tabs.results import _DISK_PROMPT

        drawn = []
        original = self.tab.canvas_host.show_figure
        self.tab.canvas_host.show_figure = (
            lambda key, build: drawn.append(key))
        try:
            self.tab.disk_field_combo.setCurrentText(_DISK_PROMPT)
            self.tab._refresh_disk()
        finally:
            self.tab.canvas_host.show_figure = original
        self.assertEqual(
            drawn, [],
            "selecting the Disk map view built a figure before the user "
            "had said which disk to look at")

    def test_the_grid_is_still_reachable(self):
        """A guard, not a removal: the grid is one click away."""
        from zbemt.gui.tabs.results import _DISK_GRID

        self.assertGreaterEqual(self.tab.disk_field_combo.findText(_DISK_GRID),
                                 0)

    def test_the_colour_controls_are_dead_on_the_placeholder(self):
        """They act on ONE disc, so they mean nothing before one is
        chosen, and nothing on the grid either."""
        from zbemt.gui.tabs.results import _DISK_GRID, _DISK_PROMPT

        for choice in (_DISK_PROMPT, _DISK_GRID):
            with self.subTest(choice=choice):
                self.tab.disk_field_combo.setCurrentText(choice)
                self.tab._update_disk_color_controls_enabled()
                self.assertFalse(self.tab.disk_color_scale_combo.isEnabled())

    def test_a_single_field_enables_them_again(self):
        field = self.tab._DISK_FIELDS[0]
        self.tab.disk_field_combo.setCurrentText(field)
        self.tab._update_disk_color_controls_enabled()
        self.assertTrue(self.tab.disk_color_scale_combo.isEnabled())


@unittest.skipUnless(HAS_QT, "PyQt6 is not installed")
class TestThe3dPreviewDrawsAtPreviewResolution(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        from PyQt6.QtWidgets import QApplication

        cls._app = QApplication.instance() or QApplication([])
        from zbemt.gui.app import MainWindow

        cls.window = MainWindow()

    def test_the_solver_mesh_is_thinned(self):
        tab = self.window.tabs.widget(6)
        rows, cols = 150, 360
        grid = np.zeros((rows, cols))
        thinned, = tab._decimate_for_drawing(grid)
        faces = (thinned.shape[0] - 1) * (thinned.shape[1] - 1)
        self.assertLess(
            faces, (rows - 1) * (cols - 1) // 4,
            "the preview still draws more than a quarter of the solver's "
            "faces; the cost of this view IS the face count")

    def test_the_rim_and_the_seam_are_kept(self):
        """Dropping the last row would stop the disc at the last station
        before the tip; dropping the last column would leave it open."""
        tab = self.window.tabs.widget(6)
        marker = np.arange(150 * 360, dtype=float).reshape(150, 360)
        thinned, = tab._decimate_for_drawing(marker)
        self.assertEqual(thinned[0, 0], marker[0, 0])
        self.assertEqual(thinned[-1, -1], marker[-1, -1])
        self.assertEqual(thinned[0, -1], marker[0, -1])
        self.assertEqual(thinned[-1, 0], marker[-1, 0])

    def test_a_grid_already_small_enough_is_untouched(self):
        tab = self.window.tabs.widget(6)
        small = np.arange(20 * 30, dtype=float).reshape(20, 30)
        thinned, = tab._decimate_for_drawing(small)
        np.testing.assert_array_equal(thinned, small)

    def test_every_array_is_thinned_the_same_way(self):
        """X, Y, Z and the values have to keep corresponding, or the
        colour of a face would belong to a different face."""
        tab = self.window.tabs.widget(6)
        a = np.arange(150 * 360, dtype=float).reshape(150, 360)
        first, second = tab._decimate_for_drawing(a, a * 2.0)
        np.testing.assert_allclose(second, first * 2.0)


def tearDownModule():
    """Qt's teardown, not the interpreter's -- see the note in
    `tests/test_small_screen.py`."""
    if not HAS_QT:                                # pragma: no cover
        return
    from PyQt6.QtWidgets import QApplication

    app = QApplication.instance()
    if app is not None:
        app.processEvents()


if __name__ == "__main__":   # pragma: no cover
    unittest.main()
