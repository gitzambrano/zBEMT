"""Verify the Design Optimization window (SC-13).

The window is driven headless the same way the transient-window tests
drive theirs: a real AppState with an in-memory project, form reads and
writes, algorithm gating, and one synchronous worker run (no thread) so
the front table fills deterministically. No solver speed matters: the
evaluation function is stubbed at ``studies._evaluate_variant``.
"""

import os
import unittest
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from tests.helpers import HAS_QT

if HAS_QT:                                        # pragma: no branch
    from PyQt6.QtWidgets import QApplication

from zbemt.models import (ConstraintDef, DesignVariable, FlightCondition,
                           ObjectiveDef, OptimizationDefinition)
from tests.helpers import make_studies_project


def _stub_evaluate(project, condition, params, should_cancel=None):
    from zbemt.models import Results
    root = float(params["root_chord_norm"])
    tip = float(params["tip_chord_norm"])
    ct = 0.006 + 0.10 * (root - 0.07) + 0.05 * (tip - 0.02)
    fm = 1.50 - 3.0 * (tip - 0.02) ** 2 - 0.5 * (root - 0.07) ** 2
    return Results(summary={"CT": ct, "FM": fm})


@unittest.skipUnless(HAS_QT, "PyQt6 is not installed")
class OptimizerWindowBase(unittest.TestCase):
    """One QApplication for the whole file, one fresh window per test."""

    @classmethod
    def setUpClass(cls):
        cls._app = QApplication.instance() or QApplication([])

    def setUp(self):
        from zbemt.gui.common import AppState
        from zbemt.gui.tabs.optimizer_window import OptimizerWindow
        self.state = AppState()
        self.window = OptimizerWindow(self.state)

    def _load_project_with_study(self):
        project = make_studies_project()
        project.saved_cases = [FlightCondition(name="opt", mu_x=0.1,
                                                collective_deg=8.0,
                                                rpm=800.0)]
        project.optimizations.append(OptimizationDefinition(
            name="study",
            objectives=[ObjectiveDef(key="CT", kind="maximize"),
                         ObjectiveDef(key="FM", kind="maximize")],
            constraints=[ConstraintDef(key="CT", operator=">=", value=0.0)],
            variables=[DesignVariable(param="root_chord_norm", lower=0.07,
                                       upper=0.15),
                        DesignVariable(param="tip_chord_norm", lower=0.02,
                                        upper=0.09)],
            algorithm="nsga2", population=8, generations=3, seed=3,
            condition=project.saved_cases[0]))
        self.state.project = project
        # The window listens for project_changed; a direct assignment does
        # not fire it, so refresh explicitly.
        self.window._refresh_from_project()
        return project


class TestConstruction(OptimizerWindowBase):
    def test_opens_with_an_empty_project(self):
        self.assertEqual(self.window.study_combo.count(), 0)
        self.assertFalse(self.window.btn_run.isEnabled())

    def test_a_project_populates_the_lists_and_enables_the_run(self):
        self._load_project_with_study()
        self.assertEqual(self.window.study_combo.count(), 1)
        self.assertTrue(self.window.btn_run.isEnabled())
        definition = self.window._current_definition()
        self.assertEqual([o.key for o in definition.objectives],
                          ["CT", "FM"])
        self.assertEqual(definition.condition.rpm, 800.0)


class TestAlgorithmGating(OptimizerWindowBase):
    def test_de_disables_the_sbx_controls_but_keeps_them_visible(self):
        """PR-2: a control that has nothing to say in a configuration
        stays on screen and disabled, so the user learns it exists."""
        self._load_project_with_study()
        index = self.window.algorithm_combo.findData("de")
        self.window.algorithm_combo.setCurrentIndex(index)
        for spin in (self.window.crossover_spin, self.window.mutation_spin,
                      self.window.rate_spin):
            self.assertFalse(spin.isEnabled())
            self.assertTrue(spin.isVisibleTo(spin.parentWidget()))
        back = self.window.algorithm_combo.findData("nsga2")
        self.window.algorithm_combo.setCurrentIndex(back)
        for spin in (self.window.crossover_spin, self.window.mutation_spin,
                      self.window.rate_spin):
            self.assertTrue(spin.isEnabled())


class TestRunFillsTheFrontTable(OptimizerWindowBase):
    def test_front_table_fills_after_a_short_run(self):
        project = self._load_project_with_study()
        definition = self.window._current_definition()
        from zbemt.gui.workers import OptimizeMultiWorker
        captured = {}
        worker = OptimizeMultiWorker(project, definition)
        worker.finished.connect(
            lambda payload: captured.__setitem__("payload", payload))
        with patch("zbemt.studies._evaluate_variant", _stub_evaluate):
            worker.run()   # synchronous: no thread, deterministic
        self.assertIn("payload", captured)
        self.window._on_finished(captured["payload"])
        columns = [self.window.front_table.horizontalHeaderItem(c).text()
                    for c in range(self.window.front_table.columnCount())]
        self.assertEqual(columns, ["root_chord_norm", "tip_chord_norm",
                                    "CT", "FM"])
        self.assertGreaterEqual(self.window.front_table.rowCount(), 1)

    def test_edits_reach_the_persisted_study(self):
        project = self._load_project_with_study()
        self.window.obj_keys[1].setCurrentText("CP")
        self.window._apply_settings()
        stored = project.optimizations[0]
        self.assertEqual([o.key for o in stored.objectives],
                          ["CT", "CP"])

    def test_run_is_blocked_while_the_study_has_errors(self):
        """Phase 3.1: static findings surface BEFORE solver time.

        The GUI now offers curated engineering result quantities instead of
        accepting arbitrary internal summary keys.  Build an invalid study
        through a user-reachable error (no design variables) rather than by
        typing an engine key the GUI deliberately no longer exposes.
        """
        from unittest.mock import patch as mock_patch
        from zbemt.gui.workers import OptimizeMultiWorker

        self._load_project_with_study()
        self.window.var_table.setRowCount(0)
        self.window._apply_settings()
        launched = []
        with mock_patch("zbemt.gui.tabs.optimizer_window."
                         "OptimizeMultiWorker",
                         side_effect=lambda *a, **k:
                             launched.append(1) or object()):
            from tests.helpers import patch_message_box_everywhere
            with patch_message_box_everywhere("QMessageBox"):
                self.window._run()
        self.assertEqual(launched, [],
                          "a study with errors must not reach the worker")


if __name__ == "__main__":
    unittest.main()
