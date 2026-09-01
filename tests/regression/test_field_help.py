"""The "?" next to each field, and the field -> documentation section link.

Embedded help has ~195 sections, one per field. A global "?" forces the
user to search which of them explains the field they are looking at; the
"?" next to the field delivers it. The link is derived by cross-referencing
the widget's `toolTip` (which already names the `.bemt` field) with the
documentation section that mentions that name -- no one maintains a third
list by hand.
"""
import unittest

try:
    from PyQt6.QtWidgets import QApplication, QPushButton
    _HAS_QT = True
except ImportError:                                   # pragma: no cover
    _HAS_QT = False

from tests import helpers


@unittest.skipUnless(_HAS_QT, "PyQt6 not installed")
class TestFieldMap(unittest.TestCase):
    def test_map_covers_most_of_the_schema_fields(self):
        from zbemt.gui.field_help import field_map
        from zbemt.bemt import BEMTConfig
        from zbemt.models import AirfoilDef

        mapping = field_map()
        target = set(BEMTConfig.__dataclass_fields__) | set(AirfoilDef.__dataclass_fields__)
        covered = target & set(mapping)
        self.assertGreater(len(covered) / len(target), 0.75,
                           f"only {len(covered)}/{len(target)} fields have a section")

    def test_every_anchor_of_the_map_exists_in_the_documentation(self):
        """A broken anchor would open documentation at the top without saying
        it failed -- worse than not having a button."""
        import re
        from zbemt import paths
        from zbemt.gui.field_help import field_map

        html = paths.documentation_path().read_text(encoding="utf-8")
        ids = set(re.findall(r'id="([\w-]+)"', html))
        broken = sorted({a for a in field_map().values() if a not in ids})
        self.assertEqual(broken, [])

    def test_central_fields_land_on_the_physics_not_the_field_table(self):
        """CURRENT contract (see `field_help`'s docstring): the
        `ajuda-{field}` row in the "Parameters by tab" table is the LAST resort,
        not the first.

        This test once asserted the opposite -- it required `ajuda-{field}` for
        these same fields --, which is a rule that `field_help` deliberately
        dropped: "Rule 3 was once FIRST -- and that's why every help link
        fell into a table cell instead of the physics section". A table cell
        repeats the tooltip; the user clicking "?" wants the section that
        explains the quantity.
        """
        from zbemt.gui.field_help import field_map
        mapping = field_map()
        for field in ("n_blades", "stall_model", "solver", "collective_deg"):
            self.assertFalse(
                mapping[field].startswith("ajuda-"),
                f"{field} fell into the field table ({mapping[field]}) instead of "
                "an explanation section")

    def test_r_norm_opens_its_own_section_not_the_exported_csv_one(self):
        """Audit F8: the bare key `r_norm` is cited both by §8.8.4 (the
        exported-CSV column list) and by its own §8.1.3 "Radial position
        of a section". The tie-break preferred the shorter export body,
        so the Airfoil tab's radial station opened the wrong section."""
        from zbemt.gui.field_help import field_anchor
        anchor = field_anchor("r_norm")
        self.assertEqual(anchor, "cap-3-1-3")
        self.assertNotEqual(anchor, "cap-3-8-3")


@unittest.skipUnless(_HAS_QT, "PyQt6 not installed")
class TestButtonsInTheWindow(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        import tempfile, shutil
        self._tmp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self._tmp, ignore_errors=True)
        with helpers.patch_message_box_everywhere("PROJECTS_ROOT", self._tmp):
            from zbemt.gui import app as gui
            self.win = gui.MainWindow()
        self.addCleanup(self.win.deleteLater)

    def _clickable_labels(self, tab_index):
        """QToolButtons that function as field labels (hand cursor)."""
        from PyQt6.QtCore import Qt
        from PyQt6.QtWidgets import QToolButton
        tab = self.win.tabs.widget(tab_index)
        return [b for b in tab.findChildren(QToolButton)
                if b.cursor().shape() == Qt.CursorShape.PointingHandCursor]

    def _block_buttons(self, tab_index):
        """Groupboxes whose TITLE opens the block help.

        It used to scan `QPushButton` with text "?" -- and that's why
        it was failing: there are no "?" buttons left in the window (see
        `field_help`'s docstring). Block help is now the `QGroupBox`'s
        title itself, set up by `common.make_block_title_clickable`,
        which marks the groupbox with `_block_help`. That marker
        identifies a block with help.
        """
        from PyQt6.QtWidgets import QGroupBox
        tab = self.win.tabs.widget(tab_index)
        return [gb for gb in tab.findChildren(QGroupBox)
                if getattr(gb, "_block_help", None) is not None]

    def test_physics_tabs_gain_clickable_labels(self):
        """Documented fields gain clickable QToolButton labels."""
        self.assertGreater(len(self._clickable_labels(2)), 15, "Airfoil tab has no clickable labels")
        self.assertGreater(len(self._clickable_labels(3)), 10, "Config/Motor tab has no clickable labels")

    def test_physics_tabs_gain_block_buttons(self):
        """Relevant groupboxes gain block '?' button."""
        self.assertGreater(len(self._block_buttons(2)), 3, "Airfoil tab has no block '?'")
        self.assertGreater(len(self._block_buttons(3)), 3, "Config/Motor tab has no block '?'")

    def test_flight_condition_gains_them_too(self):
        # Run Case has few editable fields with documented tooltips;
        # verify that at least some gained clickable label OR block button
        clickable = len(self._clickable_labels(4)) + len(self._block_buttons(4))
        self.assertGreaterEqual(clickable, 2, "Run Case tab has no interactive help")

    def test_the_label_follows_the_field_visibility(self):
        """Progressive disclosure hides the field; the clickable label must follow."""
        from PyQt6.QtCore import Qt
        from PyQt6.QtWidgets import QFormLayout, QToolButton
        tab = self.win.tabs.widget(2)  # Airfoil
        tab.stall_model_combo.setCurrentText("clip")
        tab.use_dynamic_stall.setChecked(True)
        field = tab.dyn_A

        # Find the QToolButton label in the same form row
        label_btn = None
        for form in tab.findChildren(QFormLayout):
            for r in range(form.rowCount()):
                fi = form.itemAt(r, QFormLayout.ItemRole.FieldRole)
                li = form.itemAt(r, QFormLayout.ItemRole.LabelRole)
                if fi and fi.widget() == field and li:
                    w = li.widget()
                    if isinstance(w, QToolButton):
                        label_btn = w
                        break
            if label_btn:
                break
        self.assertIsNotNone(label_btn, "dyn_A field without a QToolButton label")

        # Hide the row via progressive disclosure
        tab.use_dynamic_stall.setChecked(False)
        self.assertTrue(field.isHidden() or label_btn.isHidden(),
                        "field and label should be hidden")
        tab.use_dynamic_stall.setChecked(True)
        self.assertFalse(field.isHidden() and label_btn.isHidden(),
                         "field/label should be visible again")

    def test_install_is_idempotent(self):
        """Calling install_field_popups twice does not create duplicate labels."""
        from PyQt6.QtWidgets import QToolButton
        from zbemt.gui.field_help import install_field_popups
        tab = self.win.tabs.widget(3)
        before = len(self._clickable_labels(3))
        self.assertEqual(install_field_popups(tab), 0)
        self.assertEqual(len(self._clickable_labels(3)), before)


@unittest.skipUnless(_HAS_QT, "PyQt6 not installed")
class TestOpenHelpWithAnchor(unittest.TestCase):
    def test_url_receives_the_fragment(self):
        from unittest import mock
        from zbemt.gui import common
        with mock.patch.object(common, "QDesktopServices") as services:
            common.open_help(None, anchor="cap-3-2-1")
        url = services.openUrl.call_args[0][0]
        self.assertEqual(url.fragment(), "cap-3-2-1")
        self.assertTrue(url.toLocalFile().endswith("documentation.html"))

    def test_without_anchor_opens_at_the_top(self):
        from unittest import mock
        from zbemt.gui import common
        with mock.patch.object(common, "QDesktopServices") as services:
            common.open_help(None)
        self.assertEqual(services.openUrl.call_args[0][0].fragment(), "")


if __name__ == "__main__":
    unittest.main()


@unittest.skipUnless(_HAS_QT, "PyQt6 not installed")
class TestHelpDoesNotBreakProgressiveDisclosure(unittest.TestCase):
    """The "?" wraps the field in a container to fit the button next to it.
    This changes which widget is the FIELD in the form row -- and the code
    that hides the row searches for the original widget. Without care,
    `setRowVisible` fails to find the row and fails silently: the field
    stays on screen even when it shouldn't."""

    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def test_hiding_a_row_works_with_the_clickable_label(self):
        """Progressive disclosure must hide field AND its clickable label together."""
        import shutil, tempfile
        from PyQt6.QtWidgets import QFormLayout, QToolButton
        from zbemt import api
        tmp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, tmp, ignore_errors=True)
        with helpers.patch_message_box_everywhere("PROJECTS_ROOT", tmp):
            from zbemt.gui import app as gui
            win = gui.MainWindow()
        self.addCleanup(win.deleteLater)
        win.state.set_project(api.open_project("projects/test2"))

        tab = win.tabs.widget(5)                       # Run Batch
        field = tab.fixed_collective
        # What OCCUPIES the field column can be a wrapper of the field (Run
        # Batch indents simple spins to the column of composite field numbers).
        # `_help_container` is exactly the marker that
        # `common.set_row_visible` follows to find the row.
        occupant = getattr(field, "_help_container", None) or field

        # Find the QToolButton label of the same row
        label_btn = None
        for form in tab.findChildren(QFormLayout):
            for r in range(form.rowCount()):
                fi = form.itemAt(r, QFormLayout.ItemRole.FieldRole)
                li = form.itemAt(r, QFormLayout.ItemRole.LabelRole)
                if fi and fi.widget() == occupant and li:
                    w = li.widget()
                    if isinstance(w, QToolButton):
                        label_btn = w
                        break
            if label_btn:
                break
        self.assertIsNotNone(label_btn, "fixed_collective without a QToolButton label")

        slot_combo = tab.axis_rows[0][0]
        collective_index = [i for i, (_l, s) in enumerate(tab._AXIS_SLOTS)
                            if s == "collective_deg"][0]
        slot_combo.setCurrentIndex(collective_index)   # collective becomes AXIS -> row should vanish
        self.assertTrue(field.isHidden() or label_btn.isHidden(),
                        "fixed field stayed visible while being an axis")

        slot_combo.setCurrentIndex(0)                  # no axis -> row should come back
        self.assertFalse(field.isHidden() and label_btn.isHidden())
