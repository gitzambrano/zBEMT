"""The convention of the two flight-speed components changes with MODE.

The engine always decomposes the velocity the same way -- ``mu_x`` in the
disk plane, ``Vz`` along the shaft. What changes between rotor and
propeller is which component carries the flight speed: for a helicopter
in forward flight it is the in-plane one; for a propeller in straight
flight it is the AXIAL one.

Labeled "Advance"/"Axial flow" in both modes, the longitudinal field used
to invite the propeller user to put the aircraft's speed there -- which
enters as edgewise flow and produces the solution of an edgewise rotor
that no propeller in straight flight ever experiences. Plausible and
wrong, with nothing on screen saying otherwise.

In a second pass, the AXES rotated along with it (see
`tests/test_propeller_axes_convention.py`): in propeller mode x is the
rotor axis, the dimensionless advance ratio J_x lives in the AXIAL field,
and the in-plane field becomes the cross-flow -- with the angle measured
from the AXIS (alpha_disk, 0° in straight cruise), not from the plane.
"""
import unittest

from tests.helpers import HAS_QT as _HAS_QT

# `zbemt.gui.common` itself needs Qt, so the import below cannot be reached
# without it -- and the CI job that installs the base dependencies only (to
# prove the engine runs without Qt) must see this module SKIPPED, not a
# collection error.
if not _HAS_QT:                                  # pragma: no cover
    raise unittest.SkipTest("PyQt6 is not installed (the engine and CLI run "
                            "without it on purpose)")

from PyQt6.QtWidgets import QApplication, QFormLayout

from zbemt.gui.common import condition_label_and_tooltip


class TestTextsPerMode(unittest.TestCase):
    """The texts themselves -- pure table, no GUI assembled."""

    def test_longitudinal_label_changes_convention(self):
        rotor, _ = condition_label_and_tooltip(False, "inplane")
        prop, _ = condition_label_and_tooltip(True, "inplane")
        self.assertNotEqual(rotor, prop)
        self.assertIn("in-plane", rotor.lower())
        self.assertIn("cross", prop.lower())
        self.assertIn("in-plane", prop.lower())

    def test_axial_label_becomes_propeller_advance(self):
        """On the rotor this field is climb/descent; on the propeller it
        is THE advance ratio.

        The row LABEL ("Axial (along-shaft) Flow:") does not change text
        between modes -- it describes the AXIS, not the unit chosen
        within it. What brings the Jₓ the user is looking for is the unit
        combo (`CONDITION_UNITS[("axial", True)]`), not the label."""
        rotor, _ = condition_label_and_tooltip(False, "axial")
        prop, _ = condition_label_and_tooltip(True, "axial")
        self.assertIn("axial", rotor.lower())
        self.assertIn("axial", prop.lower())

    def test_tooltips_keep_field_name_for_help(self):
        """`field_help` derives the field from the first quoted token of
        the tooltip: without it, the "?" popup disappears from the row."""
        for is_propeller in (False, True):
            for slot, prefix in (("inplane", '"mu_x"'), ("axial", '"Vz"')):
                with self.subTest(propeller=is_propeller, slot=slot):
                    _label, tooltip = condition_label_and_tooltip(is_propeller, slot)
                    self.assertTrue(tooltip.startswith(prefix), tooltip[:40])

    def test_propeller_tooltip_says_cross_field_is_zero_in_cruise(self):
        """The mistake this help exists to prevent: putting the
        aircraft's speed in the in-plane field. It has to say that field
        is zero in straight cruise -- and where the speed goes instead."""
        _label, tooltip = condition_label_and_tooltip(True, "inplane")
        # The requirement is what the sentence SAYS, not how it opens:
        # the text comes from `nomenclature`, which may word it as
        # "In straight cruise ...".
        self.assertIn("straight cruise", tooltip.lower())
        self.assertIn("V<sub>z</sub> = 0", tooltip)
        self.assertIn("axial field below", tooltip)

    def test_propeller_tooltip_carries_classic_J_in_axial_field(self):
        """J_x = V/(nD) with V AXIAL is the J_x from propeller charts --
        and it is the field's default. The help has to bring the formula,
        otherwise the user does not know whether this is it or the
        in-plane pi*mu_x."""
        _label, tooltip = condition_label_and_tooltip(True, "axial")
        self.assertIn("V/(nD)", tooltip)
        self.assertIn("AXIAL", tooltip)

    def test_propeller_tooltip_explains_alpha_from_AXIS(self):
        """In propeller axes the angle is measured from the AXIS: 0° is
        aligned cruise. It lives in the in-plane field because it is the
        one that, from the known axial value, produces the cross-flow
        one."""
        _label, tooltip = condition_label_and_tooltip(True, "inplane")
        self.assertIn("&alpha;<sub>disk</sub>", tooltip)
        self.assertIn("shaft", tooltip)
        # The tooltip is rich text, so the degree sign may be the entity.
        self.assertTrue("0°" in tooltip or "0&deg;" in tooltip,
                        "the tooltip does not state that 0 degrees is aligned flow")


@unittest.skipUnless(_HAS_QT, "PyQt6 not installed")
class TestLabelsInWindow(unittest.TestCase):
    """The real labels, on the assembled window, switching mode."""

    @classmethod
    def setUpClass(cls):
        from zbemt.gui.app import MainWindow
        from tests.helpers import make_studies_project
        cls.app = QApplication.instance() or QApplication([])
        cls.win = MainWindow()
        cls.win.state.set_project(make_studies_project())
        cls.tabs_map = {cls.win.tabs.tabText(i).replace("*", "").strip(): cls.win.tabs.widget(i)
                        for i in range(cls.win.tabs.count())}

    @classmethod
    def tearDownClass(cls):
        # see `tests/test_airfoil_geometry.py`: `close()` on a window
        # that went through several state changes freezes the process on
        # this machine; hiding it is enough to not interfere with the next
        # test file. But `hide()` alone leaves the actual C++-side teardown
        # to whatever order Python's interpreter-shutdown GC happens to run
        # in -- which is what crashed the process (access violation) right
        # after the last test here. Force it now instead, while the
        # QApplication and event loop are still in a known-good state.
        cls.win.hide()
        win, cls.win = cls.win, None
        win.deleteLater()
        cls.app.processEvents()
        del win
        import gc
        gc.collect()

    def _reset_mode(self, propeller: bool):
        """Enters the mode coming from the OTHER one, so that the unit
        combos get rebuilt.

        The window is shared by the whole class (`setUpClass`), and
        `set_default_unit` purposely respects the unit the user chose by
        hand within a mode: without the round trip, an earlier test that
        changed the unit leaves its choice still in effect here."""
        self._set_mode(not propeller)
        self._set_mode(propeller)

    def _set_mode(self, propeller: bool):
        self.win.state.project.config["is_propeller"] = propeller
        self.win.state.mode_changed.emit()
        self.app.processEvents()

    def _label_of(self, form, field) -> str:
        target = getattr(field, "_help_container", None) or field
        row, _role = form.getWidgetPosition(target)
        item = form.itemAt(row, QFormLayout.ItemRole.LabelRole)
        return item.widget().text() if item is not None and item.widget() else ""

    def test_run_case_switches_both_labels(self):
        """The row LABEL describes the axis (fixed by design); it is the
        unit combo within it that brings Jₓ/Cross etc. -- see
        `test_propeller_advance_is_offered_in_AXIAL_field`."""
        tab = self.tabs_map["Run Case"]
        self._set_mode(False)
        rotor = (self._label_of(tab._condition_form, tab.advance),
                 self._label_of(tab._condition_form, tab.axial))
        self._set_mode(True)
        prop = (self._label_of(tab._condition_form, tab.advance),
                self._label_of(tab._condition_form, tab.axial))
        self.assertNotEqual(rotor, prop)
        self.assertIn("axial", prop[1].lower())
        self.assertIn("Cross", prop[0])

    def test_run_batch_switches_fixed_values_and_single_row(self):
        tab = self.tabs_map["Run Batch"]
        self._set_mode(True)
        self.assertIn("axial", self._label_of(tab._fixed_form, tab.fixed_axial).lower())
        self.assertIn("axial", self._label_of(tab._case_form, tab.add_row_axial).lower())
        self.assertIn("Cross", self._label_of(tab._fixed_form, tab.fixed_advance))

    def test_axis_slots_follow_the_convention(self):
        """`axis_rows[i]` is (slot_combo, unit_combo, values_edit) -- what
        brings Jₓ/μₓ is the UNIT combo of the "axial" slot, not the slot
        combo itself (which only lists the axis NAMES -- "Axial
        (along-shaft) Flow" in both modes, see
        `test_run_case_switches_both_labels`). This test used to check
        `axis_rows[0][0]` (the slot combo) instead of `axis_rows[0][1]`
        (the unit combo) and could never have passed, in either mode --
        this is not a regression from this session."""
        tab = self.tabs_map["Run Batch"]
        slot_combo, unit_combo, _values = tab.axis_rows[0]
        axial_index = next(i for i, (_r, s) in enumerate(tab._AXIS_SLOTS)
                            if s == "axial")
        self._set_mode(True)
        slot_combo.setCurrentIndex(axial_index)
        texts = [unit_combo.itemText(i) for i in range(unit_combo.count())]
        self.assertTrue(any("Jₓ" in t for t in texts), texts)
        self._set_mode(False)
        slot_combo.setCurrentIndex(axial_index)
        texts = [unit_combo.itemText(i) for i in range(unit_combo.count())]
        self.assertTrue(any(t.startswith("α") for t in texts), texts)

    def test_propeller_advance_is_offered_in_AXIAL_field(self):
        """The bug this batch fixes: in propeller mode, J_x used to be in
        the IN-PLANE field. There J_x = pi*mu_x is the edgewise ratio --
        anyone typing 0.8 expecting the J_x from propeller charts would
        get an entirely different condition, and no velocity along the
        shaft at all.

        The unit labels use real unicode subscripts
        (`widgets.CONDITION_UNITS`): Jₓ/μₓ/Vₓ on the x axis, but
        V_z/μ_z/J_z with a literal underscore on the z axis -- the same
        asymmetry that prompted the report to the user in this session."""
        tab = self.tabs_map["Run Case"]
        self._reset_mode(True)
        axial_units = [tab.axial.unit_combo.itemText(i)
                       for i in range(tab.axial.unit_combo.count())]
        inplane_units = [tab.advance.unit_combo.itemText(i)
                         for i in range(tab.advance.unit_combo.count())]
        self.assertIn("Jₓ", axial_units)
        self.assertEqual(tab.axial.unit_combo.currentText(), "Jₓ")
        self.assertNotIn("Jₓ", inplane_units)   # the axial J_x does not live here
        self.assertIn("V_z [m/s]", inplane_units)

    def test_propeller_axial_field_does_not_offer_angle(self):
        """`Vz = tan(alpha)*V_in-plane` is ZERO in every straight axial
        flight: the disk angle cannot express a propeller's most common
        condition. Whoever wants an angle uses alpha_disk, in the
        in-plane field."""
        tab = self.tabs_map["Run Case"]
        self._reset_mode(True)
        axial_units = [tab.axial.unit_combo.itemText(i)
                       for i in range(tab.axial.unit_combo.count())]
        self.assertFalse([t for t in axial_units if t.startswith("alpha")
                           or t.startswith("α")], axial_units)
        inplane_units = [tab.advance.unit_combo.itemText(i)
                         for i in range(tab.advance.unit_combo.count())]
        self.assertIn("α_dᵢₛₖ [deg]", inplane_units)

    def test_J_x_in_axial_field_produces_axial_velocity(self):
        """The end-to-end test of the inversion: J_x=0.8 has to turn into
        a positive `Vz` and a null `mu_x` -- not the other way around."""
        tab = self.tabs_map["Run Case"]
        self._reset_mode(True)
        tab.axial.unit_combo.setCurrentText("J_x")
        tab.axial.spin.setValue(0.8)
        tab.advance.spin.setValue(0.0)
        cond = tab._current_condition()
        self.assertAlmostEqual(cond.mu_x, 0.0, places=9)
        self.assertGreater(cond.Vz, 0.0)

    def test_alpha_disk_derives_cross_from_axial(self):
        """With alpha_disk in the in-plane field, it is the axial one
        that fixes the scale -- so the resolution order inverts
        (`resolve_condition_pair`). Solved in the old order, mu_x would
        come from a Vz not yet read.

        `setCurrentText` with the old ASCII text ("Vx [m/s]") used to
        fail SILENTLY against the real item ("Vₓ [m/s]", unicode
        subscript): the combo stayed at the default (Jₓ) instead of
        changing, and the rest of the test read the wrong field -- the
        real cause of the 1200.0 != 60.0 this test used to give."""
        tab = self.tabs_map["Run Case"]
        self._reset_mode(True)
        tab.axial.unit_combo.setCurrentText("Vₓ [m/s]")
        tab.axial.spin.setValue(60.0)
        tab.advance.unit_combo.setCurrentText("α_dᵢₛₖ [deg]")
        tab.advance.spin.setValue(0.0)
        self.assertAlmostEqual(tab._current_condition().mu_x, 0.0, places=9)
        tab.advance.spin.setValue(10.0)
        cond = tab._current_condition()
        self.assertGreater(cond.mu_x, 0.0)
        self.assertAlmostEqual(cond.Vz, 60.0, places=6)

    def test_returning_to_rotor_restores_rotor_units(self):
        tab = self.tabs_map["Run Case"]
        self._reset_mode(True)
        self._set_mode(False)
        inplane_units = [tab.advance.unit_combo.itemText(i)
                         for i in range(tab.advance.unit_combo.count())]
        axial_units = [tab.axial.unit_combo.itemText(i)
                       for i in range(tab.axial.unit_combo.count())]
        self.assertEqual(inplane_units, ["μₓ", "Jₓ", "Vₓ [m/s]"])
        self.assertEqual(axial_units, ["αᵣₒₜₒᵣ [deg]", "V_z [m/s]",
                                       "μ_z", "J_z"])

    def test_switching_mode_preserves_physical_condition(self):
        """Rotating the letters cannot move the velocity from one axis to
        the other: the same (mu_x, Vz) before and after -- to 3 places,
        not 6: the mode round-trip goes through the spinbox's displayed
        text (few decimal places), so a difference on the order of 1e-4
        is display quantization, not loss of physical precision."""
        tab = self.tabs_map["Run Case"]
        self._set_mode(False)
        tab.advance.set_mu(0.15)
        before = tab._current_condition()
        self._set_mode(True)
        after = tab._current_condition()
        self.assertAlmostEqual(after.mu_x, before.mu_x, places=3)
        self.assertAlmostEqual(after.Vz, before.Vz, places=3)

    def test_propeller_axial_axis_sweeps_J_x(self):
        tab = self.tabs_map["Run Batch"]
        self._reset_mode(True)
        slot_combo, unit_combo, _values = tab.axis_rows[0]
        slot_combo.setCurrentIndex(next(i for i, (_r, s) in enumerate(tab._AXIS_SLOTS)
                                         if s == "axial"))
        units = [unit_combo.itemText(i) for i in range(unit_combo.count())]
        self.assertEqual(units, ["Jₓ", "μₓ", "Vₓ [m/s]"])
        # and the variable that goes to `studies` is the ENGINE's, not the label
        self.assertEqual(tab._axis_variable(slot_combo, unit_combo), "J_z")

    def test_switching_mode_does_not_lose_axis_choice(self):
        """Only the LABEL changes: the slot chosen on each row stays the
        same (it is what decides what goes into the condition)."""
        tab = self.tabs_map["Run Batch"]
        combo = tab.axis_rows[0][0]
        self._set_mode(False)
        combo.setCurrentIndex(next(i for i, (_r, s) in enumerate(tab._AXIS_SLOTS)
                                    if s == "axial"))
        before = tab._slot_of_combo(combo)
        self._set_mode(True)
        self.assertEqual(tab._slot_of_combo(combo), before)


if __name__ == "__main__":
    unittest.main()
