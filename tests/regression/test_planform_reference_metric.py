"""Independent checks for the reference planform metric used by studies.

These tests deliberately do not call ``Geometry.reference_planform_integral``
to build the expected value.  The production studies helper already uses that
method, so doing so here would only prove that a function equals itself.
"""
from __future__ import annotations

import math
import unittest

from zbemt import geometry, studies


class TestReferencePlanformMetric(unittest.TestCase):
    def test_rectangular_planform_matches_closed_form(self):
        chord = 0.08
        blades = 4
        geom = geometry.generate_rectangular(
            root_cutout_norm=0.20,
            radius_m=1.0,
            chord_norm=chord,
            twist_root_deg=0.0,
            twist_tip_deg=0.0,
            n_blades=blades,
        )

        metrics = studies._blade_planform_metrics(geom)

        # The reference metric is defined on the complete parametric blade
        # planform from axis to tip, not only on the discretized aerodynamic
        # stations that begin at the root cutout.
        expected_integral = chord
        self.assertAlmostEqual(metrics["blade_planform_integral"], expected_integral, places=12)
        self.assertAlmostEqual(metrics["aspect_ratio"], 1.0 / expected_integral, places=12)
        self.assertAlmostEqual(
            metrics["solidity"], blades * expected_integral / math.pi, places=12)

    def test_linear_taper_matches_trapezoid_closed_form(self):
        root_chord = 0.10
        tip_chord = 0.04
        blades = 3
        geom = geometry.generate_tapered(
            root_chord_norm=root_chord,
            tip_chord_norm=tip_chord,
            twist_root_deg=0.0,
            twist_tip_deg=0.0,
            root_cutout_norm=0.15,
            radius_m=1.0,
            n_blades=blades,
            n_stations=17,
        )

        metrics = studies._blade_planform_metrics(geom)

        # Integral_0^1 [c_root + (c_tip-c_root) r] dr.
        expected_integral = 0.5 * (root_chord + tip_chord)
        self.assertAlmostEqual(metrics["blade_planform_integral"], expected_integral, places=12)
        self.assertAlmostEqual(metrics["aspect_ratio"], 1.0 / expected_integral, places=12)
        self.assertAlmostEqual(
            metrics["solidity"], blades * expected_integral / math.pi, places=12)


if __name__ == "__main__":
    unittest.main()
