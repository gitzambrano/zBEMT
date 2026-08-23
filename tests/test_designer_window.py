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
            self.assertEqual(cells, ["base", "0.1", "0.04", "14", "2", "2"])

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

        def test_parameter_without_a_column_rides_in_row_data(self):
            window = self._window_for(_make_project())
            window.vsweep_param_combo.setCurrentText("radius_m")
            window.vsweep_values_edit.setText("1.2")
            with helpers.patch_message_box_everywhere("QMessageBox"):
                window.btn_build_sweep.click()
            label_item = window.variants_table.item(1, 0)
            self.assertEqual(label_item.data(Qt.ItemDataRole.UserRole),
                             {"radius_m": 1.2})
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

if __name__ == "__main__":
    unittest.main()
