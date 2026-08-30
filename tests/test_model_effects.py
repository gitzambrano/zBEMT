"""Every physics option must produce the effect its model predicts.

`QR-8` asks that an option be shown to DO something. This file asks the
stronger question: does it do the RIGHT thing, in the right direction,
with the right trend? Each test states the effect a textbook predicts
and then measures it with everything else held fixed.

Written after a check of exactly this kind found the Øye separation
function reporting "fully attached" for the whole reverse-flow region
(see `tests/test_dynamic_stall_bounds.py`). Every option below runs, and
running was never the question.
"""
import copy
import math
import os
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import numpy as np

from zbemt import api
from zbemt.models import FlightCondition

#: The speed of sound the engine normalizes Mach against.
SPEED_OF_SOUND = 340.29


class _Rotor(unittest.TestCase):
    """One example project, solved with fields overridden per test."""

    @classmethod
    def setUpClass(cls):
        cls.project = api.open_project("projects/starter_rotor")
        cls.radius = cls.project.geometry.radius_m

    def solve(self, config=None, geometry=None, airfoil=None, **fields):
        local = copy.deepcopy(self.project)
        for key, value in (config or {}).items():
            local.config[key] = value
        for key, value in (geometry or {}).items():
            setattr(local.geometry, key, value)
        for key, value in (airfoil or {}).items():
            setattr(local.airfoil, key, value)
        base = dict(name="probe", rpm=1200.0, collective_deg=8.0, mu_x=0.0)
        base.update(fields)
        return api.run_case(local, FlightCondition(**base))

    def thrust(self, **kwargs):
        return self.solve(**kwargs).summary["Thrust"]


class TestCompressibility(_Rotor):
    """Prandtl-Glauert divides the lift slope by sqrt(1 - M^2)."""

    def _gain(self, rpm):
        off = self.thrust(config={"use_compressibility": False}, rpm=rpm)
        on = self.thrust(config={"use_compressibility": True}, rpm=rpm)
        return (on - off) / off

    def test_a_compressible_tip_carries_more_thrust(self):
        """1/sqrt(1 - M^2) > 1, so the same collective buys more lift."""
        self.assertGreater(self._gain(2400.0), 0.0)

    def test_the_correction_grows_with_tip_mach(self):
        low, middle, high = (self._gain(rpm) for rpm in (400.0, 1200.0,
                                                          2400.0))
        self.assertLess(low, middle)
        self.assertLess(middle, high)

    def test_it_vanishes_as_the_tip_speed_does(self):
        """At M = 0.15 the correction is under half a percent."""
        tip_mach = 400.0 * 2 * math.pi / 60.0 * self.radius / SPEED_OF_SOUND
        self.assertLess(tip_mach, 0.2)
        self.assertLess(abs(self._gain(400.0)), 0.02)


class TestTheInflowField(_Rotor):
    """A LINEAR inflow model varies the induced velocity across the
    disk. In hover there is no in-plane direction for it to vary along."""

    MODELS = ("glauert_local", "coleman_local", "drees_local",
              "pitt_peters_steady")

    def test_every_model_agrees_in_hover(self):
        thrusts = [self.thrust(config={"inflow_field_model": m}, mu_x=0.0)
                   for m in self.MODELS]
        spread = (max(thrusts) - min(thrusts)) / min(thrusts)
        self.assertLess(
            spread, 0.05,
            f"the models disagree by {100*spread:.1f} % in hover, where "
            f"there is no in-plane direction for a linear inflow to vary "
            f"along")

    def test_they_part_company_in_edgewise_flight(self):
        """If they agreed here too, the choice would be doing nothing."""
        glauert = self.thrust(config={"inflow_field_model": "glauert_local"},
                              mu_x=0.25)
        pitt = self.thrust(
            config={"inflow_field_model": "pitt_peters_steady"}, mu_x=0.25)
        self.assertGreater(abs(pitt - glauert) / glauert, 1e-6)

    def test_the_induced_velocity_is_larger_at_the_rear(self):
        """The signature of every linear inflow model: the stream has
        been accelerated by the front of the disk before it reaches the
        back, so the rear sees more induced velocity."""
        for model in ("coleman_local", "pitt_peters_steady"):
            with self.subTest(model=model):
                maps = self.solve(config={"inflow_field_model": model},
                                   mu_x=0.25).maps
                psi = np.asarray(maps["PSI"], dtype=float)
                lam = np.asarray(maps["lambda_i"], dtype=float)
                row = psi[0] if psi.ndim > 1 else psi
                front = lam[:, int(np.argmin(np.abs(row - np.pi)))].mean()
                rear = lam[:, int(np.argmin(np.abs(row)))].mean()
                self.assertGreater(
                    rear, front,
                    f"{model}: the inflow is not larger at the rear of the "
                    f"disk, which is the gradient the model exists to add")


class TestPrandtlLosses(_Rotor):
    """A finite blade count cannot carry lift to the very tip."""

    def _loss(self, blades):
        off = self.thrust(config={"prandtl_loss_mode": "off"},
                          geometry={"n_blades": blades})
        on = self.thrust(config={"prandtl_loss_mode": "both"},
                         geometry={"n_blades": blades})
        return (on - off) / off

    def test_the_correction_lowers_the_thrust(self):
        self.assertLess(self._loss(2), 0.0)

    def test_more_blades_lose_less(self):
        """More blades approach the continuous actuator disk the
        correction measures the distance from."""
        self.assertGreater(self._loss(6), self._loss(2))

    def test_each_mode_removes_its_own_part(self):
        thrusts = {mode: self.thrust(config={"prandtl_loss_mode": mode})
                   for mode in ("off", "tip", "root", "both")}
        self.assertLess(thrusts["tip"], thrusts["off"])
        self.assertLess(thrusts["root"], thrusts["off"])
        self.assertLess(thrusts["both"], min(thrusts["tip"],
                                              thrusts["root"]))


class TestCollectiveAndStall(_Rotor):

    def test_thrust_rises_with_collective(self):
        thrusts = [self.thrust(collective_deg=t)
                   for t in (4.0, 8.0, 12.0, 16.0, 20.0)]
        self.assertTrue(all(b > a for a, b in zip(thrusts, thrusts[1:])))

    def test_the_rate_falls_toward_stall(self):
        """The saturation is the whole reason a stall model exists."""
        thrusts = [self.thrust(collective_deg=t)
                   for t in (4.0, 8.0, 16.0, 20.0)]
        first = thrusts[1] - thrusts[0]
        last = thrusts[3] - thrusts[2]
        self.assertLess(last, first)


class TestClimbAndDescent(_Rotor):
    """Momentum theory's own curve, and the sign convention with it."""

    def test_a_positive_vz_lowers_the_thrust(self):
        climb = self.thrust(Vz=-6.0)
        hover = self.thrust(Vz=0.0)
        descent = self.thrust(Vz=+6.0)
        self.assertGreater(climb, hover)
        self.assertGreater(hover, descent)

    def test_the_induced_velocity_falls_as_the_disk_is_pushed_through(self):
        values = [self.solve(Vz=v).summary["lambda_i"]
                  for v in (-6.0, -3.0, 0.0, 3.0, 6.0)]
        self.assertTrue(all(b < a for a, b in zip(values, values[1:])),
                         f"lambda_i did not fall monotonically: {values}")


class TestTabulatedPolarsUseReynoldsAndMach(unittest.TestCase):
    """A table carries slices at several Reynolds and Mach. Each radial
    station must pick the slice NEAREST to its own -- the root and the
    tip of one blade run at different Reynolds.

    `airfoils.build_table` states the limitation in its own docstring:
    the choice is nearest neighbour, not interpolation. That is checked
    too, so the limitation stays visible instead of quietly changing.
    """

    ALPHA = np.linspace(-20.0, 20.0, 21)

    @classmethod
    def setUpClass(cls):
        from dataclasses import asdict

        from zbemt import geometry as geometry_gen
        from zbemt.bemt import BEMTConfig

        cls.geometry = geometry_gen.generate_tapered(
            root_chord_norm=0.12, tip_chord_norm=0.06, twist_root_deg=8.0,
            twist_tip_deg=0.0, radius_m=1.0, n_stations=16)
        cls.config = asdict(BEMTConfig(Ne=16, Npsi=24,
                                        use_compressibility=False,
                                        prandtl_loss_mode="off"))

    def _polar(self, reynolds, mach, scale):
        from zbemt.models import PolarSlice

        return PolarSlice(
            reynolds=reynolds, mach=mach, alpha_deg=list(self.ALPHA),
            cl=list(scale * 0.11 * self.ALPHA),
            cd=list(0.01 + 0.0004 * self.ALPHA ** 2))

    def _thrust(self, slices, rpm):
        from zbemt.models import AirfoilDef, Project

        project = Project(
            name="t", geometry=self.geometry, config=self.config,
            airfoil=AirfoilDef(source="table", name="t",
                                table_slices=slices))
        return api.run_case(project, FlightCondition(
            name="c", mu_x=0.0, rpm=rpm, collective_deg=8.0)
        ).summary["Thrust"]

    def test_the_blade_spans_several_reynolds(self):
        """The premise. If the Reynolds barely varied along the blade,
        picking a slice per station would prove nothing."""
        from zbemt import airfoils, studies
        from zbemt.bemt import BEMTConfig

        rotor = studies._to_rotor(self.geometry, rpm=3000.0)
        cfg = BEMTConfig(**{k: v for k, v in self.config.items()
                             if k in BEMTConfig.__dataclass_fields__})
        _r, reynolds, _m = airfoils.radial_reynolds_mach(rotor, cfg, mu_x=0.0)
        self.assertGreater(reynolds.max(), 3.0 * reynolds.min())

    def test_each_station_picks_its_own_slice(self):
        from zbemt import airfoils, studies
        from zbemt.bemt import BEMTConfig
        from zbemt.models import AirfoilDef

        rotor = studies._to_rotor(self.geometry, rpm=3000.0)
        cfg = BEMTConfig(**{k: v for k, v in self.config.items()
                             if k in BEMTConfig.__dataclass_fields__})
        r_norms, reynolds, mach = airfoils.radial_reynolds_mach(
            rotor, cfg, mu_x=0.0)
        built = airfoils.build_table(
            AirfoilDef(source="table", name="t",
                        table_slices=[self._polar(4.0e5, 0.0, 1.0),
                                      self._polar(1.2e6, 0.0, 1.5)]),
            radial=(r_norms, reynolds, mach))
        alpha = np.radians(np.full((len(r_norms), 1), 10.0))
        cl, _cd = built.cl_cd(alpha, None, r_norm=r_norms[:, None])
        cl = np.asarray(cl, dtype=float).ravel()
        self.assertLess(
            cl.min(), cl.max(),
            "every station got the same lift, so the table's Reynolds "
            "axis is not reaching the blade")
        self.assertAlmostEqual(cl.min(), 1.0 * 0.11 * 10.0, places=6)
        self.assertAlmostEqual(cl.max(), 1.5 * 0.11 * 10.0, places=6)

    def test_the_reynolds_slice_reaches_the_forces(self):
        flat = self._thrust([self._polar(4.0e5, 0.0, 1.0),
                             self._polar(1.2e6, 0.0, 1.0)], rpm=3000.0)
        rising = self._thrust([self._polar(4.0e5, 0.0, 1.0),
                               self._polar(1.2e6, 0.0, 1.5)], rpm=3000.0)
        self.assertGreater(rising, flat * 1.01)

    def test_the_mach_slice_reaches_the_forces(self):
        flat = self._thrust([self._polar(1e6, 0.0, 1.0),
                             self._polar(1e6, 0.6, 1.0)], rpm=6000.0)
        losing = self._thrust([self._polar(1e6, 0.0, 1.0),
                               self._polar(1e6, 0.6, 0.6)], rpm=6000.0)
        self.assertLess(losing, flat * 0.99)

    def test_the_choice_snaps_rather_than_interpolating(self):
        """The documented limitation. It is pinned so that a change to
        real interpolation is a deliberate act with this test updated,
        not a silent one."""
        from zbemt import airfoils
        from zbemt.models import AirfoilDef

        built = airfoils.build_table(
            AirfoilDef(source="table", name="t",
                        table_slices=[self._polar(4.0e5, 0.0, 1.0),
                                      self._polar(1.2e6, 0.0, 1.5)]),
            reynolds=7.0e5, mach=0.0)
        cl, _cd = built.cl_cd(np.radians(np.array([[10.0]])), None)
        got = float(np.asarray(cl).ravel()[0])
        self.assertTrue(
            abs(got - 1.10) < 1e-6 or abs(got - 1.65) < 1e-6,
            f"Cl = {got}, which is neither tabulated value: the lookup "
            f"has started interpolating, and `build_table`'s docstring "
            f"still says it does not")


if __name__ == "__main__":   # pragma: no cover
    unittest.main()
