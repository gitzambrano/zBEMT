"""The Results tab does not freeze the interface (`PR-11`).

Reported from use: "to change an option there inside the results window,
or to choose each of the cases to plot, it locks up for some
milliseconds or even seconds."

Measured, on a six-case batch and a fast machine, one COLD redraw per
view mode. The cache hides this on a repeat, which is why the numbers
have to be taken with it cleared:

    Disk map              9919 ms      <- and 7239 ms of it in qhull
    3D                    1861 ms
    Azimuth / Radius       775 ms
    Coefficients vs axis   718 ms
    Convergence            613 ms

Two separate causes, and this file guards both.

ONE REDRAW COSTS TOO MUCH. `plot_disk_map` built a
`matplotlib.tri.Triangulation` from the disk's nodes with no explicit
triangle list, so matplotlib ran a Delaunay over them -- 0.45 s per
field, sixteen fields per grid. Those nodes are not scattered: they are
a structured polar grid, whose triangulation is two triangles per cell
and is known without any search. The disk map went to 1855 ms.

ONE PATH STILL DREW SYNCHRONOUSLY. The tab already coalesced a burst of
changes through `_selection_timer`, and `_schedule_redraw` is its entry
point. `_maybe_refresh` did not use it, so the 3D view's two field
dropdowns built a figure on every change. A first attempt at this added
a SECOND timer beside the existing one; that duplicated a mechanism
rather than fixing anything, and the last test here exists so it does
not come back.
"""
import os
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import numpy as np

from tests.helpers import HAS_QT


class TestTheGridIsTriangulatedWithoutASearch(unittest.TestCase):

    def test_the_triangles_are_the_grid_cells_split_in_two(self):
        from zbemt.viz.plots import _structured_triangles

        triangles = _structured_triangles(3, 4)
        self.assertEqual(triangles.shape, (2 * 2 * 3, 3),
                          "two triangles per cell of a 3x4 grid")
        # Every node index is inside the grid, and every node of the
        # interior is used: a triangulation that drops nodes would leave
        # holes in the disk.
        self.assertEqual(int(triangles.min()), 0)
        self.assertEqual(int(triangles.max()), 3 * 4 - 1)
        self.assertEqual(len(np.unique(triangles)), 12)

    def test_the_first_cell_is_wound_consistently(self):
        """`tripcolor` needs one winding for the whole mesh; a Delaunay
        does not guarantee it."""
        from zbemt.viz.plots import _structured_triangles

        triangles = _structured_triangles(2, 2)
        self.assertEqual(sorted(triangles[0].tolist()), [0, 1, 2])
        self.assertEqual(sorted(triangles[1].tolist()), [1, 2, 3])

    def test_a_degenerate_grid_gives_no_triangles(self):
        from zbemt.viz.plots import _structured_triangles

        self.assertEqual(_structured_triangles(1, 5).shape, (0, 3))
        self.assertEqual(_structured_triangles(5, 1).shape, (0, 3))

    def test_a_delaunay_of_the_same_nodes_spills_over_the_curved_edge(self):
        """The structured triangulation is not merely faster: it covers
        the RIGHT REGION.

        A Delaunay triangulates the CONVEX HULL of the nodes, and the
        disk's inner arc is concave, so it bridges across the hub hole
        and paints area that has no data behind it -- interpolated out
        of the innermost ring. The structured grid has no such cell.
        Measured here as the excess area the Delaunay covers."""
        import matplotlib.tri as mtri

        from zbemt.viz.plots import _structured_triangles

        rows, cols = 6, 9
        r = np.linspace(0.2, 1.0, rows)
        psi = np.linspace(0.0, 2.0 * np.pi, cols)
        # A patch of the disk, not the whole annulus: over a full ring
        # the two disagree by construction, because a Delaunay bridges
        # the hub hole and the structured grid does not.
        psi = psi[:cols // 2]
        R, P = np.meshgrid(r, psi, indexing="ij")
        x, y = (R * np.cos(P)).ravel(), (R * np.sin(P)).ravel()

        def area(triangles):
            a, b, c = (np.column_stack([x, y])[triangles[:, i]]
                       for i in range(3))
            return float(np.abs(np.cross(b - a, c - a)).sum() / 2.0)

        mine = area(_structured_triangles(rows, len(psi)))
        theirs = area(mtri.Triangulation(x, y).triangles)
        self.assertGreater(
            theirs, mine,
            "a Delaunay must cover MORE than the grid it was given, "
            "because it fills the concave side")
        # The whole patch, not a sliver: the two agree on the bulk and
        # differ only along the curved boundary.
        self.assertLess((theirs - mine) / theirs, 0.10)


class TestTheDiskMapNeverRunsQhull(unittest.TestCase):
    """The regression guard proper. The cost is not in a number that a
    test can assert without being flaky on a loaded machine; it is in
    ONE CALL that should not happen at all."""

    def _maps(self, radial=12, azimuths=24):
        r = np.linspace(0.15, 1.0, radial)
        psi = np.linspace(0.0, 2.0 * np.pi * (azimuths - 1) / azimuths,
                          azimuths)
        R, P = np.meshgrid(r, psi, indexing="ij")
        return {"R_NORM": R, "PSI": P,
                "lambda_i": 0.05 + 0.02 * R * np.cos(P),
                "Ut": 1.0 + 0.3 * np.sin(P)}

    def _draw_counting_qhull(self, **kwargs):
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib._qhull as qhull
        from matplotlib.figure import Figure

        from zbemt.viz import plots

        calls = []
        original = qhull.delaunay

        def counting(*args, **kw):
            calls.append(1)
            return original(*args, **kw)

        qhull.delaunay = counting
        try:
            figure = Figure()
            plots.plot_disk_map(self._maps(), field="lambda_i",
                                 ax=figure.add_subplot(111), **kwargs)
        finally:
            qhull.delaunay = original
        return len(calls)

    def test_with_the_reverse_flow_mask(self):
        self.assertEqual(
            self._draw_counting_qhull(mask_reverse=True), 0,
            "the disk map ran a Delaunay over nodes that are already a "
            "structured grid; that was 7.2 of its 9.4 seconds")

    def test_without_the_mask(self):
        """The unmasked branch passed bare coordinates to `tricontourf`,
        which builds its own Delaunay internally -- the same cost by
        another route."""
        self.assertEqual(self._draw_counting_qhull(mask_reverse=False), 0)


@unittest.skipUnless(HAS_QT, "PyQt6 is not installed")
class TestEveryOptionTakesTheDeferredPath(unittest.TestCase):
    """The tab already coalesced a burst of changes into one redraw,
    through `_selection_timer` and `_schedule_redraw`. One path did not
    use it: `_maybe_refresh`, which the 3D view's two field dropdowns go
    through, still built a figure synchronously on every change."""

    @classmethod
    def setUpClass(cls):
        from PyQt6.QtWidgets import QApplication

        cls._app = QApplication.instance() or QApplication([])
        from zbemt.gui.app import MainWindow

        cls.window = MainWindow()

    def test_the_3d_field_dropdowns_defer_like_everything_else(self):
        tab = self.window.tabs.widget(6)
        drawn = []
        original = tab._refresh_current
        tab._refresh_current = lambda: drawn.append(1)
        try:
            tab.mode_list.setCurrentRow(tab._MODES.index("3D"))
            tab._selection_timer.stop()
            drawn.clear()
            tab._maybe_refresh("3D")
            self.assertEqual(
                drawn, [],
                "a field change on the 3D view drew synchronously instead "
                "of scheduling one redraw")
            self.assertTrue(
                tab._selection_timer.isActive(),
                "it must go through the timer the rest of the tab uses")
        finally:
            tab._refresh_current = original

    def test_there_is_exactly_one_debouncer(self):
        """A second timer beside `_selection_timer` would not make
        anything faster: it would split one mechanism in two and let the
        two disagree about what is pending."""
        tab = self.window.tabs.widget(6)
        self.assertTrue(hasattr(tab, "_selection_timer"))
        self.assertTrue(tab._selection_timer.isSingleShot())
        self.assertFalse(
            hasattr(tab, "_refresh_timer"),
            "a duplicate debouncer was added beside the existing one")


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
