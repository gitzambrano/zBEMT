"""
test_results_tab.py
===================

Regression tests for the Results tab (``zbemt/gui/tabs/results.py``):

* **independent height and color in the 3D view** -- there used to be ONE
  field selector plus a checkbox "raise the disc by the field value", so
  the height was forced to be the same quantity as the color (or none).
  ``visualization.build_disk_grid`` always accepted separate
  ``field=``/``z_field=``; it was only the GUI that tied the two together;
* **every export starts from the project's ``outputs/`` folder** -- the
  dialogs used to open wherever the process happened to be (the working
  directory, or the last one visited), scattering figures outside the
  project;
* **the reverse-flow mask belongs to the Results tab** -- it is a DISPLAY
  choice (it does not change forces or the CSV) and now lives here,
  writing to the project's ``config`` so it does not lose GUI/``.bemt``/CLI
  parity.

Each test switches to the Results tab before any assertion: on a tab
that is not selected ``isVisible()`` is always False, and the assertions
would pass without testing anything.
"""

import os
import unittest
import unittest.mock
from pathlib import Path

try:
    from PyQt6.QtWidgets import QApplication
    from PyQt6.QtCore import Qt
    _HAS_QT = True
except Exception:  # pragma: no cover - environment without PyQt6
    _HAS_QT = False

import numpy as np

from zbemt import geometry
from zbemt.models import Project, AirfoilDef, Results


def _make_project(path: str = "") -> Project:
    geom = geometry.generate_tapered(root_chord_norm=0.10, tip_chord_norm=0.04,
                                      twist_root_deg=14.0, twist_tip_deg=2.0,
                                      root_cutout_norm=0.15, radius_m=1.0, n_stations=10)
    airfoil = AirfoilDef(source="analytical", stall_model="clip",
                          alpha_stall_pos_deg=15.0, alpha_stall_neg_deg=-6.0)
    cfg = dict(Ne=6, Npsi=8, solver="fixed_point", max_iter=80)
    return Project(name="teste_results", path=path, geometry=geom, airfoil=airfoil,
                    config=cfg)


def _make_disk_result() -> Results:
    """``Results`` with ``maps`` sufficient for the 3D disk -- and with two
    fields of DIFFERENT SHAPE (``Fn`` grows with radius, ``Mach`` varies
    with azimuth), so that coloring by one and raising by the other
    produces a surface distinct from either "same field" combination."""
    Ne, Npsi = 6, 8
    r = np.linspace(0.2, 1.0, Ne)
    psi = np.linspace(0, 2 * np.pi * (1 - 1 / Npsi), Npsi)
    R_NORM, PSI = np.meshgrid(r, psi, indexing="ij")
    ones = np.ones_like(R_NORM)
    maps = dict(R_NORM=R_NORM, R_DIM=R_NORM * 1.0, PSI=PSI,
                lambda_i=0.05 + 0.02 * np.sin(PSI) * R_NORM,
                Ut=ones * 5.0, Fn=R_NORM ** 2, Ft=ones * 0.1,
                Cl=ones * 0.5, Cd=ones * 0.02, Up=ones * 0.5, W=ones * 5.0,
                alpha_eff=ones * 0.05, phi=ones * 0.02, lambda_total=ones * 0.06,
                Mach=0.3 + 0.25 * np.sin(PSI))
    return Results(summary={"mu_x": 0.2}, maps=maps, condition_name="c1")


@unittest.skipUnless(_HAS_QT, "PyQt6 not installed in this environment")
class BaseDeAbaResults(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])
        from zbemt.gui import app as gui
        cls.gui = gui

    def _janela_na_aba_results(self, projeto=None):
        """A real `MainWindow`, already WITH the Results tab selected.

        Switching tabs is mandatory: on a tab that is not selected,
        widgets have `isVisible()` False and any visibility assertion
        passes without testing anything at all."""
        win = self.gui.MainWindow()
        win.state.set_project(projeto if projeto is not None else _make_project())
        indice = win.tabs.count() - 1
        tab = win.tabs.widget(indice)
        self.assertEqual(type(tab).__name__, "ResultsTab")
        # `show()` in addition to `setCurrentIndex`: without the window
        # shown, EVERY `isVisible()` is False and the visibility
        # assertions would pass without testing anything.
        win.resize(1500, 1000)
        win.show()
        win.tabs.setCurrentIndex(indice)
        self.app.processEvents()
        self.addCleanup(win.deleteLater)
        return win, tab

    def _com_resultado(self, projeto=None):
        win, tab = self._janela_na_aba_results(projeto)
        win.state.add_history_entry(kind="case", label="c1", results=_make_disk_result())
        self.app.processEvents()
        return win, tab


class TestVista3DAlturaECorIndependentes(BaseDeAbaResults):
    """Item 7: one selector for HEIGHT and another for COLOR."""

    def test_existem_dois_seletores_e_a_altura_permite_disco_plano(self):
        _, tab = self._com_resultado()
        tab.mode_list.setCurrentRow(tab._MODES.index("3D"))
        self.app.processEvents()

        self.assertTrue(tab.field_combo.isVisible())
        self.assertTrue(tab.z_field_combo.isVisible(),
                         "the Results tab needs a HEIGHT selector besides the color one")
        rotulos = [tab.z_field_combo.itemText(i) for i in range(tab.z_field_combo.count())]
        self.assertIn(tab._SEM_RELEVO_3D, rotulos)
        # Default: the same quantity as the color (anyone who already used
        # the tab keeps seeing the relief of the chosen field).
        self.assertEqual(tab.z_field_combo.currentText(), tab.field_combo.currentText())

    def test_altura_e_cor_podem_ser_campos_diferentes(self):
        _, tab = self._com_resultado()
        tab.field_combo.setCurrentText("Fn (thrust)")
        tab.z_field_combo.setCurrentText("Mach")
        self.assertEqual(tab._campo_3d_selecionado(), "Fn")
        self.assertEqual(tab._campo_3d_de_altura(), "Mach")

        tab.z_field_combo.setCurrentText(tab._SEM_RELEVO_3D)
        self.assertIsNone(tab._campo_3d_de_altura())

    def test_o_redesenho_pede_a_malha_com_field_e_z_field_diferentes(self):
        """Where the regression actually bites: with color=Fn and
        height=Mach, the mesh must be requested with
        ``field="Fn", z_field="Mach"``. Before, ``z_field`` could only be
        the SAME field as the color (or ``None``)."""
        from zbemt.viz import visualization
        _, tab = self._com_resultado()
        tab.mode_list.setCurrentRow(tab._MODES.index("3D"))
        tab.field_combo.setCurrentText("Fn (thrust)")
        tab.z_field_combo.setCurrentText("Mach")
        # Touching the combos already drew and CACHED the figure
        # (`_CanvasComCache`); without discarding the cache, the redraw
        # below would not build any mesh and the spy would never be
        # called.
        tab.canvas_host.limpar_cache()

        with unittest.mock.patch.object(
                visualization, "build_disk_grid",
                wraps=visualization.build_disk_grid) as espiao:
            tab._refresh_3d_preview()
        self.assertTrue(espiao.called, "the 3D view did not build any mesh")
        kwargs = espiao.call_args.kwargs
        self.assertEqual(kwargs.get("field"), "Fn")
        self.assertEqual(kwargs.get("z_field"), "Mach")

        # And the (color, height) pair reaches the figure: with DIFFERENT
        # quantities the title names both, by their SYMBOLS (see
        # `TestRotulosDaVista3D`).
        fig = tab._figura_3d_matplotlib(_make_disk_result().maps, "Fn", "Mach")
        titulo = fig.axes[0].get_title()
        self.assertIn(r"$F_n$", titulo)
        self.assertIn(r"$M$", titulo)

    def test_barra_de_cor_e_eixo_z_dizem_qual_grandeza_e_qual(self):
        _, tab = self._com_resultado()
        maps = _make_disk_result().maps
        fig = tab._figura_3d_matplotlib(maps, "Fn", "Mach")
        ax = fig.axes[0]
        self.assertIn(r"$M$", ax.get_zlabel())
        self.assertEqual(ax.zaxis.labelpad, -8)
        rotulos_de_barra = [a.get_ylabel() for a in fig.axes[1:]]
        self.assertTrue(any(r"$F_n$" in r for r in rotulos_de_barra),
                         f"colorbar does not name the field: {rotulos_de_barra}")

    def test_modo_3d_redesenha_sem_erro_com_cor_e_altura_diferentes(self):
        _, tab = self._com_resultado()
        tab.mode_list.setCurrentRow(tab._MODES.index("3D"))
        tab.field_combo.setCurrentText("lambda_i")
        tab.z_field_combo.setCurrentText("Cd")
        tab._refresh_3d_preview()      # must not raise
        tab.z_field_combo.setCurrentText(tab._SEM_RELEVO_3D)
        tab._refresh_3d_preview()      # same, flat disk

    def test_tabela_pinta_rotulo_da_condicao_com_subscrito(self):
        _, tab = self._com_resultado()
        tab._refresh_table()
        cabecalho = tab.table_widget.verticalHeaderItem(0)
        self.assertIsNotNone(cabecalho)
        from zbemt.gui.tabs.results import _PAPEL_HTML
        self.assertIn("&mu;<sub>x</sub>", cabecalho.data(_PAPEL_HTML))


class TestExportacoesPartemDaPastaDoProjeto(BaseDeAbaResults):
    """Item 8: EVERY export dialog opens in ``<project>/outputs``."""

    def _projeto_em_disco(self) -> Project:
        import shutil
        import tempfile
        raiz = tempfile.mkdtemp(prefix="zbemt_results_tab_")
        self.addCleanup(shutil.rmtree, raiz, True)
        return _make_project(path=raiz)

    def test_helper_resolve_e_cria_a_pasta_outputs_do_projeto(self):
        from zbemt import api
        proj = self._projeto_em_disco()
        _, tab = self._janela_na_aba_results(proj)
        destino = tab._pasta_de_saida_padrao()
        self.assertEqual(destino, Path(api.default_project_paths(proj.path)["outputs"]))
        self.assertTrue(destino.is_dir(), "the output folder should be created if it does not exist")

    def test_sem_projeto_cai_no_outputs_global(self):
        from zbemt import paths
        win, tab = self._janela_na_aba_results()
        win.state.project = None
        self.assertEqual(tab._pasta_de_saida_padrao(criar=False), paths.outputs_dir())

    def test_relatorio_abre_no_outputs_do_projeto(self):
        from tests.helpers import patch_em_toda_gui
        proj = self._projeto_em_disco()
        _, tab = self._com_resultado(proj)
        esperado = str(Path(proj.path) / "outputs")
        with patch_em_toda_gui("QMessageBox"):
            with unittest.mock.patch(
                    "zbemt.gui.tabs.results.QFileDialog") as dlg:
                dlg.getSaveFileName.return_value = ("", "")
                tab._generate_report()
        caminho_default = dlg.getSaveFileName.call_args.args[2]
        self.assertTrue(caminho_default.startswith(esperado),
                         f"report does not start from {esperado}: {caminho_default}")

    def test_exportacao_3d_abre_no_outputs_do_projeto(self):
        from tests.helpers import patch_em_toda_gui
        proj = self._projeto_em_disco()
        _, tab = self._com_resultado(proj)
        esperado = str(Path(proj.path) / "outputs")
        with patch_em_toda_gui("QMessageBox"):
            with unittest.mock.patch(
                    "zbemt.gui.tabs.results.require_optional_package",
                    return_value=True):
                with unittest.mock.patch(
                        "zbemt.gui.tabs.results.QFileDialog") as dlg:
                    dlg.getExistingDirectory.return_value = ""
                    tab._export_3d("rotor_3d")
        self.assertEqual(dlg.getExistingDirectory.call_args.args[2], esperado)

    def test_dialogo_de_mapas_de_disco_ja_vem_com_o_outputs_do_projeto(self):
        """The "Destination folder" field starts filled in with the
        project's folder, even without a project saved to disk (in that
        case, the global outputs)."""
        from tests.helpers import patch_em_toda_gui
        proj = self._projeto_em_disco()
        _, tab = self._com_resultado(proj)
        esperado = str(Path(proj.path) / "outputs")
        capturado = {}

        def _falso_exec(self_dlg):
            # Walks the built dialog and reads the destination QLineEdit.
            from PyQt6.QtWidgets import QLineEdit, QDialog
            edits = self_dlg.findChildren(QLineEdit)
            capturado["texto"] = edits[0].text() if edits else None
            return QDialog.DialogCode.Rejected

        with patch_em_toda_gui("QMessageBox"):
            with unittest.mock.patch(
                    "zbemt.gui.tabs.results.QDialog.exec", _falso_exec):
                tab._export_disk_maps_da_selecao()
        self.assertEqual(capturado.get("texto"), esperado)


class TestBotoesDeExportacao(BaseDeAbaResults):
    """Export/Copy export and copy WHATEVER IS ON SCREEN.

    Before, there was a fixed "Export disk maps…" in any mode: in 3D, in
    Azimuth/Radius, or in the table, the single export button offered
    the plot the user was not even looking at -- and "Copy table" copied
    the table even with a plot in front."""

    def _modo(self, tab, nome: str):
        tab.mode_list.setCurrentRow(tab._MODES.index(nome))
        tab._atualizar_botoes_de_exportacao()

    def test_o_rotulo_nomeia_a_saida_do_modo(self):
        _, tab = self._com_resultado()
        for modo, esperado_export, esperado_copy in (
                ("Disk map", "Export plots…", "Copy figure"),
                ("Table", "Export table…", "Copy table"),
                ("Azimuth / Radius", "Export plots…", "Copy figure"),
                ("3D", "Export plots…", "Copy figure")):
            with self.subTest(modo=modo):
                self._modo(tab, modo)
                self.assertEqual(tab.btn_export.text(), esperado_export)
                self.assertEqual(tab.btn_copy.text(), esperado_copy)

    def test_o_rotulo_nunca_diz_selection(self):
        """Item 9, preserved: the button only exists when there is a
        selection, and the dialog already says how many cases go out."""
        _, tab = self._com_resultado()
        for modo in tab._MODES:
            with self.subTest(modo=modo):
                self._modo(tab, modo)
                self.assertNotIn("selection", tab.btn_export.text().lower())

    def test_todo_modo_tem_rotulo_e_dica_nos_dois_botoes(self):
        """A mode with no entry would fall back to a mute button -- no
        label saying what goes out and no tooltip saying the scope."""
        _, tab = self._com_resultado()
        for modo in tab._MODES:
            with self.subTest(modo=modo):
                self.assertIn(modo, tab._EXPORTACAO_POR_MODO)
                self._modo(tab, modo)
                self.assertTrue(tab.btn_export.toolTip().strip())
                self.assertTrue(tab.btn_copy.toolTip().strip())

    def test_os_tres_botoes_de_baixo_tem_a_mesma_largura(self):
        """And the width must fit the longest label of ANY mode: if
        measured only on the current one, the button would change size
        on every switch."""
        _, tab = self._com_resultado()
        tab.show()
        tab._atualizar_botoes_de_exportacao()
        larguras = {b.minimumWidth() for b in tab._botoes_de_exportacao}
        self.assertEqual(len(larguras), 1, larguras)
        tab.hide()

    def test_copiar_num_modo_de_grafico_nao_copia_a_tabela(self):
        """The inversion test: with a plot on screen, "Copy" puts an
        IMAGE on the clipboard, not the table's TSV."""
        from PyQt6.QtWidgets import QApplication
        from tests.helpers import patch_em_toda_gui
        _, tab = self._com_resultado()
        self._modo(tab, "Disk map")
        tab._refresh_current()
        QApplication.clipboard().clear()
        QApplication.clipboard().setText("sentinela")
        with patch_em_toda_gui("QMessageBox"):
            tab._copiar_da_tela()
        # either it copied the image (clearing the text), or it warned
        # that it could not -- in neither case does the table's TSV end
        # up there
        self.assertNotIn("condition_name", QApplication.clipboard().text())


class TestRotulosDaVista3D(BaseDeAbaResults):
    """The 3D view used to show the RAW key name.

    User screenshot: the color bar said "colour: lambda_i" and the z
    axis "height: lambda_i" -- the same quantity that the selector just
    above, the 2D maps and the table already show as λᵢ. And, with both
    pointing to the SAME field, the pair still appeared a third time in
    the title."""

    def test_o_rotulo_e_o_simbolo_e_nao_a_chave(self):
        _, tab = self._com_resultado()
        for campo, esperado in (("lambda_i", r"$\lambda_i$"),
                                 ("Fn", r"$F_n$ [N/m]"),
                                 ("alpha_eff", r"$\alpha$ [deg]")):
            with self.subTest(campo=campo):
                self.assertEqual(tab._rotulo_de_campo_3d(campo), esperado)
                # and what appears is mathtext, not the raw name followed
                # by the unit -- which was the old format ("lambda_i [-]")
                self.assertTrue(tab._rotulo_de_campo_3d(campo).startswith("$"))

    def test_o_simbolo_vem_da_mesma_fonte_dos_mapas_2D(self):
        """No second list: `plots._DISK_FIELD_META` is the source, and
        every field offered in the 3D selector must be in it."""
        from zbemt.viz import plots
        _, tab = self._com_resultado()
        for campo in tab._DISK_FIELDS:
            with self.subTest(campo=campo):
                self.assertIn(campo, plots._DISK_FIELD_META)
                self.assertEqual(tab._rotulo_de_campo_3d(campo).split(" [")[0],
                                  plots.disk_field_label(campo))

    def test_o_plotly_recebe_texto_puro_e_nao_mathtext(self):
        """Plotly does not render matplotlib mathtext: it would print
        `$\\lambda_i$` raw on the color bar."""
        _, tab = self._com_resultado()
        texto = tab._rotulo_de_campo_3d("lambda_i", False)
        self.assertNotIn("$", texto)
        self.assertNotIn("\\", texto)
        self.assertIn("λ", texto)          # a real λ

    def test_sem_as_palavras_colour_e_height_nos_rotulos(self):
        """Each symbol stays right next to what it describes -- the color
        bar and the z axis --, so the word adds nothing."""
        _, tab = self._com_resultado()
        for desenhado in (True, False):
            with self.subTest(desenhado=desenhado):
                rotulo = tab._rotulo_de_campo_3d("Fn", desenhado)
                self.assertNotIn("colour", rotulo.lower())
                self.assertNotIn("height", rotulo.lower())

    def test_o_titulo_so_repete_o_par_quando_cor_e_altura_diferem(self):
        """With both on the same field (the screenshot's case), the title
        line was the THIRD repetition of the same quantity."""
        _, tab = self._com_resultado()
        self.assertEqual(tab._legenda_de_par_3d("lambda_i", "lambda_i"), "")
        self.assertEqual(tab._legenda_de_par_3d("Fn", None), "")
        legenda = tab._legenda_de_par_3d("Fn", "Mach")
        self.assertIn("color", legenda)
        self.assertIn("height", legenda)
        self.assertIn(r"$F_n$", legenda)
        self.assertIn(r"$M$", legenda)

    def test_a_figura_3d_sai_com_os_simbolos(self):
        """End to end: the real figure, not just the formatter."""
        entrada, tab = self._com_resultado()
        resultado = tab._resolve_single_result()
        if resultado is None:                     # pragma: no cover
            self.skipTest("no single result in the selection")
        fig = tab._figura_3d_matplotlib(resultado.maps, "lambda_i", "lambda_i")
        eixo = fig.axes[0]
        self.assertEqual(eixo.get_zlabel(), r"$\lambda_i$")
        # and the title does not carry the third repetition
        self.assertNotIn("height", eixo.get_title())


class TestMascaraDeFluxoReversoMoraEmResults(BaseDeAbaResults):
    """Item 10: the mask is a DISPLAY choice and lives only in this tab."""

    def test_caixa_existe_e_e_visivel_no_modo_de_disco(self):
        _, tab = self._com_resultado()
        tab.mode_list.setCurrentRow(tab._MODES.index("Disk map"))
        self.app.processEvents()
        self.assertTrue(tab.disk_mask_check.isVisible())
        self.assertIn("mask_reverse_flow_plots", tab.disk_mask_check.toolTip())

    def test_caixa_reflete_o_config_do_projeto_ao_abri_lo(self):
        proj = _make_project()
        proj.config["mask_reverse_flow_plots"] = False
        _, tab = self._janela_na_aba_results(proj)
        self.assertFalse(tab.disk_mask_check.isChecked())

    def test_alternar_a_caixa_grava_no_config_do_projeto(self):
        win, tab = self._com_resultado()
        self.assertTrue(tab.disk_mask_check.isChecked())
        tab.disk_mask_check.setChecked(False)
        self.assertIs(win.state.project.config["mask_reverse_flow_plots"], False)
        tab.disk_mask_check.setChecked(True)
        self.assertIs(win.state.project.config["mask_reverse_flow_plots"], True)

    def test_abrir_projeto_nao_marca_trabalho_nao_salvo(self):
        proj = _make_project()
        proj.config["mask_reverse_flow_plots"] = False
        win, _ = self._janela_na_aba_results(proj)
        self.assertFalse(win.state.unsaved,
                          "syncing the checkbox with the project must not dirty it")


if __name__ == "__main__":   # pragma: no cover
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    unittest.main()
