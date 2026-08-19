"""The FIVE reverse flow models: effective angle formula, real effect on the
engine and fidelity of the Airfoil tab's polar preview.

Reason for this file: the models act in TWO places --
`bemt.reverse_flow_alpha_eff` (angle at which the polar is queried) and
`bemt.apply_reverse_flow_to_polar` (Cl/Cd post-processing) -- and the
preview only called the second. Consequence: choosing `viterna_full_range`
or `alpha_blending` changed NOTHING in the plot, even though it changed what
the engine calculated -- exactly the "some do not modify the plot, but modify
the modeling?" from the report.
"""
import unittest

import numpy as np

from zbemt import airfoils
from zbemt.bemt import (BEMTConfig, reverse_flow_alpha_eff,
                         apply_reverse_flow_to_polar, UT_NORMALIZADO_DE_PREVIA)
from zbemt.models import AirfoilDef

_MODELOS = ("simple_flip", "flat_plate", "alpha_blending",
            "thin_plate_blend", "viterna_full_range")


class TestAlphaEfetivoPorModelo(unittest.TestCase):
    """Formula by model, written here independently of the code -- it is the
    contract that the refactoring (extract the function from inside
    `element_state`) had to preserve."""

    def setUp(self):
        self.alpha = np.deg2rad(np.array([-20.0, -5.0, 0.0, 5.0, 20.0]))
        self.reverse = np.array([True, True, True, True, True])
        self.direto = np.zeros(self.alpha.shape, dtype=bool)

    def _cfg(self, modelo, **kw):
        return BEMTConfig(reverse_flow_model=modelo, **kw)

    def test_simple_flip_e_flat_plate_espelham_a_incidencia(self):
        for modelo in ("simple_flip", "flat_plate"):
            with self.subTest(modelo=modelo):
                obtido = reverse_flow_alpha_eff(self.alpha, self.reverse, self._cfg(modelo))
                np.testing.assert_allclose(obtido, -self.alpha)

    def test_viterna_full_range_nao_espelha_nada(self):
        obtido = reverse_flow_alpha_eff(self.alpha, self.reverse,
                                        self._cfg("viterna_full_range"))
        np.testing.assert_allclose(obtido, self.alpha)

    def test_viterna_full_range_enrola_para_dentro_de_180(self):
        alpha = np.deg2rad(np.array([200.0, -200.0]))
        obtido = np.rad2deg(reverse_flow_alpha_eff(
            alpha, np.array([False, False]), self._cfg("viterna_full_range")))
        np.testing.assert_allclose(obtido, [-160.0, 160.0], atol=1e-9)

    def test_thin_plate_blend_nao_toca_no_angulo(self):
        obtido = reverse_flow_alpha_eff(self.alpha, self.reverse,
                                        self._cfg("thin_plate_blend"))
        np.testing.assert_allclose(obtido, self.alpha)

    def test_alpha_blending_usa_o_tanh_do_ut_normalizado(self):
        k = 5.0
        ut_norm = np.full(self.alpha.shape, -0.3)
        obtido = reverse_flow_alpha_eff(self.alpha, self.reverse,
                                        self._cfg("alpha_blending", reverse_flow_blend_factor=k),
                                        ut_norm=ut_norm)
        np.testing.assert_allclose(obtido, self.alpha * np.tanh(k * -0.3))

    def test_alpha_blending_sem_ut_assume_o_limite_da_previa(self):
        k = 5.0
        obtido = reverse_flow_alpha_eff(
            self.alpha, self.reverse,
            self._cfg("alpha_blending", reverse_flow_blend_factor=k))
        np.testing.assert_allclose(
            obtido, self.alpha * np.tanh(k * UT_NORMALIZADO_DE_PREVIA))

    def test_fora_da_regiao_reversa_nenhum_modelo_mexe_no_angulo(self):
        for modelo in _MODELOS:
            with self.subTest(modelo=modelo):
                obtido = reverse_flow_alpha_eff(self.alpha, self.direto, self._cfg(modelo))
                np.testing.assert_allclose(obtido, self.alpha, atol=1e-12)

    def test_modelo_desconhecido_falha_alto(self):
        with self.assertRaises(ValueError):
            reverse_flow_alpha_eff(self.alpha, self.reverse, self._cfg("inexistente"))


class TestPosProcessamentoDaPolar(unittest.TestCase):
    """The other half: what each model does with already-queried Cl/Cd."""

    def setUp(self):
        self.alpha = np.deg2rad(np.array([5.0, 10.0]))
        self.cl = np.array([0.5, 1.0])
        self.cd = np.array([0.01, 0.02])
        self.reverse = np.array([True, True])

    def test_flat_plate_zera_cl_e_impoe_placa_plana(self):
        cl, cd = apply_reverse_flow_to_polar(
            self.cl, self.cd, self.alpha, self.reverse,
            BEMTConfig(reverse_flow_model="flat_plate"))
        np.testing.assert_allclose(cl, 0.0)
        np.testing.assert_allclose(cd, 1.9)

    def test_viterna_e_alpha_blending_nao_pos_processam(self):
        for modelo in ("viterna_full_range", "alpha_blending"):
            with self.subTest(modelo=modelo):
                cl, cd = apply_reverse_flow_to_polar(
                    self.cl, self.cd, self.alpha, self.reverse,
                    BEMTConfig(reverse_flow_model=modelo))
                np.testing.assert_allclose(cl, self.cl)
                np.testing.assert_allclose(cd, self.cd)


class TestPreviaRefleteOModelo(unittest.TestCase):
    """The Airfoil tab's preview draws what the engine consumes -- for all
    FIVE models, not just the three that post-process Cl/Cd."""

    #: full range: it is where the models separate (extrapolation and flat
    #: plate blending live above stall)
    _FAIXA = (-180.0, 180.0, 1.0)

    def _perfil(self):
        return AirfoilDef(name="p", source="analytical", stall_model="viterna")

    def _ramo_reverso(self, modelo):
        _a, cl, cd = airfoils.preview_polar(
            self._perfil(), alpha_deg_range=self._FAIXA,
            config={"reverse_flow_model": modelo}, reverse=True)
        return np.asarray(cl), np.asarray(cd)

    def test_todo_modelo_muda_o_ramo_reverso_em_relacao_ao_direto(self):
        """`thin_plate_blend` is the DELIBERATE exception: its blend is a
        function of |alpha| only, so both branches coincide -- it is the
        model's point (no discontinuity at Ut=0)."""
        _a, cl_direto, _cd = airfoils.preview_polar(
            self._perfil(), alpha_deg_range=self._FAIXA,
            config={"reverse_flow_model": "simple_flip"}, reverse=False)
        for modelo in ("simple_flip", "flat_plate", "alpha_blending"):
            with self.subTest(modelo=modelo):
                cl_rev, _cd_rev = self._ramo_reverso(modelo)
                self.assertFalse(np.allclose(cl_rev, cl_direto),
                                 f"'{modelo}' did not change the preview's reverse branch")

    def test_viterna_full_range_se_distingue_de_thin_plate_blend(self):
        """Both leave alpha_eff = alpha_geom; what separates them is the flat
        plate post-processing -- and the preview shows it."""
        cl_v, cd_v = self._ramo_reverso("viterna_full_range")
        cl_t, cd_t = self._ramo_reverso("thin_plate_blend")
        self.assertFalse(np.allclose(cl_v, cl_t))

    def test_os_cinco_produzem_curvas_distintas_duas_a_duas(self):
        """No pair of models draws the SAME curve in the reverse branch --
        which was the reported defect ("some do not modify the plot").

        The pair that comes closest is `simple_flip`/`alpha_blending`: the
        preview draws `alpha_blending` at the saturated limit of the reverse
        region (`bemt.UT_NORMALIZADO_DE_PREVIA`), where tanh -> -1 and it
        tends toward the mirroring of `simple_flip`. Still distinct, because
        tanh(-k) is not exactly -1."""
        curvas = {m: self._ramo_reverso(m)[0] for m in _MODELOS}
        for i, a in enumerate(_MODELOS):
            for b in _MODELOS[i + 1:]:
                with self.subTest(par=(a, b)):
                    self.assertFalse(np.allclose(curvas[a], curvas[b], atol=1e-3),
                                      f"'{a}' e '{b}' desenham a mesma curva")

    def test_sem_config_a_previa_e_a_polar_crua(self):
        """Compatibility: without `config` no reverse flow is applied."""
        _a, cl, _cd = airfoils.preview_polar(self._perfil(), alpha_deg_range=self._FAIXA,
                                              reverse=True)
        _a2, cl2, _cd2 = airfoils.preview_polar(self._perfil(), alpha_deg_range=self._FAIXA,
                                                 reverse=False)
        np.testing.assert_allclose(cl, cl2)


class TestModeloMudaOResultadoDoMotor(unittest.TestCase):
    """The question from the report -- "do they modify the modeling?" --
    answered in the engine: at high advance (large reverse region) the five
    give different CT values."""

    def _ct(self, modelo):
        from tests.helpers import make_studies_project
        from zbemt import studies
        from zbemt.models import FlightCondition

        projeto = make_studies_project(reverse_flow_model=modelo, Ne=10, Npsi=16)
        projeto.airfoil = AirfoilDef(source="analytical", stall_model="viterna")
        resultado = studies.run_single_case(
            projeto, FlightCondition(name="rev", mu_x=0.45, Vz=0.0,
                                      collective_deg=8.0, rpm=600.0))
        return float(resultado.summary["CT"])

    def test_ct_depende_do_modelo(self):
        cts = {m: self._ct(m) for m in _MODELOS}
        self.assertGreater(len(set(round(v, 6) for v in cts.values())), 1,
                            f"nenhum modelo mudou o CT: {cts}")


if __name__ == "__main__":
    unittest.main()
