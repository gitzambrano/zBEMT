"""What the rendered Tools windows show, not what their code says.

Every test passed and the screens still had four defects, found by
running `tools/gui_screenshots.py` and looking at the images. Three of
them are checked here; the fourth (a label that reached the screen with
a literal underscore) belongs to `tests/test_notation.py`'s rule and is
covered by the fix there.

The layout rules of CLAUDE.md were enforced over the MAIN WINDOW's tabs
and never over a Tools window:

- "Buttons that appear together should share a width", and none should
  stretch much beyond its own text. `test_gui_layout` checks this, but
  only for rows holding two or more buttons, so "Run trim only" -- alone
  in its layout and eleven hundred pixels wide for eighty pixels of text
  -- was outside every check there is.

- "Align fields vertically across forms as far as possible." A
  `QGridLayout` gives all the slack to its LAST column, so the Search
  settings box put every value about nine hundred pixels from its own
  label, at the opposite edge of the window. `widgets.py` documents the
  same defect for the flow rows; nothing tested for it here.
"""
import os
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from tests.helpers import HAS_QT

#: How much wider than its own text a button may be before it reads as a
#: banner rather than a control. Generous, because padding, an icon and
#: a group width are all legitimate.
WIDTH_ALLOWANCE = 2.6

#: How far a value may sit from the label that names it, in pixels.
#: Wide enough for a long label column, narrow enough that the two
#: pieces of one field cannot end up at opposite edges of the window.
LABEL_GAP_LIMIT = 320


@unittest.skipUnless(HAS_QT, "PyQt6 is not installed")
class TestToolsWindowsFollowTheLayoutRules(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        from PyQt6.QtWidgets import QApplication

        cls._app = QApplication.instance() or QApplication([])
        from zbemt.gui.app import MainWindow

        cls.window = MainWindow()
        cls.window.resize(1500, 980)
        cls.window.show()
        QApplication.processEvents()

    @classmethod
    def _windows(cls):
        from PyQt6.QtWidgets import QApplication
        from zbemt.gui.tabs.designer_window import GeometryDesignerWindow
        from zbemt.gui.tabs.optimizer_window import OptimizerWindow
        from zbemt.gui.tabs.stability_window import StabilityWindow
        from zbemt.gui.tabs.transient_window import TransientWindow

        for title, klass in (("Geometry Designer", GeometryDesignerWindow),
                              ("Design Optimization", OptimizerWindow),
                              ("Stability", StabilityWindow),
                              ("Transient", TransientWindow)):
            window = klass(cls.window.state)
            window.resize(1500, 980)
            window.show()
            QApplication.processEvents()
            yield title, window
            window.hide()

    def test_no_button_is_as_wide_as_its_panel(self):
        from PyQt6.QtWidgets import QPushButton

        offenders = []
        for title, window in self._windows():
            for button in window.findChildren(QPushButton):
                if not button.isVisible() or not button.text().strip():
                    continue
                text = button.fontMetrics().horizontalAdvance(button.text())
                if text <= 0:
                    continue
                if button.width() > WIDTH_ALLOWANCE * text + 60:
                    offenders.append(
                        f"{title}: {button.text()!r} is {button.width()}px "
                        f"wide for {text}px of text")
        self.assertEqual(
            offenders, [],
            "a button as wide as its panel reads as a banner, not a "
            "control: " + "; ".join(offenders))

    def test_no_value_sits_an_arms_length_from_its_label(self):
        """The two halves of one field must stay together.

        A `QGridLayout` hands all the slack to its last column, so a box
        wider than its labels pushes every value to the far edge. The
        reader then has to trace across the window to see which number
        belongs to which name.
        """
        from PyQt6.QtWidgets import (QAbstractSpinBox, QComboBox, QGridLayout,
                                     QLabel)

        offenders = []
        for title, window in self._windows():
            for grid in window.findChildren(QGridLayout):
                for row in range(grid.rowCount()):
                    label_item = grid.itemAtPosition(row, 0)
                    value_item = grid.itemAtPosition(row, 1)
                    if label_item is None or value_item is None:
                        continue
                    label = label_item.widget()
                    value = value_item.widget()
                    if not isinstance(label, QLabel):
                        continue
                    if not isinstance(value, (QAbstractSpinBox, QComboBox)):
                        continue
                    if not label.isVisible() or not value.isVisible():
                        continue
                    gap = value.x() - (label.x() + label.width())
                    if gap > LABEL_GAP_LIMIT:
                        offenders.append(
                            f"{title}: {label.text()[:34]!r} is {gap}px from "
                            f"its value")
        self.assertEqual(
            offenders, [],
            "the slack must go to a trailing column, not between a label "
            "and the field it names: " + "; ".join(offenders))

    def test_no_text_is_clipped_in_a_label(self):
        """"No text may ever be clipped or overflow its area." A label
        narrower than the text it holds is the clipped case."""
        from PyQt6.QtWidgets import QLabel

        offenders = []
        for title, window in self._windows():
            for label in window.findChildren(QLabel):
                text = label.text()
                if (not label.isVisible() or not text.strip()
                        or label.wordWrap() or "<" in text):
                    continue
                needed = label.fontMetrics().horizontalAdvance(text)
                if needed > label.width() + 2:
                    offenders.append(
                        f"{title}: {text[:34]!r} needs {needed}px, has "
                        f"{label.width()}px")
        self.assertEqual(offenders, [],
                         "clipped labels: " + "; ".join(offenders))


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
