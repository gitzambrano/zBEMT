"""
test_visualization.py
======================

`zbemt.viz.visualization`: the geometry handed to the 3D view -- the
blade surface, the rotor disk, and the scalar grid painted on it.

The three builders run without PyVista: they return plain arrays, and
PyVista only draws them. That is the point of the split, and it is what
lets these tests check the numbers -- point counts, orientation, the
field actually sampled -- on a machine with no 3D stack at all
(PR-7). `TestPyvistaAvailability` covers the other half: the absence of
PyVista must degrade the 3D view alone and never raise anywhere else.
"""
import unittest
from dataclasses import dataclass, field as dc_field

import numpy as np

from zbemt.viz import visualization


@dataclass
class _FakeGeom:
    r_norm: list = dc_field(default_factory=lambda: [0.2, 0.5, 0.8, 1.0])
    chord_norm: list = dc_field(default_factory=lambda: [0.08, 0.07, 0.05, 0.03])
    twist_deg: list = dc_field(default_factory=lambda: [12.0, 6.0, 2.0, 0.0])
    n_blades: int = 4
    radius_m: float = 1.4


class TestBuildBladeSurface(unittest.TestCase):
    def test_shapes_flat_plate_default(self):
        geom = _FakeGeom()
        pts, faces = visualization.build_blade_surface(geom, n_span=10)
        # flat plate (no profile): n_chord=2 points per station
        self.assertEqual(pts.shape, (10 * 2, 3))
        self.assertEqual(len(faces), (10 - 1) * (2 - 1) * 5)  # 5 = [4, i0,i1,i2,i3] por face
        self.assertTrue(np.all(np.isfinite(pts)))

    def test_root_and_tip_radius_scaled_by_radius_m(self):
        geom = _FakeGeom(radius_m=2.0)
        pts, _ = visualization.build_blade_surface(geom, n_span=5, azimuth_deg=0.0)
        # at psi=0, X = r*cos(0) - y_local*sin(0) = r exactly (pure span,
        # no chord offset contamination) -- see docstring of
        # build_blade_surface. hypot(x,y) would NOT work here: it would include the
        # chord offset (flat plate with xc != 0) in the distance.
        x = pts[:, 0]
        self.assertAlmostEqual(x.min(), min(geom.r_norm) * geom.radius_m, places=6)
        self.assertAlmostEqual(x.max(), max(geom.r_norm) * geom.radius_m, places=6)

    def test_azimuth_rotation_preserves_z(self):
        geom = _FakeGeom()
        pts0, _ = visualization.build_blade_surface(geom, n_span=8, azimuth_deg=0.0)
        pts90, _ = visualization.build_blade_surface(geom, n_span=8, azimuth_deg=90.0)
        # rotation around Z should not change the Z component
        self.assertTrue(np.allclose(pts0[:, 2], pts90[:, 2], atol=1e-9))

    def test_needs_at_least_two_radial_stations(self):
        geom = _FakeGeom(r_norm=[0.5], chord_norm=[0.05], twist_deg=[0.0])
        with self.assertRaises(ValueError):
            visualization.build_blade_surface(geom, n_span=10)

    def test_uses_real_profile_when_given(self):
        from zbemt.models import ProfileGeometry
        prof = ProfileGeometry(x=[0.0, 0.5, 1.0, 0.5], y=[0.0, 0.05, 0.0, -0.05])
        geom = _FakeGeom()
        pts, _ = visualization.build_blade_surface(geom, profile=prof, n_span=5)
        self.assertEqual(pts.shape, (5 * 4, 3))  # n_chord=4 pontos do perfil


class TestBuildRotorDisk(unittest.TestCase):
    def test_one_blade_mesh_per_n_blades(self):
        geom = _FakeGeom(n_blades=3)
        blades = visualization.build_rotor_disk(geom, n_span=6)
        self.assertEqual(len(blades), 3)
        for pts, faces in blades:
            self.assertEqual(pts.shape, (6 * 2, 3))

    def test_blades_evenly_spaced_in_azimuth(self):
        geom = _FakeGeom(n_blades=4)
        blades = visualization.build_rotor_disk(geom, n_span=4)
        # gets the root point (smallest radius) of each blade and checks the angles
        angles = []
        for pts, _ in blades:
            radii = np.hypot(pts[:, 0], pts[:, 1])
            i_root = np.argmin(radii)
            angles.append(np.degrees(np.arctan2(pts[i_root, 1], pts[i_root, 0])) % 360)
        angles = sorted(angles)
        diffs = np.diff(angles + [angles[0] + 360])
        self.assertTrue(np.allclose(diffs, 90.0, atol=1e-6))


class TestBuildDiskGrid(unittest.TestCase):
    def setUp(self):
        Ne, Npsi = 6, 10
        self.maps = {
            "R_DIM": np.outer(np.linspace(0.3, 1.4, Ne), np.ones(Npsi)),
            "PSI": np.outer(np.ones(Ne), np.linspace(0, 2 * np.pi, Npsi, endpoint=False)),
            "Fn": np.random.default_rng(0).random((Ne, Npsi)),
        }

    def test_flat_disk_when_no_z_field(self):
        # default close_azimuth=True: one more column, closing the disk
        # (see _close_azimuth) -- without it a slice lacks coverage
        # between the last psi node and psi=0/2*pi.
        Ne, Npsi = self.maps["R_DIM"].shape
        X, Y, Z, values = visualization.build_disk_grid(self.maps, field="Fn")
        self.assertEqual(X.shape, (Ne, Npsi + 1))
        self.assertTrue(np.all(Z == 0.0))
        self.assertTrue(np.array_equal(values[:, :-1], self.maps["Fn"]))
        # closing column repeats the psi=0 column (same field, one revolution later)
        self.assertTrue(np.array_equal(values[:, -1], self.maps["Fn"][:, 0]))

    def test_disk_is_closed_all_the_way_around(self):
        # X,Y of the last column (psi=2*pi) should match those of the
        # first (psi=0) -- i.e., no slice lacking coverage.
        X, Y, Z, values = visualization.build_disk_grid(self.maps, field="Fn")
        self.assertTrue(np.allclose(X[:, -1], X[:, 0]))
        self.assertTrue(np.allclose(Y[:, -1], Y[:, 0]))

    def test_close_azimuth_false_keeps_raw_grid(self):
        X, Y, Z, values = visualization.build_disk_grid(self.maps, field="Fn", close_azimuth=False)
        self.assertEqual(X.shape, self.maps["R_DIM"].shape)
        self.assertTrue(np.array_equal(values, self.maps["Fn"]))

    def test_extruded_disk_scaled_by_radius(self):
        X, Y, Z, values = visualization.build_disk_grid(self.maps, field="Fn", z_field="Fn", z_scale=0.2)
        R_max = np.max(self.maps["R_DIM"])
        self.assertLessEqual(np.max(np.abs(Z)), 0.2 * R_max + 1e-9)
        self.assertTrue(np.any(Z != 0.0))

    def test_missing_required_keys_raises(self):
        with self.assertRaises(KeyError):
            visualization.build_disk_grid({"Fn": np.zeros((3, 3))}, field="Fn")

    def test_unknown_field_raises(self):
        with self.assertRaises(KeyError):
            visualization.build_disk_grid(self.maps, field="does_not_exist")

    def test_unknown_z_field_raises(self):
        with self.assertRaises(KeyError):
            visualization.build_disk_grid(self.maps, field="Fn", z_field="does_not_exist")


class TestAvailableDiskFields(unittest.TestCase):
    def test_lists_only_matching_shape_arrays(self):
        maps = {
            "R_DIM": np.zeros((4, 5)), "PSI": np.zeros((4, 5)),
            "Fn": np.zeros((4, 5)), "Ft": np.zeros((4, 5)),
            "solver": "newton",              # not an array -- should be ignored
            "n_iter": np.zeros((4,)),        # different shape -- should be ignored
        }
        fields = visualization.available_disk_fields(maps)
        self.assertEqual(set(fields), {"Fn", "Ft"})

    def test_empty_without_r_dim(self):
        self.assertEqual(visualization.available_disk_fields({"Fn": np.zeros((2, 2))}), [])


class TestPyvistaAvailability(unittest.TestCase):
    def test_is_available_returns_bool_and_is_cached(self):
        result1 = visualization.is_available()
        result2 = visualization.is_available()
        self.assertIsInstance(result1, bool)
        self.assertEqual(result1, result2)

    def test_require_pyvista_raises_clear_import_error_when_unavailable(self):
        if visualization.is_available():
            self.skipTest("PyVista is installed on this machine -- nothing to test here.")
        with self.assertRaises(ImportError) as ctx:
            visualization._require_pyvista()
        self.assertIn("pyvista", str(ctx.exception).lower())

    def test_plot_functions_raise_import_error_when_pyvista_unavailable(self):
        if visualization.is_available():
            self.skipTest("PyVista is installed on this machine -- nothing to test here.")
        geom = _FakeGeom()
        with self.assertRaises(ImportError):
            visualization.plot_rotor_3d(geom)


if __name__ == "__main__":
    unittest.main()
