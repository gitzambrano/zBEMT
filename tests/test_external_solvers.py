"""Verify optional external polar-engine integration.

The tests check supported-engine identification, availability detection, XFOIL
polar parsing, request validation, and returned polar slices when an engine is
installed. They also verify clear behavior when an engine is unavailable.
Geometry and operating-point inputs are isolated fixtures; no project is
persisted by these tests.
"""

import os
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import numpy as np

from zbemt import external_solvers
from zbemt import airfoils
from zbemt.models import ProfileGeometry

NEURALFOIL_AVAILABLE = external_solvers.is_available("neuralfoil")


class TestSupportedEngines(unittest.TestCase):
    def test_neuralfoil_and_xfoil_are_supported(self):
        self.assertEqual(external_solvers.SUPPORTED_ENGINES, ("neuralfoil", "xfoil"))

    def test_unknown_engine_raises_value_error_listing_supported(self):
        with self.assertRaises(ValueError) as ctx:
            external_solvers.run_polar("bogus", ProfileGeometry(), [1e6], [0.1], -10, 10, 1.0)
        for engine_name in external_solvers.SUPPORTED_ENGINES:
            self.assertIn(engine_name, str(ctx.exception))


class TestIsAvailable(unittest.TestCase):
    def test_is_available_reflects_real_package_presence(self):
        import importlib.util
        expected = importlib.util.find_spec("neuralfoil") is not None
        self.assertEqual(external_solvers.is_available("neuralfoil"), expected)

    def test_is_available_xfoil_reflects_real_binary_presence(self):
        # The resolver checks ZBEMT_XFOIL_BIN first, then PATH; mirror
        # both sources so the assertion holds on machines where the
        # environment variable is set to a real executable.
        with mock.patch.dict(os.environ, {"ZBEMT_XFOIL_BIN": ""}):
            expected = shutil.which("xfoil") is not None
            self.assertEqual(external_solvers.is_available("xfoil"), expected)

    def test_is_available_xfoil_honors_zbemt_xfoil_bin(self):
        with tempfile.TemporaryDirectory() as tmp:
            fake = Path(tmp) / ("xfoil.exe" if os.name == "nt" else "xfoil")
            fake.write_bytes(b"stub")
            with mock.patch.dict(os.environ,
                                 {"ZBEMT_XFOIL_BIN": str(fake)}):
                self.assertTrue(external_solvers.is_available("xfoil"))
                self.assertEqual(external_solvers._xfoil_command(), str(fake))

    def test_is_available_false_for_unknown_engine(self):
        self.assertFalse(external_solvers.is_available("bogus"))


class TestParseXfoilPolar(unittest.TestCase):
    HEADER = (
        "# Comment line one\n"
        "# Comment line two\n"
        "\n"
        "  XFOIL         Version 6.99\n"
        "\n"
        "  alpha      CL        CD       CDp       CM\n"
        "  ------  --------  --------  --------  --------\n"
    )

    def test_parses_rows_and_skips_nan_junk_and_blank_lines(self):
        text = self.HEADER + (
            "  -5.000   -0.5500   0.00600   0.00200   -0.0100\n"
            "  -4.000   -0.4400     NaN     0.00210   -0.0085\n"
            "junk row without numbers\n"
            "  -3.000   -0.3300   0.00580   0.00190   -0.0070\n"
            "\n"
            "\n"
        )
        alpha_deg, cl, cd = external_solvers._parse_xfoil_polar(text)
        self.assertEqual(alpha_deg, [-5.0, -3.0])
        self.assertEqual(cl, [-0.55, -0.33])
        self.assertEqual(cd, [0.006, 0.0058])

    def test_empty_text_raises_value_error(self):
        with self.assertRaises(ValueError):
            external_solvers._parse_xfoil_polar("")
        with self.assertRaises(ValueError):
            external_solvers._parse_xfoil_polar("\n \n")

    def test_content_without_header_raises_value_error(self):
        with self.assertRaises(ValueError):
            external_solvers._parse_xfoil_polar(
                "no column header anywhere\n1.0 2.0 3.0\n"
            )


class TestXfoilScript(unittest.TestCase):
    """The pure script builder: the three XFOIL-dedicated adjustment
    values reach the binary through the spellings XFOIL 6.99 recognizes
    (`VPAR`, then `N` for Ncrit and `XTR top bot`), and the accumulation
    order that is verified working stays intact (PACC opens BEFORE ASEQ,
    closes AFTER it, and the script ends with the dot that leaves .OPER
    plus QUIT)."""

    def test_contains_adjustment_lines_with_the_given_numbers(self):
        text = external_solvers._xfoil_script(2e5, -4, 8, 2, 9.5, 0.8, 1.0)
        self.assertIn("VPAR\n", text)
        self.assertIn("\nN 9.5\n", text)
        self.assertIn("XTR 0.8 1\n", text)

    def test_adjustment_lines_come_after_visc_inside_oper(self):
        # The transition parameters live in .VPAR, a submenu that exists
        # only after VISC enables viscous mode; before it they are
        # unknown commands and the binary runs with its own baseline.
        text = external_solvers._xfoil_script(2e5, -4, 8, 2, 12.0, 0.6, 0.6)
        oper = text.index("OPER\n")
        visc = text.index("VISC ")
        vpar = text.index("VPAR\n")
        ncrit = text.index("\nN ")
        xtr = text.index("\nXTR ")
        back_to_oper = text.index("\n\nITER")
        self.assertLess(oper, visc)
        self.assertLess(visc, vpar)
        self.assertLess(vpar, ncrit)
        self.assertLess(ncrit, xtr)
        self.assertLess(xtr, back_to_oper)

    def test_keeps_accumulation_open_before_aseq_and_closed_after(self):
        text = external_solvers._xfoil_script(1e6, -10, 10, 1.0, 9.0, 1.0, 1.0)
        first_pacc = text.index("PACC")
        aseq = text.index("ASEQ")
        last_pacc = text.rindex("PACC")
        self.assertLess(first_pacc, aseq)
        self.assertLess(aseq, last_pacc)

    def test_ends_with_dot_and_quit(self):
        text = external_solvers._xfoil_script(1e6, -10, 10, 1.0, 9.0, 1.0, 1.0)
        self.assertTrue(text.endswith(".\nQUIT\n"))

    def test_alpha_and_reynolds_reach_their_commands(self):
        text = external_solvers._xfoil_script(2e5, -4, 8, 2, 9.0, 1.0, 1.0)
        self.assertIn("VISC 200000\n", text)
        self.assertIn("ASEQ -4 8 2\n", text)


class TestXfoilAdjustmentValidation(unittest.TestCase):
    """Out-of-range adjustment inputs are rejected with ValueError BEFORE
    any subprocess starts (a pure check), so an invalid value costs no
    process spawn and never reaches the binary."""

    def _geom(self):
        return airfoils.generate_naca4("0012")

    def test_non_positive_or_nan_ncrit_raises_value_error_before_subprocess(self):
        for bad in (0.0, -3.0, float("nan")):
            with self.subTest(ncrit=bad):
                with mock.patch.object(external_solvers.subprocess, "run") as run_mock:
                    with self.assertRaises(ValueError):
                        external_solvers.run_polar(
                            "xfoil", self._geom(), [1e6], [0.1], -10, 10, 1.0,
                            ncrit=bad)
                run_mock.assert_not_called()

    def test_xtr_outside_zero_one_raises_value_error_before_subprocess(self):
        for name, bad in (("xtr_top", 0.0), ("xtr_top", 1.5),
                          ("xtr_bot", 0.0), ("xtr_bot", 2.0)):
            with self.subTest(name=name, value=bad):
                kwargs = {name: bad}
                with mock.patch.object(external_solvers.subprocess, "run") as run_mock:
                    with self.assertRaises(ValueError):
                        external_solvers.run_polar(
                            "xfoil", self._geom(), [1e6], [0.1], -10, 10, 1.0,
                            **kwargs)
                run_mock.assert_not_called()

    def test_boundary_values_are_accepted_by_the_validator(self):
        # No exception: finite ncrit > 0 and xtr in (0, 1].
        external_solvers._validate_xfoil_adjustments(15.0, 1.0, 0.05)


class TestRunPolarXfoilAvailability(unittest.TestCase):
    def test_missing_binary_raises_runtime_error_with_clear_message(self):
        geom = airfoils.generate_naca4("0012")
        # Cover BOTH resolution sources: an empty ZBEMT_XFOIL_BIN and a
        # PATH lookup that finds nothing.
        with mock.patch.dict(os.environ, {"ZBEMT_XFOIL_BIN": ""}):
            with mock.patch.object(external_solvers.shutil, "which",
                                   return_value=None):
                with self.assertRaises(RuntimeError) as ctx:
                    external_solvers.run_polar(
                        "xfoil", geom, [1e6], [0.1], -10, 10, 1.0)
        msg = str(ctx.exception)
        self.assertIn("'xfoil' executable", msg)
        self.assertIn("ZBEMT_XFOIL_BIN", msg)


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
