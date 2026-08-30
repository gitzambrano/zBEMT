"""`QR-8`. The two Oye methods must agree where both are valid.

`dynamic_stall_method` publishes two ways of solving the same model. The
FREQUENCY method answers algebraically, assuming the separation point
responds to a single dominant harmonic of the loading. The TIME MARCH
integrates the relaxation equation around the disk instead, revolution
after revolution, until the response repeats.

Two implementations of one model are only trustworthy if they meet. They
should meet at LOW advance ratio, where the loading varies little around
the azimuth and the frequency method's assumption is closest to true,
and they are free to part company as the advance ratio grows and the
loading stops looking like one harmonic. That is the shape this file
pins: agreement where it is owed, and a measured, stated divergence
where it is not.

`QR-8` also asks that a physics option be shown to DO something. An
agreement test alone cannot show that: two methods that were both
inactive would agree perfectly and prove nothing. So every comparison
here first checks that dynamic stall moved the answer away from the
static polar.
"""
import unittest
from dataclasses import asdict

from zbemt import api, geometry
from zbemt.bemt import BEMTConfig
from zbemt.models import AirfoilDef, FlightCondition, Project

#: Deep enough into stall that the model has something to do: the
#: retreating side runs past the static stall angle.
STALLING_COLLECTIVE_DEG = 16.0


def _project(method: str, dynamic: bool = True) -> Project:
    geom = geometry.generate_tapered(
        root_chord_norm=0.12, tip_chord_norm=0.06, twist_root_deg=8.0,
        twist_tip_deg=0.0, radius_m=1.0, n_stations=16)
    airfoil = AirfoilDef(source="analytical", stall_model="viterna",
                          use_dynamic_stall=dynamic,
                          dynamic_stall_method=method)
    config = asdict(BEMTConfig(Ne=16, Npsi=36, solver="newton", max_iter=200,
                                use_dynamic_stall=dynamic))
    config.update(dynamic_stall_method=method, prandtl_loss_mode="off",
                   use_compressibility=False,
                   dynamic_stall_time_march_revolutions=12)
    return Project(name=f"oye {method}", geometry=geom, airfoil=airfoil,
                    config=config)


def _summary(method: str, mu_x: float, dynamic: bool = True) -> dict:
    condition = FlightCondition(mu_x=mu_x, Vz=0.0,
                                 collective_deg=STALLING_COLLECTIVE_DEG,
                                 rpm=600.0)
    return api.run_case(_project(method, dynamic), condition).summary


class TestTheModelIsActuallyDoingSomething(unittest.TestCase):
    """The premise of every comparison below."""

    #: Where the model has the most to do on THIS rotor. Measured, with
    #: the corrected separation function:
    #:
    #:     mu_x   0.20   0.30   0.40   0.50
    #:     dCT    1.36%  0.58%  0.12%  0.49%
    #:
    #: The premise only needs one condition where the option demonstrably
    #: moves the answer, and this is the strongest.
    #:
    #: It used to read 0.30, chosen when the separation function was
    #: reporting "attached" for the whole reverse-flow region: dynamic
    #: stall then multiplied the thrust of a stalled disk by up to 5.7,
    #: so any condition cleared the bar. With that fixed the effect is
    #: what a lag in separation actually buys -- a percent or two -- and
    #: the condition has to be chosen rather than assumed.
    LIVELIEST_MU_X = 0.20

    def test_dynamic_stall_moves_the_answer_away_from_the_static_polar(self):
        static = _summary("frequency", self.LIVELIEST_MU_X, dynamic=False)
        dynamic = _summary("frequency", self.LIVELIEST_MU_X, dynamic=True)
        relative = abs(dynamic["CT"] - static["CT"]) / abs(static["CT"])
        self.assertGreater(relative, 0.01,
                            "dynamic stall changed nothing, so an agreement "
                            "between the two methods would prove nothing")

    def test_the_blade_really_reaches_stall(self):
        import numpy as np

        condition = FlightCondition(mu_x=0.30, Vz=0.0,
                                     collective_deg=STALLING_COLLECTIVE_DEG,
                                     rpm=600.0)
        maps = api.run_case(_project("frequency"), condition).maps
        peak = float(np.degrees(np.asarray(maps["alpha_eff"])).max())
        self.assertGreater(peak, 15.0,
                            f"peak incidence is only {peak:.1f} deg: this "
                            "condition never stalls")


class TestTheTwoMethodsAgreeAtLowAdvanceRatio(unittest.TestCase):
    """The cross-check itself."""

    def _difference(self, mu_x, key):
        frequency = _summary("frequency", mu_x)
        march = _summary("time_march", mu_x)
        return abs(march[key] - frequency[key]) / abs(frequency[key])

    def test_thrust_agrees_within_one_percent(self):
        for mu_x in (0.02, 0.05):
            with self.subTest(mu_x=mu_x):
                self.assertLess(self._difference(mu_x, "CT"), 0.01)

    def test_torque_agrees_within_one_percent(self):
        for mu_x in (0.02, 0.05):
            with self.subTest(mu_x=mu_x):
                self.assertLess(self._difference(mu_x, "CQ"), 0.01)


class TestTheyPartCompanyWhereTheyShould(unittest.TestCase):
    """Not a defect, and worth pinning so it is not read as one.

    Past roughly a tenth of an advance ratio the loading stops looking
    like one harmonic, the frequency method's assumption stops holding,
    and the two answers separate. Measured here so that a future change
    which quietly makes them identical everywhere is noticed: that would
    mean the time march had stopped marching.
    """

    def test_the_difference_grows_with_the_advance_ratio(self):
        near_hover = self._ct_difference(0.05)
        forward = self._ct_difference(0.20)
        self.assertLess(near_hover, 0.01)
        self.assertGreater(forward, near_hover)

    def _ct_difference(self, mu_x):
        frequency = _summary("frequency", mu_x)
        march = _summary("time_march", mu_x)
        return abs(march["CT"] - frequency["CT"]) / abs(frequency["CT"])


class TestTheMarchReportsWhetherItSettled(unittest.TestCase):
    """`EN-9`: a march that did not reach a periodic regime has to say
    so, and `validate_results` is what turns that into a finding."""

    def test_the_residual_is_reported(self):
        summary = _summary("time_march", 0.05)
        self.assertIn("dynamic_stall_periodic_residual", summary)

    def test_a_settled_march_produces_no_finding(self):
        summary = _summary("time_march", 0.05)
        messages = [i.message for i in api.validate_results(summary)
                    if "periodic" in i.message]
        self.assertEqual(messages, [],
                          "twelve revolutions at this condition should settle")


if __name__ == "__main__":
    unittest.main()
