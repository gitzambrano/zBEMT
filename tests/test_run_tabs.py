"""Regressions of the Run Case (items 19/20) and Run Batch (items 22/23)
tabs.

Items reported by the user:

* 19 -- the results table's labels did not follow LaTeX: the symbol
  ``C<sub>T</sub>`` from `api.SUMMARY_SYMBOLS` was flattened to ``"C_T"``,
  and the tooltip with the spelled-out name, although written, never
  appeared (the event filter was on the `QTableWidget`, and Qt delivers
  the mouse to the viewport).
* 20 -- the configuration echo stayed hidden behind a checkbox.
* 22 -- the Run Batch "Fixed values" box had rows starting at different
  x positions and spinboxes stretching to the end of the window.
* 23 -- "replace queue" seemed to do nothing (it works, but clicking the
  checkbox produced no visible feedback).

The layout tests here do NOT lock down pixels (that ages badly): they
lock down the property the user complained about -- same label column for
all rows, same right edge on the fields, width-limited field, some
visible text announcing the "Replace queue" checkbox's effect, and the
four action buttons at a single width (Run wider than them).
"""
from __future__ import annotations

import unittest

try:
    from PyQt6.QtCore import QPoint, Qt
    from PyQt6.QtGui import QPixmap
    from PyQt6.QtWidgets import QApplication, QFormLayout, QStyleOptionViewItem
    _HAS_QT = True
except Exception:                                       # pragma: no cover
    _HAS_QT = False

from tests import helpers


def _summary_de_exemplo() -> dict:
    """Minimal summary with one key from each family (condition,
    subscripted coefficient, dimensional, and configuration echo)."""
    return {
        "mu_x": 0.2, "collective_deg": 8.0, "rpm": 600.0,
        "CT": 0.0051, "CQ": 0.00042, "Thrust": 1234.5,
        "convergence_pct": 100.0, "solver": "newton",
        "cfg_Ne": 8, "cfg_Npsi": 12, "cfg_solver": "newton",
    }


@unittest.skipUnless(_HAS_QT, "sem PyQt6")
class TestRunCaseTabelaDeResultados(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def _aba(self):
        from zbemt.gui.common import AppState
        from zbemt.gui.tabs.run_case import RunCaseTab
        state = AppState()
        state.project = helpers.make_studies_project()
        aba = RunCaseTab(state)
        self.addCleanup(aba.deleteLater)
        aba.show()
        aba._show_summary(_summary_de_exemplo())
        return aba

    # --- item 19: symbol in rich text -------------------------------

    def test_rotulo_carrega_o_simbolo_em_html_para_o_delegado(self):
        """Before, the label's only data was ``"C_T"`` -- the subscript had
        been flattened and there was no way to recover it when painting."""
        from zbemt.gui.tabs.run_case import PAPEL_SIMBOLO_HTML
        aba = self._aba()
        rotulos = [aba.results_table.item(i, 0).text()
                   for i in range(aba.results_table.rowCount())]
        linha = rotulos.index("C_T")
        item = aba.results_table.item(linha, 0)
        # plain text stays in the display role (copy/paste and the rest
        # of the suite depend on it)
        self.assertEqual(item.text(), "C_T")
        self.assertEqual(item.data(PAPEL_SIMBOLO_HTML), "C<sub>T</sub>")

    def test_unidade_do_rotulo_tambem_vem_em_html(self):
        """``N&middot;m`` has to reach the rich document as an entity and
        the plain text as a character."""
        from zbemt.gui.tabs.run_case import PAPEL_SIMBOLO_HTML
        aba = self._aba()
        aba._show_summary({"Torque": 12.0})
        item = aba.results_table.item(1, 0)
        self.assertEqual(item.text(), "Q [N·m]")
        self.assertEqual(item.data(PAPEL_SIMBOLO_HTML), "Q [N&middot;m]")

    def test_cabecalho_de_grupo_nao_tem_html(self):
        """Header is plain bold text: with no HTML role, it falls back to
        the default delegate."""
        from zbemt.gui.tabs.run_case import PAPEL_SIMBOLO_HTML
        aba = self._aba()
        item = aba.results_table.item(0, 0)
        self.assertEqual(item.text(), "Flight condition")
        self.assertIsNone(item.data(PAPEL_SIMBOLO_HTML))

    def test_delegado_pinta_o_subscrito_sem_o_texto_plano(self):
        """The delegate has to actually paint (and not leave ``C_T``
        underneath): we compare the rendering of ``C<sub>T</sub>`` with
        that of the plain text ``C_T`` in the same rectangle -- they have
        to differ."""
        from zbemt.gui.tabs.run_case import _DelegadoSimboloRico
        aba = self._aba()
        rotulos = [aba.results_table.item(i, 0).text()
                   for i in range(aba.results_table.rowCount())]
        linha = rotulos.index("C_T")
        indice = aba.results_table.model().index(linha, 0)
        delegado = aba.results_table.itemDelegateForColumn(0)
        self.assertIsInstance(delegado, _DelegadoSimboloRico)

        opcao = QStyleOptionViewItem()
        opcao.initFrom(aba.results_table)
        opcao.rect = aba.results_table.visualRect(indice)
        self.assertTrue(opcao.rect.isValid())

        from PyQt6.QtGui import QPainter
        imagens = []
        for alvo in (indice, aba.results_table.model().index(0, 0)):
            pix = QPixmap(opcao.rect.size())
            pix.fill(Qt.GlobalColor.white)
            pintor = QPainter(pix)
            o = QStyleOptionViewItem(opcao)
            o.rect = pix.rect()
            delegado.paint(pintor, o, alvo)
            pintor.end()
            imagens.append(pix.toImage())
        # the symbol row and the header row cannot come out identical
        self.assertNotEqual(imagens[0], imagens[1])
        # and the symbol's rendering has to have painted pixels (not empty)
        img = imagens[0]
        pintados = sum(1 for x in range(img.width()) for y in range(img.height())
                       if img.pixelColor(x, y) != Qt.GlobalColor.white)
        self.assertGreater(pintados, 0, "the delegate did not paint anything")

    # --- item 19: instant tooltip ---------------------------------

    def test_tooltip_instalado_no_viewport_e_nao_no_widget(self):
        """Bug: the filter was on the `QTableWidget`. `QAbstractScrollArea`
        delivers Enter/MouseMove to the VIEWPORT, so with a real mouse the
        tooltip never appeared."""
        aba = self._aba()
        self.assertTrue(hasattr(aba.results_table.viewport(), "_instant_tooltip_filter"))
        self.assertFalse(hasattr(aba.results_table, "_instant_tooltip_filter"))

    def test_tooltip_traz_nome_por_extenso_unidade_e_chave(self):
        aba = self._aba()
        rotulos = [aba.results_table.item(i, 0).text()
                   for i in range(aba.results_table.rowCount())]
        linha = rotulos.index("C_T")
        y = aba.results_table.rowViewportPosition(linha) + 2
        dica = aba._tooltip_da_linha(QPoint(5, y))
        self.assertIn("Thrust coefficient", dica)     # spelled-out name
        self.assertIn("summary key: CT", dica)        # bridge to the CSV/report
        self.assertIn("C<sub>T</sub>", dica)

    def test_tooltip_de_cabecalho_de_grupo_e_none(self):
        aba = self._aba()
        y = aba.results_table.rowViewportPosition(0) + 2
        self.assertIsNone(aba._tooltip_da_linha(QPoint(5, y)))

    # --- item 20: no configuration echo toggle --------------------

    def test_eco_de_configuracao_sempre_visivel(self):
        aba = self._aba()
        rotulos = [aba.results_table.item(i, 0).text()
                   for i in range(aba.results_table.rowCount())]
        self.assertIn("N_e", rotulos, "cfg_* deveria aparecer sem nenhum toggle")
        self.assertIn("Configuration echo (cfg_*)", rotulos)
        self.assertFalse(hasattr(aba, "show_cfg_check"),
                         "the config-echo toggle was removed (item 20)")


@unittest.skipUnless(_HAS_QT, "sem PyQt6")
class TestRunBatchCaixaDeFixos(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def _aba(self):
        from zbemt.gui.common import AppState
        from zbemt.gui.tabs.run_batch import RunBatchTab
        state = AppState()
        state.project = helpers.make_studies_project()
        aba = RunBatchTab(state)
        self.addCleanup(aba.deleteLater)
        aba.resize(1200, 900)
        aba.show()
        for _ in range(5):
            self.app.processEvents()
        return aba

    # --- item 22 -------------------------------------------------------

    def test_todos_os_campos_fixos_estao_na_coluna_de_campo(self):
        """Bug: advance and axial went in as a SPANNING row (no label),
        starting at the margin, while Collective/RPM started in the field
        column -- hence the feeling that everything was misaligned.

        The contract is "each field occupies the FIELD column of a row
        with a label", not "the column's widget is the spin itself":
        Collective and RPM come in wrapped by `_com_recuo_de_unidade`
        (item 11/4), which indents them to the compound fields' number
        column. The wrapper is declared in `_container_de_ajuda` -- the
        same mark that `common.definir_linha_visivel` consults --, so
        that is what is asked when determining which widget represents
        the field.
        """
        aba = self._aba()
        form = aba._fixed_form
        campos = set()
        for r in range(form.rowCount()):
            item = form.itemAt(r, QFormLayout.ItemRole.FieldRole)
            rotulo = form.itemAt(r, QFormLayout.ItemRole.LabelRole)
            self.assertIsNotNone(item, f"row {r} is still spanning (no label)")
            self.assertIsNotNone(rotulo, f"row {r} has no label in the label column")
            campos.add(item.widget())
        esperados = [aba.fixed_advance, aba.fixed_axial,
                     aba.fixed_collective, aba.fixed_rpm]
        na_coluna = [getattr(w, "_container_de_ajuda", None) or w for w in esperados]
        for widget, ocupante in zip(esperados, na_coluna):
            self.assertIn(ocupante, campos,
                          f"{widget} is not in the form's field column")

        # same column: all fields start at the same x inside the box
        caixa = aba.fixed_advance.parentWidget()
        xs = {w.mapTo(caixa, w.rect().topLeft()).x() for w in na_coluna}
        self.assertEqual(len(xs), 1, f"fields starting at different x: {xs}")

    def test_o_recuo_dos_campos_simples_nao_quebra_a_ajuda_de_campo(self):
        """The field column's widget is where `field_help` and
        `tools/field_index.py` read the `.bemt` field name from (via the
        tooltip). Wrapping the spin without carrying the tooltip along
        would silently drop Collective/RPM from the field index and from
        the row's "?" help."""
        from zbemt.gui.field_help import _campo_do_widget

        aba = self._aba()
        for spin, esperado in ((aba.fixed_collective, "collective_deg"),
                               (aba.fixed_rpm, "rpm"),
                               (aba.collective_spin, "collective_deg"),
                               (aba.rpm_spin, "rpm")):
            container = getattr(spin, "_container_de_ajuda", None)
            self.assertIsNotNone(container, "campo simples deveria estar recuado")
            self.assertEqual(_campo_do_widget(container), esperado)

    def test_campos_numericos_nao_ocupam_a_largura_toda(self):
        """"an enormous field to fill in (takes up the whole screen)": the
        spinbox grew with the form."""
        aba = self._aba()
        caixa = aba.fixed_advance.parentWidget()
        for widget in (aba.fixed_collective, aba.fixed_rpm,
                       aba.fixed_advance.spin, aba.fixed_axial.spin):
            self.assertLessEqual(widget.width(), aba._LARGURA_VALOR)
            self.assertLess(widget.width(), caixa.width() / 2)

    def test_esconder_linha_de_fixo_continua_funcionando(self):
        """The box now has labels; `definir_linha_visivel` still has to
        hide FIELD AND LABEL when the quantity becomes an axis."""
        aba = self._aba()
        i_coletivo = [i for i, (_l, s) in enumerate(aba._AXIS_SLOTS)
                      if s == "collective_deg"][0]
        aba.axis_rows[0][0].setCurrentIndex(i_coletivo)
        self.assertFalse(aba.fixed_collective.isVisible())
        self.assertTrue(aba.fixed_rpm.isVisible())
        aba.axis_rows[0][0].setCurrentIndex(0)
        self.assertTrue(aba.fixed_collective.isVisible())

    # --- item 23 -------------------------------------------------------

    def test_um_eco_anuncia_o_efeito_da_caixa_substituir(self):
        """The "Replace queue" checkbox does nothing when clicked -- it
        only changes what the button will do afterward. With no
        immediate feedback it reads as broken (item 23).

        The announcement used to be in the button's text; with the
        button's label reduced to the action's name (item 5), it moved
        to the echo next to the checkbox. What the test locks down is
        the INVARIANT of item 23 -- clicking the checkbox instantly
        changes a visible text that says which of the two effects
        applies --, not where that text lives.
        """
        aba = self._aba()
        eco = aba.lbl_efeito_da_fila
        self.assertTrue(eco.isVisible())
        self.assertIn("REPLACES", eco.text())
        aba.check_substituir.setChecked(False)
        self.assertIn("APPENDS", eco.text())
        aba.check_substituir.setChecked(True)
        self.assertIn("REPLACES", eco.text())

    def test_modo_caso_a_caso_esconde_a_caixa_e_troca_o_botao(self):
        aba = self._aba()
        aba.radio_lista.setChecked(True)
        self.assertEqual(aba.modo_stack.currentIndex(), 1,
                         "checking the radio by code must also switch the panel")
        self.assertFalse(aba.check_substituir.isVisible())
        self.assertFalse(aba.lbl_efeito_da_fila.isVisible(),
                         "without a checkbox there is no effect to announce")
        self.assertIn("Add Case", aba.btn_gerar.text())

    def test_substituir_e_acumular_fazem_o_que_dizem(self):
        aba = self._aba()
        i_coletivo = [i for i, (_l, s) in enumerate(aba._AXIS_SLOTS)
                      if s == "collective_deg"][0]
        aba.axis_rows[0][0].setCurrentIndex(i_coletivo)
        aba.axis_rows[0][2].setText("4, 6, 8")

        aba._gerar_casos()
        self.assertEqual(aba.batch_table.rowCount(), 3)
        aba._gerar_casos()
        self.assertEqual(aba.batch_table.rowCount(), 3, "replace deveria substituir")
        aba.check_substituir.setChecked(False)
        aba._gerar_casos()
        self.assertEqual(aba.batch_table.rowCount(), 6, "append deveria acumular")
        aba.check_substituir.setChecked(True)
        aba._gerar_casos()
        self.assertEqual(aba.batch_table.rowCount(), 3)
        # the queue is still the single source of what runs
        self.assertEqual(len(aba._condicoes_da_fila()), 3)


@unittest.skipUnless(_HAS_QT, "sem PyQt6")
class TestRunBatchModoDeExecucaoNaEtapa1(unittest.TestCase):
    """Item 12 -- the three run modes lived in step "3. Run", far from
    the fields they make (ir)relevant: it was possible to build an RPM
    axis and only later find out, three boxes below, that RPM was going
    to be RESOLVED by the trim loop and the whole axis would be
    ignored."""

    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def _aba(self):
        from zbemt.gui.common import AppState
        from zbemt.gui.tabs.run_batch import RunBatchTab
        state = AppState()
        state.project = helpers.make_studies_project()
        aba = RunBatchTab(state)
        self.addCleanup(aba.deleteLater)
        aba.resize(1200, 900)
        aba.show()
        for _ in range(5):
            self.app.processEvents()
        return aba

    def _titulo_da_caixa(self, widget):
        from PyQt6.QtWidgets import QGroupBox
        pai = widget.parentWidget()
        while pai is not None and not isinstance(pai, QGroupBox):
            pai = pai.parentWidget()
        return pai.title() if pai is not None else None

    def test_o_seletor_de_modo_esta_na_etapa_1(self):
        aba = self._aba()
        self.assertTrue(self._titulo_da_caixa(aba.run_mode_combo).startswith("1."))
        self.assertTrue(self._titulo_da_caixa(aba.trim_target_value).startswith("1."))

    def test_etapa_3_so_tem_a_execucao(self):
        """Step 3 keeps what is actually about running: button, progress,
        cancel (and the echo of the mode chosen in step 1)."""
        aba = self._aba()
        self.assertTrue(self._titulo_da_caixa(aba.btn_run).startswith("3."))
        self.assertFalse(hasattr(aba, "batch_run_mode"))
        self.assertFalse(hasattr(aba, "batch_trim_dof"))
        self.assertFalse(hasattr(aba, "batch_trim_target"))

    def test_alvo_aparece_so_quando_ha_trimagem(self):
        aba = self._aba()
        self.assertFalse(aba.trim_target_value.isVisible())
        aba.run_mode_combo.setCurrentText("Fixed RPM, target thrust/CT")
        self.assertTrue(aba.trim_target_value.isVisible())
        self.assertTrue(aba.trim_target_kind_combo.isVisible())
        aba.run_mode_combo.setCurrentText("Fixed collective & RPM")
        self.assertFalse(aba.trim_target_value.isVisible())

    def test_a_grandeza_resolvida_deixa_de_ser_oferecida_como_fixo(self):
        """"solve collective" resolves the collective: it is OUTPUT, and
        cannot remain a case input field."""
        aba = self._aba()
        aba.run_mode_combo.setCurrentText("Fixed RPM, target thrust/CT")
        self.assertFalse(aba.fixed_collective.isVisible())
        self.assertTrue(aba.fixed_rpm.isVisible())
        self.assertFalse(aba.collective_spin.isVisible(), "case-by-case mode too")
        aba.run_mode_combo.setCurrentText("Fixed collective, target thrust/CT")
        self.assertTrue(aba.fixed_collective.isVisible())
        self.assertFalse(aba.fixed_rpm.isVisible())
        aba.run_mode_combo.setCurrentText("Fixed collective & RPM")
        self.assertTrue(aba.fixed_collective.isVisible())
        self.assertTrue(aba.fixed_rpm.isVisible())

    def test_a_grandeza_resolvida_deixa_de_ser_oferecida_como_eixo(self):
        aba = self._aba()
        i_rpm = [i for i, (_l, s) in enumerate(aba._AXIS_SLOTS) if s == "rpm"][0]
        aba.axis_rows[0][0].setCurrentIndex(i_rpm)
        aba.axis_rows[0][2].setText("500, 600")
        aba.run_mode_combo.setCurrentText("Fixed collective, target thrust/CT")
        # the item disappears from the lists...
        self.assertFalse(aba.axis_rows[1][0].model().item(i_rpm).isEnabled())
        # ...and the axis that was already on it reverts to "(none)"
        self.assertEqual(aba.axis_rows[0][0].currentIndex(), 0)
        self.assertEqual(aba._active_axes(), [])

    def test_trim_spec_preserva_as_mesmas_combinacoes_de_antes(self):
        """GUI/.bemt/CLI parity: the dict handed to `studies.run_batch`
        is the same one as before the layout change."""
        aba = self._aba()
        self.assertIsNone(aba._trim_spec())
        aba.run_mode_combo.setCurrentText("Fixed RPM, target thrust/CT")
        aba.trim_target_kind_combo.setCurrentText("CT [-]")
        aba.trim_target_value.setValue(0.005)
        self.assertEqual(aba._trim_spec(), {"trim_mode": "solve_collective",
                                            "target_kind": "CT", "target_value": 0.005})
        aba.run_mode_combo.setCurrentText("Fixed collective, target thrust/CT")
        aba.trim_target_kind_combo.setCurrentText("Thrust [N]")
        aba.trim_target_value.setValue(1200.0)
        self.assertEqual(aba._trim_spec(), {"trim_mode": "solve_rpm",
                                            "target_kind": "thrust", "target_value": 1200.0})


@unittest.skipUnless(_HAS_QT, "sem PyQt6")
class TestRunBatchFaixaDosGeradores(unittest.TestCase):
    """Item 25 -- from/to/step did not track the axis's quantity: with
    "Disk angle (alpha / Vz)" + "alpha [deg]", the "fill" button wrote
    ``0, 0.1, ... 1`` -- advance ratio numbers, absurd as degrees."""

    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def _aba(self):
        from zbemt.gui.common import AppState
        from zbemt.gui.tabs.run_batch import RunBatchTab
        state = AppState()
        state.project = helpers.make_studies_project()
        aba = RunBatchTab(state)
        self.addCleanup(aba.deleteLater)
        aba.resize(1200, 900)
        aba.show()
        for _ in range(5):
            self.app.processEvents()
        return aba

    def _escolher(self, aba, slot: str, unidade: str | None = None):
        i = [k for k, (_l, s) in enumerate(aba._AXIS_SLOTS) if s == slot][0]
        aba.axis_rows[0][0].setCurrentIndex(i)
        if unidade is not None:
            aba.axis_rows[0][1].setCurrentText(unidade)
        return aba.axis_rows[0]

    def _preencher(self, aba):
        _sc, _uc, ve = aba.axis_rows[0]
        aba._preencher_valores_do_eixo(0)
        return [float(t) for t in ve.text().split(",") if t.strip()]

    def test_alpha_gera_graus_e_nao_razao_de_avanco(self):
        aba = self._aba()
        self._escolher(aba, "axial", "alpha [deg]")
        valores = self._preencher(aba)
        self.assertGreaterEqual(max(valores), 5.0,
                                f"0..1 degree is not a disk-angle sweep: {valores}")
        self.assertLessEqual(max(valores), 90.0)
        self.assertLessEqual(min(valores), -1.0, "negative disk angle is the usual case")

    def test_rpm_gera_centenas_e_nao_decimos(self):
        aba = self._aba()
        self._escolher(aba, "rpm")
        valores = self._preencher(aba)
        self.assertGreaterEqual(max(valores), 100.0, f"RPM does not live in 0..1: {valores}")

    def test_faixa_do_spin_acompanha_a_grandeza(self):
        aba = self._aba()
        self._escolher(aba, "axial", "alpha [deg]")
        de, ate, passo = aba._widgets_de_faixa(0)
        self.assertLessEqual(ate.maximum(), 90.0, "alpha does not exceed 90 degrees")
        self._escolher(aba, "rpm")
        de, ate, passo = aba._widgets_de_faixa(0)
        self.assertGreaterEqual(ate.maximum(), 10000.0, "RPM precisa de milhares")

    def test_combo_de_slot_vazio_nao_vira_o_ultimo_slot(self):
        """`self._AXIS_SLOTS[combo.currentIndex()]` with currentIndex()==-1
        indexes backward and silently returns the LAST slot (RPM) -- an
        axis the user never chose.

        Reading the slot is exercised via `_slot_do_combo`, and NOT by
        calling `QComboBox.clear()` on a combo already wired to the tab's
        signals: that `clear()` crashes the process with a native failure
        (no Python exception) inside Qt itself, when emitting
        `currentIndexChanged(-1)` while the model is being emptied. It is
        Qt fragility in the signal path, not this tab's code -- and the
        GUI never empties this combo; the real -1 shows up through other
        paths. Reproducing the crash here would only kill the whole suite
        without covering anything more.
        """
        from PyQt6.QtWidgets import QComboBox

        aba = self._aba()
        vazio = QComboBox()                     # loose: no signals wired
        self.assertEqual(vazio.currentIndex(), -1)
        self.assertIsNone(aba._slot_do_combo(vazio),
                          "empty combo defines no axis at all")
        # And an index outside the table does not accidentally become a
        # slot either.
        fora = QComboBox()
        fora.addItems([f"x{i}" for i in range(len(aba._AXIS_SLOTS) + 3)])
        fora.setCurrentIndex(fora.count() - 1)
        self.assertIsNone(aba._slot_do_combo(fora))
        # The normal path still returns the right slot.
        sc, _uc, _ve = aba.axis_rows[0]
        i_rpm = [i for i, (_l, s) in enumerate(aba._AXIS_SLOTS) if s == "rpm"][0]
        sc.setCurrentIndex(i_rpm)
        self.assertEqual(aba._slot_do_combo(sc), "rpm")


@unittest.skipUnless(_HAS_QT, "sem PyQt6")
class TestRunBatchAlinhamentoDosCampos(unittest.TestCase):
    """Item 11 -- the Advance/Axial flow/Collective/RPM rows ended at
    different x positions (the two compound ones carry the unit combo
    before the number). The test locks down the requested INVARIANT --
    same right edge --, never a width in pixels."""

    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def _aba(self):
        from zbemt.gui.common import AppState
        from zbemt.gui.tabs.run_batch import RunBatchTab
        state = AppState()
        state.project = helpers.make_studies_project()
        aba = RunBatchTab(state)
        self.addCleanup(aba.deleteLater)
        aba.resize(1200, 900)
        aba.show()
        for _ in range(5):
            self.app.processEvents()
        return aba

    def _bordas(self, aba, campos):
        caixa = aba
        bordas = set()
        for campo in campos:
            spin = getattr(campo, "spin", campo)
            x = spin.mapTo(caixa, spin.rect().topRight()).x()
            bordas.add(x)
        return bordas

    def _bordas_esquerdas(self, aba, campos):
        return {
            getattr(campo, "spin", campo).mapTo(
                aba, getattr(campo, "spin", campo).rect().topLeft()).x()
            for campo in campos
        }

    # Solved by `RunBatchTab._com_recuo_de_unidade`: the simple fields
    # (Collective/RPM) come in wrapped, with a left margin equal to the
    # unit combo's width plus the compound fields' internal spacing, so
    # that the NUMBER of the four rows lands in the same column.
    # Indent, not widen: a spin wide enough to hit the compound fields'
    # edge would be the opposite defect -- see
    # `test_campos_numericos_nao_ocupam_a_largura_toda`.
    def test_bordas_direitas_alinhadas_nos_fixos(self):
        aba = self._aba()
        bordas = self._bordas(aba, [aba.fixed_advance, aba.fixed_axial,
                                    aba.fixed_collective, aba.fixed_rpm])
        self.assertEqual(len(bordas), 1, f"bordas direitas desalinhadas: {sorted(bordas)}")
        esquerdas = self._bordas_esquerdas(
            aba, [aba.fixed_advance, aba.fixed_axial,
                  aba.fixed_collective, aba.fixed_rpm])
        self.assertEqual(len(esquerdas), 1,
                         f"bordas esquerdas desalinhadas: {sorted(esquerdas)}")

    # Same indent, in the case-by-case mode panel (see comment above).
    def test_bordas_direitas_alinhadas_no_caso_a_caso(self):
        aba = self._aba()
        aba.radio_lista.setChecked(True)
        for _ in range(5):
            self.app.processEvents()
        bordas = self._bordas(aba, [aba.add_row_advance, aba.add_row_axial,
                                    aba.collective_spin, aba.rpm_spin])
        self.assertEqual(len(bordas), 1, f"bordas direitas desalinhadas: {sorted(bordas)}")

    def test_campos_recuados_continuam_estreitos(self):
        """The indent is POSITION, not width: if one day it turns into a
        bigger `setFixedWidth`, the edges line up and this whole file
        stays green -- except here."""
        aba = self._aba()
        for spin in (aba.fixed_collective, aba.fixed_rpm,
                     aba.collective_spin, aba.rpm_spin):
            self.assertLessEqual(spin.width(), aba._LARGURA_VALOR)


@unittest.skipUnless(_HAS_QT, "sem PyQt6")
class TestRunCaseAlinhamentoDosCampos(unittest.TestCase):
    """Run Case uses the same numeric column for the four controls."""

    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def test_bordas_direitas_alinhadas(self):
        from zbemt.gui.common import AppState
        from zbemt.gui.tabs.run_case import RunCaseTab
        state = AppState()
        state.project = helpers.make_studies_project()
        aba = RunCaseTab(state)
        self.addCleanup(aba.deleteLater)
        aba.resize(900, 700)
        aba.show()
        for _ in range(5):
            self.app.processEvents()
        bordas = {
            getattr(campo, "spin", campo).mapTo(
                aba, getattr(campo, "spin", campo).rect().topRight()).x()
            for campo in (aba.advance, aba.axial, aba.collective_spin, aba.rpm_spin)
        }
        self.assertEqual(len(bordas), 1,
                         f"bordas direitas desalinhadas: {sorted(bordas)}")
        esquerdas = {
            getattr(campo, "spin", campo).mapTo(
                aba, getattr(campo, "spin", campo).rect().topLeft()).x()
            for campo in (aba.advance, aba.axial, aba.collective_spin, aba.rpm_spin)
        }
        self.assertEqual(len(esquerdas), 1,
                         f"bordas esquerdas desalinhadas: {sorted(esquerdas)}")


@unittest.skipUnless(_HAS_QT, "sem PyQt6")
class TestRunBatchLarguraDosBotoes(unittest.TestCase):
    """Item 5 -- "these 4 buttons should have the same width and Run
    Cases should be bigger". The test locks down the requested RELATION
    (equal among themselves, Run bigger than them), never a width in
    pixels: the number depends on the font."""

    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def _aba(self):
        from zbemt.gui.common import AppState, garantir_botoes_legiveis
        from zbemt.gui.tabs.run_batch import RunBatchTab
        state = AppState()
        state.project = helpers.make_studies_project()
        aba = RunBatchTab(state)
        self.addCleanup(aba.deleteLater)
        # The real window calls this after mounting the tab; without it
        # the test would not see the readability floor competing with
        # the common width.
        garantir_botoes_legiveis(aba)
        aba.resize(1200, 900)
        aba.show()
        for _ in range(5):
            self.app.processEvents()
        return aba

    def test_os_quatro_botoes_de_acao_tem_a_mesma_largura(self):
        aba = self._aba()
        larguras = {b.width() for b in aba.botoes_de_acao()}
        self.assertEqual(len(larguras), 1,
                         "larguras diferentes: "
                         + str({b.text(): b.width() for b in aba.botoes_de_acao()}))

    def test_run_e_mais_largo_que_os_quatro(self):
        aba = self._aba()
        comum = aba.btn_gerar.width()
        self.assertGreater(aba.btn_run.width(), comum)

    def test_run_continua_maior_com_a_fila_cheia(self):
        """The Run label grows with the count ("Run 12 case(s)"): the
        width is a minimum, not a fixed value that would elide the
        text."""
        aba = self._aba()
        i_coletivo = [i for i, (_l, s) in enumerate(aba._AXIS_SLOTS)
                      if s == "collective_deg"][0]
        aba.axis_rows[0][0].setCurrentIndex(i_coletivo)
        aba.axis_rows[0][2].setText("4, 6, 8, 10, 12")
        aba._gerar_casos()
        for _ in range(5):
            self.app.processEvents()
        self.assertGreater(aba.btn_run.width(), aba.btn_gerar.width())
        largura_do_texto = aba.btn_run.fontMetrics().horizontalAdvance(
            aba.btn_run.text())
        self.assertGreater(aba.btn_run.width(), largura_do_texto,
                           "Run label does not fit the button")

    def test_o_botao_de_gerar_nao_muda_de_largura_com_o_modo(self):
        aba = self._aba()
        antes = aba.btn_gerar.width()
        aba.radio_lista.setChecked(True)
        for _ in range(5):
            self.app.processEvents()
        self.assertEqual(aba.btn_gerar.width(), antes)


if __name__ == "__main__":
    unittest.main()


@unittest.skipUnless(_HAS_QT, "sem PyQt6")
class TestRunCaseAlinhadoComOResumo(unittest.TestCase):
    """Item 12: the Run Case table, the Results tab's table, and the HTML
    report must show the SAME quantities, in the SAME order.

    Before, this tab kept its own opinion on both things: its own order
    in "Condition" (mu_x, J_x, Vz, J_z, alpha...) and a REDUCED set -- a
    project in rotor mode saw no propeller coefficients, one in propeller
    mode saw neither FM nor the hub coefficients, and neither saw
    mu_x/J_x/mu_z/lambda_z. The engine always computes all of this; the
    report and the CSV always show all of this.
    """

    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def _aba(self, propeller: bool = False):
        from zbemt.gui.common import AppState
        from zbemt.gui.tabs.run_case import RunCaseTab
        state = AppState()
        projeto = helpers.make_studies_project()
        projeto.config["is_propeller"] = propeller
        state.project = projeto
        aba = RunCaseTab(state)
        self.addCleanup(aba.deleteLater)
        return aba

    def _chaves_exibidas(self, aba, summary: dict) -> list:
        aba._show_summary(summary)
        return [k for k in aba._row_keys if k is not None]

    def _summary_real(self) -> dict:
        from zbemt import api
        from zbemt.models import FlightCondition
        projeto = helpers.make_studies_project()
        return api.run_case(projeto, FlightCondition(
            name="c", mu_x=0.15, Vz=3.0, collective_deg=8.0, rpm=1200.0)).summary

    def test_nenhuma_grandeza_de_saida_fica_de_fora(self):
        """"The SAME fields" on all three surfaces: everything that is
        not `cfg_*` shows up -- minus `rotor_rpm`, which is `rpm` again,
        and minus the angle of the OTHER convention: `alpha_rotor_deg`
        (measured from the disk plane) and `alpha_disk_deg` (measured
        from the shaft) describe the same condition in mutually exclusive
        references -- the engine always computes both, but only one
        makes physical sense per mode (rotor shows alpha_rotor, propeller
        shows alpha_disk), and that is how `common._ROTULOS_DE_CONDICAO`
        treats the pair too."""
        from zbemt import api
        summary = self._summary_real()
        esperado_base = {k for k in summary
                          if not k.startswith("cfg_") and k != "rotor_rpm"}
        for propeller in (False, True):
            with self.subTest(propeller=propeller):
                irrelevante = "alpha_rotor_deg" if propeller else "alpha_disk_deg"
                esperado = esperado_base - {irrelevante}
                exibidas = set(self._chaves_exibidas(self._aba(propeller), summary))
                self.assertEqual(esperado - exibidas, set())
        self.assertTrue(esperado_base <= set(api.SUMMARY_PRIMARY_KEYS))

    def test_ordem_dentro_de_cada_grupo_segue_o_resumo(self):
        """The grouping is this tab's decision (and the group order
        changes between rotor and propeller), but the order WITHIN each
        group is that of `api.SUMMARY_PRIMARY_KEYS` -- otherwise there
        would again be two opinions."""
        from zbemt import api
        from zbemt.gui.tabs.run_case import RunCaseTab
        primaria = {k: i for i, k in enumerate(api.SUMMARY_PRIMARY_KEYS)}
        for propeller in (False, True):
            for titulo, chaves in RunCaseTab._montar_grupos(propeller):
                with self.subTest(propeller=propeller, grupo=titulo):
                    indices = [primaria[k] for k in chaves if k in primaria]
                    self.assertEqual(indices, sorted(indices))

    def test_condicao_abre_pela_componente_x_e_sem_repetir(self):
        """x first (the PRIMARY one in both modes), then z, then the
        angles. And each quantity ONCE: `mu_x`/`J_x` used to appear
        twice while the engine had two keys for the same number."""
        from zbemt.gui.tabs.run_case import RunCaseTab
        chaves = dict(RunCaseTab._montar_grupos(False))["Flight condition"]
        self.assertEqual(
            chaves,
            ["mu_x", "J_x", "Vx",
             "mu_z", "J_z", "Vz", "lambda_z",
             "alpha_rotor_deg", "alpha_disk_deg",
             "collective_deg", "rpm"])
        self.assertEqual(len(chaves), len(set(chaves)), "grandeza repetida")

    def test_triade_de_inflow_tem_grupo_proprio(self):
        """lambda_i / lambda / v_i / V_z did not exist in this table."""
        from zbemt.gui.tabs.run_case import RunCaseTab
        grupos = dict(RunCaseTab._montar_grupos(False))
        self.assertEqual(grupos["Inflow (solved)"],
                          ["lambda_i", "lambda_total", "Vi", "Vz_total"])


@unittest.skipUnless(_HAS_QT, "sem PyQt6")
class TestRunCaseBotoesDeCasoSalvo(unittest.TestCase):
    """Item 6: the Saved Cases buttons were "+ Save Current" and
    "- Remove" -- the graphic sign adds nothing to the verb, and
    "Current" repeats what the button already does by being on this
    tab."""

    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def test_botoes_sao_save_e_remove(self):
        from zbemt.gui.common import AppState
        from zbemt.gui.tabs.run_case import RunCaseTab
        from PyQt6.QtWidgets import QPushButton
        state = AppState()
        state.project = helpers.make_studies_project()
        aba = RunCaseTab(state)
        self.addCleanup(aba.deleteLater)
        textos = {b.text() for b in aba.findChildren(QPushButton)}
        self.assertIn("Save", textos)
        self.assertIn("Remove", textos)
        self.assertNotIn("+ Save Current", textos)
        self.assertNotIn("- Remove", textos)
