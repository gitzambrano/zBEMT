"""Tests for `zbemt.airfoils`: building/dispatching airfoil models (analytical, table, CST/Bezier), polar preview vs. the engine, reverse-flow handling in the preview, unique-condition/axis-value helpers, table slicing, NACA/CST geometry generation, profile file I/O, and polar CSV import/export.
"""

import math
import tempfile
import unittest
import warnings
from pathlib import Path

import numpy as np

from zbemt import airfoils
from zbemt import validation
from zbemt.models import AirfoilDef, PolarSlice, ProfileGeometry, RotorGeometryDef
from zbemt.bemt import (
    AnalyticalAirfoil, TableAirfoil, MultiSectionTableAirfoil, ViternaExtendedAirfoil,
    HeterogeneousMultiSectionAirfoil,
)


class TestBuildAnalytical(unittest.TestCase):
    def test_converts_degrees_to_radians(self):
        a = AirfoilDef(alpha0_deg=-4.5, alpha_stall_pos_deg=15.0, alpha_stall_neg_deg=-6.0)
        af = airfoils.build_analytical(a)
        self.assertIsInstance(af, AnalyticalAirfoil)
        self.assertAlmostEqual(af.alpha0, math.radians(-4.5))
        self.assertAlmostEqual(af.alpha_stall_pos, math.radians(15.0))
        self.assertAlmostEqual(af.alpha_stall_neg, math.radians(-6.0))


class TestToAirfoilDispatch(unittest.TestCase):
    # Note: `extend_full_range=False` explicit here -- the default of
    # `AirfoilDef.extend_full_range` changed to True (see models.py, matches
    # the new default `BEMTConfig.reverse_flow_model='viterna_full_
    # range'`); these tests isolate the dispatch logic of source
    # (analytical/table/multi-section) itself, not the Viterna extension.
    def test_analytical_source(self):
        a = AirfoilDef(source="analytical", stall_model="linear")
        self.assertIsInstance(airfoils.to_airfoil(a), AnalyticalAirfoil)

    def test_table_source_single_polar(self):
        a = AirfoilDef(source="table", extend_full_range=False, table_slices=[
            PolarSlice(alpha_deg=[-5, 0, 5], cl=[-0.3, 0.2, 0.7], cd=[0.02, 0.015, 0.02]),
        ])
        self.assertIsInstance(airfoils.to_airfoil(a), TableAirfoil)

    def test_table_source_multi_section(self):
        a = AirfoilDef(source="table", extend_full_range=False, table_slices=[
            PolarSlice(alpha_deg=[-5, 0, 5], cl=[-0.3, 0.2, 0.7], cd=[0.02, 0.015, 0.02], r_norm=0.3),
            PolarSlice(alpha_deg=[-5, 0, 5], cl=[-0.2, 0.3, 0.8], cd=[0.018, 0.014, 0.019], r_norm=0.9),
        ])
        self.assertIsInstance(airfoils.to_airfoil(a), MultiSectionTableAirfoil)

    def test_table_source_without_slices_raises(self):
        a = AirfoilDef(source="table", table_slices=[])
        with self.assertRaises(ValueError):
            airfoils.to_airfoil(a)

    def test_external_source_not_implemented(self):
        a = AirfoilDef(source="external")
        with self.assertRaises(NotImplementedError):
            airfoils.to_airfoil(a)

    def test_unknown_source_raises(self):
        a = AirfoilDef(source="bogus")
        with self.assertRaises(ValueError):
            airfoils.to_airfoil(a)

    def test_stall_model_viterna_wraps_analytical(self):
        a = AirfoilDef(source="analytical", stall_model="viterna")
        af = airfoils.to_airfoil(a)
        self.assertIsInstance(af, ViternaExtendedAirfoil)
        # base pre-stall is always the pure linear line, never clip/enhanced.
        self.assertEqual(af.base.stall_model, "linear")

    def test_clip_and_enhanced_never_combine_with_viterna(self):
        # Viterna is a 4th option MUTUALLY EXCLUSIVE of stall_model --
        # extend_full_range=True has no effect for source
        # 'analytical' unless stall_model is 'viterna'.
        for model in ("clip", "enhanced"):
            a = AirfoilDef(source="analytical", stall_model=model, extend_full_range=True)
            self.assertIsInstance(airfoils.to_airfoil(a), AnalyticalAirfoil)

    def test_extend_full_range_on_table_blends(self):
        # docs/plano_v2.md Section 2.4: with source='table', extend_full_range
        # always uses the 'blend' path (real table + Viterna beyond the
        # stall) -- there is no more separate choice between 'extend' and
        # 'glue', it is derived from the source.
        a = AirfoilDef(source="table", table_slices=[
            PolarSlice(alpha_deg=[-5, 0, 5], cl=[-0.3, 0.2, 0.7], cd=[0.02, 0.015, 0.02]),
        ], extend_full_range=True)
        af = airfoils.to_airfoil(a)
        self.assertIsInstance(af, ViternaExtendedAirfoil)
        self.assertIsInstance(af.base, TableAirfoil)

    def test_dynamic_stall_params_attached(self):
        # docs/plano_v2.md Finding #1: to_airfoil() attaches the parameters of
        # dynamic stall to the returned object, as the single source of truth
        # for bemt.solve_bemt.
        a = AirfoilDef(source="analytical", use_dynamic_stall=True, dynamic_stall_A=12.0)
        af = airfoils.to_airfoil(a)
        self.assertTrue(af.dynamic_stall_params["use_dynamic_stall"])
        self.assertEqual(af.dynamic_stall_params["A"], 12.0)


class TestPreviewPolar(unittest.TestCase):
    def test_preview_polar_shapes_match(self):
        a = AirfoilDef(source="analytical", stall_model="clip")
        alpha, cl, cd = airfoils.preview_polar(a, alpha_deg_range=(-10, 10, 2.0))
        self.assertEqual(len(alpha), len(cl))
        self.assertEqual(len(alpha), len(cd))
        self.assertTrue(np.all(np.isfinite(cl)))
        self.assertTrue(np.all(np.isfinite(cd)))


class TestPreviewPolarFluxoReverso(unittest.TestCase):
    """Bug: `preview_polar` called only `airfoil.cl_cd()` and stopped there, then
    changing `reverse_flow_model` changed NOTHING in the drawn curve -- although
    it changed what the engine calculated. Now it calls
    `bemt.apply_reverse_flow_to_polar`, the SAME function that `element_state`
    uses (extracted from there, not reimplemented)."""

    def _polar(self, modelo, reverse):
        a = AirfoilDef(source="analytical", stall_model="viterna",
                        extend_full_range=True,
                        alpha_stall_pos_deg=15.0, alpha_stall_neg_deg=-6.0)
        return airfoils.preview_polar(
            a, alpha_deg_range=(-180, 180, 5.0),
            config=dict(reverse_flow_model=modelo), reverse=reverse)

    def test_flat_plate_ramo_reverso_e_placa_plana(self):
        alpha, cl, cd = self._polar("flat_plate", reverse=True)
        i = list(alpha).index(60.0)
        # exactly what element_state imposes in reverse flow regime
        self.assertAlmostEqual(cl[i], 0.0)
        self.assertAlmostEqual(cd[i], 1.9)

    def test_flat_plate_ramo_direto_e_a_polar_crua(self):
        _, cl_cfg, _ = self._polar("flat_plate", reverse=False)
        a = AirfoilDef(source="analytical", stall_model="viterna",
                        extend_full_range=True,
                        alpha_stall_pos_deg=15.0, alpha_stall_neg_deg=-6.0)
        _, cl_cru, _ = airfoils.preview_polar(a, alpha_deg_range=(-180, 180, 5.0))
        np.testing.assert_allclose(cl_cfg, cl_cru)

    def test_thin_plate_blend_muda_a_curva_nos_dois_ramos(self):
        """The blend of this model is a function only of |alpha| -- by design the
        two branches coincide, and that is what makes it continuous at Ut=0."""
        alpha, cl_dir, _ = self._polar("thin_plate_blend", reverse=False)
        _, cl_rev, _ = self._polar("thin_plate_blend", reverse=True)
        np.testing.assert_allclose(cl_dir, cl_rev)
        a = AirfoilDef(source="analytical", stall_model="viterna",
                        extend_full_range=True,
                        alpha_stall_pos_deg=15.0, alpha_stall_neg_deg=-6.0)
        _, cl_cru, _ = airfoils.preview_polar(a, alpha_deg_range=(-180, 180, 5.0))
        i = list(alpha).index(60.0)
        self.assertNotAlmostEqual(cl_dir[i], cl_cru[i], places=3)

    def test_sem_config_a_curva_e_a_polar_crua(self):
        """`config=None` (default) preserves the old behavior: no
        post-processing -- that is what plots that don't know the project use."""
        a = AirfoilDef(source="analytical", stall_model="clip")
        alpha, cl, cd = airfoils.preview_polar(a, alpha_deg_range=(-10, 10, 2.0))
        self.assertTrue(np.all(np.isfinite(cl)))
        self.assertTrue(np.all(np.isfinite(cd)))


class TestPreviewPolarBateComOMotor(unittest.TestCase):
    """The curve drawn in the Airfoil tab must be EXACTLY the one that the
    engine consumes -- not a similar approximation. This test runs a real case,
    extracts `alpha_eff`/`Cl`/`Cd` from the maps and re-evaluates
    `preview_polar` at the SAME alphas, element by element.

    The corrections that depend on element state (rotational enhancement, radial
    flow, compressibility, dynamic stall) are TURNED OFF here on purpose: they
    are a function of (r, psi, W), not of the 2D polar, so they cannot appear
    in a Cl(alpha) plot and are not part of what this test checks."""

    def test_cl_cd_do_preview_batem_elemento_a_elemento(self):
        from zbemt import api, geometry
        from zbemt.models import Project, FlightCondition

        geom = geometry.generate_tapered(root_chord_norm=0.10, tip_chord_norm=0.04,
                                          radius_m=1.0, n_stations=12)
        af = AirfoilDef(source="analytical", stall_model="clip",
                         alpha_stall_pos_deg=15.0, alpha_stall_neg_deg=-6.0)
        cfg = dict(Ne=8, Npsi=12, solver="fixed_point", max_iter=150,
                    reverse_flow_model="thin_plate_blend",
                    use_compressibility=False, use_rotational_augmentation=False,
                    use_radial_flow_correction=False, use_dynamic_stall=False)
        projeto = Project(name="t", geometry=geom, airfoil=af, config=cfg)
        r = api.run_case(projeto, FlightCondition(name="c", mu_x=0.3,
                                                    collective_deg=8.0, rpm=600.0))

        alpha_eff = np.asarray(r.maps["alpha_eff"])
        Cl = np.asarray(r.maps["Cl"])
        Cd = np.asarray(r.maps["Cd"])
        reverse = np.asarray(r.maps["reverse"])

        for i, j in [(0, 0), (3, 4), (5, 7), (7, 11)]:
            with self.subTest(elemento=(i, j)):
                a_deg = float(np.degrees(alpha_eff[i, j]))
                _, cl_prev, cd_prev = airfoils.preview_polar(
                    af, (a_deg, a_deg, 1.0), config=cfg, reverse=bool(reverse[i, j]))
                self.assertAlmostEqual(cl_prev[0], Cl[i, j], places=10)
                self.assertAlmostEqual(cd_prev[0], Cd[i, j], places=10)


class TestUniqueConditions(unittest.TestCase):
    def test_empty_for_non_table_source(self):
        a = AirfoilDef(source="analytical")
        self.assertEqual(airfoils.unique_conditions(a), [])

    def test_deduplicates_conditions(self):
        a = AirfoilDef(source="table", table_slices=[
            PolarSlice(alpha_deg=[0], cl=[0], cd=[0.01], r_norm=0.5, label="raiz"),
            PolarSlice(alpha_deg=[1], cl=[0.1], cd=[0.01], r_norm=0.5, label="raiz"),  # same condition, extra alpha
            PolarSlice(alpha_deg=[0], cl=[0], cd=[0.01], r_norm=0.9, label="ponta"),
        ])
        conds = airfoils.unique_conditions(a)
        self.assertEqual(len(conds), 2)


class TestAxisValues(unittest.TestCase):
    def test_empty_for_non_table_source(self):
        a = AirfoilDef(source="analytical")
        axes = airfoils.axis_values(a)
        self.assertEqual(axes, {"r_norm": [], "reynolds": [], "mach": []})

    def test_detects_distinct_values_per_axis(self):
        a = AirfoilDef(source="table", table_slices=[
            PolarSlice(alpha_deg=[0], cl=[0], cd=[0.01], r_norm=0.3, reynolds=1e5),
            PolarSlice(alpha_deg=[0], cl=[0], cd=[0.01], r_norm=0.3, reynolds=5e5),
            PolarSlice(alpha_deg=[0], cl=[0], cd=[0.01], r_norm=0.7, reynolds=1e5),
        ])
        axes = airfoils.axis_values(a)
        self.assertEqual(axes["r_norm"], [0.3, 0.7])
        self.assertEqual(axes["reynolds"], [1e5, 5e5])
        self.assertEqual(axes["mach"], [])


class TestSliceTableAt(unittest.TestCase):
    def _table_1_axis(self):
        return AirfoilDef(source="table", table_slices=[
            PolarSlice(alpha_deg=[0], cl=[0.1], cd=[0.01], reynolds=1e5, label="lo"),
            PolarSlice(alpha_deg=[0], cl=[0.2], cd=[0.02], reynolds=1e6, label="hi"),
        ])

    def _table_2_axes(self):
        slices = []
        for r in (0.3, 0.7):
            for re in (1e5, 1e6):
                slices.append(PolarSlice(alpha_deg=[0], cl=[r + re / 1e7], cd=[0.01],
                                          r_norm=r, reynolds=re, label=f"r{r}_re{re:.0e}"))
        return AirfoilDef(source="table", table_slices=slices)

    def _table_3_axes(self):
        slices = []
        for r in (0.3, 0.7):
            for re in (1e5, 1e6):
                for m in (0.1, 0.3):
                    slices.append(PolarSlice(alpha_deg=[0], cl=[0.5], cd=[0.01],
                                              r_norm=r, reynolds=re, mach=m,
                                              label=f"r{r}_re{re:.0e}_m{m}"))
        return AirfoilDef(source="table", table_slices=slices)

    def test_raises_without_slices(self):
        a = AirfoilDef(source="table", table_slices=[])
        with self.assertRaises(ValueError):
            airfoils.slice_table_at(a)

    def test_1_axis_exact_match(self):
        a = self._table_1_axis()
        s = airfoils.slice_table_at(a, reynolds=1e6)
        self.assertEqual(s.label, "hi")

    def test_1_axis_nearest_off_grid(self):
        a = self._table_1_axis()
        s = airfoils.slice_table_at(a, reynolds=2e5)   # closer to 1e5 than 1e6
        self.assertEqual(s.label, "lo")

    def test_2_axes_exact_match(self):
        a = self._table_2_axes()
        s = airfoils.slice_table_at(a, r_norm=0.7, reynolds=1e5)
        self.assertEqual(s.label, "r0.7_re1e+05")

    def test_2_axes_nearest_off_grid(self):
        a = self._table_2_axes()
        s = airfoils.slice_table_at(a, r_norm=0.35, reynolds=9e5)
        self.assertEqual(s.label, "r0.3_re1e+06")

    def test_3_axes_exact_match(self):
        a = self._table_3_axes()
        s = airfoils.slice_table_at(a, r_norm=0.3, reynolds=1e6, mach=0.3)
        self.assertEqual(s.label, "r0.3_re1e+06_m0.3")

    def test_axis_omitted_falls_back_to_first_value(self):
        a = self._table_2_axes()
        s = airfoils.slice_table_at(a)   # no axis requested -> first r_norm/reynolds
        self.assertEqual(s.label, "r0.3_re1e+05")


class TestNacaGeometry(unittest.TestCase):
    def test_naca4_symmetric_zero_camber(self):
        prof = airfoils.generate_naca4("0012", n_points=100)
        self.assertEqual(prof.source, "naca4")
        y = np.asarray(prof.y)
        # symmetric profile (00XX): upper/lower points must have y
        # approximately opposite around the axis (the shape is closed
        # upper trailing edge -> LE -> lower trailing edge).
        self.assertAlmostEqual(np.max(y), -np.min(y), places=3)
        # maximum thickness ~12% of chord (0.12), with some tolerance
        # numerical error from discrete parameterization.
        thickness = np.max(y) - np.min(y)
        self.assertAlmostEqual(thickness, 0.12, delta=0.01)

    def test_naca4_invalid_code_raises(self):
        with self.assertRaises(ValueError):
            airfoils.generate_naca4("12", n_points=50)
        with self.assertRaises(ValueError):
            airfoils.generate_naca4("abcd", n_points=50)

    def test_naca5_valid_code_runs(self):
        prof = airfoils.generate_naca5("23012", n_points=100)
        self.assertEqual(prof.source, "naca5")
        self.assertTrue(np.all(np.isfinite(prof.x)))
        self.assertTrue(np.all(np.isfinite(prof.y)))

    def test_naca5_invalid_code_raises(self):
        with self.assertRaises(ValueError):
            airfoils.generate_naca5("1234", n_points=50)


class TestCstBezier(unittest.TestCase):
    def test_cst_requires_nonempty_lists(self):
        with self.assertRaises(ValueError):
            airfoils.generate_cst([], [0.1], n_points=50)

    def test_cst_generates_finite_coords(self):
        prof = airfoils.generate_cst(upper=[0.15, 0.2, 0.15], lower=[-0.1, -0.12, -0.1], n_points=60)
        self.assertTrue(np.all(np.isfinite(prof.x)))
        self.assertTrue(np.all(np.isfinite(prof.y)))

    def test_bezier_requires_at_least_three_points(self):
        with self.assertRaises(ValueError):
            airfoils.generate_bezier([[0, 0], [1, 0]], n_points=50)

    def test_bezier_endpoint_matches_first_control_point(self):
        pts = [[1, 0], [0.5, 0.08], [0, 0], [0.5, -0.05], [1, 0]]
        prof = airfoils.generate_bezier(pts, n_points=50)
        self.assertAlmostEqual(prof.x[0], pts[0][0], places=6)
        self.assertAlmostEqual(prof.y[0], pts[0][1], places=6)

    def test_bezier_normaliza_para_corda_unitaria(self):
        """x always goes from 0 (leading edge) to 1 (trailing edge),
        whatever the scale of the control points."""
        pts = [[2.0, 0], [1.0, 0.16], [0.0, 0.0], [1.0, -0.10], [2.0, 0]]
        prof = airfoils.generate_bezier(pts, n_points=80)
        self.assertAlmostEqual(min(prof.x), 0.0, places=6)
        self.assertAlmostEqual(max(prof.x), 1.0, places=6)

    def test_bezier_fechado_no_bordo_de_ataque_nao_sai_invertido(self):
        """Regression: the list closes at the TRAILING EDGE. If closed at the
        leading edge (what a graphical editor produces when the user starts
        drawing from the nose), the profile came out reversed -- nose
        blunt at the back, pointed at the front. Both directions must produce the
        same airfoil: curve endpoints at the trailing edge (x=1)."""
        invertido = [[0, 0], [0.3, 0.08], [1, 0], [0.3, -0.05], [0, 0]]
        prof = airfoils.generate_bezier(invertido, n_points=120)
        # the closing point (start == end of curve) is the trailing edge
        self.assertAlmostEqual(prof.x[0], 1.0, places=6)
        self.assertAlmostEqual(prof.x[-1], 1.0, places=6)
        # and the leading edge (x minimum) is in the MIDDLE of the curve, not at the end
        i_le = int(np.argmin(prof.x))
        self.assertGreater(i_le, 20)
        self.assertLess(i_le, 100)


class TestProfileFileIO(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)

    def test_load_profile_dat_selig_format(self):
        path = Path(self.tmp.name) / "naca0012.dat"
        path.write_text("NACA 0012\n1.0 0.0\n0.5 0.03\n0.0 0.0\n0.5 -0.03\n1.0 0.0\n")
        prof = airfoils.load_profile_dat(str(path))
        self.assertEqual(prof.source, "imported")
        self.assertEqual(len(prof.x), 5)

    def test_load_profile_dat_no_coordinates_raises(self):
        path = Path(self.tmp.name) / "empty.dat"
        path.write_text("nada aqui\nsó texto\n")
        with self.assertRaises(ValueError):
            airfoils.load_profile_dat(str(path))

    def test_normalize_profile_scales_to_unit_chord(self):
        prof = ProfileGeometry(x=[2.0, 4.0, 6.0], y=[0.0, 0.5, 0.0])
        normalized = airfoils.normalize_profile(prof)
        self.assertAlmostEqual(min(normalized.x), 0.0)
        self.assertAlmostEqual(max(normalized.x), 1.0)

    def test_resample_profile_changes_point_count(self):
        prof = airfoils.generate_naca4("0012", n_points=40)
        resampled = airfoils.resample_profile(prof, n_points=200)
        self.assertEqual(len(resampled.x), 200)
        self.assertEqual(resampled.n_points, 200)


class TestPolarCsvImportExport(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)

    def test_import_single_polar_csv(self):
        path = Path(self.tmp.name) / "polar.csv"
        path.write_text("alpha,Cl,Cd\n-5,-0.3,0.02\n0,0.2,0.015\n5,0.7,0.02\n")
        slices = airfoils.import_polar_csv(str(path))
        self.assertEqual(len(slices), 1)
        self.assertEqual(slices[0].alpha_deg, [-5.0, 0.0, 5.0])
        self.assertIsNone(slices[0].r_norm)

    def test_import_multi_section_csv_by_r_norm(self):
        path = Path(self.tmp.name) / "polar_multi.csv"
        path.write_text(
            "alpha,Cl,Cd,r_norm\n"
            "0,0.2,0.015,0.3\n1,0.3,0.016,0.3\n"
            "0,0.25,0.014,0.9\n1,0.35,0.015,0.9\n"
        )
        slices = airfoils.import_polar_csv(str(path))
        self.assertEqual(len(slices), 2)
        r_norms = sorted(s.r_norm for s in slices)
        self.assertEqual(r_norms, [0.3, 0.9])

    def test_import_missing_required_column_raises(self):
        path = Path(self.tmp.name) / "bad.csv"
        path.write_text("angle,lift,drag\n0,0.2,0.01\n")
        with self.assertRaises(ValueError):
            airfoils.import_polar_csv(str(path))

    def test_export_then_import_roundtrip(self):
        a = AirfoilDef(name="teste", source="table", table_slices=[
            PolarSlice(alpha_deg=[-5, 0, 5], cl=[-0.3, 0.2, 0.7], cd=[0.02, 0.015, 0.02], r_norm=0.5),
        ])
        path = Path(self.tmp.name) / "export.csv"
        airfoils.export_polar_csv(a, str(path))
        self.assertTrue(path.exists())
        slices = airfoils.import_polar_csv(str(path))
        self.assertEqual(len(slices), 1)
        self.assertAlmostEqual(slices[0].r_norm, 0.5)
        self.assertEqual(slices[0].cl, [-0.3, 0.2, 0.7])

    def test_detect_csv_axes(self):
        path = Path(self.tmp.name) / "polar.csv"
        path.write_text("alpha,Cl,Cd\n-5,-0.3,0.02\n0,0.2,0.015\n")
        axes = airfoils.detect_csv_axes(str(path))
        self.assertEqual(axes["alpha_deg"], "alpha")
        self.assertEqual(axes["cl"], "Cl")
        self.assertIsNone(axes["r_norm"])


class TestToBladeAirfoil(unittest.TestCase):
    """Phase D (docs/plano.md GUI v3, Section 4): bridge function to_blade_airfoil,
    sister of to_airfoil() for entire blade (0/1 section = old path, 2+ =
    HeterogeneousMultiSectionAirfoil)."""

    def test_empty_list_falls_back_to_default_airfoil_def(self):
        af = airfoils.to_blade_airfoil([])
        self.assertIsInstance(af, ViternaExtendedAirfoil)  # default extend_full_range=True

    def _multi_reynolds_def(self):
        """Table with 3 identical polars except for a Cl offset, one
        per Reynolds -- the offset identifies which slice was chosen."""
        alpha = np.linspace(-20.0, 20.0, 41)
        slices = [
            PolarSlice(alpha_deg=alpha.tolist(), cl=(0.05 * alpha + offset).tolist(),
                       cd=(0.01 + 0.0 * alpha).tolist(), reynolds=re, mach=0.0)
            for offset, re in [(0.0, 1e5), (1.0, 5e5), (2.0, 1e6)]
        ]
        return AirfoilDef(name="multi_re", source="table", table_slices=slices,
                          extend_full_range=False)

    def test_reynolds_is_forwarded_to_slice_selection(self):
        """Regression: `to_blade_airfoil` called `to_airfoil` WITHOUT reynolds/mach,
        then every slice tied at 0.0 in the proximity criterion and the
        FIRST was always returned -- a sweep of N Reynolds was
        generated, exported, shown in the GUI and ignored by the engine."""
        airfoil_def = self._multi_reynolds_def()
        cl_em_zero = lambda af: float(af.cl_cd(np.array([0.0]))[0][0])

        for reynolds, offset_esperado in [(1e5, 0.0), (5e5, 1.0), (1e6, 2.0)]:
            af = airfoils.to_blade_airfoil([airfoil_def], reynolds=reynolds, mach=0.0)
            self.assertAlmostEqual(cl_em_zero(af), offset_esperado, places=9,
                                   msg=f"Reynolds {reynolds:g} escolheu a slice errada")

    def test_reference_reynolds_mach_scales_with_rpm(self):
        """The (Re, Mach) reference pair must grow with rotation --
        it is what makes the engine change polars between flight conditions."""
        from zbemt import studies
        from zbemt.bemt import BEMTConfig
        geom = RotorGeometryDef(radius_m=5.0, n_blades=4,
                                r_norm=[0.2, 0.6, 1.0], chord_norm=[0.1, 0.1, 0.1],
                                twist_deg=[8.0, 4.0, 0.0])
        rotor = studies._to_rotor(geom)

        rotor.Omega_rpm = 300.0
        re_baixo, mach_baixo = airfoils.reference_reynolds_mach(rotor, BEMTConfig(), mu_x=0.0)
        rotor.Omega_rpm = 600.0
        re_alto, mach_alto = airfoils.reference_reynolds_mach(rotor, BEMTConfig(), mu_x=0.0)

        self.assertAlmostEqual(re_alto, 2.0 * re_baixo, places=3)
        self.assertAlmostEqual(mach_alto, 2.0 * mach_baixo, places=9)

    def test_reference_reynolds_mach_returns_none_for_zero_rotation(self):
        from zbemt import studies
        from zbemt.bemt import BEMTConfig
        geom = RotorGeometryDef(radius_m=5.0, n_blades=4,
                                r_norm=[0.2, 0.6, 1.0], chord_norm=[0.1, 0.1, 0.1],
                                twist_deg=[8.0, 4.0, 0.0])
        rotor = studies._to_rotor(geom)
        rotor.Omega_rpm = 0.0
        self.assertEqual(airfoils.reference_reynolds_mach(rotor, BEMTConfig()), (None, None))

    def test_single_section_matches_to_airfoil(self):
        a = AirfoilDef(name="unico", source="analytical", stall_model="linear")
        af_via_blade = airfoils.to_blade_airfoil([a])
        af_via_single = airfoils.to_airfoil(a)
        self.assertEqual(type(af_via_blade), type(af_via_single))
        alpha = np.array([0.05, 0.1])
        cl1, cd1 = af_via_blade.cl_cd(alpha)
        cl2, cd2 = af_via_single.cl_cd(alpha)
        np.testing.assert_allclose(cl1, cl2)
        np.testing.assert_allclose(cd1, cd2)

    def test_two_sections_builds_composite(self):
        root = AirfoilDef(name="raiz", r_norm=0.15, source="analytical",
                           cd0=0.02, stall_model="linear")
        tip = AirfoilDef(name="ponta", r_norm=1.0, source="analytical",
                          cd0=0.008, stall_model="linear")
        af = airfoils.to_blade_airfoil([root, tip])
        self.assertIsInstance(af, HeterogeneousMultiSectionAirfoil)
        self.assertFalse(af.dynamic_stall_params["use_dynamic_stall"])
        alpha = np.array([0.0])
        _, cd_root = af.cl_cd(alpha, r_norm=np.array([0.15]))
        self.assertAlmostEqual(float(cd_root[0]), 0.02, places=8)

    def test_two_sections_requires_r_norm_on_every_section(self):
        root = AirfoilDef(name="raiz", r_norm=0.15)
        tip = AirfoilDef(name="ponta", r_norm=None)
        with self.assertRaises(ValueError):
            airfoils.to_blade_airfoil([root, tip])

    def test_mixed_analytical_and_table_sections(self):
        root = AirfoilDef(name="raiz", r_norm=0.15, source="analytical", stall_model="linear")
        tip = AirfoilDef(name="ponta", r_norm=1.0, source="table", extend_full_range=False,
                          table_slices=[PolarSlice(alpha_deg=[-10, 0, 10], cl=[-0.5, 0.0, 0.5],
                                                    cd=[0.03, 0.015, 0.03])])
        af = airfoils.to_blade_airfoil([root, tip])
        alpha = np.deg2rad(np.array([0.0, 5.0]))
        cl, cd = af.cl_cd(alpha, r_norm=np.array([0.5, 0.5]))
        self.assertTrue(np.all(np.isfinite(cl)))
        self.assertTrue(np.all(np.isfinite(cd)))


class TestAirfoilPresetsAndGeometrySpec(unittest.TestCase):
    """Phase 7: catalog of automatic geometry generation (raw NACA4/5 +
    typical blade/rotor presets) used by the GUI (presets combo) and by the
    CLI (--airfoil-geometry)."""

    def test_all_presets_generate_valid_geometry(self):
        for key in airfoils.AIRFOIL_PRESETS:
            geom = airfoils.generate_preset(key)
            self.assertGreater(len(geom.x), 0)
            self.assertEqual(len(geom.x), len(geom.y))

    def test_unknown_preset_raises_value_error(self):
        with self.assertRaises(ValueError):
            airfoils.generate_preset("not_a_real_preset")

    def test_resolve_geometry_spec_accepts_preset_alias(self):
        geom = airfoils.resolve_geometry_spec("naca0012")
        self.assertEqual(geom.source, "naca4")
        self.assertEqual(geom.naca_code, "0012")

    def test_resolve_geometry_spec_accepts_raw_naca4_code(self):
        geom = airfoils.resolve_geometry_spec("naca2412")
        self.assertEqual(geom.source, "naca4")
        self.assertEqual(geom.naca_code, "2412")

    def test_resolve_geometry_spec_accepts_raw_naca5_code(self):
        geom = airfoils.resolve_geometry_spec("naca63012")  # 5 digits after 'naca'
        self.assertEqual(geom.source, "naca5")

    def test_resolve_geometry_spec_unrecognized_raises_with_helpful_message(self):
        with self.assertRaises(ValueError) as ctx:
            airfoils.resolve_geometry_spec("clark_y_super_secreto")
        msg = str(ctx.exception)
        self.assertIn("naca0012", msg)  # list of presets appears in the message


if __name__ == "__main__":
    unittest.main()


class TestQ4ParametrosDePa(unittest.TestCase):
    """Q4 (production-plan.md): `to_blade_airfoil` read method and timing
    of dynamic stall always from the FIRST section and fixed
    `method="frequency"` -- a project that requested `time_march` received
    `frequency` without warning, and a blade whose root didn't use dynamic stall
    delivered the parameters of that root."""

    @staticmethod
    def _secao(r_norm, **kw):
        base = dict(name=f"s{r_norm}", r_norm=r_norm, source="analytical")
        base.update(kw)
        return AirfoilDef(**base)

    def test_time_march_pedido_chega_ao_motor(self):
        secoes = [self._secao(0.2, use_dynamic_stall=True, dynamic_stall_method="time_march"),
                  self._secao(0.9, use_dynamic_stall=True, dynamic_stall_method="time_march")]
        composto = airfoils.to_blade_airfoil(secoes)
        self.assertEqual(composto.dynamic_stall_params["method"], "time_march")

    def test_secao_sem_estol_dinamico_nao_dita_os_parametros(self):
        """The root doesn't use dynamic stall; the ones in charge are the sections that use it."""
        secoes = [self._secao(0.2, use_dynamic_stall=False,
                              dynamic_stall_method="frequency",
                              dynamic_stall_time_march_revolutions=8),
                  self._secao(0.9, use_dynamic_stall=True,
                              dynamic_stall_method="time_march",
                              dynamic_stall_time_march_revolutions=20)]
        params = airfoils.to_blade_airfoil(secoes).dynamic_stall_params
        self.assertEqual(params["method"], "time_march")
        self.assertEqual(params["time_march_revolutions"], 20)

    def test_secoes_em_conflito_avisam(self):
        secoes = [self._secao(0.2, use_dynamic_stall=True, dynamic_stall_method="frequency"),
                  self._secao(0.9, use_dynamic_stall=True, dynamic_stall_method="time_march")]
        with warnings.catch_warnings(record=True) as capturados:
            warnings.simplefilter("always")
            params = airfoils.to_blade_airfoil(secoes)
        mensagens = [str(w.message) for w in capturados]
        self.assertTrue(any("dynamic_stall_method" in m for m in mensagens), mensagens)
        # the innermost wins, and the value is deterministic
        self.assertEqual(params.dynamic_stall_params["method"], "frequency")

    def test_validacao_avisa_antes_de_rodar(self):
        secoes = [self._secao(0.2, use_dynamic_stall=True, dynamic_stall_method="frequency"),
                  self._secao(0.9, use_dynamic_stall=True, dynamic_stall_method="time_march")]
        avisos = [i for i in validation.validate_airfoil_sections(secoes)
                  if i.level == "warning" and "method" in i.message]
        self.assertEqual(len(avisos), 1, [str(i) for i in avisos])

    def test_sem_conflito_nao_avisa(self):
        secoes = [self._secao(0.2, use_dynamic_stall=True, dynamic_stall_method="time_march"),
                  self._secao(0.9, use_dynamic_stall=True, dynamic_stall_method="time_march")]
        self.assertEqual(
            [i for i in validation.validate_airfoil_sections(secoes)
             if "disagree" in i.message], [])


class TestImportarContorno(unittest.TestCase):
    """`load_profile_dat` accepts any file with number pairs --
    and it is precisely for this reason that the COUNT line of Lednicer format
    ("61.  61.") entered silently as a point at x=61, producing a
    profile with a spike of 61 chords without any warning."""

    def _arquivo(self, texto: str, nome: str = "perfil.dat") -> str:
        import tempfile
        from pathlib import Path
        caminho = Path(tempfile.mkdtemp()) / nome
        caminho.write_text(texto, encoding="utf-8")
        return str(caminho)

    _SELIG = ("NACA 2412\n"
              "1.000000  0.001300\n"
              "0.500000  0.065000\n"
              "0.000000  0.000000\n"
              "0.500000 -0.035000\n"
              "1.000000 -0.001300\n")

    def test_selig_entra_como_esta(self):
        geom = airfoils.load_profile_dat(self._arquivo(self._SELIG))
        self.assertEqual(geom.n_points, 5)
        self.assertEqual(geom.source, "imported")
        self.assertAlmostEqual(geom.x[0], 1.0)

    def test_nome_e_linhas_nao_numericas_sao_ignorados(self):
        texto = "# comentário\nNACA 2412\n\n1.0 0.0\n0.0 0.0\nfim\n"
        geom = airfoils.load_profile_dat(self._arquivo(texto))
        self.assertEqual(geom.n_points, 2)

    def test_virgula_serve_de_separador(self):
        geom = airfoils.load_profile_dat(self._arquivo("x,y\n1.0,0.0\n0.0,0.0\n", "p.csv"))
        self.assertEqual(geom.n_points, 2)

    def test_contagem_do_lednicer_e_recusada_com_explicacao(self):
        texto = "NACA 2412\n      61.      61.\n\n1.0 0.0013\n0.0 0.0\n"
        with self.assertRaises(ValueError) as ctx:
            airfoils.load_profile_dat(self._arquivo(texto))
        mensagem = str(ctx.exception)
        self.assertIn("Lednicer", mensagem)
        self.assertIn("Selig", mensagem)

    def test_arquivo_sem_par_de_numeros_falha(self):
        with self.assertRaises(ValueError):
            airfoils.load_profile_dat(self._arquivo("sem coordenadas aqui\n"))
