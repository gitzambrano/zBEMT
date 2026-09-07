"""Regression tests for the empirical GLOBAL inflow models.

The tests focus on physical/model identities rather than golden output values:
- one disk-wide harmonic gradient for every global model;
- self-consistency of the azimuthally averaged annular momentum closure;
- Coleman-and-Feingold and Drees coefficient formulas;
- hover symmetry and azimuthal-grid convergence;
- operation with compressibility and Prandtl tip loss enabled.
"""

import math
import unittest

import numpy as np

import zbemt.bemt as bemt


class GlobalInflowModelTests(unittest.TestCase):
    @staticmethod
    def rotor():
        r = np.array([0.20, 0.45, 0.70, 1.00])
        chord = np.full_like(r, 0.20)
        theta = np.full_like(r, 12.0)
        return bemt.Rotor(
            R=1.4,
            Nb=4,
            Omega_rpm=1000.0,
            r_root_norm_geom=0.20,
            r_tip_norm_geom=1.0,
            r_geom=r,
            chord_geom=chord,
            theta_geom_deg=theta,
        )

    @staticmethod
    def airfoil():
        return bemt.AnalyticalAirfoil(
            cl_alpha=5.7,
            cd0=0.016,
            k=0.0,
            stall_model="linear",
        )

    @staticmethod
    def cfg(model, *, npsi=72, corrected=False):
        return bemt.BEMTConfig(
            Ne=30,
            Npsi=npsi,
            inflow_field_model=model,
            prandtl_loss_mode="tip" if corrected else "off",
            use_compressibility=bool(corrected),
            reverse_flow_model="simple_flip",
            use_rotational_augmentation=False,
            use_radial_flow_correction=False,
            use_dynamic_stall=False,
            solver="newton",
            max_iter=120,
            tol=1e-7,
            relax=0.4,
            collect_history=False,
        )

    def solve(self, model, mu=0.25, *, npsi=72, corrected=False, vz=0.0):
        rotor = self.rotor()
        cfg = self.cfg(model, npsi=npsi, corrected=corrected)
        maps = bemt.solve_bemt(rotor, self.airfoil(), cfg, mu_x=mu, Vz=vz)
        return rotor, cfg, maps, bemt.aggregate_results(rotor, cfg, maps)

    def test_legacy_glauert_global_migrates_to_axisymmetric_glauert(self):
        from zbemt.studies import _migrate_config_dict
        self.assertEqual(
            _migrate_config_dict({"inflow_field_model": "glauert_global"})["inflow_field_model"],
            "glauert_local",
        )
        self.assertEqual(
            _migrate_config_dict({"inflow_model": "glauert", "inflow_coupling": "global"})["inflow_field_model"],
            "glauert_local",
        )

    def test_coleman_feingold_gradient_matches_johnson_ndarc_form(self):
        mu = 0.23
        lam = np.array([0.061])
        kx, ky = bemt._inflow_harmonics("coleman_feingold", mu, lam)
        expected = ((15.0 * math.pi / 32.0) * mu
                    / (math.sqrt(mu * mu + lam[0] * lam[0]) + abs(lam[0])))
        self.assertAlmostEqual(float(kx[0]), expected, places=12)
        self.assertAlmostEqual(float(ky[0]), -2.0 * mu, places=12)

    def test_drees_gradient_matches_wake_angle_form(self):
        mu = 0.28
        lam = np.array([0.072])
        kx, ky = bemt._inflow_harmonics("drees", mu, lam)
        chi = math.atan2(mu, lam[0])
        expected = ((4.0 / 3.0)
                    * (1.0 - math.cos(chi) - 1.8 * mu * mu)
                    / math.sin(chi))
        self.assertAlmostEqual(float(kx[0]), expected, places=12)
        self.assertAlmostEqual(float(ky[0]), -2.0 * mu, places=12)

    def test_all_global_models_collapse_to_axisymmetric_hover(self):
        for model in (
            "coleman_global",
            "coleman_feingold_global",
            "drees_global",
        ):
            with self.subTest(model=model):
                _, _, maps, _ = self.solve(model, mu=0.0)
                spread = np.max(np.ptp(maps["lambda_i"], axis=1))
                self.assertLess(spread, 1e-12)
                self.assertAlmostEqual(float(maps["global_inflow_Kx"]), 0.0, places=14)
                self.assertAlmostEqual(float(maps["global_inflow_Ky"]), 0.0, places=14)
                self.assertTrue(bool(maps["global_inflow_converged"]))

    def test_global_outer_closure_converges_from_full_2d_loading(self):
        for model in (
            "coleman_global",
            "coleman_feingold_global",
            "drees_global",
        ):
            with self.subTest(model=model):
                _, _, maps, _ = self.solve(model, mu=0.30)
                self.assertTrue(bool(maps["global_inflow_converged"]))
                self.assertLess(float(maps["global_inflow_residual"]), 2e-6)
                self.assertGreaterEqual(int(maps["global_inflow_iterations"]), 1)
                self.assertTrue(np.all(np.isfinite(maps["lambda_i"])))
                self.assertTrue(np.all(np.isfinite(maps["Fn"])))

    def test_global_field_uses_one_disk_wide_harmonic_pair(self):
        for model in (
            "coleman_global",
            "coleman_feingold_global",
            "drees_global",
        ):
            with self.subTest(model=model):
                _, _, maps, _ = self.solve(model, mu=0.24)
                lam = np.asarray(maps["lambda_i"], dtype=float)
                mean_r = np.mean(lam, axis=1)
                kx = float(maps["global_inflow_Kx"])
                ky = float(maps["global_inflow_Ky"])
                expected = mean_r[:, None] * (
                    1.0
                    + kx * maps["R_NORM"] * np.cos(maps["PSI"])
                    + ky * maps["R_NORM"] * np.sin(maps["PSI"])
                )
                # Moderate mu/pitch avoids the +/-0.5 safety clipping, so the
                # first-harmonic construction should be exact to roundoff.
                self.assertLess(float(np.max(np.abs(lam - expected))), 2e-11)

    def test_coleman_and_coleman_feingold_are_distinct_models(self):
        _, _, c, _ = self.solve("coleman_global", mu=0.25)
        _, _, cf, _ = self.solve("coleman_feingold_global", mu=0.25)
        self.assertNotAlmostEqual(
            float(c["global_inflow_Kx"]), float(cf["global_inflow_Kx"]), places=5)
        self.assertAlmostEqual(float(c["global_inflow_Ky"]), 0.0, places=12)
        self.assertAlmostEqual(float(cf["global_inflow_Ky"]), -0.5, places=12)

    def test_drees_global_uses_lateral_gradient(self):
        mu = 0.21
        _, _, maps, _ = self.solve("drees_global", mu=mu)
        self.assertAlmostEqual(float(maps["global_inflow_Ky"]), -2.0 * mu, places=12)

    def test_global_solution_is_stable_to_azimuthal_refinement(self):
        _, _, m72, s72 = self.solve("drees_global", mu=0.27, npsi=72)
        _, _, m144, s144 = self.solve("drees_global", mu=0.27, npsi=144)
        rel_ct = abs(s144["CT"] - s72["CT"]) / max(abs(s144["CT"]), 1e-12)
        rel_lam = abs(
            float(m144["global_inflow_lambda_i_mean"])
            - float(m72["global_inflow_lambda_i_mean"])
        ) / max(abs(float(m144["global_inflow_lambda_i_mean"])), 1e-12)
        self.assertLess(rel_ct, 0.02)
        self.assertLess(rel_lam, 0.02)

    def test_global_models_work_with_mach_and_prandtl_tip(self):
        for model in (
            "coleman_global",
            "coleman_feingold_global",
            "drees_global",
        ):
            with self.subTest(model=model):
                _, _, maps, summary = self.solve(model, mu=0.30, corrected=True)
                self.assertTrue(bool(maps["global_inflow_converged"]))
                self.assertLess(float(maps["global_inflow_residual"]), 5e-6)
                self.assertTrue(math.isfinite(summary["CT"]))
                self.assertTrue(math.isfinite(summary["CQ"]))


if __name__ == "__main__":
    unittest.main()
