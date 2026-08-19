"""
test_physics_toggles.py
========================

T5 from production-plan.md -- each physical toggle of the engine only had
its DEFAULT value locked down in one test (`test_bemt.py`); nothing
verified that TURNING ON the toggle produces the expected physical effect.
Prandtl tip loss already had this kind of test (`TestPerdaDePontaDePrandtl`
in `test_physics_validation.py`); this file covers the four that were
missing: compressibility, inflow field models, reverse flow and dynamic
stall.

As in test_physics_validation.py, the references here are external to
the code (Prandtl-Glauert formula, geometry of the reverse flow region
derived from the engine's own kinematic equations) or necessary internal
properties (harmonic models must coincide in hover, where there is no
harmonic to solve at all).
"""

import unittest

import numpy as np

from zbemt import geometry, studies
from zbemt.bemt import AnalyticalAirfoil, BEMTConfig, Rotor, element_state, solve_bemt
from zbemt.models import AirfoilDef, FlightCondition, Project


# =============================================================================
# Helpers
# =============================================================================

def _rotor_para_estol(n_stations=40) -> Rotor:
    """Blade with collective high enough to touch stall over part of
    the disk in forward flight (but not in hover), with no stall at mu_x=0."""
    geom = geometry.generate_tapered(
        root_chord_norm=0.10, tip_chord_norm=0.06,
        twist_root_deg=6.0, twist_tip_deg=6.0,
        root_cutout_norm=0.15, radius_m=5.0, n_blades=2,
        n_stations=n_stations)
    return geom


def _projeto(geom=None, cfg_overrides=None, airfoil=None) -> Project:
    if geom is None:
        geom = geometry.generate_tapered(
            root_chord_norm=0.10, tip_chord_norm=0.05,
            twist_root_deg=14.0, twist_tip_deg=2.0,
            root_cutout_norm=0.15, radius_m=5.0, n_blades=4, n_stations=32)
    if airfoil is None:
        airfoil = AirfoilDef(source="analytical", stall_model="linear",
                              extend_full_range=False, cd0=0.010, k=0.0)
    cfg = dict(Ne=40, Npsi=32, prandtl_loss_mode="off",
               use_compressibility=False, use_rotational_augmentation=False,
               solver="newton", max_iter=200)
    if cfg_overrides:
        cfg.update(cfg_overrides)
    return Project(name="toggle", geometry=geom, airfoil=airfoil, config=cfg)


def _run(project, mu_x=0.0, collective_deg=8.0, rpm=300.0, Vz=0.0):
    return studies.run_single_case(project, FlightCondition(
        name=f"mu_{mu_x:g}", mu_x=mu_x, Vz=Vz, collective_deg=collective_deg, rpm=rpm))


# =============================================================================
# 1) Compressibility -- Prandtl-Glauert correction on Cl/Cd
# =============================================================================

class TestCompressibilidade(unittest.TestCase):
    """`use_compressibility` scales Cl (and Cd) by ``1/sqrt(1-M^2)``
    (bemt.py, block right after the Cl/Cd computation in `element_state`).
    Tested by calling `element_state` directly with lambda_i=0 fixed
    (without running the iterative solver): this isolates the formula from
    the indirect feedback effect -- a higher Cl would produce more thrust,
    more induced velocity and therefore a different alpha_eff at the output
    of a full `solve_bemt`, which would mix the Prandtl-Glauert effect with
    the BEMT's own rebalancing."""

    def _estado(self, use_compressibility, Omega=220.0, alpha_deg=5.0):
        R = 1.0
        R_NORM = np.array([[0.9]])
        PSI = np.array([[0.0]])
        R_DIM = R_NORM * R
        CHORD = np.array([[0.08]])
        THETA = np.array([[np.deg2rad(alpha_deg)]])  # Up=0 (lambda_i=0) => alpha_eff=THETA
        lambda_i = np.array([[0.0]])
        airfoil = AnalyticalAirfoil(cl_alpha=2 * np.pi, alpha0_deg=0.0, stall_model="linear")
        cfg = BEMTConfig(reverse_flow_model="flat_plate", prandtl_loss_mode="off",
                          use_compressibility=use_compressibility)
        OmegaR = Omega * R
        return element_state(lambda_i, R_NORM, PSI, R_DIM, CHORD, THETA,
                              mu_x=0.0, lambda_z=0.0, Nb=2, Omega=Omega, OmegaR=OmegaR,
                              airfoil=airfoil, cfg=cfg,
                              r_root_norm_geom=0.15, r_tip_norm_geom=1.0)

    def test_ligar_aumenta_cl_conforme_prandtl_glauert(self):
        off = self._estado(False)
        on = self._estado(True)

        mach = float(off["Mach"][0, 0])
        self.assertGreater(mach, 0.3, "test case needs Mach high enough for the effect to be measurable")

        beta = np.sqrt(1.0 - mach ** 2)
        cl_off = float(off["Cl"][0, 0])
        cl_on_esperado = cl_off / beta
        cl_on = float(on["Cl"][0, 0])

        self.assertAlmostEqual(cl_on / cl_on_esperado, 1.0, places=9,
                               msg=f"Cl com compressibilidade={cl_on:.6f}, "
                                   f"esperado Cl/beta={cl_on_esperado:.6f} (Mach={mach:.3f})")
        self.assertGreater(cl_on, cl_off, "ligar compressibilidade deveria aumentar Cl (beta<1)")

    def test_mach_baixo_efeito_e_desprezivel(self):
        """Negative control: at low Mach, beta~1 and the correction should
        nearly vanish -- confirms that the test above is measuring the
        Mach effect, not some artifact of the call."""
        off = self._estado(False, Omega=10.0)
        on = self._estado(True, Omega=10.0)
        mach = float(off["Mach"][0, 0])
        self.assertLess(mach, 0.05)
        cl_off = float(off["Cl"][0, 0])
        cl_on = float(on["Cl"][0, 0])
        self.assertAlmostEqual(cl_on / cl_off, 1.0, delta=0.01)


# =============================================================================
# 2) Inflow field models -- coleman_local vs drees_global vs
#    pitt_peters_steady
# =============================================================================

class TestModelosDeInflow(unittest.TestCase):
    """The three models solve the SAME momentum equation; what changes is
    the harmonic correction (Kx,Ky) that distributes the inflow along the
    azimuth. In hover (mu_x=0) this correction is null by construction
    (`_inflow_harmonics` depends on mu_x) for the harmonic models, and
    steady Pitt-Peters, with no relevant CMx/CMy forcing in axisymmetric
    flow, converges to the same nu0 -- the three should nearly coincide.
    In forward flight, each one uses a different law for the wake
    angle/harmonics, so the longitudinal (fore x aft) distribution
    diverges -- and diverges MORE the greater the advance ratio."""

    def _fore_aft_asymmetry(self, res):
        """Difference between the average inflow at the fore (cos(psi)>0)
        and the aft (cos(psi)<0) of the disk -- the signature of the
        longitudinal distribution that Coleman and Drees compute
        differently."""
        lam = res.maps["lambda_i"]
        psi = res.maps["PSI"]
        fore = lam[np.cos(psi) > 0].mean()
        aft = lam[np.cos(psi) < 0].mean()
        return float(fore - aft)

    def test_pairado_modelos_quase_coincidem(self):
        cts = {}
        for model in ("coleman_local", "drees_global", "pitt_peters_steady"):
            project = _projeto(cfg_overrides=dict(inflow_field_model=model))
            cts[model] = _run(project, mu_x=0.0).summary["CT"]
        values = list(cts.values())
        spread = (max(values) - min(values)) / max(abs(np.mean(values)), 1e-9)
        self.assertLess(spread, 0.02,
                        f"modelos de inflow deveriam quase coincidir em pairagem: {cts}")

    def test_pairado_com_pitt_peters_nao_diverge(self):
        """Regression: at EXACT ``mu_x=0``, `pitt_peters_steady` used to
        silently return ``CT=nan`` -- no exception and no warning.

        Mechanism (see `DENOMINADOR_MINIMO_DE_PITT_PETERS` and the seed in
        `_solve_pitt_peters_steady`): starting from ``nu=0`` in hover,
        ``VT=sqrt(mu_x^2+lambda^2)`` is zero, the first ``forcing/V``
        blows up and ``nu0`` jumps to ~355 (against ~0.12 of the actual
        solution); on the way back from that jump the iteration passes
        through ``lambda<0``, where ``alpha*=-90°`` makes the L gain
        matrix singular. Two of the three divisions by
        ``(1+sin alpha*)`` had no guard -> inf -> NaN. Only with the
        guard does the NaN turn into divergence to ~1e150 (worse: it
        looks like a number); the momentum-theory seed is what actually
        fixes it.

        This class's synthetic `_projeto` does NOT reproduce the defect
        (rpm=300, R=5m: low disk loading, the overshoot never reaches
        lambda<0), which is why `test_pairado_modelos_quase_coincidem`
        used to pass with the bug present. Hence this test using the
        real `starter_rotor`.

        The strong assertion is CONTINUITY as mu_x -> 0: it catches both
        the NaN and the silent divergence, which an `isfinite` alone
        would not catch."""
        import os
        from zbemt import api

        caminho = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            "projects", "starter_rotor")
        if not os.path.isdir(caminho):
            self.skipTest("starter_rotor project is not present in this checkout")

        def _ct(mu_x):
            projeto = api.open_project(caminho)
            projeto.config.update(Ne=40, Npsi=72,
                                   inflow_field_model="pitt_peters_steady")
            return api.run_case(projeto, FlightCondition(
                name=f"mu_{mu_x:g}", mu_x=mu_x, Vz=0.0,
                collective_deg=8.0, rpm=1200.0)).summary["CT"]

        ct_pairado = _ct(0.0)
        self.assertTrue(np.isfinite(ct_pairado),
                        f"CT in hover is not finite: {ct_pairado}")
        ct_quase = _ct(0.001)
        self.assertAlmostEqual(
            ct_pairado, ct_quase, places=3,
            msg=(f"CT should be continuous at mu_x->0: "
                 f"mu_x=0 -> {ct_pairado}, mu_x=0.001 -> {ct_quase}"))

    def test_voo_avancado_modelos_divergem_mensuravelmente(self):
        """Measured first (not copied from theory): the coleman-drees
        difference does NOT grow monotonically over the whole mu_x range
        -- it grows from mu_x=0.05 to ~0.1, and then goes BACK down,
        nearly reconverging around mu_x=0.3 (a finding, not expected a
        priori; see report). What can be stated safely, and is what this
        test verifies, is more modest: in moderate forward flight the two
        models diverge MUCH more than in hover (where the difference is
        ~0 by construction, see `test_pairado_modelos_quase_coincidem`)."""
        asym = {}
        for model in ("coleman_local", "drees_global"):
            project = _projeto(cfg_overrides=dict(inflow_field_model=model))
            res = _run(project, mu_x=0.15)
            asym[model] = self._fore_aft_asymmetry(res)
        diff = abs(asym["coleman_local"] - asym["drees_global"])
        self.assertGreater(diff, 5e-3,
                            f"coleman e drees deveriam divergir mensuravelmente em mu_x=0.15: {asym}")


# =============================================================================
# 3) Reverse flow -- location of the region on the disk
# =============================================================================

class TestFluxoReverso(unittest.TestCase):
    """Where ``Ut = Omega*r + Vinf*sin(psi) < 0``. Dividing by
    Omega*R: ``r_norm < -mu_x*sin(psi)``, a condition only satisfied
    for sin(psi)<0 (psi between 180 and 360 degrees, retreating side)
    and with r_norm at most mu_x (reached at psi=270 degrees). This is
    the boundary curve derived directly from the engine's kinematics
    (not a published value) -- the tests below check that the region
    the engine actually marks as reverse (Ut<0) respects this curve,
    for both reverse flow models."""

    def _mapas(self, reverse_flow_model, mu_x=0.35):
        geom = _rotor_para_estol()
        airfoil = AirfoilDef(source="analytical", stall_model="linear",
                              extend_full_range=(reverse_flow_model == "viterna_full_range"),
                              cd0=0.010, k=0.0)
        cfg_overrides = dict(reverse_flow_model=reverse_flow_model)
        project = _projeto(geom=geom, airfoil=airfoil, cfg_overrides=cfg_overrides)
        return _run(project, mu_x=mu_x, collective_deg=6.0).maps

    def _checa_regiao(self, maps, mu_x):
        Ut = maps["Ut"]
        r_norm = maps["R_NORM"]
        psi = maps["PSI"]
        reverse = Ut < 0.0
        self.assertTrue(reverse.any(), "a reverse-flow region should exist at mu_x=0.35")

        psi_reverse = psi[reverse]
        # every reverse point has to be on the retreating side (sin(psi)<0)
        self.assertTrue(np.all(np.sin(psi_reverse) < 0),
                        "reverse-flow region outside the retreating side (sin(psi)>=0)")

        r_reverse = r_norm[reverse]
        # theoretical boundary curve: r_norm <= -mu_x*sin(psi) (tolerance = 1
        # radial mesh step, since the grid is discrete and Ut is sampled, not
        # interpolated at the exact boundary)
        dr = 1.0 / maps["r_norm_nodes"].size
        limite = -mu_x * np.sin(psi_reverse)
        self.assertTrue(np.all(r_reverse <= limite + 2 * dr),
                        "ponto de fluxo reverso fora da curva-limite r_norm<=-mu_x*sin(psi)")

        # maximum radius of the reverse region has to approach mu_x (reached
        # near psi=270 degrees)
        r_max = float(r_reverse.max())
        self.assertAlmostEqual(r_max, mu_x, delta=3 * dr,
                               msg=f"max reverse-flow radius={r_max:.4f}, expected ~mu_x={mu_x}")

    def test_regiao_no_lugar_certo_flat_plate(self):
        self._checa_regiao(self._mapas("flat_plate"), mu_x=0.35)

    def test_regiao_no_lugar_certo_viterna_full_range(self):
        self._checa_regiao(self._mapas("viterna_full_range"), mu_x=0.35)

    def test_diametro_da_regiao_escala_com_mu(self):
        """The boundary curve predicts maximum radius ~mu_x -- confirms
        the scaling by varying mu_x, not just a single fixed point."""
        for mu_x in (0.2, 0.4):
            with self.subTest(mu_x=mu_x):
                maps = self._mapas("flat_plate", mu_x=mu_x)
                r_reverse = maps["R_NORM"][maps["Ut"] < 0.0]
                r_max = float(r_reverse.max())
                dr = 1.0 / maps["r_norm_nodes"].size
                self.assertAlmostEqual(r_max, mu_x, delta=3 * dr)


# =============================================================================
# 4) Dynamic stall -- deviation grows with the AoA rate of change
# =============================================================================

class TestEstolDinamico(unittest.TestCase):
    """The Øye model delays boundary-layer separation relative to the
    static polar; the deviation Cl_dynamic - Cl_static should grow when
    the angle of attack varies faster along the azimuth -- and more
    advance ratio (larger mu_x) produces more azimuthal variation of
    alpha (Ut oscillates with sin(psi), amplitude proportional to mu_x)."""

    def _desvio_medio(self, mu_x, collective_deg=11.0):
        """Average deviation |Cl-Cl_static|, restricted to the DIRECT flow
        side (Ut>=0): the reverse flow region (radius ~mu_x, see
        TestFluxoReverso) produces extreme effective angles with this
        'clip' stall airfoil (not extended to -180..180), which would
        contaminate the average with no relation at all to the azimuthal
        rate of change being measured here."""
        geom = _rotor_para_estol()
        airfoil = AirfoilDef(source="analytical", stall_model="clip",
                              alpha_stall_pos_deg=10.0, alpha_stall_neg_deg=-6.0,
                              extend_full_range=False, cd0=0.010, k=0.0,
                              use_dynamic_stall=True, dynamic_stall_A=8.0)
        project = _projeto(geom=geom, airfoil=airfoil,
                           cfg_overrides=dict(use_dynamic_stall=True))
        res = _run(project, mu_x=mu_x, collective_deg=collective_deg)
        self.assertIn("Cl_static", res.maps, "dynamic stall should have run (Cl_static missing)")
        mask = res.maps["Ut"] >= 0.0
        return float(np.mean(np.abs(res.maps["Cl"][mask] - res.maps["Cl_static"][mask])))

    def test_desvio_cresce_com_mu(self):
        """Measured: 0.0045 (mu_x=0.03) -> 0.0158 (mu_x=0.06) -> 0.0640
        (mu_x=0.10), clear monotonic growth in this range (larger mu_x
        saturates/reverses because of the growing reverse flow region
        and the 'clip' saturating -- which is why the range is restricted
        to mu_x where the reverse region is still negligible,
        r_root_cutout=0.15 > mu_x)."""
        d1 = self._desvio_medio(mu_x=0.03)
        d2 = self._desvio_medio(mu_x=0.06)
        d3 = self._desvio_medio(mu_x=0.10)
        self.assertGreater(d1, 1e-4, "there should already be some dynamic-stall deviation at mu_x=0.03")
        self.assertGreater(d2, d1, f"desvio deveria crescer de mu_x=0.03 pra 0.06: {d1:.6f} -> {d2:.6f}")
        self.assertGreater(d3, d2, f"desvio deveria crescer de mu_x=0.06 pra 0.10: {d2:.6f} -> {d3:.6f}")


if __name__ == "__main__":
    unittest.main()
