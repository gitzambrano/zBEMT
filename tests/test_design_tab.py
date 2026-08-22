"""Tests for the Design GUI tab (geometry comparison + optimization).

Headless: `tests/conftest.py` sets QT_QPA_PLATFORM=offscreen and the Agg
backend. The end-to-end runs use a deliberately coarse mesh (Ne<=10,
Npsi<=14) and a low evaluation cap so the whole file stays well under a
minute.
"""
from __future__ import annotations

import tempfile
import time
import unittest
import unittest.mock
from pathlib import Path

from tests import helpers

try:
    from PyQt6.QtWidgets import QApplication
    from PyQt6.QtCore import Qt
    _HAS_QT = True
except Exception:                                    # pragma: no cover
    _HAS_QT = False

from zbemt.models import AirfoilDef, FlightCondition, Results


def _make_project(path: str = "", **cfg_overrides):
    from zbemt import geometry
    from zbemt.models import Project
    geom = geometry.generate_tapered(root_chord_norm=0.10, tip_chord_norm=0.04,
                                      twist_root_deg=14.0, twist_tip_deg=2.0,
                                      root_cutout_norm=0.15, radius_m=1.0,
                                      n_stations=8)
    airfoil = AirfoilDef(source="analytical", stall_model="clip",
                          alpha_stall_pos_deg=15.0, alpha_stall_neg_deg=-6.0)
    cfg = dict(Ne=6, Npsi=8, solver="fixed_point", max_iter=80)
    cfg.update(cfg_overrides)
    return Project(name="teste_design", path=path, geometry=geom,
                    airfoil=airfoil, config=cfg)


if _HAS_QT:

    class DesignTabBase(unittest.TestCase):
        """Shared plumbing: one QApplication, one tab per test."""

        @classmethod
        def setUpClass(cls):
            cls.app = QApplication.instance() or QApplication([])
            from zbemt.gui import app as gui
            cls.gui = gui

        def _tab_for(self, project):
            state = self.gui.AppState()
            tab = self.gui.DesignTab(state)
            state.set_project(project)
            return tab

        def _pump(self, predicate, timeout_s: float) -> bool:
            """Pumps the event loop until ``predicate()`` holds."""
            deadline = time.time() + timeout_s
            while time.time() < deadline:
                self.app.processEvents()
                if predicate():
                    return True
                time.sleep(0.02)
            self.app.processEvents()
            return predicate()


@unittest.skipUnless(_HAS_QT, "PyQt6 not installed in this environment")
class TestDesignTabConstruction(DesignTabBase):
    """Construction, variant seeding from origin_params, row editing."""

    def test_tab_constructs_with_fast_project(self):
        tab = self._tab_for(_make_project())
        self.assertEqual(tab.variants_table.rowCount(), 1)
        self.assertEqual(tab.variables_table.rowCount(), 1)
        self.assertFalse(tab.btn_compare_run.isEnabled() is False)

    def test_base_row_seeds_from_tapered_origin_params(self):
        tab = self._tab_for(_make_project())
        cells = [tab.variants_table.item(0, c).text()
                 for c in range(tab.variants_table.columnCount())]
        self.assertEqual(cells, ["base", "0.1", "0.04", "14", "2", "2"])

    def test_rectangular_geometry_fills_both_chord_cells(self):
        from zbemt import geometry
        from zbemt.models import Project
        geom = geometry.generate_rectangular(chord_norm=0.09,
                                              twist_root_deg=10.0,
                                              twist_tip_deg=4.0,
                                              n_stations=8)
        airfoil = AirfoilDef(source="analytical", stall_model="clip")
        project = Project(name="ret", geometry=geom, airfoil=airfoil,
                           config=dict(Ne=6, Npsi=8, solver="fixed_point",
                                       max_iter=80))
        tab = self._tab_for(project)
        cells = [tab.variants_table.item(0, c).text()
                 for c in range(tab.variants_table.columnCount())]
        self.assertEqual(cells, ["base", "0.09", "0.09", "10", "4", "2"])

    def test_elliptic_geometry_disables_the_tip_chord_cell(self):
        from zbemt import geometry
        from zbemt.models import Project
        geom = geometry.generate_elliptic(max_chord_norm=0.12,
                                           twist_root_deg=12.0,
                                           twist_tip_deg=3.0,
                                           n_stations=8)
        airfoil = AirfoilDef(source="analytical", stall_model="clip")
        project = Project(name="ell", geometry=geom, airfoil=airfoil,
                           config=dict(Ne=6, Npsi=8, solver="fixed_point",
                                       max_iter=80))
        tab = self._tab_for(project)
        cells = [tab.variants_table.item(0, c).text()
                 for c in range(tab.variants_table.columnCount())]
        self.assertEqual(cells[1], "0.12")
        tip_item = tab.variants_table.item(0, tab._COL_TIP_CHORD)
        self.assertFalse(bool(tip_item.flags() & Qt.ItemFlag.ItemIsEditable))

    def test_add_variant_duplicates_base_row_with_new_label(self):
        tab = self._tab_for(_make_project())
        tab._add_variant_row()
        self.assertEqual(tab.variants_table.rowCount(), 2)
        self.assertEqual(tab.variants_table.item(1, 0).text(), "variant 1")
        self.assertEqual(tab.variants_table.item(1, 1).text(),
                         tab.variants_table.item(0, 1).text())

    def test_remove_selected_removes_one_row(self):
        tab = self._tab_for(_make_project())
        tab._add_variant_row()
        tab.variants_table.setCurrentCell(1, 0)
        tab.btn_remove_variant.click()
        self.assertEqual(tab.variants_table.rowCount(), 1)

    def test_conditions_label_reflects_saved_cases(self):
        tab = self._tab_for(_make_project())
        self.assertIn("no saved cases", tab.lbl_conditions.text())
        tab.state.project.saved_cases.append(
            FlightCondition(name="c1", mu_x=0.1, collective_deg=8.0, rpm=600.0))
        tab._update_conditions_label()
        self.assertIn("1 saved cases per geometry",
                      tab.lbl_conditions.text())

    def test_tab_survives_empty_project_and_propeller_mode(self):
        state = self.gui.AppState()
        tab = self.gui.DesignTab(state)          # no project yet
        self.assertEqual(tab.variants_table.rowCount(), 0)
        state.set_project(_make_project(config={"is_propeller": True}))
        self.assertEqual(tab.variants_table.rowCount(), 1)

    def test_definition_tooltips_follow_the_quoted_key_convention(self):
        """The field-index tooling collects fields from the first quoted
        token of each tooltip (`"max_evals" - ...`)."""
        tab = self._tab_for(_make_project())
        for widget, key in ((tab.opt_name_edit, "name"),
                            (tab.objective_kind_combo, "objective_kind"),
                            (tab.objective_key_combo, "objective_key"),
                            (tab.method_combo, "method"),
                            (tab.max_evals_spin, "max_evals"),
                            (tab.mu_x_spin, "mu_x"),
                            (tab.collective_spin, "collective_deg"),
                            (tab.vz_spin, "Vz"),
                            (tab.rpm_spin, "rpm")):
            tip = widget.toolTip().strip()
            self.assertTrue(tip.startswith(f'"{key}"'),
                            f"{key}: {tip[:40]!r}")


@unittest.skipUnless(_HAS_QT, "PyQt6 not installed in this environment")
class TestSaveDefinition(DesignTabBase):
    """Saving upserts into project.optimizations AND reaches disk."""

    def test_save_definition_persists_into_project_and_disk(self):
        from zbemt import api
        with tempfile.TemporaryDirectory() as tmp:
            project_path = Path(tmp) / "proj"
            project = api.new_project(str(project_path), name="design_proj")
            tab = self._tab_for(project)
            tab.opt_name_edit.setText("study A")
            with helpers.patch_message_box_everywhere("QMessageBox"):
                tab._save_definition()

            self.assertEqual(len(project.optimizations), 1)
            saved = project.optimizations[0]
            self.assertEqual(saved.name, "study A")
            self.assertEqual(saved.objective_kind, "maximize")
            self.assertEqual(saved.objective_key, "FM")
            self.assertEqual(saved.method, "powell")
            self.assertEqual(saved.max_evals, 40)
            self.assertEqual(len(saved.variables), 1)
            self.assertEqual(saved.variables[0].param, "tip_chord_norm")
            self.assertAlmostEqual(saved.variables[0].lower, 0.02)
            self.assertAlmostEqual(saved.variables[0].upper, 0.12)
            self.assertIsNotNone(saved.condition)
            self.assertEqual(saved.condition.rpm, 1500)
            self.assertTrue((project_path / "inputs" / "optimizations.bemt").exists())

            # Saving under the SAME name replaces the entry (upsert);
            # a different name adds a second study.
            tab.max_evals_spin.setValue(45)
            with helpers.patch_message_box_everywhere("QMessageBox"):
                tab._save_definition()
            self.assertEqual(len(project.optimizations), 1)
            self.assertEqual(project.optimizations[0].max_evals, 45)

            tab.opt_name_edit.setText("study B")
            with helpers.patch_message_box_everywhere("QMessageBox"):
                tab._save_definition()
            self.assertEqual(len(project.optimizations), 2)
            self.assertEqual([o.name for o in project.optimizations],
                             ["study A", "study B"])

    def test_reopening_a_project_loads_the_first_saved_study(self):
        from zbemt import api
        with tempfile.TemporaryDirectory() as tmp:
            project_path = Path(tmp) / "proj"
            project = api.new_project(str(project_path), name="reload_proj")
            tab = self._tab_for(project)
            tab.opt_name_edit.setText("stored study")
            tab.objective_key_combo.setCurrentText("CT")
            with helpers.patch_message_box_everywhere("QMessageBox"):
                tab._save_definition()

            reopened = api.open_project(str(project_path))
            tab2 = self._tab_for(reopened)
            self.assertEqual(tab2.opt_name_edit.text(), "stored study")
            self.assertEqual(tab2.objective_key_combo.currentText(), "CT")


@unittest.skipUnless(_HAS_QT, "PyQt6 not installed in this environment")
class TestOptimizeRun(DesignTabBase):
    """End-to-end optimization on a tiny mesh, offscreen, real engine."""

    def test_optimize_run_completes_and_updates_best_label_and_canvas(self):
        tab = self._tab_for(_make_project())
        tab.max_evals_spin.setValue(6)
        with helpers.patch_message_box_everywhere("QMessageBox"):
            tab._run_optimization()
            self.assertIsNotNone(tab._opt_worker)
            done = self._pump(lambda: tab._opt_worker is None, 60.0)

        self.assertTrue(done, "optimization did not finish within the timeout")
        self.assertIn("finished", tab.opt_status.text())
        self.assertTrue(tab.best_label.text().startswith("FM best ="),
                        tab.best_label.text())
        self.assertIn(" at {", tab.best_label.text())
        self.assertGreaterEqual(tab.opt_progress.value(), 1)
        # The convergence canvas carries the evaluation line plus the
        # running-best step line.
        lines = tab.convergence_canvas.simple.ax.get_lines()
        self.assertGreaterEqual(len(lines), 2)


@unittest.skipUnless(_HAS_QT, "PyQt6 not installed in this environment")
class TestCompareRun(DesignTabBase):
    """Geometry comparison over two tiny variants."""

    def test_compare_two_variants_populates_results_table_and_canvas(self):
        tab = self._tab_for(_make_project())
        tab._add_variant_row()
        tab.variants_table.item(1, tab._COL_TIP_CHORD).setText("0.08")
        with helpers.patch_message_box_everywhere("QMessageBox"):
            tab._run_comparison()
            self.assertIsNotNone(tab._compare_worker)
            done = self._pump(lambda: tab._compare_worker is None, 60.0)

        self.assertTrue(done, "comparison did not finish within the timeout")
        self.assertIn("Comparison finished", tab.compare_status.text())
        table = tab.results_table
        self.assertEqual(table.columnCount(), 2)
        self.assertGreaterEqual(table.rowCount(), 1)
        headers = {table.horizontalHeaderItem(j).text()
                   for j in range(table.columnCount())}
        self.assertEqual(headers, {"base", "variant 1"})
        value = float(table.item(0, 0).text())
        self.assertTrue(value == value)          # not NaN
        lines = sum(len(ax.get_lines()) for ax in
                    tab.compare_canvas._current.figure.axes)
        self.assertGreater(lines, 0)


@unittest.skipUnless(_HAS_QT, "PyQt6 not installed in this environment")
class TestCancelOptimization(DesignTabBase):
    """Cancel stops a long optimization between evaluations, no crash."""

    def test_cancel_stops_a_large_max_evals_run_without_crash(self):
        from zbemt.bemt import SolveCancelled

        calls = {"n": 0}

        def slow_solver(_project, condition, should_cancel=None):
            calls["n"] += 1
            time.sleep(0.03)
            if should_cancel is not None and should_cancel():
                raise SolveCancelled()
            return Results(summary={"FM": 0.4 + 0.01 * calls["n"],
                                     "CT": 0.005}, maps={},
                            condition_name=condition.name)

        tab = self._tab_for(_make_project())
        tab.max_evals_spin.setValue(500)
        with unittest.mock.patch("zbemt.studies.run_single_case",
                                  side_effect=slow_solver), \
             helpers.patch_message_box_everywhere("QMessageBox"):
            tab._run_optimization()
            self.assertTrue(self._pump(lambda: tab.opt_progress.value() >= 2, 15.0),
                            "the run never reached two evaluations")
            tab._cancel_optimization()
            self.assertFalse(tab.btn_optimize_cancel.isEnabled())
            done = self._pump(lambda: tab._opt_worker is None, 30.0)

        self.assertTrue(done, "worker did not stop after cancel")
        self.assertIn("canceled", tab.opt_status.text())
        self.assertLess(calls["n"], 500)
        self.assertGreaterEqual(len(tab._opt_history), 1)


if __name__ == "__main__":
    unittest.main()
