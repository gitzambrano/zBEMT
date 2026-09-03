"""The Pitt-Peters inflow must follow the loading, in every path.

Two defects lived in this model at once (`PP-P5-ASYMMETRY`, `PP-B7`):

- The harmonic forcing was read as a pair of hub moments, which carry the
  opposite sign to the loading that drives the inflow slot. The induced
  inflow came out in anti-phase with the blade loading, which drove the
  total inflow negative over a large part of the disk and made a powered
  cruise case report negative induced power.
- The marched path skipped the wind-axis rotation that the steady path
  applies, so a nonzero sideslip made the two settle on different states.
"""
from __future__ import annotations

import math
import unittest
from dataclasses import replace

import numpy as np

from zbemt import airfoils, api, studies
from zbemt.bemt import (
    _pitt_peters_L_V,
    _pitt_peters_geometry,
    _pitt_peters_exp_step,
    steady_pitt_peters_state,
)
from zbemt.models import FlightCondition, ManeuverDefinition, ManeuverPoint


def _project(**config_overrides):
    """Return the reference rotor with a small mesh."""
    project = api.open_project("projects/starter_rotor")
    config = dict(project.config)
    config.update({
        "Ne": 24, "Npsi": 36, "use_compressibility": False,
        "pitt_peters_tol": 1e-10, "pitt_peters_outer_iter": 200,
    })
    config.update(config_overrides)
    return replace(project, config=config)


def _azimuth_of_maximum(field: np.ndarray, azimuth: np.ndarray) -> float:
    """Return the azimuth, in degrees, of one field's radial-mean maximum."""
    return float(np.degrees(azimuth[int(np.argmax(np.mean(field, axis=0)))]))


class TestHarmonicInflowFollowsTheLoading(unittest.TestCase):
    """More normal load at an azimuth must mean more induced inflow there."""

    @classmethod
    def setUpClass(cls):
        cls.maps = studies.run_single_case(
            _project(inflow_field_model="pitt_peters_steady"),
            FlightCondition(name="forward", rpm=400.0, mu_x=0.15,
                            collective_deg=8.0),
        ).maps

    def test_the_inflow_maximum_sits_near_the_loading_maximum(self):
        azimuth = np.asarray(self.maps["PSI"])[0]
        inflow = _azimuth_of_maximum(np.asarray(self.maps["lambda_i"]), azimuth)
        loading = _azimuth_of_maximum(np.asarray(self.maps["Fn"]), azimuth)
        separation = abs(((inflow - loading + 180.0) % 360.0) - 180.0)
        self.assertLess(separation, 90.0)

    def test_the_field_shares_its_phase_with_the_drees_field(self):
        drees = studies.run_single_case(
            _project(inflow_field_model="drees_local"),
            FlightCondition(name="forward", rpm=400.0, mu_x=0.15,
                            collective_deg=8.0),
        ).maps
        first = np.asarray(self.maps["lambda_i"]).ravel()
        second = np.asarray(drees["lambda_i"]).ravel()
        first = first - first.mean()
        second = second - second.mean()
        correlation = float(first @ second) / float(
            np.linalg.norm(first) * np.linalg.norm(second))
        self.assertGreater(correlation, 0.5)

    def test_forward_flight_stays_inside_the_linear_range(self):
        self.assertLessEqual(
            float(self.maps["pitt_peters_frac_reversed"]), 0.02)

    def test_a_powered_cruise_case_absorbs_power(self):
        summary = studies.run_single_case(
            _project(inflow_field_model="pitt_peters_steady"),
            FlightCondition(name="cruise", rpm=400.0, mu_x=0.18,
                            collective_deg=10.0),
        ).summary
        self.assertGreater(float(summary["Power"]), 0.0)
        self.assertGreater(float(summary["Power_i"]), 0.0)


class TestMassFlowIdentities(unittest.TestCase):
    """The mass-flow parameters carry two exact relations."""

    def test_hover_harmonic_mass_flow_is_twice_the_uniform_inflow(self):
        _gain, mass_flow = _pitt_peters_L_V(0.0, 0.08, 0.0)
        self.assertAlmostEqual(float(mass_flow[1]), 0.16, places=15)

    def test_the_forward_residual_is_the_exact_algebraic_remainder(self):
        uniform = 0.08
        for advance_ratio in (1.0, 10.0, 100.0):
            with self.subTest(advance_ratio=advance_ratio):
                _gain, mass_flow = _pitt_peters_L_V(advance_ratio, uniform, 0.0)
                total = math.sqrt(advance_ratio ** 2 + uniform ** 2)
                residual = float(mass_flow[1]) / total - 1.0
                self.assertAlmostEqual(residual, uniform ** 2 / total ** 2,
                                       places=15)

    def test_the_degenerate_state_still_gives_a_solvable_system(self):
        _gain, mass_flow = _pitt_peters_L_V(0.0, 0.0, 0.0)
        self.assertTrue(np.all(mass_flow > 0.0))


class TestSideslipIsAppliedInBothPaths(unittest.TestCase):
    """The marched and the steady path must solve the same equations."""

    def _marched_and_steady(self, sideslip_deg: float):
        marched = _project(inflow_field_model="pitt_peters_unsteady",
                           inflow_sideslip_deg=sideslip_deg)
        duration = 20.0 * 60.0 / 400.0
        maneuver = ManeuverDefinition(
            name="hold", dt_s=duration / 40.0, substeps_per_step=8,
            initial_state="zero",
            points=[
                ManeuverPoint(t_s=0.0, mu_x=0.10, Vz=0.0,
                              collective_deg=8.0, rpm=400.0),
                ManeuverPoint(t_s=duration, mu_x=0.10, Vz=0.0,
                              collective_deg=8.0, rpm=400.0),
            ],
        )
        history, _maps = api.run_maneuver(marched, maneuver)
        final = np.array([float(history["nu0"].iloc[-1]),
                          float(history["nu_s"].iloc[-1]),
                          float(history["nu_c"].iloc[-1])])

        steady = _project(inflow_field_model="pitt_peters_steady",
                          inflow_sideslip_deg=sideslip_deg)
        config = studies._build_config(steady.config, airfoil_def=steady.airfoil)
        rotor = studies._to_rotor(steady.geometry, collective_deg=8.0, rpm=400.0)
        blade = airfoils.to_blade_airfoil(
            [steady.airfoil],
            radial=airfoils.radial_reynolds_mach(rotor, config, mu_x=0.10))
        equilibrium = np.asarray(
            steady_pitt_peters_state(rotor, blade, config, 0.10, 0.0))
        return final, equilibrium

    def test_the_two_paths_agree_without_sideslip(self):
        marched, steady = self._marched_and_steady(0.0)
        self.assertLess(float(np.max(np.abs(marched - steady))), 1e-6)

    def test_the_two_paths_agree_at_thirty_degrees_of_sideslip(self):
        marched, steady = self._marched_and_steady(30.0)
        self.assertLess(float(np.max(np.abs(marched - steady))), 1e-6)

    def test_the_march_leaves_a_zero_state_in_hover(self):
        """A hover march must escape the degenerate zero inflow state."""
        project = _project(inflow_field_model="pitt_peters_unsteady")
        config = studies._build_config(project.config, airfoil_def=project.airfoil)
        rotor = studies._to_rotor(project.geometry, collective_deg=8.0, rpm=400.0)
        blade = airfoils.to_blade_airfoil(
            [project.airfoil],
            radial=airfoils.radial_reynolds_mach(rotor, config, mu_x=0.0))
        geometry = _pitt_peters_geometry(rotor, config)
        state = np.zeros(3)
        for _step in range(20):
            state, _lambda_i, _fields = _pitt_peters_exp_step(
                state, 0.1, rotor, blade, config, 0.0, 0.0, *geometry)
        self.assertGreater(float(state[0]), 0.0)


if __name__ == "__main__":
    unittest.main()
