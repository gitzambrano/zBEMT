"""Instant tooltip (without the native QToolTip's ~1s delay).

Same rationale as the HTML report's CSS tooltip (`api._cabecalho_de_coluna`):
in a dense table with many short-header columns (one symbol per column),
the native delay turns reading the table into a sequence of waits. Here
the GUI equivalent (PyQt6 has no CSS tooltip) is a frameless popup
`QLabel`, positioned near the cursor, shown/hidden via an event filter on
`Enter`/`MouseMove`/`Leave` -- without relying on `QToolTip`'s internal
timer.
"""
from __future__ import annotations

from typing import Callable, Optional

from PyQt6.QtCore import QEvent, QObject, QPoint, Qt
from PyQt6.QtWidgets import QApplication, QLabel, QWidget


class _InstantTooltip(QLabel):
    """Frameless popup, singleton per root window (same pattern as
    `help_popup.HelpPopup`) -- one instant bubble at a time per window,
    not one per installed widget."""

    _instancias: dict[int, "_InstantTooltip"] = {}

    @classmethod
    def instancia(cls, pai: QWidget) -> "_InstantTooltip":
        raiz = pai.window()
        chave = id(raiz)
        if chave not in cls._instancias:
            cls._instancias[chave] = cls(raiz)
        return cls._instancias[chave]

    def __init__(self, pai: QWidget):
        super().__init__(pai, Qt.WindowType.ToolTip)
        self.setWordWrap(True)
        self.setTextFormat(Qt.TextFormat.RichText)
        self.setStyleSheet(
            "background: #2b2f38; color: #f4f5f7; border-radius: 4px;"
            " padding: 4px 8px; font-size: 11px;"
        )
        self.setMaximumWidth(520)
        self.hide()

    def mostrar(self, texto: str, pos_global: QPoint) -> None:
        self.setText(texto)
        self.adjustSize()
        tela = QApplication.primaryScreen().availableGeometry()
        x = min(pos_global.x() + 14, tela.right() - self.width() - 4)
        y = min(pos_global.y() + 18, tela.bottom() - self.height() - 4)
        self.move(max(tela.left() + 4, x), max(tela.top() + 4, y))
        self.show()


class _FiltroHoverInstantaneo(QObject):
    """`text_fn(local_pos)` returns the text to show for that position
    inside the widget (or None/"" to hide it) -- allows either a single
    tooltip widget (ignores `local_pos`) or a table header (maps
    `local_pos.x()` to the column under the cursor)."""

    def __init__(self, widget: QWidget, text_fn: Callable[[QPoint], Optional[str]]):
        super().__init__(widget)
        self._widget = widget
        self._text_fn = text_fn

    def eventFilter(self, obj: QObject, event: QEvent) -> bool:
        tipo = event.type()
        if tipo in (QEvent.Type.Enter, QEvent.Type.MouseMove):
            pos = event.position().toPoint() if hasattr(event, "position") else self._widget.mapFromGlobal(
                self._widget.cursor().pos())
            texto = self._text_fn(pos)
            tooltip = _InstantTooltip.instancia(self._widget)
            if texto:
                tooltip.mostrar(texto, self._widget.mapToGlobal(pos))
            else:
                tooltip.hide()
        elif tipo in (QEvent.Type.Leave, QEvent.Type.FocusOut,
                      QEvent.Type.WindowDeactivate, QEvent.Type.Hide):
            _InstantTooltip.instancia(self._widget).hide()
        return False


def install_instant_tooltip(widget: QWidget, text_fn: Callable[[QPoint], Optional[str]]) -> None:
    """Attaches a delay-free tooltip to `widget`: on mouse-over, calls
    `text_fn(local_pos)` (position relative to `widget`) and shows the
    returned text (plain HTML accepted) glued to the cursor; `text_fn`
    returning None/"" hides the bubble. For a simple widget (a one-line
    `QLabel`, for instance) `text_fn` can ignore `local_pos` and always
    return the same text; for a table header, `text_fn` typically maps
    `local_pos.x()` to the column under the cursor via `logicalIndexAt`.

    Enables `mouseTracking` on the widget -- without this, Qt only
    delivers `MouseMove` with a button pressed."""
    widget.setMouseTracking(True)
    filtro = _FiltroHoverInstantaneo(widget, text_fn)
    widget.installEventFilter(filtro)
    # keeps the filter alive (the event filter does not hold its own
    # reference; without this Python would collect the QObject and the
    # filter would stop firing)
    widget._instant_tooltip_filter = filtro
