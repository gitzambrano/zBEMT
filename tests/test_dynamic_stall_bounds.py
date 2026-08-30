"""The Øye separation function, and the lift it is allowed to produce.

Found by asking what each model DOES rather than whether it runs.
Switching dynamic stall on for `starter_rotor` at mu_x = 0.30 and 14 deg
of collective took the thrust from 7615 N to 43693 N and the largest Cl
on the disk from 2.74 to 113.8. No airfoil reaches a lift coefficient of
113, so the number was not a modelling choice: it was a defect.

Two linked mistakes produced it.

f_st SAID "ATTACHED" WHERE IT MEANT "SEPARATED". The separation function
is f = (2*sqrt(ratio) - 1)^2 with ratio = Cl_static / Cl_attached. That
parabola is not monotonic: f = 1 at ratio = 1, which is the lift line
itself and means fully attached, and f = 1 again at ratio = 0, which is
no lift at all and means fully separated. Its minimum, f = 0, sits at
ratio = 0.25. The code clipped a negative ratio to zero and applied the
formula, with a comment saying "ratio<0 => full separation"; the formula
returned the opposite.

In reverse flow that is the ordinary case, not an edge case. Cl_attached
is the LINEAR lift line extrapolated to alpha = -148 deg, about -15.6,
while the static polar gives +0.96. The ratio is negative over 41.7 % of
the disk at that condition.

Cl_sep DIVIDED BY ITS OWN FLOOR. `_oye_cl_sep` returns
(Cl_st - f_st*Cl_att) / max(1 - f_st, reg) and its docstring says that
near f_st -> 1 "we use Cl_att as the limit". It did not: it divided by
reg = 1e-3, turning a numerator of 16.6 into 16603.
"""
import copy
import os
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import numpy as np

from zbemt import api, bemt
from zbemt.models import FlightCondition

#: Nothing an airfoil does reaches this. Viterna's flat-plate extension
#: peaks near 1.1, and a cambered section near 2 before it stalls; the
#: bound is deliberately loose, because what it has to catch is 113.
MAX_PLAUSIBLE_CL = 6.0


class TestTheSeparationFunction(unittest.TestCase):
    """`_oye_static_separation` alone, with no solver around it."""

    def _f(self, ratio, cl_alpha=2.0 * np.pi, alpha0=0.0):
        """The f the code computes for a stated Cl_static/Cl_attached."""
        alpha = np.array([[0.2]])            # any angle; only the ratio matters
        cl_att = cl_alpha * (alpha - alpha0)
        f, _ = bemt._oye_static_separation(alpha, ratio * cl_att, cl_alpha,
                                            alpha0, 1e-3)
        return float(f[0, 0])

    def test_the_lift_line_itself_is_fully_attached(self):
        self.assertAlmostEqual(self._f(1.0), 1.0, places=6)

    def test_the_minimum_of_the_parabola_is_full_separation(self):
        self.assertAlmostEqual(self._f(0.25), 0.0, places=6)

    def test_no_lift_at_all_is_full_separation_not_full_attachment(self):
        """The defect, stated on its own. `(2*sqrt(0) - 1)^2` is 1, so
        the raw formula called a section producing NO lift fully
        attached."""
        self.assertAlmostEqual(
            self._f(0.0), 0.0, places=6,
            msg="a section producing no lift was reported as attached")

    def test_a_negative_ratio_is_full_separation(self):
        """Cl_static and the extrapolated lift line with OPPOSITE signs.
        This is the reverse-flow case that made 41.7 % of the disk
        report full attachment."""
        for ratio in (-0.06, -1.0, -10.0):
            with self.subTest(ratio=ratio):
                self.assertAlmostEqual(self._f(ratio), 0.0, places=6)

    def test_f_is_monotonic_over_the_physical_branch(self):
        """Above the minimum, more static lift means more attachment.
        Below it the parabola climbs back, which is why the branch has to
        be cut rather than merely clipped."""
        ratios = np.linspace(0.25, 1.0, 25)
        values = [self._f(r) for r in ratios]
        self.assertTrue(all(b >= a - 1e-9 for a, b in zip(values, values[1:])),
                         "f must rise with the lift ratio above ratio=0.25")

    def test_f_never_leaves_zero_to_one(self):
        for ratio in (-5.0, -0.1, 0.0, 0.1, 0.25, 0.5, 1.0, 2.0, 10.0):
            with self.subTest(ratio=ratio):
                self.assertGreaterEqual(self._f(ratio), 0.0)
                self.assertLessEqual(self._f(ratio), 1.0)


class TestTheSeparatedLiftTakesItsLimit(unittest.TestCase):

    def test_attached_flow_returns_the_lift_line(self):
        """The docstring's own rule: at f_st = 1, Cl_dyn is Cl_att
        whatever Cl_sep holds, so Cl_sep must BE Cl_att there rather than
        a numerator divided by 1e-3."""
        cl_st = np.array([0.96])
        cl_att = np.array([-15.65])
        f_st = np.array([1.0])
        out = bemt._oye_cl_sep(cl_st, f_st, cl_att, 1e-3)
        self.assertAlmostEqual(float(out[0]), float(cl_att[0]), places=9)

    def test_separated_flow_still_uses_the_formula(self):
        """The fix must not swallow the ordinary branch."""
        cl_st = np.array([1.0])
        cl_att = np.array([2.0])
        f_st = np.array([0.5])
        out = bemt._oye_cl_sep(cl_st, f_st, cl_att, 1e-3)
        self.assertAlmostEqual(float(out[0]), (1.0 - 0.5 * 2.0) / 0.5,
                                places=9)


class TestTheDiskNeverCarriesAnAbsurdLift(unittest.TestCase):
    """The end-to-end statement, on the case that exposed it."""

    @classmethod
    def setUpClass(cls):
        cls.project = api.open_project("projects/starter_rotor")

    def _run(self, use_dynamic_stall, **fields):
        local = copy.deepcopy(self.project)
        local.airfoil.use_dynamic_stall = use_dynamic_stall
        base = dict(name="probe", rpm=1200.0, collective_deg=14.0, mu_x=0.30)
        base.update(fields)
        return api.run_case(local, FlightCondition(**base))

    def test_dynamic_stall_does_not_invent_lift(self):
        off = self._run(False)
        on = self._run(True)
        cl_off = np.abs(np.asarray(off.maps["Cl"], dtype=float)).max()
        cl_on = np.abs(np.asarray(on.maps["Cl"], dtype=float)).max()
        self.assertLess(
            cl_on, MAX_PLAUSIBLE_CL,
            f"the disk carries Cl = {cl_on:.1f} with dynamic stall on; it "
            f"reached 113.8 before the separation function was fixed")
        self.assertLess(
            cl_on, 1.5 * cl_off,
            f"dynamic stall may overshoot the static polar, by tens of "
            f"percent; here it went from {cl_off:.2f} to {cl_on:.2f}")

    def test_it_does_not_multiply_the_thrust(self):
        """It delays separation and can overshoot, so a change of some
        percent is expected. A factor of 5.7 is not."""
        off = self._run(False).summary["Thrust"]
        on = self._run(True).summary["Thrust"]
        ratio = on / off
        self.assertGreater(ratio, 0.5, f"thrust ratio {ratio:.3f}")
        self.assertLess(
            ratio, 1.15,
            f"switching dynamic stall on changed the thrust by a factor "
            f"of {ratio:.2f}; it was 5.74 before the fix")

    def test_hover_is_untouched(self):
        """No cycle, so no hysteresis: the model must change NOTHING.

        This is the exact statement, not an approximate one. In steady
        flow the lag equation gives f = f_st, and the model is written so
        that the correction is proportional to (f - f_st); the static
        polar therefore comes back bit for bit. It used to lose 6.5 % of
        the thrust here, because the blend reached the static polar by a
        cancellation that failed wherever `f_st` had been clipped to 1.
        """
        off = self._run(False, mu_x=0.0).summary["Thrust"]
        on = self._run(True, mu_x=0.0).summary["Thrust"]
        self.assertAlmostEqual(on, off, delta=1e-6 * abs(off))

    def test_the_effect_grows_with_how_much_the_angle_cycles(self):
        """Dynamic stall is a lag, so its size is set by how far the
        angle of attack travels in one revolution. In hover it travels
        nowhere and the effect is exactly zero; it grows with the advance
        ratio, and it is an OVERSHOOT, because delaying separation lets
        the blade carry a little more lift than the static polar.

        Before the fix the ratio ran 0.94 at hover and 5.74 at mu_x=0.30:
        the wrong sign at rest and a factor of six in forward flight."""
        ratios = {}
        for mu in (0.0, 0.10, 0.20, 0.30):
            off = self._run(False, mu_x=mu).summary["Thrust"]
            on = self._run(True, mu_x=mu).summary["Thrust"]
            ratios[mu] = on / off
            with self.subTest(mu_x=mu):
                self.assertGreaterEqual(
                    ratios[mu], 1.0 - 1e-9,
                    f"at mu_x={mu} the model LOST lift ({off:.0f} -> "
                    f"{on:.0f} N); delaying separation cannot do that")
                self.assertLess(
                    ratios[mu], 1.15,
                    f"at mu_x={mu} the overshoot is {100*(ratios[mu]-1):.1f} %, "
                    f"which is past what a lag in separation can buy")
        self.assertGreater(
            ratios[0.30], ratios[0.10],
            "the effect must grow with the advance ratio: that is what "
            "makes it a cyclic effect rather than a constant offset")


if __name__ == "__main__":   # pragma: no cover
    unittest.main()
