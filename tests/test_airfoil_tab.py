"""Regressions in the Airfoil tab and geometry generation dialog.

Covers issues reported by the user: alpha range of preview (item 6),
canvas control bar (item 8), sections panel always visible (item 9),
Reynolds/Mach suggestion (item 15), legend by condition (item 32), and
editable number of blades/radius in the dialog (item 2).
"""
import unittest

import numpy as np

from tests.helpers import HAS_QT

# Every test here drives real widgets, so without Qt there is nothing to
# check -- and the CI job that installs the base dependencies only (to prove
# the engine runs without Qt) must see this module SKIPPED, not a collection
# error saying the engine needs Qt.
if not HAS_QT:                                   # pragma: no cover
    raise unittest.SkipTest("PyQt6 is not installed (the engine and CLI run "
                            "without it on purpose)")

from PyQt6.QtWidgets import QApplication, QDoubleSpinBox, QLineEdit, QComboBox, QCheckBox
from PyQt6.QtCore import Qt

from zbemt import airfoils, geometry
from zbemt.models import PolarSlice, AirfoilDef, FlightCondition
from zbemt.gui.common import AppState
from zbemt.gui.dialogs import GeometryGeneratorDialog
from zbemt.gui.tabs.airfoil import AirfoilTab
from zbemt.gui.tabs.geometry_tab import GeometryTab

from tests.helpers import make_studies_project, patch_message_box_everywhere


#: Kept alive at module scope -- QApplication.instance() only survives
#: between calls if something holds a reference to the object. Every
#: other GUI test file stashes it on the TestCase class (cls.app); this
#: file's tests are plain functions, so a module global does the same
#: job. Without it, the QApplication gets garbage-collected right after
#: _app() returns and Qt aborts the process on the next QWidget().
_QAPP = None


def _app() -> QApplication:
    global _QAPP
    _QAPP = QApplication.instance() or QApplication([])
    return _QAPP


def _tab_with_project(**airfoil_kwargs):
    """Create an AirfoilTab with a loaded project (the state where
    the user actually uses the tab)."""
    _app()
    state = AppState()
    project = make_studies_project()
    for k, v in airfoil_kwargs.items():
        setattr(project.airfoil, k, v)
    state.project = project
    tab = AirfoilTab(state)
    state.notify_airfoil()
    return tab, state


def _spans(tab) -> list:
    """(min, max) alpha of each curve the preview would draw."""
    d = tab._collect_airfoil_def()
    return [(float(np.min(c["alpha_deg"])), float(np.max(c["alpha_deg"])))
            for c in tab._collect_polar_curves(d)]


class PreviewAlphaRange(unittest.TestCase):
    """Item 6: with Viterna extension active, the curve must be
    CALCULATED to ±180 -- rescaling the axis via matplotlib's bar does
    not recalculate anything, and the user saw an empty plot after 30°."""

    def test_viterna_on_draws_up_to_180(self):
        tab, _ = _tab_with_project(stall_model="viterna")
        self.assertEqual(tab.alpha_range_combo.currentText(), tab._RANGE_FULL)
        for lo, hi in _spans(tab):
            self.assertAlmostEqual(lo, -180.0)
            self.assertAlmostEqual(hi, 180.0)

    def test_without_viterna_stays_in_the_typical_range(self):
        tab, _ = _tab_with_project(stall_model="clip")
        self.assertEqual(tab.alpha_range_combo.currentText(), tab._RANGE_TYPICAL)
        for lo, hi in _spans(tab):
            self.assertAlmostEqual(lo, -30.0)
            self.assertAlmostEqual(hi, 30.0)

    def test_enabling_viterna_live_opens_the_range(self):
        tab, _ = _tab_with_project(stall_model="clip")
        tab.stall_model_combo.setCurrentText("viterna")
        self.assertEqual(tab.alpha_range_combo.currentText(), tab._RANGE_FULL)
        self.assertAlmostEqual(_spans(tab)[0][1], 180.0)

    def test_explicit_user_choice_wins(self):
        tab, _ = _tab_with_project(stall_model="clip")
        # simulates the user choosing in the combo (`activated` signal)
        tab.alpha_range_combo.setCurrentText(tab._RANGE_TYPICAL)
        tab.alpha_range_combo.activated.emit(0)
        tab.stall_model_combo.setCurrentText("viterna")
        self.assertEqual(tab.alpha_range_combo.currentText(), tab._RANGE_TYPICAL)


class CanvasControlBar(unittest.TestCase):
    """Item 8: plot controls moved from the left form to a bar above
    the canvas; they must remain (a) connected and (b) without dirtying
    the project."""

    def test_controls_are_no_longer_in_the_left_form(self):
        tab, _ = _tab_with_project()
        # the left form is the widget inside the splitter's QScrollArea
        left_form = tab._airfoil_left_widget
        for w in (tab.alpha_range_combo, tab.autoscale_y_check,
                  tab.show_reverse_branch_check, tab.mach_compare_edit):
            self.assertFalse(left_form.isAncestorOf(w),
                             f"{w} is still inside the left form")

    def test_checkboxes_checked_by_default(self):
        tab, _ = _tab_with_project()
        self.assertTrue(tab.autoscale_y_check.isChecked())
        self.assertTrue(tab.show_reverse_branch_check.isChecked())

    def test_reverse_branch_shown_by_default_in_curves(self):
        tab, _ = _tab_with_project()
        labels = [c["label"] for c in tab._collect_polar_curves(tab._collect_airfoil_def())]
        self.assertTrue(any("reverse flow" in r for r in labels), labels)

    def test_plot_controls_do_not_dirty_the_project(self):
        tab, _ = _tab_with_project()
        tab._clear_dirty()
        tab.autoscale_y_check.setChecked(False)
        tab.show_reverse_branch_check.setChecked(False)
        tab.alpha_range_combo.setCurrentText(tab._RANGE_FULL)
        tab.mach_compare_edit.setText("0.0, 0.2")
        tab.mach_compare_edit.editingFinished.emit()
        self.assertFalse(tab._dirty)

    def test_plot_controls_stay_connected_to_the_redraw(self):
        """The trap of item 8: moved out of `left_widget`, they lose the
        generic connections made by findChildren."""
        tab, _ = _tab_with_project()
        tab._preview_timer.stop()
        tab.autoscale_y_check.setChecked(False)
        self.assertTrue(tab._preview_timer.isActive())
        tab._preview_timer.stop()
        tab.show_reverse_branch_check.setChecked(False)
        self.assertTrue(tab._preview_timer.isActive())
        tab._preview_timer.stop()
        tab.alpha_range_combo.setCurrentText(tab._RANGE_FULL)
        self.assertTrue(tab._preview_timer.isActive())

    def test_comparative_visualization_group_is_gone_from_the_form(self):
        tab, _ = _tab_with_project()
        titles = [b.title() for b in tab.findChildren(type(tab.table_box))]
        self.assertNotIn("Comparative Visualization", titles)


class SectionsPanel(unittest.TestCase):
    """Item 9: the sections list also exists in single-airfoil mode."""

    def test_list_visible_with_a_single_all_row(self):
        tab, _ = _tab_with_project(name="airfoil X")
        self.assertTrue(tab.sections_list.isVisibleTo(tab))
        self.assertEqual(tab.sections_list.count(), 1)
        self.assertIn("r/R=all", tab.sections_list.item(0).text())
        self.assertIn("airfoil X", tab.sections_list.item(0).text())

    def test_r_norm_row_stays_hidden_in_single_mode(self):
        tab, _ = _tab_with_project()
        for w in tab._section_r_row_widgets:
            self.assertFalse(w.isVisibleTo(tab))

    def test_selecting_the_synthetic_row_does_not_switch_section(self):
        tab, _ = _tab_with_project()
        tab.sections_list.setCurrentRow(0)
        self.assertEqual(tab._current_section_index, -1)
        self.assertEqual(tab._sections, [])

    def test_adding_a_section_switches_to_multi(self):
        tab, _ = _tab_with_project()
        tab._add_section()
        self.assertEqual(len(tab._sections), 2)
        self.assertEqual(tab.sections_list.count(), 2)
        self.assertTrue(all(w.isVisibleTo(tab) for w in tab._section_r_row_widgets))

    def test_removing_returns_to_the_single_row(self):
        tab, _ = _tab_with_project()
        tab._add_section()
        tab._remove_section()
        tab._remove_section()
        self.assertEqual(tab._sections, [])
        self.assertEqual(tab.sections_list.count(), 1)
        self.assertIn("r/R=all", tab.sections_list.item(0).text())


class ReynoldsAndMachSuggestion(unittest.TestCase):
    """Item 15: closed-form estimate, without running the engine."""

    def test_three_increasing_re_and_mach_values(self):
        geom = geometry.generate_tapered(root_chord_norm=0.10, tip_chord_norm=0.04,
                                          radius_m=2.0, n_stations=12)
        s = airfoils.suggest_reynolds_mach_lists(geom, rpm=600.0)
        self.assertEqual(len(s["reynolds"]), 3)
        self.assertEqual(len(s["mach"]), 3)
        self.assertEqual(s["reynolds"], sorted(s["reynolds"]))
        self.assertEqual(s["mach"], sorted(s["mach"]))

    def test_matches_the_closed_form_at_the_reference_station(self):
        geom = geometry.generate_rectangular(chord_norm=0.08, radius_m=1.5, n_stations=11)
        rpm, nu, a = 900.0, 1.46e-5, 340.294
        s = airfoils.suggest_reynolds_mach_lists(geom, rpm=rpm, nu_air=nu, a_sound=a)
        omega = rpm * 2 * np.pi / 60.0
        U = omega * 1.5 * airfoils.REFERENCE_RADIUS_NORM
        expected_re = U * (0.08 * 1.5) / nu
        # the list is rounded to 2 significant digits
        self.assertTrue(any(abs(v - expected_re) / expected_re < 0.05 for v in s["reynolds"]),
                        (s["reynolds"], expected_re))
        self.assertAlmostEqual(s["mach"][1], round(U / a, 2), places=2)

    def test_degenerate_geometry_does_not_raise(self):
        empty = airfoils.suggest_reynolds_mach_lists(None, rpm=600.0)
        self.assertEqual(empty, {"reynolds": [], "mach": []})

    def test_suggestion_keeps_three_stations_even_with_rounding(self):
        geom = geometry.generate_rectangular(chord_norm=0.08, radius_m=1.0,
                                              n_stations=8)
        s = airfoils.suggest_reynolds_mach_lists(geom, rpm=1.0)
        self.assertEqual(len(s["reynolds"]), 3)
        self.assertEqual(len(s["mach"]), 3)

    def test_gui_fills_when_entering_neuralfoil_mode(self):
        tab, state = _tab_with_project()
        state.project.saved_cases = [FlightCondition(name="c", rpm=1200.0)]
        before = tab.re_list_edit.text()
        tab.source_combo.setCurrentText("neuralfoil")
        self.assertNotEqual(tab.re_list_edit.text(), before)
        self.assertEqual(len(airfoils.parse_floats(tab.re_list_edit.text())
                             if hasattr(airfoils, "parse_floats")
                             else [v for v in tab.re_list_edit.text().split(",") if v.strip()]), 3)
        self.assertEqual(len([v for v in tab.mach_list_edit.text().split(",") if v.strip()]), 3)

    def test_gui_respects_the_user_typed_list(self):
        tab, _ = _tab_with_project()
        tab.re_list_edit.setText("1234, 5678")
        tab.re_list_edit.textEdited.emit("1234, 5678")   # simulates typing
        tab.source_combo.setCurrentText("neuralfoil")
        self.assertEqual(tab.re_list_edit.text(), "1234, 5678")

    def test_suggest_button_overwrites_even_after_editing(self):
        tab, _ = _tab_with_project()
        tab.re_list_edit.setText("1234")
        tab.re_list_edit.textEdited.emit("1234")
        tab._suggest_re_mach(force=True)
        self.assertNotEqual(tab.re_list_edit.text(), "1234")


class LegendPerCondition(unittest.TestCase):
    """Item 32: each generated slice carries ITS OWN Reynolds/Mach in the legend."""

    def _slices_neuralfoil(self):
        # external_solvers uses a single `label` for the entire sweep
        return [
            PolarSlice(alpha_deg=[-5, 0, 5], cl=[-0.3, 0.1, 0.6], cd=[0.02, 0.01, 0.02],
                       reynolds=1e5, mach=0.0, label="neuralfoil:naca4 2412"),
            PolarSlice(alpha_deg=[-5, 0, 5], cl=[-0.3, 0.1, 0.6], cd=[0.02, 0.01, 0.02],
                       reynolds=5e5, mach=0.3, label="neuralfoil:naca4 2412"),
        ]

    def test_generic_label_no_longer_swallows_re_and_mach(self):
        label = airfoils.condition_label(
            {"reynolds": 1e5, "mach": 0.3, "label": "neuralfoil:naca4 2412"})
        self.assertIn("Re=1e+05", label)
        self.assertIn("M=0.30", label)
        self.assertIn("neuralfoil:naca4 2412", label)

    def test_label_alone_when_there_is_no_condition(self):
        self.assertEqual(airfoils.condition_label({"label": "my_csv"}), "my_csv")

    def test_overlay_curves_have_distinct_legends(self):
        a = AirfoilDef(source="table", table_slices=self._slices_neuralfoil())
        conds = airfoils.unique_conditions(a)
        curves = airfoils.preview_polar_multi(a, conditions=conds, alpha_deg_range=(-5, 5, 5.0))
        labels = [c["label"] for c in curves]
        self.assertEqual(len(set(labels)), len(labels), labels)

    def test_selected_curve_from_the_canvas_too(self):
        tab, state = _tab_with_project()
        state.project.airfoil = AirfoilDef(source="table", extend_full_range=False,
                                            table_slices=self._slices_neuralfoil())
        state.notify_airfoil()
        tab._nav_selection = {"r_norm": None, "reynolds": 5e5, "mach": 0.3}
        curves = tab._collect_polar_curves(tab._collect_airfoil_def())
        self.assertIn("Re=5e+05", curves[0]["label"])


class GeometryGenerationPopup(unittest.TestCase):
    """Items 1 and 2 of the GeometryGeneratorDialog popup."""

    def test_combo_popup_does_not_elide_options(self):
        _app()
        dlg = GeometryGeneratorDialog(None, 3, 1.0)
        combo = dlg.kind_combo
        self.assertEqual(combo.view().textElideMode(), Qt.TextElideMode.ElideNone)
        fm = combo.fontMetrics()
        widest = max(fm.horizontalAdvance(combo.itemText(i)) for i in range(combo.count()))
        self.assertGreaterEqual(combo.minimumWidth(), widest)
        self.assertGreaterEqual(combo.view().minimumWidth(), widest)

    def test_blade_count_and_radius_are_editable_and_start_from_the_given_value(self):
        _app()
        dlg = GeometryGeneratorDialog(None, 4, 2.5)
        self.assertEqual(dlg.n_blades.value(), 4)
        self.assertAlmostEqual(dlg.radius_m.value(), 2.5)
        self.assertTrue(dlg.n_blades.isEnabled())
        self.assertTrue(dlg.radius_m.isEnabled())

    def test_changing_blade_count_updates_solidity_live(self):
        _app()
        dlg = GeometryGeneratorDialog(None, 2, 1.0)
        sigma2 = dlg.solidity.value()
        ar2 = dlg.aspect_ratio.value()
        dlg.n_blades.setValue(4)
        self.assertAlmostEqual(dlg.solidity.value(), 2 * sigma2, places=4)
        # AR is per blade: it does not depend on the number of blades
        self.assertAlmostEqual(dlg.aspect_ratio.value(), ar2, places=2)

    def test_generated_geometry_uses_the_values_edited_in_the_popup(self):
        _app()
        dlg = GeometryGeneratorDialog(None, 2, 1.0)
        dlg.n_blades.setValue(5)
        dlg.radius_m.setValue(3.0)
        dlg._on_confirm()
        self.assertIsNotNone(dlg.generated_geom)
        self.assertEqual(dlg.generated_geom.n_blades, 5)
        self.assertAlmostEqual(dlg.generated_geom.radius_m, 3.0)

    def test_geometry_tab_absorbs_the_round_trip(self):
        _app()
        state = AppState()
        state.project = make_studies_project()
        with patch_message_box_everywhere("QMessageBox"):
            tab = GeometryTab(state)
            state.notify_geometry()
            new_geom = geometry.generate_rectangular(chord_norm=0.09, radius_m=4.0,
                                                      n_blades=6, n_stations=8)
            tab.state.project.geometry = new_geom
            tab._sync_constants_from_geometry(new_geom)
        self.assertEqual(tab.n_blades.value(), 6)
        self.assertAlmostEqual(tab.radius_m.value(), 4.0)
        # and the mirroring must not trigger `_apply_constants` back
        self.assertEqual(tab.state.project.geometry.n_blades, 6)


if __name__ == "__main__":
    unittest.main()
