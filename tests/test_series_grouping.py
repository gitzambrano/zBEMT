"""Series grouping by TOLERANCE, text labels and condition names with
symbols -- the three defects seen on the same screen of the Results tab
(alpha sweep = -10, -5, 0, 5, 10 over mu_x = 0..0.4):

* the legend had ~18 curves ("alpha_rotor=-10.001", "-9.999",
  "-10.002"...) because `alpha_rotor_deg` is reconstructed by
  ``atan2(Vz, V)`` and floating-point noise passed through the rounding grid;
* the X/Y/grouping combos showed raw mathtext (``$\\mu_x$ [-]``);
* each case name was the RAW field name (``mu_x=0_alpha_deg=-10``).
"""
import unittest

import numpy as np

from zbemt import api, studies
from zbemt.models import Results
from zbemt.viz import plots


def _resultado(**summary) -> Results:
    """Minimal `Results` -- just the `summary`, which is all the plots read."""
    return Results(summary=dict(summary), maps={}, condition_name=summary.get("name", ""))


class TestMapaDeAgrupamento(unittest.TestCase):

    def test_ruido_abaixo_da_tolerancia_vira_uma_serie_so(self):
        # exactly the values read on screen
        brutos = [-10.002, -10.001, -10.0, -9.999, -9.997]
        mapa = plots.mapa_de_agrupamento(brutos, 0.01)
        self.assertEqual(len(set(mapa.values())), 1)
        self.assertAlmostEqual(next(iter(set(mapa.values()))), -10.0, places=9)

    def test_varredura_legitima_continua_separada(self):
        mapa = plots.mapa_de_agrupamento([-10.0, -5.0, 0.0, 5.0, 10.0], 0.01)
        self.assertEqual(len(set(mapa.values())), 5)

    def test_passo_menor_que_a_tolerancia_e_fundido_de_proposito(self):
        """The tolerance is the USER's: increased, it merges a fine sweep --
        that is what it means, not a defect."""
        mapa = plots.mapa_de_agrupamento([0.0, 0.05, 0.1, 0.15], 0.2)
        self.assertEqual(len(set(mapa.values())), 1)

    def test_tolerancia_zero_cai_no_comportamento_anterior(self):
        mapa = plots.mapa_de_agrupamento([-10.001, -10.0, -9.999], 0.0)
        self.assertEqual(len(set(mapa.values())), 3)

    def test_zero_negativo_nao_vira_serie_propria(self):
        mapa = plots.mapa_de_agrupamento([-0.0002, 0.0003], 0.01)
        chaves = set(mapa.values())
        self.assertEqual(len(chaves), 1)
        # "-0" and "0" format differently and would become two legends
        self.assertEqual(f"{next(iter(chaves)):g}", "0")

    def test_valores_nao_numericos_sao_chave_de_si_mesmos(self):
        mapa = plots.mapa_de_agrupamento(["newton", "aitken", 1.0], 0.01)
        self.assertEqual(mapa["newton"], "newton")
        self.assertEqual(mapa["aitken"], "aitken")


class TestPlotXYAgrupaComTolerancia(unittest.TestCase):
    """The path of truth: `plot_xy` with the alpha noise from the report."""

    def _resultados(self):
        alphas = [-10.002, -10.001, -10.0, -9.999, -9.997]
        return [_resultado(mu_x=0.05 * (i + 1), alpha_rotor_deg=a, CT=0.01 * (i + 1))
                for i, a in enumerate(alphas)]

    def _n_curvas(self, tol):
        import matplotlib.pyplot as plt
        fig, ax = plt.subplots()
        try:
            plots.plot_xy(self._resultados(), x_key="mu_x", y_key="CT",
                          group_by="alpha_rotor_deg", ax=ax, group_tol=tol)
            return len(ax.get_lines())
        finally:
            plt.close(fig)

    def test_uma_curva_com_a_tolerancia_padrao(self):
        # -1 for the horizontal reference line (`axhline`) that plot_xy draws
        self.assertEqual(self._n_curvas(plots.TOLERANCIA_DE_AGRUPAMENTO_PADRAO) - 1, 1)

    def test_cinco_curvas_sem_tolerancia_nenhuma(self):
        """The reported defect, reproduced: without tolerance, one curve per
        noise point."""
        self.assertEqual(self._n_curvas(0.0) - 1, 5)

    def test_legenda_em_ordem_de_valor(self):
        import matplotlib.pyplot as plt
        resultados = [_resultado(mu_x=0.1, alpha_rotor_deg=a, CT=0.01)
                      for a in (0.0, -10.0, -5.0, 10.0, 5.0)]
        fig, ax = plt.subplots()
        try:
            plots.plot_xy(resultados, x_key="mu_x", y_key="CT",
                          group_by="alpha_rotor_deg", ax=ax)
            rotulos = [t.get_text() for t in ax.get_legend().get_texts()]
        finally:
            plt.close(fig)
        valores = [float(r.split("=")[1]) for r in rotulos]
        self.assertEqual(valores, sorted(valores))


class TestGridAgrupaComTolerancia(unittest.TestCase):
    """Same defect in grid mode (auto-detection of secondary axes)."""

    def _resultados(self):
        saida = []
        for i, alpha in enumerate([-10.002, -10.001, -10.0, -9.999]):
            saida.append(_resultado(mu_x=0.1 * (i + 1), alpha_rotor_deg=alpha,
                                    collective_deg=8.0, rpm=600.0, CT=0.01))
        return saida

    def test_alpha_com_ruido_nao_gera_uma_serie_por_ponto(self):
        import matplotlib.pyplot as plt
        fig = plots.plot_coefficients_vs_axis(self._resultados(), axis="mu_x")
        try:
            eixo = fig.axes[0]
            # one curve + the horizontal reference line
            rotulos = [l.get_label() for l in eixo.get_lines()
                       if not l.get_label().startswith("_")]
            self.assertLessEqual(len(rotulos), 1)
        finally:
            plt.close(fig)


class TestRotuloEmTexto(unittest.TestCase):
    """Qt combos do not render LaTeX: the label must come out as text."""

    def test_mathtext_vira_unicode(self):
        self.assertEqual(plots.rotulo_de_summary_em_texto("mu_x"), "μₓ [-]")
        self.assertEqual(plots.rotulo_de_summary_em_texto("Torque"), "Q [N·m]")

    def test_nenhum_cifrao_ou_contrabarra_sobra(self):
        for key in plots._SUMMARY_KEY_LABELS:
            texto = plots.rotulo_de_summary_em_texto(key)
            with self.subTest(key=key):
                self.assertNotIn("$", texto)
                self.assertNotIn("\\", texto)
                self.assertNotIn("{", texto)
                self.assertNotIn("}", texto)

    def test_chave_desconhecida_passa_intacta(self):
        """`_summary_axis_label` falls back to the raw key name; its `_` is
        NOT subscripted ("cfg_solver", not "cfgₛolver")."""
        self.assertEqual(plots.rotulo_de_summary_em_texto("cfg_solver"), "cfg_solver")


class TestNomeDeCondicaoComSimbolo(unittest.TestCase):

    def test_simbolos_no_lugar_do_nome_cru_do_campo(self):
        nome = studies.nome_de_condicao({"mu_x": 0.1, "alpha_deg": -10})
        self.assertEqual(nome, "μ_x=0.1, α_rotor=-10°")

    def test_coletivo_e_rpm(self):
        self.assertEqual(studies.nome_de_condicao({"collective_deg": 8, "rpm": 600}),
                         "θ₀=8°, RPM=600")

    def test_variavel_desconhecida_nao_deixa_a_condicao_sem_nome(self):
        self.assertEqual(studies.nome_de_condicao({"xyz": 3}), "xyz=3")

    def test_fatorial_nomeia_com_simbolo(self):
        from tests.helpers import make_studies_project
        projeto = make_studies_project()
        condicoes = studies.build_factorial_conditions(
            projeto,
            [{"variable": "mu_x", "values": [0.0, 0.2]},
             {"variable": "alpha_deg", "values": [-5.0]}],
            {"collective_deg": 8.0, "rpm": 600.0})
        self.assertEqual([c.name for c in condicoes],
                         ["μ_x=0, α_rotor=-5°", "μ_x=0.2, α_rotor=-5°"])

    def test_nome_de_arquivo_volta_para_ascii(self):
        """The name is Unicode on screen; the FILE derived from it is not --
        it travels in zip and foreign file systems."""
        arquivo = api.sanitize_filename(studies.nome_de_condicao({"mu_x": 0.1, "alpha_deg": -10}))
        self.assertEqual(arquivo, "mu_x=0.1, alpha_rotor=-10deg")
        self.assertTrue(arquivo.isascii())

    def test_acento_digitado_pelo_usuario_continua_intacto(self):
        """Only the symbols that the tool itself generates are transcribed."""
        self.assertEqual(api.sanitize_filename("Caso Padrão"), "Caso Padrão")


if __name__ == "__main__":
    unittest.main()
