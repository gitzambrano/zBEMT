"""Verify blade-geometry generation, validation, and editing operations.

The tests supply parametric specifications and spanwise tables, then inspect
resampling, interpolation, editing, and validation results. Outputs must preserve
station ordering, dimensions, and physical bounds. The tests do not exercise airfoil
polar selection or BEMT execution.
"""

import unittest

import numpy as np

from zbemt import geometry
from zbemt.models import RotorGeometryDef


class TestGenerators(unittest.TestCase):
    def test_generate_rectangular_constant_chord(self):
        geom = geometry.generate_rectangular(chord_norm=0.08, n_stations=20, root_cutout_norm=0.15)
        self.assertEqual(len(geom.r_norm), 20)
        self.assertTrue(np.allclose(geom.chord_norm, 0.08))
        self.assertAlmostEqual(geom.r_norm[0], 0.15)
        self.assertAlmostEqual(geom.r_norm[-1], 1.0)
        self.assertEqual(geom.origin, "parametric")
        self.assertEqual(geom.origin_params["kind"], "rectangular")

    def test_generate_tapered_monotonic(self):
        geom = geometry.generate_tapered(root_chord_norm=0.10, tip_chord_norm=0.04, n_stations=15)
        chord = np.asarray(geom.chord_norm)
        # afilamento linear raiz->ponta: estritamente decrescente
        self.assertTrue(np.all(np.diff(chord) <= 1e-12))
        self.assertAlmostEqual(chord[0], 0.10)
        self.assertAlmostEqual(chord[-1], 0.04)

    def test_generate_elliptic_chord_never_zero_at_tip(self):
        geom = geometry.generate_elliptic(max_chord_norm=0.10, n_stations=30)
        chord = np.asarray(geom.chord_norm)
        self.assertTrue(np.all(chord > 0.0))
        # ellipse peak must stay near the root (small r), not at the tip
        self.assertGreater(chord[0], chord[-1])

    def test_generate_custom_from_lists(self):
        geom = geometry.generate_custom(r_norm=[0.3, 0.6, 1.0], chord_norm=[0.09, 0.06, 0.02],
                                         twist_deg=[10.0, 4.0, 0.0], radius_m=1.2, n_blades=3)
        self.assertEqual(geom.origin, "table")
        self.assertEqual(geom.n_blades, 3)
        self.assertAlmostEqual(geom.root_cutout_norm, 0.3)
        self.assertEqual(geom.radius_m, 1.2)

    def test_all_generators_return_rotor_geometry_def(self):
        for gen in (geometry.generate_rectangular, geometry.generate_tapered, geometry.generate_elliptic):
            self.assertIsInstance(gen(), RotorGeometryDef)

    def test_generate_elliptic_peak_matches_max_chord_norm_param(self):
        # Q3: the actual peak of the table (at r_norm[0], the root) must match
        # the value the user typed as "Max Chord" in the GUI --
        # before, sqrt(1-root_cutout^2) < 1 made the actual peak fall below
        # the parameter.
        geom = geometry.generate_elliptic(max_chord_norm=0.20, root_cutout_norm=0.25, n_stations=30)
        self.assertAlmostEqual(geom.chord_norm[0], 0.20, places=9)
        self.assertEqual(geom.chord_norm[0], max(geom.chord_norm))


class TestCustomTableValidation(unittest.TestCase):
    def test_generate_custom_sorts_out_of_order_table(self):
        # Pasted from spreadsheet tip->root: out of order, but each trio
        # (r, chord, twist) must remain coherent after reordering.
        geom = geometry.generate_custom(r_norm=[1.0, 0.3, 0.6], chord_norm=[0.02, 0.09, 0.06],
                                         twist_deg=[0.0, 10.0, 4.0])
        self.assertEqual(geom.r_norm, [0.3, 0.6, 1.0])
        self.assertEqual(geom.chord_norm, [0.09, 0.06, 0.02])
        self.assertEqual(geom.twist_deg, [10.0, 4.0, 0.0])
        self.assertAlmostEqual(geom.root_cutout_norm, 0.3)

    def test_generate_custom_duplicate_r_norm_raises(self):
        with self.assertRaises(ValueError):
            geometry.generate_custom(r_norm=[0.3, 0.3, 0.6], chord_norm=[0.09, 0.08, 0.06],
                                      twist_deg=[10.0, 9.0, 4.0])

    def test_generate_custom_mismatched_lengths_raises(self):
        with self.assertRaises(ValueError):
            geometry.generate_custom(r_norm=[0.3, 0.6, 1.0], chord_norm=[0.09, 0.06],
                                      twist_deg=[10.0, 4.0, 0.0])

    def test_generate_custom_empty_raises(self):
        with self.assertRaises(ValueError):
            geometry.generate_custom(r_norm=[], chord_norm=[], twist_deg=[])

    def test_resample_geometry_out_of_order_table_matches_sorted_result(self):
        ordered = RotorGeometryDef(r_norm=[0.2, 0.5, 1.0], chord_norm=[0.10, 0.07, 0.03],
                                    twist_deg=[12.0, 6.0, 1.0])
        shuffled = RotorGeometryDef(r_norm=[1.0, 0.2, 0.5], chord_norm=[0.03, 0.10, 0.07],
                                     twist_deg=[1.0, 12.0, 6.0])
        r1 = geometry.resample_geometry(ordered, n_stations=10)
        r2 = geometry.resample_geometry(shuffled, n_stations=10)
        self.assertTrue(np.allclose(r1.chord_norm, r2.chord_norm))
        self.assertTrue(np.allclose(r1.twist_deg, r2.twist_deg))

    def test_resample_geometry_duplicate_r_norm_raises(self):
        geom = RotorGeometryDef(r_norm=[0.2, 0.2, 1.0], chord_norm=[0.10, 0.09, 0.03],
                                 twist_deg=[12.0, 11.0, 1.0])
        with self.assertRaises(ValueError):
            geometry.resample_geometry(geom, n_stations=10)

    def test_interpolate_geometry_out_of_order_table_matches_sorted_result(self):
        ordered = RotorGeometryDef(r_norm=[0.2, 0.5, 1.0], chord_norm=[0.10, 0.07, 0.03],
                                    twist_deg=[12.0, 6.0, 1.0])
        shuffled = RotorGeometryDef(r_norm=[1.0, 0.2, 0.5], chord_norm=[0.03, 0.10, 0.07],
                                     twist_deg=[1.0, 12.0, 6.0])
        c1, t1 = geometry.interpolate_geometry(ordered, [0.3, 0.7])
        c2, t2 = geometry.interpolate_geometry(shuffled, [0.3, 0.7])
        self.assertTrue(np.allclose(c1, c2))
        self.assertTrue(np.allclose(t1, t2))

    def test_interpolate_geometry_duplicate_r_norm_raises(self):
        geom = RotorGeometryDef(r_norm=[0.2, 0.2, 1.0], chord_norm=[0.10, 0.09, 0.03],
                                 twist_deg=[12.0, 11.0, 1.0])
        with self.assertRaises(ValueError):
            geometry.interpolate_geometry(geom, [0.5])


class TestResampleInterpolateEdit(unittest.TestCase):
    def setUp(self):
        self.geom = geometry.generate_tapered(root_chord_norm=0.10, tip_chord_norm=0.04,
                                               twist_root_deg=14.0, twist_tip_deg=2.0,
                                               root_cutout_norm=0.2, n_stations=10)

    def test_resample_preserves_endpoints_and_changes_count(self):
        resampled = geometry.resample_geometry(self.geom, n_stations=50)
        self.assertEqual(len(resampled.r_norm), 50)
        self.assertAlmostEqual(resampled.r_norm[0], self.geom.r_norm[0])
        self.assertAlmostEqual(resampled.r_norm[-1], self.geom.r_norm[-1])
        self.assertAlmostEqual(resampled.chord_norm[0], self.geom.chord_norm[0], places=6)
        self.assertAlmostEqual(resampled.chord_norm[-1], self.geom.chord_norm[-1], places=6)
        self.assertEqual(resampled.origin, "editor")

    def test_resample_degenerate_single_point_is_noop(self):
        degenerate = RotorGeometryDef(r_norm=[0.5], chord_norm=[0.05], twist_deg=[3.0])
        out = geometry.resample_geometry(degenerate, n_stations=10)
        self.assertIs(out, degenerate)

    def test_interpolate_geometry_matches_at_known_stations(self):
        chord, twist = geometry.interpolate_geometry(self.geom, [self.geom.r_norm[0], self.geom.r_norm[-1]])
        self.assertAlmostEqual(chord[0], self.geom.chord_norm[0], places=6)
        self.assertAlmostEqual(chord[1], self.geom.chord_norm[-1], places=6)
        self.assertAlmostEqual(twist[0], self.geom.twist_deg[0], places=6)

    def test_edit_point_updates_chord_and_marks_editor_origin(self):
        original_chord0 = self.geom.chord_norm[0]
        edited = geometry.edit_point(self.geom, index=0, chord_norm=0.5)
        self.assertEqual(edited.chord_norm[0], 0.5)
        self.assertNotEqual(edited.chord_norm[0], original_chord0)
        self.assertEqual(edited.origin, "editor")

    def test_edit_point_only_twist_leaves_chord_untouched(self):
        original_chord = list(self.geom.chord_norm)
        geometry.edit_point(self.geom, index=1, twist_deg=99.0)
        self.assertEqual(self.geom.twist_deg[1], 99.0)
        self.assertEqual(self.geom.chord_norm, original_chord)


if __name__ == "__main__":
    unittest.main()
