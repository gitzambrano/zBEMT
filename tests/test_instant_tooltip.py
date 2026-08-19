"""Instant tooltip (zbemt/gui/instant_tooltip.py): shows/hides without
relying on the native QToolTip delay."""
import os
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

try:
    from PyQt6.QtWidgets import QApplication, QWidget, QLabel
    from PyQt6.QtCore import QEvent, QPoint, QPointF
    from PyQt6.QtGui import QEnterEvent
    _HAS_QT = True
except Exception:  # pragma: no cover
    _HAS_QT = False


@unittest.skipUnless(_HAS_QT, "PyQt6 not installed in this environment")
class TestInstantTooltip(unittest.TestCase):
    def setUp(self):
        import sys
        from zbemt.gui.instant_tooltip import _InstantTooltip
        self.app = QApplication.instance() or QApplication(sys.argv)
        self.janela = QWidget()
        self.janela.resize(400, 300)
        self.janela.show()
        _InstantTooltip._instancias.clear()

    def tearDown(self):
        from zbemt.gui.instant_tooltip import _InstantTooltip
        _InstantTooltip._instancias.clear()

    def _hover_em(self, widget, pos=QPoint(5, 5)):
        ev = QEnterEvent(QPointF(pos), QPointF(pos), QPointF(pos))
        widget._instant_tooltip_filter.eventFilter(widget, ev)

    def _sai_de(self, widget):
        ev = QEvent(QEvent.Type.Leave)
        widget._instant_tooltip_filter.eventFilter(widget, ev)

    def test_hover_mostra_texto_devolvido_por_text_fn(self):
        from zbemt.gui.instant_tooltip import install_instant_tooltip, _InstantTooltip
        lbl = QLabel("alvo", self.janela)
        lbl.show()
        install_instant_tooltip(lbl, lambda _pos: "explicação")

        self._hover_em(lbl)

        tooltip = _InstantTooltip.instancia(lbl)
        self.assertTrue(tooltip.isVisible())
        self.assertEqual(tooltip.text(), "explicação")

    def test_text_fn_none_nao_mostra_nada(self):
        from zbemt.gui.instant_tooltip import install_instant_tooltip, _InstantTooltip
        lbl = QLabel("alvo", self.janela)
        lbl.show()
        install_instant_tooltip(lbl, lambda _pos: None)

        self._hover_em(lbl)

        tooltip = _InstantTooltip.instancia(lbl)
        self.assertFalse(tooltip.isVisible())

    def test_sair_do_widget_esconde_o_tooltip(self):
        from zbemt.gui.instant_tooltip import install_instant_tooltip, _InstantTooltip
        lbl = QLabel("alvo", self.janela)
        lbl.show()
        install_instant_tooltip(lbl, lambda _pos: "explicação")

        self._hover_em(lbl)
        self.assertTrue(_InstantTooltip.instancia(lbl).isVisible())

        self._sai_de(lbl)
        self.assertFalse(_InstantTooltip.instancia(lbl).isVisible())

    def test_perda_de_foco_esconde_o_tooltip(self):
        from zbemt.gui.instant_tooltip import install_instant_tooltip, _InstantTooltip
        lbl = QLabel("alvo", self.janela)
        lbl.show()
        install_instant_tooltip(lbl, lambda _pos: "explicação")
        self._hover_em(lbl)
        event = QEvent(QEvent.Type.FocusOut)
        lbl._instant_tooltip_filter.eventFilter(lbl, event)
        self.assertFalse(_InstantTooltip.instancia(lbl).isVisible())

    def test_text_fn_recebe_posicao_local_para_widgets_compostos(self):
        """The central use case: a table header with different text
        per column, mapped from `local_pos.x()`."""
        from zbemt.gui.instant_tooltip import install_instant_tooltip, _InstantTooltip
        widget = QWidget(self.janela)
        widget.resize(200, 20)
        widget.show()

        def text_fn(pos):
            return "esquerda" if pos.x() < 100 else "direita"

        install_instant_tooltip(widget, text_fn)

        self._hover_em(widget, pos=QPoint(10, 5))
        self.assertEqual(_InstantTooltip.instancia(widget).text(), "esquerda")

        self._hover_em(widget, pos=QPoint(150, 5))
        self.assertEqual(_InstantTooltip.instancia(widget).text(), "direita")


if __name__ == "__main__":
    unittest.main()
