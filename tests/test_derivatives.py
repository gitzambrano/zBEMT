"""Verify the stability-derivative engine inputs (SC-14, Item 4).

Phase 4.1 physics: the sideslip angle rotates the in-plane free stream
without disturbing anything at its inert default of zero, and the hub
angular rates reach the aerodynamics and the flap balance with the signs
rotating-frame kinematics demand -- the pitch damping must come out
negative, and the flap response to a steady pitch rate must lag the rate
by about ninety degrees in hover.
"""

import math
import unittest

import numpy as np

from dataclasses import replace

from zbemt import api
from zbemt.bemt import BEMTConfig
from zbemt.models import FlightCondition
from tests.helpers import make_studies_project


def _project(**cfg):
    return make_studies_project(Ne=10, Npsi=24, **cfg)


def _condition(project, **overrides):
    base = FlightCondition(name="d", mu_x=0.0, collective_deg=8.0,
                            rpm=600.0)
    return replace(base, **overrides)


class TestSideslip(unittest.TestCase):
    def test_config_default_is_zero(self):
        self.assertEqual(BEMTConfig().inflow_sideslip_deg, 0.0)

    def test_explicit_zero_matches_the_legacy_condition(self):
        project = _project()
        cond = _condition(project, mu_x=0.2)
        legacy = replace(cond, sideslip_deg=0.0)
        a = api.run_case(project, cond).summary
        b = api.run_case(project, legacy).summary
        for key in ("Thrust", "Torque", "CT", "CP", "CH", "CY"):
            self.assertEqual(a[key], b[key], key)

    def test_sideslip_of_ninety_swaps_the_in_plane_forces(self):
        """The rotor is axisymmetric under rotating the in-plane flow by
        ninety degrees: thrust and torque are unchanged, and the
        in-plane/side force pair swaps (the side force picks up the sign
        its axis convention gives it)."""
        project = _project()
        a = api.run_case(project, _condition(
            project, mu_x=0.25, sideslip_deg=0.0)).summary
        b = api.run_case(project, _condition(
            project, mu_x=0.25, sideslip_deg=90.0)).summary
        self.assertLess(abs(a["Thrust"] - b["Thrust"]) / a["Thrust"], 1e-3)
        self.assertLess(abs(a["Torque"] - b["Torque"]) / a["Torque"],
                         1e-2)
        # The swap: H(0) reappears as Y(90), Y(0) as -H(90); the minus is
        # the fixed axes' handedness under the +90 deg rotation.
        self.assertLess(abs(abs(a["CH"]) - abs(b["CY"]))
                         / max(abs(a["CH"]), 1e-12), 0.05)
        self.assertLess(abs(abs(a["CY"]) - abs(b["CH"]))
                         / max(abs(b["CH"]), 1e-12), 0.05)

    def test_summary_reports_the_sideslip_back(self):
        project = _project()
        summary = api.run_case(project, _condition(
            project, mu_x=0.2, sideslip_deg=15.0)).summary
        self.assertAlmostEqual(summary["sideslip_deg"], 15.0)


class TestHubRates(unittest.TestCase):
    def _flapping_project(self, hinge_offset_norm=0.05, lock_number=8.0):
        project = _project()
        dynamics = project.geometry.dynamics
        dynamics.flap_model = "offset"
        dynamics.hinge_offset_norm = hinge_offset_norm
        dynamics.lock_number = lock_number
        return project

    def test_rigid_blade_with_a_hub_rate_takes_the_motion_path(self):
        """A rigid blade cannot flap, but the rate still moves every
        element out of the disk plane: the loads must change."""
        project = _project()   # flap_model stays "rigid"
        zero = api.run_case(project, _condition(project)).summary
        rated = api.run_case(project, _condition(
            project, q_rate_deg_s=30.0)).summary
        self.assertGreater(abs(rated["CY"] - zero["CY"])
                            + abs(rated["CH"] - zero["CH"]), 1e-6)

    def test_flap_response_to_a_pitch_rate_lags_about_ninety_degrees(self):
        """In hover, the periodic flap response to a steady pitch rate
        lags the forcing by close to the classic ninety degrees."""
        project = self._flapping_project(hinge_offset_norm=0.12)
        result = api.run_case(project, _condition(
            project, q_rate_deg_s=20.0))
        beta_1c, beta_1s = result.maps["beta_coeffs"][1]
        amplitude = math.hypot(beta_1c, beta_1s)
        self.assertGreater(amplitude, 1e-4,
                            "a pitch rate must excite the 1/rev flap")
        phase = math.degrees(math.atan2(beta_1s, beta_1c))
        lag = (phase - 90.0) % 360.0   # forcing sin(psi) peaks at 90 deg
        self.assertTrue(0.0 < lag < 180.0,
                         f"the response must LAG, got {lag:.1f} deg")
        self.assertLess(abs(lag - 90.0), 5.0,
                         f"hover lag was {lag:.2f} deg, expected ~90")

    def test_pitch_damping_is_negative(self):
        """The failure mode this input set must never ship: a hub moment
        that aids the pitch rate instead of opposing it."""
        project = self._flapping_project(hinge_offset_norm=0.05)
        h = 2.0   # deg/s, central difference around zero
        plus = api.run_case(project, _condition(
            project, q_rate_deg_s=h)).summary
        minus = api.run_case(project, _condition(
            project, q_rate_deg_s=-h)).summary
        dmy_dq = ((plus["My_total"] - minus["My_total"])
                   / (2.0 * math.radians(h)))
        self.assertLess(dmy_dq, 0.0,
                         f"pitch damping dMy/dq = {dmy_dq:.4f} must be "
                         "negative")

    def test_roll_and_pitch_rates_are_reported_back(self):
        project = _project()
        summary = api.run_case(project, _condition(
            project, p_rate_deg_s=7.5, q_rate_deg_s=-3.0)).summary
        self.assertAlmostEqual(summary["p_rate_deg_s"], 7.5)
        self.assertAlmostEqual(summary["q_rate_deg_s"], -3.0)


class TestDerivativeEngine(unittest.TestCase):
    """Phase 4.2: the finite-difference machinery itself."""

    def _request(self, project, **overrides):
        from zbemt.models import DerivativeRequest
        base = DerivativeRequest(
            name="d",
            condition=_condition(project),
            trim="none",
            states=["w"],
            controls=["theta_0"],
            outputs=["Thrust", "H", "Y", "Mx_total", "My_total", "Torque"],
            richardson_check=True)
        return replace(base, **overrides)

    def test_zero_and_negative_steps_are_rejected_by_name(self):
        project = _project()
        for bad in (0.0, -0.5):
            request = self._request(project,
                                     steps={"w": bad})
            with self.assertRaises(ValueError) as ctx:
                api.compute_derivatives(project, request)
            self.assertIn("w", str(ctx.exception))

    def test_unknown_variable_is_rejected(self):
        project = _project()
        request = self._request(project, states=["u", "not_a_state"])
        with self.assertRaises(ValueError) as ctx:
            api.compute_derivatives(project, request)
        self.assertIn("not_a_state", str(ctx.exception))

    def test_heave_damping_is_negative_in_hover(self):
        """The most basic rotor result: thrust falls when the rotor
        climbs (QR-8). Needs no reference data."""
        project = _project()
        outcome = api.compute_derivatives(
            project, self._request(project, controls=[]))
        value = outcome.matrix[("Thrust", "w")]
        self.assertLess(value, 0.0,
                         f"dThrust/dw = {value:.3f} must be negative")

    def test_thrust_rises_with_collective(self):
        for mu_x in (0.0, 0.15):
            with self.subTest(mu_x=mu_x):
                project = _project()
                request = self._request(project, states=[])
                request = replace(request,
                                   condition=_condition(project,
                                                         mu_x=mu_x))
                outcome = api.compute_derivatives(project, request)
                self.assertGreater(outcome.matrix[("Thrust",
                                                    "theta_0")], 0.0)

    def test_halving_the_step_stays_within_the_reported_error(self):
        """Linearity: the machinery's own error estimate bounds what a
        step refinement can change."""
        project = _project()
        outcome = api.compute_derivatives(project, self._request(project))
        # Re-run with the half step and compare against the first run.
        half = self._request(project, steps={"theta_0": 0.05})
        outcome_half = api.compute_derivatives(project, half)
        reported = outcome.step_error[("Thrust", "theta_0")]
        a = outcome.matrix[("Thrust", "theta_0")]
        b = outcome_half.matrix[("Thrust", "theta_0")]
        change = abs(a - b) / max(abs(a), 1e-12)
        # The Richardson estimate compares h vs h/2 on the SAME run; the
        # independent re-run may differ slightly more, so allow the
        # reported error plus a small margin.
        self.assertLessEqual(change, max(reported * 1.5, 0.02),
                              f"step refinement moved dT/dtheta_0 by "
                              f"{change:.3%}, reported error "
                              f"{reported:.3%}")

    def test_cancellation_between_solves_raises(self):
        from zbemt.bemt import SolveCancelled
        project = _project()
        request = self._request(project, richardson_check=False)
        calls = {"n": 0}

        def stop_after_first(_project, _condition):
            calls["n"] += 1
            if calls["n"] > 1:
                raise SolveCancelled()
            return {}

        with self.assertRaises(SolveCancelled):
            api.compute_derivatives(project, request, run_case=stop_after_first)

    def test_progress_reports_every_solve(self):
        project = _project()
        seen = []
        api.compute_derivatives(project, self._request(project),
                                 on_progress=lambda done, total:
                                     seen.append((done, total)))
        self.assertGreaterEqual(len(seen), 4)   # base + 4 perturbations

    def test_request_round_trips_through_a_bemt_file(self):
        import tempfile
        from pathlib import Path
        from zbemt.models import (DerivativeRequest, load_bemt_list,
                                   save_bemt_list)
        project = _project()
        request = self._request(project)
        with tempfile.TemporaryDirectory() as d:
            path = str(Path(d) / "derivatives.bemt")
            save_bemt_list([request], path)
            loaded = load_bemt_list(DerivativeRequest, path)[0]
        self.assertEqual(loaded.name, request.name)
        self.assertEqual(loaded.states, ["w"])
        self.assertEqual(loaded.trim, "none")
        self.assertTrue(loaded.richardson_check)


if __name__ == "__main__":
    unittest.main()
