"""Block "2D Profile Geometry" from the Airfoil tab, after the cleanup
requested by the user:

* the "typical preset" combo was removed -- all six catalog entries are NACA
  codes, so the preset and "NACA code" field were two controls for a single
  choice;
* `cst`/`bezier` were removed from the sources list (their fields were never
  reachable on screen), but remain VALID: a project that already uses them
  shows them again, and the profile is never lost;
* the remaining fields gained proper help (popup "?" and tooltip),
  including the format accepted by the `.dat` importer.
"""
import unittest

try:
    from PyQt6.QtWidgets import QApplication
    _HAS_QT = True
except Exception:                                    # pragma: no cover
    _HAS_QT = False

from zbemt import airfoils
from zbemt.models import ProfileGeometry


class _JanelaDeTeste(unittest.TestCase):
    """Base with ONE real window for all tests in this file.

    The tab is read INSIDE the window, not instantiated standalone: the width
    and help policies are applied by the window from outside, so a standalone
    tab would not have them and the test would pass by accident. And the
    window is ONE per `setUpClass`: building a `MainWindow` per test crashes
    Qt on this machine (native failure, no Python exception) -- the same Qt
    teardown defect that prevents `tests/test_airfoil_tab.py` from running
    here.
    """

    @classmethod
    def setUpClass(cls):
        from zbemt.gui.app import MainWindow
        cls.app = QApplication.instance() or QApplication([])
        cls.win = MainWindow()
        cls.aba = None
        for i in range(cls.win.tabs.count()):
            if cls.win.tabs.tabText(i).replace("*", "").strip() == "Airfoil":
                cls.aba = cls.win.tabs.widget(i)
        assert cls.aba is not None, "Airfoil tab not found in the window"

    @classmethod
    def tearDownClass(cls):
        # The window is NOT closed here on purpose: `close()` on a window
        # that went through several project changes hangs the process at the
        # end of the suite on this machine. (Update: `tests/test_airfoil_tab.py`
        # turned out to have an unrelated bug -- its own `_app()` helper
        # discarded the QApplication it created, so nothing kept it alive;
        # that is fixed now and unrelated to this window.) Hiding avoided the
        # hang but left the actual C++-side teardown to whatever order
        # Python's interpreter-shutdown GC happens to run in, which is what
        # crashed the process (access violation) right after the last test
        # here. Force it now instead, while the QApplication and event loop
        # are still in a known-good state.
        cls.win.hide()
        win, cls.win = cls.win, None
        win.deleteLater()
        cls.app.processEvents()
        del win
        import gc
        gc.collect()

    def setUp(self):
        from tests.helpers import make_studies_project
        self.state = self.win.state
        self.state.set_project(make_studies_project())
        # The window is shared by the class (see `setUpClass`): without
        # resetting the source to default, a test that left it in
        # 'neuralfoil' makes the next one start already in the mode -- and
        # the automatic suggestion, which reacts to the TRANSITION, would
        # never fire.
        self.aba.source_combo.setCurrentText("analytical")


@unittest.skipUnless(_HAS_QT, "sem PyQt6")
class TestFontesDeContorno(_JanelaDeTeste):

    def test_sem_combo_de_preset(self):
        aba = self.aba
        self.assertFalse(hasattr(aba, "profile_preset_combo"),
                          "o combo de preset era redundante com o campo NACA")

    def test_so_naca_e_importado_na_lista(self):
        aba = self.aba
        oferecidas = [aba.profile_source_combo.itemText(i)
                      for i in range(aba.profile_source_combo.count())]
        self.assertEqual(oferecidas, ["naca4", "naca5", "imported"])

    def test_projeto_legado_em_cst_recupera_a_opcao(self):
        """Hiding an option must not mean losing data from who already used
        it."""
        aba, state = self.aba, self.state
        state.project.airfoil.geometry = ProfileGeometry(
            source="cst", cst_upper=[0.2, 0.2], cst_lower=[-0.1, -0.1])
        state.notify_airfoil()
        self.assertEqual(aba.profile_source_combo.currentText(), "cst")
        self.assertEqual(aba._collect_airfoil_def().geometry.source, "cst")
        self.assertEqual(aba._collect_airfoil_def().geometry.cst_upper, [0.2, 0.2])

    def test_contorno_importado_aparece_como_importado(self):
        """The combo was not synced with the project: a profile coming from
        .dat appeared labeled "naca4"."""
        aba, state = self.aba, self.state
        state.project.airfoil.geometry = ProfileGeometry(
            source="imported", x=[1.0, 0.0, 1.0], y=[0.0, 0.0, 0.0])
        state.notify_airfoil()
        self.assertEqual(aba.profile_source_combo.currentText(), "imported")


@unittest.skipUnless(_HAS_QT, "sem PyQt6")
class TestAjudaDoBloco(unittest.TestCase):
    """Help texts and catalog: all read from CLASS attributes and pure
    functions, without building any widgets.

    No widget is built, but the class attributes still come from a
    `zbemt.gui` module, which needs Qt to import."""

    @property
    def aba(self):
        from zbemt.gui.tabs.airfoil import AirfoilTab
        return AirfoilTab

    def test_campos_do_contorno_tem_popup_de_ajuda(self):
        """They did not have entries in FIELD_HELP or anchors: the "?" did
        not appear in the row and the user got no explanation at all."""
        from zbemt.gui import help_content
        from zbemt.gui.field_help import ancora_do_campo
        for campo in ("naca_code", "cst_upper", "cst_lower", "bezier_control_points"):
            with self.subTest(campo=campo):
                self.assertIn(campo, help_content.FIELD_HELP)
                self.assertIsNotNone(ancora_do_campo(campo))

    def test_dica_do_importador_de_contorno_diz_o_formato(self):
        dica = self.aba._DICA_DE_IMPORTAR_DAT.lower()
        for termo in ("x then y", "selig", "lednicer", "chord", ".dat", ".csv"):
            with self.subTest(termo=termo):
                self.assertIn(termo, dica)

    def test_dica_do_importador_de_polar_diz_colunas_linhas_e_blocos(self):
        """The old hint was "imports a polar CSV" -- someone who never saw
        the format had no way to build the file. The entire contract
        (required columns, what is a line, how to declare a sweep) must be
        written."""
        dica = self.aba._DICA_DE_IMPORTAR_CSV
        for termo in ("alpha_deg", "Cl", "Cd", "r_norm", "reynolds", "mach",
                      "ONE LINE = ONE ANGLE OF ATTACK", "ONE BLOCK = ONE COMBINATION"):
            with self.subTest(termo=termo):
                self.assertIn(termo, dica)

    def test_dica_da_polar_lista_os_apelidos_que_o_importador_aceita(self):
        """The alternative column names are those from
        `airfoils._COLUMN_ALIASES` -- if one stops being accepted, the hint
        stops being true."""
        dica = self.aba._DICA_DE_IMPORTAR_CSV
        for apelido in ("aoa", "r/R", "Re", "M"):
            with self.subTest(apelido=apelido):
                self.assertIn(apelido, dica)
                self.assertTrue(
                    any(apelido in aliases
                        for aliases in airfoils._COLUMN_ALIASES.values()),
                    f"the hint promises the alias {apelido!r}, which the importer does not accept")

    def test_catalogo_de_naca_entra_na_dica_do_campo(self):
        """The note for each preset ("what is typical for") was the only
        content the removed combo added -- it survives in the field help,
        derived from the SAME catalog."""
        from zbemt.gui.tabs.airfoil import _CATALOGO_DE_NACA_EM_TEXTO
        dica = _CATALOGO_DE_NACA_EM_TEXTO()
        for dados in airfoils.AIRFOIL_PRESETS.values():
            with self.subTest(codigo=dados["code"]):
                self.assertIn(dados["code"], dica)


class TestEnvelopeSugerido(unittest.TestCase):
    """The suggestion calculation -- pure function, no GUI."""

    def test_avanco_entra_na_conta(self):
        from zbemt import geometry
        geom = geometry.generate_tapered(radius_m=8.0, n_stations=12)
        pairado = airfoils.suggest_reynolds_mach_lists(geom, 300.0, mu_x=0.0)
        avancando = airfoils.suggest_reynolds_mach_lists(geom, 300.0, mu_x=0.4)
        self.assertGreater(max(avancando["mach"]), max(pairado["mach"]))
        self.assertGreater(max(avancando["reynolds"]), max(pairado["reynolds"]))


@unittest.skipUnless(_HAS_QT, "sem PyQt6")
class TestCompressibilidadeDisponivel(_JanelaDeTeste):
    """The Prandtl-Glauert correction is only blocked when the polar IN USE
    already brings Mach as given. Before the condition only looked at the
    imported slices -- which remain stored when changing source --, so it was
    enough to pass through 'table' with a table swept in Mach for the toggle
    to stay gray forever, even in 'analytical', where no table is consulted."""

    def _tabela_varrida_em_mach(self):
        from zbemt.models import PolarSlice
        return [PolarSlice(alpha_deg=[0, 5], cl=[0.0, 0.5], cd=[0.01, 0.02], mach=m)
                for m in (0.1, 0.5)]

    def test_bloqueia_em_table_e_volta_em_analytical(self):
        aba = self.aba
        caixa = aba.cfg_use_compressibility
        aba._imported_slices = self._tabela_varrida_em_mach()

        aba.source_combo.setCurrentText("table")
        self.assertFalse(caixa.isEnabled(), "tabela varrida em Mach deve bloquear")

        aba.source_combo.setCurrentText("analytical")
        self.assertTrue(caixa.isEnabled(),
                        "in 'analytical' no table is consulted: nothing to lock")

    def test_valor_do_usuario_volta_ao_reabilitar(self):
        """Blocking unchecks the box; without restoring the value, the
        user's choice would be lost in a source back-and-forth."""
        aba = self.aba
        caixa = aba.cfg_use_compressibility
        caixa.setChecked(True)
        aba._imported_slices = self._tabela_varrida_em_mach()

        aba.source_combo.setCurrentText("table")
        self.assertFalse(caixa.isChecked())
        aba.source_combo.setCurrentText("analytical")
        self.assertTrue(caixa.isChecked())

    def test_tabela_sem_varredura_em_mach_nao_bloqueia(self):
        from zbemt.models import PolarSlice
        aba = self.aba
        aba._imported_slices = [
            PolarSlice(alpha_deg=[0, 5], cl=[0.0, 0.5], cd=[0.01, 0.02], reynolds=1e5),
            PolarSlice(alpha_deg=[0, 5], cl=[0.0, 0.5], cd=[0.01, 0.02], reynolds=5e5),
        ]
        aba.source_combo.setCurrentText("table")
        self.assertTrue(aba.cfg_use_compressibility.isEnabled())

    def test_tooltip_bloqueado_mantem_o_nome_do_campo(self):
        """`field_help` derives the field name from the first quoted token
        in the tooltip: if the blocking text replaced it, the help popup would
        disappear along with availability."""
        aba = self.aba
        aba._imported_slices = self._tabela_varrida_em_mach()
        aba.source_combo.setCurrentText("table")
        self.assertIn('"use_compressibility"', aba.cfg_use_compressibility.toolTip())


@unittest.skipUnless(_HAS_QT, "sem PyQt6")
class TestSugestaoDeReynoldsMach(_JanelaDeTeste):
    """The NeuralFoil suggestion follows the operating point -- before it was
    calculated once when entering the mode and fell behind."""

    def test_mu_de_referencia_e_o_maior_das_condicoes(self):
        """An envelope that does not cover the fastest condition in the
        project is useless."""
        from zbemt.models import FlightCondition
        aba, state = self.aba, self.state
        state.project.saved_cases = [
            FlightCondition(name="a", mu_x=0.1, rpm=600.0),
            FlightCondition(name="b", mu_x=0.35, rpm=600.0),
        ]
        self.assertAlmostEqual(aba._mu_de_referencia(), 0.35)

    def test_sem_condicao_nenhuma_assume_pairagem(self):
        aba = self.aba
        self.assertEqual(aba._mu_de_referencia(), 0.0)

    def test_mudanca_de_geometria_redesenha_a_sugestao(self):
        aba, state = self.aba, self.state
        aba.source_combo.setCurrentText("neuralfoil")
        antes = aba.re_list_edit.text()
        state.project.geometry.radius_m *= 2.0
        state.notify_geometry()
        self.assertNotEqual(aba.re_list_edit.text(), antes)

    def test_lista_digitada_a_mao_e_respeitada(self):
        """The suggestion follows the project UNTIL the user types theirs."""
        aba, state = self.aba, self.state
        aba.source_combo.setCurrentText("neuralfoil")
        aba.re_list_edit.setText("1e5, 2e5")
        aba._on_re_mach_edited()
        state.project.geometry.radius_m *= 2.0
        state.notify_geometry()
        self.assertEqual(aba.re_list_edit.text(), "1e5, 2e5")


if __name__ == "__main__":
    unittest.main()
