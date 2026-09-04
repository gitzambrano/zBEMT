"""Shared base for the GUI end-to-end batteries.

Drives the GUI FOR REAL through Qt: it builds the tabs, fires the slots of
real buttons and reads the state back, instead of asserting that nothing
raised.

The battery lives in two files. Sixty-two of these tests in ONE process
build about forty-five main windows, and Qt faults while tearing that pile
down -- a native abort with no traceback, landing on whichever test happens
to be running rather than on the one that filled the pile. Measured before
the split: the single file crashed six times in twelve runs, and each half
zero times in six. `tests/run_all_tests.py` gives every FILE its own
process, so splitting the file is what halves the pile.

This module is not collected: it holds no test, only the base class and the
two event-loop helpers both files need.

Requires PyQt6 -- without it both batteries skip themselves, the same
pattern as `tests/regression/test_gui_smoke.py`. `QT_QPA_PLATFORM=offscreen`
is already set by `tests/conftest.py`.

Hard rule of both files (it has bitten this repo before): NEVER let a real
`QMessageBox` appear under the offscreen backend. `exec()` never returns
without a click, and the suite freezes. Every test that reaches a code path
which can open one patches `QMessageBox` through
`helpers.patch_message_box_everywhere`.
"""


import gc
import math
import tempfile
import shutil
import time
import unittest
import unittest.mock as mock
from dataclasses import asdict

try:
    from PyQt6.QtWidgets import QApplication, QMessageBox
    from PyQt6.QtCore import QEvent, QEventLoop, QTimer, Qt
    from PyQt6.QtGui import QCloseEvent
    _HAS_QT = True
except Exception:  # pragma: no cover - environment without PyQt6
    # The names still have to EXIST. The three batteries import them from
    # here, so leaving them undefined would turn "PyQt6 is absent" into an
    # ImportError at collection -- which is exactly what the CI job that
    # runs the engine without Qt would hit, instead of skipping.
    QApplication = QMessageBox = QEvent = QEventLoop = QTimer = Qt = None
    QCloseEvent = None
    _HAS_QT = False

from zbemt import geometry as geometry_mod
from tests import helpers
from zbemt import api
from zbemt.models import Project, AirfoilDef, FlightCondition, BatchDefinition


def _pump_until_finished(worker, timeout_ms: int = 20000):
    """Pumps the main thread's event loop until ``finished``/ ``failed``
    arrives from a worker ALREADY launched (by ``launch_worker``, called
    internally by the button's real slot -- ``_run_case``/ ``_run_factorial``/
    ``_run_batch``/``_run_saved_batch``). Does NOT call ``launch_worker``
    again -- doing so would re-launch the worker in a SECOND QThread, running
    each case twice (bug found while writing this file: see note in step 6)."""
    loop = QEventLoop()
    state = {"done": False}

    def _stop(*_args):
        state["done"] = True
        loop.quit()

    worker.finished.connect(_stop)
    worker.failed.connect(_stop)
    QTimer.singleShot(timeout_ms, loop.quit)
    loop.exec()

    if not state["done"]:
        raise AssertionError("worker did not finish within the timeout")


def _run_worker_and_wait(gui, worker, timeout_ms: int = 20000):
    """Launches ``worker`` (not yet started) in a real QThread and pumps
    the event loop until it finishes -- same mechanism as
    tests/regression/test_gui_smoke.py::_run_and_wait. Only use with a worker that
    has NOT yet been launched (e.g., constructed manually in the test); for
    workers already launched by a real GUI slot, use ``_pump_until_finished``."""
    thread = gui.launch_worker(worker)
    _pump_until_finished(worker, timeout_ms=timeout_ms)
    thread.wait(2000)
    return thread


@unittest.skipUnless(_HAS_QT, "PyQt6 not installed in this environment")
class GuiE2ETestCase(unittest.TestCase):
    """Common base: session QApplication + project in a directory isolated
    from the real projects/ (we never dirty the real PROJECTS_ROOT), + patch
    of QMessageBox (no blocking modal dialog)."""

    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])
        from zbemt.gui import app as gui
        cls.gui = gui

    def setUp(self):
        self._tmpdir = tempfile.mkdtemp(prefix="zbemt_gui_e2e_")
        self.addCleanup(shutil.rmtree, self._tmpdir, ignore_errors=True)
        # S1: each GUI module has its OWN QMessageBox; a patch only in
        # `zbemt.gui.app` would not reach the tabs.
        cm = helpers.patch_message_box_everywhere("QMessageBox")
        self.mock_msgbox = cm.__enter__()
        self.addCleanup(cm.__exit__, None, None, None)
        # QMessageBox.question should return "Yes" when someone checks
        # (confirm_run_despite_issues) -- without this the value would be a
        # MagicMock, which would have to be compared explicitly with
        # StandardButton.Yes. StandardButton must be the REAL enum: the
        # production code combines buttons with `|`, which a Mock does not
        # support.
        self.mock_msgbox.StandardButton = QMessageBox.StandardButton
        self.mock_msgbox.question.return_value = QMessageBox.StandardButton.Yes
        # Every `deleteLater` scheduled by a test must be collected before
        # the next one starts. Left pending, dozens of main windows and
        # their canvases pile up inside one process, and the interpreter
        # eventually faults while Qt tears them down -- a native crash with
        # no traceback, on whichever test happens to be running.
        self.addCleanup(self._drain_deletions)
        # Registered AFTER the drain, so `addCleanup`'s LIFO order runs it
        # BEFORE it: every window is closed and every figure released
        # first, and the drain then has something to collect.
        self.addCleanup(self._release_windows_and_figures)
        # Registered LAST, so LIFO runs it FIRST, before anything is
        # deleted. The patched `QMessageBox.question` is called as
        # `question(self, ...)` from `MainWindow.closeEvent`, and a
        # `Mock` keeps every argument of every call. That call history
        # held a Python reference to each main window; `deleteLater`
        # then destroyed the C++ object underneath it and left a live
        # wrapper pointing at freed memory, which is what the interpreter
        # eventually faulted on -- a native abort with no traceback.
        self.addCleanup(self._forget_recorded_widgets)

    def _forget_recorded_widgets(self):
        """Drop the widgets the QMessageBox mock recorded as arguments."""
        self.mock_msgbox.reset_mock()

    def _drain_deletions(self):
        """Let Qt destroy every widget the test scheduled for deletion."""
        for _pass in range(3):
            self.app.processEvents()
        self.app.sendPostedEvents(None, QEvent.Type.DeferredDelete)
        self.app.processEvents()
        gc.collect()
        self.app.sendPostedEvents(None, QEvent.Type.DeferredDelete)
        self.app.processEvents()

    def _release_windows_and_figures(self):
        """Close every top-level widget and every matplotlib figure.

        A test that forgets one leaves a live window, its canvases and its
        timers inside the ONE QApplication this file shares. Sixty-two
        tests later the process faults while Qt tears the pile down -- a
        native access violation with no traceback, landing on whichever
        test happens to be running rather than on the one that leaked.
        Closing here makes the leak harmless instead of hoping every test
        remembers.

        The matplotlib figures matter as much as the windows: a canvas
        embedded in a closed window is still held by pyplot's registry,
        so its Qt object outlives the widget that owned it."""
        from PyQt6.QtCore import QTimer
        import matplotlib.pyplot as plt

        # STOP THE TIMERS FIRST. Several tabs debounce their preview
        # redraw behind a `QTimer`, and a timer left running fires into a
        # widget Qt is in the middle of destroying. That is the fault this
        # file used to end in: a native abort with no traceback, on
        # whichever test the pile happened to reach.
        for widget in list(self.app.topLevelWidgets()):
            try:
                for timer in widget.findChildren(QTimer):
                    timer.stop()
            except RuntimeError:
                continue
        plt.close("all")
        for widget in list(self.app.topLevelWidgets()):
            try:
                widget.close()
                widget.deleteLater()
            except RuntimeError:
                # Already destroyed by the test's own cleanup.
                pass

    # --- shared utilities -----------------------------------------------

    def _make_state(self):
        return self.gui.AppState()

    def _new_project(self, state, name="Heli_UH60_like"):
        """Equivalent to what ProjectTab._new_project does, but writes to
        an isolated temporary directory -- avoids using api.new_project
        directly which would be identical; we build the path manually to
        make it explicit that we do not touch the real projects/."""
        path = f"{self._tmpdir}/{name}"
        project = api.new_project(path, name=name)
        state.set_project(project)
        return project
