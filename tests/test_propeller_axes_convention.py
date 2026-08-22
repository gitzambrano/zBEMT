"""In propeller mode, x is the ROTOR AXIS -- not the disk plane.

The engine decomposes the flight velocity relative to the DISK: `mu_x` in the
plane, `Vz` along the axis, and calls the first component x and the second
component z. In a helicopter this coincides with the vehicle axes. In a
propeller it does not: the rotor axis points forward, in cruise ALL of the
aircraft's velocity is along it, and the table labeled that velocity as
"V_inf,z" -- a vertical component -- while the vertical component, which is
zero, appeared as "V_inf,x".

Consequences that these tests ensure:

  * A propeller's J_x is the AXIAL (`J_z` internal, shown as J_x): it is what
    enters propulsive efficiency and propeller charts;
  * The reported angle is measured from the AXIS (`alpha_disk_deg`), so level
    cruise reads 0°, not 90°;
  * `mu_x`/`J_x` disappear from the table in propeller mode -- in the engine
    they are synonyms for the IN-PLANE component, and the letter x there would
    say the opposite of what is true.

None of this is physics: the solver continues to see the pair (mu_x, Vz) and
no equation changes. It is the vocabulary -- and the wrong vocabulary puts the
aircraft's velocity in the wrong field.
"""
import math
import unittest

from tests.helpers import requires_qt

import numpy as np

from zbemt import api, bemt, studies
from zbemt.models import FlightCondition
from tests.helpers import make_studies_project


#: Geometry of the example project, so that OmegaR here is the same as
#: `studies` uses in conversions (V<->mu_x, J_z<->Vz) -- a local rotor with
#: a different radius would make the equivalence tests compare numbers from
#: two different rotors.
_BASE_PROJECT = make_studies_project()


def _rotor(rpm: float = 1200.0):
    return studies._to_rotor(_BASE_PROJECT.geometry, rpm=rpm)


def _omega_R(rpm: float = 1200.0) -> float:
    return _rotor(rpm).OmegaR


def _example_result():
    """A real `Results` -- the `summary` keys come from the engine, not from a
    dictionary built in the test (which would pass even if the engine stopped
    emitting the column)."""
    return api.run_case(
        _BASE_PROJECT,
        FlightCondition(name="ref", mu_x=0.2, Vz=3.0, collective_deg=8.0,
                         rpm=1200.0))


_ROTOR_RESULT = _example_result()


class TestAngleFromAxis(unittest.TestCase):
    """`alpha_disk_deg` is the complement of `alpha_rotor_deg`."""

    def test_purely_axial_cruise_reads_zero(self):
        cfg = bemt.BEMTConfig(is_propeller=True)
        rot = _rotor()
        _mu, _Vv, meta = bemt.resolve_advance_velocity(rot, cfg, mu_x=0.0, Vz=50.0)
        self.assertAlmostEqual(meta["alpha_rotor_deg"], 90.0, places=9)
        self.assertAlmostEqual(meta["alpha_disk_deg"], 0.0, places=9)

    def test_edgewise_flight_reads_ninety(self):
        cfg = bemt.BEMTConfig()
        _mu, _Vv, meta = bemt.resolve_advance_velocity(_rotor(), cfg, mu_x=0.3, Vz=0.0)
        self.assertAlmostEqual(meta["alpha_rotor_deg"], 0.0, places=9)
        self.assertAlmostEqual(meta["alpha_disk_deg"], 90.0, places=9)

    def test_the_two_angles_always_sum_to_ninety(self):
        """Modulo 360: `alpha_disk` is normalized to (-180°, 180°], so the
        sum closes at 90° within one revolution (see
        `bemt._angle_from_axis`)."""
        cfg = bemt.BEMTConfig()
        rot = _rotor()
        for mu_x in (-0.2, 0.0, 0.05, 0.2, 0.6):
            for Vz in (-30.0, -1.0, 0.0, 1.0, 40.0):
                with self.subTest(mu_x=mu_x, Vz=Vz):
                    _m, _v, meta = bemt.resolve_advance_velocity(rot, cfg, mu_x=mu_x, Vz=Vz)
                    total = meta["alpha_rotor_deg"] + meta["alpha_disk_deg"]
                    # difference AROUND (-180, 180]: `x % 360` returns
                    # 360.0 for a -1e-14, and the sum closes exactly this way
                    # in half the cases
                    deviation = (total - 90.0 + 180.0) % 360.0 - 180.0
                    self.assertAlmostEqual(deviation, 0.0, places=9)

    def test_angle_magnitude_is_real_angle_with_axis(self):
        """What an angle column must deliver: |alpha_disk| is the angle
        between the freestream vector and the +axis direction, in all four
        quadrants.

        Without normalization, negative crossflow AND axial descent
        (mu_x<0, Vz<0) gave 190° -- whose magnitude is not an angle at all."""
        cfg = bemt.BEMTConfig()
        rot = _rotor()
        for mu_x in (-0.4, -0.1, 0.0, 0.1, 0.4):
            for Vz in (-40.0, -1.0, 0.0, 1.0, 40.0):
                if mu_x == 0.0 and Vz == 0.0:
                    continue          # without freestream there is no angle
                with self.subTest(mu_x=mu_x, Vz=Vz):
                    _m, _v, meta = bemt.resolve_advance_velocity(rot, cfg, mu_x=mu_x, Vz=Vz)
                    vector = np.array([mu_x * rot.OmegaR, Vz])
                    real = np.degrees(np.arccos(
                        np.dot(vector, [0.0, 1.0]) / np.linalg.norm(vector)))
                    self.assertAlmostEqual(abs(meta["alpha_disk_deg"]), real,
                                            places=9)


class TestAlphaFromAxisAsInput(unittest.TestCase):
    """`alpha_disk_deg` resolves the IN-PLANE from the axial -- the inverse of
    `alpha_deg`. It is what a propeller needs: in cruise the misalignment is
    only a few degrees and the velocity scale comes from the axis, not the
    plane."""

    def test_alpha_disk_zero_nao_tem_escoamento_cruzado(self):
        cfg = bemt.BEMTConfig(is_propeller=True)
        mu_x, Vz, meta = bemt.resolve_advance_velocity(
            _rotor(), cfg, alpha_disk_deg=0.0, Vz=60.0)
        self.assertAlmostEqual(mu_x, 0.0, places=12)
        self.assertAlmostEqual(Vz, 60.0, places=12)
        self.assertAlmostEqual(meta["alpha_disk_deg"], 0.0, places=9)

    def test_alpha_disk_produces_matching_crossflow(self):
        cfg = bemt.BEMTConfig(is_propeller=True)
        rot = _rotor()
        mu_x, Vz, meta = bemt.resolve_advance_velocity(
            rot, cfg, alpha_disk_deg=10.0, Vz=60.0)
        self.assertAlmostEqual(mu_x * rot.OmegaR, math.tan(math.radians(10.0)) * 60.0,
                                places=9)
        self.assertAlmostEqual(meta["alpha_disk_deg"], 10.0, places=6)
        self.assertAlmostEqual(Vz, 60.0, places=12)

    def test_alpha_disk_accepts_dimensionless_axial(self):
        """J_x (internal `J_z`) is the natural way to specify propeller
        advance -- it must also serve as the scale for `alpha_disk`."""
        cfg = bemt.BEMTConfig(is_propeller=True)
        rot = _rotor()
        mu_x, Vz, _meta = bemt.resolve_advance_velocity(
            rot, cfg, alpha_disk_deg=0.0, J_z=0.8)
        self.assertAlmostEqual(Vz, (0.8 / np.pi) * rot.OmegaR, places=9)
        self.assertAlmostEqual(mu_x, 0.0, places=12)

    def test_both_angles_together_are_error(self):
        """`alpha_deg` derives the axial from the in-plane and `alpha_disk_deg`
        does the inverse: given both, no component fixes the scale and any
        multiple of the same vector satisfies both."""
        cfg = bemt.BEMTConfig()
        with self.assertRaises(ValueError) as ctx:
            bemt.resolve_advance_velocity(_rotor(), cfg,
                                           alpha_disk_deg=5.0, alpha_deg=85.0)
        self.assertIn("alpha_disk_deg", str(ctx.exception))

    def test_alpha_disk_with_axial_descent_does_not_flip_crossflow(self):
        """With Vz<0 (axial descent / windmill), using the raw sign of Vz
        in the conversion inverted the side the crossflow points to, and the
        reported angle no longer matched the geometry: 10° input came out as
        190°, which is not an angle at all. With |Vz|, it comes out as 170° --
        the real angle with the +axis direction."""
        cfg = bemt.BEMTConfig(is_propeller=True)
        rot = _rotor()
        mu_x, Vz, meta = bemt.resolve_advance_velocity(
            rot, cfg, alpha_disk_deg=10.0, Vz=-60.0)
        self.assertGreater(mu_x, 0.0)      # same side as with Vz>0
        self.assertAlmostEqual(meta["alpha_disk_deg"], 170.0, places=6)
        vector = np.array([mu_x * rot.OmegaR, Vz])
        real = np.degrees(np.arccos(
            np.dot(vector, [0.0, 1.0]) / np.linalg.norm(vector)))
        self.assertAlmostEqual(real, 170.0, places=6)

    def test_alpha_disk_still_requires_single_longitudinal(self):
        cfg = bemt.BEMTConfig()
        with self.assertRaises(ValueError):
            bemt.resolve_advance_velocity(_rotor(), cfg, alpha_disk_deg=5.0, mu_x=0.1)


class TestTwoAlphasOnePerMode(unittest.TestCase):
    """There are TWO angles, and each mode uses and shows only ITS OWN.

    `alpha_rotor` is measured from the DISK PLANE -- ~0 in a helicopter
    in level forward flight -- and is THE alpha for rotor mode. `alpha_disk`
    is measured from the AXIS -- 0 in level cruise -- and is THE alpha for
    propeller mode. Each is zero in the normal condition of its vehicle, which
    is what makes the number readable.

    Before this standardization the same symbol (α_disk) named the angle of the
    PLANE in rotor mode and the angle of the AXIS in propeller mode, and both
    columns appeared together in any mode: two numbers that never coincide
    under confusing names."""

    def test_each_angle_has_ONE_symbol_equal_in_both_modes(self):
        for is_propeller in (False, True):
            with self.subTest(propeller=is_propeller):
                self.assertEqual(api.summary_symbol("alpha_rotor_deg", is_propeller)[0],
                                  "&alpha;<sub>rotor</sub>")
                self.assertEqual(api.summary_symbol("alpha_disk_deg", is_propeller)[0],
                                  "&alpha;<sub>disk</sub>")

    def test_rotor_table_shows_only_rotor_alpha(self):
        ordered, _cfg = api.summary_keys_union([_ROTOR_RESULT], False)
        self.assertIn("alpha_rotor_deg", ordered)
        self.assertNotIn("alpha_disk_deg", ordered)

    def test_propeller_table_shows_only_disk_alpha(self):
        ordered, _cfg = api.summary_keys_union([_ROTOR_RESULT], True)
        self.assertIn("alpha_disk_deg", ordered)
        self.assertNotIn("alpha_rotor_deg", ordered)

    def test_both_remain_in_summary_whatever_the_mode(self):
        """Suppression is display-only: whoever exports CSV gets both keys,
        and a file saved in propeller mode re-read in rotor mode stays
        complete."""
        for key in ("alpha_rotor_deg", "alpha_disk_deg"):
            with self.subTest(key=key):
                self.assertIn(key, _ROTOR_RESULT.summary)

    def test_alpha_rotor_deg_is_accepted_as_input(self):
        """Input and output write the same quantity with the SAME name --
        before input was `alpha_deg` and output was `alpha_rotor_deg`."""
        cfg = bemt.BEMTConfig()
        rot = _rotor()
        _m1, v1, _meta1 = bemt.resolve_advance_velocity(
            rot, cfg, mu_x=0.2, alpha_deg=5.0)
        _m2, v2, _meta2 = bemt.resolve_advance_velocity(
            rot, cfg, mu_x=0.2, alpha_rotor_deg=5.0)
        self.assertAlmostEqual(v1, v2, places=12)
        with self.assertRaises(ValueError):
            bemt.resolve_advance_velocity(rot, cfg, mu_x=0.2, alpha_deg=5.0,
                                           alpha_rotor_deg=5.0)

    def test_alpha_x_name_no_longer_exists_anywhere(self):
        """Standardization: only `alpha_rotor` and `alpha_disk`."""
        import pathlib
        root = pathlib.Path(__file__).resolve().parents[1]
        leftovers = []
        for path in list((root / "zbemt").rglob("*.py")):
            if "__pycache__" in str(path):
                continue
            if "alpha_x" in path.read_text(encoding="utf-8"):
                leftovers.append(str(path.relative_to(root)))
        self.assertEqual(leftovers, [], f"still use 'alpha_x': {leftovers}")


class TestSymbolsRotateWithMode(unittest.TestCase):
    """The letters rotate; the numbers and the KEYS do not."""

    def test_axial_advance_becomes_J_x_in_propeller(self):
        self.assertEqual(api.summary_symbol("J_z", True)[0], "J<sub>x</sub>")
        self.assertEqual(api.summary_symbol("mu_z", True)[0], "&mu;<sub>x</sub>")
        self.assertEqual(api.summary_symbol("Vz", True)[0], "V<sub>x</sub>")

    def test_inplane_becomes_z_index_in_propeller(self):
        self.assertEqual(api.summary_symbol("mu_x", True)[0], "&mu;<sub>z</sub>")
        self.assertEqual(api.summary_symbol("J_x", True)[0], "J<sub>z</sub>")
        self.assertEqual(api.summary_symbol("Vx", True)[0], "V<sub>z</sub>")

    def test_total_velocity_through_disk_becomes_V_x(self):
        """`Vz` is `Vz + v_i` (the U_P from the manual): the velocity that
        crosses the disk. In propeller axes it is along the x axis."""
        self.assertEqual(api.summary_symbol("Vz", True)[0], "V<sub>x</sub>")
        self.assertEqual(api.summary_symbol("Vz", False)[0], "V<sub>z</sub>")

    def test_vi_stays_on_rotor_axis_in_both_modes(self):
        """Explicit request: v_i does not rotate -- it always has been, and
        remains, along the axis. What changes is the LETTER of that axis."""
        self.assertEqual(api.summary_symbol("Vi", True)[0],
                          api.summary_symbol("Vi", False)[0])
        self.assertIn("shaft", api.summary_symbol("Vi", True)[1].lower())

    def test_rotor_mode_changes_nothing(self):
        self.assertIs(api.summary_symbols(False), api._COLUMN_SYMBOL)

    def test_every_rotated_key_still_exists_in_rotor_mode(self):
        """An override without a corresponding key would be a symbol that
        never appears -- and the rotor mode coverage test would not catch it."""
        for key in api._COLUMN_SYMBOL_PROPELLER:
            with self.subTest(key=key):
                self.assertIn(key, api._COLUMN_SYMBOL)


class TestOutputTableInPropellerMode(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        project = make_studies_project()
        project.config["is_propeller"] = True
        cls.project = project
        cls.result = api.run_case(
            project,
            FlightCondition(name="cruise", mu_x=0.0, Vz=20.0,
                             collective_deg=8.0, rpm=1200.0))

    def test_summary_carries_angle_from_axis(self):
        self.assertIn("alpha_disk_deg", self.result.summary)
        self.assertAlmostEqual(
            self.result.summary["alpha_disk_deg"]
            + self.result.summary["alpha_rotor_deg"], 90.0, places=6)

    def test_axial_cruise_reads_zero_degree_in_right_column(self):
        self.assertAlmostEqual(self.result.summary["alpha_disk_deg"], 0.0,
                                places=6)

    def test_propeller_J_is_the_axial_one(self):
        """`J_x` (internal, in-plane) is 0 in level cruise; what matters is
        `J_z`, shown as J_x."""
        self.assertAlmostEqual(self.result.summary["J_x"], 0.0, places=9)
        self.assertGreater(self.result.summary["J_z"], 0.0)

    def _headers(self, is_propeller: bool) -> list:
        import re
        header_row = api._summary_table([self.result],
                                         is_propeller).split("</tr>")[0]
        return re.findall(r'data-tip="[^"]*">(.*?)</th>', header_row)

    def test_report_starts_by_axial_advance_in_propeller_mode(self):
        """A propeller table starts with J_x -- and the same result, read in
        rotor mode, starts with mu_x."""
        self.assertEqual(self._headers(True)[:2],
                          ["condition", "&mu;<sub>x</sub>"])
        self.assertEqual(self._headers(False)[:2],
                          ["condition", "&mu;<sub>x</sub>"])

    def test_flight_velocity_only_changes_letter(self):
        prop, rotor = self._headers(True), self._headers(False)
        self.assertIn("V<sub>x</sub>", prop)     # Vz, rotor axis
        self.assertIn("V<sub>z</sub>", rotor)      # the same Vz
        # and the engine's in-plane synonyms do not appear in propeller axes
        self.assertIn("&mu;<sub>x</sub>", rotor)
        self.assertEqual(prop.count("&mu;<sub>x</sub>"), 1)  # only mu_z, rotated

    def test_report_condition_row_renders_subscripts(self):
        from zbemt.models import Results
        result = Results(condition_name="mu_x=0.2, alpha_rotor=5",
                         summary={"mu_x": 0.2})
        table = api._summary_table([result])
        self.assertIn("&mu;<sub>x</sub>=0.2", table)
        self.assertIn("&alpha;<sub>rotor</sub>=5", table)

    def test_propeller_mode_is_inferred_from_project_and_echo(self):
        self.assertTrue(api.propeller_mode([], self.project))
        self.assertTrue(api.propeller_mode([self.result]))
        self.assertFalse(api.propeller_mode([]))


class TestFactorialInPropellerConvention(unittest.TestCase):

    def setUp(self):
        self.project = make_studies_project()
        self.project.config["is_propeller"] = True

    def test_axial_J_axis_sweeps_propeller_advance(self):
        cond = studies.build_factorial_conditions(
            self.project, [{"variable": "J_z", "values": [0.4, 0.8]}],
            fixed={"mu_x": 0.0, "rpm": 1200.0, "collective_deg": 8.0})
        self.assertEqual(len(cond), 2)
        self.assertAlmostEqual(cond[0].mu_x, 0.0, places=12)
        self.assertGreater(cond[1].Vz, cond[0].Vz)
        # and the name comes out in propeller letters
        self.assertIn("J_x=0.4", cond[0].name)

    def test_alpha_disk_derives_cross_from_axial(self):
        cond = studies.build_factorial_conditions(
            self.project, [{"variable": "alpha_disk", "values": [0.0, 10.0]}],
            fixed={"Vz": 60.0, "rpm": 1200.0, "collective_deg": 8.0})
        self.assertAlmostEqual(cond[0].mu_x, 0.0, places=12)
        self.assertGreater(cond[1].mu_x, 0.0)
        self.assertAlmostEqual(cond[0].Vz, 60.0, places=9)
        self.assertAlmostEqual(cond[1].Vz, 60.0, places=9)
        self.assertIn("α_disk=0°", cond[0].name)

    def test_alpha_disk_and_alpha_deg_together_are_error(self):
        with self.assertRaises(ValueError):
            studies.build_factorial_conditions(
                self.project, [{"variable": "alpha_disk", "values": [0.0]}],
                fixed={"alpha_deg": 85.0, "rpm": 1200.0})

    def test_same_axis_in_rotor_mode_uses_rotor_letters(self):
        self.project.config["is_propeller"] = False
        cond = studies.build_factorial_conditions(
            self.project, [{"variable": "mu_x", "values": [0.2]}],
            fixed={"rpm": 1200.0, "collective_deg": 8.0})
        self.assertIn("μ_x=0.2", cond[0].name)

    def test_mu_z_as_axial_axis_equivalent_to_Vv(self):
        cond_mu_z = studies.build_factorial_conditions(
            self.project, [{"variable": "mu_z", "values": [0.1]}],
            fixed={"mu_x": 0.0, "rpm": 1200.0, "collective_deg": 8.0})
        self.assertAlmostEqual(cond_mu_z[0].Vz, 0.1 * _omega_R(), places=6)


class TestCommandLineParity(unittest.TestCase):
    """The axial advance and angle from the axis must be reachable via the
    CLI -- it is the GUI/.bemt/CLI parity rule from CLAUDE.md."""

    #: `--project` is required in the parser; here it is just syntax noise
    _BASE = ["--project", "projects/test11"]

    def _parse(self, *extra):
        from zbemt import cli
        return cli._build_parser().parse_args(self._BASE + list(extra))

    def test_axial_flags_exist_and_are_exclusive(self):
        self.assertAlmostEqual(
            self._parse("--j-axial", "0.8", "--rpm", "2500").J_axial, 0.8)
        self.assertAlmostEqual(
            self._parse("--mu-axial", "0.25", "--rpm", "2500").mu_axial, 0.25)
        with self.assertRaises(SystemExit):
            self._parse("--j-axial", "0.8", "--v-axial", "60", "--rpm", "2500")

    def test_flags_named_by_slot_not_letter(self):
        """The letter of a component depends on the mode; a flag parsed in
        the same pass as `--project` cannot know it. `mu_x` must therefore
        never name the in-plane component on the command line -- on a
        propeller that component is shown as mu_z."""
        from zbemt import cli
        help_text = cli._build_parser().format_help()
        for flag in ("--mu-inplane", "--j-inplane", "--v-inplane",
                     "--mu-axial", "--j-axial", "--v-axial"):
            with self.subTest(flag=flag):
                self.assertIn(flag, help_text)
        for old_flag in ("--mux ", "--muz ", "--jx ", "--jz ", "--vz "):
            with self.subTest(old_flag=old_flag):
                self.assertNotIn(old_flag, help_text)

    def test_angle_from_axis_exists_and_excludes_plane_one(self):
        args = self._parse("--alpha-disk-deg", "6", "--v-axial", "65", "--rpm", "2500")
        self.assertAlmostEqual(args.alpha_disk_deg, 6.0)
        # `--alpha-disk-deg` is in the SAME mutually exclusive group as the
        # other in-plane representations: it is that component, as an angle
        with self.assertRaises(SystemExit):
            self._parse("--alpha-disk-deg", "6", "--mu-inplane", "0.1")
    def test_two_angles_on_command_line_are_rejected(self):
        """The two angles are in DIFFERENT mutually exclusive groups, so
        `argparse` accepts them: without explicit checking in `cli.run`,
        `--alpha-disk-deg 6 --alpha-rotor-deg 84` would resolve Vz from a
        still-zero mu_x and run a PAIRING in silence."""
        import io
        import contextlib
        from zbemt import cli
        argv = self._BASE + ["--alpha-disk-deg", "6", "--alpha-rotor-deg", "84",
                              "--rpm", "2500"]
        args = self._parse("--alpha-disk-deg", "6", "--alpha-rotor-deg", "84",
                            "--rpm", "2500")     # the parser accepts...
        self.assertIsNotNone(args.alpha_disk_deg)
        stderr_out = io.StringIO()
        with contextlib.redirect_stderr(stderr_out):
            code = cli.main(argv)              # ...and execution rejects
        self.assertEqual(code, 2)
        self.assertIn("same angle written two ways", stderr_out.getvalue())

    def test_every_new_flag_is_RunOptions_field(self):
        """`cli.RunOptions` is generated from the parser: a Python script
        builds the condition without building `argv`."""
        import dataclasses
        from zbemt import cli
        field_names = {f.name for f in dataclasses.fields(cli.RunOptions)}
        for name in ("alpha_disk_deg", "alpha_rotor_deg",
                     "mu_inplane", "J_inplane", "V_inplane",
                     "mu_axial", "J_axial", "V_axial"):
            with self.subTest(field=name):
                self.assertIn(name, field_names)


class TestDisplayedNomenclature(unittest.TestCase):
    """Ensures the boundary between internal keys and displayed symbols."""

    def test_report_descriptions_do_not_expose_raw_vx_vz_or_mu(self):
        from zbemt import api

        for mode in (False, True):
            for key, (_symbol, description) in api.summary_symbols(mode).items():
                rendered = api._description_with_symbols(description)
                with self.subTest(mode=mode, key=key):
                    self.assertNotRegex(rendered, r"(?<![\w])(Vx|Vz|mu_x|mu_z|J_x|J_z)(?![\w])")

    def test_report_suppresses_only_opposite_mode_alpha(self):
        from zbemt.models import Results
        from zbemt import api

        result = Results(summary={
            "alpha_rotor_deg": 1.0, "alpha_disk_deg": 89.0,
            "mu_x": 0.1, "mu_z": 0.0,
        })
        rotor, _ = api._sorted_keys([result], is_propeller=False)
        prop, _ = api._sorted_keys([result], is_propeller=True)
        self.assertIn("alpha_rotor_deg", rotor)
        self.assertNotIn("alpha_disk_deg", rotor)
        self.assertIn("alpha_disk_deg", prop)
        self.assertNotIn("alpha_rotor_deg", prop)

    @requires_qt
    def test_slot_labels_are_equal_across_tabs(self):
        from zbemt.gui.common import condition_label_and_tooltip
        from zbemt.gui.tabs.run_batch import RunBatchTab

        self.assertEqual(condition_label_and_tooltip(False, "inplane")[0],
                         "Edgewise (in-plane) Flow:")
        self.assertEqual(condition_label_and_tooltip(False, "axial")[0],
                         "Axial (along-shaft) Flow:")
        self.assertEqual(condition_label_and_tooltip(True, "inplane")[0],
                         "Cross (in-plane) Flow:")
        self.assertEqual(RunBatchTab._AXIS_SLOTS[1][0],
                         "Edgewise (in-plane) Flow")
        self.assertEqual(RunBatchTab._AXIS_SLOTS_PROPELLER["inplane"],
                         "Cross (in-plane) Flow")

    def test_help_text_renders_components_with_subscript(self):
        from zbemt import api

        text = api._description_with_symbols(
            "Use V_x and V_z with mu_x, J_x, alpha_rotor and lambda_z.")
        self.assertIn("V<sub>x</sub>", text)
        self.assertIn("V<sub>z</sub>", text)
        self.assertIn("&mu;<sub>x</sub>", text)
        self.assertIn("J<sub>x</sub>", text)
        self.assertIn("&alpha;<sub>rotor</sub>", text)
        self.assertIn("&lambda;<sub>z</sub>", text)
        self.assertIn("&alpha;<sub>rotor</sub>",
                      api._description_with_symbols("alpha_rotor_deg=-10"))
        self.assertIn("&alpha;<sub>disk</sub>",
                      api._description_with_symbols("α_disk=2"))

    def test_combo_labels_render_greek_and_subscript(self):
        from zbemt.viz import plots

        self.assertEqual(plots.summary_label_html("mu_x"),
                         "&mu;<sub>x</sub> [-]")
        self.assertEqual(plots.summary_label_html("J_x"),
                         "J<sub>x</sub> [-]")
        self.assertEqual(plots.summary_label_html("mu_z"),
                         "&mu;<sub>z</sub> [-]")


if __name__ == "__main__":
    unittest.main()
