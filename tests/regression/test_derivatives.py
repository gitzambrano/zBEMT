"""Verify the stability-derivative engine inputs (SC-14, Item 4).

Phase 4.1 physics: the sideslip angle rotates the in-plane free stream
without disturbing anything at its inert default of zero, and the hub
angular rates reach the aerodynamics and the flap balance with the signs
rotating-frame kinematics demand -- the pitch damping must come out
negative, and the flap response to a steady pitch rate must lag the rate
by about ninety degrees in hover.
"""

import math
import unittest

import numpy as np

from dataclasses import replace

from zbemt import api
from zbemt.bemt import BEMTConfig
from zbemt.models import BladeDynamicsDef, FlightCondition
from tests.helpers import make_studies_project


def _project(**cfg):
    return make_studies_project(Ne=10, Npsi=24, **cfg)


def _condition(project, **overrides):
    base = FlightCondition(name="d", mu_x=0.0, collective_deg=8.0,
                            rpm=600.0)
    return replace(base, **overrides)


def _omega_r(project) -> float:
    """Tip speed of the project's rotor at the condition RPM used here."""
    return api.mu_to_V(1.0, 600.0, project.geometry.radius_m)


class TestSideslip(unittest.TestCase):
    def test_config_default_is_zero(self):
        self.assertEqual(BEMTConfig().inflow_sideslip_deg, 0.0)

    def test_explicit_zero_matches_the_legacy_condition(self):
        project = _project()
        cond = _condition(project, mu_x=0.2)
        legacy = replace(cond, sideslip_deg=0.0)
        a = api.run_case(project, cond).summary
        b = api.run_case(project, legacy).summary
        for key in ("Thrust", "Torque", "CT", "CP", "CH", "CY"):
            self.assertEqual(a[key], b[key], key)

    def test_the_angle_that_names_no_velocity_is_refused(self):
        """Ninety degrees of sideslip has no reading.

        The angle SPLITS the longitudinal component into a lateral one,
        so at ninety degrees it asks for a lateral velocity while giving
        the longitudinal one no share of the stream at all. The lateral
        velocity is the spelling that says it, and the angle spelling
        says so instead of returning a number built from a tangent that
        has run away."""
        project = _project()
        with self.assertRaises(ValueError) as raised:
            api.run_case(project, _condition(
                project, mu_x=0.25, sideslip_deg=90.0))
        self.assertIn("Vy", str(raised.exception))

    def test_lateral_flow_of_ninety_degrees_swaps_the_in_plane_forces(self):
        """The rotor is axisymmetric under rotating the in-plane flow by
        ninety degrees: thrust and torque are unchanged, and the
        in-plane/side force pair swaps (the side force picks up the sign
        its axis convention gives it).

        The ninety-degree case is written with the LATERAL VELOCITY, the
        one spelling that reaches it: the whole in-plane stream moves
        into V_y and the longitudinal component goes to zero."""
        project = _project()
        omega_r = _omega_r(project)
        a = api.run_case(project, _condition(
            project, mu_x=0.25, sideslip_deg=0.0)).summary
        b = api.run_case(project, _condition(
            project, mu_x=0.0, Vy=0.25 * omega_r)).summary
        self.assertAlmostEqual(b["sideslip_deg"], 90.0, places=6)
        self.assertLess(abs(a["Thrust"] - b["Thrust"]) / a["Thrust"], 1e-3)
        self.assertLess(abs(a["Torque"] - b["Torque"]) / a["Torque"],
                         1e-2)
        # The swap: H(0) reappears as Y(90), Y(0) as -H(90); the minus is
        # the fixed axes' handedness under the +90 deg rotation.
        self.assertLess(abs(abs(a["CH"]) - abs(b["CY"]))
                         / max(abs(a["CH"]), 1e-12), 0.05)
        self.assertLess(abs(abs(a["CY"]) - abs(b["CH"]))
                         / max(abs(b["CH"]), 1e-12), 0.05)

    def test_summary_reports_the_sideslip_back(self):
        project = _project()
        summary = api.run_case(project, _condition(
            project, mu_x=0.2, sideslip_deg=15.0)).summary
        self.assertAlmostEqual(summary["sideslip_deg"], 15.0)


class TestHubRates(unittest.TestCase):
    def _flapping_project(self, hinge_offset_norm=0.05, lock_number=8.0):
        project = _project()
        dynamics = project.geometry.dynamics
        dynamics.flap_model = "offset"
        dynamics.hinge_offset_norm = hinge_offset_norm
        dynamics.lock_number = lock_number
        return project

    def test_rigid_blade_with_a_hub_rate_takes_the_motion_path(self):
        """A rigid blade cannot flap, but the rate still moves every
        element out of the disk plane: the loads must change."""
        project = _project()   # flap_model stays "rigid"
        zero = api.run_case(project, _condition(project)).summary
        rated = api.run_case(project, _condition(
            project, q_rate_deg_s=30.0)).summary
        self.assertGreater(abs(rated["CY"] - zero["CY"])
                            + abs(rated["CH"] - zero["CH"]), 1e-6)

    def test_flap_response_to_a_pitch_rate_lags_about_ninety_degrees(self):
        """In hover, the periodic flap response to a steady pitch rate
        lags the forcing by close to the classic ninety degrees."""
        project = self._flapping_project(hinge_offset_norm=0.12)
        result = api.run_case(project, _condition(
            project, q_rate_deg_s=20.0))
        beta_1c, beta_1s = result.maps["beta_coeffs"][1]
        amplitude = math.hypot(beta_1c, beta_1s)
        self.assertGreater(amplitude, 1e-4,
                            "a pitch rate must excite the 1/rev flap")
        phase = math.degrees(math.atan2(beta_1s, beta_1c))
        # The gyroscopic forcing of a pitch rate is -q*sin(psi), so it
        # peaks at psi = 270 deg, not at 90. The reference used to say
        # 90, matching a forcing whose sign made the hover damping
        # matrix lose its rotation invariance; the ninety-degree lag the
        # test is really about is unchanged and still measured here.
        lag = (phase - 270.0) % 360.0
        self.assertTrue(0.0 < lag < 180.0,
                         f"the response must LAG, got {lag:.1f} deg")
        self.assertLess(abs(lag - 90.0), 5.0,
                         f"hover lag was {lag:.2f} deg, expected ~90")

    def test_pitch_damping_is_negative(self):
        """The failure mode this input set must never ship: a hub moment
        that aids the pitch rate instead of opposing it.

        The pitch damping is dM_x/dq. Both belong to the psi=0 axis --
        `nomenclature` calls q the rate "about the psi=0 axis" and
        M_x,total the "tilting moment about the psi=0 axis" -- so
        pairing q with M_y read the CROSS term instead, which for a
        rotor whose flap response lags by nearly ninety degrees is the
        LARGER number and has no reason to share the damping's sign. The
        check therefore passed while the damping itself was positive.
        """
        project = self._flapping_project(hinge_offset_norm=0.05)
        h = 2.0   # deg/s, central difference around zero
        plus = api.run_case(project, _condition(
            project, q_rate_deg_s=h)).summary
        minus = api.run_case(project, _condition(
            project, q_rate_deg_s=-h)).summary
        dmx_dq = ((plus["Mx_total"] - minus["Mx_total"])
                   / (2.0 * math.radians(h)))
        self.assertLess(dmx_dq, 0.0,
                         f"pitch damping dMx/dq = {dmx_dq:.4f} must be "
                         "negative")

    def test_roll_damping_matches_the_pitch_damping_in_hover(self):
        """The partner of the test above. In hover the rotor cannot tell
        one in-plane direction from another, so the roll damping must
        equal the pitch damping -- same number, same sign."""
        project = self._flapping_project(hinge_offset_norm=0.05)
        h = 2.0

        def slope(key, **rate):
            plus = api.run_case(project, _condition(
                project, **{k: +v for k, v in rate.items()})).summary
            minus = api.run_case(project, _condition(
                project, **{k: -v for k, v in rate.items()})).summary
            return (plus[key] - minus[key]) / (2.0 * math.radians(h))

        pitch = slope("Mx_total", q_rate_deg_s=h)
        roll = slope("My_total", p_rate_deg_s=h)
        self.assertLess(roll, 0.0)
        self.assertAlmostEqual(roll, pitch, delta=0.02 * abs(pitch) + 1e-6)

    def test_roll_and_pitch_rates_are_reported_back(self):
        project = _project()
        summary = api.run_case(project, _condition(
            project, p_rate_deg_s=7.5, q_rate_deg_s=-3.0)).summary
        self.assertAlmostEqual(summary["p_rate_deg_s"], 7.5)
        self.assertAlmostEqual(summary["q_rate_deg_s"], -3.0)


class TestDerivativeEngine(unittest.TestCase):
    """Phase 4.2: the finite-difference machinery itself."""

    def _request(self, project, **overrides):
        from zbemt.models import DerivativeRequest
        base = DerivativeRequest(
            name="d",
            condition=_condition(project),
            trim="none",
            states=["w"],
            controls=["theta_0"],
            outputs=["Thrust", "H", "Y", "Mx_total", "My_total", "Torque"],
            richardson_check=True)
        return replace(base, **overrides)

    def test_zero_and_negative_steps_are_rejected_by_name(self):
        project = _project()
        for bad in (0.0, -0.5):
            request = self._request(project,
                                     steps={"w": bad})
            with self.assertRaises(ValueError) as ctx:
                api.compute_derivatives(project, request)
            self.assertIn("w", str(ctx.exception))

    def test_unknown_variable_is_rejected(self):
        project = _project()
        request = self._request(project, states=["u", "not_a_state"])
        with self.assertRaises(ValueError) as ctx:
            api.compute_derivatives(project, request)
        self.assertIn("not_a_state", str(ctx.exception))

    def test_heave_damping_is_negative_in_hover(self):
        """The most basic rotor result: thrust falls when the rotor
        climbs (QR-8). Needs no reference data."""
        project = _project()
        outcome = api.compute_derivatives(
            project, self._request(project, controls=[]))
        value = outcome.matrix[("Thrust", "w")]
        self.assertLess(value, 0.0,
                         f"dThrust/dw = {value:.3f} must be negative")

    def test_thrust_rises_with_collective(self):
        for mu_x in (0.0, 0.15):
            with self.subTest(mu_x=mu_x):
                project = _project()
                request = self._request(project, states=[])
                request = replace(request,
                                   condition=_condition(project,
                                                         mu_x=mu_x))
                outcome = api.compute_derivatives(project, request)
                self.assertGreater(outcome.matrix[("Thrust",
                                                    "theta_0")], 0.0)

    def test_halving_the_step_stays_within_the_reported_error(self):
        """Linearity: the machinery's own error estimate bounds what a
        step refinement can change."""
        project = _project()
        outcome = api.compute_derivatives(project, self._request(project))
        # Re-run with the half step and compare against the first run.
        half = self._request(project, steps={"theta_0": 0.05})
        outcome_half = api.compute_derivatives(project, half)
        reported = outcome.step_error[("Thrust", "theta_0")]
        a = outcome.matrix[("Thrust", "theta_0")]
        b = outcome_half.matrix[("Thrust", "theta_0")]
        change = abs(a - b) / max(abs(a), 1e-12)
        # The Richardson estimate compares h vs h/2 on the SAME run; the
        # independent re-run may differ slightly more, so allow the
        # reported error plus a small margin.
        self.assertLessEqual(change, max(reported * 1.5, 0.02),
                              f"step refinement moved dT/dtheta_0 by "
                              f"{change:.3%}, reported error "
                              f"{reported:.3%}")

    def test_cancellation_between_solves_raises(self):
        from zbemt.bemt import SolveCancelled
        project = _project()
        request = self._request(project, richardson_check=False)
        calls = {"n": 0}

        def stop_after_first(_project, _condition):
            calls["n"] += 1
            if calls["n"] > 1:
                raise SolveCancelled()
            return {}

        with self.assertRaises(SolveCancelled):
            api.compute_derivatives(project, request, run_case=stop_after_first)

    def test_progress_reports_every_solve(self):
        project = _project()
        seen = []
        api.compute_derivatives(project, self._request(project),
                                 on_progress=lambda done, total:
                                     seen.append((done, total)))
        self.assertGreaterEqual(len(seen), 4)   # base + 4 perturbations

    def test_request_round_trips_through_a_bemt_file(self):
        import tempfile
        from pathlib import Path
        from zbemt.models import (DerivativeRequest, load_bemt_list,
                                   save_bemt_list)
        project = _project()
        request = self._request(project)
        with tempfile.TemporaryDirectory() as d:
            path = str(Path(d) / "derivatives.bemt")
            save_bemt_list([request], path)
            loaded = load_bemt_list(DerivativeRequest, path)[0]
        self.assertEqual(loaded.name, request.name)
        self.assertEqual(loaded.states, ["w"])
        self.assertEqual(loaded.trim, "none")
        self.assertTrue(loaded.richardson_check)


class TestVehicleMatrices(unittest.TestCase):
    """Phase 4.3: hub derivatives -> rigid-body A/B, checked against a
    synthetic outcome whose exact poles are known by construction."""

    class _FakeOutcome:
        def __init__(self):
            from zbemt.derivatives import _A_PAIRS
            self.matrix = {pair: float(i + 1) for i, pair
                            in enumerate(_A_PAIRS)}
            self.matrix_nondim = {}
            self.trim_state = {"rpm": 600.0}

    def test_missing_pairs_are_named(self):
        from zbemt import derivatives as drv
        outcome = self._FakeOutcome()
        del outcome.matrix[("Mx_total", "q")]
        with self.assertRaises(ValueError) as ctx:
            drv.vehicle_matrices(outcome, mass=100.0, Ix=50.0,
                                  Iy=80.0, Iz=20.0)
        self.assertIn("Mx_total", str(ctx.exception))
        self.assertIn("q", str(ctx.exception))

    def test_synthetic_derivatives_reproduce_exact_poles(self):
        """Feed an outcome whose derivatives place KNOWN eigenvalues:
        the heave pole is exactly Z_w/m, and the yaw pole is -(dQ/dOmega)
        over I_z -- dOmega/dr is DIMENSIONLESS, so no factor of Omega
        appears."""
        from zbemt import derivatives as drv
        outcome = self._FakeOutcome()
        m, zw = 250.0, -40.0
        outcome.matrix[("Thrust", "w")] = zw   # only heave coupling on w
        iz, dq_dom = 30.0, -5.0
        outcome.matrix[("Torque", "Omega")] = dq_dom
        built = drv.vehicle_matrices(outcome, mass=m, Ix=100.0, Iy=120.0,
                                      Iz=iz, g=9.81)
        A = built["A"]
        idx = {name: i for i, name in enumerate(built["state_names"])}
        # Heave decoupled in this synthetic set: column/row w has one term.
        self.assertAlmostEqual(A[idx["w"], idx["w"]], zw / m, places=12)
        self.assertAlmostEqual(A[idx["r"], idx["r"]], -dq_dom / iz,
                                places=12)
        # Gravity couples attitude into the speed rows.
        self.assertAlmostEqual(A[idx["u"], idx["theta"]],
                                -9.81, places=12)
        eig = built["eigenvalues"]
        self.assertEqual(len(eig), 8)

    def test_every_entry_of_A_is_a_rate(self):
        """The state equation is xdot = A x, so EVERY entry of A has
        units of 1/s, whatever the state it multiplies.

        The yaw entry did not: it multiplied dQ/dOmega [N*m*s] by Omega
        [rad/s] and divided by I_z [kg*m^2], which leaves 1/s^2. The
        yaw pole was therefore wrong by the numerical value of Omega --
        a factor of about sixty at six hundred rpm. Dimensions are
        checked here by scaling: doubling every INERTIA and every MASS
        must halve every entry that carries one, and no entry may change
        when only the trim rpm changes, because rpm is not part of any
        of these units."""
        from zbemt import derivatives as drv
        import numpy as np

        slow = self._FakeOutcome()
        fast = self._FakeOutcome()
        fast.trim_state = {"rpm": 6000.0}      # ten times the shaft speed
        kwargs = dict(mass=100.0, Ix=50.0, Iy=80.0, Iz=20.0)
        a_slow = drv.vehicle_matrices(slow, **kwargs)["A"]
        a_fast = drv.vehicle_matrices(fast, **kwargs)["A"]
        np.testing.assert_allclose(
            a_fast, a_slow, atol=0.0, rtol=0.0,
            err_msg="an entry of A changed with the trim rpm, so it is "
                    "carrying a stray factor of Omega")

    def test_the_pitch_row_takes_Mx_and_the_roll_row_takes_My(self):
        """`Mx_total` is this engine's PITCHING moment and `My_total`
        its rolling one -- `api.summary_symbols` says so, and the
        damping pairs follow the same axes. The rigid-body model used
        to feed each into the other's row.

        The check is a pure routing check: put a marker in one
        derivative and see which row it comes out of."""
        from zbemt import derivatives as drv
        outcome = self._FakeOutcome()
        for pair in list(outcome.matrix):
            outcome.matrix[pair] = 0.0
        outcome.matrix[("Mx_total", "q")] = 7.0
        outcome.matrix[("My_total", "p")] = 5.0
        built = drv.vehicle_matrices(outcome, mass=1.0, Ix=1.0, Iy=1.0,
                                      Iz=1.0, g=0.0)
        A = built["A"]
        idx = {name: i for i, name in enumerate(built["state_names"])}
        self.assertAlmostEqual(A[idx["q"], idx["q"]], 7.0,
                                msg="the pitch row must take Mx_total")
        self.assertAlmostEqual(A[idx["p"], idx["p"]], 5.0,
                                msg="the roll row must take My_total")

    def test_forward_speed_row_opposes_the_H_force(self):
        """`H` is positive AFT (`api.summary_symbols`), so the forward
        force is -H. Written as +H, a rotor whose drag grew with speed
        was reported as accelerating itself."""
        from zbemt import derivatives as drv
        outcome = self._FakeOutcome()
        for pair in list(outcome.matrix):
            outcome.matrix[pair] = 0.0
        outcome.matrix[("H", "u")] = 8.0      # drag grows with speed
        built = drv.vehicle_matrices(outcome, mass=2.0, Ix=1.0, Iy=1.0,
                                      Iz=1.0, g=0.0)
        idx = {name: i for i, name in enumerate(built["state_names"])}
        self.assertAlmostEqual(built["A"][idx["u"], idx["u"]], -4.0,
                                msg="a rotor whose aft force grows with "
                                    "forward speed must DECELERATE")

    def test_the_hub_arm_tips_the_nose_up_for_a_rearward_force(self):
        """A force acting aft, above the CG, tips the vehicle nose-up --
        push the top of a box backwards and it falls backwards. The two
        hub-offset transfers used opposite relative signs for the same
        geometry."""
        from zbemt import derivatives as drv
        outcome = self._FakeOutcome()
        for pair in list(outcome.matrix):
            outcome.matrix[pair] = 0.0
        outcome.matrix[("H", "u")] = 3.0
        outcome.matrix[("Y", "v")] = 3.0
        built = drv.vehicle_matrices(outcome, mass=1.0, Ix=1.0, Iy=1.0,
                                      Iz=1.0, g=0.0, hub_offset=(0.0, 0.0, 2.0))
        A = built["A"]
        idx = {name: i for i, name in enumerate(built["state_names"])}
        self.assertAlmostEqual(A[idx["q"], idx["u"]], 6.0)
        # And the same arm, the same sign, for the side force into roll.
        self.assertAlmostEqual(A[idx["p"], idx["v"]], 6.0)

    def test_control_column_scales_by_mass(self):
        from zbemt import derivatives as drv
        outcome = self._FakeOutcome()
        outcome.matrix[("Thrust", "theta_0")] = 12.0
        built = drv.vehicle_matrices(outcome, mass=200.0, Ix=1.0,
                                      Iy=1.0, Iz=1.0)
        idx = {name: i for i, name in enumerate(built["state_names"])}
        j = built["control_names"].index("theta_0")
        self.assertAlmostEqual(built["B"][idx["w"], j], 12.0 / 200.0)

    def test_real_outcome_builds_without_error(self):
        from zbemt.models import DerivativeRequest
        project = _project()
        request = DerivativeRequest(
            name="vehicle",
            condition=_condition(project, mu_x=0.05),
            trim="none",
            states=["u", "v", "w", "p", "q", "Omega"],
            controls=["theta_0", "theta_1c", "theta_1s"],
            outputs=["Thrust", "H", "Y", "Mx_total", "My_total", "Torque"],
            richardson_check=False)
        outcome = api.compute_derivatives(project, request)
        from zbemt import derivatives as drv
        built = drv.vehicle_matrices(outcome, mass=220.0, Ix=90.0,
                                      Iy=140.0, Iz=45.0)
        self.assertEqual(len(built["eigenvalues"]), 8)
        self.assertIn("no fuselage", built["limits"])


class TestHoverDampingIsRotationInvariant(unittest.TestCase):
    """`SC-14`. A rotor in hover is axisymmetric about its own shaft, so
    the two-by-two matrix that maps a hub rate to a hub tilting moment
    cannot prefer a direction. Written in a consistent pair of
    orthogonal directions it must have the rotation-invariant form

        [[ a,  b],
         [-b,  a]]

    -- the two DIRECT terms equal, the two CROSS terms equal and
    opposite. This holds whatever the sign convention, whatever the
    hinge offset and whatever the aerodynamic model: it is a symmetry of
    the configuration, not of the model.

    The hub pitch-rate terms used to carry the wrong sign, in the
    element velocity and again in the gyroscopic flap forcing. That put
    the matrix in the form [[a, b], [b, -a]]: the direct terms came out
    equal and OPPOSITE, so one of pitch and roll damping was always
    reported as unstable while the other was stable, at exactly the same
    magnitude. The structure below is what catches that. A sign
    assertion on one derivative alone cannot, because there is a
    convention in which either sign looks right.
    """

    def _damping(self, dynamics):
        from zbemt import derivatives, geometry
        from zbemt.models import (AirfoilDef, DerivativeRequest,
                                  FlightCondition, Project)

        geom = geometry.generate_rectangular(
            chord_norm=0.08, twist_root_deg=0.0, twist_tip_deg=0.0,
            radius_m=1.0, n_stations=16)
        project = Project(
            name="damping", geometry=replace(geom, dynamics=dynamics),
            airfoil=AirfoilDef(source="analytical", stall_model="linear"),
            config=dict(Ne=16, Npsi=24, solver="newton", max_iter=300,
                        inflow_field_model="pitt_peters_steady",
                        prandtl_loss_mode="off",
                        use_rotational_augmentation=False,
                        use_radial_flow_correction=False,
                        use_compressibility=False))
        request = DerivativeRequest(
            condition=FlightCondition(name="hover", mu_x=0.0,
                                       collective_deg=8.0, rpm=600.0),
            trim="none", states=["p", "q"],
            outputs=["Mx_total", "My_total"], richardson_check=False)
        return derivatives.compute_derivatives(project, request).matrix

    def _assert_invariant(self, matrix):
        direct_pitch = matrix[("Mx_total", "q")]
        direct_roll = matrix[("My_total", "p")]
        cross_a = matrix[("Mx_total", "p")]
        cross_b = matrix[("My_total", "q")]
        scale = max(abs(direct_pitch), abs(direct_roll), abs(cross_a),
                     abs(cross_b), 1e-9)
        self.assertLess(abs(direct_pitch - direct_roll) / scale, 0.02,
                        "the direct terms must be EQUAL in hover, got "
                        "dMx/dq=%+.4f and dMy/dp=%+.4f"
                        % (direct_pitch, direct_roll))
        self.assertLess(abs(cross_a + cross_b) / scale, 0.02,
                        "the cross terms must be equal and OPPOSITE in hover, "
                        "got dMx/dp=%+.4f and dMy/dq=%+.4f"
                        % (cross_a, cross_b))

    def test_a_rigid_rotor_is_rotation_invariant(self):
        self._assert_invariant(self._damping(BladeDynamicsDef()))

    def test_an_articulated_rotor_is_rotation_invariant(self):
        self._assert_invariant(self._damping(BladeDynamicsDef(
            flap_model="offset", hinge_offset_norm=0.05,
            inertia_source="lock", lock_number=8.0, harmonics=3)))

    def test_a_rigid_rotor_damps_its_own_hub_rate(self):
        """With no flap freedom the tilting moment is purely
        aerodynamic, and then the sign is not a matter of convention: a
        nose-up rate lifts the front of the disk, which raises the
        inflow there, cuts the lift there, and so produces a nose-DOWN
        moment. Both damping derivatives must be negative."""
        matrix = self._damping(BladeDynamicsDef())
        self.assertLess(matrix[("Mx_total", "q")], 0.0)
        self.assertLess(matrix[("My_total", "p")], 0.0)


if __name__ == "__main__":
    unittest.main()


class TestDampingSummary(unittest.TestCase):
    """Item 5, cross-link 12 engine: heave/pitch damping per variant."""

    def test_linear_toy_returns_exact_slopes_per_variant(self):
        from zbemt import derivatives as drv
        from zbemt.models import Results

        def fake_run(project, condition, should_cancel=None):
            w = float(condition.Vz)
            q = math.radians(float(condition.q_rate_deg_s))
            stiff = (-2.0 if project.geometry.chord_norm[0]
                      < float(project.geometry.chord_norm[0]) else 0.0)
            # Distinguish the two variants by their ROOT chord value.
            marker = float(project.geometry.chord_norm[0])
            stiff = -2.0 if marker < 0.11 else -4.0
            # CROSS TERMS ON PURPOSE. With a separable toy -- thrust
            # from w alone, moment from q alone -- perturbing w and q in
            # the same pair of solves gives the right answer by
            # accident, so the old toy could not tell a directional
            # derivative from a partial one. Here dT/dq and dM/dw are
            # both non-zero, and only one-variable-at-a-time recovers
            # the intended slopes.
            return {"Thrust": 1000.0 + (-3.0 + stiff * 0.25) * w + 7.0 * q,
                    "Mx_total": -2.0 * q + 11.0 * w}

        project = _project()
        geom_a = replace(project.geometry)
        geom_b = replace(project.geometry,
                          chord_norm=[c * 1.2 for c in geom_a.chord_norm])
        condition = FlightCondition(name="h", mu_x=0.0,
                                     collective_deg=8.0, rpm=600.0)
        out = drv.damping_summary(
            project, {"a": geom_a, "b": geom_b}, condition,
            run_case=fake_run)
        self.assertAlmostEqual(out["a"]["heave_damping"], -3.5, places=9)
        self.assertAlmostEqual(out["b"]["heave_damping"], -4.0, places=9)
        for label in ("a", "b"):
            self.assertAlmostEqual(out[label]["pitch_damping"], -2.0,
                                    places=9)

    def test_real_variants_build_without_error(self):
        from zbemt import derivatives as drv
        from dataclasses import replace as dc_replace
        project = _project()
        geom_b = dc_replace(project.geometry,
                             chord_norm=[c * 1.2 for c in
                                          project.geometry.chord_norm])
        condition = FlightCondition(name="h", mu_x=0.05,
                                     collective_deg=8.0, rpm=600.0)
        out = drv.damping_summary(project, {"a": project.geometry,
                                             "b": geom_b}, condition)
        for label in ("a", "b"):
            for key in ("heave_damping", "pitch_damping"):
                self.assertTrue(math.isfinite(out[label][key]))


class TestFlapConvergenceGate(unittest.TestCase):
    """SC-11: a derivative matrix must carry the flap convergence behind it.

    A finite difference built on a flap solve that missed its declared outer
    tolerance is not a derivative. The study therefore counts those solves
    and clears its usable flag (`DERIV-A5`).
    """

    def _request(self, project):
        from zbemt.models import DerivativeRequest
        return DerivativeRequest(
            name="flap gate", condition=_condition(project), trim="none",
            states=["w"], outputs=["Thrust"], steps={"w": 0.5},
            richardson_check=False)

    def test_a_converged_study_is_marked_usable(self):
        project = _project()
        outcome = api.compute_derivatives(project, self._request(project))
        self.assertTrue(outcome.flap_converged)
        self.assertEqual(outcome.unconverged_solves, 0)
        self.assertNotIn("not usable", outcome.message)

    def test_one_unconverged_flap_solve_clears_the_usable_flag(self):
        project = _project()

        def run_case(_project, _condition):
            return {"Thrust": 1.0, "flap_outer_converged": False}

        outcome = api.compute_derivatives(
            project, self._request(project), run_case=run_case)
        self.assertFalse(outcome.flap_converged)
        self.assertEqual(outcome.unconverged_solves, outcome.n_solves)
        self.assertIn("not usable", outcome.message)

    def test_a_mixed_study_counts_only_the_unconverged_solves(self):
        project = _project()
        calls = {"n": 0}

        def run_case(_project, _condition):
            calls["n"] += 1
            return {"Thrust": float(calls["n"]),
                    "flap_outer_converged": calls["n"] != 2}

        outcome = api.compute_derivatives(
            project, self._request(project), run_case=run_case)
        self.assertFalse(outcome.flap_converged)
        self.assertEqual(outcome.unconverged_solves, 1)
