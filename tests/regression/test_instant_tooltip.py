"""Verify the non-blocking instant field tooltip behavior.

The tests construct the tooltip widget, provide field text, and inspect visibility
and timing transitions without relying on the native Qt tooltip delay. They cover
presentation behavior only and do not invoke the solver or modify project files.
"""
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
        self.window = QWidget()
        self.window.resize(400, 300)
        self.window.show()
        _InstantTooltip._instances.clear()

    def tearDown(self):
        from zbemt.gui.instant_tooltip import _InstantTooltip
        _InstantTooltip._instances.clear()

    def _hover_em(self, widget, pos=None):
        # `pos=QPoint(5, 5)` as a DEFAULT was evaluated while the class body
        # ran -- before `skipUnless` could skip anything -- so without Qt the
        # module failed to import instead of skipping.
        if pos is None:
            pos = QPoint(5, 5)
        ev = QEnterEvent(QPointF(pos), QPointF(pos), QPointF(pos))
        widget._instant_tooltip_filter.eventFilter(widget, ev)

    def _leave(self, widget):
        ev = QEvent(QEvent.Type.Leave)
        widget._instant_tooltip_filter.eventFilter(widget, ev)

    def test_hover_shows_the_text_returned_by_text_fn(self):
        from zbemt.gui.instant_tooltip import install_instant_tooltip, _InstantTooltip
        lbl = QLabel("target", self.window)
        lbl.show()
        install_instant_tooltip(lbl, lambda _pos: "explanation")

        self._hover_em(lbl)

        tooltip = _InstantTooltip.instance(lbl)
        self.assertTrue(tooltip.isVisible())
        self.assertEqual(tooltip.text(), "explanation")

    def test_text_fn_none_shows_nothing(self):
        from zbemt.gui.instant_tooltip import install_instant_tooltip, _InstantTooltip
        lbl = QLabel("target", self.window)
        lbl.show()
        install_instant_tooltip(lbl, lambda _pos: None)

        self._hover_em(lbl)

        tooltip = _InstantTooltip.instance(lbl)
        self.assertFalse(tooltip.isVisible())

    def test_leaving_the_widget_hides_the_tooltip(self):
        from zbemt.gui.instant_tooltip import install_instant_tooltip, _InstantTooltip
        lbl = QLabel("target", self.window)
        lbl.show()
        install_instant_tooltip(lbl, lambda _pos: "explanation")

        self._hover_em(lbl)
        self.assertTrue(_InstantTooltip.instance(lbl).isVisible())

        self._leave(lbl)
        self.assertFalse(_InstantTooltip.instance(lbl).isVisible())

    def test_losing_focus_hides_the_tooltip(self):
        from zbemt.gui.instant_tooltip import install_instant_tooltip, _InstantTooltip
        lbl = QLabel("target", self.window)
        lbl.show()
        install_instant_tooltip(lbl, lambda _pos: "explanation")
        self._hover_em(lbl)
        event = QEvent(QEvent.Type.FocusOut)
        lbl._instant_tooltip_filter.eventFilter(lbl, event)
        self.assertFalse(_InstantTooltip.instance(lbl).isVisible())

    def test_text_fn_receives_local_position_for_composite_widgets(self):
        """The central use case: a table header with different text
        per column, mapped from `local_pos.x()`."""
        from zbemt.gui.instant_tooltip import install_instant_tooltip, _InstantTooltip
        widget = QWidget(self.window)
        widget.resize(200, 20)
        widget.show()

        def text_fn(pos):
            return "left" if pos.x() < 100 else "right"

        install_instant_tooltip(widget, text_fn)

        self._hover_em(widget, pos=QPoint(10, 5))
        self.assertEqual(_InstantTooltip.instance(widget).text(), "left")

        self._hover_em(widget, pos=QPoint(150, 5))
        self.assertEqual(_InstantTooltip.instance(widget).text(), "right")


if __name__ == "__main__":
    unittest.main()
