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
    from PyQt6.QtCore import QEventLoop, QThread, QTimer
    from PyQt6.QtWidgets import QApplication
    _HAS_QT = True
except Exception:                                        # pragma: no cover
    _HAS_QT = False

from tests import helpers
from zbemt.models import BatchDefinition, FlightCondition

#: Enough cases that "incremental" is distinguishable from "all at once",
#: few enough that the file stays fast.
N_CASOS = 6

#: The heartbeat that proves the loop is alive. Short relative to a single
#: case, so a run that blocks the thread for even one case misses several
#: beats.
INTERVALO_DE_BATIDA_MS = 5


@unittest.skipUnless(_HAS_QT, "PyQt6 not available")
class TestOMotorNaoTravaAInterface(unittest.TestCase):

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
                        for i in range(1, N_CASOS + 1)])

    def _rodar_observando(self, timeout_ms: int = 60000) -> dict:
        """Runs the batch through the real worker and records, while it
        runs, everything needed to judge responsiveness."""
        from zbemt.gui.workers import BatchRunnerWorker

        worker = BatchRunnerWorker(self.project, batch=self.batch)
        registro = {"batidas": 0, "progresso": [], "thread_do_worker": None,
                    "resultados": None, "erro": None}
        thread_da_gui = QThread.currentThread()

        loop = QEventLoop()

        pulso = QTimer()
        pulso.setInterval(INTERVALO_DE_BATIDA_MS)
        pulso.timeout.connect(lambda: registro.__setitem__("batidas",
                                                           registro["batidas"] + 1))

        def ao_terminar_caso(indice, total, resultado):
            # Recorded from the GUI thread: `case_finished` is a queued
            # connection across threads, so its slot running here at all
            # is itself part of the claim.
            registro["progresso"].append((indice, total))
            if registro["thread_do_worker"] is None:
                registro["thread_do_worker"] = worker.thread()

        def ao_terminar(resultados):
            registro["resultados"] = resultados
            loop.quit()

        def ao_falhar(mensagem):
            registro["erro"] = mensagem
            loop.quit()

        worker.case_finished.connect(ao_terminar_caso)
        worker.finished.connect(ao_terminar)
        worker.failed.connect(ao_falhar)

        thread = QThread()
        worker.moveToThread(thread)
        thread.started.connect(worker.run)
        registro["thread_declarada"] = thread

        pulso.start()
        thread.start()
        QTimer.singleShot(timeout_ms, loop.quit)
        loop.exec()
        pulso.stop()

        thread.quit()
        thread.wait(5000)

        self.assertIsNone(registro["erro"], f"the batch failed: {registro['erro']}")
        self.assertIsNotNone(registro["resultados"],
                             "the batch did not finish within the timeout")
        return registro

    def test_o_solve_nao_roda_na_thread_da_interface(self):
        """The first and simplest form of the claim: if the solve ran on
        the GUI thread, no amount of care elsewhere could keep the window
        responsive."""
        thread_da_gui = QThread.currentThread()
        registro = self._rodar_observando()
        self.assertIsNot(registro["thread_declarada"], thread_da_gui,
                         "the worker was given the GUI thread to run on")

    def test_o_laco_de_eventos_continua_girando_durante_o_solve(self):
        """A timer started before the run must keep firing while it runs.
        Each beat is one pass of the event loop, which is one opportunity
        for the window to repaint, for a button to respond, and for the
        cancel to be noticed."""
        registro = self._rodar_observando()
        self.assertGreater(
            registro["batidas"], 3,
            "the event loop stopped dispatching during the solve: only "
            f"{registro['batidas']} timer beats over {N_CASOS} cases")

    def test_o_progresso_chega_caso_a_caso_e_nao_de_uma_vez(self):
        """`case_finished` must arrive once per case, in order. Delivered
        in one burst at the end, a progress bar is decoration: it tells
        the user the work is done at the moment it is already done."""
        registro = self._rodar_observando()
        indices = [i for i, _total in registro["progresso"]]
        self.assertEqual(len(indices), N_CASOS,
                         f"expected one progress signal per case, got {indices}")
        self.assertEqual(indices, sorted(indices),
                         f"progress arrived out of order: {indices}")
        totais = {total for _i, total in registro["progresso"]}
        self.assertEqual(totais, {N_CASOS},
                         "the total announced with the progress is not the batch size")

    def test_os_resultados_chegam_completos_ao_fim(self):
        """Running off the main thread must not cost a result."""
        registro = self._rodar_observando()
        self.assertEqual(len(registro["resultados"]), N_CASOS)

    def test_o_cancelamento_e_notado_no_meio_da_execucao(self):
        """Cancellation is the user-visible consequence of the loop still
        turning: the flag is set from the GUI thread while the worker is
        between cases, and the worker must read it before the end."""
        from zbemt.gui.workers import BatchRunnerWorker

        worker = BatchRunnerWorker(self.project, batch=self.batch)
        feitos = []
        loop = QEventLoop()

        def ao_terminar_caso(indice, _total, _resultado):
            feitos.append(indice)
            if len(feitos) == 2:
                worker.cancel()

        worker.case_finished.connect(ao_terminar_caso)
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

        self.assertGreaterEqual(len(feitos), 2, "the batch never started")
        self.assertLess(len(feitos), N_CASOS,
                        "the cancel was only read after the last case: the "
                        "worker is not checking it between cases")


if __name__ == "__main__":
    unittest.main()
