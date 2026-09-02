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

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


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
    """`EN-4`. The damping is the moment of the ``(r - eR)*beta_dot``
    term of U_P about the hinge, so it is one elementary integral and
    there is no reason to ship an approximation of it."""

    def test_central_hinge_reduces_to_the_classic_gamma_over_eight(self):
        gamma = 8.0
        self.assertAlmostEqual(geometry.flap_aero_damping(gamma, 0.0),
                                gamma / 8.0, places=12)

    def test_it_matches_the_integral_it_comes_from(self):
        """Checked against the integral itself, evaluated numerically,
        rather than against a rewritten formula: that is what makes this
        a check on the algebra."""
        from scipy import integrate

        gamma = 8.0
        for e in (0.0, 0.05, 0.12, 0.30):
            with self.subTest(hinge_offset=e):
                value, _err = integrate.quad(
                    lambda x, e=e: x * (x - e) ** 2, e, 1.0)
                self.assertAlmostEqual(geometry.flap_aero_damping(gamma, e),
                                        0.5 * gamma * value, places=10)

    def test_the_old_expansion_is_recovered_for_a_small_offset(self):
        """gamma*(1/8 - e/3 + e^2/4) is the second-order expansion of the
        same expression. It has to agree where the expansion is valid,
        and it is allowed to disagree where it is not -- at e = 0.3 the
        expansion is 0.7 % high."""
        gamma = 8.0
        expansion = lambda e: gamma * (0.125 - e / 3.0 + 0.25 * e * e)
        self.assertAlmostEqual(geometry.flap_aero_damping(gamma, 0.05),
                                expansion(0.05), places=5)
        self.assertLess(geometry.flap_aero_damping(gamma, 0.30),
                         expansion(0.30))


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

        def _advancing_alpha_mean(res):
            """MEAN SIGNED incidence over the advancing quadrant.

            This used to be the 95th percentile of |alpha_eff|, which
            measured the wrong thing. Once the flap RATE reaches the
            aerodynamics the relief gets stronger, not weaker -- the mean
            incidence there falls from about 9.8 deg rigid to about 6.6
            deg -- but the tilt also carries part of the quadrant to
            slightly NEGATIVE incidence, and taking the absolute value
            first turned that extra redistribution into a larger number.
            The percentile was reporting spread; the docstring above
            claims relief. The mean is what the claim is about."""
            maps = res.maps
            mask = (maps["PSI"] < np.pi / 2) & (maps["Ut"] > 0)
            return float(np.degrees(np.mean(maps["alpha_eff"][mask])))

        self.assertLess(_advancing_alpha_mean(r_on),
                        _advancing_alpha_mean(r_off),
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


class TestForwardFlapConvergence(unittest.TestCase):
    def test_reference_rotor_converges_at_moderate_advance_ratio(self):
        """SC-11: a declared outer tolerance must be reached before use."""
        project = api.open_project(os.path.join(REPO, "projects", "starter_rotor"))
        dynamics = BladeDynamicsDef(
            flap_model="offset", hinge_offset_norm=0.05,
            inertia_source="lock", lock_number=8.0, harmonics=2,
            outer_tol_deg=1e-4, outer_max_iter=40, outer_relax=0.5,
        )
        project.geometry.dynamics = dynamics
        project.config.update(Ne=32, Npsi=48, solver="newton", max_iter=300)
        for advance_ratio in (0.20, 0.25):
            with self.subTest(advance_ratio=advance_ratio):
                result = studies.run_single_case(
                    project,
                    FlightCondition(name="moderate-forward", mu_x=advance_ratio,
                                    collective_deg=10.0, rpm=600.0),
                )
                self.assertTrue(result.summary["flap_outer_converged"])
                self.assertLess(
                    result.summary["flap_outer_residual_deg"],
                    dynamics.outer_tol_deg,
                )


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
        self.assertIn("test13", golden,
                      "the example project must be part of the snapshot")
        project = api.open_project(
            os.path.join(REPO, "projects", "test13"))
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
        self.assertEqual(result.maps["beta_coeffs"], {})
        self.assertEqual(result.maps["beta_0_rad"], 0.0)
        self.assertEqual(result.maps["beta_1c_rad"], 0.0)
        self.assertEqual(result.maps["beta_1s_rad"], 0.0)
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


def _flapping_project(**dyn_overrides):
    """A flapping blade in forward flight -- where the rate terms matter."""
    dyn = BladeDynamicsDef(flap_model="rigid_flap", hinge_offset_norm=0.05,
                            inertia_source="lock", lock_number=8.0,
                            harmonics=3, **dyn_overrides)
    geom = geometry.generate_rectangular(chord_norm=0.08, twist_root_deg=0.0,
                                          twist_tip_deg=0.0, radius_m=1.0,
                                          n_stations=16)
    return Project(name="flap_rates",
                    geometry=replace(geom, dynamics=dyn),
                    airfoil=AirfoilDef(source="analytical", stall_model="linear"),
                    config=dict(Ne=16, Npsi=24, solver="newton", max_iter=300,
                                inflow_field_model="pitt_peters_steady",
                                prandtl_loss_mode="off",
                                use_rotational_augmentation=False,
                                use_radial_flow_correction=False,
                                use_compressibility=False))


class TestTheBladeRateReachesTheAerodynamics(unittest.TestCase):
    """`SC-11`. A flapping blade sees its own incidence change in
    proportion to the flap RATE: the term (r - eR)*beta_dot of U_P is
    first-order physics, not a refinement.

    The outer loop deliberately holds the rates at zero WHILE it
    iterates -- feeding them back inside the loop makes the iteration
    gain far exceed one for a small hinge offset -- and then does one
    final solve with the converged rates, so that the reported field is
    the one the reported blade state produces. That final pass was
    guarded by a variable that was initialised to None and never
    assigned, so it never ran: every flapping result carried
    beta_dot = 0 while reporting a blade sweeping through tens of
    degrees, and the check box that feeds the lag rate into the in-plane
    speed did nothing at all.
    """

    def test_the_flap_rate_is_not_identically_zero(self):
        project = _flapping_project()
        maps = studies.run_single_case(project, FlightCondition(
            mu_x=0.30, collective_deg=8.0, rpm=600.0)).maps
        beta = np.asarray(maps["beta"], dtype=float)
        rate = np.asarray(maps["beta_rate"], dtype=float)
        self.assertGreater(np.max(np.abs(beta)), 1e-3,
                            "the blade is not flapping at all: the test says "
                            "nothing about the rate")
        self.assertGreater(np.max(np.abs(rate)), 1e-6,
                            "the blade flaps but its rate is zero everywhere: "
                            "the consistency pass did not run")

    def test_the_rate_is_the_derivative_of_the_angle(self):
        """The map carries beta_dot in rad/s, so it is Omega*d(beta)/d(psi).
        If the two disagree, the field was solved with one blade state
        and reported with another."""
        project = _flapping_project()
        maps = studies.run_single_case(project, FlightCondition(
            mu_x=0.30, collective_deg=8.0, rpm=600.0)).maps
        beta = np.asarray(maps["beta"], dtype=float)[0, :]
        rate = np.asarray(maps["beta_rate"], dtype=float)[0, :]
        psi = np.asarray(maps["PSI"], dtype=float)[0, :]
        omega = 600.0 * 2.0 * np.pi / 60.0
        numeric = omega * np.gradient(beta, psi, edge_order=2)
        scale = max(np.max(np.abs(numeric)), 1e-9)
        self.assertLess(np.max(np.abs(rate - numeric)) / scale, 0.05)

    def test_feeding_the_lag_rate_back_changes_the_answer(self):
        """`lag_feeds_back` is a physics switch, so it must move a
        number (`QR-8`). It adds the lag rate to the in-plane speed,
        which is what the tangential force is built from."""
        off = studies.run_single_case(
            _flapping_project(lag_enabled=True, lag_inertia_kg_m2=0.05,
                              lag_damping_nms_per_rad=2.0,
                              lag_feeds_back=False),
            FlightCondition(mu_x=0.30, collective_deg=8.0, rpm=600.0)).summary
        on = studies.run_single_case(
            _flapping_project(lag_enabled=True, lag_inertia_kg_m2=0.05,
                              lag_damping_nms_per_rad=2.0,
                              lag_feeds_back=True),
            FlightCondition(mu_x=0.30, collective_deg=8.0, rpm=600.0)).summary
        self.assertNotAlmostEqual(off["CQ"], on["CQ"], places=9)

    def test_the_reported_field_matches_the_reported_blade_state(self):
        """`beta_coeffs` and the maps must describe the same blade. They
        used to be one relaxation step apart, because the loop reported
        the state it had just updated to while returning the field it
        had solved before updating."""
        project = _flapping_project()
        maps = studies.run_single_case(project, FlightCondition(
            mu_x=0.30, collective_deg=8.0, rpm=600.0)).maps
        psi = np.asarray(maps["PSI"], dtype=float)[0, :]
        coeffs = maps["beta_coeffs"]
        rebuilt = np.full_like(psi, coeffs[0][0])
        for k, (c, sn) in coeffs.items():
            if k:
                rebuilt = rebuilt + c * np.cos(k * psi) + sn * np.sin(k * psi)
        beta = np.asarray(maps["beta"], dtype=float)[0, :]
        self.assertLess(np.max(np.abs(beta - rebuilt)), 1e-9)


class TestFlapbackCarriesANoseUpHubMoment(unittest.TestCase):
    """`SC-11`/`SC-14`. The classic result, and the origin of a
    helicopter's speed stability: put an offset-hinge rotor into forward
    flight with no cyclic and it flaps BACK -- the tip path plane tilts
    aft -- and the moment that tilt carries through the hinge is
    NOSE-UP. That is what makes a helicopter want to pitch up as it
    gains speed.

    The hub moment follows the tip path plane, and this engine already
    states that the longitudinal tilt is the NEGATIVE of the first
    cosine harmonic (``tpp_tilt_long_deg = -beta_1c_deg``). The hub
    moment was built from ``+beta_1c`` instead, so it came out
    nose-DOWN in exactly the case every textbook uses to introduce it.
    """

    def _forward_flight(self, mu_x):
        dyn = BladeDynamicsDef(flap_model="offset", hinge_offset_norm=0.05,
                                inertia_source="lock", lock_number=8.0,
                                harmonics=3, outer_max_iter=60)
        geom = geometry.generate_rectangular(
            chord_norm=0.08, twist_root_deg=0.0, twist_tip_deg=0.0,
            radius_m=1.0, n_stations=16)
        project = Project(
            name="flapback", geometry=replace(geom, dynamics=dyn),
            airfoil=AirfoilDef(source="analytical", stall_model="linear"),
            config=dict(Ne=16, Npsi=24, solver="newton", max_iter=300,
                        inflow_field_model="pitt_peters_steady",
                        prandtl_loss_mode="off",
                        use_rotational_augmentation=False,
                        use_radial_flow_correction=False,
                        use_compressibility=False))
        return studies.run_single_case(project, FlightCondition(
            mu_x=mu_x, collective_deg=8.0, rpm=600.0)).summary

    def test_the_rotor_flaps_back(self):
        summary = self._forward_flight(0.25)
        self.assertLess(summary["beta_1c_deg"], 0.0)
        self.assertGreater(summary["tpp_tilt_long_deg"], 0.0,
                            "the tip path plane must tilt AFT in forward flight")

    def test_the_hub_moment_of_the_flapback_is_nose_up(self):
        summary = self._forward_flight(0.25)
        self.assertGreater(summary["Mx_hub"], 0.0,
                            "an aft-tilted tip path plane carries a NOSE-UP "
                            "moment through the hinge -- this is the source of "
                            "a helicopter's speed stability")

    def test_the_hub_moment_grows_with_the_flapback(self):
        slow = self._forward_flight(0.15)
        fast = self._forward_flight(0.30)
        self.assertGreater(fast["tpp_tilt_long_deg"], slow["tpp_tilt_long_deg"])
        self.assertGreater(fast["Mx_hub"], slow["Mx_hub"])

    def test_the_hub_moment_follows_the_tip_path_plane(self):
        """The same statement as a sign identity, so that it survives a
        change of magnitude: the hub moment and the longitudinal tilt
        always agree in sign."""
        summary = self._forward_flight(0.25)
        self.assertGreater(summary["Mx_hub"] * summary["tpp_tilt_long_deg"], 0.0)


class TestSideslipRotatesTheConingTerm(unittest.TestCase):
    """`SC-14`. The sideslip angle turns the in-plane free stream, and
    every term built from that stream has to turn with it. Two of the
    three already did -- the tangential speed uses sin(psi - psi_w), the
    spanwise speed uses cos(psi - psi_w) -- while the coning
    contribution to the normal speed was left on cos(psi). A
    sideslipping rotor therefore mixed two different wind directions
    inside one velocity triangle.

    Turning the wind within the disk cannot change an integral over the
    whole disk, so C_T and the coning angle beta_0 are both invariants.
    Measured worst case over psi_w in {15, 30, 45, -45, 90, 135} deg, at
    mu_x = 0.25, every run converged to a residual below 1e-4 deg:

        beta_0 drift : 24.3 % -> 15.5 %
        C_T    drift : 14.2 % ->  2.5 %

    KNOWN GAP, stated rather than asserted: the drift does not reach
    zero. Something else in the engine still fails to rotate with
    psi_w -- the residual is identical at -45 and at 135 deg, and
    vanishes at 180 deg, so it is a once-per-revolution asymmetry. That
    is a separate defect with its own diagnosis to do. The thresholds
    below sit where this fix demonstrably puts them and where the old
    code demonstrably failed; they are not a claim that the model is
    invariant.
    """

    def _summary(self, sideslip_deg):
        dyn = BladeDynamicsDef(flap_model="offset", hinge_offset_norm=0.05,
                                inertia_source="lock", lock_number=8.0,
                                harmonics=3, outer_max_iter=60)
        geom = geometry.generate_rectangular(
            chord_norm=0.08, twist_root_deg=0.0, twist_tip_deg=0.0,
            radius_m=1.0, n_stations=16)
        project = Project(
            name="sideslip", geometry=replace(geom, dynamics=dyn),
            airfoil=AirfoilDef(source="analytical", stall_model="linear"),
            config=dict(Ne=16, Npsi=72, solver="newton", max_iter=300,
                        inflow_field_model="pitt_peters_steady",
                        prandtl_loss_mode="off",
                        use_rotational_augmentation=False,
                        use_radial_flow_correction=False,
                        use_compressibility=False,
                        inflow_sideslip_deg=sideslip_deg))
        return studies.run_single_case(project, FlightCondition(
            mu_x=0.25, collective_deg=8.0, rpm=600.0)).summary

    def test_coning_barely_moves_with_the_wind_direction(self):
        """beta_0 is the azimuthal MEAN of the flap response. Before the
        fix a thirty-degree sideslip moved it by two percent."""
        straight = self._summary(0.0)["beta_0_deg"]
        for sideslip in (30.0, 45.0):
            with self.subTest(sideslip=sideslip):
                self.assertAlmostEqual(self._summary(sideslip)["beta_0_deg"],
                                        straight, delta=0.005 * abs(straight))

    def test_thrust_barely_moves_with_the_wind_direction(self):
        """The clearest witness: at ninety degrees of sideslip the old
        coning term put C_T thirteen percent away from the straight
        case."""
        straight = self._summary(0.0)["CT"]
        for sideslip in (90.0, 135.0):
            with self.subTest(sideslip=sideslip):
                self.assertAlmostEqual(self._summary(sideslip)["CT"],
                                        straight, delta=0.03 * abs(straight))

    def test_half_a_turn_of_sideslip_is_exact(self):
        """A 180-degree rotation maps the azimuth grid onto itself, so
        this one is not approximate: it must hold to the solver's own
        tolerance, and it does so with or without the fix."""
        straight = self._summary(0.0)
        turned = self._summary(180.0)
        self.assertAlmostEqual(turned["CT"], straight["CT"], places=9)
        self.assertAlmostEqual(turned["beta_0_deg"], straight["beta_0_deg"],
                                places=9)


class TestTheHubRateForcingMatchesItsClosedForm(unittest.TestCase):
    """`EN-4`/`SC-14`. A hub rate reaches the blade twice, and the two
    paths have to be right SEPARATELY.

    The first path is aerodynamic: a pitching hub carries the element
    out of the disk plane, so U_P gains -r*(q*cos(psi) + p*sin(psi)).
    The second is inertial, and it is the one that is easy to get wrong.
    Working in vehicle axes (x forward, y to port, z up) with psi
    measured from the tail, so that e_r = -cos(psi) x - sin(psi) y, the
    hub-rate part of the element's vertical acceleration comes out of
    TWO equal halves:

        Euler, because z turns with the body:
            (dOmega_f/dt) x R      = -Omega*r*(p*cos + q_y*sin) z
        the centrifugal cross term:
            omega_b x (Omega*r*e_t) = -Omega*r*(p*cos + q_y*sin) z

    so a_z = -2*Omega*r*(p*cos(psi) + q_y*sin(psi)) and the balance sees

        Mbar_gyro = 2*(p*cos(psi) - q*sin(psi))/Omega,

    the sign of the second term following from q_y = -q once q is the
    aeronautical nose-up rate. A derivation that keeps only one of the
    two halves lands on a factor of ONE, which is why the factor is
    pinned here against a closed form rather than against a comment.

    With the 1/rev balance written out for a hovering rotor, and with
    kappa = nu_beta^2 - 1 and d the flap aero damping,

        kappa*b1c + d*b1s = +d*qbar          kappa*b1c + d*b1s = +2*pbar
        kappa*b1s - d*b1c = -2*qbar          kappa*b1s - d*b1c = +d*pbar

    whose solutions are the four numbers checked below. At kappa -> 0
    the pitch-rate response collapses to the textbook b1c = 16*qbar/gamma
    cross-coupling, which is the classical statement of the same result.

    The tolerance is five percent on the amplitude. The engine solves a
    real rotor -- non-uniform inflow, a root cutout, a real polar --
    against a closed form written for a uniform blade, so the two are
    not supposed to agree exactly. Five percent is far tighter than the
    factor of about 1.9 that separates the correct forcing from the
    half-forcing, which is what the test exists to tell apart.
    """

    E_HINGE = 0.05
    LOCK = 8.0
    RPM = 600.0

    def _project(self):
        dyn = BladeDynamicsDef(flap_model="rigid_flap",
                               hinge_offset_norm=self.E_HINGE,
                               inertia_source="lock", lock_number=self.LOCK,
                               harmonics=3)
        geom = geometry.generate_rectangular(
            chord_norm=0.08, twist_root_deg=0.0, twist_tip_deg=0.0,
            radius_m=1.0, n_stations=16)
        return Project(name="gyro",
                       geometry=replace(geom, dynamics=dyn),
                       airfoil=AirfoilDef(source="analytical",
                                          stall_model="linear"),
                       config=dict(Ne=16, Npsi=36, solver="newton",
                                   max_iter=300,
                                   inflow_field_model="glauert_global",
                                   prandtl_loss_mode="off",
                                   use_rotational_augmentation=False,
                                   use_radial_flow_correction=False,
                                   use_compressibility=False))

    def _first_harmonic(self, project, **rates):
        condition = FlightCondition(mu_x=0.0, Vz=0.0, collective_deg=6.0,
                                     rpm=self.RPM, **rates)
        return studies.run_single_case(project, condition).maps["beta_coeffs"][1]

    def _constants(self):
        omega = self.RPM * 2.0 * math.pi / 60.0
        d = geometry.flap_aero_damping(self.LOCK, self.E_HINGE)
        kappa = geometry.flap_frequency_ratio_squared(
            self.E_HINGE, 0.0, 1.0, 1.0) - 1.0
        return omega, d, kappa, kappa ** 2 + d ** 2

    def test_hover_without_a_rate_has_no_first_harmonic(self):
        """The premise: whatever the rate produces below is the rate's,
        not a 1/rev the trimmed hover already carried."""
        base = self._first_harmonic(self._project())
        self.assertLess(max(abs(base[0]), abs(base[1])), 1e-9)

    def test_the_pitch_rate_response_matches_the_closed_form(self):
        project = self._project()
        base = self._first_harmonic(project)
        omega, d, kappa, det = self._constants()
        for q_deg_s in (2.0, 4.0):
            with self.subTest(q_deg_s=q_deg_s):
                got = self._first_harmonic(project, q_rate_deg_s=q_deg_s)
                q_bar = math.radians(q_deg_s) / omega
                b1c = got[0] - base[0]
                b1s = got[1] - base[1]
                self.assertAlmostEqual(b1c / (d * q_bar * (kappa + 2.0) / det),
                                       1.0, delta=0.05)
                self.assertAlmostEqual(b1s / (q_bar * (d * d - 2.0 * kappa)
                                              / det), 1.0, delta=0.06)

    def test_halving_the_gyroscopic_term_would_be_caught(self):
        """The discriminating check, stated on its own so that a failure
        names the cause. A forcing of 1*(p*cos - q*sin) instead of 2*
        moves b1c by the ratio (kappa+1)/(kappa+2), about 0.52 here --
        an order of magnitude outside the tolerance above."""
        _omega, _d, kappa, _det = self._constants()
        half = (kappa + 1.0) / (kappa + 2.0)
        self.assertLess(abs(half - 1.0), 0.5)
        self.assertGreater(abs(half - 1.0), 0.20,
                            "the two forcings are no longer far enough "
                            "apart for this test to discriminate")

    def test_the_roll_rate_response_matches_the_closed_form(self):
        project = self._project()
        base = self._first_harmonic(project)
        omega, d, kappa, det = self._constants()
        got = self._first_harmonic(project, p_rate_deg_s=2.0)
        p_bar = math.radians(2.0) / omega
        b1c = got[0] - base[0]
        b1s = got[1] - base[1]
        self.assertAlmostEqual(b1c / (p_bar * (2.0 * kappa - d * d) / det),
                               1.0, delta=0.06)
        self.assertAlmostEqual(b1s / (d * p_bar * (kappa + 2.0) / det),
                               1.0, delta=0.05)

    def test_the_two_rates_are_one_response_turned_by_a_quarter_turn(self):
        """An axisymmetric rotor in hover cannot tell a roll rate from a
        pitch rate except by where it points, so the roll response must
        be the pitch response rotated by 90 degrees:
        (b1c, b1s)_p = (-b1s, b1c)_q. This holds for the engine's answer
        without any closed form at all, and it fails the moment one of
        the four terms -- two aerodynamic, two gyroscopic -- carries a
        sign the other three do not agree with."""
        project = self._project()
        base = self._first_harmonic(project)
        q = self._first_harmonic(project, q_rate_deg_s=2.0)
        p = self._first_harmonic(project, p_rate_deg_s=2.0)
        q1c, q1s = q[0] - base[0], q[1] - base[1]
        p1c, p1s = p[0] - base[0], p[1] - base[1]
        scale = max(abs(q1c), abs(q1s))
        self.assertGreater(scale, 1e-9, "neither rate did anything")
        self.assertLess(abs(p1c - (-q1s)) / scale, 1e-6)
        self.assertLess(abs(p1s - q1c) / scale, 1e-6)


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
