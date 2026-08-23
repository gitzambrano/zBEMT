"""Execution outside the GUI thread.

Every long solve (batch, factorial analysis, external polar generation)
runs here, in a ``QThread``, so the window never freezes.
"""

from __future__ import annotations

from PyQt6.QtCore import pyqtSignal, QObject, QThread

from .. import api
from ..bemt import SolveCancelled
from ..models import Project, ProfileGeometry, BatchDefinition, OptimizationOutcome



# =============================================================================
# Worker thread (docs/plano_v3.md Part 2): Run Case/Run Batch/factorial
# analysis no longer block the window. ``BatchRunnerWorker`` runs in a
# separate ``QThread`` and delegates entirely to ``api.run_batch``/
# ``api.run_factorial_batch``, which in turn pass ``on_case_done``/
# ``should_cancel`` on to ``studies.py`` (zero physics here, zero schema
# change). A single explicit list of 1 condition also covers "Run Case"
# for free (same infrastructure, see RunCaseTab._run_case).
# =============================================================================

class BatchRunnerWorker(QObject):
    # (index, total, Results | Exception) — emitted after EACH case.
    case_finished = pyqtSignal(int, int, object)
    # list of Results for the successful cases, in order, at the end.
    finished = pyqtSignal(list)
    # fatal error BEFORE running any case (for example, invalid sweep_kind,
    # malformed axis). Unrelated to an individual case failure.
    failed = pyqtSignal(str)

    def __init__(self, project: Project, *, batch: BatchDefinition | None = None,
                 factorial_axes: list[dict] | None = None, factorial_fixed: dict | None = None,
                 trim: dict | None = None):
        super().__init__()
        self.project = project
        self.batch = batch
        self.factorial_axes = factorial_axes
        self.factorial_fixed = factorial_fixed
        # Trimmed case (Step 8): {"condition", "trim_mode", "target_kind",
        # "target_value", "bracket"} — routed to `api.run_case_trimmed`
        # instead of `api.run_batch`, same thread/cancellation/progress UI
        # as usual (see RunCaseTab._run_case).
        self.trim = trim
        self.cancel_requested = False

    def cancel(self):
        self.cancel_requested = True

    def run(self):
        try:
            if self.trim is not None:
                try:
                    result = api.run_case_trimmed(
                        self.project, self.trim["condition"],
                        trim_mode=self.trim["trim_mode"], target_kind=self.trim["target_kind"],
                        target_value=self.trim["target_value"], bracket=self.trim.get("bracket"),
                        should_cancel=lambda: self.cancel_requested)
                except SolveCancelled:
                    self.finished.emit([])
                    return
                results = [result]
            elif self.batch is not None:
                results = api.run_batch(
                    self.project, self.batch,
                    on_case_done=self._emit_case, should_cancel=lambda: self.cancel_requested)
            else:
                results = api.run_factorial_batch(
                    self.project, self.factorial_axes, self.factorial_fixed,
                    on_case_done=self._emit_case, should_cancel=lambda: self.cancel_requested)
        except Exception as exc:
            self.failed.emit(str(exc))
            return
        self.finished.emit(results)

    def _emit_case(self, index: int, total: int, result_or_exc: object):
        self.case_finished.emit(index, total, result_or_exc)


class ExternalPolarWorker(QObject):
    """Runs ``api.run_external_polar_from_geometry`` (NeuralFoil) outside
    the GUI thread (C4, production-plan.md). It used to run
    synchronously in ``AirfoilTab._run_external``, freezing the window
    ("Not Responding") for minutes and freezing the GUI test suite along
    with it. Same pattern as ``BatchRunnerWorker``/``launch_worker``
    already used by RunCaseTab/RunBatchTab.

    ``external_solvers.run_polar`` exposes no internal checkpoint (it is
    a single call, not a per-case loop). There is no way to interrupt
    NeuralFoil mid-alpha. ``cancel()`` therefore does not abort the
    calculation already in progress. It only marks ``cancel_requested``
    so that the caller (``AirfoilTab``) ignores the result when
    ``finished`` arrives, instead of applying it to the UI."""
    finished = pyqtSignal(list)
    failed = pyqtSignal(str)

    def __init__(self, profile: ProfileGeometry, *, engine: str,
                 reynolds_list: list[float], mach_list: list[float],
                 alpha_min_deg: float, alpha_max_deg: float, alpha_step_deg: float,
                 diagnostics: Optional[list] = None):
        super().__init__()
        self.profile = profile
        self.engine = engine
        self.reynolds_list = reynolds_list
        self.mach_list = mach_list
        self.alpha_min_deg = alpha_min_deg
        self.alpha_max_deg = alpha_max_deg
        self.alpha_step_deg = alpha_step_deg
        # Filled BY the engine with one line per partial result (a
        # Reynolds that produced no points, dropped alphas); the tab
        # reads it when `finished` arrives and tells the user what the
        # sweep actually produced.
        self.diagnostics = diagnostics if diagnostics is not None else []
        self.cancel_requested = False

    def cancel(self):
        self.cancel_requested = True

    def run(self):
        try:
            slices = api.run_external_polar_from_geometry(
                self.profile, engine=self.engine,
                reynolds_list=self.reynolds_list, mach_list=self.mach_list,
                alpha_min_deg=self.alpha_min_deg, alpha_max_deg=self.alpha_max_deg,
                alpha_step_deg=self.alpha_step_deg,
                diagnostics=self.diagnostics,
            )
        except Exception as exc:
            self.failed.emit(str(exc))
            return
        self.finished.emit(slices)


class CompareWorker(QObject):
    """Runs ``api.compare_geometries`` outside the GUI thread.

    Same pattern as ``BatchRunnerWorker``: the variants dict maps a
    display label to a ``RotorGeometryDef``, every variant runs the same
    ordered conditions on a ``QThread``, and the window keeps responding.
    ``progress`` carries ``(cases done, total cases)`` so the caller can
    show a determinate bar. ``cancel()`` asks for an interruption between
    cases; the flag reaches the engine through the ``should_cancel``
    closure. When the engine reports the cancellation,
    ``finished`` arrives with an empty list. ``trim`` ("none"/"thrust"/
    "CT") holds the loading constant across variants; the FIRST variant
    is the reference every other one is trimmed to."""
    finished = pyqtSignal(list)
    failed = pyqtSignal(str)
    # (cases done, total cases) -- emitted after EACH case.
    progress = pyqtSignal(int, int)

    def __init__(self, project: Project, variants: dict,
                 conditions=None, *, trim: str = "none"):
        super().__init__()
        self.project = project
        self.variants = variants
        self.conditions = list(conditions) if conditions is not None else None
        self.trim = trim
        self.cancel_requested = False

    def cancel(self):
        self.cancel_requested = True

    def run(self):
        try:
            results = api.compare_geometries(
                self.project, self.variants, self.conditions,
                trim=self.trim,
                on_case_done=lambda done, total, _res: self.progress.emit(done, total),
                should_cancel=lambda: self.cancel_requested)
        except SolveCancelled:
            self.finished.emit([])
            return
        except Exception as exc:
            self.failed.emit(str(exc))
            return
        self.finished.emit(results)


class OptimizeWorker(QObject):
    """Runs ``api.optimize_design`` outside the GUI thread.

    Same pattern as ``CompareWorker``. ``progress`` carries
    ``(evaluations done, max evaluations, best value so far)``, emitted
    after each evaluation, so the caller updates its bar and its
    convergence plot while the search runs. ``cancel()`` sets the flag
    that the ``should_cancel`` closure reads; ``studies.optimize_design``
    turns it into a normal outcome with ``message == "cancelled"``, which
    still arrives through ``finished``."""
    finished = pyqtSignal(object)
    failed = pyqtSignal(str)
    # (evals done, max evals, best value so far) -- after EACH evaluation.
    progress = pyqtSignal(int, int, float)

    def __init__(self, project: Project, definition):
        super().__init__()
        self.project = project
        self.definition = definition
        self.cancel_requested = False

    def cancel(self):
        self.cancel_requested = True

    def run(self):
        try:
            outcome = api.optimize_design(
                self.project, self.definition,
                on_progress=lambda done, total, best: self.progress.emit(done, total, best),
                should_cancel=lambda: self.cancel_requested)
        except SolveCancelled:
            outcome = OptimizationOutcome(
                objective_key=self.definition.objective_key,
                objective_kind=self.definition.objective_kind,
                message="cancelled")
        except Exception as exc:
            self.failed.emit(str(exc))
            return
        self.finished.emit(outcome)


class ReportWorker(QObject):
    """Generates the report outside the application's main thread."""

    finished = pyqtSignal(str)
    failed = pyqtSignal(str)

    def __init__(self, results, path: str, *, project=None, plots=None, dpi: int = 150):
        super().__init__()
        self.results = results
        self.path = path
        self.project = project
        self.plots = plots
        self.dpi = dpi

    def run(self):
        try:
            dest = api.generate_report(
                self.results, self.path, project=self.project,
                plots=self.plots, dpi=self.dpi)
        except Exception as exc:
            self.failed.emit(str(exc))
            return
        self.finished.emit(str(dest))


def launch_worker(worker: BatchRunnerWorker) -> QThread:
    """Moves ``worker`` to a new ``QThread``, connects completion
    (``finished``/``failed``) to stop/clean up the thread, and starts it.
    The caller MUST keep a reference to both (``self._thread``/
    ``self._worker``) while they run, or Python collects and tears down
    everything.

    Launching the SAME worker twice is an error and raises here. Without
    this guard, the second call created a second ``QThread`` over the
    same object and the whole batch ran TWICE -- each case emitting
    ``case_finished`` twice, double the execution time, and duplicated
    results in the table. Nothing gave it away. It was just "the batch
    took a while". Found while writing the GUI's end-to-end test
    battery."""
    if getattr(worker, "_launched", False):
        raise RuntimeError(
            f"{type(worker).__name__} was already launched on a QThread. "
            "Launching it again would silently run the whole job in "
            "duplicate. Create a new worker for each run.")
    worker._launched = True

    thread = QThread()
    worker.moveToThread(thread)
    thread.started.connect(worker.run)

    def _cleanup(*_args):
        thread.quit()

    worker.finished.connect(_cleanup)
    worker.failed.connect(_cleanup)
    thread.start()
    return thread


