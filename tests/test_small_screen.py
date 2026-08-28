"""Every window must fit a small laptop screen (`PR-2`, `QR`).

A 1366x768 panel is still the second most common laptop resolution.
Once the window frame and the task bar are gone it leaves roughly
1366x700 of client area, and a window whose MINIMUM size is larger than
that cannot be made to fit: Qt honours the minimum, the content runs
past the screen edge, and there is no scroll bar to reach it. The user
meets it as a Run button they cannot click.

Four windows failed this. The Stability window asked for 1490x655 and
the Geometry Designer for 1476x757, both because a `QTabWidget` takes
the largest minimum of its pages. The main window asked for 1500x351,
because a `QSplitter`'s minimum is the SUM of its panes' minimums and
the Airfoil tab put a 520-pixel form beside a 954-pixel preview; the
Results tab added a 582-pixel history panel next to its plots.

The fix is the same one the plot canvases already use: content that
cannot shrink goes into a `QScrollArea` with `setWidgetResizable(True)`,
which changes nothing when there is room and scrolls when there is not.

These numbers are a CEILING on a minimum, so they cannot be satisfied by
accident: a window that fails here is one a user cannot fully see.
"""
import unittest

from tests.helpers import HAS_QT as _HAS_QT

if not _HAS_QT:                                  # pragma: no cover
    raise unittest.SkipTest("PyQt6 is not installed (the engine and CLI run "
                            "without it on purpose)")

from PyQt6.QtWidgets import QApplication

#: A 1366x768 laptop, less the window frame and the task bar.
SMALL_W, SMALL_H = 1366, 700


#: One main window for the whole module, built on first use and never
#: closed. `setUpClass` runs once per CLASS, so a per-class window gives
#: one per subclass; closing them again is not enough, because Qt's
#: teardown of several fully built main windows in one process is what
#: `CLAUDE.md` warns about, and in a sibling file it stopped the process
#: exiting at all. The runner gives this file its own process.
_WINDOW = None


def _shared_window():
    global _WINDOW
    if _WINDOW is None:
        from zbemt import api
        from zbemt.gui.app import MainWindow

        _WINDOW = MainWindow()
        _WINDOW.state.set_project(api.open_project("projects/starter_rotor"))
    return _WINDOW


class SmallScreenBase(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls._app = QApplication.instance() or QApplication([])
        cls.window = _shared_window()

    def _required(self, widget):
        """What the widget cannot be made smaller than, in pixels."""
        hint = widget.minimumSizeHint()
        floor = widget.minimumSize()
        return (max(hint.width(), floor.width()),
                max(hint.height(), floor.height()))

    def _assert_fits(self, name, widget):
        need_w, need_h = self._required(widget)
        self.assertLessEqual(
            need_w, SMALL_W,
            f"{name} cannot be narrower than {need_w} px, so on a "
            f"{SMALL_W}-wide screen part of it is unreachable")
        self.assertLessEqual(
            need_h, SMALL_H,
            f"{name} cannot be shorter than {need_h} px, so on a "
            f"{SMALL_H}-tall client area part of it is unreachable")


class TestTheToolsWindowsFit(SmallScreenBase):
    """The four windows behind the Tools menu."""

    TOOLS = (("Geometry Designer", "geometry_designer"),
             ("Transient Simulation", "transient_window"),
             ("Design Optimization", "optimizer_window"),
             ("Stability Derivatives", "stability_window"))

    def test_each_tools_window_fits(self):
        for label, attribute in self.TOOLS:
            with self.subTest(window=label):
                widget = getattr(self.window, attribute, None)
                self.assertIsNotNone(
                    widget, f"{label} is not built on the main window as "
                            f"{attribute!r}; if it was renamed, rename it here "
                            f"too rather than dropping the check")
                self._assert_fits(label, widget)


class TestTheMainWindowFits(SmallScreenBase):

    def test_the_main_window_fits(self):
        self._assert_fits("main window", self.window)

    def test_every_tab_fits(self):
        """Named one by one, because the window takes the LARGEST minimum
        of its tabs and a failure that only names the window does not say
        which tab to look at."""
        tabs = self.window.tabs
        for index in range(tabs.count()):
            with self.subTest(tab=tabs.tabText(index)):
                self._assert_fits(tabs.tabText(index), tabs.widget(index))


class TestScrollingIsWhatMakesItFit(SmallScreenBase):
    """A guard against the wrong fix.

    Shrinking a minimum by deleting content, or by letting labels wrap
    into unreadable two-line rows, would also pass the tests above. What
    is wanted is that the content is still THERE and reachable, which is
    what a scroll area provides.
    """

    def test_the_stability_pages_are_scrollable(self):
        from PyQt6.QtWidgets import QScrollArea, QTabWidget

        window = self.window.stability_window
        pages = window.findChild(QTabWidget)
        self.assertIsNotNone(pages, "the Stability window has no page tabs")
        for index in range(pages.count()):
            with self.subTest(page=pages.tabText(index)):
                self.assertIsInstance(
                    pages.widget(index), QScrollArea,
                    "the page must sit in a scroll area, so that making the "
                    "window small hides nothing permanently")

    def test_the_designer_pages_are_scrollable(self):
        from PyQt6.QtWidgets import QScrollArea

        pages = self.window.geometry_designer.pages
        for index in range(pages.count()):
            with self.subTest(page=pages.tabText(index)):
                self.assertIsInstance(pages.widget(index), QScrollArea)

    def test_a_scrolled_page_still_reports_its_natural_size(self):
        """The page inside keeps the size it wants; only the AREA around
        it is allowed to be small. If the page itself had been squeezed,
        the layout would be broken rather than scrolled."""
        from PyQt6.QtWidgets import QTabWidget

        pages = self.window.stability_window.findChild(QTabWidget)
        inner = pages.widget(0).widget()
        self.assertIsNotNone(inner, "the scroll area holds no page")
        self.assertGreater(inner.sizeHint().width(), 200,
                            "the page collapsed instead of being scrolled")



def tearDownModule():
    """Hand the shared windows back to QT while it can still take them.

    `hide()` then `deleteLater()` is the pattern the other GUI test
    files use. Left to the interpreter instead, the last reference was
    dropped in an order Qt does not control and the process exited with
    a native access violation on roughly half the runs -- with every
    test having PASSED, which is the worst way for a suite to fail.
    """
    global _WINDOW
    for window in (_WINDOW,):
        if window is not None:
            window.hide()
            window.deleteLater()
    _WINDOW = None
    app = QApplication.instance()
    if app is not None:
        app.processEvents()

if __name__ == "__main__":   # pragma: no cover
    unittest.main()
