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


def _projeto_de_referencia(**cfg_overrides) -> Project:
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
    return Project(name="referencia", geometry=geom, airfoil=airfoil, config=cfg)


def _pairado(project, collective_deg=8.0, rpm=300.0):
    return studies.run_single_case(project, FlightCondition(
        name="pairado", mu_x=0.0, Vz=0.0, collective_deg=collective_deg, rpm=rpm))


def _ct_ideal_power(CT: float) -> float:
    """Minimum theoretical induced power in hover: ``CP_ideal =
    CT^1.5 / sqrt(2)``. No real rotor can go below this -- it is the
    cost of accelerating air with perfectly uniform inflow."""
    return CT ** 1.5 / np.sqrt(2.0)


class TestTeoriaDaQuantidadeDeMovimentoEmPairado(unittest.TestCase):
    """T1 -- in hover, each elementary ring must satisfy
    simultaneously the blade element theory and the momentum theory.
    This is the equation the BEMT solves; these tests check that
    the CONVERGED solution actually satisfies it, measured from the output."""

    @classmethod
    def setUpClass(cls):
        cls.project = _projeto_de_referencia()
        cls.res = _pairado(cls.project)

    def test_integral_de_momento_reproduz_a_tracao(self):
        """The central test. Thrust comes from integrating blade element forces
        (``Fn``); the induced velocity comes from the momentum balance.
        If the solution truly converged, integrating
        ``dCT = 4*lambda_i^2*r*dr`` over the disk must return the SAME
        CT -- the two sides of the equation the solver couples.

        This is not tautological: a factor, normalization, or
        integration error in `aggregate_results` would break the equality without
        preventing convergence."""
        lambda_i = self.res.maps["lambda_i"].mean(axis=1)   # média azimutal
        r_norm = self.res.maps["R_NORM"].mean(axis=1)

        CT_momento = 4.0 * np.trapezoid(lambda_i ** 2 * r_norm, r_norm)
        CT_elemento = self.res.summary["CT"]

        self.assertAlmostEqual(CT_momento / CT_elemento, 1.0, places=2,
                               msg=(f"momentum theory gives CT={CT_momento:.6f}, "
                                    f"blade element gives CT={CT_elemento:.6f} -- "
                                    "the two sides of the BEMT coupling diverged"))

    def test_inflow_medio_bate_com_a_teoria_de_momento(self):
        """For uniform inflow, ``lambda_i = sqrt(CT/2)``. A real blade
        doesn't have uniform inflow, so proximity is expected, not
        equality -- the deviation IS the non-uniformity."""
        CT = self.res.summary["CT"]
        lambda_teorico = np.sqrt(CT / 2.0)
        lambda_solver = float(self.res.maps["lambda_i"].mean())

        razao = lambda_solver / lambda_teorico
        self.assertGreater(razao, 0.90, f"inflow {razao:.3f}x o da teoria de momento")
        self.assertLess(razao, 1.15, f"inflow {razao:.3f}x o da teoria de momento")


class TestLimitesDeImpossibilidadeFisica(unittest.TestCase):
    """A solver can converge beautifully to a result that violates
    energy conservation. These tests block exactly that."""

    def test_figura_de_merito_nunca_passa_de_um_em_pairado(self):
        """``FM = CT^1.5 / (sqrt(2)*CP)`` compares power spent with the
        theoretical minimum. FM > 1 means producing thrust cheaper than the
        ideal limit -- impossible.

        Valid only in HOVER: in advanced flight the metric loses meaning and
        exceeds 1 routinely (see Q6 in production-plan.md), which
        is NOT a bug."""
        project = _projeto_de_referencia()
        for collective in (4.0, 6.0, 8.0, 10.0, 12.0):
            with self.subTest(collective_deg=collective):
                fm = _pairado(project, collective_deg=collective).summary["FM"]
                self.assertGreater(fm, 0.0, "negative FM makes no physical sense")
                self.assertLess(fm, 1.0,
                                f"FM={fm:.4f} > 1 em pairado: o rotor estaria "
                                "spending less than the ideal power")

    def test_potencia_induzida_nunca_fica_abaixo_da_ideal(self):
        """The same limit, isolated in the induced component (without profile drag,
        which only worsens the balance). The ratio ``kappa = CPi/CP_ideal``
        is the induced power factor: 1.0 would be perfectly uniform inflow,
        and values much above ~1.5 would indicate an implausible inflow field,
        not a bad rotor."""
        project = _projeto_de_referencia()
        for collective in (6.0, 8.0, 10.0):
            with self.subTest(collective_deg=collective):
                s = _pairado(project, collective_deg=collective).summary
                kappa = s["CPi"] / _ct_ideal_power(s["CT"])
                self.assertGreaterEqual(kappa, 1.0,
                    f"kappa={kappa:.4f} < 1: induced power below the theoretical minimum")
                self.assertLess(kappa, 1.5, f"kappa={kappa:.4f} implausivelmente alto")


class TestLimiteDeGlauertEmVooAvancado(unittest.TestCase):
    """T2 -- in fast advanced flight, the rotor acts like a circular wing and
    the induced velocity tends to ``lambda_i -> CT/(2*mu_x)``
    (Glauert). The approximation holds when ``mu_x >> lambda_i``, so it must
    appear at intermediate/high mu_x."""

    @classmethod
    def setUpClass(cls):
        cls.project = _projeto_de_referencia()
        cls.mus = (0.1, 0.2, 0.3, 0.5)
        cls.resultados = [
            studies.run_single_case(cls.project, FlightCondition(
                name=f"mu_{mu_x:g}", mu_x=mu_x, Vz=0.0, collective_deg=8.0, rpm=300.0))
            for mu_x in cls.mus
        ]

    def _razao_glauert(self, res, mu_x):
        """1.0 = perfect agreement with Glauert."""
        return float(res.maps["lambda_i"].mean()) * 2.0 * mu_x / res.summary["CT"]

    def test_converge_para_glauert_conforme_mu_cresce(self):
        """The ratio must APPROACH 1 as mu_x grows -- it is this
        trend, not a value at one point, that validates the model."""
        erros = [abs(self._razao_glauert(r, mu_x) - 1.0)
                 for r, mu_x in zip(self.resultados, self.mus)]
        self.assertLess(erros[1], erros[0], "mu_x=0.2 did not improve over mu_x=0.1")
        self.assertLess(erros[2], erros[1], "mu_x=0.3 did not improve over mu_x=0.2")

    def test_concorda_com_glauert_no_mu_intermediario(self):
        """At mu_x=0.3, well within the validity regime, the agreement
        must be good. 15% tolerance covers what the average over the
        disk loses by not being the uniform inflow that Glauert assumes."""
        razao = self._razao_glauert(self.resultados[2], 0.3)
        self.assertAlmostEqual(razao, 1.0, delta=0.15,
                               msg=f"measured lambda_i is {razao:.3f}x that of Glauert")

    def test_inflow_cai_quando_o_avanco_cresce(self):
        """Classic signature of advanced flight: the same thrust is
        sustained by a smaller induced velocity, because the rotor
        processes much more air mass per second."""
        inflows = [float(r.maps["lambda_i"].mean()) for r in self.resultados]
        self.assertEqual(inflows, sorted(inflows, reverse=True),
                         f"lambda_i deveria cair monotonicamente com mu_x: {inflows}")


class TestPerdaDePontaDePrandtl(unittest.TestCase):
    """T5 (first line) -- tip loss had only the default value
    locked in a test; nothing checked that ENABLING does what it should."""

    def test_ligar_reduz_a_tracao_e_o_carregamento_na_ponta(self):
        """The Prandtl correction models the pressure leakage at the tip:
        circulation must drop to zero there. Enabling must reduce both
        total thrust and, concentrated at the tip, the load near the
        tip."""
        sem = _pairado(_projeto_de_referencia(prandtl_loss_mode="off"))
        com = _pairado(_projeto_de_referencia(prandtl_loss_mode="both"))

        self.assertLess(com.summary["CT"], sem.summary["CT"],
                        "tip loss should reduce the total thrust")

        # load normalized by radial station, azimuthal average
        def carga_na_ponta(res):
            fn = res.maps["Fn"].mean(axis=1)
            r_norm = res.maps["R_NORM"].mean(axis=1)
            ponta = r_norm > 0.95
            return fn[ponta].sum() / fn.sum()

        self.assertLess(carga_na_ponta(com), carga_na_ponta(sem),
                        "a queda deveria se concentrar perto da ponta, "
                        "not be a uniform cut")


if __name__ == "__main__":
    unittest.main()
