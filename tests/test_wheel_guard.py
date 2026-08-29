"""The mouse wheel scrolls the page; it does not edit a field in passing.

Reported from use: "you are scrolling and suddenly it falls into a field
and starts changing it without you meaning to."

Three separate holes produced that, and each is checked on its own here
because each fails differently:

1. The guard stepped aside for any field with FOCUS. Focus is not a
   click: tabbing into a field, a programmatic `setFocus`, or clicking a
   field once to type a number all leave it focused, and the wheel then
   edited it whenever the cursor passed over it. The rule is now
   narrower -- the field must have been CLICKED into.

2. The guard handed the wheel to the nearest ancestor
   `QAbstractScrollArea` and DROPPED it when there was none. In the
   Results tab, the Design Optimization window and the Transient window
   no field has such an ancestor, so the wheel did nothing at all over
   37 controls.

3. `adjust_focus_policy` ran on the main window one line after the tabs
   were built, while `self.tabs` still had no parent, so it walked an
   empty tree and adjusted zero widgets. 206 of 212 sensitive fields
   were left on `WheelFocus`, the policy that lets the wheel itself take
   focus -- the exact bypass the guard exists to close.
"""
import os
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from tests.helpers import HAS_QT

if HAS_QT:                                        # pragma: no branch
    from PyQt6.QtCore import QPoint, QPointF, Qt
    from PyQt6.QtGui import QWheelEvent
    from PyQt6.QtWidgets import (QAbstractSpinBox, QApplication, QComboBox,
                                 QDoubleSpinBox, QSlider, QVBoxLayout,
                                 QWidget)

    SENSITIVE = (QAbstractSpinBox, QComboBox, QSlider)


def _wheel(widget, notches=-1):
    """One notch of the wheel over ``widget``, as Qt delivers it."""
    local = QPointF(widget.rect().center())
    return QWheelEvent(
        local, widget.mapToGlobal(widget.rect().center()).toPointF(),
        QPoint(0, notches * 120), QPoint(0, notches * 120),
        Qt.MouseButton.NoButton, Qt.KeyboardModifier.NoModifier,
        Qt.ScrollPhase.NoScrollPhase, False)


@unittest.skipUnless(HAS_QT, "PyQt6 is not installed")
class TestThePassingWheelDoesNotEdit(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls._app = QApplication.instance() or QApplication([])
        from zbemt.gui.wheel_guard import install_wheel_guard

        cls._guard = install_wheel_guard(cls._app)

    def setUp(self):
        self.host = QWidget()
        layout = QVBoxLayout(self.host)
        self.spin = QDoubleSpinBox()
        self.spin.setRange(0.0, 100.0)
        self.spin.setValue(10.0)
        layout.addWidget(self.spin)
        self.host.show()
        # Without this the window is not active yet and `hasFocus` is
        # False for every widget in it, which would make the guard look
        # stricter than it is.
        self.host.activateWindow()
        QApplication.processEvents()

    def tearDown(self):
        self.host.hide()
        self.host.deleteLater()

    def test_an_unfocused_field_is_not_edited(self):
        self.spin.clearFocus()
        before = self.spin.value()
        QApplication.sendEvent(self.spin, _wheel(self.spin))
        self.assertEqual(self.spin.value(), before)

    def test_a_field_that_has_focus_but_was_not_clicked_is_not_edited(self):
        """The reported case. Focus arrives from a keyboard tab or from a
        programmatic `setFocus` as readily as from a click, and the old
        guard treated all three the same."""
        self.spin.setFocus(Qt.FocusReason.TabFocusReason)
        before = self.spin.value()
        QApplication.sendEvent(self.spin, _wheel(self.spin))
        self.assertEqual(
            self.spin.value(), before,
            "a field the user never clicked into was edited by the wheel")

    def test_a_field_the_user_clicked_into_still_edits(self):
        """The deliberate gesture is preserved: this is a guard, not a
        removal of wheel editing."""
        from PyQt6.QtGui import QMouseEvent

        press = QMouseEvent(
            QMouseEvent.Type.MouseButtonPress,
            QPointF(self.spin.rect().center()),
            self.spin.mapToGlobal(self.spin.rect().center()).toPointF(),
            Qt.MouseButton.LeftButton, Qt.MouseButton.LeftButton,
            Qt.KeyboardModifier.NoModifier)
        QApplication.sendEvent(self.spin, press)
        self.spin.setFocus(Qt.FocusReason.MouseFocusReason)
        before = self.spin.value()
        QApplication.sendEvent(self.spin, _wheel(self.spin))
        self.assertNotEqual(
            self.spin.value(), before,
            "clicking a field and turning the wheel must still edit it")


@unittest.skipUnless(HAS_QT, "PyQt6 is not installed")
class TestTheWheelIsNeverSwallowed(unittest.TestCase):

    def test_it_is_handed_up_the_parent_chain_without_a_scroll_area(self):
        """37 controls live in windows where no field has a scrollable
        ancestor. The guard used to drop the event there, so the wheel
        did nothing at all."""
        from zbemt.gui.wheel_guard import _hand_back_to_the_page

        received = []

        class Listener(QWidget):
            def wheelEvent(self, event):
                received.append(event.angleDelta().y())
                event.accept()

        parent = Listener()
        layout = QVBoxLayout(parent)
        spin = QDoubleSpinBox()
        layout.addWidget(spin)
        parent.show()

        _hand_back_to_the_page(spin, _wheel(spin))
        self.assertTrue(
            received,
            "the wheel was dropped instead of being handed to the page")
        parent.hide()
        parent.deleteLater()


@unittest.skipUnless(HAS_QT, "PyQt6 is not installed")
class TestNoFieldIsLeftOnWheelFocus(unittest.TestCase):
    """`WheelFocus` lets the wheel itself take focus, which is the one
    gesture that would walk straight past the click requirement."""

    @classmethod
    def setUpClass(cls):
        cls._app = QApplication.instance() or QApplication([])
        from zbemt.gui.app import MainWindow

        cls.window = MainWindow()
        cls.window.show()

    def _offenders(self, root):
        return [w for kind in SENSITIVE for w in root.findChildren(kind)
                if w.focusPolicy() == Qt.FocusPolicy.WheelFocus]

    def test_every_tab_of_the_main_window(self):
        for i in range(self.window.tabs.count()):
            tab = self.window.tabs.widget(i)
            with self.subTest(tab=self.window.tabs.tabText(i)):
                self.assertEqual(
                    [w.__class__.__name__ for w in self._offenders(tab)], [],
                    "these fields can still be focused by the wheel itself")

    def test_every_tools_window(self):
        """They were never swept at all: `adjust_focus_policy` was called
        on the main window and nowhere else."""
        from zbemt.gui.tabs.designer_window import GeometryDesignerWindow
        from zbemt.gui.tabs.optimizer_window import OptimizerWindow
        from zbemt.gui.tabs.stability_window import StabilityWindow
        from zbemt.gui.tabs.transient_window import TransientWindow

        for title, klass in (("Geometry Designer", GeometryDesignerWindow),
                              ("Design Optimization", OptimizerWindow),
                              ("Stability", StabilityWindow),
                              ("Transient", TransientWindow)):
            window = klass(self.window.state)
            window.show()
            QApplication.processEvents()
            with self.subTest(window=title):
                self.assertEqual(
                    [w.__class__.__name__ for w in self._offenders(window)],
                    [], "this Tools window was never swept")
            window.hide()


def tearDownModule():
    """Qt's teardown, not the interpreter's -- see the note in
    `tests/test_small_screen.py`."""
    if not HAS_QT:                                # pragma: no cover
        return
    app = QApplication.instance()
    if app is not None:
        app.processEvents()


if __name__ == "__main__":   # pragma: no cover
    unittest.main()
