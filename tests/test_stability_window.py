"""Verify the Stability Derivatives window (SC-14).

Headless, the same way the optimizer-window tests drive theirs: real
AppState with an in-memory project, gating per PR-2 (visible but
disabled), one synchronous worker run so the matrix table fills
deterministically with a stubbed solver, and sign checks that read
PASS on a healthy toy.
"""

import math
import os
import unittest
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6.QtWidgets import QApplication

from zbemt.models import DerivativeRequest, FlightCondition
from tests.helpers import make_studies_project


def _stub_summary(project, condition, should_cancel=None):
    """A linear toy: every load is an exact linear function of the
    state, so each finite difference comes out EXACT and the sign
    checks are meaningful."""
    class _R:
        pass
    r = _R()
    rpm = float(condition.rpm or 600.0)
    u = condition.mu_x * rpm * 2 * math.pi / 60.0   # rough physical speed
    w = condition.Vz
    p = getattr(condition, "p_rate_deg_s", 0.0)
    q = getattr(condition, "q_rate_deg_s", 0.0)
    theta = condition.collective_deg
    r.summary = {
        "Thrust": 5000.0 - 25.0 * abs(w) - 3.0 * w + 80.0 * theta,
        "Torque": 300.0,
        "H": 10.0 * u,
        "Y": 8.0 * (p / 57.3),
        "Mx_total": -0.5 * (p / 57.3),
        "My_total": -2.0 * (q / 57.3),
        "convergence_pct": 100.0,
    }
    return r


class StabilityWindowBase(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls._app = QApplication.instance() or QApplication([])

    def setUp(self):
        from zbemt.gui.common import AppState
        from zbemt.gui.tabs.stability_window import StabilityWindow
        self.state = AppState()
        self.window = StabilityWindow(self.state)

    def _load_project(self, flap_model="offset"):
        project = make_studies_project()
        project.saved_cases = [FlightCondition(name="trim", mu_x=0.0,
                                                collective_deg=8.0,
                                                rpm=600.0)]
        project.geometry.dynamics.flap_model = flap_model
        project.geometry.dynamics.hinge_offset_norm = 0.12
        project.derivatives.append(DerivativeRequest(
            name="study",
            condition=project.saved_cases[0],
            trim="none",
            states=["w", "q"], controls=["theta_0"],
            outputs=["Thrust", "My_total"]))
        self.state.project = project
        self.window._refresh_from_project()
        return project


class TestConstruction(StabilityWindowBase):
    def test_opens_with_an_empty_project(self):
        self.assertEqual(self.window.study_combo.count(), 0)
        self.assertFalse(self.window.btn_run.isEnabled())

    def test_project_populates_and_enables_the_run(self):
        self._load_project()
        self.assertEqual(self.window.study_combo.count(), 1)
        self.assertTrue(self.window.btn_run.isEnabled())
        request = self.window._current_request()
        self.assertEqual(request.states, ["w", "q"])
        self.assertEqual(request.trim, "none")


class TestGating(StabilityWindowBase):
    def test_rigid_blade_disables_rates_and_cyclic_but_keeps_them_visible(
            self):
        """PR-2: a control that cannot act stays on screen, greyed out,
        saying why in its tooltip."""
        self._load_project(flap_model="rigid")
        for name in ("p", "q", "theta_1c", "theta_1s"):
            check = self.window.var_checks[name]
            self.assertFalse(check.isEnabled(), name)
            self.assertTrue(check.isVisibleTo(check.parentWidget()), name)
            self.assertIn("no flap freedom", check.toolTip())
        # The zero-flapping trim has nothing to solve on a rigid blade.
        idx = self.window.trim_combo.findData("cyclic_flapback")
        model_item = self.window.trim_combo.model().item(idx)
        self.assertFalse(model_item.isEnabled())

    def test_flapping_blade_keeps_everything_enabled(self):
        self._load_project(flap_model="offset")
        for name in ("p", "q", "theta_1c", "theta_1s"):
            self.assertTrue(self.window.var_checks[name].isEnabled())


class TestRunFillsTheMatrix(StabilityWindowBase):
    def test_matrix_sign_checks_and_vehicle_after_a_run(self):
        project = self._load_project(flap_model="offset")
        request = self.window._current_request()
        captured = {}
        worker = None
        from zbemt.gui.workers import DerivativeWorker
        worker = DerivativeWorker(project, request)
        worker.finished.connect(
            lambda payload: captured.__setitem__("payload", payload))
        worker.failed.connect(
            lambda msg: captured.__setitem__("error", msg))
        with patch("zbemt.studies.run_single_case", _stub_summary):
            worker.run()   # synchronous on purpose
        self.assertNotIn("error", captured, captured.get("error"))
        self.assertIn("payload", captured)
        outcome = captured["payload"]
        self.window._on_finished(outcome)

        columns = [self.window.matrix_table.horizontalHeaderItem(c).text()
                    for c in range(self.window.matrix_table.columnCount())]
        self.assertEqual(columns[0], "output")
        rows = {self.window.matrix_table.verticalHeaderItem(r).text()
                 for r in range(self.window.matrix_table.rowCount())}
        self.assertEqual(rows, {"Thrust", "My_total"})

        # Sign checks read PASS on this healthy toy.
        text = self.window.sign_panel.text()
        self.assertIn("Heave damping: PASS", text)
        self.assertIn("Pitch damping: PASS", text)
        self.assertIn("Collective thrust: PASS", text)

        # The vehicle block becomes available once u/v/w/p/q/Omega ran;
        # this study only perturbed w/q/theta_0, so it stays disabled.
        self.assertFalse(self.window.vehicle_check.isEnabled())


if __name__ == "__main__":
    unittest.main()
