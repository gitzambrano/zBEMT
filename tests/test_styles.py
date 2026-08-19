"""Regression guard for `zbemt/gui/styles.py`.

Any QSS rule targeting `QCheckBox`/`QRadioButton` (even just `spacing`)
strips the native style (Fusion) of the indicator drawing and requires
the QSS to draw ALL sub-parts -- without an explicit ``::indicator``
rule with a border, the unchecked square vanishes completely. Seen on
screen: no unchecked checkbox in the GUI had a visible square.
"""
import re
import unittest

from tests.helpers import HAS_QT

# Reads the GUI stylesheet: without Qt there is nothing to check, and the CI
# job that installs the base dependencies only (to prove the engine runs
# without Qt) must see this module SKIPPED, not a collection error.
if not HAS_QT:                                   # pragma: no cover
    raise unittest.SkipTest("PyQt6 is not installed (the engine and CLI run "
                            "without it on purpose)")

from zbemt.gui import styles


class TestIndicadorDeCheckboxEVisivel(unittest.TestCase):
    def test_indicador_desmarcado_tem_borda_e_tamanho_explicitos(self):
        css = styles.APP_QSS
        bloco = re.search(
            r"QCheckBox::indicator,\s*QRadioButton::indicator\s*\{([^}]*)\}", css)
        self.assertIsNotNone(bloco, "sem regra QCheckBox::indicator no QSS")
        corpo = bloco.group(1)
        self.assertIn("border:", corpo)
        self.assertIn("width:", corpo)
        self.assertIn("height:", corpo)

    def test_indicador_marcado_tem_cor_de_preenchimento_distinta(self):
        css = styles.APP_QSS
        self.assertIn("QCheckBox::indicator:checked", css)
        self.assertIn("QRadioButton::indicator:checked", css)


class TestSetasDeControleExistem(unittest.TestCase):
    """Same pitfall as the checkbox indicator above, in two other controls:
    any QSS rule on `QComboBox`/`QSpinBox` strips Fusion of the sub-part
    drawing. Seen on screen: NO dropdown in the GUI had an arrow (every
    combo looked indistinguishable from a QLineEdit) and the spinbox step
    buttons came out as a broken glyph shaped like a bracket.

    The triangle via CSS border doesn't work -- Qt paints a rectangle.
    The arrows are SVGs in `zbemt/gui/assets/`, and their existence on
    disk is what this test guards: a `url()` pointing to a non-existent
    file fails in SILENCE (the arrow disappears, the QSS doesn't complain)."""

    def test_combo_e_spinbox_declaram_imagem_de_seta(self):
        css = styles.APP_QSS
        for regra in ("QComboBox::down-arrow",
                      "QSpinBox::up-arrow", "QSpinBox::down-arrow",
                      "QDoubleSpinBox::up-arrow", "QDoubleSpinBox::down-arrow"):
            self.assertIn(regra, css, f"sem regra {regra} no QSS")
        self.assertIn("image: url(", css)

    def test_todo_svg_referenciado_pelo_qss_existe_em_disco(self):
        from pathlib import Path

        referencias = re.findall(r"image:\s*url\(([^)]+)\)", styles.APP_QSS)
        self.assertTrue(referencias, "nenhum `image: url(...)` no QSS")
        faltando = [r for r in referencias if not Path(r).is_file()]
        self.assertEqual(faltando, [], f"SVG(s) de seta ausentes: {faltando}")


class TestBotoesDeMessageBoxNaoCortam(unittest.TestCase):
    """Bug: `QMessageBox QPushButton { max-width: none; }` -- Qt doesn't
    handle "none" well for this property and instead of removing the limit,
    it collapsed ALL sibling buttons to a uniform width smaller than the
    text itself (reproduced: "Discard"/"Cancel" cut to ~69px needing
    84/72px). See comment in `styles.py`."""

    @classmethod
    def setUpClass(cls):
        from PyQt6.QtWidgets import QApplication
        cls.app = QApplication.instance() or QApplication([])
        cls.app.setStyle("Fusion")
        cls.app.setStyleSheet(styles.APP_QSS)

    def test_todo_botao_de_confirmacao_cabe_seu_proprio_texto(self):
        from PyQt6.QtWidgets import QMessageBox, QPushButton
        from PyQt6.QtGui import QFontMetrics

        mb = QMessageBox()
        mb.setText("There is unsaved work:")
        mb.setStandardButtons(
            QMessageBox.StandardButton.Save
            | QMessageBox.StandardButton.Discard
            | QMessageBox.StandardButton.Cancel
        )
        mb.setDefaultButton(QMessageBox.StandardButton.Save)
        mb.show()
        self.app.processEvents()
        try:
            botoes = mb.findChildren(QPushButton)
            self.assertTrue(botoes)
            for btn in botoes:
                largura_texto = QFontMetrics(btn.font()).horizontalAdvance(btn.text())
                self.assertGreaterEqual(
                    btn.width(), largura_texto,
                    f"button {btn.text()!r} clipped: width={btn.width()}px, text needs {largura_texto}px")
        finally:
            mb.close()


class TestNenhumBotaoDaGuiCortaOProprioTexto(unittest.TestCase):
    """Bug: `QPushButton { max-width: 360px; }` -- Qt clamps the computed
    sizeHint to this limit (not just a layout ceiling), so any real button
    with longer text gets cut off. Found when instantiating the real tabs:
    "Check airfoil (live preview on the right)" (Airfoil) needs ~492px and
    got 390px. Scans every visible QPushButton in each tab, not just the
    case found -- to catch the next long label before it becomes a bug
    again."""

    @classmethod
    def setUpClass(cls):
        from PyQt6.QtWidgets import QApplication
        cls.app = QApplication.instance() or QApplication([])
        cls.app.setStyle("Fusion")
        cls.app.setStyleSheet(styles.APP_QSS)

    def test_todo_pushbutton_visivel_cabe_seu_texto(self):
        from PyQt6.QtWidgets import QPushButton
        from PyQt6.QtGui import QFontMetrics
        from zbemt.gui.common import AppState
        from zbemt.gui.tabs.config import ConfigMotorTab
        from zbemt.gui.tabs.airfoil import AirfoilTab
        from zbemt.gui.tabs.geometry_tab import GeometryTab
        from zbemt.gui.tabs.run_case import RunCaseTab
        from zbemt.gui.tabs.run_batch import RunBatchTab
        from zbemt.gui.tabs.project import ProjectTab

        state = AppState()
        abas = {
            "Project": ProjectTab(state),
            "Geometry": GeometryTab(state),
            "Airfoil": AirfoilTab(state),
            "Config": ConfigMotorTab(state),
            "Run Case": RunCaseTab(state),
            "Run Batch": RunBatchTab(state),
        }
        cortados = []
        for nome, aba in abas.items():
            aba.resize(1400, 900)
            aba.show()
            self.app.processEvents()
            for btn in aba.findChildren(QPushButton):
                texto = btn.text()
                if not texto or len(texto) <= 1:
                    continue  # help "?" buttons: 1 character, never cut
                largura_texto = QFontMetrics(btn.font()).horizontalAdvance(texto)
                if btn.sizeHint().width() < largura_texto:
                    cortados.append((nome, texto, btn.sizeHint().width(), largura_texto))
            aba.close()
        self.assertEqual(
            cortados, [],
            f"Clipped button(s) (width < required text): {cortados}")


if __name__ == "__main__":
    unittest.main()
