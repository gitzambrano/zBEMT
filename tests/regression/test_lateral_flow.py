"""The lateral component of the in-plane free stream (SC-15).

The disk plane carries two directions. `FlightCondition.mu_x` gives the
longitudinal one and `FlightCondition.Vy` the lateral one, and the engine
reads the pair as one magnitude and one direction. These tests hold the
two spellings of that freedom to the same physics, hold a condition
without lateral flow to its legacy numbers, and hold every surface that
reports it to one consistent set of components.
"""
from __future__ import annotations

import math
import unittest

from zbemt import api, models, studies
from zbemt.models import FlightCondition
from zbemt.validation import validate_flight_condition

from tests.helpers import make_studies_project

RPM = 600.0


def _project():
    return make_studies_project()


def _omega_r(project) -> float:
    return api.mu_to_V(1.0, RPM, project.geometry.radius_m)


def _condition(**overrides) -> FlightCondition:
    base = dict(name="lateral", mu_x=0.2, collective_deg=8.0, rpm=RPM)
    base.update(overrides)
    return FlightCondition(**base)


class TestResolvingTheTwoComponents(unittest.TestCase):
    """`models.resolve_inplane_flow` is the one place the pair becomes a
    vector."""

    def test_no_lateral_flow_leaves_the_condition_exactly_as_it_was(self):
        for mu_x in (0.0, 0.2, -0.15):
            with self.subTest(mu_x=mu_x):
                self.assertEqual(
                    models.resolve_inplane_flow(_condition(mu_x=mu_x), 100.0),
                    (mu_x, 0.0))

    def test_the_pair_becomes_a_magnitude_and_a_direction(self):
        mu, psi_w = models.resolve_inplane_flow(
            _condition(mu_x=0.3, Vy=10.0), 100.0)
        self.assertAlmostEqual(mu, math.hypot(30.0, 10.0) / 100.0)
        self.assertAlmostEqual(psi_w, math.degrees(math.atan2(10.0, 30.0)))

    def test_the_angle_spelling_splits_the_longitudinal_component(self):
        """psi_w never sets the scale of a velocity: it takes the known
        longitudinal component and gives the lateral one its share."""
        mu, psi_w = models.resolve_inplane_flow(
            _condition(mu_x=0.3, sideslip_deg=30.0), 100.0)
        self.assertAlmostEqual(psi_w, 30.0)
        self.assertAlmostEqual(mu, 0.3 / math.cos(math.radians(30.0)))

    def test_the_two_spellings_agree_on_the_lateral_velocity(self):
        angle = _condition(mu_x=0.3, sideslip_deg=30.0)
        velocity = _condition(
            mu_x=0.3, Vy=0.3 * 100.0 * math.tan(math.radians(30.0)))
        self.assertAlmostEqual(
            models.lateral_velocity(angle, 100.0),
            models.lateral_velocity(velocity, 100.0))
        self.assertEqual(models.resolve_inplane_flow(angle, 100.0)[1],
                         models.resolve_inplane_flow(velocity, 100.0)[1])

    def test_pure_sideward_flight_is_reachable(self):
        """The angle spelling cannot express it, and the velocity one
        can: that is the reason the velocity is what a condition stores."""
        mu, psi_w = models.resolve_inplane_flow(
            _condition(mu_x=0.0, Vy=10.0), 100.0)
        self.assertAlmostEqual(mu, 0.1)
        self.assertAlmostEqual(psi_w, 90.0)

    def test_the_angle_that_names_no_velocity_is_refused(self):
        with self.assertRaises(ValueError):
            models.resolve_inplane_flow(
                _condition(mu_x=0.2, sideslip_deg=90.0), 100.0)


class TestValidationOfTheLateralFlow(unittest.TestCase):
    def test_one_spelling_at_a_time(self):
        issues = validate_flight_condition(
            _condition(Vy=10.0, sideslip_deg=5.0))
        self.assertTrue(any("given twice" in i.message for i in issues))

    def test_either_spelling_alone_is_accepted(self):
        self.assertEqual(validate_flight_condition(_condition(Vy=10.0)), [])
        self.assertEqual(
            validate_flight_condition(_condition(sideslip_deg=12.0)), [])

    def test_ninety_degrees_is_rejected_before_the_solve(self):
        issues = validate_flight_condition(_condition(sideslip_deg=90.0))
        self.assertTrue(any("-90 to 90" in i.message for i in issues))


class TestTheSolveReportsTheComponentsBack(unittest.TestCase):
    def test_the_reported_components_are_consistent(self):
        """A reader who takes atan2(V_y, V_x) from the results must get
        the sideslip angle printed beside them."""
        project = _project()
        summary = api.run_case(
            project, _condition(mu_x=0.2, Vy=10.0)).summary
        self.assertAlmostEqual(summary["Vy"], 10.0)
        self.assertAlmostEqual(summary["mu_y"], 10.0 / _omega_r(project))
        self.assertAlmostEqual(summary["J_y"], math.pi * summary["mu_y"])
        self.assertAlmostEqual(summary["mu_x"], 0.2)
        self.assertAlmostEqual(
            summary["sideslip_deg"],
            math.degrees(math.atan2(summary["Vy"], summary["Vx"])), places=6)

    def test_no_lateral_flow_reproduces_the_legacy_result(self):
        project = _project()
        plain = api.run_case(project, _condition(mu_x=0.2)).summary
        explicit = api.run_case(
            project, _condition(mu_x=0.2, Vy=0.0)).summary
        for key in ("Thrust", "Torque", "CT", "CP", "CH", "CY"):
            self.assertEqual(plain[key], explicit[key], key)
        self.assertEqual(plain["Vy"], 0.0)

    def test_the_two_spellings_produce_the_same_loads(self):
        project = _project()
        omega_r = _omega_r(project)
        angle = api.run_case(
            project, _condition(mu_x=0.2, sideslip_deg=20.0)).summary
        velocity = api.run_case(project, _condition(
            mu_x=0.2, Vy=0.2 * omega_r * math.tan(math.radians(20.0)))).summary
        for key in ("Thrust", "Torque", "CT", "CP", "CH", "CY"):
            self.assertAlmostEqual(
                angle[key], velocity[key],
                delta=abs(angle[key]) * 1e-9 + 1e-12, msg=key)

    def test_lateral_flow_raises_the_in_plane_speed(self):
        """A lateral component adds to the stream instead of turning it:
        the blade meets more speed, so the thrust rises."""
        project = _project()
        omega_r = _omega_r(project)
        plain = api.run_case(project, _condition(mu_x=0.2)).summary
        sideways = api.run_case(
            project, _condition(mu_x=0.2, Vy=0.1 * omega_r)).summary
        self.assertGreater(sideways["CT"], plain["CT"])


class TestTheLateralSlotIsAFullBatchAxis(unittest.TestCase):
    def test_a_sweep_of_the_lateral_velocity(self):
        project = _project()
        conditions = studies.build_factorial_conditions(
            project, [{"variable": "Vy", "values": [0.0, 5.0, 10.0]}],
            {"mu_x": 0.2, "rpm": RPM, "collective_deg": 8.0})
        self.assertEqual([c.Vy for c in conditions], [0.0, 5.0, 10.0])
        self.assertTrue(all(c.sideslip_deg == 0.0 for c in conditions))

    def test_a_sweep_of_the_sideslip_angle(self):
        project = _project()
        conditions = studies.build_factorial_conditions(
            project, [{"variable": "sideslip_deg", "values": [0.0, 10.0]}],
            {"mu_x": 0.2, "rpm": RPM, "collective_deg": 8.0})
        self.assertEqual([c.sideslip_deg for c in conditions], [0.0, 10.0])
        self.assertTrue(all(c.Vy == 0.0 for c in conditions))

    def test_the_ratio_spellings_convert_to_a_velocity(self):
        project = _project()
        omega_r = _omega_r(project)
        conditions = studies.build_factorial_conditions(
            project, [{"variable": "mu_y", "values": [0.05]}],
            {"mu_x": 0.2, "rpm": RPM, "collective_deg": 8.0})
        self.assertAlmostEqual(conditions[0].Vy, 0.05 * omega_r)

    def test_the_slot_cannot_be_an_axis_and_a_fixed_value_at_once(self):
        project = _project()
        with self.assertRaises(ValueError):
            studies.build_factorial_conditions(
                project, [{"variable": "Vy", "values": [0.0, 5.0]}],
                {"mu_x": 0.2, "rpm": RPM, "sideslip_deg": 10.0})


class TestTheCaseFileCarriesTheLateralFlow(unittest.TestCase):
    def test_a_saved_case_round_trips_through_bemt(self):
        import tempfile
        from pathlib import Path
        project = _project()
        project.saved_cases = [_condition(name="sideways", Vy=7.5)]
        with tempfile.TemporaryDirectory() as folder:
            project.path = str(Path(folder) / "proj")
            api.save_project(project)
            reopened = api.open_project(project.path)
        self.assertAlmostEqual(reopened.saved_cases[0].Vy, 7.5)


if __name__ == "__main__":
    unittest.main()
