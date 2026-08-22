"""
test_physics_validation.py
===========================

PHYSICAL validation of the solver against theory, not against itself.

The rest of the suite checks monotonicity ("more collective -> more thrust"),
dimensionless identities (``J_x = pi*mu_x``, which hold whether the physics
is correct or wrong) and ranges recorded from previous runs. None of this
proves that the NUMBERS are correct -- only that they haven't changed.

Here the references are external to the code: momentum theory, the Glauert
limit in advanced flight, and limits of physical impossibility. A test
failing here means the solver is wrong, not that a default changed.

Items T1 and T2 of production-plan.md.
"""

import unittest

import numpy as np

from zbemt import api, geometry, studies
from zbemt.models import AirfoilDef, FlightCondition, Project


def _reference_project(**cfg_overrides) -> Project:
    """Clean rotor to compare against theory: tip loss and
    compressibility DISABLED, linear analytical polar without stall.

    Each of these options is a deliberate departure from ideal theory --
    Prandtl loss exists precisely to model what momentum theory doesn't see.
    Enabling them here would mix the solver error with the effect being modeled."""
    geom = geometry.generate_tapered(
        root_chord_norm=0.10, tip_chord_norm=0.05,
        twist_root_deg=14.0, twist_tip_deg=2.0,
        root_cutout_norm=0.15, radius_m=5.0, n_blades=4, n_stations=20)
    airfoil = AirfoilDef(source="analytical", stall_model="linear",
                         extend_full_range=False, cd0=0.010, k=0.0)
    cfg = dict(Ne=60, Npsi=32, prandtl_loss_mode="off",
               use_compressibility=False, use_rotational_augmentation=False,
               solver="newton", max_iter=200)
    cfg.update(cfg_overrides)
    return Project(name="reference", geometry=geom, airfoil=airfoil, config=cfg)


def _hover(project, collective_deg=8.0, rpm=300.0):
    return studies.run_single_case(project, FlightCondition(
        name="hover", mu_x=0.0, Vz=0.0, collective_deg=collective_deg, rpm=rpm))


def _ct_ideal_power(CT: float) -> float:
    """Minimum theoretical induced power in hover: ``CP_ideal =
    CT^1.5 / sqrt(2)``. No real rotor can go below this -- it is the
    cost of accelerating air with perfectly uniform inflow."""
    return CT ** 1.5 / np.sqrt(2.0)


class TestMomentumTheoryInHover(unittest.TestCase):
    """T1 -- in hover, each elementary ring must satisfy
    simultaneously the blade element theory and the momentum theory.
    This is the equation the BEMT solves; these tests check that
    the CONVERGED solution actually satisfies it, measured from the output."""

    @classmethod
    def setUpClass(cls):
        cls.project = _reference_project()
        cls.res = _hover(cls.project)

    def test_momentum_integral_reproduces_the_thrust(self):
        """The central test. Thrust comes from integrating blade element forces
        (``Fn``); the induced velocity comes from the momentum balance.
        If the solution truly converged, integrating
        ``dCT = 4*lambda_i^2*r*dr`` over the disk must return the SAME
        CT -- the two sides of the equation the solver couples.

        This is not tautological: a factor, normalization, or
        integration error in `aggregate_results` would break the equality without
        preventing convergence."""
        lambda_i = self.res.maps["lambda_i"].mean(axis=1)   # azimuthal mean
        r_norm = self.res.maps["R_NORM"].mean(axis=1)

        CT_momentum = 4.0 * np.trapezoid(lambda_i ** 2 * r_norm, r_norm)
        CT_element = self.res.summary["CT"]

        self.assertAlmostEqual(CT_momentum / CT_element, 1.0, places=2,
                               msg=(f"momentum theory gives CT={CT_momentum:.6f}, "
                                    f"blade element gives CT={CT_element:.6f} -- "
                                    "the two sides of the BEMT coupling diverged"))

    def test_mean_inflow_matches_momentum_theory(self):
        """For uniform inflow, ``lambda_i = sqrt(CT/2)``. A real blade
        doesn't have uniform inflow, so proximity is expected, not
        equality -- the deviation IS the non-uniformity."""
        CT = self.res.summary["CT"]
        lambda_theory = np.sqrt(CT / 2.0)
        lambda_solver = float(self.res.maps["lambda_i"].mean())

        ratio = lambda_solver / lambda_theory
        self.assertGreater(ratio, 0.90, f"inflow {ratio:.3f}x the momentum theory one")
        self.assertLess(ratio, 1.15, f"inflow {ratio:.3f}x the momentum theory one")


class TestLimitsOfPhysicalImpossibility(unittest.TestCase):
    """A solver can converge beautifully to a result that violates
    energy conservation. These tests block exactly that."""

    def test_figure_of_merit_never_exceeds_one_in_hover(self):
        """``FM = CT^1.5 / (sqrt(2)*CP)`` compares power spent with the
        theoretical minimum. FM > 1 means producing thrust cheaper than the
        ideal limit -- impossible.

        Valid only in HOVER: in advanced flight the metric loses meaning and
        exceeds 1 routinely (see Q6 in production-plan.md), which
        is NOT a bug."""
        project = _reference_project()
        for collective in (4.0, 6.0, 8.0, 10.0, 12.0):
            with self.subTest(collective_deg=collective):
                fm = _hover(project, collective_deg=collective).summary["FM"]
                self.assertGreater(fm, 0.0, "negative FM makes no physical sense")
                self.assertLess(fm, 1.0,
                                f"FM={fm:.4f} > 1 in hover: the rotor would be "
                                "spending less than the ideal power")

    def test_induced_power_never_goes_below_the_ideal(self):
        """The same limit, isolated in the induced component (without profile drag,
        which only worsens the balance). The ratio ``kappa = CPi/CP_ideal``
        is the induced power factor: 1.0 would be perfectly uniform inflow,
        and values much above ~1.5 would indicate an implausible inflow field,
        not a bad rotor."""
        project = _reference_project()
        for collective in (6.0, 8.0, 10.0):
            with self.subTest(collective_deg=collective):
                s = _hover(project, collective_deg=collective).summary
                kappa = s["CPi"] / _ct_ideal_power(s["CT"])
                self.assertGreaterEqual(kappa, 1.0,
                    f"kappa={kappa:.4f} < 1: induced power below the theoretical minimum")
                self.assertLess(kappa, 1.5, f"kappa={kappa:.4f} implausibly high")


class TestGlauertLimitInAdvancedFlight(unittest.TestCase):
    """T2 -- in fast advanced flight, the rotor acts like a circular wing and
    the induced velocity tends to ``lambda_i -> CT/(2*mu_x)``
    (Glauert). The approximation holds when ``mu_x >> lambda_i``, so it must
    appear at intermediate/high mu_x."""

    @classmethod
    def setUpClass(cls):
        cls.project = _reference_project()
        cls.mus = (0.1, 0.2, 0.3, 0.5)
        cls.results = [
            studies.run_single_case(cls.project, FlightCondition(
                name=f"mu_{mu_x:g}", mu_x=mu_x, Vz=0.0, collective_deg=8.0, rpm=300.0))
            for mu_x in cls.mus
        ]

    def _glauert_ratio(self, res, mu_x):
        """1.0 = perfect agreement with Glauert."""
        return float(res.maps["lambda_i"].mean()) * 2.0 * mu_x / res.summary["CT"]

    def test_converges_to_glauert_as_mu_grows(self):
        """The ratio must APPROACH 1 as mu_x grows -- it is this
        trend, not a value at one point, that validates the model."""
        errors = [abs(self._glauert_ratio(r, mu_x) - 1.0)
                  for r, mu_x in zip(self.results, self.mus)]
        self.assertLess(errors[1], errors[0], "mu_x=0.2 did not improve over mu_x=0.1")
        self.assertLess(errors[2], errors[1], "mu_x=0.3 did not improve over mu_x=0.2")

    def test_agrees_with_glauert_at_the_intermediate_mu(self):
        """At mu_x=0.3, well within the validity regime, the agreement
        must be good. 15% tolerance covers what the average over the
        disk loses by not being the uniform inflow that Glauert assumes."""
        ratio = self._glauert_ratio(self.results[2], 0.3)
        self.assertAlmostEqual(ratio, 1.0, delta=0.15,
                               msg=f"measured lambda_i is {ratio:.3f}x that of Glauert")

    def test_inflow_drops_as_advance_grows(self):
        """Classic signature of advanced flight: the same thrust is
        sustained by a smaller induced velocity, because the rotor
        processes much more air mass per second."""
        inflows = [float(r.maps["lambda_i"].mean()) for r in self.results]
        self.assertEqual(inflows, sorted(inflows, reverse=True),
                         f"lambda_i should drop monotonically with mu_x: {inflows}")


class TestPrandtlTipLoss(unittest.TestCase):
    """T5 (first line) -- tip loss had only the default value
    locked in a test; nothing checked that ENABLING does what it should."""

    def test_enabling_reduces_thrust_and_tip_loading(self):
        """The Prandtl correction models the pressure leakage at the tip:
        circulation must drop to zero there. Enabling must reduce both
        total thrust and, concentrated at the tip, the load near the
        tip."""
        without = _hover(_reference_project(prandtl_loss_mode="off"))
        with_loss = _hover(_reference_project(prandtl_loss_mode="both"))

        self.assertLess(with_loss.summary["CT"], without.summary["CT"],
                        "tip loss should reduce the total thrust")

        # load normalized by radial station, azimuthal average
        def tip_load(res):
            fn = res.maps["Fn"].mean(axis=1)
            r_norm = res.maps["R_NORM"].mean(axis=1)
            tip = r_norm > 0.95
            return fn[tip].sum() / fn.sum()

        self.assertLess(tip_load(with_loss), tip_load(without),
                        "the drop should concentrate near the tip, "
                        "not be a uniform cut")


if __name__ == "__main__":
    unittest.main()
