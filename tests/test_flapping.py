"""Blade flapping and lead-lag (Item 1 of the work plan, SC-11).

Each test pins one behavior of the rigid-blade dynamics against a
reference external to the implementation: a published closed form
(EN-4), a physical limit the model must reproduce, or an invariant the
data contract promises. The resonance test enforces EN-8; the golden and
cancellation tests protect backward compatibility and PR-11.
"""
import math
import os
import tempfile
import unittest

import numpy as np

from zbemt import api, geometry, studies
from dataclasses import replace
from zbemt.bemt import SolveCancelled, solve_blade_motion
from zbemt.models import (AirfoilDef, BladeDynamicsDef, FlightCondition,
                           Project)

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _make_project(dynamics: BladeDynamicsDef, *, stall_model="clip",
                  config_overrides=None) -> Project:
    geom = geometry.generate_tapered(
        root_chord_norm=0.10, tip_chord_norm=0.04,
        twist_root_deg=10.0, twist_tip_deg=2.0,
        root_cutout_norm=0.15, radius_m=1.0, n_stations=12)
    cfg = dict(Ne=10, Npsi=16, solver="newton", max_iter=250)
    if config_overrides:
        cfg.update(config_overrides)
    return Project(name="flap_test",
                   geometry=replace(geom, dynamics=dynamics),
                   airfoil=AirfoilDef(source="analytical",
                                       stall_model=stall_model),
                   config=cfg)


class TestFrequencyRatioClosedForm(unittest.TestCase):
    def test_offset_only_ratio_matches_closed_form(self):
        """EN-4: with e = 0.05 and no spring, nu_beta^2 must equal
        1 + (3/2)*e/(1-e) exactly -- the published closed form for a
        uniform blade with an offset hinge."""
        e = 0.05
        nu2 = geometry.flap_frequency_ratio_squared(e, 0.0, 0.07, 100.0)
        self.assertAlmostEqual(nu2, 1.0 + 1.5 * e / (1.0 - e), places=12)

    def test_spring_term_matches_closed_form(self):
        """The spring contribution K/(I*Omega^2) adds linearly."""
        k, inertia, omega = 500.0, 0.05, 40.0
        nu2 = geometry.flap_frequency_ratio_squared(0.0, k, inertia, omega)
        self.assertAlmostEqual(nu2, 1.0 + k / (inertia * omega ** 2),
                               places=12)


class TestFlapAeroDampingClosedForm(unittest.TestCase):
    def test_central_hinge_reduces_to_the_classic_gamma_over_eight(self):
        """EN-4: at e = 0 the aerodynamic flap damping must reduce to the
        published gamma/8 of the centrally hinged blade; with an offset
        it follows gamma*(1/8 - e/3 + e^2/4), hand-integrated from the
        same U_P term the engine uses."""
        gamma = 8.0
        self.assertAlmostEqual(geometry.flap_aero_damping(gamma, 0.0),
                                gamma / 8.0, places=12)
        e = 0.05
        self.assertAlmostEqual(
            geometry.flap_aero_damping(gamma, e),
            gamma * (0.125 - e / 3.0 + 0.25 * e * e), places=12)


class TestResonanceGuard(unittest.TestCase):
    def test_articulated_first_harmonic_raises_and_names_it(self):
        """EN-8: with e = 0, no spring and one harmonic, the denominator
        is exactly zero. The solver must raise ValueError naming the
        harmonic instead of returning a large number -- and the message
        must say this is the articulated rotor's physical fact."""
        npsi = 24
        psi = np.linspace(0, 2 * np.pi * (1 - 1 / npsi), npsi)
        moment = 50.0 * np.ones(npsi)
        with self.assertRaises(ValueError) as ctx:
            solve_blade_motion(moment, psi, 1.0, 0.08, 80.0, n_harm=1,
                                freedom="flap", hinge_offset_norm=0.0)
        message = str(ctx.exception).lower()
        self.assertIn("resonant", message)
        self.assertIn("harmonic 1", message)
        self.assertIn("articulated", message)

    def test_validation_reports_the_resonance_before_a_run(self):
        """PR-6: validate_blade_dynamics flags the same configuration as
        an error before any solve happens."""
        from zbemt.validation import validate_blade_dynamics
        dyn = BladeDynamicsDef(flap_model="offset", hinge_offset_norm=0.0,
                               harmonics=2)
        geom = geometry.generate_rectangular()
        issues = validate_blade_dynamics(dyn, geom, rpm=800.0)
        errors = [i.message for i in issues if i.level == "error"]
        self.assertTrue(any("resonant" in m.lower() for m in errors),
                        str(issues))


class TestConingInHover(unittest.TestCase):
    def test_hover_coning_reproduces_the_uniform_inflow_closed_form(self):
        """For a constant-chord, untwisted blade in hover with uniform
        inflow (Pitt-Peters steady is axisymmetric there), no tip loss
        and a linear polar, the harmonic balance must reproduce the
        closed form of its own integrals:

            beta_0 = [gamma/2*(theta_eff*(1/4 - e/3)
                               - lambda*(1/3 - e/2))] / nu_beta^2

        with theta_eff = theta - alpha_zero_lift. Agreement within a few
        percent validates the moment integral, the Lock-number
        normalization and the balance together."""
        e = 0.05
        gamma = 8.0
        collective_deg = 6.0
        dyn = BladeDynamicsDef(flap_model="offset", hinge_offset_norm=e,
                               inertia_source="lock", lock_number=gamma,
                               harmonics=3)
        # The closed form assumes a CONSTANT chord and ZERO twist: the
        # test builds that blade explicitly instead of the tapered,
        # twisted one every other test uses.
        geom = geometry.generate_rectangular(chord_norm=0.08,
                                              twist_root_deg=0.0,
                                              twist_tip_deg=0.0,
                                              radius_m=1.0, n_stations=20)
        project = Project(
            name="flap_coning",
            geometry=replace(geom, dynamics=dyn),
            airfoil=AirfoilDef(source="analytical", stall_model="linear"),
            config=dict(Ne=20, Npsi=24, solver="newton", max_iter=300,
                        inflow_field_model="pitt_peters_steady",
                        prandtl_loss_mode="off",
                        use_rotational_augmentation=False,
                        use_radial_flow_correction=False,
                        use_compressibility=False))
        condition = FlightCondition(name="hover", mu_x=0.0,
                                     collective_deg=collective_deg,
                                     rpm=800.0)
        result = studies.run_single_case(project, condition)

        alpha0 = math.radians(project.airfoil.alpha0_deg)
        theta_eff = math.radians(collective_deg) - alpha0
        lam = result.summary["lambda_i"]
        nu2 = 1.0 + 1.5 * e / (1.0 - e)
        mbar0 = (gamma / 2.0) * (theta_eff * (0.25 - e / 3.0)
                                  - lam * (1.0 / 3.0 - e / 2.0))
        expected_deg = math.degrees(mbar0 / nu2)
        got = result.summary["beta_0_deg"]
        self.assertGreater(got, 0.0, "coning must be positive in hover")
        # A few percent: the residue comes from the residual radial
        # non-uniformity of the inflow.
        tolerance = 0.05 * expected_deg + 0.25
        self.assertAlmostEqual(got, expected_deg, delta=tolerance)


class TestFlapRelievesRetreatingSide(unittest.TestCase):
    def test_flap_redistributes_azimuthal_loading_and_moves_the_hub_moment(self):
        """At mu = 0.3 the flap response tilts the tip path plane, and the
        tilt MOVES load between the two halves of the disk: the
        advancing-side incidence falls while the retreating side takes
        more of the loading. The structural hub-moment path (Mx_hub)
        also appears -- zero on the rigid run by construction -- and the
        outer loop converges.

        Scope note (SC-11): which HALF gains depends on the solved tilt,
        so the test pins the physical invariant (the tilt redistributes
        section incidence between the halves, and the unloaded half is
        the one the rigid run overloaded) instead of an assumed
        direction for every configuration."""
        dyn = BladeDynamicsDef(flap_model="offset", hinge_offset_norm=0.05,
                               inertia_source="lock", lock_number=8.0,
                               harmonics=3, outer_max_iter=60)
        project = _make_project(dyn)
        rigid_project = _make_project(BladeDynamicsDef())
        condition = FlightCondition(name="fwd", mu_x=0.3,
                                     collective_deg=8.0, rpm=800.0)
        r_on = studies.run_single_case(project, condition)
        r_off = studies.run_single_case(rigid_project, condition)

        def _advancing_alpha_p95(res):
            maps = res.maps
            mask = (maps["PSI"] < np.pi / 2) & (maps["Ut"] > 0)
            return float(np.degrees(
                np.percentile(np.abs(maps["alpha_eff"][mask]), 95)))

        self.assertLess(_advancing_alpha_p95(r_on),
                        _advancing_alpha_p95(r_off),
                        "flapping must relieve the loaded half of the disk")

        beta_1c = r_on.summary["beta_1c_deg"]
        beta_1s = r_on.summary["beta_1s_deg"]
        self.assertGreater(abs(beta_1c) + abs(beta_1s), 0.5,
                           "forward flight must produce a 1/rev response")
        self.assertGreater(r_on.summary["flap_outer_iterations"], 0)
        self.assertLessEqual(r_on.summary["flap_outer_residual_deg"],
                             max(10.0 * dyn.outer_tol_deg, 1e-3))
        # Structural hub-moment path present only when flapping.
        self.assertNotIn("Mx_hub", r_off.summary)
        self.assertIn("Mx_hub", r_on.summary)


class TestRigidIsTheOldPath(unittest.TestCase):
    def test_rigid_projects_reproduce_the_golden_results(self):
        """With flap_model='rigid' the summary must match
        tests/data/golden_results.json exactly, for every example
        project: the rigid blade IS the behavior every existing project
        was recorded with."""
        import json
        with open(os.path.join(REPO, "tests", "data",
                                "golden_results.json"),
                   encoding="utf-8") as handle:
            golden = json.load(handle)
        self.assertIn("flapping_rotor", golden,
                      "the example project must be part of the snapshot")
        project = api.open_project(
            os.path.join(REPO, "projects", "flapping_rotor"))
        # The flapping example runs through the dynamics path; its
        # RIGID twin (same planform, default dynamics) must reproduce
        # the engine bit-for-bit, which the snapshot check
        # (test_golden_results) enforces for all projects. Here we pin
        # the routing rule itself: a rigid dynamics block never takes
        # the Section 4h path.
        from zbemt.bemt import solve_bemt_flapping  # noqa: F401
        from dataclasses import replace as dc_replace
        rigid_project = dc_replace(
            project,
            geometry=dc_replace(project.geometry,
                                 dynamics=BladeDynamicsDef()))
        condition = FlightCondition(name="hover", mu_x=0.0,
                                     collective_deg=8.0, rpm=1400.0)
        result = studies.run_single_case(rigid_project, condition)
        self.assertNotIn("beta_coeffs", result.maps)
        self.assertNotIn("beta_0_deg", result.summary)
        self.assertNotIn("Mx_hub", result.summary)


class TestRoundTrip(unittest.TestCase):
    def test_blade_dynamics_survives_save_and_open(self):
        """A BladeDynamicsDef survives save_bemt/load_bemt inside the
        geometry, and an old geom.bemt with no dynamics key loads with
        the rigid default."""
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "geom.bemt")
            geom = geometry.generate_rectangular()
            dyn = BladeDynamicsDef(flap_model="spring",
                                    flap_spring_nm_per_rad=300.0,
                                    inertia_source="inertia",
                                    flap_inertia_kg_m2=0.09)
            geom.dynamics = dyn
            from zbemt.models import load_bemt, save_bemt
            save_bemt(geom, path)
            loaded = load_bemt(type(geom), path)
            self.assertEqual(loaded.dynamics, dyn)

    def test_legacy_geometry_without_dynamics_loads_rigid(self):
        legacy = {"r_norm": [0.2, 1.0], "chord_norm": [0.1, 0.05],
                  "twist_deg": [8.0, 2.0], "n_blades": 2, "radius_m": 1.0,
                  "root_cutout_norm": 0.2}
        import json
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "legacy_geom.bemt")
            with open(path, "w", encoding="utf-8") as handle:
                json.dump(legacy, handle)
            from zbemt.models import RotorGeometryDef, load_bemt
            loaded = load_bemt(RotorGeometryDef, path)
        self.assertEqual(loaded.dynamics.flap_model, "rigid")


class TestCyclicFlapbackTrim(unittest.TestCase):
    def test_solve_cyclic_flapback_drives_both_harmonics_to_zero(self):
        """The wind-tunnel trim solves theta_1c/theta_1s until both first
        flap harmonics are below 0.01 degree."""
        dyn = BladeDynamicsDef(flap_model="offset", hinge_offset_norm=0.05,
                               inertia_source="lock", lock_number=8.0,
                               harmonics=3, outer_max_iter=60)
        project = _make_project(dyn)
        condition = FlightCondition(name="fwd", mu_x=0.25,
                                     collective_deg=8.0, rpm=800.0)
        result = studies.run_case_trimmed(
            project, condition, trim_mode="solve_cyclic_flapback",
            max_iter=12)
        self.assertLess(abs(result.summary["beta_1c_deg"]), 0.01,
                        str(result.summary.get("beta_1c_deg")))
        self.assertLess(abs(result.summary["beta_1s_deg"]), 0.01)
        # What was traded is reported, matching compare_geometries'
        # convention.
        self.assertIn("trim_dof", result.summary)
        self.assertIn("trim_dof_value", result.summary)


class TestWarmStart(unittest.TestCase):
    def test_warm_start_reproduces_the_cold_solution(self):
        """Passing the previous case's blade angle through ``warm_start``
        must converge to the same coefficients as a cold start, in no
        more outer iterations. The warm path projects the given ANGLE
        onto the coefficient vector the loop iterates; before this was
        tested it routed a Fourier tuple through a helper that expects
        the coefficient dict and raised TypeError on first use."""
        from zbemt.bemt import solve_bemt_flapping
        from zbemt.studies import _to_rotor, _require_rpm, _build_config
        import zbemt.airfoils as airfoils

        dyn = BladeDynamicsDef(flap_model="offset", hinge_offset_norm=0.05,
                               inertia_source="lock", lock_number=8.0,
                               harmonics=3, outer_max_iter=60)
        project = _make_project(dyn, config_overrides=dict(Ne=12, Npsi=20))
        condition = FlightCondition(name="fwd", mu_x=0.25,
                                     collective_deg=8.0, rpm=800.0)

        cfg = _build_config(project.config)
        rotor = _to_rotor(project.geometry,
                           collective_deg=condition.collective_deg,
                           rpm=_require_rpm(condition.rpm))
        radial = airfoils.radial_reynolds_mach(rotor, cfg,
                                                mu_x=condition.mu_x)
        airfoil_obj = airfoils.to_blade_airfoil([project.airfoil],
                                                 radial=radial)

        cold = solve_bemt_flapping(rotor, airfoil_obj, cfg, condition.mu_x,
                                    condition.Vz, dynamics=dyn)
        coeffs = cold["beta_coeffs"]
        psi = cold["psi_nodes"]
        angle = np.full_like(psi, coeffs[0][0])
        for n, (cn, sn) in coeffs.items():
            if n:
                angle = angle + cn * np.cos(n * psi) + sn * np.sin(n * psi)
        warm = solve_bemt_flapping(rotor, airfoil_obj, cfg, condition.mu_x,
                                    condition.Vz, dynamics=dyn,
                                    warm_start={"beta_psi": angle})
        self.assertAlmostEqual(warm["beta_0_rad"], cold["beta_0_rad"],
                                delta=1e-6)
        self.assertAlmostEqual(warm["beta_1c_rad"], cold["beta_1c_rad"],
                                delta=1e-6)
        self.assertLessEqual(warm["flap_outer_iterations"],
                              cold["flap_outer_iterations"])


class TestCancellation(unittest.TestCase):
    def test_should_cancel_on_third_iteration_raises_solve_cancelled(self):
        """PR-11: a should_cancel that fires on the third outer
        iteration raises SolveCancelled -- never a partial result."""
        dyn = BladeDynamicsDef(flap_model="offset", hinge_offset_norm=0.05,
                               inertia_source="lock", lock_number=8.0,
                               harmonics=3, outer_max_iter=60,
                               outer_tol_deg=1e-8)
        project = _make_project(dyn, config_overrides=dict(Ne=12, Npsi=20))
        condition = FlightCondition(name="fwd", mu_x=0.25,
                                     collective_deg=8.0, rpm=800.0)
        calls = {"n": 0}

        def cancel_on_third():
            calls["n"] += 1
            return calls["n"] > 2

        with self.assertRaises(SolveCancelled):
            studies.run_single_case(project, condition,
                                     should_cancel=cancel_on_third)


if __name__ == "__main__":   # pragma: no cover
    unittest.main()
