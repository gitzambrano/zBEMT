"""Verify the core blade-element/momentum solver.

The tests cover hover, forward flight, propeller conventions, solver-method
agreement, convergence identities, airfoil extrapolation, compressibility limits,
and heterogeneous sections. Inputs are controlled configurations and model objects;
outputs are compared against physical identities, tolerances, and golden values.
These tests do not define GUI or file-format behavior.
"""

import math
import os
import unittest
import warnings

import numpy as np

from zbemt.bemt import (
    Rotor, BEMTConfig, AnalyticalAirfoil, TableAirfoil, MultiSectionTableAirfoil,
    ViternaExtendedAirfoil, HeterogeneousMultiSectionAirfoil, solve_bemt, solve_bemt_flight,
    aggregate_results, resolve_advance_velocity,
    BETA_MINIMO_DE_PRANDTL_GLAUERT, MACH_MAXIMO_DE_PRANDTL_GLAUERT,
)


def _small_rotor(n_blades=2) -> Rotor:
    """Well-behaved rotor, mesh coarse enough to run fast
    in the tests (it's not about numerical accuracy, it's about the API/
    engine identities -- bemt.py itself already has its own self-test
    blocks in __main__, see Section 10 of the file)."""
    r = np.array([0.15, 0.4, 0.7, 1.0])
    chord = np.array([0.09, 0.08, 0.06, 0.03])   # meters
    theta = np.array([16.0, 10.0, 5.0, 2.0])     # degrees
    return Rotor(R=1.0, Nb=n_blades, Omega_rpm=600.0, r_root_norm_geom=0.15,
                 r_tip_norm_geom=1.0, r_geom=r, chord_geom=chord, theta_geom_deg=theta)


def _fast_cfg(**overrides) -> BEMTConfig:
    base = dict(Ne=10, Npsi=16, solver="newton", max_iter=100, collect_history=False)
    base.update(overrides)
    return BEMTConfig(**base)


class TestSolveBemtHover(unittest.TestCase):
    """Hover (mu_x=0, Vz=0): the simplest and most robust case of the engine."""

    def setUp(self):
        self.rotor = _small_rotor()
        self.airfoil = AnalyticalAirfoil(stall_model="clip")
        self.cfg = _fast_cfg()

    def test_converges_and_produces_finite_maps(self):
        maps = solve_bemt(self.rotor, self.airfoil, self.cfg, mu_x=0.0, Vz=0.0)
        for key in ("Fn", "Ft", "alpha_eff", "Cl", "Cd", "lambda_i"):
            self.assertTrue(np.all(np.isfinite(maps[key])), f"{key} has non-finite values")
        # in hover with a reasonable positive collective, the overwhelming
        # majority of the mesh should converge within max_iter=100
        self.assertGreater(np.mean(maps["converged"]), 0.9)

    def test_positive_thrust_for_positive_collective(self):
        rotor = _small_rotor()
        rotor.theta_geom_deg = rotor.theta_geom_deg + 4.0  # more collective
        maps = solve_bemt(rotor, self.airfoil, self.cfg, mu_x=0.0, Vz=0.0)
        summary = aggregate_results(rotor, self.cfg, maps)
        self.assertGreater(summary["Thrust"], 0.0)
        self.assertGreater(summary["Torque"], 0.0)
        self.assertGreater(summary["CT"], 0.0)

    def test_more_collective_means_more_thrust(self):
        low = _small_rotor()
        high = _small_rotor()
        high.theta_geom_deg = high.theta_geom_deg + 5.0
        maps_low = solve_bemt(low, self.airfoil, self.cfg, mu_x=0.0, Vz=0.0)
        maps_high = solve_bemt(high, self.airfoil, self.cfg, mu_x=0.0, Vz=0.0)
        T_low = aggregate_results(low, self.cfg, maps_low)["Thrust"]
        T_high = aggregate_results(high, self.cfg, maps_high)["Thrust"]
        self.assertGreater(T_high, T_low)

    def test_all_solvers_agree_approximately(self):
        # the 4 iterative methods solve the SAME fixed-point equation;
        # they should converge to similar thrust/torque (not identical --
        # different tolerances/relaxation), serving as a cross-check.
        thrusts = {}
        for solver in ("newton", "fixed_point", "bisection", "aitken"):
            cfg = _fast_cfg(solver=solver, max_iter=150)
            maps = solve_bemt(self.rotor, self.airfoil, cfg, mu_x=0.0, Vz=0.0)
            thrusts[solver] = aggregate_results(self.rotor, cfg, maps)["Thrust"]
        values = list(thrusts.values())
        spread = (max(values) - min(values)) / max(abs(np.mean(values)), 1e-9)
        self.assertLess(spread, 0.05, f"solvers divergem demais entre si: {thrusts}")


class TestSolversAgreeInForwardFlight(unittest.TestCase):
    """T4 from production-plan.md. The test above (`test_all_solvers_agree_approximately`)
    only covers hover, coarse mesh (Ne=10, Npsi=16) and Thrust -- it is close
    to stall and the reverse-flow boundary, in forward flight, that the
    four solvers have a real chance of diverging (see the bemt.py docstring:
    `bisection` exists as a "fallback for non-monotonic post-stall
    regions", which only makes sense if the other regions are
    difficult for it).

    Mesh Ne=40/Npsi=32 (4x finer than `_fast_cfg`'s, still far
    from the production mesh 120x180, but enough to not mask the effect --
    measured below): the engine is vectorized (~ms per solve on this mesh).

    The tolerances per quantity were MEASURED, not copied from the hover
    test: CT (the most "smoothed" integral, dominated by the
    well-behaved elements) agrees to <1%; CQ/CH/CMx, more sensitive to
    small phase and sign corrections near the reverse-flow
    boundary, agree worse. See `test_fixed_point_convergence_is_incomplete_near_reverse_flow`
    for the finding about the weakest solver."""

    @classmethod
    def setUpClass(cls):
        cls.rotor = _small_rotor()
        cls.airfoil = AnalyticalAirfoil(stall_model="clip")

    def _summaries(self, mu_x, solvers, max_iter=300):
        out = {}
        for solver in solvers:
            cfg = _fast_cfg(Ne=40, Npsi=32, solver=solver, max_iter=max_iter,
                             reverse_flow_model="flat_plate")
            maps = solve_bemt(self.rotor, self.airfoil, cfg, mu_x=mu_x, Vz=0.0)
            out[solver] = aggregate_results(self.rotor, cfg, maps)
        return out

    def _assert_spread_below(self, summaries, key, tol, mu_x):
        values = [s[key] for s in summaries.values()]
        spread = (max(values) - min(values)) / max(abs(np.mean(values)), 1e-9)
        self.assertLess(spread, tol,
                        f"mu_x={mu_x}: solvers divergem demais em {key} (spread={spread:.3%}, "
                        f"tolerance={tol:.0%}): { {k: v[key] for k, v in summaries.items()} }")

    def test_newton_bisection_aitken_agree_at_mu_0_2_and_0_35(self):
        """`fixed_point` is deliberately left out of this comparison -- see
        the next test, which documents why it does not converge
        enough in this range even with a high max_iter, which would make
        it an outlier due to incomplete convergence, not due to real
        physical disagreement between the OTHER three solvers (which is
        what this test measures).

        Measured tolerances (max-min spread / mean, over the 3 solvers, at
        mu_x=0.2 and mu_x=0.35 on this mesh): CT <=0.8%, CQ <=8.4%, CH <=4.3%,
        CMx <=14.3%, CMy <=0.8%. The bounds below give margin (~1.4x) over
        the worst measured case, without being loose enough to let a
        factor-2 regression through like the old bands did."""
        for mu_x in (0.2, 0.35):
            with self.subTest(mu_x=mu_x):
                summaries = self._summaries(mu_x, ("newton", "bisection", "aitken"))
                self._assert_spread_below(summaries, "CT", 0.02, mu_x)
                self._assert_spread_below(summaries, "CQ", 0.12, mu_x)
                self._assert_spread_below(summaries, "CH", 0.08, mu_x)
                self._assert_spread_below(summaries, "CMx", 0.20, mu_x)
                self._assert_spread_below(summaries, "CMy", 0.03, mu_x)

    def test_fixed_point_convergence_is_incomplete_near_reverse_flow(self):
        """FINDING: in forward flight (mu_x=0.2), the `fixed_point` solver
        (pure Picard) does NOT converge over the whole mesh even with
        max_iter=1000 -- measured: converged fraction ~75% at max_iter=300
        and still only ~95.5% at max_iter=1000 (Ne=40, Npsi=32, mu_x=0.2),
        versus 100% (bisection, aitken) or ~99.9% (newton) at max_iter=300.
        This is not a loose test in disguise: instead of forcing
        `fixed_point` to agree with the others (which would require a
        tolerance so wide it would mask a real regression in the other
        three), the test records the limitation as expected behavior of
        the simplest solver near the reverse-flow boundary, and still
        checks that CT (dominated by the well-behaved elements) stays in
        a sane range regardless."""
        cfg_300 = _fast_cfg(Ne=40, Npsi=32, solver="fixed_point", max_iter=300,
                             reverse_flow_model="flat_plate")
        maps_300 = solve_bemt(self.rotor, self.airfoil, cfg_300, mu_x=0.2, Vz=0.0)
        frac_300 = float(np.mean(maps_300["converged"]))

        cfg_1000 = _fast_cfg(Ne=40, Npsi=32, solver="fixed_point", max_iter=1000,
                              reverse_flow_model="flat_plate")
        maps_1000 = solve_bemt(self.rotor, self.airfoil, cfg_1000, mu_x=0.2, Vz=0.0)
        frac_1000 = float(np.mean(maps_1000["converged"]))

        self.assertLess(frac_300, 0.90,
                        f"expected fixed_point with clearly incomplete convergence at "
                        f"max_iter=300 perto do fluxo reverso; obteve {frac_300:.3%}")
        self.assertLess(frac_1000, 0.99,
                        f"esperava fixed_point ainda incompleto mesmo em max_iter=1000; "
                        f"obteve {frac_1000:.3%} -- se isso passou a dar >=99%, o achado "
                        "no longer holds and this test can be removed/revised")

        # even with incomplete convergence over part of the mesh, CT
        # (the disk integral, dominated by the well-converging elements)
        # should not be grossly outside the range of the other solvers.
        summary_fp = aggregate_results(self.rotor, cfg_300, maps_300)
        summary_newton = aggregate_results(
            self.rotor, _fast_cfg(Ne=40, Npsi=32, solver="newton", max_iter=300,
                                   reverse_flow_model="flat_plate"),
            solve_bemt(self.rotor, self.airfoil,
                       _fast_cfg(Ne=40, Npsi=32, solver="newton", max_iter=300,
                                 reverse_flow_model="flat_plate"), mu_x=0.2, Vz=0.0))
        rel_ct = abs(summary_fp["CT"] - summary_newton["CT"]) / abs(summary_newton["CT"])
        self.assertLess(rel_ct, 0.05,
                        f"CT from fixed_point (not fully converged) drifted too far "
                        f"do newton: {rel_ct:.3%}")


class TestSolveBemtForwardFlight(unittest.TestCase):
    def test_runs_with_nonzero_advance_ratio(self):
        rotor = _small_rotor()
        airfoil = AnalyticalAirfoil(stall_model="clip")
        cfg = _fast_cfg(reverse_flow_model="flat_plate")
        maps = solve_bemt(rotor, airfoil, cfg, mu_x=0.2, Vz=0.0)
        self.assertTrue(np.all(np.isfinite(maps["Fn"])))
        summary = aggregate_results(rotor, cfg, maps)
        self.assertTrue(np.isfinite(summary["Thrust"]))
        self.assertTrue(np.isfinite(summary["H"]))


class TestResolveAdvanceVelocityIdentities(unittest.TestCase):
    """J_x = pi*mu_x is an exact identity of the rotor<->propeller
    nondimensionalization (see comment in aggregate_results, Sec.6c) --
    checked here starting from the input (resolve_advance_velocity), not
    only at the output."""

    def test_mu_and_J_are_consistent(self):
        rotor = _small_rotor()
        cfg = _fast_cfg()
        mu_direct, Vv_direct, meta_direct = resolve_advance_velocity(rotor, cfg, mu_x=0.25, alpha_deg=0.0)
        self.assertAlmostEqual(mu_direct, 0.25, places=9)
        self.assertAlmostEqual(meta_direct["J_x"], np.pi * 0.25, places=9)

    def test_j_input_recovers_same_mu(self):
        rotor = _small_rotor()
        cfg = _fast_cfg()
        J_x = np.pi * 0.25
        mu_from_J, _, _ = resolve_advance_velocity(rotor, cfg, J_x=J_x, alpha_deg=0.0)
        self.assertAlmostEqual(mu_from_J, 0.25, places=6)


class TestAggregateResultsPropellerConvention(unittest.TestCase):
    def test_propeller_coefficients_are_finite_and_consistently_scaled(self):
        rotor = _small_rotor()
        airfoil = AnalyticalAirfoil(stall_model="clip")
        cfg = _fast_cfg()
        maps = solve_bemt(rotor, airfoil, cfg, mu_x=0.0, Vz=0.0)
        summary = aggregate_results(rotor, cfg, maps)
        # exact identity (independent of the physics being solved): CT_prop = CT * pi^3/4
        self.assertAlmostEqual(summary["CT_prop"], summary["CT"] * np.pi ** 3 / 4, places=6)
        self.assertAlmostEqual(summary["CQ_prop"], summary["CQ"] * np.pi ** 3 / 8, places=6)


class TestSolveBemtFlightWrapper(unittest.TestCase):
    def test_wrapper_attaches_flight_meta(self):
        rotor = _small_rotor()
        airfoil = AnalyticalAirfoil(stall_model="clip")
        cfg = _fast_cfg()
        maps = solve_bemt_flight(rotor, airfoil, cfg, mu_x=0.1, alpha_deg=0.0)
        for key in ("mu_x", "J_x", "alpha_rotor_deg"):
            self.assertIn(key, maps)


class TestTableAndViternaAirfoils(unittest.TestCase):
    def test_table_airfoil_runs_in_solver(self):
        rotor = _small_rotor()
        alpha = np.linspace(-20, 20, 41)
        cl = 2 * np.pi * np.deg2rad(alpha) * 0.9  # simplified linear
        cd = 0.02 + 0.01 * (alpha / 20) ** 2
        airfoil = TableAirfoil(alpha.tolist(), cl.tolist(), cd.tolist())
        cfg = _fast_cfg()
        maps = solve_bemt(rotor, airfoil, cfg, mu_x=0.0, Vz=0.0)
        self.assertTrue(np.all(np.isfinite(maps["Fn"])))

    def test_viterna_extended_covers_reverse_flow(self):
        base = AnalyticalAirfoil(stall_model="clip")
        extended = ViternaExtendedAirfoil(base, alpha_stall_pos_deg=15.0, alpha_stall_neg_deg=-6.0)
        alpha = np.deg2rad(np.array([-170.0, -90.0, 0.0, 90.0, 170.0]))
        cl, cd = extended.cl_cd(alpha)
        self.assertTrue(np.all(np.isfinite(cl)))
        self.assertTrue(np.all(np.isfinite(cd)))
        self.assertTrue(np.all(cd > 0))

    def test_reverse_flow_viterna_full_range_runs(self):
        rotor = _small_rotor()
        base = AnalyticalAirfoil(stall_model="clip")
        airfoil = ViternaExtendedAirfoil(base, alpha_stall_pos_deg=15.0, alpha_stall_neg_deg=-6.0)
        cfg = _fast_cfg(reverse_flow_model="viterna_full_range")
        # mu_x high enough to generate reverse flow near the root
        maps = solve_bemt(rotor, airfoil, cfg, mu_x=0.6, Vz=0.0)
        self.assertTrue(np.all(np.isfinite(maps["Fn"])))

    def test_viterna_extended_multi_section_uses_own_anchor_per_section(self):
        """Regression: ViternaExtendedAirfoil over a MultiSectionTableAirfoil
        must anchor EACH section on its OWN Cl_stall/Cd_stall (must not
        raise ValueError for missing r_norm, nor use the Cl_stall of a
        single section for all of them)."""
        sections = {
            0.3: ([-10, -5, 0, 5, 10, 15], [-0.5, -0.3, 0.2, 0.7, 1.1, 1.3],
                  [0.03, 0.02, 0.015, 0.02, 0.03, 0.05]),
            0.9: ([-10, -5, 0, 5, 10, 15], [-0.4, -0.2, 0.3, 0.8, 1.2, 1.8],
                  [0.028, 0.018, 0.014, 0.019, 0.028, 0.09]),
        }
        base = MultiSectionTableAirfoil(sections)
        extended = ViternaExtendedAirfoil(base, alpha_stall_pos_deg=15.0, alpha_stall_neg_deg=-10.0)

        alpha = np.deg2rad(np.array([20.0]))
        cl_inner, cd_inner = extended.cl_cd(alpha, r_norm=np.array([0.3]))
        cl_outer, cd_outer = extended.cl_cd(alpha, r_norm=np.array([0.9]))
        # the two sections stall at quite different Cl/Cd (1.3/0.05 vs
        # 1.8/0.09) -- the post-stall extrapolation must reflect this, not
        # give the same result (which would happen if only a single global
        # anchor were used for both sections).
        self.assertFalse(np.isclose(cl_inner[0], cl_outer[0]))
        self.assertFalse(np.isclose(cd_inner[0], cd_outer[0]))
        self.assertTrue(np.isfinite(cl_inner[0]) and np.isfinite(cd_inner[0]))

        # interpolation in r_norm between neighboring sections still works
        cl_mid, cd_mid = extended.cl_cd(alpha, r_norm=np.array([0.6]))
        self.assertTrue(np.isfinite(cl_mid[0]) and np.isfinite(cd_mid[0]))

        # without r_norm, must raise a clear error (same as MultiSectionTableAirfoil)
        with self.assertRaises(ValueError):
            extended.cl_cd(alpha)

    def _synthetic_polar_with_real_poststall_data(self):
        """Synthetic table with stall at 14 deg but with REAL measured data
        up to 25 deg (post-stall already present in the table) -- used to
        test that the Viterna extrapolation only kicks in beyond 25 deg,
        not at 14."""
        alpha_deg = np.arange(-20, 26, 1.0)
        alpha_rad = np.deg2rad(alpha_deg)
        cl_alpha, alpha0 = 2 * np.pi, np.deg2rad(-2.0)
        cl_lin = cl_alpha * (alpha_rad - alpha0)
        i_stall = np.argmin(np.abs(alpha_deg - 14))
        cl = np.where(alpha_deg <= 14, cl_lin, cl_lin[i_stall] * (1 - 0.03 * (alpha_deg - 14)))
        cd = 0.01 + 0.02 * cl ** 2 + np.where(alpha_deg > 14, 0.01 * (alpha_deg - 14), 0.0)
        return alpha_deg, cl, cd

    def test_auto_detect_anchors_at_clmax_but_preserves_real_poststall_table_data(self):
        """User finding #1: CLmax must be detected automatically
        (without depending on alpha_stall_pos_deg/neg_deg), and real
        table data beyond the CLmax (here, up to 25 deg) must NOT be
        overwritten by the Viterna extrapolation -- only what comes after
        25 deg is Viterna."""
        alpha_deg, cl, cd = self._synthetic_polar_with_real_poststall_data()
        table = TableAirfoil(alpha_deg, cl, cd)
        extended = ViternaExtendedAirfoil(table, alpha_stall_pos_deg=None,
                                           alpha_stall_neg_deg=None, blend_width_deg=6.0)

        self.assertAlmostEqual(np.degrees(extended.alpha_s_pos), 14.0, places=6)
        self.assertAlmostEqual(np.degrees(extended.alpha_edge_pos), 25.0, places=6)

        test_deg = np.array([-20.0, 0.0, 10.0, 14.0, 20.0, 25.0])
        cl_out, _ = extended.cl_cd(np.deg2rad(test_deg))
        cl_ref = np.interp(test_deg, alpha_deg, cl)
        np.testing.assert_allclose(cl_out, cl_ref, atol=1e-9)

    def test_auto_detect_negative_side_and_fallback_to_table_edge(self):
        """Table without Cl reversal on the negative side (Cl still
        decreasing monotonically all the way to the edge) -- the detected
        'stall' must fall on the last tabulated point on that side itself,
        without raising an error or creating a discontinuity."""
        alpha_deg, cl, cd = self._synthetic_polar_with_real_poststall_data()
        table = TableAirfoil(alpha_deg, cl, cd)
        extended = ViternaExtendedAirfoil(table, alpha_stall_pos_deg=None,
                                           alpha_stall_neg_deg=None, blend_width_deg=6.0)
        self.assertAlmostEqual(np.degrees(extended.alpha_s_neg), -20.0, places=6)
        self.assertAlmostEqual(np.degrees(extended.alpha_edge_neg), -20.0, places=6)

    def test_blend_removes_slope_discontinuity_at_stall(self):
        """User finding #2: the abrupt switch at alpha_stall (blend_width=0)
        creates a slope jump (the 'kink'); with blend_width>0 the slope
        jump right at the stall must drop to ~0."""
        base = AnalyticalAirfoil(stall_model="linear")
        eps_rad = np.deg2rad(0.01)
        a0 = np.deg2rad(15.0)

        hard = ViternaExtendedAirfoil(base, alpha_stall_pos_deg=15.0,
                                       alpha_stall_neg_deg=-6.0, blend_width_deg=0.0)
        cl_m, _ = hard.cl_cd(np.array([a0 - eps_rad]))
        cl_0, _ = hard.cl_cd(np.array([a0]))
        cl_p, _ = hard.cl_cd(np.array([a0 + eps_rad]))
        jump_hard = (cl_p[0] - cl_0[0]) / eps_rad - (cl_0[0] - cl_m[0]) / eps_rad

        smooth = ViternaExtendedAirfoil(base, alpha_stall_pos_deg=15.0,
                                         alpha_stall_neg_deg=-6.0, blend_width_deg=6.0)
        cl_m, _ = smooth.cl_cd(np.array([a0 - eps_rad]))
        cl_0, _ = smooth.cl_cd(np.array([a0]))
        cl_p, _ = smooth.cl_cd(np.array([a0 + eps_rad]))
        jump_smooth = (cl_p[0] - cl_0[0]) / eps_rad - (cl_0[0] - cl_m[0]) / eps_rad

        self.assertGreater(abs(jump_hard), 1.0)
        # C1-continuous (slope matches exactly) is not the same as
        # C2-continuous (curvature may differ slightly) -- that's why the
        # residual blend jump scales with eps (~O(eps)) instead of being
        # exactly zero, unlike the "hard" case which stays O(1)
        # regardless of eps. What matters is the difference in order of
        # magnitude between the two -- not still a real slope step.
        self.assertLess(abs(jump_smooth), 0.05)
        self.assertLess(abs(jump_smooth), abs(jump_hard) / 50.0)

    def test_blend_peak_lands_at_defined_stall_angle_not_beyond(self):
        """Bug reported by the user: with the "forward" blend (old),
        the effective alpha_stall and CLmax came out larger AND AFTER the
        parametrized value (the base model without a clamp keeps rising
        well beyond the anchor before being pulled toward Viterna --
        overshoot of ~5% and a peak ~2-3° after the defined angle). With
        the "backward" blend (current, C1-continuous Hermite), the peak
        must land BEFORE (never after) alpha_stall_pos_deg, with a small,
        bounded overshoot (on the order of 1-2% for blend_width_deg=4°,
        inherent to any C1 smoothing with slopes of opposite sign -- see
        the `ViternaExtendedAirfoil` docstring)."""
        base = AnalyticalAirfoil(stall_model="linear")
        alpha_stall_deg = 15.0
        smooth = ViternaExtendedAirfoil(base, alpha_stall_pos_deg=alpha_stall_deg,
                                         alpha_stall_neg_deg=-6.0, blend_width_deg=4.0)
        fine_deg = np.linspace(0.0, 40.0, 20001)
        cl_fine, _ = smooth.cl_cd(np.deg2rad(fine_deg))
        peak_deg = fine_deg[np.argmax(cl_fine)]
        cl_peak = np.max(cl_fine)
        cl_at_stall_base, _ = base.cl_cd(np.array([np.deg2rad(alpha_stall_deg)]))
        cl_stall = float(cl_at_stall_base[0])

        # never after the defined angle (the reported bug), and at most
        # `blend_width_deg` before it (the whole blend window)
        self.assertLessEqual(peak_deg, alpha_stall_deg + 1e-6)
        self.assertGreaterEqual(peak_deg, alpha_stall_deg - 4.0)
        # small, bounded overshoot (not the ~5% of the original bug)
        self.assertLess((cl_peak - cl_stall) / cl_stall, 0.03)

    def test_multisection_autodetects_stall_per_section(self):
        """Each radial section of a MultiSectionTableAirfoil must detect
        its OWN CLmax/stall angle from its own table, in automatic
        mode (without alpha_stall_pos_deg/neg_deg)."""
        sections = {
            0.3: ([-10, -5, 0, 5, 10, 15], [-0.5, -0.3, 0.2, 0.7, 1.1, 1.3],
                  [0.03, 0.02, 0.015, 0.02, 0.03, 0.05]),
            0.9: ([-10, -5, 0, 5, 10, 15], [-0.4, -0.2, 0.3, 0.9, 1.4, 1.2],
                  [0.028, 0.018, 0.014, 0.019, 0.028, 0.09]),
        }
        base = MultiSectionTableAirfoil(sections)
        extended = ViternaExtendedAirfoil(base, alpha_stall_pos_deg=None, alpha_stall_neg_deg=None)
        # section 0.3: Cl still rising at 15 deg (CLmax = edge, 15 deg)
        # section 0.9: Cl has already dropped at 15 deg (CLmax = 10 deg)
        self.assertAlmostEqual(np.degrees(extended._section_children[0].alpha_s_pos), 15.0, places=6)
        self.assertAlmostEqual(np.degrees(extended._section_children[1].alpha_s_pos), 10.0, places=6)


class TestBEMTConfigDefaults(unittest.TestCase):
    """Locks in the defaults requested in the 2026-07 update: dense mesh
    (matching the zBEMT MATLAB v30 reference mesh), local Coleman,
    Prandtl on, compressibility on, viterna_full_range, and
    reverse-flow masking in plots on by default."""

    def test_mesh_matches_matlab_reference(self):
        cfg = BEMTConfig()
        self.assertEqual(cfg.Ne, 120)
        self.assertEqual(cfg.Npsi, 180)

    def test_inflow_default_is_coleman_local(self):
        self.assertEqual(BEMTConfig().inflow_field_model, "coleman_local")

    def test_prandtl_and_compressibility_default_on(self):
        cfg = BEMTConfig()
        self.assertEqual(cfg.prandtl_loss_mode, "both")
        self.assertTrue(cfg.use_compressibility)

    def test_reverse_flow_model_default_is_viterna_full_range(self):
        self.assertEqual(BEMTConfig().reverse_flow_model, "viterna_full_range")

    def test_mask_reverse_flow_plots_default_true(self):
        self.assertTrue(BEMTConfig().mask_reverse_flow_plots)


class TestCompressibilityCeiling(unittest.TestCase):
    """Prandtl-Glauert is limited by a documented Mach ceiling.

    The old guard (`beta > 1e-3`) only prevented an EXACT division by
    zero: it corresponds to M > 0.9999995, and at M = 0.99998 it
    multiplied Cl by 159 -- discontinuously on top of that, because
    above the cutoff the correction was skipped entirely and the factor
    dropped to 1. A rotor pushed into the transonic range by mistake
    (the old Run Case tab default did exactly that) returned Cl on the
    order of hundreds, and the corresponding disk map turned into a
    single-color rectangle.
    """

    def _resolve(self, mach: float, floor: float | None = None):
        """Solve the same rotor with and without compressibility, at the
        given Mach.

        `a_sound` is what fixes the Mach without touching the kinematics:
        lowering it raises M = W/a without changing W, Reynolds, or the
        angle of attack, so the difference between the two maps isolates
        the correction.
        """
        from zbemt import bemt

        rotor = _small_rotor()
        airfoil = AnalyticalAirfoil(stall_model="clip")
        Ne, Npsi = 6, 8
        cfg_off = _fast_cfg(Ne=Ne, Npsi=Npsi, use_compressibility=False)
        W = float(np.nanmax(solve_bemt(rotor, airfoil, cfg_off,
                                       mu_x=0.0, Vz=0.0)["W"]))
        cfg_on = _fast_cfg(Ne=Ne, Npsi=Npsi, use_compressibility=True)
        cfg_on.a_sound = cfg_off.a_sound = W / mach

        original = bemt.BETA_MINIMO_DE_PRANDTL_GLAUERT
        if floor is not None:
            bemt.BETA_MINIMO_DE_PRANDTL_GLAUERT = floor
        try:
            corrected = solve_bemt(rotor, airfoil, cfg_on, mu_x=0.0, Vz=0.0)
        finally:
            bemt.BETA_MINIMO_DE_PRANDTL_GLAUERT = original
        uncorrected = solve_bemt(rotor, airfoil, cfg_off, mu_x=0.0, Vz=0.0)
        return corrected, uncorrected

    #: Maximum Cl amplification that is still defensible as a
    #: linearized correction. Deliberately NOT derived from
    #: `BETA_MINIMO_DE_PRANDTL_GLAUERT`: a limit computed from the
    #: very constant under test would pass for any value of it --
    #: including for the old guard, which amplified 191x.
    MAX_DEFENSIBLE_AMPLIFICATION = 3.0

    def test_transonic_mesh_does_not_amplify_cl_without_limit(self):
        """With the old guard (`beta > 1e-3`) this same case returned
        Cl = 164 -- 191x the max of the uncorrected polar, which is 0.86."""
        corrected, uncorrected = self._resolve(0.99998)
        self.assertGreater(np.nanmax(corrected["Mach"]), 0.99,
                           "the case must actually reach the transonic regime")
        ratio = (float(np.nanmax(np.abs(corrected["Cl"])))
                 / float(np.nanmax(np.abs(uncorrected["Cl"]))))
        self.assertLessEqual(
            ratio, self.MAX_DEFENSIBLE_AMPLIFICATION,
            f"Cl amplified {ratio:.1f}x by a linearized correction -- "
            "numerical artifact presented as a result")

    def test_the_mach_ceiling_stays_in_the_range_where_the_model_still_says_something(self):
        """Prandtl-Glauert is honest up to M ~ 0.7 and empty above M ~ 0.9.
        A ceiling outside that range either cuts nothing (the original
        defect) or cuts a valid result."""
        self.assertTrue(0.85 <= MACH_MAXIMO_DE_PRANDTL_GLAUERT <= 0.9,
                        f"ceiling at M={MACH_MAXIMO_DE_PRANDTL_GLAUERT}")
        self.assertAlmostEqual(
            BETA_MINIMO_DE_PRANDTL_GLAUERT,
            float(np.sqrt(1.0 - MACH_MAXIMO_DE_PRANDTL_GLAUERT ** 2)),
            places=12, msg="the beta floor must be the one from the Mach ceiling")

    def test_below_the_ceiling_nothing_changes(self):
        """The ceiling only cuts the range that was already physically empty.

        Below M = 0.9 the expression must be identical to the classic one,
        with no floor at all -- that is what guarantees no already-validated
        result moves. The thirteen example projects reach at most M = 0.75.
        """
        with_ceiling, _ = self._resolve(0.75)
        without_floor, _ = self._resolve(0.75, floor=0.0)
        for key in ("Cl", "Cd", "Fn", "Ft", "lambda_i"):
            with self.subTest(key=key):
                np.testing.assert_allclose(with_ceiling[key], without_floor[key],
                                           rtol=0, atol=0)


class TestHeterogeneousMultiSectionAirfoil(unittest.TestCase):
    """Phase D (docs/plano.md GUI v3, Section 4): heterogeneous
    multi-section airfoil -- interpolates the ALREADY-EVALUATED Cl/Cd of
    N independently-built airfoil objects (unlike MultiSectionTableAirfoil,
    which interpolates data from a single table)."""

    def test_requires_at_least_two_sections(self):
        af = AnalyticalAirfoil()
        with self.assertRaises(ValueError):
            HeterogeneousMultiSectionAirfoil([(0.5, af)])

    def test_requires_r_norm_to_evaluate(self):
        root = AnalyticalAirfoil(cd0=0.02)
        tip = AnalyticalAirfoil(cd0=0.008)
        composite = HeterogeneousMultiSectionAirfoil([(0.15, root), (1.0, tip)])
        with self.assertRaises(ValueError):
            composite.cl_cd(np.array([0.1]))

    def test_matches_endpoint_sections_exactly(self):
        root = AnalyticalAirfoil(cd0=0.02, cl_alpha=5.0)
        tip = AnalyticalAirfoil(cd0=0.008, cl_alpha=6.0)
        composite = HeterogeneousMultiSectionAirfoil([(0.15, root), (1.0, tip)])
        alpha = np.array([0.05, 0.1, 0.15])

        cl_root_ref, cd_root_ref = root.cl_cd(alpha)
        cl_root, cd_root = composite.cl_cd(alpha, r_norm=np.full_like(alpha, 0.15))
        np.testing.assert_allclose(cl_root, cl_root_ref)
        np.testing.assert_allclose(cd_root, cd_root_ref)

        cl_tip_ref, cd_tip_ref = tip.cl_cd(alpha)
        cl_tip, cd_tip = composite.cl_cd(alpha, r_norm=np.full_like(alpha, 1.0))
        np.testing.assert_allclose(cl_tip, cl_tip_ref)
        np.testing.assert_allclose(cd_tip, cd_tip_ref)

    def test_interpolates_linearly_between_two_sections(self):
        root = AnalyticalAirfoil(cd0=0.02)
        tip = AnalyticalAirfoil(cd0=0.008)
        composite = HeterogeneousMultiSectionAirfoil([(0.0, root), (1.0, tip)])
        alpha = np.array([0.0])
        _, cd_mid = composite.cl_cd(alpha, r_norm=np.array([0.5]))
        # alpha=0 -> cl=0 for both, cd = pure cd0; the midpoint r=0.5 must
        # fall exactly on the average of the two cd0 (linear interpolation).
        self.assertAlmostEqual(float(cd_mid[0]), 0.5 * (0.02 + 0.008), places=8)

    def test_clamps_outside_defined_range(self):
        root = AnalyticalAirfoil(cd0=0.02)
        tip = AnalyticalAirfoil(cd0=0.008)
        composite = HeterogeneousMultiSectionAirfoil([(0.15, root), (1.0, tip)])
        alpha = np.array([0.0])
        _, cd_below = composite.cl_cd(alpha, r_norm=np.array([0.0]))
        _, cd_above = composite.cl_cd(alpha, r_norm=np.array([1.5]))
        self.assertAlmostEqual(float(cd_below[0]), 0.02, places=8)
        self.assertAlmostEqual(float(cd_above[0]), 0.008, places=8)

    def test_three_sections_can_mix_analytical_and_table(self):
        root = AnalyticalAirfoil(cd0=0.02)
        mid_table = TableAirfoil(alpha_deg=[-10, 0, 10], cl=[-0.5, 0.0, 0.5], cd=[0.03, 0.015, 0.03])
        tip = AnalyticalAirfoil(cd0=0.008)
        composite = HeterogeneousMultiSectionAirfoil([(1.0, tip), (0.15, root), (0.6, mid_table)])
        self.assertEqual(list(composite.r_norms), [0.15, 0.6, 1.0])
        alpha = np.deg2rad(np.array([0.0, 0.0, 0.0]))
        cl, cd = composite.cl_cd(alpha, r_norm=np.array([0.15, 0.6, 1.0]))
        self.assertTrue(np.all(np.isfinite(cl)))
        self.assertTrue(np.all(np.isfinite(cd)))

    def test_cl_alpha_alpha0_field_uses_each_sections_own_values(self):
        """Before, `MultiSectionTableAirfoil`/`HeterogeneousMultiSectionAirfoil`
        only exposed a single representative (Cl_alpha, alpha0) pair
        (median section) for the whole blade -- `cl_alpha_alpha0_field`
        fixes this, interpolating each section's OWN value."""
        root = AnalyticalAirfoil(cl_alpha=4.0, alpha0_deg=-2.0)
        tip = AnalyticalAirfoil(cl_alpha=7.0, alpha0_deg=1.0)
        composite = HeterogeneousMultiSectionAirfoil([(0.0, root), (1.0, tip)])

        cl_alpha_root, alpha0_root = composite.cl_alpha_alpha0_field(np.array([0.0]))
        cl_alpha_tip, alpha0_tip = composite.cl_alpha_alpha0_field(np.array([1.0]))
        cl_alpha_mid, _ = composite.cl_alpha_alpha0_field(np.array([0.5]))

        self.assertAlmostEqual(float(cl_alpha_root[0]), 4.0, places=8)
        self.assertAlmostEqual(float(cl_alpha_tip[0]), 7.0, places=8)
        self.assertAlmostEqual(float(alpha0_root[0]), np.deg2rad(-2.0), places=8)
        self.assertAlmostEqual(float(alpha0_tip[0]), np.deg2rad(1.0), places=8)
        # midpoint linearly interpolated between the two endpoints.
        self.assertAlmostEqual(float(cl_alpha_mid[0]), 5.5, places=8)

    def test_dynamic_stall_applies_only_to_sections_that_opt_in(self):
        """Reproduces the `airfoils.to_blade_airfoil` -> `solve_bemt` path
        with one section requesting dynamic stall and another not: the
        section WITHOUT dynamic stall should stay essentially on the
        static polar, the section WITH it should diverge from it
        noticeably."""
        from zbemt import airfoils as airfoils_mod
        from zbemt.models import AirfoilDef

        root = AirfoilDef(name="raiz", r_norm=0.15, source="analytical",
                           cl_alpha=2 * np.pi, alpha0_deg=-2.0, stall_model="clip",
                           alpha_stall_pos_deg=12.0, alpha_stall_neg_deg=-8.0,
                           use_dynamic_stall=True, dynamic_stall_A=8.0)
        tip = AirfoilDef(name="ponta", r_norm=1.0, source="analytical",
                          cl_alpha=2 * np.pi, alpha0_deg=-2.0, stall_model="clip",
                          alpha_stall_pos_deg=12.0, alpha_stall_neg_deg=-8.0,
                          use_dynamic_stall=False)
        composite = airfoils_mod.to_blade_airfoil([root, tip])
        self.assertTrue(composite.dynamic_stall_params["use_dynamic_stall"])

        rotor = _small_rotor()
        cfg = _fast_cfg(use_dynamic_stall=True)
        maps = solve_bemt(rotor, composite, cfg, mu_x=0.3, Vz=0.0)

        self.assertIn("Cl_static", maps)
        diff_root = np.max(np.abs(maps["Cl"][0] - maps["Cl_static"][0]))
        diff_tip = np.max(np.abs(maps["Cl"][-1] - maps["Cl_static"][-1]))
        self.assertGreater(diff_root, 1e-3, "section with dynamic stall should diverge from the static polar")
        self.assertLess(diff_tip, 1e-3, "section without dynamic stall should stay essentially on the static polar")
        self.assertGreater(diff_root, 100 * diff_tip,
                            "section with dynamic stall must diverge MUCH more than the section without it")

    def test_end_to_end_solve_bemt_runs_with_composite_airfoil(self):
        rotor = _small_rotor()
        root = AnalyticalAirfoil(cd0=0.02)
        tip = AnalyticalAirfoil(cd0=0.008)
        composite = HeterogeneousMultiSectionAirfoil([(0.15, root), (1.0, tip)])
        cfg = _fast_cfg()
        maps = solve_bemt(rotor, composite, cfg, mu_x=0.0, Vz=0.0)
        summary = aggregate_results(rotor, cfg, maps)
        self.assertTrue(np.isfinite(summary["CT"]))
        self.assertGreater(summary["CT"], 0.0)


class TestPrandtlLossFactor(unittest.TestCase):
    """The loss factor must match the closed form, including the 1/x.

    The exponent measures the distance to the edge in units of the spacing
    between helical vortex sheets, s = 2*pi*x*sin(phi)/Nb. That spacing
    grows with radius, so x belongs in the denominator; dropping it applies
    a spurious loss inboard, worth a few per cent of thrust.
    """

    @staticmethod
    def _esperado(x, xr, Nb, phi):
        s = max(abs(math.sin(phi)), 1e-6) * max(x, 1e-6)
        F = 1.0
        for f in (-(Nb / 2.0) * (1.0 - x) / s, -(Nb / 2.0) * (x - xr) / s):
            F *= min(max((2.0 / math.pi) * math.acos(min(max(math.exp(f), -1.0), 1.0)),
                         0.01), 1.0)
        return F

    def _estado(self, x, rotor, cfg):
        from zbemt import bemt
        um = np.array([[x]])
        return bemt.element_state(
            np.array([[0.05]]), um, np.array([[0.0]]),
            np.array([[x * rotor.R]]), np.array([[0.08 * rotor.R]]),
            np.array([[math.radians(8.0)]]), 0.0, 0.0,
            rotor.Nb, rotor.Omega, rotor.Omega * rotor.R,
            AnalyticalAirfoil(), cfg,
            rotor.r_root_norm_geom, rotor.r_tip_norm_geom)

    def test_fator_bate_com_a_forma_fechada(self):
        rotor = _small_rotor(n_blades=4)
        cfg = _fast_cfg(prandtl_loss_mode="both")
        for x in (0.25, 0.5, 0.75, 0.9, 0.97):
            with self.subTest(r_norm=x):
                estado = self._estado(x, rotor, cfg)
                phi = float(np.asarray(estado["phi"]).ravel()[0])
                obtido = float(np.asarray(estado["F"]).ravel()[0])
                esperado = self._esperado(x, rotor.r_root_norm_geom, rotor.Nb, phi)
                self.assertAlmostEqual(obtido, esperado, places=6)

    def test_perda_desaparece_longe_das_bordas(self):
        """Well inside the blade the factor is essentially one."""
        rotor = _small_rotor(n_blades=4)
        cfg = _fast_cfg(prandtl_loss_mode="both")
        estado = self._estado(0.5, rotor, cfg)
        self.assertGreater(float(np.asarray(estado["F"]).ravel()[0]), 0.99)


from zbemt import bemt


class TestOneSidedTableStall(unittest.TestCase):
    """A polar that only converged on ONE side of alpha=0 used to kill
    the whole Run Case with "Table has no points on alpha side 'pos'".
    The stall anchor on the empty side is now MIRRORED from the side
    that exists (stated assumption, warned), and the case runs."""

    def _pos_only_table(self):
        # Strictly positive alphas: alpha=0 counts as the 'neg' side
        # (mask alpha<=0), so the fixture must exclude it.
        alpha = np.linspace(0.5, 12.0, 12)
        cl = 0.11 * alpha * (1.0 - (alpha / 14.0) ** 2)   # peak ~1.2 near 8-9 deg
        cd = 0.01 + 0.002 * alpha ** 2
        return bemt.TableAirfoil(alpha, cl, cd)

    def test_viterna_extension_builds_from_pos_only_table(self):
        base = self._pos_only_table()
        with self.assertWarns(UserWarning):
            ext = bemt.ViternaExtendedAirfoil(base)
        self.assertGreater(ext.alpha_s_pos, 0.0)
        # Mirrored anchor, clamped to stay at/beyond the data edge (0 deg):
        self.assertLessEqual(ext.alpha_s_neg, 0.0)
        cl, cd = ext.cl_cd(np.deg2rad(np.array([-8.0, 0.0, 8.0])))
        self.assertTrue(np.all(np.isfinite(cl)) and np.all(np.isfinite(cd)))

    def test_neg_only_table_mirrors_pos_anchor(self):
        alpha = np.linspace(-12.0, -0.5, 12)
        cl = -0.11 * (-alpha) * (1.0 - ((-alpha) / 14.0) ** 2)
        cd = 0.01 + 0.002 * (-alpha) ** 2
        base = bemt.TableAirfoil(alpha, cl, cd)
        with self.assertWarns(UserWarning):
            ext = bemt.ViternaExtendedAirfoil(base)
        self.assertGreaterEqual(ext.alpha_s_pos, 0.0)
        self.assertLess(ext.alpha_s_neg, 0.0)

    def test_empty_table_still_raises_with_actionable_text(self):
        for side in ("pos", "neg"):
            with self.subTest(side=side):
                with self.assertRaises(ValueError) as ctx:
                    bemt._detect_stall_extremum(np.array([]), np.array([]), side)
                self.assertIn("no alpha points", str(ctx.exception))

    def test_warning_tells_how_to_get_real_data(self):
        base = self._pos_only_table()
        with self.assertWarnsRegex(UserWarning, r"(?s)MIRRORED.*wider"):
            bemt.ViternaExtendedAirfoil(base)

    def test_mirror_anchor_is_the_sign_flipped_extremum_of_the_existing_side(self):
        # The anchor of the empty side is the extremum of the existing
        # side, with the sign flipped. For strictly one-sided data the
        # clamp compares against the edge of the EXISTING side, so it
        # never binds: the observable anchor is the pure sign flip.
        alpha = np.linspace(0.5, 12.0, 12)
        cl = 0.11 * alpha * (1.0 - (alpha / 14.0) ** 2)
        cd = 0.01 + 0.002 * alpha ** 2
        table = bemt.TableAirfoil(alpha, cl, cd)
        j = int(np.argmax(table.cl_tab))
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            idx, alpha_s, cl_s = bemt._detect_stall_extremum(
                table.alpha, table.cl_tab, "neg")
        self.assertEqual(idx, int(np.argmin(table.alpha)))
        self.assertAlmostEqual(alpha_s, -float(table.alpha[j]), places=12)
        self.assertAlmostEqual(cl_s, -float(table.cl_tab[j]), places=12)

    def test_mirrored_anchor_reaches_the_viterna_wrapper(self):
        base = self._pos_only_table()
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            ext = bemt.ViternaExtendedAirfoil(base)
        peak_alpha = float(base.alpha[int(np.argmax(base.cl_tab))])
        self.assertAlmostEqual(ext.alpha_s_neg, -peak_alpha, places=12)
        self.assertGreater(ext.alpha_s_pos, 0.0)
        self.assertLess(ext.alpha_s_neg, 0.0)


if __name__ == "__main__":
    unittest.main()
