"""One convention for every axial quantity (`PR-8`, `EN-4`).

The rule, stated once so a change to any one surface has something to
fail against:

    V_z, lambda_z, mu_z, J_z, lambda_total and V_z,total are POSITIVE in
    the direction the induced velocity acts -- through the disk from
    above to below. That is why lambda_total = lambda_z + lambda_i is a
    SUM, and why a positive V_z lowers the thrust.

    alpha_rotor is the disk ANGLE OF ATTACK and is written the way a
    wing's is: POSITIVE when the stream arrives from BELOW the disk. It
    is therefore -atan2(V_z, V_x), and a positive angle goes with a
    NEGATIVE V_z.

    alpha_disk is not an angle of attack. It measures the stream's tilt
    away from the SHAFT, keeps the geometric sign, and reads zero for a
    propeller in straight cruise.

`alpha_rotor` used to carry the geometric sign, which put it alone
outside the family: a positive angle meant a stream from ABOVE, the
opposite of what the same symbol means in every rotor text. The whole
point of the family is that a reader can predict the sign of one
quantity from another, so the odd one out was the defect.

`alpha_deg` is an INPUT-ONLY alias: a saved condition stores `Vz`, and
no `.bemt` file holds an angle, so this convention lives entirely on the
surfaces the user reads and types. The single exception is a batch whose
`sweep_params` carry `alpha_deg_values`, which is re-read under the new
rule like any other input.
"""
import unittest

import numpy as np

from zbemt import api, bemt, geometry, studies
from zbemt.models import AirfoilDef, FlightCondition, Project


def _project(propeller=False):
    geom = geometry.generate_rectangular(chord_norm=0.08, twist_root_deg=8.0,
                                          twist_tip_deg=0.0, radius_m=1.0,
                                          n_stations=12)
    config = dict(Ne=12, Npsi=24, solver="newton", max_iter=200,
                   prandtl_loss_mode="off", use_compressibility=False)
    if propeller:
        config["is_propeller"] = True
    return Project(name="sign", geometry=geom,
                    airfoil=AirfoilDef(source="analytical",
                                       stall_model="linear"),
                    config=config)


def _summary(Vz, propeller=False, mu_x=0.2, rpm=600.0):
    return api.run_case(_project(propeller),
                         FlightCondition(mu_x=mu_x, Vz=Vz,
                                         collective_deg=8.0,
                                         rpm=rpm)).summary


class TestTheAxialFamilySharesOneSign(unittest.TestCase):

    FAMILY = ("lambda_z", "mu_z", "J_z")

    def test_every_member_follows_Vz(self):
        for Vz in (-10.0, 10.0):
            summary = _summary(Vz)
            for key in self.FAMILY:
                with self.subTest(Vz=Vz, key=key):
                    self.assertEqual(np.sign(summary[key]), np.sign(Vz),
                                      f"{key} does not follow the sign of Vz")

    def test_the_total_is_a_sum_not_a_difference(self):
        """`lambda_total = lambda_z + lambda_i`. If the axial component
        were counted the other way this would have to be a subtraction,
        which is exactly the confusion the one-convention rule removes."""
        for Vz in (-10.0, 0.0, 10.0):
            with self.subTest(Vz=Vz):
                s = _summary(Vz)
                self.assertAlmostEqual(s["lambda_total"],
                                       s["lambda_z"] + s["lambda_i"],
                                       places=9)

    def test_a_positive_axial_flow_lowers_the_thrust(self):
        """The physical consequence, and the reason the sum is a sum:
        flow from above adds to the induced velocity, so the blade sees
        a smaller incidence."""
        self.assertLess(_summary(10.0)["CT"], _summary(0.0)["CT"])
        self.assertGreater(_summary(-10.0)["CT"], _summary(0.0)["CT"])


class TestTheDiskAngleOfAttack(unittest.TestCase):

    def test_a_stream_from_below_is_positive(self):
        self.assertGreater(_summary(-10.0)["alpha_rotor_deg"], 0.0)

    def test_a_stream_from_above_is_negative(self):
        self.assertLess(_summary(10.0)["alpha_rotor_deg"], 0.0)

    def test_it_is_the_negative_of_the_geometric_angle(self):
        for Vz in (-30.0, -1.0, 1.0, 30.0):
            with self.subTest(Vz=Vz):
                s = _summary(Vz)
                geometric = np.degrees(np.arctan2(s["Vz"], s["Vx"]))
                self.assertAlmostEqual(s["alpha_rotor_deg"], -geometric,
                                       places=6)

    def test_the_positive_angle_is_the_one_that_raises_the_thrust(self):
        """The reason the convention is worth having: the sign of the
        angle predicts the sign of the thrust change, exactly as it does
        for a wing."""
        high = _summary(-10.0)
        low = _summary(10.0)
        self.assertGreater(high["alpha_rotor_deg"], low["alpha_rotor_deg"])
        self.assertGreater(high["CT"], low["CT"])

    def test_level_forward_flight_is_zero(self):
        self.assertAlmostEqual(_summary(0.0)["alpha_rotor_deg"], 0.0,
                               places=9)


class TestTheAngleFromTheShaftDidNotChange(unittest.TestCase):
    """`alpha_disk` measures a different thing and keeps its own sign."""

    def test_a_propeller_in_straight_cruise_reads_zero(self):
        summary = _summary(30.0, propeller=True, mu_x=0.0, rpm=3000.0)
        self.assertAlmostEqual(summary["alpha_disk_deg"], 0.0, places=6)

    def test_edgewise_flight_reads_ninety(self):
        self.assertAlmostEqual(_summary(0.0)["alpha_disk_deg"], 90.0,
                               places=6)

    def test_the_identity_between_the_two_angles(self):
        """`alpha_disk = 90 + alpha_rotor`, modulo one revolution."""
        for Vz in (-30.0, -1.0, 0.0, 1.0, 30.0):
            with self.subTest(Vz=Vz):
                s = _summary(Vz)
                deviation = (s["alpha_disk_deg"] - s["alpha_rotor_deg"]
                             - 90.0 + 180.0) % 360.0 - 180.0
                self.assertAlmostEqual(deviation, 0.0, places=6)


class TestTheInputConvertersAgreeWithTheOutput(unittest.TestCase):
    """`PA-1`: the angle a user TYPES and the angle the run REPORTS have
    to be the same quantity, or the GUI and the results table disagree
    about what was flown."""

    RPM, RADIUS, MU = 600.0, 1.0, 0.2

    def test_a_positive_angle_gives_a_negative_axial_speed(self):
        self.assertLess(api.vv_from_alpha_deg(5.0, self.MU, self.RPM,
                                               self.RADIUS), 0.0)

    def test_the_pair_round_trips(self):
        for alpha in (-30.0, -5.0, 0.0, 5.0, 30.0):
            with self.subTest(alpha=alpha):
                Vz = api.vv_from_alpha_deg(alpha, self.MU, self.RPM,
                                            self.RADIUS)
                back = api.alpha_deg_from_vv(Vz, self.MU, self.RPM,
                                              self.RADIUS)
                self.assertAlmostEqual(back, alpha, places=9)

    def test_typing_an_angle_reproduces_it_in_the_summary(self):
        """End to end: convert an angle to the axial speed the way the
        GUI does, run it, and read the angle back off the results."""
        for alpha in (-10.0, 4.0):
            with self.subTest(alpha=alpha):
                Vz = api.vv_from_alpha_deg(alpha, self.MU, self.RPM,
                                            self.RADIUS)
                summary = _summary(Vz, mu_x=self.MU, rpm=self.RPM)
                self.assertAlmostEqual(summary["alpha_rotor_deg"], alpha,
                                       places=6)


class TestTheEngineAcceptsTheAngleAsAnInput(unittest.TestCase):
    """`resolve_advance_velocity` must invert its own reporting."""

    def test_giving_the_angle_reproduces_it(self):
        cfg = bemt.BEMTConfig()
        rotor = studies._to_rotor(_project().geometry, rpm=600.0)
        for alpha in (-20.0, -3.0, 3.0, 20.0):
            with self.subTest(alpha=alpha):
                _mu, Vv, meta = bemt.resolve_advance_velocity(
                    rotor, cfg, mu_x=0.2, alpha_deg=alpha)
                self.assertAlmostEqual(meta["alpha_rotor_deg"], alpha,
                                       places=9)
                self.assertEqual(np.sign(Vv), -np.sign(alpha))


if __name__ == "__main__":   # pragma: no cover
    unittest.main()
