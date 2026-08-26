"""Tests for the Geometry Designer window (Tools > Geometry Designer).

Headless: `tests/conftest.py` sets QT_QPA_PLATFORM=offscreen and the Agg
backend. End-to-end runs use a coarse mesh (Ne=6, Npsi=8) and one
condition, so the whole file stays well under a minute.
"""
from __future__ import annotations

import time
import unittest
import unittest.mock
from pathlib import Path

import numpy as np

from tests import helpers

try:
    from PyQt6.QtCore import Qt
    from PyQt6.QtWidgets import QApplication
    _HAS_QT = True
except Exception:                                    # pragma: no cover
    _HAS_QT = False

from zbemt.models import AirfoilDef, Results


def _make_project(path: str = "", **cfg_overrides):
    from zbemt import geometry
    from zbemt.models import Project
    geom = geometry.generate_tapered(root_chord_norm=0.10,
                                      tip_chord_norm=0.04,
                                      twist_root_deg=14.0,
                                      twist_tip_deg=2.0,
                                      root_cutout_norm=0.15,
                                      radius_m=1.0, n_stations=8)
    airfoil = AirfoilDef(source="analytical", stall_model="clip",
                          alpha_stall_pos_deg=15.0,
                          alpha_stall_neg_deg=-6.0)
    cfg = dict(Ne=6, Npsi=8, solver="fixed_point", max_iter=80)
    cfg.update(cfg_overrides)
    return Project(name="teste_designer", path=path, geometry=geom,
                    airfoil=airfoil, config=cfg)


def _result(label, name, **summary):
    return Results(summary={"geometry_label": label, **summary}, maps={},
                    condition_name=name)


def _assert_same_geometry(testcase, a, b):
    """Field-by-field equality of two radial tables (RotorGeometryDef)."""
    testcase.assertEqual(a.n_blades, b.n_blades)
    testcase.assertAlmostEqual(a.radius_m, b.radius_m, places=9)
    testcase.assertAlmostEqual(a.root_cutout_norm, b.root_cutout_norm,
                                places=9)
    testcase.assertEqual(len(a.r_norm), len(b.r_norm))
    for attr in ("r_norm", "chord_norm", "twist_deg"):
        for value_a, value_b in zip(getattr(a, attr), getattr(b, attr)):
            testcase.assertAlmostEqual(value_a, value_b, places=9)


def _save_other_project(tmpdir):
    """Writes a small on-disk project distinct from ``_make_project``
    (rectangular, 3 blades, radius 1.2 m) and returns (path, project)."""
    from zbemt import api, geometry
    from zbemt.models import AirfoilDef, Project
    geom = geometry.generate_rectangular(chord_norm=0.09,
                                          twist_root_deg=10.0,
                                          twist_tip_deg=3.0, radius_m=1.2,
                                          n_blades=3, n_stations=10)
    airfoil = AirfoilDef(source="analytical", stall_model="clip")
    project = Project(name="other_rotor",
                      path=str(Path(tmpdir) / "other_rotor"),
                      geometry=geom, airfoil=airfoil,
                      config=dict(Ne=6, Npsi=8, solver="fixed_point",
                                  max_iter=80))
    api.save_project(project)
    return project.path, project


def _snapshot_files(root):
    """Byte snapshot of every file under ``root``, keyed by relative
    path -- equality of two snapshots proves nothing was rewritten."""
    root = Path(root)
    return {str(p.relative_to(root)): p.read_bytes()
            for p in sorted(root.rglob("*")) if p.is_file()}


if _HAS_QT:

    class DesignerWindowBase(unittest.TestCase):
        """Shared plumbing: one QApplication, one window per test."""

        @classmethod
        def setUpClass(cls):
            cls.app = QApplication.instance() or QApplication([])
            from zbemt.gui.tabs.designer_window import GeometryDesignerWindow
            cls.window_cls = GeometryDesignerWindow

        def _window_for(self, project=None):
            from zbemt.gui.common import AppState
            state = AppState()
            if project is not None:
                state.set_project(project)
            window = self.window_cls(state)
            self.addCleanup(window.deleteLater)
            return window

        def _build_tip_sweep(self, window, values="0.06"):
            window.vsweep_param_combo.setCurrentText("tip_chord_norm")
            window.vsweep_values_edit.setText(values)
            with helpers.patch_message_box_everywhere("QMessageBox"):
                window.btn_build_sweep.click()

        def _pump(self, predicate, timeout_s):
            deadline = time.time() + timeout_s
            while time.time() < deadline:
                self.app.processEvents()
                if predicate():
                    return True
                time.sleep(0.02)
            self.app.processEvents()
            return predicate()

        def _run_to_completion(self, window, timeout_s=45.0):
            with helpers.patch_message_box_everywhere("QMessageBox"):
                window._run_comparison()
                done = self._pump(
                    lambda: window._compare_worker is None, timeout_s)
            self.assertTrue(done, "comparison did not finish in time")

    @unittest.skipUnless(_HAS_QT, "PyQt6 not installed in this environment")
    class TestDesignerConstruction(DesignerWindowBase):
        """Construction, empty projects, propeller mode."""

        def test_window_constructs_with_fast_project(self):
            window = self._window_for(_make_project())
            self.assertEqual(window.variants_table.rowCount(), 1)
            names = [window.pages.tabText(i)
                     for i in range(window.pages.count())]
            self.assertEqual(names,
                             ["Variants", "Conditions", "Run && results"])

        def test_window_survives_an_empty_project(self):
            window = self._window_for()          # no project at all
            self.assertEqual(window.variants_table.rowCount(), 0)
            self.assertIn("project", window.summary_label.text().lower())

        def test_window_constructs_in_propeller_mode(self):
            window = self._window_for(
                _make_project(config={"is_propeller": True}))
            self.assertEqual(window.variants_table.rowCount(), 1)

        def test_base_row_seeds_from_tapered_origin_params(self):
            window = self._window_for(_make_project())
            cells = [window.variants_table.item(0, c).text()
                     for c in range(window.variants_table.columnCount())]
            geom = window._session_base_geometry()
            integral = float(np.trapezoid(geom.chord_norm, x=geom.r_norm))
            self.assertEqual(cells, ["base", "0.1", "0.04", "14", "2", "2",
                                     f"{geom.root_cutout_norm:.3f}",
                                     f"{geom.radius_m:.3f}",
                                     f"{1.0 / integral:.2f}",
                                     f"{int(geom.n_blades) * integral / np.pi:.3f}",
                                     "—"])

    @unittest.skipUnless(_HAS_QT, "PyQt6 not installed in this environment")
    class TestVariationSweepBuilder(DesignerWindowBase):
        """The sweep builder appends validated rows to the table."""

        def test_linspace_sweep_builds_expected_labels_and_count(self):
            window = self._window_for(_make_project())
            window.vsweep_param_combo.setCurrentText("tip_chord_norm")
            window.vsweep_start.setValue(0.03)
            window.vsweep_end.setValue(0.05)
            window.vsweep_count.setValue(3)
            with helpers.patch_message_box_everywhere("QMessageBox"):
                window.btn_build_sweep.click()
            table = window.variants_table
            self.assertEqual(table.rowCount(), 4)      # base + 3 values
            labels = [table.item(r, 0).text() for r in (1, 2, 3)]
            self.assertEqual(labels, ["tip_chord_norm=0.030",
                                      "tip_chord_norm=0.040",
                                      "tip_chord_norm=0.050"])
            self.assertEqual(table.item(1, 2).text(), "0.03")

        def test_explicit_value_list_replaces_the_range(self):
            window = self._window_for(_make_project())
            self._build_tip_sweep(window, values="0.06, 0.08")
            table = window.variants_table
            self.assertEqual(table.rowCount(), 3)      # base + 2 values
            labels = [table.item(r, 0).text() for r in (1, 2)]
            self.assertEqual(labels, ["tip_chord_norm=0.060",
                                      "tip_chord_norm=0.080"])

        def test_blade_count_sweep_uses_integer_labels_and_cells(self):
            window = self._window_for(_make_project())
            window.vsweep_param_combo.setCurrentText("n_blades")
            window.vsweep_values_edit.setText("3, 4")
            with helpers.patch_message_box_everywhere("QMessageBox"):
                window.btn_build_sweep.click()
            table = window.variants_table
            self.assertEqual([table.item(r, 0).text() for r in (1, 2)],
                             ["n_blades=3", "n_blades=4"])
            self.assertEqual(table.item(1, 5).text(), "3")

        def test_radius_sweep_fills_its_own_column_cell(self):
            window = self._window_for(_make_project())
            window.vsweep_param_combo.setCurrentText("radius_m")
            window.vsweep_values_edit.setText("1.2")
            with helpers.patch_message_box_everywhere("QMessageBox"):
                window.btn_build_sweep.click()
            table = window.variants_table
            self.assertEqual(table.item(1, 7).text(), "1.2")
            label_item = table.item(1, 0)
            self.assertIsNone(label_item.data(Qt.ItemDataRole.UserRole))
            label, overrides = window._row_overrides(1)
            self.assertEqual(label, "radius_m=1.200")
            self.assertEqual(overrides.get("radius_m"), 1.2)

        def test_invalid_parameter_kind_combination_is_rejected(self):
            from zbemt import geometry
            from zbemt.models import Project
            geom = geometry.generate_elliptic(max_chord_norm=0.12,
                                               n_stations=8)
            airfoil = AirfoilDef(source="analytical", stall_model="clip")
            project = Project(name="ell", geometry=geom, airfoil=airfoil,
                               config=dict(Ne=6, Npsi=8,
                                           solver="fixed_point",
                                           max_iter=80))
            window = self._window_for(project)
            window.vsweep_param_combo.setCurrentText("tip_chord_norm")
            window.vsweep_values_edit.setText("0.06")
            with helpers.patch_message_box_everywhere("QMessageBox") as box:
                window.btn_build_sweep.click()
            self.assertEqual(window.variants_table.rowCount(), 1)
            box.warning.assert_called()

    @unittest.skipUnless(_HAS_QT, "PyQt6 not installed in this environment")
    class TestExtraOverridesColumn(DesignerWindowBase):
        """The read-only column that summarizes columnless overrides."""

        def test_column_exists_and_is_read_only(self):
            window = self._window_for(_make_project())
            table = window.variants_table
            self.assertEqual(table.columnCount(), 11)
            self.assertEqual(table.horizontalHeaderItem(10).text(),
                             "Extra overrides")
            flags = table.item(0, 10).flags()
            self.assertFalse(flags & Qt.ItemFlag.ItemIsEditable)

        def test_radius_sweep_fills_its_own_column_and_extra_stays_empty(self):
            window = self._window_for(_make_project())
            window.vsweep_param_combo.setCurrentText("radius_m")
            window.vsweep_values_edit.setText("1.2, 1.4, 1.6")
            with helpers.patch_message_box_everywhere("QMessageBox"):
                window.btn_build_sweep.click()
            table = window.variants_table
            self.assertEqual(table.item(0, 10).text(), "—")
            # Radius owns an editable column now: the swept values land
            # there, and the Extra projection stays empty.
            self.assertEqual([table.item(r, 7).text() for r in (1, 2, 3)],
                             ["1.2", "1.4", "1.6"])
            self.assertEqual([table.item(r, 10).text() for r in (1, 2, 3)],
                             ["—", "—", "—"])
            # A duplicated row carries its override and its summary.
            table.selectRow(1)
            with helpers.patch_message_box_everywhere("QMessageBox"):
                window.btn_duplicate_variant.click()
            self.assertEqual(table.item(4, 7).text(), "1.2")
            self.assertEqual(table.item(4, 10).text(), "—")
            _label, overrides = window._row_overrides(4)
            self.assertEqual(overrides.get("radius_m"), 1.2)

        def test_cell_edits_recompute_the_projection(self):
            from zbemt import geometry
            from zbemt.models import Project
            geom = geometry.generate_rectangular(chord_norm=0.08,
                                                  n_stations=8)
            airfoil = AirfoilDef(source="analytical", stall_model="clip")
            project = Project(name="rect", geometry=geom, airfoil=airfoil,
                               config=dict(Ne=6, Npsi=8,
                                           solver="fixed_point",
                                           max_iter=80))
            window = self._window_for(project)
            table = window.variants_table
            # The rectangular generator drives chord_norm, which has no
            # dedicated column: the base row names it.
            self.assertEqual(table.item(0, 10).text(), "chord_norm=0.080")
            table.item(0, 1).setText("0.12")
            self.assertEqual(table.item(0, 10).text(), "chord_norm=0.120")

    @unittest.skipUnless(_HAS_QT, "PyQt6 not installed in this environment")
    class TestRichTableColumns(DesignerWindowBase):
        """Root cutout, Radius, Aspect ratio and Solidity columns."""

        @staticmethod
        def _expected_texts(geom):
            """(cutout, radius, AR, solidity) texts of one geometry."""
            integral = float(np.trapezoid(geom.chord_norm, x=geom.r_norm))
            return (f"{float(geom.root_cutout_norm):.3f}",
                    f"{float(geom.radius_m):.3f}",
                    f"{1.0 / integral:.2f}",
                    f"{int(geom.n_blades) * integral / np.pi:.3f}")

        def test_header_order_and_column_count(self):
            window = self._window_for(_make_project())
            table = window.variants_table
            self.assertEqual(table.columnCount(), 11)
            headers = [table.horizontalHeaderItem(c).text()
                       for c in range(table.columnCount())]
            self.assertEqual(
                headers,
                ["Label", "Root chord c/R", "Tip chord c/R",
                 "Twist root [deg]", "Twist tip [deg]", "Blades",
                 "Root cutout [r/R]", "Radius [m]", "Aspect ratio",
                 "Solidity", "Extra overrides"])

        def test_integral_helper_matches_trapezoid_within_tolerance(self):
            from zbemt.gui.tabs.designer_window import _planform_integral
            window = self._window_for(_make_project())
            geom = window._session_base_geometry()
            expected = float(np.trapezoid(geom.chord_norm, x=geom.r_norm))
            self.assertAlmostEqual(_planform_integral(geom) / expected,
                                    1.0, places=6)

        def test_base_row_shows_its_own_direct_and_derived_values(self):
            window = self._window_for(_make_project())
            table = window.variants_table
            cutout, radius, ar, sigma = self._expected_texts(
                window._session_base_geometry())
            self.assertEqual(table.item(0, 6).text(), cutout)
            self.assertEqual(table.item(0, 7).text(), radius)
            self.assertEqual(table.item(0, 8).text(), ar)
            self.assertEqual(table.item(0, 9).text(), sigma)
            # Root cutout and Radius are direct parameters: they stay
            # editable on the base row, like Blades.
            for col in (6, 7):
                flags = table.item(0, col).flags()
                self.assertTrue(flags & Qt.ItemFlag.ItemIsEditable)
            for col in (8, 9):
                flags = table.item(0, col).flags()
                self.assertFalse(flags & Qt.ItemFlag.ItemIsEditable)

        def test_blade_edit_scales_solidity_exactly(self):
            from zbemt import geometry
            from zbemt.models import Project
            geom = geometry.generate_rectangular(chord_norm=0.50,
                                                  radius_m=1.0,
                                                  n_blades=2, n_stations=8)
            airfoil = AirfoilDef(source="analytical", stall_model="clip")
            project = Project(name="fat", geometry=geom, airfoil=airfoil,
                               config=dict(Ne=6, Npsi=8,
                                           solver="fixed_point",
                                           max_iter=80))
            window = self._window_for(project)
            table = window.variants_table
            sigma_before = float(table.item(0, 9).text())
            table.item(0, 5).setText("4")
            sigma_after = float(table.item(0, 9).text())
            # The display rounds to three decimals; the ratio holds to
            # well within that rounding.
            self.assertAlmostEqual(sigma_after / sigma_before, 2.0,
                                    delta=0.01)
            # Exactness against the same integral the window derives.
            *_, sigma_expected = self._expected_texts(
                window._row_resolved(0)[1])
            self.assertEqual(table.item(0, 9).text(), sigma_expected)

        def test_root_cutout_override_lands_in_its_column(self):
            window = self._window_for(_make_project())
            table = window.variants_table
            window.vsweep_param_combo.setCurrentText("root_cutout_norm")
            window.vsweep_values_edit.setText("0.25")
            with helpers.patch_message_box_everywhere("QMessageBox"):
                window.btn_build_sweep.click()
            self.assertEqual(table.rowCount(), 2)
            self.assertEqual(table.item(1, 6).text(), "0.25")
            label, overrides = window._row_overrides(1)
            self.assertEqual(label, "root_cutout_norm=0.250")
            self.assertEqual(overrides.get("root_cutout_norm"), 0.25)
            # The parameter owns a column now: nothing leaks into the
            # Extra overrides projection.
            self.assertNotIn("root_cutout", table.item(1, 10).text())
            # Editing the cell re-reads as the override, resolves into
            # the row's geometry, and moves the derived columns.
            table.item(1, 6).setText("0.3")
            _label, overrides = window._row_overrides(1)
            self.assertEqual(overrides.get("root_cutout_norm"), 0.3)
            _, geom = window._row_resolved(1)
            self.assertAlmostEqual(geom.root_cutout_norm, 0.3, places=9)
            _, _, ar, sigma = self._expected_texts(geom)
            self.assertEqual(table.item(1, 8).text(), ar)
            self.assertEqual(table.item(1, 9).text(), sigma)

        def test_generated_row_derives_from_its_own_geometry(self):
            window = self._window_for(_make_project())
            table = window.variants_table
            window.btn_add_generated.click()
            cutout = float(window.gen_cutout_spin.value())
            r = np.linspace(cutout, 1.0,
                            int(window.gen_stations_spin.value()))
            c = np.full(len(r), float(window.gen_chord_spin.value()))
            integral = float(np.trapezoid(c, x=r))
            blades = int(window.gen_blades_spin.value())
            self.assertEqual(table.item(1, 6).text(), f"{cutout:.3f}")
            self.assertEqual(
                table.item(1, 7).text(),
                f"{float(window.gen_radius_spin.value()):.3f}")
            self.assertEqual(table.item(1, 8).text(),
                             f"{1.0 / integral:.2f}")
            self.assertEqual(table.item(1, 9).text(),
                             f"{blades * integral / np.pi:.3f}")
            # The carried geometry fills the direct cells of a payload
            # row read-only.
            for col in (6, 7):
                flags = table.item(1, col).flags()
                self.assertFalse(flags & Qt.ItemFlag.ItemIsEditable)
            marker = table.item(1, 10).text()
            self.assertIn("generated", marker)
            self.assertNotIn("root_cutout", marker)

        def test_derived_cells_are_read_only_on_every_row(self):
            window = self._window_for(_make_project())
            self._build_tip_sweep(window)          # one override row
            window.btn_add_generated.click()       # one payload row
            table = window.variants_table
            self.assertEqual(table.rowCount(), 3)
            for row in range(table.rowCount()):
                for col in (8, 9, 10):
                    flags = table.item(row, col).flags()
                    self.assertFalse(flags & Qt.ItemFlag.ItemIsEditable,
                                     f"row {row}, column {col}")

        def test_ranking_and_overlay_offer_the_derived_metrics(self):
            window = self._window_for(_make_project())
            results = [_result("base", "hover", FM=0.70, Thrust=10.0,
                                aspect_ratio=16.81, solidity=0.038),
                       _result("v1", "hover", FM=0.72, Thrust=11.0,
                                aspect_ratio=18.20, solidity=0.035)]
            window._fill_ranking_combo(results)
            texts = [window.ranking_field_combo.itemText(i)
                     for i in range(window.ranking_field_combo.count())]
            self.assertEqual(texts, ["(none)", "FM", "Thrust",
                                     "aspect_ratio", "solidity"])
            overlay_results = [_result("base", "hover",
                                        aspect_ratio=16.81,
                                        solidity=0.038),
                               _result("v1", "hover",
                                        aspect_ratio=18.20,
                                        solidity=0.035)]
            from matplotlib.figure import Figure
            from zbemt.gui.tabs import designer_window
            fig = Figure()
            ax = fig.add_subplot(111)
            with unittest.mock.patch.object(
                    designer_window.plots, "plot_geometry_comparison",
                    return_value=ax) as plot_call, \
                    unittest.mock.patch.object(window.overlay_canvas,
                                                "show_figure"):
                window._draw_overlay(overlay_results)
            self.assertEqual(plot_call.call_args.kwargs.get("fields"),
                             ("aspect_ratio", "solidity"))

    @unittest.skipUnless(_HAS_QT, "PyQt6 not installed in this environment")
    class TestDefaultRankingMetric(DesignerWindowBase):
        """The metric combo opens on the mode-appropriate quantity."""

        def test_propeller_summaries_default_to_eta_prop(self):
            window = self._window_for(
                _make_project(config={"is_propeller": True}))
            results = [_result("base", "cruise", eta_prop=0.80, FM=0.70,
                                cfg_is_propeller=True),
                       _result("v1", "cruise", eta_prop=0.85, FM=0.72,
                                cfg_is_propeller=1)]
            window._fill_ranking_combo(results)
            self.assertEqual(window.ranking_field_combo.currentText(),
                             "eta_prop")

        def test_rotor_summaries_default_to_fm(self):
            window = self._window_for(_make_project())
            results = [_result("base", "hover", FM=0.70, eta_prop=0.50,
                                cfg_is_propeller=False),
                       _result("v1", "hover", FM=0.75,
                                cfg_is_propeller=0)]
            window._fill_ranking_combo(results)
            self.assertEqual(window.ranking_field_combo.currentText(),
                             "FM")

        def test_fallback_keeps_the_first_available_metric(self):
            window = self._window_for(_make_project())
            results = [_result("base", "hover", CT=0.005)]
            window._fill_ranking_combo(results)
            self.assertEqual(window.ranking_field_combo.currentText(),
                             "CT")

        def test_previous_choice_survives_when_still_valid(self):
            window = self._window_for(_make_project())
            results = [_result("base", "hover", CT=0.005, FM=0.70),
                       _result("v1", "hover", CT=0.006, FM=0.72)]
            window._fill_ranking_combo(results)
            window.ranking_field_combo.setCurrentText("CT")
            window._fill_ranking_combo(results)
            self.assertEqual(window.ranking_field_combo.currentText(),
                             "CT")

    @unittest.skipUnless(_HAS_QT, "PyQt6 not installed in this environment")
    class TestRankingConditionCombo(DesignerWindowBase):
        """The ranking reads the case picked in the Condition combo."""

        @staticmethod
        def _results():
            results = []
            for label, fm in (("base", 0.70), ("v1", 0.74), ("v2", 0.78)):
                for name, mult in (("hover", 1.0), ("cruise", 1.02)):
                    results.append(_result(label, name, CT=0.005,
                                            FM=fm * mult, CP=0.010,
                                            cfg_is_propeller=False))
            return results

        def test_combo_lists_conditions_in_first_appearance_order(self):
            window = self._window_for(_make_project())
            window._comparison_results = self._results()
            window._populate_results(window._comparison_results)
            combo = window.ranking_condition_combo
            self.assertEqual(
                [combo.itemText(i) for i in range(combo.count())],
                ["hover", "cruise"])
            self.assertEqual(combo.currentText(), "hover")

        def test_selecting_second_condition_reranks_at_position_one(self):
            window = self._window_for(_make_project())
            window._comparison_results = self._results()
            window._populate_results(window._comparison_results)
            window.ranking_condition_combo.setCurrentIndex(1)
            with unittest.mock.patch(
                    "zbemt.gui.tabs.designer_window.plots"
                    ".plot_geometry_ranking") as ranking:
                window._draw_ranking()
            self.assertEqual(ranking.call_args.kwargs.get("ref_index"), 1)

        def test_ranking_title_names_the_selected_condition(self):
            window = self._window_for(_make_project())
            window._comparison_results = self._results()
            window._populate_results(window._comparison_results)
            window.ranking_condition_combo.setCurrentIndex(1)
            window._draw_ranking()
            title = window.ranking_canvas.simple.ax.get_title()
            self.assertIn("cruise", title)

        def test_combos_disable_while_a_run_is_in_flight(self):
            window = self._window_for(_make_project())
            window.ranking_condition_combo.addItem("hover")
            window._set_compare_running(True)
            self.assertFalse(window.ranking_field_combo.isEnabled())
            self.assertFalse(window.ranking_condition_combo.isEnabled())
            window._set_compare_running(False)
            self.assertTrue(window.ranking_condition_combo.isEnabled())

    @unittest.skipUnless(_HAS_QT, "PyQt6 not installed in this environment")
    class TestConditionsPage(DesignerWindowBase):
        """Solve estimate, sweep condition naming, mode requirements."""

        def test_totals_label_counts_variants_times_cases(self):
            window = self._window_for(_make_project())
            self._build_tip_sweep(window)
            self.assertIn("2 variants × 1 cases = 2 solves",
                          window.summary_label.text())
            window.radio_sweep.setChecked(True)
            window.sweep_count.setValue(5)
            self.assertIn("2 variants × 5 cases = 10 solves",
                          window.summary_label.text())

        def test_saved_cases_mode_without_cases_states_the_problem(self):
            window = self._window_for(_make_project())
            window.radio_saved_cases.setChecked(True)
            self.assertIn("no saved cases",
                          window.summary_label.text().lower())

        def test_sweep_condition_names_carry_two_decimals(self):
            window = self._window_for(_make_project())
            window.radio_sweep.setChecked(True)
            window.sweep_axis_combo.setCurrentText("mu_x")
            window.sweep_start.setValue(0.0)
            window.sweep_stop.setValue(0.2)
            window.sweep_count.setValue(3)
            conditions = window._selected_conditions()
            self.assertEqual([c.name for c in conditions],
                             ["mu=0.00", "mu=0.10", "mu=0.20"])

        def test_single_condition_carries_the_rpm_field(self):
            window = self._window_for(_make_project())
            conditions = window._selected_conditions()
            self.assertEqual(len(conditions), 1)
            self.assertEqual(conditions[0].rpm, window.rpm_spin.value())

    @unittest.skipUnless(_HAS_QT, "PyQt6 not installed in this environment")
    class TestThrustMatching(DesignerWindowBase):
        """The Conditions-page trim selector reaches the comparison run."""

        def test_combo_offers_exactly_the_three_choices(self):
            window = self._window_for(_make_project())
            combo = window.trim_combo
            self.assertEqual(
                [combo.itemText(i) for i in range(combo.count())],
                ["(off)", "Thrust", "CT"])
            self.assertEqual(combo.currentText(), "(off)")

        def test_combo_tooltip_states_the_session_only_nature(self):
            window = self._window_for(_make_project())
            tooltip = window.trim_combo.toolTip()
            # Session-only choice: no .bemt key exists, and the tooltip
            # must say so instead of inventing one.
            self.assertIn(".bemt", tooltip)
            self.assertIn("reference", tooltip.lower())

        def _trim_reaching_the_worker(self, choice):
            from zbemt.gui.tabs import designer_window
            window = self._window_for(_make_project())
            self._build_tip_sweep(window)
            window.trim_combo.setCurrentText(choice)
            with unittest.mock.patch.object(
                    designer_window, "CompareWorker") as worker_cls, \
                    unittest.mock.patch.object(designer_window,
                                                "launch_worker"), \
                    helpers.patch_message_box_everywhere("QMessageBox"):
                try:
                    window._run_comparison()
                finally:
                    window._reset_compare_ui()
            return worker_cls.call_args.kwargs.get("trim")

        def test_thrust_choice_reaches_the_worker_as_trim_thrust(self):
            self.assertEqual(self._trim_reaching_the_worker("Thrust"),
                             "thrust")

        def test_ct_choice_reaches_the_worker_as_trim_ct(self):
            self.assertEqual(self._trim_reaching_the_worker("CT"), "CT")

        def test_off_is_the_default_sent_to_the_worker(self):
            self.assertEqual(self._trim_reaching_the_worker("(off)"),
                             "none")

        def test_selector_is_disabled_while_a_run_is_in_flight(self):
            window = self._window_for(_make_project())
            window._set_compare_running(True)
            self.assertFalse(window.trim_combo.isEnabled())
            window._set_compare_running(False)
            self.assertTrue(window.trim_combo.isEnabled())

        def test_estimate_extends_while_trim_is_active(self):
            window = self._window_for(_make_project())
            self._build_tip_sweep(window)
            window.trim_combo.setCurrentText("Thrust")
            self.assertIn("(trim)", window.summary_label.text())
            window.trim_combo.setCurrentText("(off)")
            self.assertNotIn("(trim)", window.summary_label.text())

    @unittest.skipUnless(_HAS_QT, "PyQt6 not installed in this environment")
    class TestVerdictStrip(DesignerWindowBase):
        """Best-in-class badges; eta_prop only in propeller summaries."""

        @staticmethod
        def _first_by_label(results):
            first = {}
            for res in results:
                first.setdefault(res.summary["geometry_label"], res)
            return first

        def test_rotor_summaries_hide_the_efficiency_badge(self):
            window = self._window_for(_make_project())
            results = [
                _result("a", "hover", CT=0.005, FM=0.70, CP=0.010,
                        cfg_is_propeller=False),
                _result("b", "hover", CT=0.004, FM=0.75, CP=0.009,
                        cfg_is_propeller=0),
            ]
            window._populate_verdict(self._first_by_label(results))
            text = window.guidance_label.text()
            self.assertIn("endurance pick b", text)
            self.assertNotIn("cruise", text)

        def test_propeller_summaries_show_the_efficiency_badge(self):
            window = self._window_for(_make_project())
            results = [
                _result("a", "cruise", CT=0.005, eta_prop=0.80,
                        CP=0.010, cfg_is_propeller=True),
                _result("b", "cruise", CT=0.004, eta_prop=0.85,
                        CP=0.009, cfg_is_propeller=1),
            ]
            window._populate_verdict(self._first_by_label(results))
            self.assertIn("b converts power best",
                          window.guidance_label.text())

    @unittest.skipUnless(_HAS_QT, "PyQt6 not installed in this environment")
    class TestEndToEndRun(DesignerWindowBase):
        """Tiny real run: two variants, one condition, full results UI."""

        def test_two_variants_single_condition_populates_results(self):
            window = self._window_for(_make_project())
            self._build_tip_sweep(window, values="0.06")   # base + 1
            conditions = window._selected_conditions()
            self.assertEqual(len(conditions), 1)
            self.assertTrue(conditions[0].rpm > 0)
            self._run_to_completion(window)

            self.assertIn("finished", window.compare_status.text())
            # Verdict chips: one per variant, plus a guidance sentence.
            self.assertEqual(window.verdict_strip.count(), 2)
            self.assertTrue(window.guidance_label.text())
            # Ranking canvas: FM default, one bar per variant.
            self.assertEqual(window.ranking_field_combo.currentText(), "FM")
            self.assertGreaterEqual(
                len(window.ranking_canvas.simple.ax.patches), 2)
            # Overlay canvas: multi-panel figure, ALL variants together.
            overlay_fig = window.overlay_canvas._current.figure
            self.assertGreaterEqual(len(overlay_fig.axes), 2)
            self.assertIn("Geometry comparison",
                          overlay_fig._suptitle.get_text())
            lines = sum(len(ax.get_lines()) for ax in overlay_fig.axes)
            self.assertGreater(lines, 0)
            # Delta canvas: percent change of the variant against base.
            self.assertGreaterEqual(
                len(window.delta_canvas.simple.ax.patches), 1)

    @unittest.skipUnless(_HAS_QT, "PyQt6 not installed in this environment")
    class TestDeltaViewPage(DesignerWindowBase):
        """The third canvas expresses each variant against the base."""

        def test_populate_draws_percent_bars_against_base(self):
            window = self._window_for(_make_project())
            results = [_result("base", "hover", CT=0.005, FM=0.50,
                                cfg_is_propeller=False),
                       _result("variant 1", "hover", CT=0.006, FM=0.55,
                                cfg_is_propeller=False)]
            window._populate_results(results)
            ax = window.delta_canvas.simple.ax
            self.assertGreaterEqual(len(ax.patches), 1)
            heights = sorted(round(p.get_height(), 6)
                             for p in ax.patches)
            self.assertIn(10.0, heights)

        def test_none_metric_disables_the_delta_view(self):
            window = self._window_for(_make_project())
            results = [_result("base", "hover", CT=0.005, FM=0.70),
                       _result("variant 1", "hover", CT=0.006, FM=0.72)]
            window.ranking_field_combo.setCurrentText("(none)")
            window._draw_delta(results)
            self.assertGreater(len(window.delta_canvas.simple.ax.texts), 0)
            self.assertEqual(len(window.delta_canvas.simple.ax.patches), 0)

    @unittest.skipUnless(_HAS_QT, "PyQt6 not installed in this environment")
    class TestCancelPath(DesignerWindowBase):
        """Cancel stops the run between cases, no crash, clean state."""

        def test_cancel_stops_between_cases_without_crash(self):
            from zbemt.bemt import SolveCancelled

            calls = {"n": 0}

            def slow_solver(_project, condition, should_cancel=None):
                calls["n"] += 1
                time.sleep(0.05)
                if should_cancel is not None and should_cancel():
                    raise SolveCancelled()
                return Results(summary={"CT": 0.005, "FM": 0.7,
                                         "cfg_is_propeller": False},
                                maps={}, condition_name=condition.name)

            window = self._window_for(_make_project())
            self._build_tip_sweep(window)
            with unittest.mock.patch("zbemt.studies.run_single_case",
                                      side_effect=slow_solver), \
                 helpers.patch_message_box_everywhere("QMessageBox"):
                window._run_comparison()
                started = self._pump(
                    lambda: window.compare_progress.value() >= 1, 15.0)
                self.assertTrue(started, "the run never finished one case")
                window._cancel_comparison()
                self.assertFalse(window.btn_compare_cancel.isEnabled())
                done = self._pump(lambda: window._compare_worker is None,
                                  30.0)
            self.assertTrue(done, "worker did not stop after cancel")
            self.assertIn("canceled",
                          window.compare_status.text().lower())
            self.assertLess(calls["n"], 4)
            self.assertEqual(window.verdict_strip.count(), 0)

    @unittest.skipUnless(_HAS_QT, "PyQt6 not installed in this environment")
    class TestExports(DesignerWindowBase):
        """Report and CSV land in the project outputs folder."""

        def test_report_and_csv_land_in_the_outputs_folder(self):
            import tempfile
            from zbemt import api
            with tempfile.TemporaryDirectory() as tmp:
                project = _make_project(path=str(Path(tmp) / "proj"))
                window = self._window_for(project)
                self._build_tip_sweep(window)
                self._run_to_completion(window)
                with helpers.patch_message_box_everywhere("QMessageBox"):
                    window._export_comparison_report()
                    window._export_comparison_csv()
                outdir = Path(api.project_outputs_dir(project))
                reports = list(outdir.glob("geometry_comparison_*.html"))
                csvs = list(outdir.glob("geometry_comparison_*.csv"))
                self.assertEqual(len(reports), 1)
                self.assertEqual(len(csvs), 1)
                self.assertGreater(reports[0].stat().st_size, 1000)

    @unittest.skipUnless(_HAS_QT, "PyQt6 not installed in this environment")
    class TestGenerateVariantBlock(DesignerWindowBase):
        """The family dropdown builds rows carrying a COMPLETE geometry."""

        def test_family_combo_reveals_exactly_its_own_fields(self):
            window = self._window_for(_make_project())
            form = window._generate_form

            def visible(widget):
                return bool(form.isRowVisible(widget))

            window.gen_family_combo.setCurrentText("rectangular")
            self.assertTrue(visible(window.gen_chord_spin))
            self.assertFalse(visible(window.gen_root_chord_spin))
            self.assertFalse(visible(window.gen_tip_chord_spin))
            self.assertFalse(visible(window.gen_max_chord_spin))
            self.assertTrue(visible(window.gen_twist_root_spin))
            self.assertTrue(visible(window.gen_twist_tip_spin))
            window.gen_family_combo.setCurrentText("tapered")
            self.assertFalse(visible(window.gen_chord_spin))
            self.assertTrue(visible(window.gen_root_chord_spin))
            self.assertTrue(visible(window.gen_tip_chord_spin))
            self.assertFalse(visible(window.gen_max_chord_spin))
            window.gen_family_combo.setCurrentText("elliptic")
            self.assertFalse(visible(window.gen_chord_spin))
            self.assertFalse(visible(window.gen_root_chord_spin))
            self.assertFalse(visible(window.gen_tip_chord_spin))
            self.assertTrue(visible(window.gen_max_chord_spin))
            self.assertTrue(visible(window.gen_twist_root_spin))

        def test_rectangular_defaults_append_a_generated_row(self):
            from zbemt import geometry
            window = self._window_for(_make_project())
            table = window.variants_table
            self.assertEqual(int(window.gen_stations_spin.value()),
                              len(window.state.project.geometry.r_norm))
            window.btn_add_generated.click()
            self.assertEqual(table.rowCount(), 2)
            self.assertEqual(table.item(1, 0).text(), "rectangular 1")
            marker = table.item(1, 10).text()
            self.assertIn("generated", marker)
            self.assertIn("rectangular", marker)
            expected = geometry.generate_rectangular(
                chord_norm=window.gen_chord_spin.value(),
                twist_root_deg=window.gen_twist_root_spin.value(),
                twist_tip_deg=window.gen_twist_tip_spin.value(),
                radius_m=window.gen_radius_spin.value(),
                n_blades=int(window.gen_blades_spin.value()),
                root_cutout_norm=window.gen_cutout_spin.value(),
                n_stations=int(window.gen_stations_spin.value()))
            _assert_same_geometry(
                self, window._collect_variants()["rectangular 1"], expected)

        def test_labels_are_numbered_per_family(self):
            window = self._window_for(_make_project())
            table = window.variants_table
            window.btn_add_generated.click()
            window.gen_family_combo.setCurrentText("tapered")
            window.btn_add_generated.click()
            window.gen_family_combo.setCurrentText("rectangular")
            window.btn_add_generated.click()
            labels = [table.item(r, 0).text() for r in (1, 2, 3)]
            self.assertEqual(labels,
                             ["rectangular 1", "tapered 1",
                              "rectangular 2"])

        def test_duplicate_of_a_generated_row_carries_the_geometry(self):
            from zbemt import geometry
            window = self._window_for(_make_project())
            table = window.variants_table
            window.btn_add_generated.click()
            expected = geometry.generate_rectangular(
                chord_norm=window.gen_chord_spin.value(),
                twist_root_deg=window.gen_twist_root_spin.value(),
                twist_tip_deg=window.gen_twist_tip_spin.value(),
                radius_m=window.gen_radius_spin.value(),
                n_blades=int(window.gen_blades_spin.value()),
                root_cutout_norm=window.gen_cutout_spin.value(),
                n_stations=int(window.gen_stations_spin.value()))
            table.selectRow(1)
            window.btn_duplicate_variant.click()
            self.assertEqual([table.item(r, 0).text() for r in (1, 2)],
                             ["rectangular 1", "rectangular 1 copy"])
            variants = window._collect_variants()
            _assert_same_geometry(self, variants["rectangular 1"], expected)
            _assert_same_geometry(self, variants["rectangular 1 copy"],
                                   expected)

    @unittest.skipUnless(_HAS_QT, "PyQt6 not installed in this environment")
    class TestImportFromProject(DesignerWindowBase):
        """Bringing another project's blade in as variant or base.

        The message-box patch here is scoped to the two modules that can
        open a dialog on these paths (`designer_window` itself and
        `common.show_error`): the shared all-modules helper imports
        `zbemt.gui.app`, whose health is another work stream's concern.
        """

        def _click_import(self, window, path, choice):
            import unittest.mock
            with unittest.mock.patch(
                    "zbemt.gui.tabs.designer_window.QFileDialog"
                    ".getExistingDirectory",
                    return_value=path) as dialog, \
                    unittest.mock.patch.object(window,
                                                "_ask_import_choice",
                                                return_value=choice):
                window.btn_import_project.click()
            dialog.assert_called_once()

        def test_add_as_variant_appends_a_row_labeled_with_the_project(self):
            import tempfile
            from zbemt import api
            with tempfile.TemporaryDirectory() as tmp:
                path, _saved = _save_other_project(tmp)
                opened = api.open_project(path)
                window = self._window_for(_make_project())
                self._click_import(window, path, "variant")
                table = window.variants_table
                self.assertEqual(table.rowCount(), 2)
                self.assertEqual(table.item(1, 0).text(), "other_rotor")
                got = window._collect_variants()["other_rotor"]
                _assert_same_geometry(self, got, opened.geometry)

        def test_replace_base_swaps_the_session_base_without_touching_disk(self):
            import tempfile
            from zbemt import api
            with tempfile.TemporaryDirectory() as tmp:
                path, saved = _save_other_project(tmp)
                opened = api.open_project(path)
                window = self._window_for(_make_project())
                original = window.state.project.geometry
                before = _snapshot_files(path)
                self._click_import(window, path, "base")
                table = window.variants_table
                self.assertEqual(table.item(0, 0).text(), "base")
                variants = window._collect_variants()
                _assert_same_geometry(self, variants["base"],
                                       opened.geometry)
                note = table.item(0, 10).text()
                self.assertTrue(note.startswith("imported:"))
                self.assertIn("other_rotor", note)
                # The seeded columns now describe the imported blade.
                self.assertEqual(table.item(0, 1).text(), "0.09")
                self.assertEqual(table.item(0, 5).text(), "3")
                # Nothing on disk moved, and the open project neither.
                self.assertEqual(_snapshot_files(path), before)
                reopened = api.open_project(path)
                _assert_same_geometry(self, reopened.geometry,
                                       saved.geometry)
                _assert_same_geometry(self, original,
                                       window.state.project.geometry)

        def test_invalid_folder_reports_what_a_project_folder_is(self):
            import tempfile
            import unittest.mock
            with tempfile.TemporaryDirectory() as tmp:
                empty = Path(tmp) / "empty"
                empty.mkdir()
                window = self._window_for(_make_project())
                with unittest.mock.patch(
                        "zbemt.gui.tabs.designer_window.QMessageBox"), \
                        unittest.mock.patch(
                            "zbemt.gui.common.QMessageBox") as box, \
                        unittest.mock.patch(
                            "zbemt.gui.tabs.designer_window.QFileDialog"
                            ".getExistingDirectory",
                            return_value=str(empty)):
                    window.btn_import_project.click()
                self.assertEqual(window.variants_table.rowCount(), 1)
                self.assertFalse(box.critical.call_args is None)
                message = box.critical.call_args[0][2]
                self.assertIn(".bemt", message)
                self.assertIn("inputs", message)

        def test_opening_another_project_clears_the_imported_base(self):
            import tempfile
            with tempfile.TemporaryDirectory() as tmp:
                path, _saved = _save_other_project(tmp)
                window = self._window_for(_make_project())
                self._click_import(window, path, "base")
                self.assertIsNotNone(window._base_override)
                window.state.set_project(_make_project())
                self.assertIsNone(window._base_override)
                table = window.variants_table
                self.assertEqual(table.item(0, 10).text(), "—")
                self.assertEqual(table.item(0, 1).text(), "0.1")
                self.assertEqual(table.item(0, 5).text(), "2")

    @unittest.skipUnless(_HAS_QT, "PyQt6 not installed in this environment")
    class TestTableOriginSweepRegression(DesignerWindowBase):
        """A planform sweep over a non-parametric base builds rows.

        Before table-space overrides landed in `studies.variant_geometry`,
        any planform parameter over such a base stopped the build with
        "need a parametric generator"; the endpoint value must now come
        out exactly where the sweep asked for it.
        """

        def _table_origin_window(self):
            import numpy as np
            from zbemt import geometry
            from zbemt.models import Project
            r = np.linspace(0.15, 1.0, 8).tolist()
            chord = np.linspace(0.10, 0.04, 8).tolist()
            twist = np.linspace(14.0, 2.0, 8).tolist()
            geom = geometry.generate_custom(r, chord, twist, radius_m=1.0,
                                             n_blades=2)
            airfoil = AirfoilDef(source="analytical", stall_model="clip")
            project = Project(name="tbl", geometry=geom, airfoil=airfoil,
                               config=dict(Ne=6, Npsi=8,
                                           solver="fixed_point",
                                           max_iter=80))
            return self._window_for(project)

        def test_planform_sweep_builds_on_a_table_origin_base(self):
            window = self._table_origin_window()
            table = window.variants_table
            window.vsweep_param_combo.setCurrentText("tip_chord_norm")
            window.vsweep_values_edit.setText("0.06")
            with unittest.mock.patch(
                    "zbemt.gui.tabs.designer_window.QMessageBox") as box:
                window.btn_build_sweep.click()
            self.assertEqual(table.rowCount(), 2)
            box.warning.assert_not_called()
            self.assertEqual(table.item(1, 0).text(),
                              "tip_chord_norm=0.060")
            got = window._collect_variants()["tip_chord_norm=0.060"]
            self.assertAlmostEqual(got.chord_norm[-1], 0.06, places=9)

        def test_sweep_tooltip_names_the_table_space_fallback(self):
            window = self._table_origin_window()
            tooltip = window.vsweep_param_combo.toolTip()
            self.assertIn("table space", tooltip)


if __name__ == "__main__":
    unittest.main()


if _HAS_QT:

    class TestLiveFieldLists(unittest.TestCase):
        """Item 5, finding 8: the ranking/overlay offers EVERY summary
        key the results carry (beyond the curated defaults), so keys
        Items 1/2/4 add are reachable."""

        class _R:
            def __init__(self, summary):
                self.summary = summary

        def test_extra_keys_join_after_the_defaults(self):
            from zbemt.gui.tabs.designer_window import GeometryDesignerWindow
            results = [self._R({"CT": 1, "FM": 2, "lambda_i": 0.1,
                                 "not_in_nomenclature_xyz": 5.0})]
            fields = GeometryDesignerWindow._live_field_list(
                results, GeometryDesignerWindow._OVERLAY_FIELDS)
            # Defaults that are present stay first, in their order.
            self.assertEqual(fields[0], "CT")
            self.assertIn("FM", fields[:2])
            # A nomenclature-known extra joins; an unknown one does not.
            self.assertIn("lambda_i", fields)
            self.assertNotIn("not_in_nomenclature_xyz", fields)

        def test_absent_defaults_are_dropped(self):
            from zbemt.gui.tabs.designer_window import GeometryDesignerWindow
            results = [self._R({"CT": 1})]
            fields = GeometryDesignerWindow._live_field_list(
                results, GeometryDesignerWindow._RANKING_FIELDS)
            self.assertEqual(fields, ["CT"])


if _HAS_QT:

    class TestAcceptDesignFromOptimizer(unittest.TestCase):
        """Item 5, cross-link 11: a Pareto member lands as an absolute
        row whose label states study and front index."""

        def test_accept_design_appends_labeled_absolute_row(self):
            from tests.helpers import make_studies_project
            from zbemt.gui.common import AppState
            project = make_studies_project()
            state = AppState()
            state.set_project(project)
            from zbemt.gui.tabs.designer_window import GeometryDesignerWindow
            window = GeometryDesignerWindow(state)
            self.addCleanup(window.deleteLater)
            before = window.variants_table.rowCount()
            window.accept_design("pareto #2",
                                  {"tip_chord_norm": 0.055})
            self.assertEqual(window.variants_table.rowCount(), before + 1)
            label_item = window.variants_table.item(
                window.variants_table.rowCount() - 1, window._COL_LABEL)
            self.assertEqual(label_item.text(), "pareto #2")
            payload = label_item.data(
                __import__("PyQt6.QtCore", fromlist=["Qt"]).Qt.ItemDataRole.UserRole)
            self.assertIsNotNone(payload, "the row must carry the full "
                                           "geometry payload")


if _HAS_QT:

    class TestCompareWithDerivatives(unittest.TestCase):
        """Item 5, cross-link 12: the button computes per-variant
        damping off-thread and presents it; the summary stays on the
        window for future columns."""

        @classmethod
        def setUpClass(cls):
            cls.app = QApplication.instance() or QApplication([])

        def test_button_computes_and_stores_damping(self):
            import time
            import unittest
            from PyQt6.QtWidgets import QApplication
            from tests.helpers import make_studies_project
            from zbemt.gui.common import AppState
            from zbemt.gui.tabs.designer_window import GeometryDesignerWindow
            from zbemt.models import FlightCondition
            project = make_studies_project()
            project.saved_cases = [FlightCondition(name="h", mu_x=0.0,
                                                    collective_deg=8.0,
                                                    rpm=600.0)]
            state = AppState()
            state.set_project(project)
            window = GeometryDesignerWindow(state)
            self.addCleanup(window.deleteLater)
            window._comparison_results = [{"summary": {}}]  # truthy gate
            window._comparison_conditions = list(project.saved_cases)
            window.ranking_condition_combo.addItem("h", 0)

            toy = {"base": {"pitch_damping": -2.0,
                             "heave_damping": -3.0}}
            with unittest.mock.patch(
                    "zbemt.api.damping_summary", return_value=toy):
                with helpers.patch_message_box_everywhere("QMessageBox"):
                    window._compare_with_derivatives()
                    deadline = time.time() + 10
                    while time.time() < deadline:
                        self.app.processEvents()
                        if getattr(window, "_damping_summary",
                                    None) is not None:
                            break
                        time.sleep(0.02)
            self.assertEqual(window._damping_summary, toy)
