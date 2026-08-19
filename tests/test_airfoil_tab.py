"""Regressions in the Airfoil tab and geometry generation dialog.

Covers issues reported by the user: alpha range of preview (item 6),
canvas control bar (item 8), sections panel always visible (item 9),
Reynolds/Mach suggestion (item 15), legend by condition (item 32), and
editable number of blades/radius in the dialog (item 2).
"""
import unittest

import numpy as np
from PyQt6.QtWidgets import QApplication, QDoubleSpinBox, QLineEdit, QComboBox, QCheckBox
from PyQt6.QtCore import Qt

from zbemt import airfoils, geometry
from zbemt.models import PolarSlice, AirfoilDef, FlightCondition
from zbemt.gui.common import AppState
from zbemt.gui.dialogs import GeometryGeneratorDialog
from zbemt.gui.tabs.airfoil import AirfoilTab
from zbemt.gui.tabs.geometry_tab import GeometryTab

from tests.helpers import make_studies_project, patch_em_toda_gui


#: Kept alive at module scope -- QApplication.instance() only survives
#: between calls if something holds a reference to the object. Every
#: other GUI test file stashes it on the TestCase class (cls.app); this
#: file's tests are plain functions, so a module global does the same
#: job. Without it, the QApplication gets garbage-collected right after
#: _app() returns and Qt aborts the process on the next QWidget().
_QAPP = None


def _app() -> QApplication:
    global _QAPP
    _QAPP = QApplication.instance() or QApplication([])
    return _QAPP


def _tab_com_projeto(**airfoil_kwargs):
    """Create an AirfoilTab with a loaded project (the state where
    the user actually uses the tab)."""
    _app()
    state = AppState()
    projeto = make_studies_project()
    for k, v in airfoil_kwargs.items():
        setattr(projeto.airfoil, k, v)
    state.project = projeto
    aba = AirfoilTab(state)
    state.notify_airfoil()
    return aba, state


def _spans(aba) -> list:
    """(min, max) de alpha de cada curva que o preview desenharia."""
    d = aba._collect_airfoil_def()
    return [(float(np.min(c["alpha_deg"])), float(np.max(c["alpha_deg"])))
            for c in aba._collect_polar_curves(d)]


class FaixaDeAlphaDoPreview(unittest.TestCase):
    """Item 6: with Viterna extension active, the curve must be
    CALCULATED to ±180 -- rescaling the axis via matplotlib's bar does
    not recalculate anything, and the user saw an empty plot after 30°."""

    def test_viterna_ativa_desenha_ate_180(self):
        aba, _ = _tab_com_projeto(stall_model="viterna")
        self.assertEqual(aba.alpha_range_combo.currentText(), aba._FAIXA_COMPLETA)
        for lo, hi in _spans(aba):
            self.assertAlmostEqual(lo, -180.0)
            self.assertAlmostEqual(hi, 180.0)

    def test_sem_viterna_continua_na_faixa_tipica(self):
        aba, _ = _tab_com_projeto(stall_model="clip")
        self.assertEqual(aba.alpha_range_combo.currentText(), aba._FAIXA_TIPICA)
        for lo, hi in _spans(aba):
            self.assertAlmostEqual(lo, -30.0)
            self.assertAlmostEqual(hi, 30.0)

    def test_ligar_viterna_em_tempo_real_abre_a_faixa(self):
        aba, _ = _tab_com_projeto(stall_model="clip")
        aba.stall_model_combo.setCurrentText("viterna")
        self.assertEqual(aba.alpha_range_combo.currentText(), aba._FAIXA_COMPLETA)
        self.assertAlmostEqual(_spans(aba)[0][1], 180.0)

    def test_escolha_explicita_do_usuario_vence(self):
        aba, _ = _tab_com_projeto(stall_model="clip")
        # simula o usuario escolhendo no combo (sinal `activated`)
        aba.alpha_range_combo.setCurrentText(aba._FAIXA_TIPICA)
        aba.alpha_range_combo.activated.emit(0)
        aba.stall_model_combo.setCurrentText("viterna")
        self.assertEqual(aba.alpha_range_combo.currentText(), aba._FAIXA_TIPICA)


class FaixaDeControlesDoCanvas(unittest.TestCase):
    """Item 8: plot controls moved from the left form to a bar above
    the canvas; they must remain (a) connected and (b) without dirtying
    the project."""

    def test_controles_nao_estao_mais_no_formulario_esquerdo(self):
        aba, _ = _tab_com_projeto()
        # o formulario esquerdo e' o widget dentro da QScrollArea do splitter
        esquerda = aba._airfoil_left_widget
        for w in (aba.alpha_range_combo, aba.autoscale_y_check,
                  aba.show_reverse_branch_check, aba.mach_compare_edit):
            self.assertFalse(esquerda.isAncestorOf(w),
                             f"{w} continua dentro do formulario da esquerda")

    def test_caixas_marcadas_por_padrao(self):
        aba, _ = _tab_com_projeto()
        self.assertTrue(aba.autoscale_y_check.isChecked())
        self.assertTrue(aba.show_reverse_branch_check.isChecked())

    def test_ramo_reverso_aparece_por_padrao_nas_curvas(self):
        aba, _ = _tab_com_projeto()
        rotulos = [c["label"] for c in aba._collect_polar_curves(aba._collect_airfoil_def())]
        self.assertTrue(any("reverse flow" in r for r in rotulos), rotulos)

    def test_controles_de_plot_nao_sujam_o_projeto(self):
        aba, _ = _tab_com_projeto()
        aba._clear_dirty()
        aba.autoscale_y_check.setChecked(False)
        aba.show_reverse_branch_check.setChecked(False)
        aba.alpha_range_combo.setCurrentText(aba._FAIXA_COMPLETA)
        aba.mach_compare_edit.setText("0.0, 0.2")
        aba.mach_compare_edit.editingFinished.emit()
        self.assertFalse(aba._dirty)

    def test_controles_de_plot_continuam_ligados_ao_redesenho(self):
        """A armadilha do item 8: movidos para fora de `left_widget`, eles
        perdem as conexoes genericas por findChildren."""
        aba, _ = _tab_com_projeto()
        aba._preview_timer.stop()
        aba.autoscale_y_check.setChecked(False)
        self.assertTrue(aba._preview_timer.isActive())
        aba._preview_timer.stop()
        aba.show_reverse_branch_check.setChecked(False)
        self.assertTrue(aba._preview_timer.isActive())
        aba._preview_timer.stop()
        aba.alpha_range_combo.setCurrentText(aba._FAIXA_COMPLETA)
        self.assertTrue(aba._preview_timer.isActive())

    def test_grupo_de_visualizacao_comparativa_sumiu_do_formulario(self):
        aba, _ = _tab_com_projeto()
        titulos = [b.title() for b in aba.findChildren(type(aba.table_box))]
        self.assertNotIn("Comparative Visualization", titulos)


class PainelDeSecoes(unittest.TestCase):
    """Item 9: a lista de secoes existe tambem em modo aerofolio unico."""

    def test_lista_visivel_com_uma_linha_all(self):
        aba, _ = _tab_com_projeto(name="perfil X")
        self.assertTrue(aba.sections_list.isVisibleTo(aba))
        self.assertEqual(aba.sections_list.count(), 1)
        self.assertIn("r/R=all", aba.sections_list.item(0).text())
        self.assertIn("perfil X", aba.sections_list.item(0).text())

    def test_linha_de_r_norm_continua_escondida_em_modo_unico(self):
        aba, _ = _tab_com_projeto()
        for w in aba._section_r_row_widgets:
            self.assertFalse(w.isVisibleTo(aba))

    def test_selecionar_a_linha_sintetica_nao_troca_de_secao(self):
        aba, _ = _tab_com_projeto()
        aba.sections_list.setCurrentRow(0)
        self.assertEqual(aba._current_section_index, -1)
        self.assertEqual(aba._sections, [])

    def test_adicionar_secao_passa_para_multi(self):
        aba, _ = _tab_com_projeto()
        aba._add_section()
        self.assertEqual(len(aba._sections), 2)
        self.assertEqual(aba.sections_list.count(), 2)
        self.assertTrue(all(w.isVisibleTo(aba) for w in aba._section_r_row_widgets))

    def test_remover_volta_para_a_linha_unica(self):
        aba, _ = _tab_com_projeto()
        aba._add_section()
        aba._remove_section()
        aba._remove_section()
        self.assertEqual(aba._sections, [])
        self.assertEqual(aba.sections_list.count(), 1)
        self.assertIn("r/R=all", aba.sections_list.item(0).text())


class SugestaoDeReynoldsEMach(unittest.TestCase):
    """Item 15: estimativa fechada, sem rodar o motor."""

    def test_tres_valores_crescentes_de_re_e_mach(self):
        geom = geometry.generate_tapered(root_chord_norm=0.10, tip_chord_norm=0.04,
                                          radius_m=2.0, n_stations=12)
        s = airfoils.suggest_reynolds_mach_lists(geom, rpm=600.0)
        self.assertEqual(len(s["reynolds"]), 3)
        self.assertEqual(len(s["mach"]), 3)
        self.assertEqual(s["reynolds"], sorted(s["reynolds"]))
        self.assertEqual(s["mach"], sorted(s["mach"]))

    def test_bate_com_a_conta_fechada_na_estacao_de_referencia(self):
        geom = geometry.generate_rectangular(chord_norm=0.08, radius_m=1.5, n_stations=11)
        rpm, nu, a = 900.0, 1.46e-5, 340.294
        s = airfoils.suggest_reynolds_mach_lists(geom, rpm=rpm, nu_air=nu, a_sound=a)
        omega = rpm * 2 * np.pi / 60.0
        U = omega * 1.5 * airfoils.REFERENCE_RADIUS_NORM
        re_esperado = U * (0.08 * 1.5) / nu
        # a lista e' arredondada a 2 algarismos significativos
        self.assertTrue(any(abs(v - re_esperado) / re_esperado < 0.05 for v in s["reynolds"]),
                        (s["reynolds"], re_esperado))
        self.assertAlmostEqual(s["mach"][1], round(U / a, 2), places=2)

    def test_geometria_degenerada_nao_levanta(self):
        vazio = airfoils.suggest_reynolds_mach_lists(None, rpm=600.0)
        self.assertEqual(vazio, {"reynolds": [], "mach": []})

    def test_sugestao_mantem_tres_estacoes_mesmo_com_arredondamento(self):
        geom = geometry.generate_rectangular(chord_norm=0.08, radius_m=1.0,
                                              n_stations=8)
        s = airfoils.suggest_reynolds_mach_lists(geom, rpm=1.0)
        self.assertEqual(len(s["reynolds"]), 3)
        self.assertEqual(len(s["mach"]), 3)

    def test_gui_preenche_ao_entrar_no_modo_neuralfoil(self):
        aba, state = _tab_com_projeto()
        state.project.saved_cases = [FlightCondition(name="c", rpm=1200.0)]
        antes = aba.re_list_edit.text()
        aba.source_combo.setCurrentText("neuralfoil")
        self.assertNotEqual(aba.re_list_edit.text(), antes)
        self.assertEqual(len(airfoils.parse_floats(aba.re_list_edit.text())
                             if hasattr(airfoils, "parse_floats")
                             else [v for v in aba.re_list_edit.text().split(",") if v.strip()]), 3)
        self.assertEqual(len([v for v in aba.mach_list_edit.text().split(",") if v.strip()]), 3)

    def test_gui_respeita_lista_digitada_pelo_usuario(self):
        aba, _ = _tab_com_projeto()
        aba.re_list_edit.setText("1234, 5678")
        aba.re_list_edit.textEdited.emit("1234, 5678")   # simula digitacao
        aba.source_combo.setCurrentText("neuralfoil")
        self.assertEqual(aba.re_list_edit.text(), "1234, 5678")

    def test_botao_suggest_sobrescreve_mesmo_apos_edicao(self):
        aba, _ = _tab_com_projeto()
        aba.re_list_edit.setText("1234")
        aba.re_list_edit.textEdited.emit("1234")
        aba._suggest_re_mach(force=True)
        self.assertNotEqual(aba.re_list_edit.text(), "1234")


class LegendaPorCondicao(unittest.TestCase):
    """Item 32: cada fatia gerada leva o SEU Reynolds/Mach na legenda."""

    def _slices_neuralfoil(self):
        # external_solvers uses a single `label` for the entire sweep
        return [
            PolarSlice(alpha_deg=[-5, 0, 5], cl=[-0.3, 0.1, 0.6], cd=[0.02, 0.01, 0.02],
                       reynolds=1e5, mach=0.0, label="neuralfoil:naca4 2412"),
            PolarSlice(alpha_deg=[-5, 0, 5], cl=[-0.3, 0.1, 0.6], cd=[0.02, 0.01, 0.02],
                       reynolds=5e5, mach=0.3, label="neuralfoil:naca4 2412"),
        ]

    def test_label_generico_nao_engole_mais_re_e_mach(self):
        rotulo = airfoils.condition_label(
            {"reynolds": 1e5, "mach": 0.3, "label": "neuralfoil:naca4 2412"})
        self.assertIn("Re=1e+05", rotulo)
        self.assertIn("M=0.30", rotulo)
        self.assertIn("neuralfoil:naca4 2412", rotulo)

    def test_label_sozinho_quando_nao_ha_condicao(self):
        self.assertEqual(airfoils.condition_label({"label": "meu_csv"}), "meu_csv")

    def test_curvas_de_overlay_tem_legendas_distintas(self):
        a = AirfoilDef(source="table", table_slices=self._slices_neuralfoil())
        conds = airfoils.unique_conditions(a)
        curvas = airfoils.preview_polar_multi(a, conditions=conds, alpha_deg_range=(-5, 5, 5.0))
        rotulos = [c["label"] for c in curvas]
        self.assertEqual(len(set(rotulos)), len(rotulos), rotulos)

    def test_curva_selecionada_do_canvas_tambem(self):
        aba, state = _tab_com_projeto()
        state.project.airfoil = AirfoilDef(source="table", extend_full_range=False,
                                            table_slices=self._slices_neuralfoil())
        state.notify_airfoil()
        aba._nav_selection = {"r_norm": None, "reynolds": 5e5, "mach": 0.3}
        curvas = aba._collect_polar_curves(aba._collect_airfoil_def())
        self.assertIn("Re=5e+05", curvas[0]["label"])


class PopupDeGeracaoDeGeometria(unittest.TestCase):
    """Itens 1 e 2 do popup GeometryGeneratorDialog."""

    def test_popup_do_combo_nao_elide_as_opcoes(self):
        _app()
        dlg = GeometryGeneratorDialog(None, 3, 1.0)
        combo = dlg.kind_combo
        self.assertEqual(combo.view().textElideMode(), Qt.TextElideMode.ElideNone)
        fm = combo.fontMetrics()
        mais_largo = max(fm.horizontalAdvance(combo.itemText(i)) for i in range(combo.count()))
        self.assertGreaterEqual(combo.minimumWidth(), mais_largo)
        self.assertGreaterEqual(combo.view().minimumWidth(), mais_largo)

    def test_n_pas_e_raio_sao_editaveis_e_partem_do_valor_recebido(self):
        _app()
        dlg = GeometryGeneratorDialog(None, 4, 2.5)
        self.assertEqual(dlg.n_blades.value(), 4)
        self.assertAlmostEqual(dlg.radius_m.value(), 2.5)
        self.assertTrue(dlg.n_blades.isEnabled())
        self.assertTrue(dlg.radius_m.isEnabled())

    def test_mudar_n_pas_atualiza_solidez_ao_vivo(self):
        _app()
        dlg = GeometryGeneratorDialog(None, 2, 1.0)
        sigma2 = dlg.solidity.value()
        ar2 = dlg.aspect_ratio.value()
        dlg.n_blades.setValue(4)
        self.assertAlmostEqual(dlg.solidity.value(), 2 * sigma2, places=4)
        # AR e' por PA: nao depende do numero de pas
        self.assertAlmostEqual(dlg.aspect_ratio.value(), ar2, places=2)

    def test_geometria_gerada_usa_os_valores_editados_no_popup(self):
        _app()
        dlg = GeometryGeneratorDialog(None, 2, 1.0)
        dlg.n_blades.setValue(5)
        dlg.radius_m.setValue(3.0)
        dlg._on_confirm()
        self.assertIsNotNone(dlg.generated_geom)
        self.assertEqual(dlg.generated_geom.n_blades, 5)
        self.assertAlmostEqual(dlg.generated_geom.radius_m, 3.0)

    def test_geometry_tab_absorve_o_round_trip(self):
        _app()
        state = AppState()
        state.project = make_studies_project()
        with patch_em_toda_gui("QMessageBox"):
            aba = GeometryTab(state)
            state.notify_geometry()
            nova = geometry.generate_rectangular(chord_norm=0.09, radius_m=4.0,
                                                  n_blades=6, n_stations=8)
            aba.state.project.geometry = nova
            aba._sync_constants_from_geometry(nova)
        self.assertEqual(aba.n_blades.value(), 6)
        self.assertAlmostEqual(aba.radius_m.value(), 4.0)
        # e o espelhamento nao pode disparar `_apply_constants` de volta
        self.assertEqual(aba.state.project.geometry.n_blades, 6)


if __name__ == "__main__":
    unittest.main()
