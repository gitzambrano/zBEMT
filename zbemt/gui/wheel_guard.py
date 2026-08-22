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
_SENSITIVE_WIDGETS = (QAbstractSpinBox, QComboBox, QSlider)


def _ancestor_scroll_area(widget: QWidget) -> QAbstractScrollArea | None:
    """Walks up the parent tree until it finds the scrollable scroll_area that
    contains the widget -- that is where the wheel event goes when the
    field has no focus."""
    parent = widget.parentWidget()
    while parent is not None:
        if isinstance(parent, QAbstractScrollArea):
            return parent
        parent = parent.parentWidget()
    return None


class WheelGuard(QObject):
    """Application-wide event filter: discards the wheel on an unfocused
    field and returns it to the surrounding scrollable scroll_area."""

    def eventFilter(self, obj: QObject, event: QEvent) -> bool:
        if event.type() != QEvent.Type.Wheel:
            return False
        if not isinstance(obj, _SENSITIVE_WIDGETS):
            return False
        # Open combo (the dropdown list) should scroll normally: there the
        # wheel navigates the list, it doesn't change the value by accident.
        if isinstance(obj, QComboBox) and obj.view().isVisible():
            return False
        if obj.hasFocus():
            return False   # deliberate gesture: a focused field edits as usual

        scroll_area = _ancestor_scroll_area(obj)
        if scroll_area is not None:
            QApplication.sendEvent(scroll_area.viewport(), event)
        return True   # never reaches the field -- no value changes


def install_wheel_guard(app: QApplication) -> WheelGuard:
    """Installs the guard for the whole application. Returns the filter
    (the caller needs to keep the reference alive: an ownerless `QObject`
    is garbage-collected by Python and the filter stops firing)."""
    guard = WheelGuard(app)
    app.installEventFilter(guard)
    return guard


def adjust_focus_policy(root: QWidget) -> int:
    """Swaps `WheelFocus` for `StrongFocus` on the sensitive fields under
    ``root``. Without this, the first turn of the wheel would give focus
    to the field and the second would already edit the value -- the guard
    above would be bypassed by the very gesture it exists to neutralize.

    Returns how many widgets were adjusted."""
    adjusted = 0
    for widget_type in _SENSITIVE_WIDGETS:
        for widget in root.findChildren(widget_type):
            if widget.focusPolicy() == Qt.FocusPolicy.WheelFocus:
                widget.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
                adjusted += 1
    return adjusted
