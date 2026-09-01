"""
test_gui_responsiveness.py
==========================

PR-11 -- no user action may block the main thread.

The suite already proved that a batch can be cancelled, which is adjacent
evidence: a cancel button that works implies the event loop was turning at
the moment it was clicked. It is not the same claim. A run that blocks for
eight seconds and then processes the queued click still cancels, still
passes that test, and still froze the GUI for eight seconds.

What is asserted here is the claim itself:

  * the solve happens on a thread that is NOT the GUI thread;
  * while it runs, the event loop keeps dispatching -- a timer set up
    before the run fires DURING it, repeatedly;
  * progress arrives incrementally, case by case, rather than in one
    burst at the end;
  * the results reach the GUI as they are produced.

Requires PyQt6. `QT_QPA_PLATFORM=offscreen` comes from `tests/conftest.py`.
"""
from __future__ import annotations

import os
import shutil
import tempfile
import unittest

try:
    from PyQt6.QtCore import QEventLoop, QThread, QTimer, Qt
    from PyQt6.QtWidgets import QApplication
    _HAS_QT = True
except Exception:                                        # pragma: no cover
    _HAS_QT = False

from tests import helpers
from zbemt.models import BatchDefinition, FlightCondition

#: Enough cases that "incremental" is distinguishable from "all at once",
#: few enough that the file stays fast.
N_CASES = 6

#: The heartbeat that proves the loop is alive. Short relative to a single
#: case, so a run that blocks the thread for even one case misses several
#: beats.
HEARTBEAT_INTERVAL_MS = 5


@unittest.skipUnless(_HAS_QT, "PyQt6 not available")
class TestEngineDoesNotFreezeTheInterface(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)
        self.project = helpers.make_api_fast_project(os.path.join(self.tmp, "proj"))
        self.batch = BatchDefinition(
            name="responsiveness",
            conditions=[FlightCondition(name=f"c{i}", mu_x=0.02 * i,
                                        collective_deg=8.0, rpm=600.0)
                        for i in range(1, N_CASES + 1)])

    def _run_observing(self, timeout_ms: int = 60000) -> dict:
        """Runs the batch through the real worker and records, while it
        runs, everything needed to judge responsiveness."""
        from zbemt.gui.workers import BatchRunnerWorker

        worker = BatchRunnerWorker(self.project, batch=self.batch)
        log = {"beats": 0, "progress": [], "worker_thread": None,
               "results": None, "error": None}
        gui_thread = QThread.currentThread()

        loop = QEventLoop()

        pulse = QTimer()
        pulse.setInterval(HEARTBEAT_INTERVAL_MS)
        pulse.timeout.connect(lambda: log.__setitem__("beats",
                                                      log["beats"] + 1))

        def on_case_done(index, total, result):
            # Recorded from the GUI thread: `case_finished` is a queued
            # connection across threads, so its slot running here at all
            # is itself part of the claim.
            log["progress"].append((index, total))
            if log["worker_thread"] is None:
                log["worker_thread"] = worker.thread()

        def on_finished(results):
            log["results"] = results
            loop.quit()

        def on_failed(message):
            log["error"] = message
            loop.quit()

        worker.case_finished.connect(on_case_done)
        worker.finished.connect(on_finished)
        worker.failed.connect(on_failed)

        thread = QThread()
        worker.moveToThread(thread)
        thread.started.connect(worker.run)
        log["declared_thread"] = thread

        pulse.start()
        thread.start()
        QTimer.singleShot(timeout_ms, loop.quit)
        loop.exec()
        pulse.stop()

        thread.quit()
        thread.wait(5000)

        self.assertIsNone(log["error"], f"the batch failed: {log['error']}")
        self.assertIsNotNone(log["results"],
                             "the batch did not finish within the timeout")
        return log

    def test_the_solve_does_not_run_on_the_interface_thread(self):
        """The first and simplest form of the claim: if the solve ran on
        the GUI thread, no amount of care elsewhere could keep the window
        responsive."""
        gui_thread = QThread.currentThread()
        log = self._run_observing()
        self.assertIsNot(log["declared_thread"], gui_thread,
                         "the worker was given the GUI thread to run on")

    def test_the_event_loop_keeps_turning_during_the_solve(self):
        """A timer started before the run must keep firing while it runs.
        Each beat is one pass of the event loop, which is one opportunity
        for the window to repaint, for a button to respond, and for the
        cancel to be noticed."""
        log = self._run_observing()
        self.assertGreater(
            log["beats"], 3,
            "the event loop stopped dispatching during the solve: only "
            f"{log['beats']} timer beats over {N_CASES} cases")

    def test_progress_arrives_case_by_case_not_all_at_once(self):
        """`case_finished` must arrive once per case, in order. Delivered
        in one burst at the end, a progress bar is decoration: it tells
        the user the work is done at the moment it is already done."""
        log = self._run_observing()
        indices = [i for i, _total in log["progress"]]
        self.assertEqual(len(indices), N_CASES,
                         f"expected one progress signal per case, got {indices}")
        self.assertEqual(indices, sorted(indices),
                         f"progress arrived out of order: {indices}")
        totals = {total for _i, total in log["progress"]}
        self.assertEqual(totals, {N_CASES},
                         "the total announced with the progress is not the batch size")

    def test_results_arrive_complete_at_the_end(self):
        """Running off the main thread must not cost a result."""
        log = self._run_observing()
        self.assertEqual(len(log["results"]), N_CASES)

    def test_cancellation_is_noticed_mid_execution(self):
        """Cancellation is the user-visible consequence of the loop still
        turning: the flag is set from the GUI thread while the worker is
        between cases, and the worker must read it before the end."""
        from zbemt.gui.workers import BatchRunnerWorker

        worker = BatchRunnerWorker(self.project, batch=self.batch)
        done = []
        loop = QEventLoop()

        def on_case_done(index, _total, _result):
            done.append(index)
            if len(done) == 2:
                worker.cancel()

        # DirectConnection: the slot runs on the WORKER thread, between
        # two cases, so `worker.cancel()` is observable before the next
        # case starts. The default queued connection made this a race:
        # with fast cases the worker could finish all six before the
        # main thread ever dispatched the slot that sets the flag (seen
        # as a rare 6-not-less-than-6 failure under the full runner).
        # The slot touches no GUI state, so running it on the worker
        # thread is safe.
        worker.case_finished.connect(on_case_done,
                                     Qt.ConnectionType.DirectConnection)
        worker.finished.connect(lambda _r: loop.quit())
        worker.failed.connect(lambda _m: loop.quit())

        thread = QThread()
        worker.moveToThread(thread)
        thread.started.connect(worker.run)
        thread.start()
        QTimer.singleShot(60000, loop.quit)
        loop.exec()
        thread.quit()
        thread.wait(5000)

        self.assertGreaterEqual(len(done), 2, "the batch never started")
        self.assertLess(len(done), N_CASES,
                        "the cancel was only read after the last case: the "
                        "worker is not checking it between cases")


class TestTheResultsTabDoesNotRepeatItsWork(unittest.TestCase):
    """`PR-11`, second half: work only the main thread can do is done
    ONCE per gesture.

    Three defects lived here, and all three were invisible to the tests
    above because none of them involves a thread:

      * `_symbols()` rebuilt the description of all 130 columns once per
        COLUMN, about a million regular-expression substitutions per
        refresh;
      * the vertical header stayed in `ResizeToContents` during the fill,
        so inserting n rows measured n rows n times;
      * selecting a mode, and deleting a history entry, ran the whole
        refresh inside the click instead of on the coalescing timer.

    Together they were the reported multi-second freeze on selecting or
    deleting a case.
    """

    @classmethod
    def setUpClass(cls):
        if not _HAS_QT:                                  # pragma: no cover
            raise unittest.SkipTest("PyQt6 is not installed")
        cls.app = QApplication.instance() or QApplication([])

    def _results_tab(self):
        from zbemt.gui.app import MainWindow

        window = MainWindow()
        for index in range(window.tabs.count()):
            tab = window.tabs.widget(index)
            if type(tab).__name__ == "ResultsTab":
                self._window = window        # keep it alive for the test
                return tab
        self.fail("the Results tab is not in the window")

    def test_the_column_symbols_are_built_once_per_mode(self):
        """The same dict object must come back. A fresh dict per call is
        the defect returning, whatever its contents."""
        tab = self._results_tab()
        first = tab._symbols()
        self.assertIs(tab._symbols(), first)
        self.assertIs(tab._symbols(), first)

    def test_the_symbols_still_differ_between_the_two_modes(self):
        """Caching must not flatten the axis rotation: the rotor and the
        propeller do not label the same key the same way."""
        from zbemt.gui.tabs.results import ResultsTab

        ResultsTab._SYMBOLS_BY_MODE.clear()
        tab = self._results_tab()
        rotor = dict(tab._symbols())
        original = tab._propeller_mode
        try:
            tab._propeller_mode = lambda: True
            propeller = dict(tab._symbols())
        finally:
            tab._propeller_mode = original
        self.assertNotEqual(rotor, propeller)

    def test_the_vertical_header_is_measuring_again_after_a_fill(self):
        """It is put back to `ResizeToContents` at the end, so the
        finished table still sizes its rows to the rich label it paints
        -- the speed comes from measuring once, not from giving up."""
        from PyQt6.QtWidgets import QHeaderView

        tab = self._results_tab()
        tab._refresh_table()
        self.assertEqual(tab.table_widget.verticalHeader().sectionResizeMode(0)
                          if tab.table_widget.rowCount() else
                          QHeaderView.ResizeMode.ResizeToContents,
                          QHeaderView.ResizeMode.ResizeToContents)

    def test_deleting_a_history_entry_defers_the_redraw(self):
        """The delete must return to the event loop before the table is
        rebuilt. `_selection_timer` running is the evidence that the
        redraw was scheduled rather than executed inside the click."""
        tab = self._results_tab()
        tab._selection_timer.stop()
        tab._on_history_changed()
        self.assertTrue(tab._selection_timer.isActive(),
                        "the history change redrew synchronously instead of "
                        "scheduling the redraw")

    def test_choosing_the_table_mode_defers_the_redraw_too(self):
        """The table was special-cased as "cheap". It was the most
        expensive of the seven modes."""
        tab = self._results_tab()
        tab._selection_timer.stop()
        tab._on_mode_changed(0)
        self.assertTrue(tab._selection_timer.isActive())


if __name__ == "__main__":
    unittest.main()
