"""`zbemt/gui/help_registry.py` -- field-level context popup (Part 1
of the documentation redesign plan).

Derives the short explanation for each field from the SAME "Parameters by
tab" table that `field_help.field_map()` already uses for the anchor
-- without a second source of content. See the module's docstring for the
full reasoning.
"""
import unittest

try:
    from PyQt6.QtWidgets import QApplication
    _HAS_QT = True
except ImportError:                                   # pragma: no cover
    _HAS_QT = False


class TestRegistroDeCampos(unittest.TestCase):
    def test_cobre_campos_conhecidos(self):
        from zbemt.gui.help_registry import field_registry
        reg = field_registry()
        self.assertIn("n_blades", reg)
        self.assertIn("stall_model", reg)
        self.assertIn("collective_deg", reg)

    def test_short_description_matches_the_html(self):
        from zbemt.gui.help_registry import short_description
        desc = short_description("n_blades")
        self.assertIsNotNone(desc)
        self.assertIn("Number of blades", desc)

    def test_qualified_name_with_prefix_is_accepted(self):
        """`field_help._widget_field` returns the suffix, but a
        caller may pass `"geometry.n_blades"` by mistake -- it must not
        break, just fall through to the same field."""
        from zbemt.gui.help_registry import short_description
        self.assertEqual(short_description("n_blades"), short_description("geometry.n_blades"))

    def test_unknown_field_returns_none(self):
        from zbemt.gui.help_registry import short_description
        self.assertIsNone(short_description("field_that_does_not_exist_xyz"))


@unittest.skipUnless(_HAS_QT, "PyQt6 not installed")
class TestClickableLabelInGeometry(unittest.TestCase):
    """The new system uses QToolButton as clickable label -- no '?' button per field."""

    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        import tempfile, shutil
        from tests import helpers
        self._tmp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self._tmp, ignore_errors=True)
        with helpers.patch_message_box_everywhere("PROJECTS_ROOT", self._tmp):
            from zbemt.gui import app as gui
            self.win = gui.MainWindow()
        self.addCleanup(self.win.deleteLater)

    def test_geometry_tab_has_clickable_labels(self):
        """Documented fields in the Geometry tab gain QToolButton label (hand cursor)."""
        from PyQt6.QtCore import Qt
        from PyQt6.QtWidgets import QToolButton
        tab = self.win.tabs.widget(1)   # Geometry
        clickable = [b for b in tab.findChildren(QToolButton)
                     if b.cursor().shape() == Qt.CursorShape.PointingHandCursor]
        self.assertTrue(clickable, "Geometry tab has no clickable field labels")
        # default tooltip for clickable labels
        # The exact string comes from `field_help._label_clicavel`. This test
        # searched for "Click for help", which never existed -- the tooltip is
        # "Click the label for help on this field" --, so it has failed since
        # it was written. Matching by stable substring ("for help") instead of
        # the whole phrase prevents a copy rewrite from breaking the test
        # without anything actually breaking.
        self.assertTrue(any("for help" in b.toolTip() for b in clickable),
                        f"tooltips: {[b.toolTip() for b in clickable][:3]}")


@unittest.skipUnless(_HAS_QT, "PyQt6 not installed")
class TestPopupNeverOverflowsScreen(unittest.TestCase):
    """Regression: the field-help popup must never exceed the screen and
    nothing inside its body may be cut off at the right edge.

    House rule: "No text may ever be clipped or overflow its area".
    The `geometry_spec` field reproduces the reported defect: grammar
    strings like ``cst:a1,a2,...`` plus three analytic families packed
    into one mathtext image pushed the body wider than the scroll
    viewport (whose horizontal scrollbar is always off), so the tail of
    every line vanished past the popup's right edge.
    """

    #: Hard readability cap asserted here; must match the engine's cap.
    HARD_CAP_PX = 760

    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        from PyQt6.QtWidgets import QWidget
        from zbemt.gui.help_popup import HelpPopup
        self._host = QWidget()
        self._host.move(0, 0)          # deterministic anchor at the origin
        self._host.resize(400, 300)
        self._host.show()
        self.app.processEvents()
        self.popup = HelpPopup.instance(self._host)
        self.addCleanup(self._cleanup)

    def _cleanup(self):
        try:
            self.popup.close_popup()
        except RuntimeError:
            pass
        self._host.close()
        self._host.deleteLater()

    def _open_and_measure(self, field):
        """Opens the real popup for `field` and returns
        (availableGeometry, popup frameGeometry)."""
        screen = self.app.primaryScreen()
        self.assertIsNotNone(screen)
        self.popup.show_field(field, self._host)
        self.app.processEvents()
        return screen.availableGeometry(), self.popup.frameGeometry()

    def test_geometry_spec_width_respects_screen_fraction_and_cap(self):
        avail, frame = self._open_and_measure("geometry_spec")
        limit = min(int(avail.width() * 0.92) + 1, self.HARD_CAP_PX)
        self.assertLessEqual(
            frame.width(), limit,
            f"popup is {frame.width()}px wide; cap is "
            f"min(92% of {avail.width()}px, {self.HARD_CAP_PX}px) = {limit}px")

    def test_geometry_spec_height_respects_available_height(self):
        avail, frame = self._open_and_measure("geometry_spec")
        self.assertLessEqual(
            frame.height(), avail.height() + 1,
            f"popup is {frame.height()}px tall on a "
            f"{avail.height()}px-high screen")

    def test_every_body_label_has_word_wrap(self):
        from PyQt6.QtWidgets import QLabel
        self._open_and_measure("geometry_spec")
        nowrap = [lbl for lbl in self.popup._body_widget.findChildren(QLabel)
                  if not lbl.wordWrap()]
        self.assertEqual(
            nowrap, [],
            f"{len(nowrap)} body QLabel(s) without WordWrap: "
            f"{[(l.text()[:30] or '<pixmap>') for l in nowrap]}")

    def test_no_body_row_is_wider_than_the_viewport(self):
        self._open_and_measure("geometry_spec")
        viewport_w = self.popup._scroll.viewport().width()
        wider = []
        layout = self.popup._body_layout
        for i in range(layout.count()):
            item = layout.itemAt(i)
            w = item.widget() if item else None
            if w is None:
                continue
            min_w = w.minimumSizeHint().width()
            if min_w > viewport_w + 2:
                wider.append((i, min_w))
        self.assertEqual(
            wider, [],
            f"rows wider than the {viewport_w}px viewport are cut at the "
            f"right edge (horizontal scrollbar is always off): {wider}")

    def test_second_content_heavy_field_also_fits(self):
        from zbemt.gui.help_content import FIELD_HELP
        key = "ncrit" if "ncrit" in FIELD_HELP else "bezier_control_points"
        avail, frame = self._open_and_measure(key)
        limit = min(int(avail.width() * 0.92) + 1, self.HARD_CAP_PX)
        self.assertLessEqual(frame.width(), limit)
        self.assertLessEqual(frame.height(), avail.height() + 1)


if __name__ == "__main__":
    unittest.main()
