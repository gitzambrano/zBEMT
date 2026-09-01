"""`PR-4`/`PR-8`: what the windows actually PRINT, not what they store.

`tests/architecture/test_notation.py` sweeps `nomenclature`, the documentation prose
and the two help dictionaries. Nothing swept the strings the windows
build themselves, and four surfaces were leaking:

  * the Geometry tab wrote an unclosed overbar, so the hinge offset was
    labelled with the literal text "\\bare";
  * the same tab's read-outs printed "&nu;_&beta;^2", because
    `to_html` substituted the Greek macros BEFORE it looked for
    subscripts, and by then the subscript pattern could no longer see
    one;
  * the Stability window labelled its outputs and its bar chart with raw
    engine keys -- `Mx_total`, `My_total`, `Omega`;
  * the Transient window's result table used the engine keys as column
    headings and its preview legend read the plain word "mu".

The rule these check is narrow and mechanical: a string a user reads
must not contain a LaTeX macro, an unlowered `_` between two names, or
a caret. Whether the right symbol was chosen is a different question,
and `nomenclature` is what answers it.
"""
import re
import unittest

from tests.helpers import HAS_QT as _HAS_QT

if not _HAS_QT:                                  # pragma: no cover
    raise unittest.SkipTest("PyQt6 is not installed (the engine and CLI run "
                            "without it on purpose)")

from PyQt6.QtWidgets import QApplication

#: A leftover LaTeX macro, an exponent caret, or an underscore joining
#: two word characters -- the three shapes a half-rendered symbol takes.
_RAW_MACRO = re.compile(r"\\[a-zA-Z]+")
_RAW_CARET = re.compile(r"\^")
_RAW_UNDERSCORE = re.compile(r"[A-Za-z0-9](_)[A-Za-z0-9]")


def _offences(text: str) -> list:
    found = []
    if _RAW_MACRO.search(text):
        found.append("a LaTeX macro")
    if _RAW_CARET.search(text):
        found.append("a caret instead of a superscript")
    if _RAW_UNDERSCORE.search(text):
        found.append("an underscore instead of a subscript")
    return found


class TestTheGeometryTabLabels(unittest.TestCase):
    """Every symbol the blade-dynamics block puts on a label."""

    SYMBOLS = (r"\bar{e}", r"\nu_\beta", r"\nu_\beta^2", r"K_\beta",
               r"I_\beta", r"\gamma", r"\delta_3", "N_h", "m_b", "f_1",
               r"K_\zeta", r"C_\zeta", r"I_\zeta", r"\nu_\zeta")

    @classmethod
    def setUpClass(cls):
        cls._app = QApplication.instance() or QApplication([])

    def test_every_one_renders(self):
        from zbemt.gui.tabs.geometry_tab import _sym

        for latex in self.SYMBOLS:
            with self.subTest(latex=latex):
                rendered = _sym(latex)
                self.assertEqual(
                    _offences(rendered), [],
                    f"{latex!r} rendered as {rendered!r}")

    def test_a_name_with_no_mathematics_is_left_alone(self):
        """The guard that makes the rest safe: `_sym` marks its argument
        as mathematics, and `nomenclature` must still refuse to lower the
        underscore of an identifier that reaches it by another route."""
        from zbemt.nomenclature import to_html

        self.assertEqual(to_html("cfg_solver"), "cfg_solver")
        self.assertEqual(to_html("RPM"), "RPM")


#: One main window and one transient window for the whole module, built
#: on first use and never closed. Closing a fully built main window while
#: other Qt objects are still alive is what made this file exit with a
#: native access violation instead of a result.
_WINDOW = None
_TRANSIENT = None


def _main_window():
    global _WINDOW
    if _WINDOW is None:
        from zbemt.gui.app import MainWindow

        _WINDOW = MainWindow()
    return _WINDOW


def _transient_window():
    global _TRANSIENT
    if _TRANSIENT is None:
        from zbemt.gui.common import AppState
        from zbemt.gui.tabs.transient_window import TransientWindow

        _TRANSIENT = TransientWindow(AppState())
    return _TRANSIENT


class TestTheStabilityWindowOutputs(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls._app = QApplication.instance() or QApplication([])
        cls.window = _main_window()

    def test_the_output_check_boxes_show_symbols(self):
        window = self.window.stability_window
        for key, check in window.output_checks.items():
            with self.subTest(key=key):
                label = check.text()
                self.assertEqual(_offences(label), [],
                                  f"{key} is labelled {label!r}")
                if key in ("Mx_total", "My_total"):
                    self.assertNotEqual(
                        label, key,
                        "the engine key reached the label unrendered")

    def test_the_engine_key_is_still_the_identity(self):
        """The label changed; the dictionary key must not, or
        `_collect_request` would stop naming outputs the engine knows."""
        window = self.window.stability_window
        for key in ("Thrust", "H", "Y", "Mx_total", "My_total", "Torque"):
            self.assertIn(key, window.output_checks)

    def test_the_bar_chart_combo_keeps_the_key_as_data(self):
        combo = self.window.stability_window.bar_output_combo
        self.assertGreater(combo.count(), 0)
        for index in range(combo.count()):
            with self.subTest(index=index):
                self.assertEqual(_offences(combo.itemText(index)), [])
                self.assertIsNotNone(
                    combo.itemData(index),
                    "the engine key must ride along as the item's data, so "
                    "the chart does not depend on how the label is spelled")


class TestTheTransientWindowHeadings(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls._app = QApplication.instance() or QApplication([])

    def setUp(self):
        # Shared, not rebuilt: these three tests only READ headings, and
        # a fresh window per test was three more Qt object trees for the
        # teardown to trip over.
        self.window = _transient_window()

    RESULT_COLUMNS = ("t", "CT", "CQ", "CP", "nu0", "nu_s", "nu_c",
                       "collective_deg", "cyclic_c_deg", "beta_0_deg",
                       "marched_interval_s", "substeps")

    def test_every_result_heading_renders(self):
        for key in self.RESULT_COLUMNS:
            with self.subTest(key=key):
                heading = self.window._column_heading(key)
                self.assertEqual(_offences(heading), [],
                                  f"{key} heads its column as {heading!r}")

    def test_the_inflow_states_are_not_left_as_engine_keys(self):
        """`nu0` is the one group `nomenclature` does not own, so it is
        the one that would silently stay raw."""
        for key in ("nu0", "nu_s", "nu_c"):
            with self.subTest(key=key):
                self.assertNotEqual(self.window._column_heading(key), key)
                self.assertIn("ν", self.window._column_heading(key))

    def test_time_is_still_seconds(self):
        self.assertIn("s", self.window._column_heading("t"))



def tearDownModule():
    """Hand the shared windows back to QT while it can still take them.

    `hide()` then `deleteLater()` is the pattern the other GUI test
    files use. Left to the interpreter instead, the last reference was
    dropped in an order Qt does not control and the process exited with
    a native access violation on roughly half the runs -- with every
    test having PASSED, which is the worst way for a suite to fail.
    """
    global _WINDOW, _TRANSIENT
    for window in (_WINDOW, _TRANSIENT):
        if window is not None:
            window.hide()
            window.deleteLater()
    _WINDOW, _TRANSIENT = None, None
    app = QApplication.instance()
    if app is not None:
        app.processEvents()

if __name__ == "__main__":   # pragma: no cover
    unittest.main()
