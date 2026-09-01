"""All example projects versioned under ``projects/test1`` – ``test12``.

They are not decoration: they are the first contact for anyone who
installs zBEMT, and an example that opens with an error or returns a
number without physical sense is worse than no example at all. This file
runs all of them end to end and checks that the results fall within the
range the aircraft category requires.

The ranges are WIDE on purpose. They are not validation against measured
data. They are fences that catch gross regressions: a flipped sign, a factor of 2, a
violation of energy conservation, a rotor that stopped converging.
"""
import math
import unittest

from zbemt import api
from zbemt import paths


# test1..test10, test12 are rotors; test11 is the propeller example.
ROTOR_PROJECTS = ["test1", "test2", "test3", "test4", "test5",
                  "test6", "test7", "test8", "test9", "test10", "test12"]
ALL_PROJECTS = ROTOR_PROJECTS + ["test11"]


def _path(name: str) -> str:
    return str(paths.projects_root() / name)


def _solidity(project) -> float:
    g = project.geometry
    mean_chord = sum(g.chord_norm) / len(g.chord_norm)
    return g.n_blades * mean_chord / math.pi


class TestExampleProjectsOpen(unittest.TestCase):
    """Before any physics: the files exist, open, and are valid."""

    def test_all_open_without_error(self):
        for name in ALL_PROJECTS:
            with self.subTest(project=name):
                project = api.open_project(_path(name))
                self.assertTrue(project.name)
                self.assertGreaterEqual(len(project.geometry.r_norm), 2)
                self.assertTrue(project.saved_cases, "project without a saved case is not an example")

    def test_no_project_has_a_validation_error(self):
        """An example distributed with a validation error teaches the user
        to ignore validation."""
        for name in ALL_PROJECTS:
            with self.subTest(project=name):
                project = api.open_project(_path(name))
                errors = [i for i in api.validate_project(project, conditions=project.saved_cases)
                          if i.level == "error"]
                self.assertEqual(errors, [], [str(i) for i in errors])

    def test_round_trip_preserves_the_project(self):
        """Saving and reopening must return the same project -- it is the
        GUI/.bemt/CLI parity contract applied to distributed material."""
        import shutil
        import tempfile
        from dataclasses import asdict
        for name in ALL_PROJECTS:
            with self.subTest(project=name):
                original = api.open_project(_path(name))
                dest = tempfile.mkdtemp()
                self.addCleanup(shutil.rmtree, dest, ignore_errors=True)
                original.path = dest
                api.save_project(original)
                reopened = api.open_project(dest)
                self.assertEqual(reopened.name, original.name)
                self.assertEqual(asdict(reopened.geometry), asdict(original.geometry))
                self.assertEqual(asdict(reopened.airfoil), asdict(original.airfoil))
                self.assertEqual(dict(reopened.config), dict(original.config))


class TestRotorsInHover(unittest.TestCase):
    """Hover is the only regime in which classic rotor metrics carry the
    meaning they appear to have (see Q6 in production-plan.md: FM in
    forward flight routinely exceeds 1, and that is not a bug)."""

    def test_figure_of_merit_below_1(self):
        """FM > 1 in HOVER would mean extracting more thrust from a given
        power than the ideal actuator disk -- a violation of energy
        conservation, and the classic symptom of an inflow error."""
        for name in ROTOR_PROJECTS:
            with self.subTest(project=name):
                project = api.open_project(_path(name))
                hover_case = next(c for c in project.saved_cases if c.mu_x == 0.0 and not c.Vz)
                s = api.run_case(project, hover_case).summary
                self.assertGreater(s["FM"], 0.4, "FM too low for a plausible rotor")
                self.assertLess(s["FM"], 1.0, "FM >= 1 in hover violates the ideal limit")

    def test_blade_loading_within_category_range(self):
        """CT/sigma is the blade loading: the quantity that says whether
        the rotor is close to stall. A real rotorcraft rotor operates
        between ~0.05 and ~0.14; above that the blade stalls over a
        large part of the disk."""
        for name in ROTOR_PROJECTS:
            with self.subTest(project=name):
                project = api.open_project(_path(name))
                hover_case = next(c for c in project.saved_cases if c.mu_x == 0.0 and not c.Vz)
                s = api.run_case(project, hover_case).summary
                ct_sigma = s["CT"] / _solidity(project)
                self.assertGreater(ct_sigma, 0.03, f"CT/sigma={ct_sigma:.4f}: unloaded rotor")
                self.assertLess(ct_sigma, 0.16, f"CT/sigma={ct_sigma:.4f}: beyond stall")

    def test_thrust_and_power_positive_in_hover(self):
        for name in ROTOR_PROJECTS:
            with self.subTest(project=name):
                project = api.open_project(_path(name))
                hover_case = next(c for c in project.saved_cases if c.mu_x == 0.0 and not c.Vz)
                s = api.run_case(project, hover_case).summary
                self.assertGreater(s["Thrust"], 0.0)
                self.assertGreater(s["Power"], 0.0)

    def test_tip_mach_below_divergence(self):
        """Above M~0.9 at the tip, wave drag dominates and this code's
        Prandtl-Glauert model no longer applies."""
        for name in ROTOR_PROJECTS:
            with self.subTest(project=name):
                project = api.open_project(_path(name))
                hover_case = next(c for c in project.saved_cases if c.mu_x == 0.0 and not c.Vz)
                s = api.run_case(project, hover_case).summary
                tip_mach = s["rotor_OmegaR"] / project.config["a_sound"]
                self.assertLess(tip_mach, 0.85, f"tip Mach {tip_mach:.2f}")

    def test_all_saved_cases_converge(self):
        for name in ROTOR_PROJECTS:
            project = api.open_project(_path(name))
            for case in project.saved_cases:
                with self.subTest(project=name, case=case.name):
                    s = api.run_case(project, case).summary
                    self.assertGreater(s["convergence_pct"], 95.0)


class TestPropeller(unittest.TestCase):
    """The propeller is the example that exists to exercise
    `is_propeller=True` and the AXIAL convention for flight speed."""

    def setUp(self):
        self.project = api.open_project(_path("test11"))

    def test_flight_speed_is_axial_not_in_plane(self):
        """The propeller mode pitfall: `mu_x` is the IN-PLANE component of
        the disk. Putting flight speed there makes the blade see +-V
        along the azimuth -- what a helicopter rotor in forward flight
        sees and a propeller in straight flight never does. The examples
        use `Vz`."""
        for case in self.project.saved_cases:
            with self.subTest(case=case.name):
                self.assertEqual(case.mu_x, 0.0,
                                 "propeller speed in mu_x produces a plausible and wrong result")

    def test_propulsive_efficiency_never_exceeds_1(self):
        """eta = T*V/P > 1 is energy coming out of nowhere."""
        for case in self.project.saved_cases:
            with self.subTest(case=case.name):
                s = api.run_case(self.project, case).summary
                self.assertGreaterEqual(s["eta_prop"], 0.0)
                self.assertLess(s["eta_prop"], 1.0)

    def test_efficiency_grows_with_speed_and_is_high_in_cruise(self):
        etas = {c.name: api.run_case(self.project, c).summary["eta_prop"]
                for c in self.project.saved_cases}
        static_eta = etas["static (V=0)"]
        cruise_eta = etas["cruise 65 m/s"]
        self.assertEqual(static_eta, 0.0, "propulsive efficiency at static is 0 by definition (V=0)")
        self.assertGreater(cruise_eta, 0.7, f"cruise propeller with eta={cruise_eta:.2f} is poorly matched")

    def test_produces_thrust_across_all_saved_cases(self):
        for case in self.project.saved_cases:
            with self.subTest(case=case.name):
                s = api.run_case(self.project, case).summary
                self.assertGreater(s["Thrust"], 0.0,
                                   "propeller in windmill state: the pitch does not cover this speed")


class TestEtaPropUsaAComponenteAxial(unittest.TestCase):
    """Regression test for the bug found while building these examples.

    `eta_prop` used to be `J_x * CT_prop / CP_prop` with a LONGITUDINAL
    J_x, even though the comment right next to it said the quantity only
    has meaning with purely axial advance -- a case in which J_x = 0 and
    the formula returned zero. A correctly specified propeller reported
    zero efficiency across the whole sweep; specified wrong, it reported
    values above 1.
    """

    def setUp(self):
        self.project = api.open_project(_path("test11"))

    def test_axial_propeller_reports_nonzero_efficiency(self):
        from zbemt.models import FlightCondition
        case = FlightCondition(name="axial", mu_x=0.0, Vz=40.0, collective_deg=0.0, rpm=2500.0)
        s = api.run_case(self.project, case).summary
        self.assertEqual(s["J_x"], 0.0, "axial advance has zero longitudinal J_x, by construction")
        self.assertGreater(s["J_z"], 0.0)
        self.assertGreater(s["eta_prop"], 0.3,
                           "eta_prop reads the longitudinal component again")

    def test_eta_matches_the_T_V_over_P_definition(self):
        """Checks against the dimensional definition, not against the
        dimensionless formula -- that is the point of the test."""
        from zbemt.models import FlightCondition
        V = 40.0
        s = api.run_case(self.project, FlightCondition(
            name="axial", mu_x=0.0, Vz=V, collective_deg=0.0, rpm=2500.0)).summary
        eta_dimensional = s["Thrust"] * V / s["Power"]
        self.assertAlmostEqual(s["eta_prop"], eta_dimensional, places=6)

    def test_windmill_does_not_report_positive_efficiency(self):
        """In windmill state, thrust and power are both negative and the
        ratio turns positive again -- it would give a high 'efficiency'
        exactly where the propeller consumes energy from the flow
        instead of propelling."""
        from zbemt.models import FlightCondition
        s = api.run_case(self.project, FlightCondition(
            name="windmill", mu_x=0.0, Vz=140.0, collective_deg=0.0, rpm=2500.0)).summary
        self.assertLess(s["Thrust"], 0.0, "this speed should put the propeller in windmill state")
        self.assertEqual(s["eta_prop"], 0.0)


if __name__ == "__main__":
    unittest.main()


class TestPropellerModeGuiAndDefaults(unittest.TestCase):
    """The GUI must not push the user toward the wrong specification.

    When opening the propeller project the AXES rotate (see
    `tests/regression/test_propeller_axes_convention.py`): the AXIAL field becomes
    advance, in `J_x` -- the J_x from propeller charts, built on the
    speed along the axis --, and the in-plane field becomes the CROSS
    flow, which is zero in straight cruise.

    Before, the axial field opened on `alpha [deg]`, which left flight
    speed without a natural field and invited putting it in the
    longitudinal one -- which is the IN-PLANE component of the disk.
    Later it opened on `Vz [m/s]`, which already fixed that but still
    offered "J_x" (= pi*mu_x, the edgewise ratio) in the wrong field."""

    @classmethod
    def setUpClass(cls):
        try:
            from PyQt6.QtWidgets import QApplication
        except ImportError:                       # pragma: no cover
            raise unittest.SkipTest("PyQt6 not installed")
        cls.app = QApplication.instance() or QApplication([])

    def _tab(self, project: str):
        from zbemt.gui import app as gui
        state = gui.AppState()
        tab = gui.RunCaseTab(state)
        state.set_project(api.open_project(_path(project)))
        return tab

    def test_propeller_opens_with_advance_in_AXIAL_field(self):
        tab = self._tab("test11")
        self.assertEqual(tab.axial.unit_combo.currentText(), "Jₓ")
        self.assertEqual(tab.advance.unit_combo.currentText(), "V_z [m/s]")
        # and the in-plane "Jₓ" (pi*mu_x) is not even offered in the
        # wrong field
        inplane_units = [tab.advance.unit_combo.itemText(i)
                         for i in range(tab.advance.unit_combo.count())]
        self.assertNotIn("Jₓ", inplane_units)

    def test_rotor_still_opens_on_mu_x_and_alpha_rotor(self):
        """Standardized nomenclature: there is no more bare "mu_x" or
        "alpha" -- every component says which AXIS it belongs to (with a
        real unicode subscript, see `widgets.CONDITION_UNITS`), and
        the angle says which reference it is measured from."""
        tab = self._tab("test1")
        self.assertEqual(tab.advance.unit_combo.currentText(), "μₓ")
        self.assertEqual(tab.axial.unit_combo.currentText(), "αᵣₒₜₒᵣ [deg]")

    def test_axial_field_range_follows_the_unit(self):
        """+-90 is an angle range. In m/s it would truncate an airplane
        propeller: cruise at 65 passes, but a windmill case at 140 would
        be silently clipped."""
        tab = self._tab("test11")
        tab.axial.unit_combo.setCurrentText("Vₓ [m/s]")
        self.assertGreaterEqual(tab.axial.spin.maximum(), 200.0)

    def test_manual_user_choice_is_not_overwritten(self):
        """Within the SAME mode: the list did not change, so the choice
        holds. On a mode switch the old list stops existing and the
        field goes back to the new mode's default -- see
        `AxialInput.set_default_unit`."""
        tab = self._tab("test11")
        tab.axial.unit_combo.setCurrentText("Vₓ [m/s]")    # manual choice
        tab.axial.set_default_unit(True)                        # same mode
        self.assertEqual(tab.axial.unit_combo.currentText(), "Vₓ [m/s]")


class TestPropellerConventionWarning(unittest.TestCase):
    """The guard that catches the same mistake coming from the CLI or a
    script, where there is no widget at all to guide the user."""

    def setUp(self):
        from zbemt.models import FlightCondition
        self.FlightCondition = FlightCondition
        self.project = api.open_project(_path("test11"))

    def _propeller_warnings(self, condition):
        return [i for i in api.validate_project(self.project, conditions=[condition])
                if i.level == "warning" and "propeller" in i.message]

    def test_all_advance_in_plane_raises_warning(self):
        bad = self.FlightCondition(name="wrong", mu_x=0.3, Vz=0.0,
                                    collective_deg=0.0, rpm=2500.0)
        self.assertEqual(len(self._propeller_warnings(bad)), 1)

    def test_correct_axial_specification_raises_no_warning(self):
        good = self.FlightCondition(name="right", mu_x=0.0, Vz=65.0,
                                     collective_deg=0.0, rpm=2500.0)
        self.assertEqual(self._propeller_warnings(good), [])

    def test_tilted_axis_is_legitimate_and_raises_no_warning(self):
        """A tilt-rotor in transition genuinely has both components; only
        the TOTAL absence of an axial component is the mistake's
        signature."""
        oblique = self.FlightCondition(name="oblique", mu_x=0.1, Vz=50.0,
                                        collective_deg=0.0, rpm=2500.0)
        self.assertEqual(self._propeller_warnings(oblique), [])

    def test_rotor_with_mu_is_not_warned(self):
        rotor = api.open_project(_path("test1"))
        condition = self.FlightCondition(name="advance", mu_x=0.3, Vz=0.0,
                                          collective_deg=8.0, rpm=258.0)
        warnings = [i for i in api.validate_project(rotor, conditions=[condition])
                    if "propeller" in i.message]
        self.assertEqual(warnings, [])


class TestExampleVariety(unittest.TestCase):
    """The examples exist to exercise DIFFERENT paths in the engine.

    Five rotors with an analytical polar and the same config would
    cover just one path: variety is what makes them a test, not a
    showcase.
    """

    def test_there_is_an_example_with_tabulated_polar(self):
        """The table path is separate code -- including the slice choice
        per radial station, which only runs with `source='table'`."""
        project = api.open_project(_path("test4"))
        self.assertEqual(project.airfoil.source, "table")
        self.assertGreaterEqual(len(project.airfoil.table_slices), 3)
        reynolds = {s.reynolds for s in project.airfoil.table_slices}
        self.assertGreaterEqual(len(reynolds), 3, "table without a real Reynolds axis")

    def test_there_is_an_example_with_dynamic_stall_on(self):
        project = api.open_project(_path("test5"))
        self.assertTrue(project.airfoil.use_dynamic_stall)

    def test_examples_cover_different_polar_sources(self):
        sources = {api.open_project(_path(n)).airfoil.source for n in ALL_PROJECTS}
        self.assertIn("analytical", sources)
        self.assertIn("table", sources)

    def test_examples_cover_different_inflow_models(self):
        models = {api.open_project(_path(n)).config.get("inflow_field_model")
                  for n in ALL_PROJECTS}
        self.assertGreaterEqual(len(models), 3, f"little inflow variety: {models}")

    def test_there_is_an_example_with_and_without_compressibility(self):
        values = {bool(api.open_project(_path(n)).config.get("use_compressibility"))
                  for n in ALL_PROJECTS}
        self.assertEqual(values, {True, False},
                          "every example with the same compressibility state")

    def test_there_is_an_example_with_and_without_viterna_extension(self):
        values = {bool(api.open_project(_path(n)).airfoil.extend_full_range)
                  for n in ALL_PROJECTS}
        self.assertEqual(values, {True, False},
                          "every example with the same Viterna extension state")

    def test_there_is_an_example_with_pitt_peters(self):
        """Pitt-Peters finite-state inflow is the only dynamic inflow model in
        use; at least one example must demonstrate it as the default."""
        project = api.open_project(_path("test8"))
        self.assertEqual(project.config.get("inflow_field_model"),
                         "pitt_peters_steady")
        self.assertGreater(project.config.get("pitt_peters_outer_iter", 0), 0)

    def test_there_is_an_example_with_enhanced_stall(self):
        """Enhanced stall model (smoothed nonlinear roll-off) is different from
        clip and viterna; at least one example must use it."""
        project = api.open_project(_path("test9"))
        self.assertEqual(project.airfoil.stall_model, "enhanced")

    def test_there_is_an_example_with_multi_section_airfoil(self):
        """Multi-section (heterogeneous) airfoil distribution with 2+ radial
        sections is a real feature; at least one example must exercise it."""
        project = api.open_project(_path("test10"))
        self.assertGreaterEqual(len(project.airfoil_sections), 2)
        for section in project.airfoil_sections:
            self.assertIsNotNone(section.r_norm,
                                 "every section of a multi-section airfoil needs r_norm defined")
