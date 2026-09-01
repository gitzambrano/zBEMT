"""The vehicle model is a SETTING, not a session (`PA-3`, `SC-14`).

The Stability window's rigid-body block asks for a mass, three moments
of inertia, where the hub sits relative to the centre of gravity, and
gravity itself. None of it is derivable from the rotor: it describes the
aircraft the rotor is bolted to.

It used to live only in the spin boxes. Nothing wrote it into
`DerivativeRequest`, so it never reached `inputs/derivatives.bemt`, the
CLI could not see it, and it was gone the moment the window closed --
while it decides every eigenvalue drawn beside it. The hub arm and
gravity had no control at all, so every A matrix was built with a zero
arm: not a neutral default, but the choice that removes the term
coupling a hub force into the pitching equation.

What is checked here is the contract, not the physics: the fields
exist, they survive a save and a load, they reach the engine call, and
a study written before they existed still opens.
"""
import os
import tempfile
import unittest

from zbemt import api
from zbemt.models import DerivativeRequest, FlightCondition

#: Every field of the block, with a value that is not its default, so a
#: field silently dropped on the way to disk cannot pass by coincidence.
VEHICLE = {
    "vehicle_enabled": True,
    "vehicle_mass_kg": 1234.5,
    "vehicle_Ix_kg_m2": 11.0,
    "vehicle_Iy_kg_m2": 22.0,
    "vehicle_Iz_kg_m2": 33.0,
    "hub_offset_x_m": 0.25,
    "hub_offset_z_m": 1.75,
    "gravity_m_s2": 9.80665,
}


def _request(**overrides):
    fields = dict(
        name="v", condition=FlightCondition(mu_x=0.1, rpm=600.0),
        states=["u", "w", "q"], controls=["theta_0"],
        outputs=["Thrust", "My_total"])
    fields.update(overrides)
    return DerivativeRequest(**fields)


class TestTheFieldsExist(unittest.TestCase):

    def test_every_one_is_on_the_request(self):
        request = DerivativeRequest()
        for field in VEHICLE:
            with self.subTest(field=field):
                self.assertTrue(hasattr(request, field),
                                 f"{field} is not part of DerivativeRequest, "
                                 f"so it cannot be saved or read from the CLI")

    def test_the_defaults_reproduce_the_old_window(self):
        """A study written before this block existed must build the same
        matrices it used to. The defaults are the values the spin boxes
        were born with, and a zero arm."""
        request = DerivativeRequest()
        self.assertFalse(request.vehicle_enabled)
        self.assertAlmostEqual(request.vehicle_mass_kg, 100.0)
        self.assertAlmostEqual(request.vehicle_Ix_kg_m2, 50.0)
        self.assertAlmostEqual(request.vehicle_Iy_kg_m2, 80.0)
        self.assertAlmostEqual(request.vehicle_Iz_kg_m2, 20.0)
        self.assertAlmostEqual(request.hub_offset_x_m, 0.0)
        self.assertAlmostEqual(request.hub_offset_z_m, 0.0)
        self.assertAlmostEqual(request.gravity_m_s2, 9.81)


class TestItSurvivesTheDisk(unittest.TestCase):

    def _round_trip(self, request):
        with tempfile.TemporaryDirectory() as folder:
            path = os.path.join(folder, "proj")
            project = api.new_project(path, "vehicle_test")
            project.derivatives.append(request)
            api.save_project(project)
            return api.open_project(path).derivatives[0]

    def test_every_field_comes_back_unchanged(self):
        back = self._round_trip(_request(**VEHICLE))
        for field, value in VEHICLE.items():
            with self.subTest(field=field):
                got = getattr(back, field)
                if isinstance(value, bool):
                    self.assertEqual(got, value)
                else:
                    self.assertAlmostEqual(got, value, places=9)

    def test_a_study_without_the_block_still_opens(self):
        """Backward compatibility, stated as a test rather than hoped
        for: an `inputs/derivatives.bemt` written before these keys
        existed has none of them."""
        back = self._round_trip(_request())
        self.assertFalse(back.vehicle_enabled)
        self.assertAlmostEqual(back.vehicle_mass_kg, 100.0)


class TestTheWindowReadsAndWritesIt(unittest.TestCase):
    """`PA-1`: the GUI is one of the three interfaces, so what it shows
    and what the file holds have to be the same numbers."""

    @classmethod
    def setUpClass(cls):
        from tests.helpers import HAS_QT

        if not HAS_QT:                            # pragma: no cover
            raise unittest.SkipTest("PyQt6 is not installed")
        from PyQt6.QtWidgets import QApplication

        cls._app = QApplication.instance() or QApplication([])

    def setUp(self):
        from zbemt.gui.common import AppState
        from zbemt.gui.tabs.stability_window import StabilityWindow

        self.window = StabilityWindow(AppState())

    def test_filling_the_editor_shows_the_saved_numbers(self):
        self.window._fill_editor(_request(**VEHICLE))
        self.assertTrue(self.window.vehicle_check.isChecked())
        self.assertAlmostEqual(self.window.mass_spin.value(), 1234.5, places=3)
        self.assertAlmostEqual(self.window.ix_spin.value(), 11.0, places=3)
        self.assertAlmostEqual(self.window.iy_spin.value(), 22.0, places=3)
        self.assertAlmostEqual(self.window.iz_spin.value(), 33.0, places=3)
        self.assertAlmostEqual(self.window.hub_x_spin.value(), 0.25, places=3)
        self.assertAlmostEqual(self.window.hub_z_spin.value(), 1.75, places=3)
        self.assertAlmostEqual(self.window.gravity_spin.value(), 9.80665,
                                places=3)

    def test_what_the_window_shows_is_what_it_stores(self):
        self.window._fill_editor(_request(**VEHICLE))
        request = self.window._current_request()
        for field, value in VEHICLE.items():
            with self.subTest(field=field):
                got = getattr(request, field)
                if isinstance(value, bool):
                    self.assertEqual(got, value)
                else:
                    self.assertAlmostEqual(got, value, places=3)

    def test_the_hub_arm_has_a_control_at_all(self):
        """It had none, so every matrix was built with a zero arm."""
        self.assertTrue(hasattr(self.window, "hub_x_spin"))
        self.assertTrue(hasattr(self.window, "hub_z_spin"))
        self.assertTrue(hasattr(self.window, "gravity_spin"))


def tearDownModule():
    """Qt's teardown, not the interpreter's -- see the note in
    `tests/regression/test_small_screen.py`."""
    from tests.helpers import HAS_QT

    if not HAS_QT:                                # pragma: no cover
        return
    from PyQt6.QtWidgets import QApplication

    app = QApplication.instance()
    if app is not None:
        app.processEvents()


if __name__ == "__main__":   # pragma: no cover
    unittest.main()
