"""All example projects versioned under ``projects/test1`` – ``test12``.

They are not decoration: they are the first contact for anyone who
installs zBEMT, and an example that opens with an error or returns a
number without physical sense is worse than no example at all. This file
runs all of them end to end and checks that the results fall within the
range the aircraft category requires.

The ranges are WIDE on purpose. They are not validation against measured
data. They are fences that catch gross regressions: a flipped sign, a factor of 2, a
violation of energy conservation, a rotor that stopped converging.
"""
import math
import unittest

from zbemt import api
from zbemt import paths


# test1..test10, test12 are rotors; test11 is the propeller example.
PROJETOS_ROTOR = ["test1", "test2", "test3", "test4", "test5",
                  "test6", "test7", "test8", "test9", "test10", "test12"]
TODOS = PROJETOS_ROTOR + ["test11"]


def _caminho(nome: str) -> str:
    return str(paths.projects_root() / nome)


def _solidez(projeto) -> float:
    g = projeto.geometry
    corda_media = sum(g.chord_norm) / len(g.chord_norm)
    return g.n_blades * corda_media / math.pi


class TestProjetosExemploAbrem(unittest.TestCase):
    """Before any physics: the files exist, open, and are valid."""

    def test_todos_abrem_sem_erro(self):
        for nome in TODOS:
            with self.subTest(projeto=nome):
                projeto = api.open_project(_caminho(nome))
                self.assertTrue(projeto.name)
                self.assertGreaterEqual(len(projeto.geometry.r_norm), 2)
                self.assertTrue(projeto.saved_cases, "project without a saved case is not an example")

    def test_nenhum_projeto_tem_erro_de_validacao(self):
        """An example distributed with a validation error teaches the user
        to ignore validation."""
        for nome in TODOS:
            with self.subTest(projeto=nome):
                projeto = api.open_project(_caminho(nome))
                erros = [i for i in api.validate_project(projeto, conditions=projeto.saved_cases)
                         if i.level == "error"]
                self.assertEqual(erros, [], [str(i) for i in erros])

    def test_round_trip_preserva_o_projeto(self):
        """Saving and reopening must return the same project -- it is the
        GUI/.bemt/CLI parity contract applied to distributed material."""
        import shutil
        import tempfile
        from dataclasses import asdict
        for nome in TODOS:
            with self.subTest(projeto=nome):
                original = api.open_project(_caminho(nome))
                destino = tempfile.mkdtemp()
                self.addCleanup(shutil.rmtree, destino, ignore_errors=True)
                original.path = destino
                api.save_project(original)
                relido = api.open_project(destino)
                self.assertEqual(relido.name, original.name)
                self.assertEqual(asdict(relido.geometry), asdict(original.geometry))
                self.assertEqual(asdict(relido.airfoil), asdict(original.airfoil))
                self.assertEqual(dict(relido.config), dict(original.config))


class TestRotoresEmPairado(unittest.TestCase):
    """Hover is the only regime in which classic rotor metrics carry the
    meaning they appear to have (see Q6 in production-plan.md: FM in
    forward flight routinely exceeds 1, and that is not a bug)."""

    def test_figura_de_merito_abaixo_de_1(self):
        """FM > 1 in HOVER would mean extracting more thrust from a given
        power than the ideal actuator disk -- a violation of energy
        conservation, and the classic symptom of an inflow error."""
        for nome in PROJETOS_ROTOR:
            with self.subTest(projeto=nome):
                projeto = api.open_project(_caminho(nome))
                pairado = next(c for c in projeto.saved_cases if c.mu_x == 0.0 and not c.Vz)
                s = api.run_case(projeto, pairado).summary
                self.assertGreater(s["FM"], 0.4, "FM too low for a plausible rotor")
                self.assertLess(s["FM"], 1.0, "FM >= 1 em pairado viola o limite ideal")

    def test_carregamento_de_pa_na_faixa_da_categoria(self):
        """CT/sigma is the blade loading: the quantity that says whether
        the rotor is close to stall. A real rotorcraft rotor operates
        between ~0.05 and ~0.14; above that the blade stalls over a
        large part of the disk."""
        for nome in PROJETOS_ROTOR:
            with self.subTest(projeto=nome):
                projeto = api.open_project(_caminho(nome))
                pairado = next(c for c in projeto.saved_cases if c.mu_x == 0.0 and not c.Vz)
                s = api.run_case(projeto, pairado).summary
                ct_sigma = s["CT"] / _solidez(projeto)
                self.assertGreater(ct_sigma, 0.03, f"CT/sigma={ct_sigma:.4f}: rotor descarregado")
                self.assertLess(ct_sigma, 0.16, f"CT/sigma={ct_sigma:.4f}: acima do estol")

    def test_tracao_e_potencia_positivas_em_pairado(self):
        for nome in PROJETOS_ROTOR:
            with self.subTest(projeto=nome):
                projeto = api.open_project(_caminho(nome))
                pairado = next(c for c in projeto.saved_cases if c.mu_x == 0.0 and not c.Vz)
                s = api.run_case(projeto, pairado).summary
                self.assertGreater(s["Thrust"], 0.0)
                self.assertGreater(s["Power"], 0.0)

    def test_mach_de_ponta_abaixo_da_divergencia(self):
        """Above M~0.9 at the tip, wave drag dominates and this code's
        Prandtl-Glauert model no longer applies."""
        for nome in PROJETOS_ROTOR:
            with self.subTest(projeto=nome):
                projeto = api.open_project(_caminho(nome))
                pairado = next(c for c in projeto.saved_cases if c.mu_x == 0.0 and not c.Vz)
                s = api.run_case(projeto, pairado).summary
                mach_ponta = s["rotor_OmegaR"] / projeto.config["a_sound"]
                self.assertLess(mach_ponta, 0.85, f"Mach de ponta {mach_ponta:.2f}")

    def test_todos_os_casos_salvos_convergem(self):
        for nome in PROJETOS_ROTOR:
            projeto = api.open_project(_caminho(nome))
            for caso in projeto.saved_cases:
                with self.subTest(projeto=nome, caso=caso.name):
                    s = api.run_case(projeto, caso).summary
                    self.assertGreater(s["convergence_pct"], 95.0)


class TestHelice(unittest.TestCase):
    """The propeller is the example that exists to exercise
    `is_propeller=True` and the AXIAL convention for flight speed."""

    def setUp(self):
        self.projeto = api.open_project(_caminho("test11"))

    def test_velocidade_de_voo_e_axial_nao_no_plano(self):
        """The propeller mode pitfall: `mu_x` is the IN-PLANE component of
        the disk. Putting flight speed there makes the blade see +-V
        along the azimuth -- what a helicopter rotor in forward flight
        sees and a propeller in straight flight never does. The examples
        use `Vz`."""
        for caso in self.projeto.saved_cases:
            with self.subTest(caso=caso.name):
                self.assertEqual(caso.mu_x, 0.0,
                                 "propeller speed in mu_x produces a plausible and wrong result")

    def test_eficiencia_propulsiva_nunca_passa_de_1(self):
        """eta = T*V/P > 1 is energy coming out of nowhere."""
        for caso in self.projeto.saved_cases:
            with self.subTest(caso=caso.name):
                s = api.run_case(self.projeto, caso).summary
                self.assertGreaterEqual(s["eta_prop"], 0.0)
                self.assertLess(s["eta_prop"], 1.0)

    def test_eficiencia_cresce_com_a_velocidade_e_e_alta_no_cruzeiro(self):
        etas = {c.name: api.run_case(self.projeto, c).summary["eta_prop"]
                for c in self.projeto.saved_cases}
        estatico = etas["static (V=0)"]
        cruzeiro = etas["cruise 65 m/s"]
        self.assertEqual(estatico, 0.0, "propulsive efficiency at static is 0 by definition (V=0)")
        self.assertGreater(cruzeiro, 0.7, f"cruise propeller with eta={cruzeiro:.2f} is poorly matched")

    def test_traciona_em_toda_a_faixa_de_casos_salvos(self):
        for caso in self.projeto.saved_cases:
            with self.subTest(caso=caso.name):
                s = api.run_case(self.projeto, caso).summary
                self.assertGreater(s["Thrust"], 0.0,
                                   "propeller in windmill state: the pitch does not cover this speed")


class TestEtaPropUsaAComponenteAxial(unittest.TestCase):
    """Regression test for the bug found while building these examples.

    `eta_prop` used to be `J_x * CT_prop / CP_prop` with a LONGITUDINAL
    J_x, even though the comment right next to it said the quantity only
    has meaning with purely axial advance -- a case in which J_x = 0 and
    the formula returned zero. A correctly specified propeller reported
    zero efficiency across the whole sweep; specified wrong, it reported
    values above 1.
    """

    def setUp(self):
        self.projeto = api.open_project(_caminho("test11"))

    def test_helice_axial_reporta_eficiencia_nao_nula(self):
        from zbemt.models import FlightCondition
        caso = FlightCondition(name="axial", mu_x=0.0, Vz=40.0, collective_deg=0.0, rpm=2500.0)
        s = api.run_case(self.projeto, caso).summary
        self.assertEqual(s["J_x"], 0.0, "axial advance has zero longitudinal J_x, by construction")
        self.assertGreater(s["J_z"], 0.0)
        self.assertGreater(s["eta_prop"], 0.3,
                           "eta_prop voltou a ler a componente longitudinal")

    def test_eta_bate_com_a_definicao_T_V_sobre_P(self):
        """Checks against the dimensional definition, not against the
        dimensionless formula -- that is the point of the test."""
        from zbemt.models import FlightCondition
        V = 40.0
        s = api.run_case(self.projeto, FlightCondition(
            name="axial", mu_x=0.0, Vz=V, collective_deg=0.0, rpm=2500.0)).summary
        eta_dimensional = s["Thrust"] * V / s["Power"]
        self.assertAlmostEqual(s["eta_prop"], eta_dimensional, places=6)

    def test_moinho_nao_reporta_eficiencia_positiva(self):
        """In windmill state, thrust and power are both negative and the
        ratio turns positive again -- it would give a high 'efficiency'
        exactly where the propeller consumes energy from the flow
        instead of propelling."""
        from zbemt.models import FlightCondition
        s = api.run_case(self.projeto, FlightCondition(
            name="moinho", mu_x=0.0, Vz=140.0, collective_deg=0.0, rpm=2500.0)).summary
        self.assertLess(s["Thrust"], 0.0, "this speed should put the propeller in windmill state")
        self.assertEqual(s["eta_prop"], 0.0)


if __name__ == "__main__":
    unittest.main()


class TestGuiEDefaultsDoModoHelice(unittest.TestCase):
    """The GUI must not push the user toward the wrong specification.

    When opening the propeller project the AXES rotate (see
    `tests/test_propeller_axes_convention.py`): the AXIAL field becomes
    advance, in `J_x` -- the J_x from propeller charts, built on the
    speed along the axis --, and the in-plane field becomes the CROSS
    flow, which is zero in straight cruise.

    Before, the axial field opened on `alpha [deg]`, which left flight
    speed without a natural field and invited putting it in the
    longitudinal one -- which is the IN-PLANE component of the disk.
    Later it opened on `Vz [m/s]`, which already fixed that but still
    offered "J_x" (= pi*mu_x, the edgewise ratio) in the wrong field."""

    @classmethod
    def setUpClass(cls):
        try:
            from PyQt6.QtWidgets import QApplication
        except ImportError:                       # pragma: no cover
            raise unittest.SkipTest("sem PyQt6")
        cls.app = QApplication.instance() or QApplication([])

    def _aba(self, projeto: str):
        from zbemt.gui import app as gui
        estado = gui.AppState()
        aba = gui.RunCaseTab(estado)
        estado.set_project(api.open_project(_caminho(projeto)))
        return aba

    def test_helice_abre_com_o_avanco_no_campo_AXIAL(self):
        aba = self._aba("test11")
        self.assertEqual(aba.axial.unit_combo.currentText(), "Jₓ")
        self.assertEqual(aba.advance.unit_combo.currentText(), "V_z [m/s]")
        # and the in-plane "Jₓ" (pi*mu_x) is not even offered in the
        # wrong field
        planos = [aba.advance.unit_combo.itemText(i)
                  for i in range(aba.advance.unit_combo.count())]
        self.assertNotIn("Jₓ", planos)

    def test_rotor_continua_abrindo_em_mu_x_e_alpha_rotor(self):
        """Standardized nomenclature: there is no more bare "mu_x" or
        "alpha" -- every component says which AXIS it belongs to (with a
        real unicode subscript, see `widgets.UNIDADES_DE_CONDICAO`), and
        the angle says which reference it is measured from."""
        aba = self._aba("test1")
        self.assertEqual(aba.advance.unit_combo.currentText(), "μₓ")
        self.assertEqual(aba.axial.unit_combo.currentText(), "αᵣₒₜₒᵣ [deg]")

    def test_faixa_do_campo_axial_acompanha_a_unidade(self):
        """+-90 is an angle range. In m/s it would truncate an airplane
        propeller: cruise at 65 passes, but a windmill case at 140 would
        be silently clipped."""
        aba = self._aba("test11")
        aba.axial.unit_combo.setCurrentText("Vₓ [m/s]")
        self.assertGreaterEqual(aba.axial.spin.maximum(), 200.0)

    def test_escolha_manual_do_usuario_nao_e_sobrescrita(self):
        """Within the SAME mode: the list did not change, so the choice
        holds. On a mode switch the old list stops existing and the
        field goes back to the new mode's default -- see
        `AxialInput.set_default_unit`."""
        aba = self._aba("test11")
        aba.axial.unit_combo.setCurrentText("Vₓ [m/s]")    # manual choice
        aba.axial.set_default_unit(True)                        # same mode
        self.assertEqual(aba.axial.unit_combo.currentText(), "Vₓ [m/s]")


class TestAvisoDeConvencaoDeHelice(unittest.TestCase):
    """The guard that catches the same mistake coming from the CLI or a
    script, where there is no widget at all to guide the user."""

    def setUp(self):
        from zbemt.models import FlightCondition
        self.FlightCondition = FlightCondition
        self.projeto = api.open_project(_caminho("test11"))

    def _avisos_de_helice(self, condicao):
        return [i for i in api.validate_project(self.projeto, conditions=[condicao])
                if i.level == "warning" and "propeller" in i.message]

    def test_avanco_todo_no_plano_gera_aviso(self):
        ruim = self.FlightCondition(name="errado", mu_x=0.3, Vz=0.0,
                                     collective_deg=0.0, rpm=2500.0)
        self.assertEqual(len(self._avisos_de_helice(ruim)), 1)

    def test_especificacao_axial_correta_nao_gera_aviso(self):
        bom = self.FlightCondition(name="certo", mu_x=0.0, Vz=65.0,
                                    collective_deg=0.0, rpm=2500.0)
        self.assertEqual(self._avisos_de_helice(bom), [])

    def test_eixo_inclinado_e_legitimo_e_nao_gera_aviso(self):
        """A tilt-rotor in transition genuinely has both components; only
        the TOTAL absence of an axial component is the mistake's
        signature."""
        obliquo = self.FlightCondition(name="oblíquo", mu_x=0.1, Vz=50.0,
                                        collective_deg=0.0, rpm=2500.0)
        self.assertEqual(self._avisos_de_helice(obliquo), [])

    def test_rotor_com_mu_nao_e_avisado(self):
        rotor = api.open_project(_caminho("test1"))
        condicao = self.FlightCondition(name="avanço", mu_x=0.3, Vz=0.0,
                                         collective_deg=8.0, rpm=258.0)
        avisos = [i for i in api.validate_project(rotor, conditions=[condicao])
                  if "propeller" in i.message]
        self.assertEqual(avisos, [])


class TestVariedadeDosExemplos(unittest.TestCase):
    """The examples exist to exercise DIFFERENT paths in the engine.

    Five rotors with an analytical polar and the same config would
    cover just one path: variety is what makes them a test, not a
    showcase.
    """

    def test_ha_exemplo_com_polar_tabelada(self):
        """The table path is separate code -- including the slice choice
        per radial station, which only runs with `source='table'`."""
        projeto = api.open_project(_caminho("test4"))
        self.assertEqual(projeto.airfoil.source, "table")
        self.assertGreaterEqual(len(projeto.airfoil.table_slices), 3)
        reynolds = {s.reynolds for s in projeto.airfoil.table_slices}
        self.assertGreaterEqual(len(reynolds), 3, "tabela sem eixo de Reynolds real")

    def test_ha_exemplo_com_estol_dinamico_ligado(self):
        projeto = api.open_project(_caminho("test5"))
        self.assertTrue(projeto.airfoil.use_dynamic_stall)

    def test_os_exemplos_cobrem_fontes_de_polar_diferentes(self):
        fontes = {api.open_project(_caminho(n)).airfoil.source for n in TODOS}
        self.assertIn("analytical", fontes)
        self.assertIn("table", fontes)

    def test_os_exemplos_cobrem_modelos_de_inflow_diferentes(self):
        modelos = {api.open_project(_caminho(n)).config.get("inflow_field_model")
                   for n in TODOS}
        self.assertGreaterEqual(len(modelos), 3, f"pouca variedade de inflow: {modelos}")

    def test_ha_exemplo_com_e_sem_compressibilidade(self):
        valores = {bool(api.open_project(_caminho(n)).config.get("use_compressibility"))
                   for n in TODOS}
        self.assertEqual(valores, {True, False},
                          "todo exemplo com o mesmo estado de compressibilidade")

    def test_ha_exemplo_com_e_sem_extensao_viterna(self):
        valores = {bool(api.open_project(_caminho(n)).airfoil.extend_full_range)
                   for n in TODOS}
        self.assertEqual(valores, {True, False},
                          "every example with the same Viterna extension state")

    def test_ha_exemplo_com_pitt_peters(self):
        """Pitt-Peters finite-state inflow is the only dynamic inflow model in
        use; at least one example must demonstrate it as the default."""
        projeto = api.open_project(_caminho("test8"))
        self.assertEqual(projeto.config.get("inflow_field_model"),
                         "pitt_peters_steady")
        self.assertGreater(projeto.config.get("pitt_peters_outer_iter", 0), 0)

    def test_ha_exemplo_com_enhanced_stall(self):
        """Enhanced stall model (smoothed nonlinear roll-off) is different from
        clip and viterna; at least one example must use it."""
        projeto = api.open_project(_caminho("test9"))
        self.assertEqual(projeto.airfoil.stall_model, "enhanced")

    def test_ha_exemplo_com_aerofolia_multisecao(self):
        """Multi-section (heterogeneous) airfoil distribution with 2+ radial
        sections is a real feature; at least one example must exercise it."""
        projeto = api.open_project(_caminho("test10"))
        self.assertGreaterEqual(len(projeto.airfoil_sections), 2)
        for section in projeto.airfoil_sections:
            self.assertIsNotNone(section.r_norm,
                                 "every section of a multi-section airfoil needs r_norm defined")
