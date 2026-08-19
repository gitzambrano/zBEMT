"""The "?" next to each field, and the field -> documentation section link.

Embedded help has ~195 sections, one per field. A global "?" forces the
user to search which of them explains the field they are looking at; the
"?" next to the field delivers it. The link is derived by cross-referencing
the widget's `toolTip` (which already names the `.bemt` field) with the
documentation section that mentions that name -- no one maintains a third
list by hand.
"""
import unittest

try:
    from PyQt6.QtWidgets import QApplication, QPushButton
    _HAS_QT = True
except ImportError:                                   # pragma: no cover
    _HAS_QT = False

from tests import helpers


@unittest.skipUnless(_HAS_QT, "sem PyQt6")
class TestMapaDeCampos(unittest.TestCase):
    def test_mapa_cobre_a_maioria_dos_campos_do_schema(self):
        from zbemt.gui.field_help import mapa_de_campos
        from zbemt.bemt import BEMTConfig
        from zbemt.models import AirfoilDef

        mapa = mapa_de_campos()
        alvo = set(BEMTConfig.__dataclass_fields__) | set(AirfoilDef.__dataclass_fields__)
        cobertos = alvo & set(mapa)
        self.assertGreater(len(cobertos) / len(alvo), 0.75,
                           f"only {len(cobertos)}/{len(alvo)} fields have a section")

    def test_toda_ancora_do_mapa_existe_na_documentacao(self):
        """A broken anchor would open documentation at the top without saying
        it failed -- worse than not having a button."""
        import re
        from zbemt import paths
        from zbemt.gui.field_help import mapa_de_campos

        html = paths.documentation_path().read_text(encoding="utf-8")
        ids = set(re.findall(r'id="([\w-]+)"', html))
        quebradas = sorted({a for a in mapa_de_campos().values() if a not in ids})
        self.assertEqual(quebradas, [])

    def test_campos_centrais_caem_na_fisica_e_nao_na_tabela_de_campos(self):
        """CURRENT contract (see `field_help`'s docstring): the
        `ajuda-{field}` row in the "Parameters by tab" table is the LAST resort,
        not the first.

        This test once asserted the opposite -- it required `ajuda-{field}` for
        these same fields --, which is a rule that `field_help` deliberately
        dropped: "Rule 3 was once FIRST -- and that's why every help link
        fell into a table cell instead of the physics section". A table cell
        repeats the tooltip; the user clicking "?" wants the section that
        explains the quantity.
        """
        from zbemt.gui.field_help import mapa_de_campos
        mapa = mapa_de_campos()
        for campo in ("n_blades", "stall_model", "solver", "collective_deg"):
            self.assertFalse(
                mapa[campo].startswith("ajuda-"),
                f"{campo} caiu na tabela de campos ({mapa[campo]}) em vez de "
                "in an explanation section")


@unittest.skipUnless(_HAS_QT, "sem PyQt6")
class TestBotoesNaJanela(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        import tempfile, shutil
        self._tmp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self._tmp, ignore_errors=True)
        with helpers.patch_em_toda_gui("PROJECTS_ROOT", self._tmp):
            from zbemt.gui import app as gui
            self.win = gui.MainWindow()
        self.addCleanup(self.win.deleteLater)

    def _labels_clicaveis(self, indice_aba):
        """QToolButtons that function as field labels (hand cursor)."""
        from PyQt6.QtCore import Qt
        from PyQt6.QtWidgets import QToolButton
        aba = self.win.tabs.widget(indice_aba)
        return [b for b in aba.findChildren(QToolButton)
                if b.cursor().shape() == Qt.CursorShape.PointingHandCursor]

    def _botoes_bloco(self, indice_aba):
        """Groupboxes whose TITLE opens the block help.

        It used to scan `QPushButton` with text "?" -- and that's why
        it was failing: there are no "?" buttons left in the window (see
        `field_help`'s docstring). Block help is now the `QGroupBox`'s
        title itself, set up by `common.tornar_titulo_de_bloco_clicavel`,
        which marks the groupbox with `_ajuda_de_bloco`. That marker
        identifies a block with help.
        """
        from PyQt6.QtWidgets import QGroupBox
        aba = self.win.tabs.widget(indice_aba)
        return [gb for gb in aba.findChildren(QGroupBox)
                if getattr(gb, "_ajuda_de_bloco", None) is not None]

    def test_abas_de_fisica_ganham_labels_clicaveis(self):
        """Documented fields gain clickable QToolButton labels."""
        self.assertGreater(len(self._labels_clicaveis(2)), 15, "Airfoil tab has no clickable labels")
        self.assertGreater(len(self._labels_clicaveis(3)), 10, "Config/Motor tab has no clickable labels")

    def test_abas_de_fisica_ganham_botoes_de_bloco(self):
        """Relevant groupboxes gain block '?' button."""
        self.assertGreater(len(self._botoes_bloco(2)), 3, "Airfoil tab has no block '?'")
        self.assertGreater(len(self._botoes_bloco(3)), 3, "aba Config/Motor sem '?' de bloco")

    def test_condicao_de_voo_tambem_ganha(self):
        # Run Case has few editable fields with documented tooltips;
        # verify that at least some gained clickable label OR block button
        clicaveis = len(self._labels_clicaveis(4)) + len(self._botoes_bloco(4))
        self.assertGreaterEqual(clicaveis, 2, "aba Run Case sem ajuda interativa")

    def test_o_label_segue_a_visibilidade_do_campo(self):
        """Progressive disclosure hides the field; the clickable label must follow."""
        from PyQt6.QtCore import Qt
        from PyQt6.QtWidgets import QFormLayout, QToolButton
        aba = self.win.tabs.widget(2)  # Airfoil
        aba.stall_model_combo.setCurrentText("clip")
        aba.use_dynamic_stall.setChecked(True)
        campo = aba.dyn_A

        # Encontra o QToolButton label na mesma linha do formulário
        label_btn = None
        for form in aba.findChildren(QFormLayout):
            for r in range(form.rowCount()):
                fi = form.itemAt(r, QFormLayout.ItemRole.FieldRole)
                li = form.itemAt(r, QFormLayout.ItemRole.LabelRole)
                if fi and fi.widget() == campo and li:
                    w = li.widget()
                    if isinstance(w, QToolButton):
                        label_btn = w
                        break
            if label_btn:
                break
        self.assertIsNotNone(label_btn, "campo dyn_A sem label QToolButton")

        # Hide the row via progressive disclosure
        aba.use_dynamic_stall.setChecked(False)
        self.assertTrue(campo.isHidden() or label_btn.isHidden(),
                        "campo e label deveriam estar ocultos")
        aba.use_dynamic_stall.setChecked(True)
        self.assertFalse(campo.isHidden() and label_btn.isHidden(),
                         "field/label should be visible again")

    def test_instalar_e_idempotente(self):
        """Calling instalar_popups_de_campo twice does not create duplicate labels."""
        from PyQt6.QtWidgets import QToolButton
        from zbemt.gui.field_help import instalar_popups_de_campo
        aba = self.win.tabs.widget(3)
        antes = len(self._labels_clicaveis(3))
        self.assertEqual(instalar_popups_de_campo(aba), 0)
        self.assertEqual(len(self._labels_clicaveis(3)), antes)


@unittest.skipUnless(_HAS_QT, "sem PyQt6")
class TestOpenHelpComAncora(unittest.TestCase):
    def test_url_recebe_o_fragmento(self):
        from unittest import mock
        from zbemt.gui import common
        with mock.patch.object(common, "QDesktopServices") as servicos:
            common.open_help(None, anchor="cap-3-2-1")
        url = servicos.openUrl.call_args[0][0]
        self.assertEqual(url.fragment(), "cap-3-2-1")
        self.assertTrue(url.toLocalFile().endswith("documentation.html"))

    def test_sem_ancora_abre_no_topo(self):
        from unittest import mock
        from zbemt.gui import common
        with mock.patch.object(common, "QDesktopServices") as servicos:
            common.open_help(None)
        self.assertEqual(servicos.openUrl.call_args[0][0].fragment(), "")


if __name__ == "__main__":
    unittest.main()


@unittest.skipUnless(_HAS_QT, "sem PyQt6")
class TestAjudaNaoQuebraRevelacaoProgressiva(unittest.TestCase):
    """The "?" wraps the field in a container to fit the button next to it.
    This changes which widget is the FIELD in the form row -- and the code
    that hides the row searches for the original widget. Without care,
    `setRowVisible` fails to find the row and fails silently: the field
    stays on screen even when it shouldn't."""

    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def test_esconder_linha_funciona_com_label_clicavel(self):
        """Progressive disclosure must hide field AND its clickable label together."""
        import shutil, tempfile
        from PyQt6.QtWidgets import QFormLayout, QToolButton
        from zbemt import api
        tmp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, tmp, ignore_errors=True)
        with helpers.patch_em_toda_gui("PROJECTS_ROOT", tmp):
            from zbemt.gui import app as gui
            win = gui.MainWindow()
        self.addCleanup(win.deleteLater)
        win.state.set_project(api.open_project("projects/test2"))

        aba = win.tabs.widget(5)                       # Run Batch
        campo = aba.fixed_collective
        # What OCCUPIES the field column can be a wrapper of the field (Run
        # Batch indents simple spins to the column of composite field numbers).
        # `_container_de_ajuda` is exactly the marker that
        # `common.definir_linha_visivel` follows to find the row.
        ocupante = getattr(campo, "_container_de_ajuda", None) or campo

        # Encontra label QToolButton da mesma linha
        label_btn = None
        for form in aba.findChildren(QFormLayout):
            for r in range(form.rowCount()):
                fi = form.itemAt(r, QFormLayout.ItemRole.FieldRole)
                li = form.itemAt(r, QFormLayout.ItemRole.LabelRole)
                if fi and fi.widget() == ocupante and li:
                    w = li.widget()
                    if isinstance(w, QToolButton):
                        label_btn = w
                        break
            if label_btn:
                break
        self.assertIsNotNone(label_btn, "fixed_collective sem label QToolButton")

        slot_combo = aba.axis_rows[0][0]
        i_coletivo = [i for i, (_l, s) in enumerate(aba._AXIS_SLOTS)
                      if s == "collective_deg"][0]
        slot_combo.setCurrentIndex(i_coletivo)         # coletivo vira EIXO → linha deve sumir
        self.assertTrue(campo.isHidden() or label_btn.isHidden(),
                        "fixed field stayed visible while being an axis")

        slot_combo.setCurrentIndex(0)                  # nenhum eixo → linha deve voltar
        self.assertFalse(campo.isHidden() and label_btn.isHidden())
