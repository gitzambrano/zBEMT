"""Verify that no label in the GUI shows its own markup (`PR-4`).

`nomenclature.to_html` emits entities (``&gamma;``) and tags
(``&delta;<sub>3</sub>``). Two Qt behaviors turn that into visible
garbage, and both were on screen at once:

* a `QAbstractButton` always reads ``&`` as a mnemonic, so ``&gamma;``
  reached the screen as ``gamma;`` with the g underlined, and it never
  renders HTML, so ``<sub>`` showed verbatim;
* a `QLabel` on `AutoText` decides by looking for a TAG, so a label whose
  only markup is an entity was classified as plain text and printed the
  entity.

The earlier test for this checked ONE synthetic label, which is why the
defect survived on the real screens. This walks every tab and every Tools
window and reads what each label actually PAINTS.
"""
import re
import unittest

from tests.helpers import HAS_QT

if not HAS_QT:                                    # pragma: no cover
    raise unittest.SkipTest("PyQt6 is not installed")

from PyQt6.QtWidgets import QApplication, QLabel, QAbstractButton, QFormLayout
from PyQt6.QtCore import Qt


#: What must never survive into painted text.
_LEAK = re.compile(r"&[a-zA-Z]+;|&#\d+;|</?(?:sub|sup|b|i)>")


#: What `Qt::mightBeRichText` looks for: a '<' that opens something. An
#: ENTITY alone does not qualify, which is the whole trap.
_LOOKS_LIKE_A_TAG = re.compile(r"<[a-zA-Z!/]")


def _painted(widget) -> str:
    """What the widget actually draws, not what was handed to it.

    `AutoText` is the subtle case: Qt calls `mightBeRichText`, which
    decides by looking for a TAG. A label carrying `<sub>` renders, and a
    label whose only markup is `&#9888;` or `&gamma;` does not. Treating
    all of AutoText as leaking would flag every `<b>Heading</b>` in the
    app; treating none of it as leaking is how the real defect hid.
    """
    doc = getattr(widget, "_doc", None)
    if doc is not None:                # `_RichToolButton` paints this
        return doc.toPlainText()

    if isinstance(widget, QLabel):
        fmt = widget.textFormat()
        if fmt == Qt.TextFormat.RichText:
            return ""                  # Qt parses entities and tags alike
        text = widget.text()
        if fmt == Qt.TextFormat.AutoText and _LOOKS_LIKE_A_TAG.search(text):
            return ""                  # detected as rich text, so it renders
        return text

    # A plain button never renders markup, and reads `&` as a mnemonic.
    return widget.text() if hasattr(widget, "text") else ""


class TestNoLabelShowsItsOwnMarkup(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls._app = QApplication.instance() or QApplication([])
        from zbemt.gui.app import MainWindow

        cls.window = MainWindow()
        cls.window.show()

    def _offenders(self, root):
        """Every QLabel and every button, not only the form labels.

        Scoping this to `QFormLayout` label rows is what let the Run Case
        findings strip through: it is a loose `QLabel`, it joins its
        findings with `<br>`, and with a SINGLE finding there was no tag
        for `AutoText` to notice, so `&#9888;` was painted verbatim."""
        found = []
        for label in root.findChildren(QLabel):
            text = _painted(label)
            if _LEAK.search(text):
                found.append(text)
        for button in root.findChildren(QAbstractButton):
            text = _painted(button)
            if _LEAK.search(text):
                found.append(text)
        return found

    def test_every_tab_of_the_main_window(self):
        for i in range(self.window.tabs.count()):
            tab = self.window.tabs.widget(i)
            with self.subTest(tab=self.window.tabs.tabText(i)):
                self.assertEqual(self._offenders(tab), [],
                                  "these labels paint their own markup")

    def test_every_tools_window(self):
        from zbemt.gui.tabs.designer_window import GeometryDesignerWindow
        from zbemt.gui.tabs.optimizer_window import OptimizerWindow
        from zbemt.gui.tabs.stability_window import StabilityWindow
        from zbemt.gui.tabs.transient_window import TransientWindow

        for title, klass in (("Geometry Designer", GeometryDesignerWindow),
                              ("Design Optimization", OptimizerWindow),
                              ("Stability", StabilityWindow),
                              ("Transient", TransientWindow)):
            window = klass(self.window.state)
            window.show()
            QApplication.processEvents()
            with self.subTest(window=title):
                self.assertEqual(self._offenders(window), [],
                                  "these labels paint their own markup")
            window.hide()

    def test_the_blade_dynamics_rows_that_only_a_flapping_blade_reveals(self):
        """The flap rows carry most of the mathematics in the GUI, and
        progressive disclosure hides them while the model is Rigid, so a
        sweep of the default screen never reached them."""
        from zbemt.gui.tabs.geometry_tab import GeometryTab

        tab = next(self.window.tabs.widget(i)
                    for i in range(self.window.tabs.count())
                    if isinstance(self.window.tabs.widget(i), GeometryTab))
        tab.show()
        for mode in ("offset", "spring", "offset_spring"):
            index = tab.dyn_flap_model.findData(mode)
            tab.dyn_flap_model.setCurrentIndex(index)
            tab.dyn_lag_enabled.setChecked(True)
            QApplication.processEvents()
            with self.subTest(flap_model=mode):
                self.assertEqual(self._offenders(tab), [],
                                  "these labels paint their own markup")


class TestNoTableHeadingIsClipped(unittest.TestCase):
    """House rule: no text may ever be clipped or overflow its area.

    `QHeaderView.ResizeMode.Stretch` divides the width EQUALLY over the
    columns and ignores what each heading says, so a table with many
    columns, or with one long unit, cut its own headings. Three tables
    were in that state at once, the worst losing 104 px of "RPM
    [rev/min]". Qt's own `sectionSizeHint` is the measure: a section
    narrower than its hint is painting an ellipsis.
    """

    @classmethod
    def setUpClass(cls):
        cls._app = QApplication.instance() or QApplication([])
        from zbemt.gui.app import MainWindow

        cls.window = MainWindow()
        cls.window.resize(1600, 1000)
        cls.window.show()

    def _clipped(self, root):
        from PyQt6.QtWidgets import QTableWidget

        found = []
        for table in root.findChildren(QTableWidget):
            header = table.horizontalHeader()
            for column in range(table.columnCount()):
                item = table.horizontalHeaderItem(column)
                if item is None:
                    continue
                actual = header.sectionSize(column)
                hint = header.sectionSizeHint(column)
                if actual > 0 and hint > actual:
                    found.append(f"{item.text()!r} has {actual}px, needs {hint}px")
        return found

    def test_every_tab_of_the_main_window(self):
        for i in range(self.window.tabs.count()):
            tab = self.window.tabs.widget(i)
            with self.subTest(tab=self.window.tabs.tabText(i)):
                self.assertEqual(self._clipped(tab), [])

    def test_every_tools_window(self):
        from zbemt.gui.tabs.designer_window import GeometryDesignerWindow
        from zbemt.gui.tabs.optimizer_window import OptimizerWindow
        from zbemt.gui.tabs.stability_window import StabilityWindow
        from zbemt.gui.tabs.transient_window import TransientWindow

        for title, klass in (("Geometry Designer", GeometryDesignerWindow),
                              ("Design Optimization", OptimizerWindow),
                              ("Stability", StabilityWindow),
                              ("Transient", TransientWindow)):
            window = klass(self.window.state)
            window.resize(1500, 900)
            window.show()
            QApplication.processEvents()
            with self.subTest(window=title):
                self.assertEqual(self._clipped(window), [])
            window.hide()


def tearDownModule():
    if not HAS_QT:                                # pragma: no cover
        return
    app = QApplication.instance()
    if app is not None:
        app.processEvents()


if __name__ == "__main__":
    unittest.main()
