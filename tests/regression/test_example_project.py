"""Verify the versioned example projects end to end.

Each test loads a project, runs its configured case or sweep, and checks convergence
and physically plausible ranges. Project files are inputs and solver results are
outputs; the tests intentionally exercise the same public execution path used by
users. The suite does not rewrite example data.
"""

import os
import unittest

import numpy as np

from zbemt import api

_PROJECT_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
                              "projects", "starter_rotor")


@unittest.skipUnless(os.path.isdir(_PROJECT_PATH), "example project is not present in this checkout")
class TestExampleProjectMuSweep(unittest.TestCase):
    """End-to-end integration test: opens the starter rotor project
    shipped with the platform (same production mesh, Ne=90/Npsi=144) and
    reproduces the original mu_x sweep from zBEMT.py (Section 12 of the plan)
    via api.open_project + api.run_batch — the same path used by the GUI/
    main_batch.py. Serves as regression: if a future refactor to
    bemt.py/studies.py changes the physical result unintentionally, this test
    breaks."""

    @classmethod
    def setUpClass(cls):
        cls.project = api.open_project(_PROJECT_PATH)
        # `starter_rotor` carries more than one saved batch; the original
        # zBEMT.py Section 12 sweep is the one with sweep_kind="mu_sweep"
        # (a parametric definition, not an explicit list of conditions) --
        # selecting by position instead of by kind broke silently once a
        # second, differently-ordered batch was added to the project.
        cls.batch = next(b for b in cls.project.batches if b.sweep_kind == "mu_sweep")
        cls.results = api.run_batch(cls.project, cls.batch)

    def test_geometry_loaded_correctly(self):
        geom = self.project.geometry
        self.assertEqual(geom.n_blades, 4)
        self.assertAlmostEqual(geom.radius_m, 1.25)
        self.assertAlmostEqual(geom.root_cutout_norm, 0.2143)
        self.assertEqual(len(geom.r_norm), 15)

    def test_batch_definition_loaded_correctly(self):
        batch = self.batch
        self.assertEqual(batch.sweep_kind, "mu_sweep")
        self.assertEqual(batch.sweep_params["mu_values"],
                          [0, 0.05, 0.1, 0.13, 0.16, 0.19, 0.23, 0.3, 0.4])
        self.assertEqual(batch.sweep_params["rpm"], 1200)

    def test_one_result_per_mu_value(self):
        self.assertEqual(len(self.results), 9)

    def test_all_cases_converge_well(self):
        # Note (default update -- see bemt.BEMTConfig): with
        # `reverse_flow_model='viterna_full_range'` (new default) the polar
        # continues across -180..+180 but with very steep derivative near the
        # reverse flow region boundary; in a small fraction of
        # elements (~<3%, concentrated exactly at that boundary, with low W
        # and negligible contribution to integrated load -- see
        # comment on `early_exit_fraction`/`stagnation_patience` in
        # bemt.py) the solver does not close `tol` before `max_iter`. It only
        # appears visibly at the highest mu_x of the sweep (mu_x=0.4, larger
        # reverse flow region); that is why the threshold here is 95%, not 99%.
        for r in self.results:
            self.assertGreater(r.summary["convergence_pct"], 95.0,
                                f"{r.condition_name}: poor convergence ({r.summary['convergence_pct']:.1f}%)")

    def test_ct_increases_monotonically_with_mu(self):
        # With fixed collective/RPM, increasing mu_x (advance) increases the
        # resolved CT in this configuration -- expected and stable physical
        # behavior between solvers (checked in test_bemt.py); here it becomes
        # regression baseline for the full open_project->run_batch pipeline.
        ct_values = [r.summary["CT"] for r in self.results]
        self.assertEqual(ct_values, sorted(ct_values))

    def test_ct_values_within_expected_ballpark(self):
        # Loose numeric baseline (does not lock to 4th digit -- that is the
        # responsibility of bemt.py, see Section 10 of the plan); only serves
        # to catch gross regressions (e.g., sign flipped, 2x factor, etc.).
        ct_values = np.array([r.summary["CT"] for r in self.results])
        self.assertTrue(np.all(ct_values > 0.01))
        self.assertTrue(np.all(ct_values < 0.1))

_PROP_PROJECT_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
                                  "projects", "starter_propeller")


@unittest.skipUnless(os.path.isdir(_PROP_PROJECT_PATH), "starter_propeller project is not present in this checkout")
class TestExampleStarterPropeller(unittest.TestCase):
    """End-to-end integration test for the starter_propeller:
    opens the project and runs the axial velocity sweep via run_batch."""

    @classmethod
    def setUpClass(cls):
        cls.project = api.open_project(_PROP_PROJECT_PATH)
        cls.results = api.run_batch(cls.project, cls.project.batches[0])

    def test_geometry_loaded_correctly(self):
        geom = self.project.geometry
        self.assertEqual(geom.n_blades, 3)
        self.assertAlmostEqual(geom.radius_m, 0.94)
        self.assertTrue(self.project.config["is_propeller"])

    def test_all_cases_converge(self):
        for r in self.results:
            self.assertGreater(r.summary["convergence_pct"], 95.0,
                                f"{r.condition_name}: poor convergence")

    def test_propulsive_efficiency_behavior(self):
        # At V=0 propulsive efficiency is 0; in cruise it should be positive and < 1
        etas = [r.summary["eta_prop"] for r in self.results]
        self.assertEqual(etas[0], 0.0)
        self.assertTrue(all(0.0 <= e < 1.0 for e in etas))


if __name__ == "__main__":
    unittest.main()
