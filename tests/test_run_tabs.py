"""Regressions of the Run Case (items 19/20) and Run Batch (items 22/23)
tabs.

Items reported by the user:

* 19 -- the results table's labels did not follow LaTeX: the symbol
  ``C<sub>T</sub>`` from `api.SUMMARY_SYMBOLS` was flattened to ``"C_T"``,
  and the tooltip with the spelled-out name, although written, never
  appeared (the event filter was on the `QTableWidget`, and Qt delivers
  the mouse to the viewport).
* 20 -- the configuration echo stayed hidden behind a checkbox.
* 22 -- the Run Batch "Fixed values" box had rows starting at different
  x positions and spinboxes stretching to the end of the window.
* 23 -- "replace queue" seemed to do nothing (it works, but clicking the
  checkbox produced no visible feedback).

The layout tests here do NOT lock down pixels (that ages badly): they
lock down the property the user complained about -- same label column for
all rows, same right edge on the fields, width-limited field, some
visible text announcing the "Replace queue" checkbox's effect, and the
four action buttons at a single width (Run wider than them).
"""
from __future__ import annotations

import unittest

try:
    from PyQt6.QtCore import QPoint, Qt
    from PyQt6.QtGui import QPixmap
    from PyQt6.QtWidgets import QApplication, QFormLayout, QStyleOptionViewItem
    _HAS_QT = True
except Exception:                                       # pragma: no cover
    _HAS_QT = False

from tests import helpers


def _sample_summary() -> dict:
    """Minimal summary with one key from each family (condition,
    subscripted coefficient, dimensional, and configuration echo)."""
    return {
        "mu_x": 0.2, "collective_deg": 8.0, "rpm": 600.0,
        "CT": 0.0051, "CQ": 0.00042, "Thrust": 1234.5,
        "convergence_pct": 100.0, "solver": "newton",
        "cfg_Ne": 8, "cfg_Npsi": 12, "cfg_solver": "newton",
    }


@unittest.skipUnless(_HAS_QT, "PyQt6 not installed")
class TestRunCaseResultsTable(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def _tab(self):
        from zbemt.gui.common import AppState
        from zbemt.gui.tabs.run_case import RunCaseTab
        state = AppState()
        state.project = helpers.make_studies_project()
        tab = RunCaseTab(state)
        self.addCleanup(tab.deleteLater)
        tab.show()
        tab._show_summary(_sample_summary())
        return tab

    # --- item 19: symbol in rich text -------------------------------

    def test_label_carries_the_symbol_in_html_for_the_delegate(self):
        """Before, the label's only data was ``"C_T"`` -- the subscript had
        been flattened and there was no way to recover it when painting."""
        from zbemt.gui.tabs.run_case import HTML_SYMBOL_ROLE
        tab = self._tab()
        labels = [tab.results_table.item(i, 0).text()
                  for i in range(tab.results_table.rowCount())]
        row = labels.index("C_T")
        item = tab.results_table.item(row, 0)
        # plain text stays in the display role (copy/paste and the rest
        # of the suite depend on it)
        self.assertEqual(item.text(), "C_T")
        self.assertEqual(item.data(HTML_SYMBOL_ROLE), "C<sub>T</sub>")

    def test_label_unit_also_comes_in_html(self):
        """``N&middot;m`` has to reach the rich document as an entity and
        the plain text as a character."""
        from zbemt.gui.tabs.run_case import HTML_SYMBOL_ROLE
        tab = self._tab()
        tab._show_summary({"Torque": 12.0})
        item = tab.results_table.item(1, 0)
        self.assertEqual(item.text(), "Q [N·m]")
        self.assertEqual(item.data(HTML_SYMBOL_ROLE), "Q [N&middot;m]")

    def test_group_header_has_no_html(self):
        """Header is plain bold text: with no HTML role, it falls back to
        the default delegate."""
        from zbemt.gui.tabs.run_case import HTML_SYMBOL_ROLE
        tab = self._tab()
        item = tab.results_table.item(0, 0)
        self.assertEqual(item.text(), "Flight condition")
        self.assertIsNone(item.data(HTML_SYMBOL_ROLE))

    def test_delegate_paints_the_subscript_without_the_plain_text(self):
        """The delegate has to actually paint (and not leave ``C_T``
        underneath): we compare the rendering of ``C<sub>T</sub>`` with
        that of the plain text ``C_T`` in the same rectangle -- they have
        to differ."""
        from zbemt.gui.tabs.run_case import _RichSymbolDelegate
        tab = self._tab()
        labels = [tab.results_table.item(i, 0).text()
                  for i in range(tab.results_table.rowCount())]
        row = labels.index("C_T")
        index = tab.results_table.model().index(row, 0)
        delegate = tab.results_table.itemDelegateForColumn(0)
        self.assertIsInstance(delegate, _RichSymbolDelegate)

        option = QStyleOptionViewItem()
        option.initFrom(tab.results_table)
        option.rect = tab.results_table.visualRect(index)
        self.assertTrue(option.rect.isValid())

        from PyQt6.QtGui import QPainter
        images = []
        for target in (index, tab.results_table.model().index(0, 0)):
            pix = QPixmap(option.rect.size())
            pix.fill(Qt.GlobalColor.white)
            painter = QPainter(pix)
            o = QStyleOptionViewItem(option)
            o.rect = pix.rect()
            delegate.paint(painter, o, target)
            painter.end()
            images.append(pix.toImage())
        # the symbol row and the header row cannot come out identical
        self.assertNotEqual(images[0], images[1])
        # and the symbol's rendering has to have painted pixels (not empty)
        img = images[0]
        painted = sum(1 for x in range(img.width()) for y in range(img.height())
                      if img.pixelColor(x, y) != Qt.GlobalColor.white)
        self.assertGreater(painted, 0, "the delegate did not paint anything")

    # --- item 19: instant tooltip ---------------------------------

    def test_tooltip_installed_on_the_viewport_not_the_widget(self):
        """Bug: the filter was on the `QTableWidget`. `QAbstractScrollArea`
        delivers Enter/MouseMove to the VIEWPORT, so with a real mouse the
        tooltip never appeared."""
        tab = self._tab()
        self.assertTrue(hasattr(tab.results_table.viewport(), "_instant_tooltip_filter"))
        self.assertFalse(hasattr(tab.results_table, "_instant_tooltip_filter"))

    def test_tooltip_carries_full_name_unit_and_key(self):
        tab = self._tab()
        labels = [tab.results_table.item(i, 0).text()
                  for i in range(tab.results_table.rowCount())]
        row = labels.index("C_T")
        y = tab.results_table.rowViewportPosition(row) + 2
        tooltip = tab._row_tooltip(QPoint(5, y))
        self.assertIn("Thrust coefficient", tooltip)     # spelled-out name
        self.assertIn("summary key: CT", tooltip)        # bridge to the CSV/report
        self.assertIn("C<sub>T</sub>", tooltip)

    def test_group_header_tooltip_is_none(self):
        tab = self._tab()
        y = tab.results_table.rowViewportPosition(0) + 2
        self.assertIsNone(tab._row_tooltip(QPoint(5, y)))

    # --- item 20: no configuration echo toggle --------------------

    def test_config_echo_always_visible(self):
        tab = self._tab()
        labels = [tab.results_table.item(i, 0).text()
                  for i in range(tab.results_table.rowCount())]
        self.assertIn("N_e", labels, "cfg_* should appear without any toggle")
        self.assertIn("Configuration echo (cfg_*)", labels)
        self.assertFalse(hasattr(tab, "show_cfg_check"),
                         "the config-echo toggle was removed (item 20)")


@unittest.skipUnless(_HAS_QT, "PyQt6 not installed")
class TestUnitCombosFollowPr2(unittest.TestCase):
    """An axis row's unit dropdown is progressive disclosure: hidden while
    the axis sits at "(none)", and alive (visible, populated, enabled) as
    soon as a quantity is chosen. PR-2 forbids the middle state this once
    had -- visible and empty."""

    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def _tab(self):
        from zbemt.gui.common import AppState
        from zbemt.gui.tabs.run_batch import RunBatchTab
        state = AppState()
        state.project = helpers.make_studies_project()
        tab = RunBatchTab(state)
        self.addCleanup(tab.deleteLater)
        tab.show()
        for _ in range(5):
            self.app.processEvents()
        return tab

    def test_unit_combo_hidden_until_slot_chosen_then_alive(self):
        tab = self._tab()
        slot, unit = tab.axis_rows[0][0], tab.axis_rows[0][1]
        if slot.currentIndex() == 0:   # "(none)"
            self.assertFalse(unit.isVisibleTo(tab),
                             "no quantity chosen: the unit row must stay hidden")
        slot.setCurrentIndex(1)
        self.app.processEvents()
        self.assertTrue(unit.isVisibleTo(tab))
        self.assertGreater(unit.count(), 0)
        self.assertTrue(unit.isEnabled())


@unittest.skipUnless(_HAS_QT, "PyQt6 not installed")
class TestRunBatchFixedValuesBox(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def _tab(self):
        from zbemt.gui.common import AppState
        from zbemt.gui.tabs.run_batch import RunBatchTab
        state = AppState()
        state.project = helpers.make_studies_project()
        tab = RunBatchTab(state)
        self.addCleanup(tab.deleteLater)
        tab.resize(1200, 900)
        tab.show()
        for _ in range(5):
            self.app.processEvents()
        return tab

    # --- item 22 -------------------------------------------------------

    def test_all_fixed_fields_are_in_the_field_column(self):
        """Bug: advance and axial went in as a SPANNING row (no label),
        starting at the margin, while Collective/RPM started in the field
        column -- hence the feeling that everything was misaligned.

        The contract is "each field occupies the FIELD column of a row
        with a label", not "the column's widget is the spin itself":
        Collective and RPM come in wrapped by `_with_unit_indent`
        (item 11/4), which indents them to the compound fields' number
        column. The wrapper is declared in `_help_container` -- the
        same mark that `common.set_row_visible` consults --, so
        that is what is asked when determining which widget represents
        the field.
        """
        tab = self._tab()
        form = tab._fixed_form
        fields = set()
        for r in range(form.rowCount()):
            item = form.itemAt(r, QFormLayout.ItemRole.FieldRole)
            label = form.itemAt(r, QFormLayout.ItemRole.LabelRole)
            self.assertIsNotNone(item, f"row {r} is still spanning (no label)")
            self.assertIsNotNone(label, f"row {r} has no label in the label column")
            fields.add(item.widget())
        expected = [tab.fixed_advance, tab.fixed_axial,
                    tab.fixed_collective, tab.fixed_rpm]
        in_column = [getattr(w, "_help_container", None) or w for w in expected]
        for widget, occupant in zip(expected, in_column):
            self.assertIn(occupant, fields,
                          f"{widget} is not in the form's field column")

        # same column: all fields start at the same x inside the box
        box = tab.fixed_advance.parentWidget()
        xs = {w.mapTo(box, w.rect().topLeft()).x() for w in in_column}
        self.assertEqual(len(xs), 1, f"fields starting at different x: {xs}")

    def test_the_simple_fields_indent_does_not_break_field_help(self):
        """The field column's widget is where `field_help` and
        `tools/field_index.py` read the `.bemt` field name from (via the
        tooltip). Wrapping the spin without carrying the tooltip along
        would silently drop Collective/RPM from the field index and from
        the row's "?" help."""
        from zbemt.gui.field_help import _widget_field

        tab = self._tab()
        for spin, expected in ((tab.fixed_collective, "collective_deg"),
                               (tab.fixed_rpm, "rpm"),
                               (tab.collective_spin, "collective_deg"),
                               (tab.rpm_spin, "rpm")):
            container = getattr(spin, "_help_container", None)
            self.assertIsNotNone(container, "simple field should be indented")
            self.assertEqual(_widget_field(container), expected)

    def test_numeric_fields_do_not_take_the_full_width(self):
        """"an enormous field to fill in (takes up the whole screen)": the
        spinbox grew with the form."""
        tab = self._tab()
        box = tab.fixed_advance.parentWidget()
        for widget in (tab.fixed_collective, tab.fixed_rpm,
                       tab.fixed_advance.spin, tab.fixed_axial.spin):
            self.assertLessEqual(widget.width(), tab._VALUE_WIDTH)
            self.assertLess(widget.width(), box.width() / 2)

    def test_hiding_a_fixed_row_still_works(self):
        """The box now has labels; `set_row_visible` still has to
        hide FIELD AND LABEL when the quantity becomes an axis."""
        tab = self._tab()
        collective_index = [i for i, (_l, s) in enumerate(tab._AXIS_SLOTS)
                            if s == "collective_deg"][0]
        tab.axis_rows[0][0].setCurrentIndex(collective_index)
        self.assertFalse(tab.fixed_collective.isVisible())
        self.assertTrue(tab.fixed_rpm.isVisible())
        tab.axis_rows[0][0].setCurrentIndex(0)
        self.assertTrue(tab.fixed_collective.isVisible())

    # --- item 23 -------------------------------------------------------

    def test_an_echo_announces_the_replace_checkbox_effect(self):
        """The "Replace queue" checkbox does nothing when clicked -- it
        only changes what the button will do afterward. With no
        immediate feedback it reads as broken (item 23).

        The announcement used to be in the button's text; with the
        button's label reduced to the action's name (item 5), it moved
        to the echo next to the checkbox. What the test locks down is
        the INVARIANT of item 23 -- clicking the checkbox instantly
        changes a visible text that says which of the two effects
        applies --, not where that text lives.
        """
        tab = self._tab()
        echo = tab.lbl_queue_effect
        self.assertTrue(echo.isVisible())
        self.assertIn("REPLACES", echo.text())
        tab.check_replace_queue.setChecked(False)
        self.assertIn("APPENDS", echo.text())
        tab.check_replace_queue.setChecked(True)
        self.assertIn("REPLACES", echo.text())

    def test_case_by_case_mode_hides_the_box_and_switches_the_button(self):
        tab = self._tab()
        tab.radio_list.setChecked(True)
        self.assertEqual(tab.mode_stack.currentIndex(), 1,
                         "checking the radio by code must also switch the panel")
        self.assertFalse(tab.check_replace_queue.isVisible())
        self.assertFalse(tab.lbl_queue_effect.isVisible(),
                         "without a checkbox there is no effect to announce")
        self.assertIn("Add Case", tab.btn_generate.text())

    def test_replace_and_accumulate_do_what_they_say(self):
        tab = self._tab()
        collective_index = [i for i, (_l, s) in enumerate(tab._AXIS_SLOTS)
                            if s == "collective_deg"][0]
        tab.axis_rows[0][0].setCurrentIndex(collective_index)
        tab.axis_rows[0][2].setText("4, 6, 8")

        tab._generate_cases()
        self.assertEqual(tab.batch_table.rowCount(), 3)
        tab._generate_cases()
        self.assertEqual(tab.batch_table.rowCount(), 3, "replace should replace")
        tab.check_replace_queue.setChecked(False)
        tab._generate_cases()
        self.assertEqual(tab.batch_table.rowCount(), 6, "append should accumulate")
        tab.check_replace_queue.setChecked(True)
        tab._generate_cases()
        self.assertEqual(tab.batch_table.rowCount(), 3)
        # the queue is still the single source of what runs
        self.assertEqual(len(tab._queue_conditions()), 3)


@unittest.skipUnless(_HAS_QT, "PyQt6 not installed")
class TestRunBatchModoDeExecucaoNaEtapa1(unittest.TestCase):
    """Item 12 -- the three run modes lived in step "3. Run", far from
    the fields they make (ir)relevant: it was possible to build an RPM
    axis and only later find out, three boxes below, that RPM was going
    to be RESOLVED by the trim loop and the whole axis would be
    ignored."""

    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def _tab(self):
        from zbemt.gui.common import AppState
        from zbemt.gui.tabs.run_batch import RunBatchTab
        state = AppState()
        state.project = helpers.make_studies_project()
        tab = RunBatchTab(state)
        self.addCleanup(tab.deleteLater)
        tab.resize(1200, 900)
        tab.show()
        for _ in range(5):
            self.app.processEvents()
        return tab

    def _box_title(self, widget):
        from PyQt6.QtWidgets import QGroupBox
        parent = widget.parentWidget()
        while parent is not None and not isinstance(parent, QGroupBox):
            parent = parent.parentWidget()
        return parent.title() if parent is not None else None

    def test_the_mode_selector_is_in_step_1(self):
        tab = self._tab()
        self.assertTrue(self._box_title(tab.run_mode_combo).startswith("1."))
        self.assertTrue(self._box_title(tab.trim_target_value).startswith("1."))

    def test_step_3_only_has_the_running(self):
        """Step 3 keeps what is actually about running: button, progress,
        cancel (and the echo of the mode chosen in step 1)."""
        tab = self._tab()
        self.assertTrue(self._box_title(tab.btn_run).startswith("3."))
        self.assertFalse(hasattr(tab, "batch_run_mode"))
        self.assertFalse(hasattr(tab, "batch_trim_dof"))
        self.assertFalse(hasattr(tab, "batch_trim_target"))

    def test_target_appears_only_when_there_is_trimming(self):
        tab = self._tab()
        self.assertFalse(tab.trim_target_value.isVisible())
        tab.run_mode_combo.setCurrentText("Fixed RPM, target thrust/CT")
        self.assertTrue(tab.trim_target_value.isVisible())
        self.assertTrue(tab.trim_target_kind_combo.isVisible())
        tab.run_mode_combo.setCurrentText("Fixed collective & RPM")
        self.assertFalse(tab.trim_target_value.isVisible())

    def test_the_resolved_quantity_stops_being_offered_as_fixed(self):
        """"solve collective" resolves the collective: it is OUTPUT, and
        cannot remain a case input field."""
        tab = self._tab()
        tab.run_mode_combo.setCurrentText("Fixed RPM, target thrust/CT")
        self.assertFalse(tab.fixed_collective.isVisible())
        self.assertTrue(tab.fixed_rpm.isVisible())
        self.assertFalse(tab.collective_spin.isVisible(), "case-by-case mode too")
        tab.run_mode_combo.setCurrentText("Fixed collective, target thrust/CT")
        self.assertTrue(tab.fixed_collective.isVisible())
        self.assertFalse(tab.fixed_rpm.isVisible())
        tab.run_mode_combo.setCurrentText("Fixed collective & RPM")
        self.assertTrue(tab.fixed_collective.isVisible())
        self.assertTrue(tab.fixed_rpm.isVisible())

    def test_the_resolved_quantity_stops_being_offered_as_axis(self):
        tab = self._tab()
        rpm_index = [i for i, (_l, s) in enumerate(tab._AXIS_SLOTS) if s == "rpm"][0]
        tab.axis_rows[0][0].setCurrentIndex(rpm_index)
        tab.axis_rows[0][2].setText("500, 600")
        tab.run_mode_combo.setCurrentText("Fixed collective, target thrust/CT")
        # the item disappears from the lists...
        self.assertFalse(tab.axis_rows[1][0].model().item(rpm_index).isEnabled())
        # ...and the axis that was already on it reverts to "(none)"
        self.assertEqual(tab.axis_rows[0][0].currentIndex(), 0)
        self.assertEqual(tab._active_axes(), [])

    def test_trim_spec_keeps_the_same_combinations_as_before(self):
        """GUI/.bemt/CLI parity: the dict handed to `studies.run_batch`
        is the same one as before the layout change."""
        tab = self._tab()
        self.assertIsNone(tab._trim_spec())
        tab.run_mode_combo.setCurrentText("Fixed RPM, target thrust/CT")
        tab.trim_target_kind_combo.setCurrentText("CT [-]")
        tab.trim_target_value.setValue(0.005)
        self.assertEqual(tab._trim_spec(), {"trim_mode": "solve_collective",
                                             "target_kind": "CT", "target_value": 0.005})
        tab.run_mode_combo.setCurrentText("Fixed collective, target thrust/CT")
        tab.trim_target_kind_combo.setCurrentText("Thrust [N]")
        tab.trim_target_value.setValue(1200.0)
        self.assertEqual(tab._trim_spec(), {"trim_mode": "solve_rpm",
                                             "target_kind": "thrust", "target_value": 1200.0})


@unittest.skipUnless(_HAS_QT, "PyQt6 not installed")
class TestRunBatchFaixaDosGeradores(unittest.TestCase):
    """Item 25 -- from/to/step did not track the axis's quantity: with
    "Disk angle (alpha / Vz)" + "alpha [deg]", the "fill" button wrote
    ``0, 0.1, ... 1`` -- advance ratio numbers, absurd as degrees."""

    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def _tab(self):
        from zbemt.gui.common import AppState
        from zbemt.gui.tabs.run_batch import RunBatchTab
        state = AppState()
        state.project = helpers.make_studies_project()
        tab = RunBatchTab(state)
        self.addCleanup(tab.deleteLater)
        tab.resize(1200, 900)
        tab.show()
        for _ in range(5):
            self.app.processEvents()
        return tab

    def _choose(self, tab, slot: str, unit: str | None = None):
        i = [k for k, (_l, s) in enumerate(tab._AXIS_SLOTS) if s == slot][0]
        tab.axis_rows[0][0].setCurrentIndex(i)
        if unit is not None:
            tab.axis_rows[0][1].setCurrentText(unit)
        return tab.axis_rows[0]

    def _fill(self, tab):
        _sc, _uc, values_edit = tab.axis_rows[0]
        tab._fill_axis_values(0)
        return [float(t) for t in values_edit.text().split(",") if t.strip()]

    def test_alpha_generates_degrees_not_advance_ratio(self):
        tab = self._tab()
        self._choose(tab, "axial", "alpha [deg]")
        values = self._fill(tab)
        self.assertGreaterEqual(max(values), 5.0,
                                f"0..1 degree is not a disk-angle sweep: {values}")
        self.assertLessEqual(max(values), 90.0)
        self.assertLessEqual(min(values), -1.0, "negative disk angle is the usual case")

    def test_rpm_generates_hundreds_not_tenths(self):
        tab = self._tab()
        self._choose(tab, "rpm")
        values = self._fill(tab)
        self.assertGreaterEqual(max(values), 100.0, f"RPM does not live in 0..1: {values}")

    def test_the_spin_range_follows_the_quantity(self):
        tab = self._tab()
        self._choose(tab, "axial", "alpha [deg]")
        _from_w, to_w, _step_w = tab._range_widgets(0)
        self.assertLessEqual(to_w.maximum(), 90.0, "alpha does not exceed 90 degrees")
        self._choose(tab, "rpm")
        _from_w, to_w, _step_w = tab._range_widgets(0)
        self.assertGreaterEqual(to_w.maximum(), 10000.0, "RPM needs thousands")

    def test_an_empty_slot_combo_does_not_become_the_last_slot(self):
        """`self._AXIS_SLOTS[combo.currentIndex()]` with currentIndex()==-1
        indexes backward and silently returns the LAST slot (RPM) -- an
        axis the user never chose.

        Reading the slot is exercised via `_slot_of_combo`, and NOT by
        calling `QComboBox.clear()` on a combo already wired to the tab's
        signals: that `clear()` crashes the process with a native failure
        (no Python exception) inside Qt itself, when emitting
        `currentIndexChanged(-1)` while the model is being emptied. It is
        Qt fragility in the signal path, not this tab's code -- and the
        GUI never empties this combo; the real -1 shows up through other
        paths. Reproducing the crash here would only kill the whole suite
        without covering anything more.
        """
        from PyQt6.QtWidgets import QComboBox

        tab = self._tab()
        empty = QComboBox()                     # loose: no signals wired
        self.assertEqual(empty.currentIndex(), -1)
        self.assertIsNone(tab._slot_of_combo(empty),
                          "empty combo defines no axis at all")
        # And an index outside the table does not accidentally become a
        # slot either.
        out_of_range = QComboBox()
        out_of_range.addItems([f"x{i}" for i in range(len(tab._AXIS_SLOTS) + 3)])
        out_of_range.setCurrentIndex(out_of_range.count() - 1)
        self.assertIsNone(tab._slot_of_combo(out_of_range))
        # The normal path still returns the right slot.
        sc, _uc, _ve = tab.axis_rows[0]
        rpm_index = [i for i, (_l, s) in enumerate(tab._AXIS_SLOTS) if s == "rpm"][0]
        sc.setCurrentIndex(rpm_index)
        self.assertEqual(tab._slot_of_combo(sc), "rpm")


@unittest.skipUnless(_HAS_QT, "PyQt6 not installed")
class TestRunBatchFieldAlignment(unittest.TestCase):
    """Item 11 -- the Advance/Axial flow/Collective/RPM rows ended at
    different x positions (the two compound ones carry the unit combo
    before the number). The test locks down the requested INVARIANT --
    same right edge --, never a width in pixels."""

    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def _tab(self):
        from zbemt.gui.common import AppState
        from zbemt.gui.tabs.run_batch import RunBatchTab
        state = AppState()
        state.project = helpers.make_studies_project()
        tab = RunBatchTab(state)
        self.addCleanup(tab.deleteLater)
        tab.resize(1200, 900)
        tab.show()
        for _ in range(5):
            self.app.processEvents()
        return tab

    def _right_edges(self, tab, fields):
        container = tab
        edges = set()
        for field in fields:
            spin = getattr(field, "spin", field)
            x = spin.mapTo(container, spin.rect().topRight()).x()
            edges.add(x)
        return edges

    def _left_edges(self, tab, fields):
        return {
            getattr(field, "spin", field).mapTo(
                tab, getattr(field, "spin", field).rect().topLeft()).x()
            for field in fields
        }

    # Solved by `RunBatchTab._with_unit_indent`: the simple fields
    # (Collective/RPM) come in wrapped, with a left margin equal to the
    # unit combo's width plus the compound fields' internal spacing, so
    # that the NUMBER of the four rows lands in the same column.
    # Indent, not widen: a spin wide enough to hit the compound fields'
    # edge would be the opposite defect -- see
    # `test_numeric_fields_do_not_take_the_full_width`.
    def test_right_edges_aligned_in_the_fixed_values(self):
        tab = self._tab()
        edges = self._right_edges(tab, [tab.fixed_advance, tab.fixed_axial,
                                        tab.fixed_collective, tab.fixed_rpm])
        self.assertEqual(len(edges), 1, f"right edges misaligned: {sorted(edges)}")
        lefts = self._left_edges(
            tab, [tab.fixed_advance, tab.fixed_axial,
                  tab.fixed_collective, tab.fixed_rpm])
        self.assertEqual(len(lefts), 1,
                         f"left edges misaligned: {sorted(lefts)}")

    # Same indent, in the case-by-case mode panel (see comment above).
    def test_right_edges_aligned_in_case_by_case(self):
        tab = self._tab()
        tab.radio_list.setChecked(True)
        for _ in range(5):
            self.app.processEvents()
        edges = self._right_edges(tab, [tab.add_row_advance, tab.add_row_axial,
                                        tab.collective_spin, tab.rpm_spin])
        self.assertEqual(len(edges), 1, f"right edges misaligned: {sorted(edges)}")

    def test_indented_fields_stay_narrow(self):
        """The indent is POSITION, not width: if one day it turns into a
        bigger `setFixedWidth`, the edges line up and this whole file
        stays green -- except here."""
        tab = self._tab()
        for spin in (tab.fixed_collective, tab.fixed_rpm,
                     tab.collective_spin, tab.rpm_spin):
            self.assertLessEqual(spin.width(), tab._VALUE_WIDTH)


@unittest.skipUnless(_HAS_QT, "PyQt6 not installed")
class TestRunCaseFieldAlignment(unittest.TestCase):
    """Run Case uses the same numeric column for the four controls."""

    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def test_right_edges_aligned(self):
        from zbemt.gui.common import AppState
        from zbemt.gui.tabs.run_case import RunCaseTab
        state = AppState()
        state.project = helpers.make_studies_project()
        tab = RunCaseTab(state)
        self.addCleanup(tab.deleteLater)
        tab.resize(900, 700)
        tab.show()
        for _ in range(5):
            self.app.processEvents()
        edges = {
            getattr(field, "spin", field).mapTo(
                tab, getattr(field, "spin", field).rect().topRight()).x()
            for field in (tab.advance, tab.axial, tab.collective_spin, tab.rpm_spin)
        }
        self.assertEqual(len(edges), 1,
                         f"right edges misaligned: {sorted(edges)}")
        lefts = {
            getattr(field, "spin", field).mapTo(
                tab, getattr(field, "spin", field).rect().topLeft()).x()
            for field in (tab.advance, tab.axial, tab.collective_spin, tab.rpm_spin)
        }
        self.assertEqual(len(lefts), 1,
                         f"left edges misaligned: {sorted(lefts)}")


@unittest.skipUnless(_HAS_QT, "PyQt6 not installed")
class TestRunBatchButtonWidths(unittest.TestCase):
    """Item 5 -- "these 4 buttons should have the same width and Run
    Cases should be bigger". The test locks down the requested RELATION
    (equal among themselves, Run bigger than them), never a width in
    pixels: the number depends on the font."""

    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def _tab(self):
        from zbemt.gui.common import AppState, ensure_button_legibility
        from zbemt.gui.tabs.run_batch import RunBatchTab
        state = AppState()
        state.project = helpers.make_studies_project()
        tab = RunBatchTab(state)
        self.addCleanup(tab.deleteLater)
        # The real window calls this after mounting the tab; without it
        # the test would not see the readability floor competing with
        # the common width.
        ensure_button_legibility(tab)
        tab.resize(1200, 900)
        tab.show()
        for _ in range(5):
            self.app.processEvents()
        return tab

    def test_the_four_action_buttons_have_the_same_width(self):
        tab = self._tab()
        widths = {b.width() for b in tab.action_buttons()}
        self.assertEqual(len(widths), 1,
                         "different widths: "
                         + str({b.text(): b.width() for b in tab.action_buttons()}))

    def test_run_is_wider_than_the_four(self):
        tab = self._tab()
        common_width = tab.btn_generate.width()
        self.assertGreater(tab.btn_run.width(), common_width)

    def test_run_stays_wider_with_a_full_queue(self):
        """The Run label grows with the count ("Run 12 case(s)"): the
        width is a minimum, not a fixed value that would elide the
        text."""
        tab = self._tab()
        collective_index = [i for i, (_l, s) in enumerate(tab._AXIS_SLOTS)
                            if s == "collective_deg"][0]
        tab.axis_rows[0][0].setCurrentIndex(collective_index)
        tab.axis_rows[0][2].setText("4, 6, 8, 10, 12")
        tab._generate_cases()
        for _ in range(5):
            self.app.processEvents()
        self.assertGreater(tab.btn_run.width(), tab.btn_generate.width())
        text_width = tab.btn_run.fontMetrics().horizontalAdvance(
            tab.btn_run.text())
        self.assertGreater(tab.btn_run.width(), text_width,
                           "Run label does not fit the button")

    def test_the_generate_button_keeps_its_width_across_modes(self):
        tab = self._tab()
        before = tab.btn_generate.width()
        tab.radio_list.setChecked(True)
        for _ in range(5):
            self.app.processEvents()
        self.assertEqual(tab.btn_generate.width(), before)


if __name__ == "__main__":
    unittest.main()


@unittest.skipUnless(_HAS_QT, "PyQt6 not installed")
class TestRunCaseAlignedWithTheSummary(unittest.TestCase):
    """Item 12: the Run Case table, the Results tab's table, and the HTML
    report must show the SAME quantities, in the SAME order.

    Before, this tab kept its own opinion on both things: its own order
    in "Condition" (mu_x, J_x, Vz, J_z, alpha...) and a REDUCED set -- a
    project in rotor mode saw no propeller coefficients, one in propeller
    mode saw neither FM nor the hub coefficients, and neither saw
    mu_x/J_x/mu_z/lambda_z. The engine always computes all of this; the
    report and the CSV always show all of this.
    """

    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def _tab(self, propeller: bool = False):
        from zbemt.gui.common import AppState
        from zbemt.gui.tabs.run_case import RunCaseTab
        state = AppState()
        project = helpers.make_studies_project()
        project.config["is_propeller"] = propeller
        state.project = project
        tab = RunCaseTab(state)
        self.addCleanup(tab.deleteLater)
        return tab

    def _shown_keys(self, tab, summary: dict) -> list:
        tab._show_summary(summary)
        return [k for k in tab._row_keys if k is not None]

    def _real_summary(self) -> dict:
        from zbemt import api
        from zbemt.models import FlightCondition
        project = helpers.make_studies_project()
        return api.run_case(project, FlightCondition(
            name="c", mu_x=0.15, Vz=3.0, collective_deg=8.0, rpm=1200.0)).summary

    def test_no_output_quantity_is_left_out(self):
        """"The SAME fields" on all three surfaces: everything that is
        not `cfg_*` shows up -- minus `rotor_rpm`, which is `rpm` again,
        and minus the angle of the OTHER convention: `alpha_rotor_deg`
        (measured from the disk plane) and `alpha_disk_deg` (measured
        from the shaft) describe the same condition in mutually exclusive
        references -- the engine always computes both, but only one
        makes physical sense per mode (rotor shows alpha_rotor, propeller
        shows alpha_disk), and that is how `nomenclature._SLOT_LABELS`
        treats the pair too."""
        from zbemt import api
        summary = self._real_summary()
        expected_base = {k for k in summary
                         if not k.startswith("cfg_") and k != "rotor_rpm"}
        for propeller in (False, True):
            with self.subTest(propeller=propeller):
                irrelevant = "alpha_rotor_deg" if propeller else "alpha_disk_deg"
                expected = expected_base - {irrelevant}
                shown = set(self._shown_keys(self._tab(propeller), summary))
                self.assertEqual(expected - shown, set())
        self.assertTrue(expected_base <= set(api.SUMMARY_PRIMARY_KEYS))

    def test_order_within_each_group_follows_the_summary(self):
        """The grouping is this tab's decision (and the group order
        changes between rotor and propeller), but the order WITHIN each
        group is that of `api.SUMMARY_PRIMARY_KEYS` -- otherwise there
        would again be two opinions."""
        from zbemt import api
        from zbemt.gui.tabs.run_case import RunCaseTab
        primary_index = {k: i for i, k in enumerate(api.SUMMARY_PRIMARY_KEYS)}
        for propeller in (False, True):
            for title, keys in RunCaseTab._build_groups(propeller):
                with self.subTest(propeller=propeller, group=title):
                    indices = [primary_index[k] for k in keys if k in primary_index]
                    self.assertEqual(indices, sorted(indices))

    def test_condition_opens_with_the_x_component_and_without_repeats(self):
        """x first (the PRIMARY one in both modes), then z, then the
        angles. And each quantity ONCE: `mu_x`/`J_x` used to appear
        twice while the engine had two keys for the same number. The
        cyclic harmonics sit beside the collective since SC-11 gave the
        condition its own 1/rev pitch controls; the SC-14 perturbation
        inputs (sideslip, hub rates) close the block."""
        from zbemt.gui.tabs.run_case import RunCaseTab
        keys = dict(RunCaseTab._build_groups(False))["Flight condition"]
        self.assertEqual(
            keys,
            ["mu_x", "J_x", "Vx",
             "mu_z", "J_z", "Vz", "lambda_z",
             "alpha_rotor_deg", "alpha_disk_deg",
             "collective_deg", "cyclic_c_deg", "cyclic_s_deg",
             "rpm",
             "sideslip_deg", "p_rate_deg_s", "q_rate_deg_s"])
        self.assertEqual(len(keys), len(set(keys)), "repeated quantity")

    def test_inflow_triad_has_its_own_group(self):
        """lambda_i / lambda / v_i / V_z did not exist in this table."""
        from zbemt.gui.tabs.run_case import RunCaseTab
        grupos = dict(RunCaseTab._build_groups(False))
        self.assertEqual(grupos["Inflow (solved)"],
                          ["lambda_i", "lambda_total", "Vi", "Vz_total"])


@unittest.skipUnless(_HAS_QT, "PyQt6 not installed")
class TestRunCaseSavedCaseButtons(unittest.TestCase):
    """Item 6: the Saved Cases buttons were "+ Save Current" and
    "- Remove" -- the graphic sign adds nothing to the verb, and
    "Current" repeats what the button already does by being on this
    tab."""

    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def test_buttons_are_save_and_remove(self):
        from zbemt.gui.common import AppState
        from zbemt.gui.tabs.run_case import RunCaseTab
        from PyQt6.QtWidgets import QPushButton
        state = AppState()
        state.project = helpers.make_studies_project()
        tab = RunCaseTab(state)
        self.addCleanup(tab.deleteLater)
        texts = {b.text() for b in tab.findChildren(QPushButton)}
        self.assertIn("Save", texts)
        self.assertIn("Remove", texts)
        self.assertNotIn("+ Save Current", texts)
        self.assertNotIn("- Remove", texts)
