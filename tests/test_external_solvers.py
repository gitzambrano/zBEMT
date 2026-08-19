"""Tests for `zbemt.external_solvers`: which engines are supported, availability checks, and running an external polar solver (validation and computation), including behavior when the optional package is not installed.
"""

import os
import unittest

import numpy as np

from zbemt import external_solvers
from zbemt import airfoils
from zbemt.models import ProfileGeometry

NEURALFOIL_AVAILABLE = external_solvers.is_available("neuralfoil")


class TestSupportedEngines(unittest.TestCase):
    def test_only_neuralfoil_is_supported(self):
        self.assertEqual(external_solvers.SUPPORTED_ENGINES, ("neuralfoil",))

    def test_unknown_engine_raises_value_error(self):
        with self.assertRaises(ValueError):
            external_solvers.run_polar("bogus_engine", ProfileGeometry(), [1e6], [0.1], -10, 10, 1.0)

    def test_xfoil_is_unknown_engine(self):
        # XFOIL was deliberately removed (Phase 7) -- it is no longer a
        # "known but not implemented" engine, it is unknown.
        with self.assertRaises(ValueError):
            external_solvers.run_polar("xfoil", ProfileGeometry(), [1e6], [0.1], -10, 10, 1.0)


class TestIsAvailable(unittest.TestCase):
    def test_is_available_reflects_real_package_presence(self):
        import importlib.util
        expected = importlib.util.find_spec("neuralfoil") is not None
        self.assertEqual(external_solvers.is_available("neuralfoil"), expected)

    def test_is_available_false_for_unknown_engine(self):
        self.assertFalse(external_solvers.is_available("xfoil"))
        self.assertFalse(external_solvers.is_available("bogus"))


class TestRunPolarValidation(unittest.TestCase):
    """Validations that don't depend on the `neuralfoil` package being installed."""

    def test_empty_reynolds_or_mach_raises_value_error(self):
        geom = airfoils.generate_naca4("0012")
        with self.assertRaises(ValueError):
            external_solvers.run_polar("neuralfoil", geom, [], [0.1], -10, 10, 1.0)
        with self.assertRaises(ValueError):
            external_solvers.run_polar("neuralfoil", geom, [1e6], [], -10, 10, 1.0)

    def test_non_positive_alpha_step_raises_value_error(self):
        geom = airfoils.generate_naca4("0012")
        with self.assertRaises(ValueError):
            external_solvers.run_polar("neuralfoil", geom, [1e6], [0.1], -10, 10, 0.0)

    def test_geometry_without_coordinates_raises_value_error(self):
        if not NEURALFOIL_AVAILABLE:
            self.skipTest("neuralfoil not installed -- covered by test_missing_package_raises_clear_error")
        empty_geom = ProfileGeometry(source="naca4", naca_code="0012")  # x/y vazios
        with self.assertRaises(ValueError):
            external_solvers.run_polar("neuralfoil", empty_geom, [1e6], [0.1], -10, 10, 1.0)

    def test_missing_package_raises_clear_error_not_traceback(self):
        if NEURALFOIL_AVAILABLE:
            self.skipTest("neuralfoil is installed in this environment -- nothing to test here")
        geom = airfoils.generate_naca4("0012")
        with self.assertRaises(RuntimeError) as ctx:
            external_solvers.run_polar("neuralfoil", geom, [1e6], [0.1], -10, 10, 1.0)
        msg = str(ctx.exception)
        self.assertIn("neuralfoil", msg)
        self.assertIn("pip install", msg)


@unittest.skipUnless(NEURALFOIL_AVAILABLE, "'neuralfoil' package not installed in this environment")
class TestRunPolarComputation(unittest.TestCase):
    def test_run_polar_produces_valid_polarslices(self):
        geom = airfoils.generate_naca4("0012")
        slices = external_solvers.run_polar("neuralfoil", geom, [1e6], [0.1], -10, 10, 2.0)
        self.assertGreater(len(slices), 0)
        for s in slices:
            self.assertGreater(len(s.alpha_deg), 0)
            self.assertTrue(np.all(np.isfinite(s.cl)))
            self.assertTrue(np.all(np.isfinite(s.cd)))
            self.assertTrue(min(s.alpha_deg) >= -10 - 1e-6)
            self.assertTrue(max(s.alpha_deg) <= 10 + 1e-6)

    def test_run_polar_multiple_re_mach_combinations(self):
        geom = airfoils.generate_naca4("0012")
        slices = external_solvers.run_polar("neuralfoil", geom, [1e5, 1e6], [0.1, 0.3], -5, 5, 1.0)
        combos = {(s.reynolds, s.mach) for s in slices}
        self.assertEqual(len(combos), 4)

    def test_non_convergent_extreme_alpha_is_dropped_not_raised(self):
        geom = airfoils.generate_naca4("0012")
        # Aggressive range (deep stall) -- must not propagate exception;
        # at worst, low-confidence points are discarded.
        slices = external_solvers.run_polar("neuralfoil", geom, [1e6], [0.1], -85, 85, 5.0)
        self.assertIsInstance(slices, list)


if __name__ == "__main__":
    unittest.main()
