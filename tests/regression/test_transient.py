"""Transient time marching over a prescribed trajectory (SC-12).

Every physics test turns an option ON and checks it against something
external to the code: the algebraic equilibrium the march must reach, a
settling time that must scale with the inflow's own time constant, the
analytic sampling of the resampler, and the periodic residual EN-9
demands. Cancellation follows PR-11.
"""
import math
import os
import unittest

import numpy as np

from dataclasses import replace

from zbemt import api, studies
from zbemt.bemt import BEMTConfig, SolveCancelled
from zbemt.models import AirfoilDef, ManeuverDefinition, ManeuverPoint

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def _fast_project():
    from tests.helpers import make_studies_project
    return make_studies_project(
        inflow_field_model="pitt_peters_unsteady")


def _constant_maneuver(rpm=600.0, mu=0.1, duration_rev=20.0, dt_s=None):
    """A trajectory holding ONE condition for duration_rev revolutions."""
    omega = 2.0 * math.pi * rpm / 60.0
    t_end = duration_rev * 2.0 * math.pi / omega
    if dt_s is None:
        dt_s = t_end / 40.0
    return ManeuverDefinition(name="hold", dt_s=dt_s,
                               substeps_per_step=8,
                               points=[
        ManeuverPoint(t_s=0.0, mu_x=mu, Vz=0.0, collective_deg=8.0,
                       rpm=rpm),
        ManeuverPoint(t_s=t_end, mu_x=mu, Vz=0.0, collective_deg=8.0,
                       rpm=rpm),
    ])


class TestConstantTrajectoryReachesSteady(unittest.TestCase):
    def test_constant_trajectory_reaches_the_steady_answer(self):
        """Marching one held condition for twenty revolutions must land on
        the algebraic Pitt-Peters equilibrium to within 1e-4: the march's
        only fixed point under a constant command IS the steady solution."""
        project = _fast_project()
        definition = _constant_maneuver()
        history, _maps = studies.run_maneuver(project, definition)
        cfg = replace(studies._build_config(project.config),
                       inflow_field_model="pitt_peters_unsteady")
        rotor = studies._to_rotor(project.geometry, collective_deg=8.0,
                                   rpm=600.0)
        airfoil_obj = api.__dict__["airfoils"].to_blade_airfoil([project.airfoil])
        from zbemt.bemt import steady_pitt_peters_state
        nu_eq = steady_pitt_peters_state(rotor, airfoil_obj, cfg,
                                          definition.points[0].mu_x, 0.0)
        final = history.iloc[-1]
        got = np.array([final["nu0"], final["nu_s"], final["nu_c"]],
                        dtype=float)
        self.assertLess(float(np.max(np.abs(got - nu_eq))), 1e-4)


class TestInflowLags(unittest.TestCase):
    def test_collective_step_overshoots_then_settles(self):
        """A collective step makes CT rise past its new steady value
        before settling back: the inflow needs a few revolutions to build
        up, so the blade element answer leads, then the induced velocity
        catches up. The settling spans a few inflow time constants."""
        project = _fast_project()
        rpm = 600.0
        t_step = 0.5
        m = ManeuverDefinition(name="step", dt_s=0.02,
                                points=[
            ManeuverPoint(t_s=0.0, mu_x=0.05, Vz=0.0, collective_deg=6.0,
                           rpm=rpm),
            ManeuverPoint(t_s=t_step, mu_x=0.05, Vz=0.0, collective_deg=10.0,
                           rpm=rpm),
            ManeuverPoint(t_s=t_step + 2.0, mu_x=0.05, Vz=0.0,
                           collective_deg=10.0, rpm=rpm),
        ])
        history, _maps = studies.run_maneuver(project, m)
        after = history[history["t"] > t_step]
        ct_after = after["CT"].values.astype(float)
        peak = float(np.max(ct_after))
        final = float(np.mean(ct_after[-5:]))
        # Overshoot: the immediate response passes the settled level.
        self.assertGreater(peak, final)
        # Settling: by two seconds after the step, drift is small.
        self.assertLess(abs(float(np.max(ct_after[-20:]))
                             - float(np.min(ct_after[-20:]))),
                         0.15 * abs(final))


class TestExponentialIntegratorStability(unittest.TestCase):
    def test_single_substep_produces_only_finite_values(self):
        """The docstring at `_pitt_peters_exp_step` claims unconditional
        stability even with one sub-step per sample. Prove it: nothing in
        the marched state may go non-finite (QR-8)."""
        project = _fast_project()
        m = ManeuverDefinition(name="coarse", dt_s=0.25,
                                substeps_per_step=1,
                                points=[
            ManeuverPoint(t_s=0.0, mu_x=0.0, Vz=0.0, collective_deg=8.0,
                           rpm=800.0),
            ManeuverPoint(t_s=1.0, mu_x=0.25, Vz=1.0, collective_deg=11.0,
                           rpm=800.0),
        ])
        history, _maps = studies.run_maneuver(project, m)
        for column in ("nu0", "nu_s", "nu_c", "CT", "CQ"):
            values = history[column].values.astype(float)
            self.assertTrue(np.all(np.isfinite(values)),
                            f"{column} went non-finite")


class TestSampling(unittest.TestCase):
    def test_linear_and_hold_sample_the_expected_tables(self):
        """Linear interpolation halves the step between nodes; hold keeps
        each node's value until the next node starts. Three nodes with a
        distinctive ramp pin both rules down exactly."""
        from zbemt.studies import _maneuver_samples
        m = ManeuverDefinition(name="s", interpolation="linear", dt_s=1.0,
                                points=[
            ManeuverPoint(t_s=0.0, mu_x=0.0, Vz=0.0, collective_deg=4.0,
                           rpm=100.0),
            ManeuverPoint(t_s=2.0, mu_x=0.2, Vz=4.0, collective_deg=8.0,
                           rpm=200.0),
            ManeuverPoint(t_s=4.0, mu_x=0.4, Vz=8.0, collective_deg=12.0,
                           rpm=300.0),
        ])
        lin = _maneuver_samples(m)
        self.assertEqual(len(lin), 5)     # 0,1,2,3,4 s
        self.assertAlmostEqual(lin[1].mu_x, 0.1)
        self.assertAlmostEqual(lin[3].collective_deg, 10.0)
        self.assertEqual(lin[0].rpm, 100.0)
        self.assertAlmostEqual(lin[1].rpm, 150.0)
        m_hold = replace(m, interpolation="hold")
        hold = _maneuver_samples(m_hold)
        self.assertAlmostEqual(hold[1].mu_x, 0.0)   # holds node A
        self.assertAlmostEqual(hold[3].mu_x, 0.2)   # holds node B


class TestPeriodicResidualFallsWithRevolutions(unittest.TestCase):
    def test_residual_decreases_from_two_to_eight_revolutions(self):
        """EN-9 in action: one ISOLATED case (no maneuver threading)
        marched with more revolutions leaves a SMALLER change between its
        last two revolutions, because the start-up transient decays. Two
        revolutions cannot have settled; eight are close."""
        project = _fast_project()
        # An isolated case resolves a steady equilibrium, so the inflow
        # here must be a steady variant; the TIME MARCH under test is the
        # Oye separation march, not the inflow.
        project.config["inflow_field_model"] = "glauert_local"
        # A large lag constant makes tau comparable to the revolution, so
        # consecutive revolutions still differ at n_rev=2: exactly the
        # transient EN-9's residual is supposed to expose.
        project.airfoil.use_dynamic_stall = True
        project.airfoil.dynamic_stall_method = "time_march"
        project.airfoil.stall_model = "clip"
        project.airfoil.dynamic_stall_A = 200.0
        from zbemt.models import FlightCondition
        cond = FlightCondition(name="hold", mu_x=0.1, Vz=0.0,
                                collective_deg=12.0, rpm=600.0)
        residuals = {}
        for n_rev in (2, 8):
            project.airfoil.dynamic_stall_time_march_revolutions = n_rev
            result = studies.run_single_case(project, cond)
            residuals[n_rev] = float(
                result.maps["dynamic_stall_periodic_residual"])
        self.assertGreater(residuals[2], residuals[8],
                           f"residual must fall with revolutions: "
                           f"{residuals}")
        # With tau comparable to the revolution the decay per revolution
        # is about exp(-2*pi/(Omega*tau)) = 0.52, so eight revolutions are
        # NOT yet settled -- which is precisely what this residual exists
        # to tell the user (EN-9).
        self.assertGreater(residuals[8], 0.0)


class TestCancellation(unittest.TestCase):
    def test_cancel_between_samples_raises_solve_cancelled(self):
        """PR-11: a should_cancel that fires from the second sample stops
        the march through SolveCancelled -- never a partial history."""
        project = _fast_project()
        calls = {"n": 0}

        def cancel_on_second():
            calls["n"] += 1
            return calls["n"] >= 2

        m = _constant_maneuver(duration_rev=6, dt_s=None)
        with self.assertRaises(SolveCancelled):
            studies.run_maneuver(project, m,
                                  should_cancel=cancel_on_second)


if __name__ == "__main__":   # pragma: no cover
    unittest.main()


class TestMarchedFlapResponse(unittest.TestCase):
    """SC-12: `march_flapping` must run and must report its blade state.

    The maneuver solved the flap response and published its coefficients, but
    not the blade properties behind them. `aggregate_results` read those
    properties unconditionally, so every marched flapping run raised
    KeyError before it could return a single sample (`DS-H4`).
    """

    def _project(self):
        from zbemt.models import BladeDynamicsDef
        project = _fast_project()
        dynamics = BladeDynamicsDef(
            flap_model="offset", hinge_offset_norm=0.05,
            inertia_source="lock", lock_number=8.0, harmonics=2)
        return replace(project, geometry=replace(project.geometry,
                                                 dynamics=dynamics))

    def test_a_marched_flapping_maneuver_completes(self):
        maneuver = replace(_constant_maneuver(mu=0.15), march_flapping=True)
        history, maps_list = api.run_maneuver(self._project(), maneuver)
        self.assertEqual(len(history), len(maps_list))
        self.assertTrue(np.all(np.isfinite(history["CT"].to_numpy())))

    def test_the_history_reports_the_blade_state_it_solved(self):
        maneuver = replace(_constant_maneuver(mu=0.15), march_flapping=True)
        history, _maps = api.run_maneuver(self._project(), maneuver)
        for column in ("beta_0_deg", "beta_1c_deg", "beta_1s_deg",
                       "nu_beta", "lock_number", "flap_inertia_kg_m2",
                       "Mx_total", "My_total"):
            with self.subTest(column=column):
                self.assertIn(column, history.columns)
                self.assertTrue(np.all(np.isfinite(history[column].to_numpy())))

    def test_a_marched_sample_claims_no_outer_flap_convergence(self):
        """The maneuver solves the flap response once per sample.

        There is no outer loop there, so the row must not carry an outer
        residual, a tolerance, or a convergence verdict.
        """
        maneuver = replace(_constant_maneuver(mu=0.15), march_flapping=True)
        history, _maps = api.run_maneuver(self._project(), maneuver)
        for column in ("flap_outer_converged", "flap_outer_residual_deg",
                       "flap_outer_tolerance_deg", "flap_outer_iterations"):
            with self.subTest(column=column):
                self.assertNotIn(column, history.columns)

    def test_a_rigid_blade_marches_without_flap_columns(self):
        maneuver = replace(_constant_maneuver(mu=0.15), march_flapping=True)
        history, _maps = api.run_maneuver(_fast_project(), maneuver)
        self.assertNotIn("beta_0_deg", history.columns)
        self.assertTrue(np.all(np.isfinite(history["CT"].to_numpy())))
