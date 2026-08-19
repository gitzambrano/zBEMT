"""
test_gui_layout.py
==================

LAYOUT defects that only appear with the window actually mounted --
none of them break a logic test, and all of them were seen on screen
before becoming a test here.

Deliberately does NOT check style pixels (exact width, color, font):
that ages badly and blocks the next redesign (CLAUDE.md, rule 3). What
is checked here is the *structural invariant*:

  * orphan label -- visible label whose field was hidden;
  * stretched field -- numeric/enum input stretched to the end of the
    form row (the ~1370px box to type "72");
  * mute field -- value widget without a tooltip, which as a
    consequence also does not get a clickable help label (`field_help`
    derives one from the other).
"""
from __future__ import annotations

import unittest

try:
    from PyQt6.QtWidgets import (
        QApplication, QAbstractSpinBox, QComboBox, QFormLayout, QGroupBox,
        QLabel, QLineEdit, QPlainTextEdit, QScrollArea, QStackedWidget,
        QTabWidget, QTextEdit, QToolButton,
    )
    _HAS_QT = True
except Exception:                                    # pragma: no cover
    _HAS_QT = False

if _HAS_QT:
    from zbemt.gui import styles

    #: Every widget through which the user enters a VALUE. The tooltip
    #: sweep uses this list instead of walking `QFormLayout`: seven real
    #: fields escaped the previous version by being text fields or by
    #: living in a `QHBoxLayout`.
    TIPOS_DE_CAMPO_DE_VALOR = (QAbstractSpinBox, QComboBox, QLineEdit,
                               QPlainTextEdit, QTextEdit)

    #: Where the search for "container that explains the field" must stop.
    AGRUPADORES_DE_TELA = (QGroupBox, QScrollArea, QStackedWidget, QTabWidget)


LARGURA_DE_JANELA = 1400

#: Fields whose content is free text of unpredictable size: stretching is
#: the right behavior there (folder path, list "0, 0.1, 0.2").
#: `compactar_campos_de_formulario` does not touch them, and neither does
#: this test.


def _e_campo_editavel(w) -> bool:
    """Discards what is not really an input field.

    An editable `QComboBox` and a `QAbstractSpinBox` contain an internal
    `QLineEdit` that the sweep would find as an independent field; and a
    read-only field is not where anything gets entered.
    """
    if isinstance(w, QLineEdit):
        if w.isReadOnly():
            return False
        pai = w.parentWidget()
        if isinstance(pai, (QComboBox, QAbstractSpinBox)):
            return False
    if isinstance(w, (QPlainTextEdit, QTextEdit)) and w.isReadOnly():
        return False
    return True


def _tem_explicacao(w, raiz) -> bool:
    """The widget explains itself, either on its own or via the container
    that composes it.

    A compound field (`widgets.LongitudinalInput`: unit dropdown +
    spinbox) is ONE field from the user's and `field_help`'s point of
    view -- the tooltip lives on the container, and requiring it from
    every internal piece would mean requiring the same sentence three
    times.
    """
    if (w.toolTip() or "").strip():
        return True
    atual = w.parentWidget()
    # The climb stops at the first SCREEN grouper: a tooltip on the
    # `QGroupBox` explains the block, not each field inside it, and
    # accepting it here would let an entire block of mute fields pass.
    while (atual is not None and atual is not raiz
           and not isinstance(atual, AGRUPADORES_DE_TELA)):
        if (atual.toolTip() or "").strip():
            return True
        atual = atual.parentWidget()
    return False


def _descrever_campo(w) -> str:
    """Identifies the field in the failure message (label, name or class)."""
    for atributo in ("placeholderText", "currentText", "objectName"):
        valor = getattr(w, atributo, None)
        texto = (valor() if callable(valor) else valor) or ""
        if texto:
            return f"{type(w).__name__} {texto!r}"
    return f"{type(w).__name__} without a label"


@unittest.skipUnless(_HAS_QT, "PyQt6 not available")
class TestLayoutDaJanelaMontada(unittest.TestCase):
    """Mounts the real `MainWindow` (not loose tabs): the width and field
    help adjustments are applied from OUTSIDE, by the window, so a tab
    instantiated alone would not have them and the test would pass by
    mistake."""

    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])
        cls.app.setStyle("Fusion")
        cls.app.setStyleSheet(styles.APP_QSS)

        from zbemt.gui.app import MainWindow
        cls.win = MainWindow()
        cls.win.resize(LARGURA_DE_JANELA, 900)
        cls.win.show()
        cls.app.processEvents()

    @classmethod
    def tearDownClass(cls):
        cls.win.close()

    def _abas(self):
        """Each tab with it ACTIVE in the `QTabWidget`.

        `QWidget.isVisible()` is false for everything in a tab that is not
        selected -- iterating the tabs without switching the current one
        makes every visibility test here pass vacuously (observed: the
        previous version of this file passed with the orphan-label bug
        deliberately reintroduced). Switching the tab is what gives the
        widgets real geometry and visibility.
        """
        for i in range(self.win.tabs.count()):
            self.win.tabs.setCurrentIndex(i)
            self.app.processEvents()
            yield self.win.tabs.tabText(i), self.win.tabs.widget(i)

    def test_nenhum_rotulo_fica_orfao_do_proprio_campo(self):
        """Real bug: in "Run Batch" > "3. Run", the "Entered values" mode
        hid the trim fields with `setVisible(False)` -- which hides only
        the FIELD. "Trim variable:" and "Target:" stayed on screen
        pointing at nothing. `common.definir_linha_visivel` exists exactly
        for this and was not being used there."""
        orfaos = []
        for nome_aba, aba in self._abas():
            for form in aba.findChildren(QFormLayout):
                for linha in range(form.rowCount()):
                    item_label = form.itemAt(linha, QFormLayout.ItemRole.LabelRole)
                    item_campo = form.itemAt(linha, QFormLayout.ItemRole.FieldRole)
                    if item_label is None or item_campo is None:
                        continue
                    label = item_label.widget()
                    campo = item_campo.widget()
                    if label is None or campo is None:
                        continue
                    if label.isVisible() and not campo.isVisible():
                        texto = label.text() if hasattr(label, "text") else "?"
                        orfaos.append(f"{nome_aba}: {texto!r}")
        self.assertEqual(
            orfaos, [],
            "visible label with hidden field -- use "
            "`common.definir_linha_visivel`, not `setVisible`: " + str(orfaos))

    def test_nenhum_campo_numerico_ou_de_enum_vira_faixa(self):
        """A `QFormLayout` stretches the field to the end of the row; in a
        1400px window this gave a ~1370px box to type "72", and the same
        quantity came out with a different width in each tab.
        `common.compactar_campos_de_formulario` sets a ceiling by content
        TYPE -- number, enum -- and it is that ceiling this test
        protects."""
        from zbemt.gui.common import LARGURA_DE_NUMERO, LARGURA_MAX_DE_ENUM

        faixas = []
        for nome_aba, aba in self._abas():
            for w in aba.findChildren(QAbstractSpinBox):
                if w.isVisible() and w.width() > max(LARGURA_DE_NUMERO,
                                                     w.minimumSizeHint().width()):
                    faixas.append(f"{nome_aba}: number field {w.width()}px")
            for w in aba.findChildren(QComboBox):
                # The floor is the minimum the combo itself requests: a
                # combo whose longest option does not fit in
                # `LARGURA_MAX_DE_ENUM` asks for more (see
                # `dialogs.ajustar_largura_de_combo`), and squeezing it
                # would elide the option with "…" -- the generic ceiling
                # cannot override that concrete need. What this test
                # forbids is the field stretched BEYOND what it needs,
                # which is the real defect (a 1370px box to type "72").
                teto = max(LARGURA_MAX_DE_ENUM, w.minimumWidth(),
                           w.minimumSizeHint().width())
                if w.isVisible() and w.width() > teto:
                    faixas.append(f"{nome_aba}: enum de {w.width()}px "
                                  f"({w.currentText()!r})")
        self.assertEqual(faixas, [], "field stretched to the end of the row: "
                                      + str(faixas))

    def test_nenhum_bloco_visivel_e_espremido_abaixo_do_proprio_minimo(self):
        """Real bug: "Run Batch" was the only tab without a
        `QScrollArea`. The four stacked steps add up to more height than
        the window, and Qt squeezed the "1. Generate cases" box 89px
        below its own `minimumSizeHint` -- the four "Fixed values" rows
        were flattened to ~14px, with the label text cut off in the
        middle and the spinboxes reduced to a horizontal dash.

        A widget smaller than its own minimum is always a defect: it
        means the content is being cut off, not reorganized. The correct
        answer is to scroll, not to shrink.
        """
        from PyQt6.QtWidgets import QGroupBox

        espremidos = []
        for nome_aba, aba in self._abas():
            for gb in aba.findChildren(QGroupBox):
                if not gb.isVisible():
                    continue
                minimo = gb.minimumSizeHint().height()
                # 2px tolerance: rounding of border/margin from the QSS.
                if minimo > 0 and gb.height() < minimo - 2:
                    espremidos.append(
                        f"{nome_aba}: {gb.title()!r} com {gb.height()}px, "
                        f"precisa de {minimo}px")
        self.assertEqual(espremidos, [],
                          "block squeezed below the minimum: " + str(espremidos))

    def test_todo_campo_de_valor_visivel_tem_tooltip(self):
        """Without a tooltip the field is mute on two levels: it does not
        explain itself on hover AND does not get a clickable help label --
        `field_help` extracts the field NAME from the tooltip itself, so a
        missing tooltip silently drops the help popup too.

        The sweep also covers `QLineEdit`/`QPlainTextEdit` and widgets
        OUTSIDE `QFormLayout`: seven fields escaped the previous version
        of this test precisely because they were text fields ("Project
        Name", "NACA code", "CST upper/lower", "Bézier") or because they
        lived in a `QHBoxLayout` ("Field", in the Results tab).
        """
        mudos = []
        for nome_aba, aba in self._abas():
            for w in aba.findChildren(TIPOS_DE_CAMPO_DE_VALOR):
                # No visibility filter: a field revealed only when "cst"
                # is chosen still needs a tooltip, and five of the mute
                # fields found on screen were exactly in these
                # progressive-reveal blocks.
                if not _e_campo_editavel(w) or _tem_explicacao(w, aba):
                    continue
                mudos.append(f"{nome_aba}: {_descrever_campo(w)}")
        self.assertEqual(mudos, [], "campo de valor sem tooltip: " + str(mudos))

    def test_tooltip_nomeia_o_campo_no_formato_que_a_ajuda_espera(self):
        """`field_help._campo_do_widget` reads the field name from the
        FIRST quoted token of the tooltip (`"n_blades" — ...`). A tooltip
        that does not start like that is loose text: the field has no way
        to resolve the documentation anchor, and the clickable label is
        never born.

        Not every value widget corresponds to a `.bemt` field (there are
        display-only controls), so what is required here is the converse:
        if the tooltip names a field, that name has to actually exist --
        either as a field persisted in the project dataclasses or as an
        API execution parameter (trim, for example, is not saved in the
        `.bemt`: it is an argument of `api.run_case_trimmed`)."""
        import inspect

        from zbemt import api
        from zbemt.bemt import BEMTConfig
        from zbemt.gui.field_help import _campo_do_widget
        from zbemt.models import (AirfoilDef, BatchDefinition, FlightCondition,
                                  ProfileGeometry, Project, RotorGeometryDef)

        conhecidos: set = set(inspect.signature(
            api.run_case_trimmed).parameters)
        for cls in (BEMTConfig, AirfoilDef, RotorGeometryDef, FlightCondition,
                    BatchDefinition, ProfileGeometry, Project):
            conhecidos |= set(cls.__dataclass_fields__)

        inventados = []
        for nome_aba, aba in self._abas():
            for w in aba.findChildren(TIPOS_DE_CAMPO_DE_VALOR):
                campo = _campo_do_widget(w)
                if campo is not None and campo not in conhecidos:
                    inventados.append(f"{nome_aba}: {campo!r}")
        self.assertEqual(inventados, [],
                         "tooltip nomeia campo inexistente: " + str(inventados))

    def test_nenhum_botao_estica_muito_alem_do_proprio_texto(self):
        """In a `QHBoxLayout` without a trailing stretch, the buttons absorb
        all the row's slack: "- Remove" (80px of text) measured 550px, the
        width ceiling of the stylesheet, and the whole row turned into a
        bar of giant buttons.

        `setSizePolicy(Fixed)` does NOT fix it -- with the QSS applied the
        button grows up to `max-width` even with Fixed policy (measured on
        the mounted window). What fixes it is `addStretch(1)` at the end of
        the row, and that is what this test protects.

        Full-row action buttons (a `Run Case` that occupies the row for
        that purpose) are excluded: they are not on a row WITH other
        widgets, which is where the defect shows up.
        """
        from PyQt6.QtWidgets import QHBoxLayout, QPushButton

        esticados = []
        for nome_aba, aba in self._abas():
            for linha in aba.findChildren(QHBoxLayout):
                botoes = [linha.itemAt(i).widget() for i in range(linha.count())]
                botoes = [b for b in botoes
                          if isinstance(b, QPushButton) and b.isVisible()]
                if len(botoes) < 2:
                    continue
                for b in botoes:
                    # GROUP width is deliberate, not layout slack: the
                    # four Run Batch action buttons share the width of the
                    # longest label by explicit request, and "Clear" is
                    # wide for its own text because of that (see
                    # `RunBatchTab._uniformizar_largura_dos_botoes`).
                    if getattr(b, "_largura_de_grupo", None) is not None:
                        continue
                    folga = b.width() - b.sizeHint().width()
                    if folga > 40:
                        esticados.append(
                            f"{nome_aba}: {b.text()!r} com {b.width()}px "
                            f"for {b.sizeHint().width()}px of content")
        self.assertEqual(esticados, [],
                          "button stretched by the row's slack -- missing a "
                          "`addStretch(1)` no fim: " + str(esticados))

    def test_todo_bloco_de_ajuda_alcanca_um_groupbox_de_verdade(self):
        """`app._BLOCOS` matches the groupbox TITLE as a string. A renamed
        title (several were, in this very session) leaves the entry
        orphaned and that block's help vanishes with no error at all --
        it just disappears.

        The check runs both ways: no `BLOCK_HELP` entry is left without a
        groupbox, and no visible groupbox is left without a clickable
        title.
        """
        from PyQt6.QtWidgets import QGroupBox

        from zbemt.gui.common import _TituloDeBlocoClicavel
        from zbemt.gui.help_blocks import BLOCK_HELP

        alcancados: set = set()
        mudos: list = []
        for nome_aba, aba in self._abas():
            for gb in aba.findChildren(QGroupBox):
                filtro = next((c for c in gb.children()
                               if isinstance(c, _TituloDeBlocoClicavel)), None)
                if filtro is None:
                    mudos.append(f"{nome_aba}: {gb.title()!r}")
                else:
                    alcancados.add(filtro._bloco)

        self.assertEqual(mudos, [],
                         "groupbox sem ajuda de bloco: " + str(mudos))
        self.assertEqual(sorted(set(BLOCK_HELP) - alcancados), [],
                         "BLOCK_HELP entry that no groupbox reaches "
                         "-- title renamed without updating `app._BLOCOS`")

    def test_todo_campo_com_tooltip_ganhou_rotulo_clicavel_de_ajuda(self):
        """The tooltip names the field (`"n_blades" — ...`) and it is from
        that name that `field_help.instalar_popups_de_campo` derives the
        clickable label. A field that HAS the name in the tooltip but did
        not become a clickable label means the help never reached it --
        the user is left without the popup and without the link to the
        full documentation."""
        from zbemt.gui.field_help import _campo_do_widget, ancora_do_campo
        from zbemt.gui import help_content

        sem_ajuda = []
        for nome_aba, aba in self._abas():
            for form in aba.findChildren(QFormLayout):
                for linha in range(form.rowCount()):
                    item = form.itemAt(linha, QFormLayout.ItemRole.FieldRole)
                    item_label = form.itemAt(linha, QFormLayout.ItemRole.LabelRole)
                    if item is None or item_label is None:
                        continue
                    w, label = item.widget(), item_label.widget()
                    if w is None or label is None or not w.isVisible():
                        continue
                    campo = _campo_do_widget(w)
                    if campo is None:
                        continue
                    documentado = (campo in help_content.FIELD_HELP
                                   or ancora_do_campo(campo) is not None)
                    if documentado and not isinstance(label, QToolButton):
                        sem_ajuda.append(f"{nome_aba}: {campo!r}")
        self.assertEqual(sem_ajuda, [],
                         "documented field without a clickable label: " + str(sem_ajuda))

    def test_nenhum_combo_de_unidade_elide_a_propria_opcao(self):
        """Real bug: "alpha [deg]" came out cut off ("alpha [deg") in the
        condition combos of Run Case and Run Batch, which had a fixed
        110px.

        This is not a pixel assertion (rule 3): the floor is the widget's
        own FONT METRIC, so it keeps holding if the font, the theme, or
        the language changes."""
        from zbemt.gui.widgets import LongitudinalInput, AxialInput

        cortados = []
        for nome_aba, aba in self._abas():
            for campo in aba.findChildren((LongitudinalInput, AxialInput)):
                combo = campo.unit_combo
                if not combo.isVisible():
                    continue
                fm = combo.fontMetrics()
                mais_longo = max((combo.itemText(i) for i in range(combo.count())),
                                 key=fm.horizontalAdvance, default="")
                # the dropdown arrow eats ~22px (styles.py) + padding
                if combo.width() < fm.horizontalAdvance(mais_longo) + 24:
                    cortados.append(f"{nome_aba}: {mais_longo!r} em {combo.width()}px")
        self.assertEqual(cortados, [], "combo de unidade elidido: " + str(cortados))

    def test_campos_de_condicao_comecam_na_mesma_coluna(self):
        """Run Case and Run Batch put the NUMBER of every condition row in
        the same column -- the compound rows (mu_x/J_x, alpha/Vz) have a
        combo-label before the number, and the simple ones (Collective,
        RPM) are indented up to that point by `_com_recuo_de_unidade`.
        Different widths between the two tabs misaligned the column
        within each one."""
        from zbemt.gui.widgets import LongitudinalInput, AxialInput

        for nome_aba, aba in self._abas():
            if nome_aba.replace("*", "").strip() not in ("Run Case", "Run Batch"):
                continue
            larguras = {c.unit_combo.width()
                        for c in aba.findChildren((LongitudinalInput, AxialInput))
                        if c.unit_combo.isVisible()}
            with self.subTest(aba=nome_aba):
                self.assertLessEqual(len(larguras), 1,
                                      f"{nome_aba}: combos de unidade com larguras {larguras}")

    def test_caixas_vizinhas_nao_colam_umas_nas_outras(self):
        """Real bug: in Run Batch > export, the "Coefficients" label
        touched the "Azimuthal loads" checkbox -- four checkboxes on one
        row with the style's default spacing read as a single block, and
        the eye cannot tell which box each word belongs to."""
        from PyQt6.QtWidgets import QCheckBox, QHBoxLayout, QRadioButton
        from zbemt.gui.common import ESPACAMENTO_MINIMO_ENTRE_CAIXAS

        coladas = []
        for nome_aba, aba in self._abas():
            for linha in aba.findChildren(QHBoxLayout):
                caixas = [linha.itemAt(i).widget() for i in range(linha.count())
                          if isinstance(linha.itemAt(i).widget(), (QCheckBox, QRadioButton))]
                caixas = [c for c in caixas if c.isVisible()]
                for esquerda, direita in zip(caixas, caixas[1:]):
                    folga = (direita.mapTo(aba, direita.rect().topLeft()).x()
                             - (esquerda.mapTo(aba, esquerda.rect().topLeft()).x()
                                + esquerda.width()))
                    if folga < ESPACAMENTO_MINIMO_ENTRE_CAIXAS:
                        coladas.append(
                            f"{nome_aba}: {esquerda.text()!r} e {direita.text()!r} "
                            f"a {folga}px")
        self.assertEqual(coladas, [], "caixas coladas: " + str(coladas))

    def test_linhas_de_eixo_do_fatorial_comecam_na_mesma_coluna(self):
        """The three factorial axes have a unit combo with a different
        NATURAL width ("mu_x" versus "alpha [deg]"), and the disabled
        axis has no combo at all -- each row started the "values:" field
        at a different x. The column is reserved across all three."""
        aba = None
        for nome_aba, widget in self._abas():
            if nome_aba.replace("*", "").strip() == "Run Batch":
                aba = widget
        self.assertIsNotNone(aba, "Run Batch tab not found")

        # one longitudinal axis, one axial, and one disabled: the case
        # where the three natural widths are different
        for indice, slot_desejado in ((0, "longitudinal"), (1, "axial")):
            combo = aba.axis_rows[indice][0]
            combo.setCurrentIndex(next(i for i, (_r, s) in enumerate(aba._AXIS_SLOTS)
                                       if s == slot_desejado))
        self.app.processEvents()

        xs = {edit.mapTo(aba, edit.rect().topLeft()).x()
              for _slot, _unit, edit in aba.axis_rows}
        self.assertEqual(len(xs), 1,
                          f"'values:' fields starting at different x: {sorted(xs)}")

    def test_faixa_de_opcoes_encolhe_para_o_modo_corrente(self):
        """Real bug: the control strip above the Results tab's plot
        reserved the height of the TALLEST panel (the "3D" mode's) in
        every mode -- 216px measured, with a blank gap of more than a
        hundred pixels above the disk maps, which ended up squeezed
        beneath it.

        What is measured is the RATIO, not the pixel (rule 3): a mode
        with few controls must leave more screen for the plot than a
        mode with many."""
        aba = None
        for nome_aba, widget in self._abas():
            if nome_aba.replace("*", "").strip() == "Results":
                aba = widget
        self.assertIsNotNone(aba, "Results tab not found")

        def altura_do_grafico(modo: str) -> int:
            linha = [i for i in range(aba.mode_list.count())
                     if aba.mode_list.item(i).text() == modo]
            self.assertTrue(linha, f"mode {modo!r} does not exist in the list")
            aba.mode_list.setCurrentRow(linha[0])
            self.app.processEvents()
            self.app.processEvents()
            return aba.canvas_stack.height()

        magro = altura_do_grafico("Convergence")   # panel practically empty
        gordo = altura_do_grafico("3D")            # the tallest panel in the tab
        self.assertGreater(
            magro, gordo,
            "the options row did not shrink: the plot has the same height in a "
            "modo sem controles e no modo com mais controles")

    def test_linha_de_checkbox_nao_cola_na_linha_seguinte(self):
        """Real bug: "Enable dynamic stall (Øye)" touched "Lag
        constant A:", and the three rows of "3D rotational effects" read
        as a single block. The policy lives in the `common` module
        (`arejar_formularios`), applied by the window -- what is checked
        here is that it reached EVERY form."""
        from zbemt.gui.common import ESPACAMENTO_MINIMO_DE_LINHA

        apertados = []
        for nome_aba, aba in self._abas():
            for form in aba.findChildren(QFormLayout):
                if form.rowCount() < 2:
                    continue
                if form.verticalSpacing() < ESPACAMENTO_MINIMO_DE_LINHA:
                    apertados.append(f"{nome_aba}: {form.verticalSpacing()}px")
        self.assertEqual(apertados, [], "cramped form: " + str(apertados))

    def test_as_sete_etapas_do_topo_tem_a_mesma_largura(self):
        """"Project" and "Config/Engine" differ by dozens of pixels: seven
        colored pills of different sizes read as seven different things,
        not as seven steps of the same flow."""
        barra = self.win.flow_bar
        barra._igualar_largura_das_etapas()
        larguras = {b.width() or b.minimumWidth() for b in barra._buttons}
        self.assertEqual(len(larguras), 1, f"larguras diferentes: {larguras}")

    def test_as_etapas_do_topo_ficam_centradas_na_faixa(self):
        """Without a fixed height the pill stretches vertically and
        touches both edges of the dark strip -- the colored rectangle
        turns into a bar."""
        barra = self.win.flow_bar
        for btn in barra._buttons:
            with self.subTest(etapa=btn.text()):
                self.assertEqual(btn.height(), barra.ALTURA_DE_ETAPA)
        # and margin is left over on top and bottom (the strip is taller
        # than the pill), which is what "centered" means here
        self.assertGreaterEqual(
            barra.height(), barra.ALTURA_DE_ETAPA + 2 * barra.MARGEM_VERTICAL)


if __name__ == "__main__":
    unittest.main()
