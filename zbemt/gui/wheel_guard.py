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


#: Marks the widget the user last CLICKED into. Kept as an attribute on
#: the widget rather than in a set held here, so a deleted widget takes
#: it with it and no reference to a dead QObject survives.
_CLICKED = "_wheel_guard_clicked"


class WheelGuard(QObject):
    """Application-wide event filter.

    The wheel edits a field only when the user CLICKED into that field.
    Otherwise the event is handed back to the page, which scrolls.
    """

    def eventFilter(self, obj: QObject, event: QEvent) -> bool:
        kind = event.type()

        # --- keep every sensitive field off `WheelFocus` ---------------
        # Done here, at polish time, instead of by a sweep over one
        # window: a sweep has to be called for each window and re-called
        # for every field built later, and the one call that existed ran
        # before the widget tree was attached, so it adjusted nothing.
        if kind == QEvent.Type.Polish and isinstance(obj, _SENSITIVE_WIDGETS):
            if obj.focusPolicy() == Qt.FocusPolicy.WheelFocus:
                obj.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
            return False

        # --- remember the field the user actually clicked into ---------
        if kind == QEvent.Type.MouseButtonPress:
            if isinstance(obj, _SENSITIVE_WIDGETS):
                setattr(obj, _CLICKED, True)
            return False
        # Leaving the field ends the permission. Without this, one click
        # early in a session would keep that field wheel-editable for as
        # long as it lived.
        if kind == QEvent.Type.FocusOut and isinstance(obj, _SENSITIVE_WIDGETS):
            setattr(obj, _CLICKED, False)
            return False

        if kind != QEvent.Type.Wheel:
            return False
        if not isinstance(obj, _SENSITIVE_WIDGETS):
            return False
        # An OPEN combo (its dropdown list) scrolls normally: there the
        # wheel navigates the list, it does not change the value blindly.
        if isinstance(obj, QComboBox) and obj.view().isVisible():
            return False
        # The deliberate gesture: clicked into, and still there.
        if obj.hasFocus() and getattr(obj, _CLICKED, False):
            return False

        _hand_back_to_the_page(obj, event)
        return True   # never reaches the field -- no value changes


def _hand_back_to_the_page(widget: QWidget, event: QEvent) -> None:
    """Gives the wheel to whatever would have scrolled.

    The nearest scrollable ancestor first, because that is the page the
    user is scrolling. When there is none -- the Results tab, the Design
    Optimization window and the Transient window have no field inside a
    scroll area -- the event walks UP THE PARENT CHAIN instead of being
    dropped, which is how Qt propagates a wheel nobody handled. Dropping
    it is what made the wheel do nothing at all over those 37 controls.
    """
    scroll_area = _ancestor_scroll_area(widget)
    if scroll_area is not None:
        QApplication.sendEvent(scroll_area.viewport(), event)
        return
    parent = widget.parentWidget()
    while parent is not None:
        event.setAccepted(False)
        QApplication.sendEvent(parent, event)
        if event.isAccepted():
            return
        parent = parent.parentWidget()


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

    `WheelGuard` now does the same thing per widget, when the widget is
    polished, which is what actually covers every window. This remains
    for an explicit sweep over a tree that is already built, and it is
    what a test uses to assert that a window is clean.

    Returns how many widgets were adjusted."""
    adjusted = 0
    for widget_type in _SENSITIVE_WIDGETS:
        for widget in root.findChildren(widget_type):
            if widget.focusPolicy() == Qt.FocusPolicy.WheelFocus:
                widget.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
                adjusted += 1
    return adjusted
