"""Mouse wheel only edits a field that has FOCUS.

The problem this solves: in a form inside `QScrollArea` (which is how
Geometry/Airfoil/Config are assembled), passing the mouse wheel over a
`QDoubleSpinBox`/`QComboBox` while scrolling SILENTLY changes that
field's value. The user was just scrolling the page, and leaves with a
chord, a collective pitch, or an inflow model swapped without noticing --
and the `.bemt` marked as unsaved by an edit they never meant to make.

The fix is not simply SWALLOWING the event (that would leave the page
stuck: the wheel would stop scrolling whenever the cursor crossed a
field). It is to redirect: without focus, the wheel event is resent to
the ancestor `QAbstractScrollArea`, which scrolls normally; with focus,
the field receives the event and edits as usual. This way "click the
field and turn the wheel" keeps working, which is the deliberate gesture,
and "pass the mouse over it" becomes harmless again.

`Qt.FocusPolicy.StrongFocus` (instead of these widgets' default
`WheelFocus`) is part of the fix: with `WheelFocus`, the wheel itself
GIVES focus to the field, and the second notch of the wheel would
already edit the value.
"""
from __future__ import annotations

from PyQt6.QtCore import QEvent, QObject, Qt
from PyQt6.QtWidgets import (
    QAbstractScrollArea,
    QAbstractSpinBox,
    QApplication,
    QComboBox,
    QSlider,
    QWidget,
)

#: Widgets that edit a value with the wheel and, therefore, need the guard.
#: `QAbstractSpinBox` covers QSpinBox/QDoubleSpinBox/QDateTimeEdit at once.
_WIDGETS_SENSIVEIS = (QAbstractSpinBox, QComboBox, QSlider)


def _area_rolavel_ancestral(widget: QWidget) -> QAbstractScrollArea | None:
    """Walks up the parent tree until it finds the scrollable area that
    contains the widget -- that is where the wheel event goes when the
    field has no focus."""
    pai = widget.parentWidget()
    while pai is not None:
        if isinstance(pai, QAbstractScrollArea):
            return pai
        pai = pai.parentWidget()
    return None


class GuardaDeRoda(QObject):
    """Application-wide event filter: discards the wheel on an unfocused
    field and returns it to the surrounding scrollable area."""

    def eventFilter(self, obj: QObject, event: QEvent) -> bool:
        if event.type() != QEvent.Type.Wheel:
            return False
        if not isinstance(obj, _WIDGETS_SENSIVEIS):
            return False
        # Open combo (the dropdown list) should scroll normally: there the
        # wheel navigates the list, it doesn't change the value by accident.
        if isinstance(obj, QComboBox) and obj.view().isVisible():
            return False
        if obj.hasFocus():
            return False   # deliberate gesture: a focused field edits as usual

        area = _area_rolavel_ancestral(obj)
        if area is not None:
            QApplication.sendEvent(area.viewport(), event)
        return True   # never reaches the field -- no value changes


def instalar_guarda_de_roda(app: QApplication) -> GuardaDeRoda:
    """Installs the guard for the whole application. Returns the filter
    (the caller needs to keep the reference alive: an ownerless `QObject`
    is garbage-collected by Python and the filter stops firing)."""
    guarda = GuardaDeRoda(app)
    app.installEventFilter(guarda)
    return guarda


def ajustar_politica_de_foco(raiz: QWidget) -> int:
    """Swaps `WheelFocus` for `StrongFocus` on the sensitive fields under
    ``raiz``. Without this, the first turn of the wheel would give focus
    to the field and the second would already edit the value -- the guard
    above would be bypassed by the very gesture it exists to neutralize.

    Returns how many widgets were adjusted."""
    ajustados = 0
    for tipo in _WIDGETS_SENSIVEIS:
        for widget in raiz.findChildren(tipo):
            if widget.focusPolicy() == Qt.FocusPolicy.WheelFocus:
                widget.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
                ajustados += 1
    return ajustados
