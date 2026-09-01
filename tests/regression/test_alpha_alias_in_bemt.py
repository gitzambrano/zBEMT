"""An angle is an input in all THREE interfaces (`PA-1`).

The GUI lets the axial component be given as an angle and converts it on
the spot. The CLI has `--alpha-rotor-deg` and `--alpha-disk-deg`. A
`.bemt` file had neither: `alpha_rotor_deg` is not a field of
`FlightCondition`, so the key was dropped with a warning and the case
went on to solve at Vz = 0 -- level flight instead of the descent that
was asked for, and a plausible number at the end.

What is checked here is that the file now accepts the angle, that it
produces the SAME velocity the GUI and the CLI produce from it, that
nothing new is written back to disk, and that every way of stating the
angle ambiguously is refused rather than guessed at.
"""
import json
import math
import os
import tempfile
import unittest

from zbemt import api
from zbemt.models import (BatchDefinition, FlightCondition, ManeuverDefinition,
                          ManeuverPoint, save_bemt_list)

RPM = 600.0
RADIUS = 2.0
MU_X = 0.20
ALPHA = -8.0


def _project(folder, **files):
    """A project on disk whose condition files are written RAW, so a key
    that no dataclass has can be put in one."""
    path = os.path.join(folder, "proj")
    project = api.new_project(path, "alpha_alias")
    project.geometry.radius_m = RADIUS
    api.save_project(project)
    paths = api.default_project_paths(path)
    for key, payload in files.items():
        with open(paths[key], "w", encoding="utf-8") as f:
            json.dump(payload, f)
    return path


def _case(**overrides):
    raw = {"name": "descent", "mu_x": MU_X, "rpm": RPM, "collective_deg": 8.0}
    raw.update(overrides)
    return raw


class TestTheAngleIsAccepted(unittest.TestCase):

    def test_alpha_rotor_becomes_the_axial_velocity(self):
        with tempfile.TemporaryDirectory() as folder:
            path = _project(folder,
                            saved_cases=[_case(alpha_rotor_deg=ALPHA)])
            case = api.open_project(path).saved_cases[0]
        expected = api.vv_from_alpha_deg(ALPHA, MU_X, RPM, RADIUS)
        self.assertAlmostEqual(case.Vz, expected, places=9)

    def test_it_is_the_same_number_the_gui_and_the_cli_produce(self):
        """One conversion, not three. A second formula anywhere is how
        the two alpha definitions drifted apart before."""
        with tempfile.TemporaryDirectory() as folder:
            path = _project(folder,
                            saved_cases=[_case(alpha_rotor_deg=ALPHA)])
            case = api.open_project(path).saved_cases[0]
        self.assertAlmostEqual(
            api.alpha_deg_from_vv(case.Vz, MU_X, RPM, RADIUS), ALPHA,
            places=9)

    def test_a_negative_alpha_gives_a_positive_vz(self):
        """The convention, stated as a test: alpha_rotor is positive when
        the stream arrives from BELOW the disk, and Vz is positive from
        above to below. A negative alpha therefore descends."""
        with tempfile.TemporaryDirectory() as folder:
            path = _project(folder,
                            saved_cases=[_case(alpha_rotor_deg=-10.0)])
            case = api.open_project(path).saved_cases[0]
        self.assertGreater(case.Vz, 0.0)

    def test_alpha_disk_sets_the_in_plane_component_instead(self):
        """Measured from the SHAFT, so the dependency inverts: the axial
        component is the known one. This is the propeller's case."""
        with tempfile.TemporaryDirectory() as folder:
            path = _project(folder, saved_cases=[
                {"name": "cross", "Vz": 40.0, "rpm": RPM,
                 "alpha_disk_deg": 6.0}])
            case = api.open_project(path).saved_cases[0]
        omega_r = RPM * 2.0 * math.pi / 60.0 * RADIUS
        expected = math.tan(math.radians(6.0)) * 40.0 / omega_r
        self.assertAlmostEqual(case.mu_x, expected, places=9)

    def test_it_reaches_a_batch_and_a_maneuver_too(self):
        """Every file that carries a condition, not only `cases.bemt`.
        A file the resolver forgets is a file whose angle is silently
        ignored, which is the defect itself."""
        with tempfile.TemporaryDirectory() as folder:
            path = _project(
                folder,
                batches=[{"name": "b", "conditions":
                          [_case(alpha_rotor_deg=ALPHA)]}],
                maneuvers=[{"name": "m", "points":
                            [{"t_s": 0.0, "mu_x": MU_X, "rpm": RPM,
                              "alpha_rotor_deg": ALPHA}]}])
            project = api.open_project(path)
        expected = api.vv_from_alpha_deg(ALPHA, MU_X, RPM, RADIUS)
        self.assertAlmostEqual(project.batches[0].conditions[0].Vz, expected,
                               places=9)
        self.assertAlmostEqual(project.maneuvers[0].points[0].Vz, expected,
                               places=9)


class TestNothingNewIsStored(unittest.TestCase):
    """The angle is an INPUT ALIAS. `mu_x` and `Vz` stay the only stored
    form of the flight condition, so there is no second copy of one axis
    that a later edit could leave disagreeing with the first."""

    def test_saving_writes_the_velocity_and_not_the_angle(self):
        with tempfile.TemporaryDirectory() as folder:
            path = _project(folder,
                            saved_cases=[_case(alpha_rotor_deg=ALPHA)])
            project = api.open_project(path)
            api.save_project(project)
            with open(api.default_project_paths(path)["saved_cases"],
                      encoding="utf-8") as f:
                raw = json.load(f)
        self.assertNotIn("alpha_rotor_deg", raw[0])
        self.assertIn("Vz", raw[0])
        self.assertAlmostEqual(
            raw[0]["Vz"], api.vv_from_alpha_deg(ALPHA, MU_X, RPM, RADIUS),
            places=9)

    def test_a_project_that_uses_no_angle_is_untouched(self):
        with tempfile.TemporaryDirectory() as folder:
            path = _project(folder, saved_cases=[_case(Vz=3.5)])
            case = api.open_project(path).saved_cases[0]
        self.assertAlmostEqual(case.Vz, 3.5)
        self.assertAlmostEqual(case.mu_x, MU_X)


class TestAnUnusableAngleIsRefused(unittest.TestCase):
    """Refusing is the point. The original defect was not that the angle
    was unsupported: it was that it was dropped in SILENCE and the case
    solved at Vz = 0 anyway."""

    def _open(self, **files):
        with tempfile.TemporaryDirectory() as folder:
            api.open_project(_project(folder, **files))

    def test_both_angles_at_once(self):
        with self.assertRaises(ValueError) as caught:
            self._open(saved_cases=[_case(alpha_rotor_deg=-8.0,
                                          alpha_disk_deg=6.0)])
        self.assertIn("alpha_disk_deg", str(caught.exception))

    def test_alpha_rotor_together_with_a_nonzero_vz(self):
        with self.assertRaises(ValueError) as caught:
            self._open(saved_cases=[_case(alpha_rotor_deg=-8.0, Vz=3.0)])
        self.assertIn("Vz", str(caught.exception))

    def test_alpha_disk_together_with_a_nonzero_mu_x(self):
        with self.assertRaises(ValueError) as caught:
            self._open(saved_cases=[{"name": "c", "mu_x": 0.2, "Vz": 40.0,
                                     "rpm": RPM, "alpha_disk_deg": 6.0}])
        self.assertIn("mu_x", str(caught.exception))

    def test_an_angle_without_an_rpm(self):
        """Vz = -tan(alpha) * mu_x * Omega R. With no Omega the angle
        does not define a velocity, and defaulting to zero is exactly
        the silent wrong answer this replaces."""
        raw = _case(alpha_rotor_deg=ALPHA)
        raw.pop("rpm")
        with self.assertRaises(ValueError) as caught:
            self._open(saved_cases=[raw])
        self.assertIn("rpm", str(caught.exception))


class TestTheOldBehaviorIsGone(unittest.TestCase):

    def test_the_angle_no_longer_warns_as_an_unknown_field(self):
        """It used to be reported as a field that does not exist, which
        pointed the reader at the schema instead of at the fact that the
        condition was about to run at the wrong angle."""
        import warnings

        with tempfile.TemporaryDirectory() as folder:
            path = _project(folder,
                            saved_cases=[_case(alpha_rotor_deg=ALPHA)])
            with warnings.catch_warnings(record=True) as caught:
                warnings.simplefilter("always")
                api.open_project(path)
        self.assertFalse(
            [w for w in caught if "alpha_rotor_deg" in str(w.message)],
            "the angle is understood now, so it must not be reported as an "
            "unknown key")


if __name__ == "__main__":   # pragma: no cover
    unittest.main()
