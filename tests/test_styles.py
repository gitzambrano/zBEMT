"""Regression guard for `zbemt/gui/styles.py`.

Any QSS rule targeting `QCheckBox`/`QRadioButton` (even just `spacing`)
strips the native style (Fusion) of the indicator drawing and requires
the QSS to draw ALL sub-parts -- without an explicit ``::indicator``
rule with a border, the unchecked square vanishes completely. Seen on
screen: no unchecked checkbox in the GUI had a visible square.
"""
import re
import unittest

from tests.helpers import HAS_QT

# Reads the GUI stylesheet: without Qt there is nothing to check, and the CI
# job that installs the base dependencies only (to prove the engine runs
# without Qt) must see this module SKIPPED, not a collection error.
if not HAS_QT:                                   # pragma: no cover
    raise unittest.SkipTest("PyQt6 is not installed (the engine and CLI run "
                            "without it on purpose)")

from zbemt.gui import styles


class TestCheckboxIndicatorIsVisible(unittest.TestCase):
    def test_unchecked_indicator_has_an_explicit_border_and_size(self):
        css = styles.APP_QSS
        block = re.search(
            r"QCheckBox::indicator,\s*QRadioButton::indicator\s*\{([^}]*)\}", css)
        self.assertIsNotNone(block, "QSS has no QCheckBox::indicator rule")
        body = block.group(1)
        self.assertIn("border:", body)
        self.assertIn("width:", body)
        self.assertIn("height:", body)

    def test_checked_indicator_has_a_distinct_fill_colour(self):
        css = styles.APP_QSS
        self.assertIn("QCheckBox::indicator:checked", css)
        self.assertIn("QRadioButton::indicator:checked", css)


class TestControlArrowsExist(unittest.TestCase):
    """Same pitfall as the checkbox indicator above, in two other controls:
    any QSS rule on `QComboBox`/`QSpinBox` strips Fusion of the sub-part
    drawing. Seen on screen: NO dropdown in the GUI had an arrow (every
    combo looked indistinguishable from a QLineEdit) and the spinbox step
    buttons came out as a broken glyph shaped like a bracket.

    The triangle via CSS border doesn't work -- Qt paints a rectangle.
    The arrows are SVGs in `zbemt/gui/assets/`, and their existence on
    disk is what this test guards: a `url()` pointing to a non-existent
    file fails in SILENCE (the arrow disappears, the QSS doesn't complain)."""

    def test_combo_and_spinbox_declare_an_arrow_image(self):
        css = styles.APP_QSS
        for rule in ("QComboBox::down-arrow",
                      "QSpinBox::up-arrow", "QSpinBox::down-arrow",
                      "QDoubleSpinBox::up-arrow", "QDoubleSpinBox::down-arrow"):
            self.assertIn(rule, css, f"QSS has no {rule} rule")
        self.assertIn("image: url(", css)

    def test_every_svg_referenced_by_qss_exists_on_disk(self):
        from pathlib import Path

        references = re.findall(r"image:\s*url\(([^)]+)\)", styles.APP_QSS)
        self.assertTrue(references, "QSS has no `image: url(...)` rule")
        missing = [reference for reference in references if not Path(reference).is_file()]
        self.assertEqual(missing, [], f"Missing arrow SVG(s): {missing}")


class TestMessageBoxButtonsAreNotClipped(unittest.TestCase):
    """Bug: `QMessageBox QPushButton { max-width: none; }` -- Qt doesn't
    handle "none" well for this property and instead of removing the limit,
    it collapsed ALL sibling buttons to a uniform width smaller than the
    text itself (reproduced: "Discard"/"Cancel" cut to ~69px needing
    84/72px). See comment in `styles.py`."""

    @classmethod
    def setUpClass(cls):
        from PyQt6.QtWidgets import QApplication
        cls.app = QApplication.instance() or QApplication([])
        cls.app.setStyle("Fusion")
        cls.app.setStyleSheet(styles.APP_QSS)

    def test_every_confirmation_button_fits_its_text(self):
        from PyQt6.QtWidgets import QMessageBox, QPushButton
        from PyQt6.QtGui import QFontMetrics

        mb = QMessageBox()
        mb.setText("There is unsaved work:")
        mb.setStandardButtons(
            QMessageBox.StandardButton.Save
            | QMessageBox.StandardButton.Discard
            | QMessageBox.StandardButton.Cancel
        )
        mb.setDefaultButton(QMessageBox.StandardButton.Save)
        mb.show()
        self.app.processEvents()
        try:
            buttons = mb.findChildren(QPushButton)
            self.assertTrue(buttons)
            for button in buttons:
                text_width = QFontMetrics(button.font()).horizontalAdvance(button.text())
                self.assertGreaterEqual(
                    button.width(), text_width,
                    f"button {button.text()!r} clipped: width={button.width()}px, text needs {text_width}px")
        finally:
            mb.close()


class TestNoGuiButtonClipsItsOwnText(unittest.TestCase):
    """Bug: `QPushButton { max-width: 360px; }` -- Qt clamps the computed
    sizeHint to this limit (not just a layout ceiling), so any real button
    with longer text gets cut off. Found when instantiating the real tabs:
    "Check airfoil (live preview on the right)" (Airfoil) needs ~492px and
    got 390px. Scans every visible QPushButton in each tab, not just the
    case found -- to catch the next long label before it becomes a bug
    again."""

    @classmethod
    def setUpClass(cls):
        from PyQt6.QtWidgets import QApplication
        cls.app = QApplication.instance() or QApplication([])
        cls.app.setStyle("Fusion")
        cls.app.setStyleSheet(styles.APP_QSS)

    def test_every_visible_pushbutton_fits_its_text(self):
        from PyQt6.QtWidgets import QPushButton
        from PyQt6.QtGui import QFontMetrics
        from zbemt.gui.common import AppState
        from zbemt.gui.tabs.config import ConfigMotorTab
        from zbemt.gui.tabs.airfoil import AirfoilTab
        from zbemt.gui.tabs.geometry_tab import GeometryTab
        from zbemt.gui.tabs.run_case import RunCaseTab
        from zbemt.gui.tabs.run_batch import RunBatchTab
        from zbemt.gui.tabs.project import ProjectTab

        state = AppState()
        tabs = {
            "Project": ProjectTab(state),
            "Geometry": GeometryTab(state),
            "Airfoil": AirfoilTab(state),
            "Config": ConfigMotorTab(state),
            "Run Case": RunCaseTab(state),
            "Run Batch": RunBatchTab(state),
        }
        clipped = []
        for name, tab in tabs.items():
            tab.resize(1400, 900)
            tab.show()
            self.app.processEvents()
            for button in tab.findChildren(QPushButton):
                text = button.text()
                if not text or len(text) <= 1:
                    continue  # help "?" buttons: 1 character, never cut
                text_width = QFontMetrics(button.font()).horizontalAdvance(text)
                if button.sizeHint().width() < text_width:
                    clipped.append((name, text, button.sizeHint().width(), text_width))
            tab.close()
        self.assertEqual(
            clipped, [],
            f"Clipped button(s) (width < required text): {clipped}")


if __name__ == "__main__":
    unittest.main()
