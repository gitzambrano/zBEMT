"""Every unit offered by the two flight-condition fields must convert.

The unit dropdown of `widgets.LongitudinalInput` and
`widgets.AxialInput` is the field's own label: choosing "Vₓ [m/s]" and
typing 5 must mean five metres per second, not the number five in
whatever unit the engine happens to prefer.

`CONDITION_UNITS` names the velocity variable of the in-plane slot
``"Vx"``, but the two conversion helpers of `LongitudinalInput` tested
for ``"V"``. No branch matched, both helpers returned ``None``, and the
caller's fallback handed the raw number to the engine as ``mu_x``. A
rotor asked for V_x = 5 m/s was solved at mu_x = 5 -- roughly a hundred
times the intended speed, with no message anywhere.

The structural test below is the one that keeps the defect from coming
back under a different name: it asserts that EVERY variable the unit
table offers is understood by the widget that offers it (`PR-1`).
"""
import unittest

from tests.helpers import HAS_QT as _HAS_QT

if not _HAS_QT:                                  # pragma: no cover
    raise unittest.SkipTest("PyQt6 is not installed (the engine and CLI run "
                            "without it on purpose)")

from PyQt6.QtWidgets import QApplication

from zbemt import api
from zbemt.gui.widgets import (CONDITION_UNITS, AxialInput, LongitudinalInput,
                               unit_label_variable)

#: A radius and an RPM whose tip speed is exactly 100 m/s, so that a
#: velocity of 5 m/s is a round mu_x = 0.05 and a failed conversion is
#: unmistakable in the assertion message.
RADIUS_M = 5.0
RPM = 20.0 * 60.0 / (2.0 * 3.141592653589793)     # omega = 20 rad/s


class _ConditionWidgetTest(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def _longitudinal(self, is_propeller=False):
        field = LongitudinalInput()
        field.set_context_provider(lambda: (RPM, RADIUS_M))
        field.set_default_unit(is_propeller)
        return field

    def _axial(self, is_propeller=False):
        field = AxialInput()
        field.set_context_provider(lambda: (0.2, RPM, RADIUS_M))
        field.set_default_unit(is_propeller)
        return field


class TestVelocityUnitIsRead(_ConditionWidgetTest):
    """The reported defect: a velocity typed in m/s reached the engine
    unconverted."""

    def test_rotor_Vx_in_m_per_s_becomes_mu_x(self):
        field = self._longitudinal(is_propeller=False)
        field.unit_combo.setCurrentText("Vₓ [m/s]")
        field.spin.setValue(5.0)
        self.assertAlmostEqual(field.mu_x(), 0.05, places=9,
                                msg="V_x = 5 m/s at OmegaR = 100 m/s is "
                                    "mu_x = 0.05, not the raw number typed")

    def test_propeller_cross_flow_in_m_per_s_becomes_mu_x(self):
        """Same slot, propeller convention: the field is the CROSS flow
        and its velocity unit is labeled V_z."""
        field = self._longitudinal(is_propeller=True)
        field.unit_combo.setCurrentText("V_z [m/s]")
        field.spin.setValue(5.0)
        self.assertAlmostEqual(field.mu_x(), 0.05, places=9)

    def test_writing_mu_x_back_shows_metres_per_second(self):
        field = self._longitudinal(is_propeller=False)
        field.unit_combo.setCurrentText("Vₓ [m/s]")
        field.set_mu(0.05)
        self.assertAlmostEqual(field.spin.value(), 5.0, places=6)

    def test_switching_to_metres_per_second_converts_the_value(self):
        """Switching the unit must rewrite the number, not relabel it."""
        field = self._longitudinal(is_propeller=False)
        field.unit_combo.setCurrentText("μₓ")
        field.spin.setValue(0.05)
        field.unit_combo.setCurrentText("Vₓ [m/s]")
        self.assertAlmostEqual(field.spin.value(), 5.0, places=6)

    def test_switching_back_from_metres_per_second_converts_the_value(self):
        field = self._longitudinal(is_propeller=False)
        field.unit_combo.setCurrentText("Vₓ [m/s]")
        field.spin.setValue(5.0)
        field.unit_combo.setCurrentText("μₓ")
        self.assertAlmostEqual(field.spin.value(), 0.05, places=6)

    def test_axial_velocity_is_read_in_both_modes(self):
        rotor = self._axial(is_propeller=False)
        rotor.unit_combo.setCurrentText("V_z [m/s]")
        rotor.spin.setValue(5.0)
        self.assertAlmostEqual(rotor.vv(0.2, RPM, RADIUS_M), 5.0, places=9)
        prop = self._axial(is_propeller=True)
        prop.unit_combo.setCurrentText("Vₓ [m/s]")
        prop.spin.setValue(5.0)
        self.assertAlmostEqual(prop.vv(0.2, RPM, RADIUS_M), 5.0, places=9)


class TestEveryOfferedUnitConverts(_ConditionWidgetTest):
    """The structural guard.

    A unit the widget offers but cannot convert is a silent wrong
    answer, so the table and the conversion helpers are checked against
    each other rather than one example at a time."""

    def test_every_in_plane_unit_round_trips(self):
        for is_propeller in (False, True):
            field = self._longitudinal(is_propeller)
            for label, var in CONDITION_UNITS[("inplane", is_propeller)]:
                if var == "alpha_disk":
                    continue      # derived from the axial component
                with self.subTest(propeller=is_propeller, unit=label):
                    field.unit_combo.setCurrentText(label)
                    self.assertEqual(field.variable_name(), var)
                    shown = field._value_in(label, 0.05)
                    self.assertIsNotNone(
                        shown, f"unit {label!r} ({var}) has no way to display "
                                "a mu_x -- the field would show the wrong number")
                    self.assertAlmostEqual(field._mu_from(label, shown), 0.05,
                                            places=9)

    def test_every_axial_unit_round_trips(self):
        for is_propeller in (False, True):
            field = self._axial(is_propeller)
            for label, var in CONDITION_UNITS[("axial", is_propeller)]:
                with self.subTest(propeller=is_propeller, unit=label):
                    field.unit_combo.setCurrentText(label)
                    self.assertEqual(field.variable_name(), var)
                    field.set_vv(5.0, 0.2, RPM, RADIUS_M)
                    # The tolerance is the spinbox's own resolution, not
                    # the arithmetic's: the value makes a round trip
                    # through a field that stores a finite number of
                    # decimals. What the test rejects is a unit that
                    # comes back a factor away, not one that comes back
                    # a millimetre per second away.
                    self.assertAlmostEqual(
                        field.vv(0.2, RPM, RADIUS_M), 5.0, delta=1e-3,
                        msg=f"unit {label!r} ({var}) does not round-trip")

    def test_labels_are_unique_within_a_slot(self):
        """`unit_label_variable` searches both modes, so a label reused
        between them with a DIFFERENT variable would resolve to
        whichever came first."""
        for slot in ("inplane", "axial"):
            seen = {}
            for is_propeller in (False, True):
                for label, var in CONDITION_UNITS[(slot, is_propeller)]:
                    self.assertEqual(seen.setdefault(label, var), var,
                                        f"{label!r} means two things in {slot}")
                    self.assertEqual(unit_label_variable(slot, label), var)


if __name__ == "__main__":
    unittest.main()
