"""In propeller mode, x is the ROTOR AXIS -- not the disk plane.

The engine decomposes the flight velocity relative to the DISK: `mu_x` in the
plane, `Vz` along the axis, and calls the first component x and the second
component z. In a helicopter this coincides with the vehicle axes. In a
propeller it does not: the rotor axis points forward, in cruise ALL of the
aircraft's velocity is along it, and the table labeled that velocity as
"V_inf,z" -- a vertical component -- while the vertical component, which is
zero, appeared as "V_inf,x".

Consequences that these tests ensure:

  * A propeller's J_x is the AXIAL (`J_z` internal, shown as J_x): it is what
    enters propulsive efficiency and propeller charts;
  * The reported angle is measured from the AXIS (`alpha_disk_deg`), so level
    cruise reads 0°, not 90°;
  * `mu_x`/`J_x` disappear from the table in propeller mode -- in the engine
    they are synonyms for the IN-PLANE component, and the letter x there would
    say the opposite of what is true.

None of this is physics: the solver continues to see the pair (mu_x, Vz) and
no equation changes. It is the vocabulary -- and the wrong vocabulary puts the
aircraft's velocity in the wrong field.
"""
import math
import unittest

from tests.helpers import requires_qt

import numpy as np

from zbemt import api, bemt, studies
from zbemt.models import FlightCondition
from tests.helpers import make_studies_project


#: Geometry of the example project, so that OmegaR here is the same as
#: `studies` uses in conversions (V<->mu_x, J_z<->Vz) -- a local rotor with
#: a different radius would make the equivalence tests compare numbers from
#: two different rotors.
_PROJETO_BASE = make_studies_project()


def _rotor(rpm: float = 1200.0):
    return studies._to_rotor(_PROJETO_BASE.geometry, rpm=rpm)


def _omega_R(rpm: float = 1200.0) -> float:
    return _rotor(rpm).OmegaR


def _resultado_de_exemplo():
    """A real `Results` -- the `summary` keys come from the engine, not from a
    dictionary built in the test (which would pass even if the engine stopped
    emitting the column)."""
    return api.run_case(
        _PROJETO_BASE,
        FlightCondition(name="ref", mu_x=0.2, Vz=3.0, collective_deg=8.0,
                         rpm=1200.0))


_RESULTADO_DE_ROTOR = _resultado_de_exemplo()


class TestAnguloAPartirDoEixo(unittest.TestCase):
    """`alpha_disk_deg` is the complement of `alpha_rotor_deg`."""

    def test_cruzeiro_puramente_axial_le_zero(self):
        cfg = bemt.BEMTConfig(is_propeller=True)
        rot = _rotor()
        _mu, _Vv, meta = bemt.resolve_advance_velocity(rot, cfg, mu_x=0.0, Vz=50.0)
        self.assertAlmostEqual(meta["alpha_rotor_deg"], 90.0, places=9)
        self.assertAlmostEqual(meta["alpha_disk_deg"], 0.0, places=9)

    def test_voo_de_bordo_le_noventa(self):
        cfg = bemt.BEMTConfig()
        _mu, _Vv, meta = bemt.resolve_advance_velocity(_rotor(), cfg, mu_x=0.3, Vz=0.0)
        self.assertAlmostEqual(meta["alpha_rotor_deg"], 0.0, places=9)
        self.assertAlmostEqual(meta["alpha_disk_deg"], 90.0, places=9)

    def test_os_dois_angulos_somam_noventa_sempre(self):
        """Modulo 360: `alpha_disk` is normalized to (-180°, 180°], so the
        sum closes at 90° within one revolution (see
        `bemt._angulo_a_partir_do_eixo`)."""
        cfg = bemt.BEMTConfig()
        rot = _rotor()
        for mu_x in (-0.2, 0.0, 0.05, 0.2, 0.6):
            for Vz in (-30.0, -1.0, 0.0, 1.0, 40.0):
                with self.subTest(mu_x=mu_x, Vz=Vz):
                    _m, _v, meta = bemt.resolve_advance_velocity(rot, cfg, mu_x=mu_x, Vz=Vz)
                    soma = meta["alpha_rotor_deg"] + meta["alpha_disk_deg"]
                    # difference AROUND (-180, 180]: `x % 360` returns
                    # 360.0 for a -1e-14, and the sum closes exactly this way
                    # in half the cases
                    desvio = (soma - 90.0 + 180.0) % 360.0 - 180.0
                    self.assertAlmostEqual(desvio, 0.0, places=9)

    def test_o_modulo_do_angulo_e_o_angulo_real_com_o_eixo(self):
        """What an angle column must deliver: |alpha_disk| is the angle
        between the freestream vector and the +axis direction, in all four
        quadrants.

        Without normalization, negative crossflow AND axial descent
        (mu_x<0, Vz<0) gave 190° -- whose magnitude is not an angle at all."""
        cfg = bemt.BEMTConfig()
        rot = _rotor()
        for mu_x in (-0.4, -0.1, 0.0, 0.1, 0.4):
            for Vz in (-40.0, -1.0, 0.0, 1.0, 40.0):
                if mu_x == 0.0 and Vz == 0.0:
                    continue          # without freestream there is no angle
                with self.subTest(mu_x=mu_x, Vz=Vz):
                    _m, _v, meta = bemt.resolve_advance_velocity(rot, cfg, mu_x=mu_x, Vz=Vz)
                    vetor = np.array([mu_x * rot.OmegaR, Vz])
                    real = np.degrees(np.arccos(
                        np.dot(vetor, [0.0, 1.0]) / np.linalg.norm(vetor)))
                    self.assertAlmostEqual(abs(meta["alpha_disk_deg"]), real,
                                            places=9)


class TestAlphaAPartirDoEixoComoENTRADA(unittest.TestCase):
    """`alpha_disk_deg` resolves the IN-PLANE from the axial -- the inverse of
    `alpha_deg`. It is what a propeller needs: in cruise the misalignment is
    only a few degrees and the velocity scale comes from the axis, not the
    plane."""

    def test_alpha_disk_zero_nao_tem_escoamento_cruzado(self):
        cfg = bemt.BEMTConfig(is_propeller=True)
        mu_x, Vz, meta = bemt.resolve_advance_velocity(
            _rotor(), cfg, alpha_disk_deg=0.0, Vz=60.0)
        self.assertAlmostEqual(mu_x, 0.0, places=12)
        self.assertAlmostEqual(Vz, 60.0, places=12)
        self.assertAlmostEqual(meta["alpha_disk_deg"], 0.0, places=9)

    def test_alpha_disk_produz_o_cruzado_correspondente(self):
        cfg = bemt.BEMTConfig(is_propeller=True)
        rot = _rotor()
        mu_x, Vz, meta = bemt.resolve_advance_velocity(
            rot, cfg, alpha_disk_deg=10.0, Vz=60.0)
        self.assertAlmostEqual(mu_x * rot.OmegaR, math.tan(math.radians(10.0)) * 60.0,
                                places=9)
        self.assertAlmostEqual(meta["alpha_disk_deg"], 10.0, places=6)
        self.assertAlmostEqual(Vz, 60.0, places=12)

    def test_alpha_disk_aceita_o_axial_adimensional(self):
        """J_x (internal `J_z`) is the natural way to specify propeller
        advance -- it must also serve as the scale for `alpha_disk`."""
        cfg = bemt.BEMTConfig(is_propeller=True)
        rot = _rotor()
        mu_x, Vz, _meta = bemt.resolve_advance_velocity(
            rot, cfg, alpha_disk_deg=0.0, J_z=0.8)
        self.assertAlmostEqual(Vz, (0.8 / np.pi) * rot.OmegaR, places=9)
        self.assertAlmostEqual(mu_x, 0.0, places=12)

    def test_os_dois_angulos_juntos_sao_erro(self):
        """`alpha_deg` derives the axial from the in-plane and `alpha_disk_deg`
        does the inverse: given both, no component fixes the scale and any
        multiple of the same vector satisfies both."""
        cfg = bemt.BEMTConfig()
        with self.assertRaises(ValueError) as ctx:
            bemt.resolve_advance_velocity(_rotor(), cfg,
                                           alpha_disk_deg=5.0, alpha_deg=85.0)
        self.assertIn("alpha_disk_deg", str(ctx.exception))

    def test_alpha_disk_com_descida_axial_nao_inverte_o_cruzado(self):
        """With Vz<0 (axial descent / windmill), using the raw sign of Vz
        in the conversion inverted the side the crossflow points to, and the
        reported angle no longer matched the geometry: 10° input came out as
        190°, which is not an angle at all. With |Vz|, it comes out as 170° --
        the real angle with the +axis direction."""
        cfg = bemt.BEMTConfig(is_propeller=True)
        rot = _rotor()
        mu_x, Vz, meta = bemt.resolve_advance_velocity(
            rot, cfg, alpha_disk_deg=10.0, Vz=-60.0)
        self.assertGreater(mu_x, 0.0)      # same side as with Vz>0
        self.assertAlmostEqual(meta["alpha_disk_deg"], 170.0, places=6)
        vetor = np.array([mu_x * rot.OmegaR, Vz])
        real = np.degrees(np.arccos(
            np.dot(vetor, [0.0, 1.0]) / np.linalg.norm(vetor)))
        self.assertAlmostEqual(real, 170.0, places=6)

    def test_alpha_disk_continua_exigindo_um_so_longitudinal(self):
        cfg = bemt.BEMTConfig()
        with self.assertRaises(ValueError):
            bemt.resolve_advance_velocity(_rotor(), cfg, alpha_disk_deg=5.0, mu_x=0.1)


class TestDoisAlphasUmPorModo(unittest.TestCase):
    """There are TWO angles, and each mode uses and shows only ITS OWN.

    `alpha_rotor` is measured from the DISK PLANE -- ~0 in a helicopter
    in level forward flight -- and is THE alpha for rotor mode. `alpha_disk`
    is measured from the AXIS -- 0 in level cruise -- and is THE alpha for
    propeller mode. Each is zero in the normal condition of its vehicle, which
    is what makes the number readable.

    Before this standardization the same symbol (α_disk) named the angle of the
    PLANE in rotor mode and the angle of the AXIS in propeller mode, and both
    columns appeared together in any mode: two numbers that never coincide
    under confusing names."""

    def test_cada_angulo_tem_UM_simbolo_igual_nos_dois_modos(self):
        for modo in (False, True):
            with self.subTest(propeller=modo):
                self.assertEqual(api.summary_symbol("alpha_rotor_deg", modo)[0],
                                  "&alpha;<sub>rotor</sub>")
                self.assertEqual(api.summary_symbol("alpha_disk_deg", modo)[0],
                                  "&alpha;<sub>disk</sub>")

    def test_a_tabela_de_rotor_mostra_so_o_alpha_do_rotor(self):
        ordenadas, _cfg = api.summary_keys_union([_RESULTADO_DE_ROTOR], False)
        self.assertIn("alpha_rotor_deg", ordenadas)
        self.assertNotIn("alpha_disk_deg", ordenadas)

    def test_a_tabela_de_helice_mostra_so_o_alpha_do_disco(self):
        ordenadas, _cfg = api.summary_keys_union([_RESULTADO_DE_ROTOR], True)
        self.assertIn("alpha_disk_deg", ordenadas)
        self.assertNotIn("alpha_rotor_deg", ordenadas)

    def test_os_dois_continuam_no_summary_seja_qual_for_o_modo(self):
        """Suppression is display-only: whoever exports CSV gets both keys,
        and a file saved in propeller mode re-read in rotor mode stays
        complete."""
        for chave in ("alpha_rotor_deg", "alpha_disk_deg"):
            with self.subTest(chave=chave):
                self.assertIn(chave, _RESULTADO_DE_ROTOR.summary)

    def test_alpha_rotor_deg_e_aceito_como_ENTRADA(self):
        """Input and output write the same quantity with the SAME name --
        before input was `alpha_deg` and output was `alpha_rotor_deg`."""
        cfg = bemt.BEMTConfig()
        rot = _rotor()
        _m1, v1, _meta1 = bemt.resolve_advance_velocity(
            rot, cfg, mu_x=0.2, alpha_deg=5.0)
        _m2, v2, _meta2 = bemt.resolve_advance_velocity(
            rot, cfg, mu_x=0.2, alpha_rotor_deg=5.0)
        self.assertAlmostEqual(v1, v2, places=12)
        with self.assertRaises(ValueError):
            bemt.resolve_advance_velocity(rot, cfg, mu_x=0.2, alpha_deg=5.0,
                                           alpha_rotor_deg=5.0)

    def test_o_nome_alpha_x_nao_existe_mais_em_lugar_nenhum(self):
        """Standardization: only `alpha_rotor` and `alpha_disk`."""
        import pathlib
        raiz = pathlib.Path(__file__).resolve().parents[1]
        sobras = []
        for caminho in list((raiz / "zbemt").rglob("*.py")):
            if "__pycache__" in str(caminho):
                continue
            if "alpha_x" in caminho.read_text(encoding="utf-8"):
                sobras.append(str(caminho.relative_to(raiz)))
        self.assertEqual(sobras, [], f"ainda usam 'alpha_x': {sobras}")


class TestSimbolosGiramComOModo(unittest.TestCase):
    """The letters rotate; the numbers and the KEYS do not."""

    def test_o_avanco_axial_vira_J_x_na_helice(self):
        self.assertEqual(api.summary_symbol("J_z", True)[0], "J<sub>x</sub>")
        self.assertEqual(api.summary_symbol("mu_z", True)[0], "&mu;<sub>x</sub>")
        self.assertEqual(api.summary_symbol("Vz", True)[0], "V<sub>x</sub>")

    def test_o_cruzado_vira_indice_z_na_helice(self):
        self.assertEqual(api.summary_symbol("mu_x", True)[0], "&mu;<sub>z</sub>")
        self.assertEqual(api.summary_symbol("J_x", True)[0], "J<sub>z</sub>")
        self.assertEqual(api.summary_symbol("Vx", True)[0], "V<sub>z</sub>")

    def test_a_velocidade_total_pelo_disco_vira_V_x(self):
        """`Vz` is `Vz + v_i` (the U_P from the manual): the velocity that
        crosses the disk. In propeller axes it is along the x axis."""
        self.assertEqual(api.summary_symbol("Vz", True)[0], "V<sub>x</sub>")
        self.assertEqual(api.summary_symbol("Vz", False)[0], "V<sub>z</sub>")

    def test_vi_continua_no_eixo_do_rotor_nos_dois_modos(self):
        """Explicit request: v_i does not rotate -- it always has been, and
        remains, along the axis. What changes is the LETTER of that axis."""
        self.assertEqual(api.summary_symbol("Vi", True)[0],
                          api.summary_symbol("Vi", False)[0])
        self.assertIn("shaft", api.summary_symbol("Vi", True)[1].lower())

    def test_modo_rotor_nao_muda_nada(self):
        self.assertIs(api.summary_symbols(False), api._SIMBOLO_DE_COLUNA)

    def test_toda_chave_girada_continua_existindo_no_modo_rotor(self):
        """An override without a corresponding key would be a symbol that
        never appears -- and the rotor mode coverage test would not catch it."""
        for chave in api._SIMBOLO_DE_COLUNA_HELICE:
            with self.subTest(chave=chave):
                self.assertIn(chave, api._SIMBOLO_DE_COLUNA)


class TestTabelaDeSaidaEmModoHelice(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        projeto = make_studies_project()
        projeto.config["is_propeller"] = True
        cls.projeto = projeto
        cls.resultado = api.run_case(
            projeto,
            FlightCondition(name="cruise", mu_x=0.0, Vz=20.0,
                             collective_deg=8.0, rpm=1200.0))

    def test_o_resumo_traz_o_angulo_a_partir_do_eixo(self):
        self.assertIn("alpha_disk_deg", self.resultado.summary)
        self.assertAlmostEqual(
            self.resultado.summary["alpha_disk_deg"]
            + self.resultado.summary["alpha_rotor_deg"], 90.0, places=6)

    def test_cruzeiro_axial_le_zero_grau_na_coluna_certa(self):
        self.assertAlmostEqual(self.resultado.summary["alpha_disk_deg"], 0.0,
                                places=6)

    def test_o_J_da_helice_e_o_axial(self):
        """`J_x` (internal, in-plane) is 0 in level cruise; what matters is
        `J_z`, shown as J_x."""
        self.assertAlmostEqual(self.resultado.summary["J_x"], 0.0, places=9)
        self.assertGreater(self.resultado.summary["J_z"], 0.0)

    def _cabecalho(self, is_propeller: bool) -> list:
        import re
        cabecalho = api._summary_table([self.resultado],
                                        is_propeller).split("</tr>")[0]
        return re.findall(r'data-tip="[^"]*">(.*?)</th>', cabecalho)

    def test_o_relatorio_abre_pelo_avanco_axial_em_modo_helice(self):
        """A propeller table starts with J_x -- and the same result, read in
        rotor mode, starts with mu_x."""
        self.assertEqual(self._cabecalho(True)[:2],
                          ["condition", "&mu;<sub>x</sub>"])
        self.assertEqual(self._cabecalho(False)[:2],
                          ["condition", "&mu;<sub>x</sub>"])

    def test_a_velocidade_de_voo_muda_de_letra_e_so(self):
        helice, rotor = self._cabecalho(True), self._cabecalho(False)
        self.assertIn("V<sub>x</sub>", helice)     # Vz, rotor axis
        self.assertIn("V<sub>z</sub>", rotor)      # the same Vz
        # and the engine's in-plane synonyms do not appear in propeller axes
        self.assertIn("&mu;<sub>x</sub>", rotor)
        self.assertEqual(helice.count("&mu;<sub>x</sub>"), 1)  # only mu_z, rotated

    def test_linha_de_condicao_do_relatorio_renderiza_subscritos(self):
        from zbemt.models import Results
        resultado = Results(condition_name="mu_x=0.2, alpha_rotor=5",
                            summary={"mu_x": 0.2})
        tabela = api._summary_table([resultado])
        self.assertIn("&mu;<sub>x</sub>=0.2", tabela)
        self.assertIn("&alpha;<sub>rotor</sub>=5", tabela)

    def test_modo_helice_e_deduzido_do_projeto_e_do_eco(self):
        self.assertTrue(api.modo_helice([], self.projeto))
        self.assertTrue(api.modo_helice([self.resultado]))
        self.assertFalse(api.modo_helice([]))


class TestFatorialNaConvencaoDeHelice(unittest.TestCase):

    def setUp(self):
        self.projeto = make_studies_project()
        self.projeto.config["is_propeller"] = True

    def test_eixo_de_J_axial_varre_o_avanco_da_helice(self):
        cond = studies.build_factorial_conditions(
            self.projeto, [{"variable": "J_z", "values": [0.4, 0.8]}],
            fixed={"mu_x": 0.0, "rpm": 1200.0, "collective_deg": 8.0})
        self.assertEqual(len(cond), 2)
        self.assertAlmostEqual(cond[0].mu_x, 0.0, places=12)
        self.assertGreater(cond[1].Vz, cond[0].Vz)
        # and the name comes out in propeller letters
        self.assertIn("J_x=0.4", cond[0].name)

    def test_alpha_disk_deriva_o_cruzado_do_axial(self):
        cond = studies.build_factorial_conditions(
            self.projeto, [{"variable": "alpha_disk", "values": [0.0, 10.0]}],
            fixed={"Vz": 60.0, "rpm": 1200.0, "collective_deg": 8.0})
        self.assertAlmostEqual(cond[0].mu_x, 0.0, places=12)
        self.assertGreater(cond[1].mu_x, 0.0)
        self.assertAlmostEqual(cond[0].Vz, 60.0, places=9)
        self.assertAlmostEqual(cond[1].Vz, 60.0, places=9)
        self.assertIn("α_disk=0°", cond[0].name)

    def test_alpha_disk_e_alpha_disk_juntos_sao_erro(self):
        with self.assertRaises(ValueError):
            studies.build_factorial_conditions(
                self.projeto, [{"variable": "alpha_disk", "values": [0.0]}],
                fixed={"alpha_deg": 85.0, "rpm": 1200.0})

    def test_o_mesmo_eixo_em_modo_rotor_usa_as_letras_de_rotor(self):
        self.projeto.config["is_propeller"] = False
        cond = studies.build_factorial_conditions(
            self.projeto, [{"variable": "mu_x", "values": [0.2]}],
            fixed={"rpm": 1200.0, "collective_deg": 8.0})
        self.assertIn("μ_x=0.2", cond[0].name)

    def test_mu_z_como_eixo_axial_equivale_a_Vv(self):
        cond_mu_z = studies.build_factorial_conditions(
            self.projeto, [{"variable": "mu_z", "values": [0.1]}],
            fixed={"mu_x": 0.0, "rpm": 1200.0, "collective_deg": 8.0})
        self.assertAlmostEqual(cond_mu_z[0].Vz, 0.1 * _omega_R(), places=6)


class TestParidadeDeLinhaDeComando(unittest.TestCase):
    """The axial advance and angle from the axis must be reachable via the
    CLI -- it is the GUI/.bemt/CLI parity rule from CLAUDE.md."""

    #: `--project` is required in the parser; here it is just syntax noise
    _BASE = ["--project", "projects/test11"]

    def _parse(self, *extra):
        from zbemt import cli
        return cli._build_parser().parse_args(self._BASE + list(extra))

    def test_as_flags_axiais_existem_e_sao_excludentes(self):
        self.assertAlmostEqual(
            self._parse("--j-axial", "0.8", "--rpm", "2500").J_axial, 0.8)
        self.assertAlmostEqual(
            self._parse("--mu-axial", "0.25", "--rpm", "2500").mu_axial, 0.25)
        with self.assertRaises(SystemExit):
            self._parse("--j-axial", "0.8", "--v-axial", "60", "--rpm", "2500")

    def test_as_flags_sao_nomeadas_pelo_slot_nao_pela_letra(self):
        """The letter of a component depends on the mode; a flag parsed in
        the same pass as `--project` cannot know it. `mu_x` must therefore
        never name the in-plane component on the command line -- on a
        propeller that component is shown as mu_z."""
        from zbemt import cli
        texto = cli._build_parser().format_help()
        for flag in ("--mu-inplane", "--j-inplane", "--v-inplane",
                     "--mu-axial", "--j-axial", "--v-axial"):
            with self.subTest(flag=flag):
                self.assertIn(flag, texto)
        for antiga in ("--mux ", "--muz ", "--jx ", "--jz ", "--vz "):
            with self.subTest(antiga=antiga):
                self.assertNotIn(antiga, texto)

    def test_o_angulo_a_partir_do_eixo_existe_e_exclui_o_do_plano(self):
        args = self._parse("--alpha-disk-deg", "6", "--v-axial", "65", "--rpm", "2500")
        self.assertAlmostEqual(args.alpha_disk_deg, 6.0)
        # `--alpha-disk-deg` is in the SAME mutually exclusive group as the
        # other in-plane representations: it is that component, as an angle
        with self.assertRaises(SystemExit):
            self._parse("--alpha-disk-deg", "6", "--mu-inplane", "0.1")
    def test_os_dois_angulos_na_linha_de_comando_sao_recusados(self):
        """The two angles are in DIFFERENT mutually exclusive groups, so
        `argparse` accepts them: without explicit checking in `cli.run`,
        `--alpha-disk-deg 6 --alpha-rotor-deg 84` would resolve Vz from a
        still-zero mu_x and run a PAIRING in silence."""
        import io
        import contextlib
        from zbemt import cli
        argv = self._BASE + ["--alpha-disk-deg", "6", "--alpha-rotor-deg", "84",
                              "--rpm", "2500"]
        args = self._parse("--alpha-disk-deg", "6", "--alpha-rotor-deg", "84",
                            "--rpm", "2500")     # the parser accepts...
        self.assertIsNotNone(args.alpha_disk_deg)
        erro = io.StringIO()
        with contextlib.redirect_stderr(erro):
            codigo = cli.main(argv)              # ...and execution rejects
        self.assertEqual(codigo, 2)
        self.assertIn("same angle written two ways", erro.getvalue())

    def test_toda_flag_nova_e_campo_de_RunOptions(self):
        """`cli.RunOptions` is generated from the parser: a Python script
        builds the condition without building `argv`."""
        import dataclasses
        from zbemt import cli
        campos = {f.name for f in dataclasses.fields(cli.RunOptions)}
        for nome in ("alpha_disk_deg", "alpha_rotor_deg",
                     "mu_inplane", "J_inplane", "V_inplane",
                     "mu_axial", "J_axial", "V_axial"):
            with self.subTest(campo=nome):
                self.assertIn(nome, campos)


class TestNomenclaturaExibida(unittest.TestCase):
    """Ensures the boundary between internal keys and displayed symbols."""

    def test_descricoes_de_relatorio_nao_expoem_vx_vz_ou_mu_crus(self):
        from zbemt import api

        for modo in (False, True):
            for chave, (_simbolo, descricao) in api.summary_symbols(modo).items():
                exibida = api._descricao_com_simbolos(descricao)
                with self.subTest(modo=modo, chave=chave):
                    self.assertNotRegex(exibida, r"(?<![\w])(Vx|Vz|mu_x|mu_z|J_x|J_z)(?![\w])")

    def test_relatorio_suprime_apenas_o_alpha_do_modo_oposto(self):
        from zbemt.models import Results
        from zbemt import api

        resultado = Results(summary={
            "alpha_rotor_deg": 1.0, "alpha_disk_deg": 89.0,
            "mu_x": 0.1, "mu_z": 0.0,
        })
        rotor, _ = api._chaves_ordenadas([resultado], is_propeller=False)
        helice, _ = api._chaves_ordenadas([resultado], is_propeller=True)
        self.assertIn("alpha_rotor_deg", rotor)
        self.assertNotIn("alpha_disk_deg", rotor)
        self.assertIn("alpha_disk_deg", helice)
        self.assertNotIn("alpha_rotor_deg", helice)

    @requires_qt
    def test_rotulos_dos_slots_sao_iguais_nas_abas(self):
        from zbemt.gui.common import _ROTULOS_DE_CONDICAO
        from zbemt.gui.tabs.run_batch import RunBatchTab

        self.assertEqual(_ROTULOS_DE_CONDICAO[False]["inplane"][0],
                         "Edgewise (in-plane) flow:")
        self.assertEqual(_ROTULOS_DE_CONDICAO[False]["axial"][0],
                         "Axial (along-shaft) Flow:")
        self.assertEqual(_ROTULOS_DE_CONDICAO[True]["inplane"][0],
                         "Cross (in-plane) Flow:")
        self.assertEqual(RunBatchTab._AXIS_SLOTS[1][0],
                         "Edgewise (in-plane) flow")
        self.assertEqual(RunBatchTab._AXIS_SLOTS_HELICE["inplane"],
                         "Cross (in-plane) Flow")

    def test_texto_de_ajuda_renderiza_componentes_com_subscrito(self):
        from zbemt import api

        texto = api._descricao_com_simbolos(
            "Use V_x and V_z with mu_x, J_x, alpha_rotor and lambda_z.")
        self.assertIn("V<sub>x</sub>", texto)
        self.assertIn("V<sub>z</sub>", texto)
        self.assertIn("&mu;<sub>x</sub>", texto)
        self.assertIn("J<sub>x</sub>", texto)
        self.assertIn("&alpha;<sub>rotor</sub>", texto)
        self.assertIn("&lambda;<sub>z</sub>", texto)
        self.assertIn("&alpha;<sub>rotor</sub>",
                      api._descricao_com_simbolos("alpha_rotor_deg=-10"))
        self.assertIn("&alpha;<sub>disk</sub>",
                      api._descricao_com_simbolos("α_disk=2"))

    def test_rotulos_dos_combos_renderizam_grega_e_subscrito(self):
        from zbemt.viz import plots

        self.assertEqual(plots.rotulo_de_summary_em_html("mu_x"),
                         "&mu;<sub>x</sub> [-]")
        self.assertEqual(plots.rotulo_de_summary_em_html("J_x"),
                         "J<sub>x</sub> [-]")
        self.assertEqual(plots.rotulo_de_summary_em_html("mu_z"),
                         "&mu;<sub>z</sub> [-]")


if __name__ == "__main__":
    unittest.main()
