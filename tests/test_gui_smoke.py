"""
test_gui_smoke.py
==================

Headless smoke tests (via Xvfb) for docs/plano_v3.md Part 2 -- worker
thread. Does not test the whole GUI (no other Part does that, see
tests/README.md "What is NOT covered"): only this Part's new mechanism,
``gui.BatchRunnerWorker`` + ``gui.launch_worker``, which is what
``RunCaseTab``/``RunBatchTab`` now use instead of calling
``api.run_batch``/``api.run_factorial_batch`` directly on the GUI thread.

Requires PyQt6 installed and a display (real or Xvfb via ``xvfb-run``).
If PyQt6 is not available, the whole suite is skipped (same spirit as
test_visualization.py with PyVista absent) -- it does not break for
whoever runs the tests in an environment without PyQt6 (see
tests/README.md).
"""

import os
import sys
import time
import unittest
from pathlib import Path

from tests import helpers
import unittest.mock


try:
    from PyQt6.QtWidgets import QApplication
    from PyQt6.QtCore import QEventLoop, QTimer, Qt
    _HAS_QT = True
except Exception:  # pragma: no cover - environment without PyQt6
    _HAS_QT = False

from zbemt import geometry
from zbemt.models import Project, AirfoilDef, FlightCondition, BatchDefinition


def _make_project() -> Project:
    geom = geometry.generate_tapered(root_chord_norm=0.10, tip_chord_norm=0.04,
                                      twist_root_deg=14.0, twist_tip_deg=2.0,
                                      root_cutout_norm=0.15, radius_m=1.0, n_stations=10)
    airfoil = AirfoilDef(source="analytical", stall_model="clip",
                          alpha_stall_pos_deg=15.0, alpha_stall_neg_deg=-6.0)
    cfg = dict(Ne=6, Npsi=8, solver="fixed_point", max_iter=80)
    return Project(name="teste_worker", geometry=geom, airfoil=airfoil, config=cfg)


@unittest.skipUnless(_HAS_QT, "PyQt6 not installed in this environment")
class TestBatchRunnerWorker(unittest.TestCase):
    """Tests gui.BatchRunnerWorker in isolation (without mounting the
    whole GUI's tabs) -- it is the object that actually runs on a
    separate QThread and emits the incremental progress that
    RunBatchTab/RunCaseTab consume."""

    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])
        # late import: only after ensuring QApplication (matplotlib.use("QtAgg"))
        from zbemt.gui import app as gui
        cls.gui = gui

    def _run_and_wait(self, worker, timeout_ms: int = 15000):
        """Runs ``worker`` and pumps the main thread's event loop until
        ``finished``/``failed`` arrives (or until the timeout). Necessary
        because signal delivery between threads in PyQt6 is queued on the
        main thread -- blocking with ``QThread.wait()`` without processing
        events would leave the cleanup (``quit()``) undelivered, and
        ``wait()`` would time out waiting for the thread to end on its
        own (which never happens without the ``quit()``)."""
        thread = self.gui.launch_worker(worker)
        loop = QEventLoop()
        state = {"done": False}

        def _stop(*_args):
            state["done"] = True
            loop.quit()

        worker.finished.connect(_stop)
        worker.failed.connect(_stop)
        QTimer.singleShot(timeout_ms, loop.quit)
        loop.exec()

        self.assertTrue(state["done"], "worker did not finish within the timeout")
        thread.wait(2000)   # should have terminated (quit() fired in cleanup)
        return thread

    def test_progress_bar_advances_one_case_at_a_time_in_order(self):
        project = _make_project()
        conditions = [FlightCondition(name=f"c{i}", mu_x=0.05 * i, collective_deg=8.0, rpm=600.0)
                      for i in range(4)]
        batch = BatchDefinition(conditions=conditions)
        worker = self.gui.BatchRunnerWorker(project, batch=batch)

        seen = []
        finished_results = []
        worker.case_finished.connect(lambda i, total, r: seen.append((i, total)))
        worker.finished.connect(lambda results: finished_results.append(results))

        self._run_and_wait(worker)

        self.assertEqual(seen, [(i, 4) for i in range(4)])
        self.assertEqual(len(finished_results), 1)
        self.assertEqual(len(finished_results[0]), 4)

    def test_cancel_button_interrupts_before_all_cases_run(self):
        """C8.2 (production-plan.md): the real semantics is "cancels BETWEEN
        cases" -- ``studies._run_conditions`` only checks
        ``should_cancel()`` before running the next case, never during
        a case's resolution. ``worker.case_finished`` is emitted in
        the worker thread but connected from the main thread, and
        signal delivery to a "loose" callable (not bound to a
        QObject) ends up queued in the main thread -- that is, the
        ``worker.cancel()`` fired inside ``on_case`` only takes effect
        when the main event loop processes the queue.
        With the real solver (blazing fast at Ne=6/Npsi=8) the next
        batch case sometimes already started and finished before that
        delivery, causing the test to fail by race ~1 in 3 times.

        Fixed by making the test deterministic: ``studies.run_single_case``
        is mocked to be slow and countable, giving enough slack for
        the main event loop to always process the cancellation before
        the next case starts. This does not change the solver's semantics
        (still "cancels between cases") -- only removes the test's race
        dependency.

        The time slack, however, was still a BET: running after heavy GUI
        files, the queued delivery passed the 0.1s `sleep` and all six
        cases ran -- the test failed by execution order, not by defect.
        The signal connection is `DirectConnection` here: `on_case` runs
        in the worker thread, at the instant the case ends, so the
        cancellation is set BEFORE the next case starts, without depending
        on any clock. It still honors the same contract we want to test
        ("cancels BETWEEN cases"), and now without races."""
        project = _make_project()
        conditions = [FlightCondition(name=f"c{i}", mu_x=0.0, collective_deg=8.0, rpm=600.0)
                      for i in range(6)]
        batch = BatchDefinition(conditions=conditions)
        worker = self.gui.BatchRunnerWorker(project, batch=batch)

        from zbemt.models import Results
        call_count = {"n": 0}

        def slow_run_single_case(proj, cond, should_cancel=None):
            call_count["n"] += 1
            time.sleep(0.1)   # slack >> signal delivery latency in the event loop queue
            return Results(summary={"mu_x": cond.mu_x}, maps={}, condition_name=cond.name)

        seen = []
        finished_results = []

        def on_case(i, total, r):
            seen.append(i)
            if i == 1:   # simula clique em "Cancelar" no meio do batch
                worker.cancel()

        worker.case_finished.connect(on_case, Qt.ConnectionType.DirectConnection)
        worker.finished.connect(lambda results: finished_results.append(results))

        with unittest.mock.patch("zbemt.studies.run_single_case", side_effect=slow_run_single_case):
            self._run_and_wait(worker)

        self.assertEqual(call_count["n"], len(seen), "cada caso rodado deve ter emitido case_finished")
        self.assertLess(len(seen), 6, "cancelamento deveria ter interrompido antes do fim")
        self.assertEqual(len(finished_results), 1)
        self.assertEqual(len(finished_results[0]), len(seen))

    def test_factorial_worker_reports_correct_total(self):
        project = _make_project()
        axes = [{"variable": "mu_x", "values": [0.0, 0.1, 0.2]}]
        worker = self.gui.BatchRunnerWorker(project, factorial_axes=axes, factorial_fixed={"rpm": 600})

        totals_seen = set()
        finished_results = []
        worker.case_finished.connect(lambda i, total, r: totals_seen.add(total))
        worker.finished.connect(lambda results: finished_results.append(results))

        self._run_and_wait(worker)

        self.assertEqual(totals_seen, {3})
        self.assertEqual(len(finished_results[0]), 3)


@unittest.skipUnless(_HAS_QT, "PyQt6 not installed in this environment")
class TestResultsHistory(unittest.TestCase):
    """docs/plano_v3.md Part 4.1 -- `AppState.results_history` grows via
    `append` (never overwrites) and `ResultsTab` reflects it in the
    history list with multiple selection via checkboxes."""

    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])
        from zbemt.gui import app as gui
        cls.gui = gui

    def test_add_history_entry_appends_and_emits_signal(self):
        state = self.gui.AppState()
        seen = []
        state.history_changed.connect(lambda: seen.append(1))

        from zbemt.models import Results
        r1 = Results(summary={"mu_x": 0.0}, maps={}, condition_name="c1")
        r2 = Results(summary={"mu_x": 0.1}, maps={}, condition_name="c2")

        e1 = state.add_history_entry(kind="case", label="caso 1", results=r1)
        e2 = state.add_history_entry(kind="case", label="caso 2", results=r2)

        self.assertEqual(len(state.results_history), 2)
        self.assertEqual(len(seen), 2)
        self.assertNotEqual(e1.id, e2.id)
        self.assertIs(state.results_history[0].results, r1)
        self.assertIs(state.results_history[1].results, r2)

    def test_clear_history_resets_list_and_counter(self):
        state = self.gui.AppState()
        from zbemt.models import Results
        state.add_history_entry(kind="case", label="c", results=Results(summary={}, maps={}))
        state.clear_history()
        self.assertEqual(state.results_history, [])

    def test_set_project_clears_history(self):
        state = self.gui.AppState()
        from zbemt.models import Results
        state.add_history_entry(kind="case", label="c", results=Results(summary={}, maps={}))
        self.assertEqual(len(state.results_history), 1)
        state.set_project(_make_project())
        self.assertEqual(len(state.results_history), 0)

    def test_results_tab_reflects_history_and_selection_gates_modes(self):
        state = self.gui.AppState()
        state.set_project(_make_project())
        geometry_tab = self.gui.GeometryTab(state)
        airfoil_tab = self.gui.AirfoilTab(state)
        tab = self.gui.ResultsTab(state, geometry_tab, airfoil_tab)

        from zbemt.models import Results
        r_case = Results(summary={"mu_x": 0.0, "CT": 0.01}, maps={"Fn": [[0.0]]}, condition_name="c1")
        r_batch = [Results(summary={"mu_x": 0.1, "CT": 0.02}, maps={}, condition_name="b1"),
                   Results(summary={"mu_x": 0.2, "CT": 0.03}, maps={}, condition_name="b2")]

        state.add_history_entry(kind="case", label="caso A", results=r_case)
        self.assertEqual(tab.history_list.count(), 1)
        # new entry arrives already checked (Part 4.1 -- "see right away" the
        # newly calculated result without having to check it manually).
        from PyQt6.QtCore import Qt as _Qt
        self.assertEqual(tab.history_list.item(0).checkState(), _Qt.CheckState.Checked)

        state.add_history_entry(kind="batch", label="batch B", results=r_batch)
        self.assertEqual(tab.history_list.count(), 2)

        # Only the newest entry (batch B) is checked by default;
        # with 1 selected, single-result modes are enabled.
        tab._clear_history_selection()
        tab.history_list.item(1).setCheckState(_Qt.CheckState.Checked)
        self.assertEqual(len(tab._selected_entries()), 1)
        for i in range(tab.mode_list.count()):
            item = tab.mode_list.item(i)
            if item.text() in tab._SINGLE_RESULT_MODES:
                self.assertTrue(bool(item.flags() & _Qt.ItemFlag.ItemIsEnabled))

        # Select both entries: NO mode is disabled.
        #
        # Before, checking more than one result disabled disk/azimuth/3D/
        # convergence due to "ambiguous selection", and a user who checked
        # six cases from Run Case simply could not plot anything -- it was
        # the owner's complaint. Ambiguity is now resolved via a
        # condition dropdown, not by forbidding selection: single-condition
        # modes draw the chosen condition there, and the coefficients mode
        # keeps using all of them.
        tab._select_all_history()
        self.assertEqual(len(tab._selected_entries()), 2)
        for i in range(tab.mode_list.count()):
            item = tab.mode_list.item(i)
            self.assertTrue(
                bool(item.flags() & _Qt.ItemFlag.ItemIsEnabled),
                f"mode '{item.text()}' disabled with 2 results checked")
        # And the condition selector now offers both conditions from the
        # batch plus the standalone case.
        self.assertGreaterEqual(tab.condition_combo.count(), 2)

    def test_flatten_selection_matches_plots_module(self):
        from zbemt.viz import plots as plots_module
        state = self.gui.AppState()
        from zbemt.models import Results
        r1 = Results(summary={"mu_x": 0.0}, maps={}, condition_name="c1")
        batch = [Results(summary={"mu_x": 0.1}, maps={}, condition_name="b1"),
                 Results(summary={"mu_x": 0.2}, maps={}, condition_name="b2")]
        state.add_history_entry(kind="case", label="c", results=r1)
        state.add_history_entry(kind="batch", label="b", results=batch)
        flat = plots_module.flatten_selection(state.results_history)
        self.assertEqual(flat, [r1] + batch)


@unittest.skipUnless(_HAS_QT, "PyQt6 not installed in this environment")
class TestResultsDiskZoomAndColorScale(unittest.TestCase):
    """Zoom/axis scale on all Results tab plots (matplotlib toolbar) +
    COLOR scale of the disk map (linear/log, manual min/max) -- the
    toolbar does not edit a tricontourf's color bar, so this control
    is explicit (docs/plano_v3.md Part 8)."""

    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])
        from zbemt.gui import app as gui
        cls.gui = gui

    def _make_disk_result(self):
        import numpy as np
        from zbemt.models import Results
        Ne, Npsi = 6, 8
        r = np.linspace(0.2, 1.0, Ne)
        psi = np.linspace(0, 2 * np.pi * (1 - 1 / Npsi), Npsi)
        R_NORM, PSI = np.meshgrid(r, psi, indexing="ij")
        lambda_i = 0.05 + 0.02 * np.sin(PSI) * R_NORM
        ones = np.ones_like(R_NORM)
        maps = dict(R_NORM=R_NORM, PSI=PSI, lambda_i=lambda_i, Ut=ones * 5.0,
                    Fn=ones * 1.0, Ft=ones * 0.1, Cl=ones * 0.5, Cd=ones * 0.02,
                    Up=ones * 0.5, W=ones * 5.0, alpha_eff=ones * 0.05, phi=ones * 0.02,
                    lambda_total=ones * 0.06)
        return Results(summary={"mu_x": 0.2}, maps=maps, condition_name="c1")

    def _make_tab_with_result(self):
        state = self.gui.AppState()
        state.set_project(_make_project())
        geometry_tab = self.gui.GeometryTab(state)
        airfoil_tab = self.gui.AirfoilTab(state)
        tab = self.gui.ResultsTab(state, geometry_tab, airfoil_tab)
        state.add_history_entry(kind="case", label="c1", results=self._make_disk_result())
        return tab

    def test_results_canvas_has_zoom_toolbar(self):
        tab = self._make_tab_with_result()
        self.assertIsNotNone(tab.canvas_host._toolbar)

    def test_toolbar_stays_bound_to_currently_shown_canvas(self):
        """`show_figure` (grid) switches canvas instances -- the
        toolbar must follow, not stay stuck to the old canvas."""
        tab = self._make_tab_with_result()
        tab.disk_field_combo.setCurrentText("lambda_i")
        tab._refresh_disk()
        self.assertIs(tab.canvas_host._toolbar.canvas, tab.canvas_host._current)

        tab.disk_field_combo.setCurrentText("(grid with all fields)")
        tab._refresh_disk()
        self.assertIs(tab.canvas_host._toolbar.canvas, tab.canvas_host._current)

    def test_color_scale_controls_disabled_for_grid_enabled_for_single_field(self):
        tab = self._make_tab_with_result()
        tab.disk_field_combo.setCurrentText("lambda_i")
        self.assertTrue(tab.disk_color_scale_combo.isEnabled())
        tab.disk_field_combo.setCurrentText("(grid with all fields)")
        self.assertFalse(tab.disk_color_scale_combo.isEnabled())

    def test_log_color_scale_and_manual_bounds_draw_without_error(self):
        tab = self._make_tab_with_result()
        tab.disk_field_combo.setCurrentText("lambda_i")
        tab.disk_color_scale_combo.setCurrentText("log")
        tab._refresh_disk()   # must not raise an exception
        tab.disk_color_scale_combo.setCurrentText("linear")
        tab.disk_color_vmin_edit.setText("0.03")
        tab.disk_color_vmax_edit.setText("0.09")
        tab._refresh_disk()   # must not raise an exception


@unittest.skipUnless(_HAS_QT, "PyQt6 not installed in this environment")
class TestAirfoilPreviewCanvas(unittest.TestCase):
    """Smoke tests of the Airfoil tab's embedded canvas (docs/plano_v3.md
    Part 5): live preview, Polar/Profile switching, multi-axis navigation
    (r/R, Reynolds, Mach), and absence of "Airfoil" mode from
    ResultsTab (migrated here)."""

    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])
        from zbemt.gui import app as gui
        cls.gui = gui

    def test_results_tab_no_longer_has_airfoil_mode(self):
        from zbemt.models import AirfoilDef as _AirfoilDef
        state = self.gui.AppState()
        state.set_project(_make_project())
        geometry_tab = self.gui.GeometryTab(state)
        airfoil_tab = self.gui.AirfoilTab(state)
        tab = self.gui.ResultsTab(state, geometry_tab, airfoil_tab)
        mode_names = [tab.mode_list.item(i).text() for i in range(tab.mode_list.count())]
        self.assertNotIn("Airfoil", mode_names)

    def test_abrir_projeto_redesenha_o_preview_da_polar(self):
        """Real bug, seen on screen: opening a project repopulated the form
        but left the PREVIOUS airfoil's curve in the canvas.

        `_refresh_from_project` sets `_loading`, which silences field-change
        signals while the form is being filled -- and it is precisely those
        signals that would schedule the redraw. The result was the form
        saying "viterna / full range" while the graph next to it still said
        "linear / measured range only": another airfoil's polar, with no
        indication it was different.
        """
        from zbemt.models import AirfoilDef as _AirfoilDef

        state = self.gui.AppState()
        tab = self.gui.AirfoilTab(state)

        projeto = _make_project()
        projeto.airfoil = _AirfoilDef(name="linear one", source="analytical",
                                      stall_model="linear", extend_full_range=False)
        state.set_project(projeto)
        initial_title = tab.cl_alpha_canvas.use_simple().ax.get_title()
        self.assertIn("linear", initial_title)

        outro = _make_project()
        outro.airfoil = _AirfoilDef(name="viterna one", source="analytical",
                                    stall_model="viterna", extend_full_range=True)
        state.set_project(outro)

        title = tab.cl_alpha_canvas.use_simple().ax.get_title()
        self.assertIn("viterna", title,
                      "the preview kept showing the previous airfoil")
        self.assertIn("full range", title)

    def test_coincident_curves_become_one_legend_entry(self):
        """Real bug, seen on screen: the Cl×α preview legend listed six
        entries with four curves drawn.

        Three of the six labels named the SAME line: with
        `reverse_flow_model="viterna_full_range"` the reverse branch is
        the extended polar itself (there is no separate reverse treatment),
        and the comparison curve at M=0 is the compressibility-uncorrected
        polar -- again the main one. The three strokes sat stacked at the
        same thickness, and the legend promised curves the reader searched
        for in the plot and could not find.
        """
        from zbemt.gui.tabs.airfoil import _unir_curvas_coincidentes

        a = [-5.0, 0.0, 5.0]
        base = dict(alpha_deg=a, cl=[-0.5, 0.0, 0.5], cd=[0.02, 0.01, 0.02])
        other = dict(alpha_deg=a, cl=[-0.6, 0.0, 0.6], cd=[0.02, 0.01, 0.02])
        curves = [dict(base, label="SC1095"),
                  dict(base, label="reverse flow (viterna_full_range)"),
                  dict(base, label="M=0.00"),
                  dict(other, label="M=0.30 (P-G)")]

        merged = _unir_curvas_coincidentes(curves)

        self.assertEqual(len(merged), 2,
                         "one legend entry per actually drawn line")
        self.assertEqual(
            merged[0]["label"],
            "SC1095 = reverse flow (viterna_full_range) = M=0.00",
            "the merged label must say WHICH conditions fall on the curve")
        self.assertEqual(merged[1]["label"], "M=0.30 (P-G)")

    def test_navigator_appears_only_for_axes_with_2plus_values(self):
        from zbemt.models import PolarSlice
        state = self.gui.AppState()
        tab = self.gui.AirfoilTab(state)

        # table with r/R x Reynolds (2 values each) and fixed Mach -- must
        # generate exactly 2 navigation controls (not 3).
        slices = []
        for r in (0.3, 0.7):
            for re in (1e5, 1e6):
                slices.append(PolarSlice(alpha_deg=[-5, 0, 5], cl=[0.0, 0.5, 1.0],
                                          cd=[0.02, 0.015, 0.02], r_norm=r, reynolds=re, mach=0.2))
        tab._imported_slices = slices
        tab.source_combo.setCurrentText("table")
        tab._populate_slices_list()
        tab._refresh_preview()

        self.assertEqual(set(tab._nav_widgets.keys()), {"r_norm", "reynolds"})
        self.assertNotIn("mach", tab._nav_widgets)

    def test_switching_polar_to_perfil_keeps_navigator_selection(self):
        from zbemt.models import PolarSlice
        state = self.gui.AppState()
        tab = self.gui.AirfoilTab(state)
        slices = [PolarSlice(alpha_deg=[0], cl=[0.1], cd=[0.01], r_norm=r) for r in (0.2, 0.5, 0.8)]
        tab._imported_slices = slices
        tab.source_combo.setCurrentText("table")
        tab._populate_slices_list()
        tab._refresh_preview()

        combo = tab._nav_widgets["r_norm"]
        combo.setCurrentIndex(2)   # r/R = 0.8
        self.assertEqual(tab._nav_selection["r_norm"], 0.8)

        tab.preview_tabs.setCurrentIndex(3)   # "Profile" tab (4th mini-tab, after Cl x alpha/Cd x alpha/Cd x Cl)
        tab._refresh_preview()
        self.assertEqual(tab._nav_selection["r_norm"], 0.8)   # state preserved

        tab.preview_tabs.setCurrentIndex(0)   # back to "Cl x alpha"
        tab._refresh_preview()
        self.assertEqual(tab._nav_selection["r_norm"], 0.8)

    def test_preview_has_four_mini_tabs_in_order(self):
        """docs/plano_v3.md Part 7, items 4/5: Cl x alpha, Cd x alpha,
        Cd x Cl (separate plots, with zoom) + Profile (2D geometry) as
        the 4th tab, in that order."""
        state = self.gui.AppState()
        tab = self.gui.AirfoilTab(state)
        names = [tab.preview_tabs.tabText(i) for i in range(tab.preview_tabs.count())]
        # `PR-4`: these used to be "C_L x α", with the subscript typed
        # as an UNDERSCORE, and this assertion pinned that. A QTabWidget
        # paints plain text, so `nomenclature` supplies the fallback it
        # uses everywhere else for a symbol Unicode cannot subscript.
        self.assertEqual(names, ["CL \u00d7 \u03b1", "CD \u00d7 \u03b1",
                                  "CD \u00d7 CL", "Profile"])

    def test_preview_canvases_have_zoom_toolbar(self):
        """Item 4: zoom (rectangle/wheel) and axis scale/limit editing
        -- via NavigationToolbar2QT embedded in each mini-tab."""
        state = self.gui.AppState()
        tab = self.gui.AirfoilTab(state)
        for host in (tab.cl_alpha_canvas, tab.cd_alpha_canvas, tab.cd_cl_canvas, tab.profile_canvas):
            self.assertIsNotNone(host._toolbar)

    def test_editing_form_field_schedules_debounced_preview_refresh(self):
        state = self.gui.AppState()
        tab = self.gui.AirfoilTab(state)
        self.assertTrue(tab._preview_timer.isSingleShot())
        self.assertEqual(tab._preview_timer.interval(), 300)
        tab.cd0.setValue(tab.cd0.value() + 0.001)
        self.assertTrue(tab._preview_timer.isActive())


@unittest.skipUnless(_HAS_QT, "PyQt6 not installed in this environment")
class TestGeometryPreviewCanvas(unittest.TestCase):
    """docs/plano_v3.md Part 6.1 -- embedded "Top View"/"Chord-Twist" canvas
    in the Geometry tab, live with debounce, no need for "Apply" to
    reflect the current table edit."""

    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])
        from zbemt.gui import app as gui
        cls.gui = gui

    def _make_project(self):
        geom = geometry.generate_tapered(root_chord_norm=0.10, tip_chord_norm=0.04,
                                          twist_root_deg=14.0, twist_tip_deg=2.0,
                                          root_cutout_norm=0.15, radius_m=1.0, n_stations=8)
        airfoil = AirfoilDef(source="analytical", stall_model="clip",
                              alpha_stall_pos_deg=15.0, alpha_stall_neg_deg=-6.0)
        return Project(name="teste_geom_canvas", geometry=geom, airfoil=airfoil,
                        config=dict(Ne=6, Npsi=8, solver="fixed_point", max_iter=80))

    def test_editing_table_cell_schedules_debounced_preview_refresh_and_marks_dirty(self):
        state = self.gui.AppState()
        state.set_project(self._make_project())
        tab = self.gui.GeometryTab(state)
        tab._refresh_from_project()
        self.assertFalse(tab._dirty)
        self.assertTrue(tab._preview_timer.isSingleShot())
        self.assertEqual(tab._preview_timer.interval(), 300)

        tab.table.item(0, 1).setText("0.2000")
        self.assertTrue(tab._preview_timer.isActive())
        self.assertTrue(tab._dirty)

    def test_apply_table_edits_applies_live_and_updates_planform_canvas(self):
        state = self.gui.AppState()
        state.set_project(self._make_project())
        tab = self.gui.GeometryTab(state)
        tab._refresh_from_project()
        tab.table.item(1, 1).setText("0.3000")
        tab._apply_table_edits()
        # asterisk = "not saved to disk": live apply still leaves
        # the project dirty until "Save project".
        self.assertTrue(tab._dirty)
        self.assertAlmostEqual(state.project.geometry.chord_norm[1], 0.3, places=6)
        # canvas "Top View" drew something (>=1 line in the single ax)
        tab._refresh_preview()
        self.assertGreaterEqual(len(tab.planform_canvas.simple.ax.get_lines()), 1)

    def test_chord_twist_tab_no_stale_twin_axes_across_refreshes(self):
        """Regression: `plot_chord_twist_distribution` uses twinx -- the
        embedded canvas cannot accumulate phantom axes on each live
        refresh (see `MplCanvas.clear`)."""
        state = self.gui.AppState()
        state.set_project(self._make_project())
        tab = self.gui.GeometryTab(state)
        tab.preview_tabs.setCurrentIndex(1)
        for _ in range(3):
            tab._refresh_preview()
        self.assertEqual(len(tab.chord_twist_canvas.simple.ax.figure.axes), 2)


@unittest.skipUnless(_HAS_QT, "PyQt6 not installed in this environment")
class TestResultsTabDropsGeometriaMode(unittest.TestCase):
    """docs/plano_v3.md Part 6.1: the "Geometry" mode from ResultsTab was
    removed -- functionality has completely migrated to the embedded
    preview in the Geometry tab."""

    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])
        from zbemt.gui import app as gui
        cls.gui = gui

    def test_geometria_not_in_modes(self):
        state = self.gui.AppState()
        geometry_tab = self.gui.GeometryTab(state)
        airfoil_tab = self.gui.AirfoilTab(state)
        results_tab = self.gui.ResultsTab(state, geometry_tab, airfoil_tab)
        self.assertNotIn("Geometria", results_tab._MODES)
        self.assertFalse(hasattr(results_tab, "_build_geometry_options"))
        self.assertFalse(hasattr(results_tab, "_refresh_geometry"))


@unittest.skipUnless(_HAS_QT, "PyQt6 not installed in this environment")
class TestResultsTabCustomXYMode(unittest.TestCase):
    """Custom X-Y mode for ResultsTab (user request: plot any summary
    key against any other, grouping by a third) -- X/Y/Group-by combos
    populated from current selection, and mode switching must not raise."""

    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])
        from zbemt.gui import app as gui
        cls.gui = gui

    def _tab_with_selection(self):
        state = self.gui.AppState()
        state.set_project(_make_project())
        geometry_tab = self.gui.GeometryTab(state)
        airfoil_tab = self.gui.AirfoilTab(state)
        tab = self.gui.ResultsTab(state, geometry_tab, airfoil_tab)
        tab.show()  # isVisible() only reflects the real tree when the top is shown

        from zbemt.models import Results
        r1 = Results(summary={"mu_x": 0.0, "CT": 0.01, "collective_deg": 8.0}, maps={}, condition_name="c1")
        r2 = Results(summary={"mu_x": 0.1, "CT": 0.02, "collective_deg": 10.0}, maps={}, condition_name="c2")
        state.add_history_entry(kind="case", label="caso A", results=r1)
        state.add_history_entry(kind="case", label="caso B", results=r2)
        from PyQt6.QtCore import Qt as _Qt
        for i in range(tab.history_list.count()):
            tab.history_list.item(i).setCheckState(_Qt.CheckState.Checked)
        tab._on_selection_changed()
        return tab

    def test_xy_combos_exist(self):
        tab = self._tab_with_selection()
        self.assertTrue(hasattr(tab, "xy_x_combo"))
        self.assertTrue(hasattr(tab, "xy_y_combo"))
        self.assertTrue(hasattr(tab, "xy_group_combo"))

    def test_combos_populate_from_selection_and_exclude_cfg_fields(self):
        with unittest.mock.patch("zbemt.gui.tabs.results.HAS_INTERACTIVE_PLOTS", False):
            tab = self._tab_with_selection()
            tab.mode_list.setCurrentRow(tab._MODES.index("Coefficients vs axis"))
            tab.axis_mode_xy_check.setChecked(True)
        keys = {tab.xy_x_combo.itemData(i) for i in range(tab.xy_x_combo.count())}
        self.assertIn("mu_x", keys)
        self.assertIn("CT", keys)
        self.assertIn("collective_deg", keys)
        self.assertFalse(any(k and k.startswith("cfg_") for k in keys))
        # "(none)" always available in the group-by combo
        group_keys = [tab.xy_group_combo.itemData(i) for i in range(tab.xy_group_combo.count())]
        self.assertIn(None, group_keys)

    def test_switching_to_custom_xy_mode_refreshes_without_raising(self):
        # HAS_INTERACTIVE_PLOTS=False here for the same reason no other
        # test in this suite exercises the Plotly path for grid mode
        # (_refresh_axis): QWebEngineView hangs (no exception) under
        # QT_QPA_PLATFORM=offscreen -- see PlotlyCanvasHost's docstring in
        # gui/common.py. The Plotly path for free X-Y is covered
        # separately in tests/test_plots_interactive.py (no PyQt6).
        with unittest.mock.patch("zbemt.gui.tabs.results.HAS_INTERACTIVE_PLOTS", False):
            tab = self._tab_with_selection()
            tab.mode_list.setCurrentRow(tab._MODES.index("Coefficients vs axis"))
            tab.axis_mode_xy_check.setChecked(True)  # dispara _on_axis_mode_changed -> _refresh_axis
            self.assertTrue(tab.axis_xy_options.isVisible())
            self.assertFalse(tab.axis_grid_options.isVisible())

    def test_grid_mode_still_default_and_unaffected(self):
        """Nothing changes for those who don't touch the selector: grid stays default."""
        tab = self._tab_with_selection()
        tab.mode_list.setCurrentRow(tab._MODES.index("Coefficients vs axis"))
        self.assertFalse(tab.axis_mode_xy_check.isChecked())
        self.assertTrue(tab.axis_grid_options.isVisible())
        self.assertFalse(tab.axis_xy_options.isVisible())


@unittest.skipUnless(_HAS_QT, "PyQt6 not installed in this environment")
class TestFlowIndicatorBar(unittest.TestCase):
    """docs/plano_v3.md Part 6.2 -- flow bar between tabs: gray without
    project, green with valid project, click jumps directly to tab."""

    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])
        from zbemt.gui import app as gui
        cls.gui = gui

    def test_no_project_all_gray_and_click_jumps_tab(self):
        win = self.gui.MainWindow()
        for btn in win.flow_bar._buttons:
            self.assertIn("#9e9e9e", btn.styleSheet())
        win.flow_bar._buttons[2].click()   # "Airfoil"
        self.assertEqual(win.tabs.currentIndex(), 2)

    def test_project_loaded_marks_projeto_green(self):
        win = self.gui.MainWindow()
        geom = geometry.generate_tapered(n_stations=8)
        airfoil = AirfoilDef(source="analytical", stall_model="clip",
                              alpha_stall_pos_deg=15.0, alpha_stall_neg_deg=-6.0)
        project = Project(name="t", geometry=geom, airfoil=airfoil,
                           config=dict(Ne=6, Npsi=8, solver="fixed_point", max_iter=80))
        win.state.set_project(project)
        self.assertIn("#2e7d32", win.flow_bar._buttons[0].styleSheet())


@unittest.skipUnless(_HAS_QT, "PyQt6 not installed in this environment")
class TestInflowCouplingComboRemoved(unittest.TestCase):
    """Point fix (see docs/CHANGELOG.md): the 'Type:' inflow coupling
    combo was completely removed -- not just the 'global' option --
    because for every family implemented today, it never offered more
    than one real option (always 'local' or 'steady')."""

    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])
        from zbemt.gui import app as gui
        cls.gui = gui

    def test_coupling_type_widget_does_not_exist(self):
        state = self.gui.AppState()
        tab = self.gui.ConfigMotorTab(state)
        self.assertFalse(hasattr(tab, "cfg_inflow_coupling_type"))
        self.assertFalse(hasattr(tab, "_update_inflow_coupling_options"))
        self.assertFalse(hasattr(tab, "_INFLOW_COUPLING_OPTIONS"))

    def test_field_model_uses_fixed_coupling_per_family(self):
        state = self.gui.AppState()
        tab = self.gui.ConfigMotorTab(state)
        for family, expected in (("glauert", "glauert_local"), ("coleman", "coleman_local"),
                                  ("drees", "drees_local"), ("pitt_peters", "pitt_peters_steady")):
            tab.cfg_inflow_family.setCurrentText(family)
            self.assertEqual(tab._inflow_field_model_from_widgets(), expected)

    def test_loading_legacy_global_field_model_falls_back_to_local(self):
        state = self.gui.AppState()
        tab = self.gui.ConfigMotorTab(state)
        with helpers.patch_message_box_everywhere("QMessageBox"):
            tab._set_inflow_widgets_from_field_model("drees_global")
        self.assertEqual(tab.cfg_inflow_family.currentText(), "drees")
        self.assertEqual(tab._inflow_field_model_from_widgets(), "drees_local")


    def test_source_combo_has_four_consolidated_options(self):
        """Item 6 (plano_v3.md Part 7), extended by user decision: analytical /
        table / neuralfoil / xfoil in a single selector -- no separate visible
        'Engine' combo."""
        state = self.gui.AppState()
        tab = self.gui.AirfoilTab(state)
        items = [tab.source_combo.itemText(i) for i in range(tab.source_combo.count())]
        self.assertEqual(items, ["analytical", "table", "neuralfoil", "xfoil"])

    def test_each_source_mode_shows_only_its_own_blocks(self):
        state = self.gui.AppState()
        tab = self.gui.AirfoilTab(state)
        tab.show()
        expected = {
            "analytical": dict(table=False, geometry=False, external=False),
            "table": dict(table=True, geometry=False, external=False),
            "neuralfoil": dict(table=True, geometry=True, external=True),
            "xfoil": dict(table=True, geometry=True, external=True),
        }
        for mode, vis in expected.items():
            tab.source_combo.setCurrentText(mode)
            self.assertEqual(tab.table_box.isVisible(), vis["table"], mode)
            self.assertEqual(tab.geometry_box.isVisible(), vis["geometry"], mode)
            self.assertEqual(tab.external_box.isVisible(), vis["external"], mode)

    def test_neuralfoil_mode_maps_to_table_source_with_neuralfoil_engine(self):
        """'neuralfoil' is not a separate AirfoilDef.source -- it is treated
        as a table generated on the fly (item 6)."""
        state = self.gui.AppState()
        tab = self.gui.AirfoilTab(state)
        tab.source_combo.setCurrentText("neuralfoil")
        a = tab._collect_airfoil_def()
        self.assertEqual(a.source, "table")
        self.assertEqual(a.external_engine, "neuralfoil")

    def test_loading_neuralfoil_airfoil_def_selects_neuralfoil_mode(self):
        a = AirfoilDef(source="table", external_engine="neuralfoil")
        state = self.gui.AppState()
        tab = self.gui.AirfoilTab(state)
        tab._load_form_from_airfoil_def(a)
        self.assertEqual(tab.source_combo.currentText(), "neuralfoil")

    def test_loading_plain_table_airfoil_def_selects_table_mode(self):
        a = AirfoilDef(source="table", external_engine="none")
        state = self.gui.AppState()
        tab = self.gui.AirfoilTab(state)
        tab._load_form_from_airfoil_def(a)
        self.assertEqual(tab.source_combo.currentText(), "table")


@unittest.skipUnless(_HAS_QT, "PyQt6 not installed in this environment")
class TestNeuralFoilExternalBox(unittest.TestCase):
    """Smoke tests for the 'f) External Engine -- NeuralFoil' block (Phase 7):
    combo restricted to none/neuralfoil (XFOIL removed), 'Run' button
    reflects actual package availability, and successful run feeds
    the Polar canvas (Part 5) with a Reynolds navigator without
    reopening the tab."""

    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])
        from zbemt.gui import app as gui
        cls.gui = gui

    def test_engine_combo_offers_none_neuralfoil_and_xfoil(self):
        """XFOIL returned as a first-class engine: the combo offers it and
        the binary is required only when a run with it is requested."""
        state = self.gui.AppState()
        tab = self.gui.AirfoilTab(state)
        items = [tab.engine_combo.itemText(i) for i in range(tab.engine_combo.count())]
        self.assertEqual(items, ["none", "neuralfoil", "xfoil"])

    def test_xfoil_adjustment_fields_exist_and_follow_engine_visibility(self):
        """The three XFOIL-dedicated adjustment inputs exist, start hidden
        for engines that ignore them, and appear only when the engine is
        xfoil."""
        state = self.gui.AppState()
        tab = self.gui.AirfoilTab(state)
        tab.show()
        tab.source_combo.setCurrentText("neuralfoil")
        tab.engine_combo.setCurrentText("neuralfoil")
        self.assertFalse(tab.ext_ncrit.isVisible())
        self.assertFalse(tab.ext_xtr_top.isVisible())
        self.assertFalse(tab.ext_xtr_bot.isVisible())
        tab.engine_combo.setCurrentText("xfoil")
        self.assertTrue(tab.ext_ncrit.isVisible())
        self.assertTrue(tab.ext_xtr_top.isVisible())
        self.assertTrue(tab.ext_xtr_bot.isVisible())

    def test_xfoil_adjustment_fields_have_ranges_defaults_and_keyed_tooltips(self):
        state = self.gui.AppState()
        tab = self.gui.AirfoilTab(state)
        self.assertEqual((tab.ext_ncrit.minimum(), tab.ext_ncrit.maximum()), (1.0, 15.0))
        self.assertEqual(tab.ext_ncrit.value(), 9.0)
        for widget in (tab.ext_xtr_top, tab.ext_xtr_bot):
            self.assertEqual(widget.minimum(), 0.01)
            self.assertEqual(widget.maximum(), 1.0)
            self.assertEqual(widget.value(), 1.0)
        self.assertTrue(tab.ext_ncrit.toolTip().startswith('"xfoil_ncrit"'))
        self.assertTrue(tab.ext_xtr_top.toolTip().startswith('"xfoil_xtr_top"'))
        self.assertTrue(tab.ext_xtr_bot.toolTip().startswith('"xfoil_xtr_bot"'))

    def test_xfoil_adjustment_values_round_trip_through_airfoil_def(self):
        state = self.gui.AppState()
        tab = self.gui.AirfoilTab(state)
        a = AirfoilDef(source="table", external_engine="xfoil",
                       xfoil_ncrit=11.5, xfoil_xtr_top=0.7, xfoil_xtr_bot=0.3)
        tab._load_form_from_airfoil_def(a)
        collected = tab._collect_airfoil_def()
        self.assertAlmostEqual(collected.xfoil_ncrit, 11.5)
        self.assertAlmostEqual(collected.xfoil_xtr_top, 0.7)
        self.assertAlmostEqual(collected.xfoil_xtr_bot, 0.3)

    def test_external_block_labels_are_engine_neutral(self):
        """The block no longer promises NeuralFoil: with 'xfoil' selectable,
        title and button say what they do, not which engine does it."""
        state = self.gui.AppState()
        tab = self.gui.AirfoilTab(state)
        self.assertEqual(tab.external_box.title(), "Polar Generation via External Engine")
        self.assertEqual(tab.btn_run_external.text(), "Run polar generation")

    def test_run_with_xfoil_requires_the_binary_before_running(self):
        """`require_optional_binary` gates the xfoil path: without the
        executable anywhere in the lookup chain, no worker is dispatched
        and the actionable dialog opens (Locate… / download link)."""
        from zbemt.gui import common
        from zbemt import airfoils
        state = self.gui.AppState()
        tab = self.gui.AirfoilTab(state)
        tab.source_combo.setCurrentText("neuralfoil")
        tab._profile = airfoils.generate_naca4("0012")
        tab.engine_combo.setCurrentText("xfoil")
        opened = []
        def fake_exec(dialog):
            opened.append(dialog)
            return 0  # closed without locating anything
        with unittest.mock.patch.object(common, "resolve_xfoil_binary",
                                        return_value=None):
            with unittest.mock.patch.object(common.MissingBinaryDialog,
                                            "exec", fake_exec):
                tab._run_external()
        self.assertEqual(len(opened), 1, "the missing-binary dialog must open once")
        self.assertIn("ZBEMT_XFOIL_BIN", opened[0].message_label.text())
        self.assertIsNone(tab._ext_worker, "no worker should be dispatched without the binary")

    def test_require_optional_binary_found_through_env_var(self):
        import tempfile
        from pathlib import Path
        from zbemt.gui import common
        state = self.gui.AppState()
        tab = self.gui.AirfoilTab(state)
        with tempfile.TemporaryDirectory() as tmp:
            fake = Path(tmp) / ("xfoil.exe" if os.name == "nt" else "xfoil")
            fake.write_bytes(b"stub")
            with unittest.mock.patch.dict(os.environ, {"ZBEMT_XFOIL_BIN": str(fake)}):
                with helpers.patch_message_box_everywhere("QMessageBox") as mb:
                    ok = common.require_optional_binary(
                        tab, feature="XFOIL", env_var="ZBEMT_XFOIL_BIN",
                        download_hint="Install XFOIL.")
                    self.assertEqual(mb.information.call_count, 0)
        self.assertTrue(ok)

    def _fake_executable(self, tmp: str) -> str:
        exe = Path(tmp) / ("xfoil.exe" if os.name == "nt" else "xfoil")
        exe.write_bytes(b"stub binary")
        return str(exe)

    def test_no_dialog_when_the_binary_resolves_at_entry(self):
        """A hit anywhere in the chain returns True before any dialog:
        today's users whose XFOIL sits in the standard install folder
        stop seeing the box at all."""
        import tempfile
        from zbemt.gui import common
        state = self.gui.AppState()
        tab = self.gui.AirfoilTab(state)
        with tempfile.TemporaryDirectory() as tmp:
            fake = self._fake_executable(tmp)
            with unittest.mock.patch.object(common, "resolve_xfoil_binary",
                                            return_value=fake):
                with unittest.mock.patch.object(
                        common.MissingBinaryDialog, "exec") as exec_mock:
                    ok = common.require_optional_binary(
                        tab, feature="XFOIL", env_var="ZBEMT_XFOIL_BIN",
                        download_hint="Install XFOIL.")
        self.assertTrue(ok)
        exec_mock.assert_not_called()

    def test_locate_flow_saves_the_choice_and_returns_true(self):
        """Picking a valid executable stores it (`paths.save_app_setting`)
        and closes the request as satisfied, without restarting the
        flow or needing a restart of zBEMT."""
        import tempfile
        from zbemt.gui import common
        from zbemt import paths as paths_mod
        state = self.gui.AppState()
        tab = self.gui.AirfoilTab(state)
        with tempfile.TemporaryDirectory() as home, \
                tempfile.TemporaryDirectory() as pick_dir:
            fake = self._fake_executable(pick_dir)
            def fake_exec(dialog):
                dialog.chosen_path = fake
                return 1  # Accepted
            with unittest.mock.patch.dict(os.environ,
                                          {"ZBEMT_HOME": home,
                                           "ZBEMT_XFOIL_BIN": ""}):
                with unittest.mock.patch.object(common, "resolve_xfoil_binary",
                                                return_value=None):
                    with unittest.mock.patch.object(common.MissingBinaryDialog,
                                                    "exec", fake_exec):
                        ok = common.require_optional_binary(
                            tab, feature="XFOIL", env_var="ZBEMT_XFOIL_BIN",
                            download_hint="Install XFOIL.")
                self.assertTrue(ok)
                self.assertEqual(
                    paths_mod.load_app_setting(common.XFOIL_SETTINGS_KEY),
                    fake)

    def test_cancel_leaves_the_settings_store_unchanged(self):
        import tempfile
        from pathlib import Path
        from zbemt.gui import common
        from zbemt import paths as paths_mod
        state = self.gui.AppState()
        tab = self.gui.AirfoilTab(state)
        with tempfile.TemporaryDirectory() as home:
            with unittest.mock.patch.dict(os.environ,
                                          {"ZBEMT_HOME": home,
                                           "ZBEMT_XFOIL_BIN": ""}):
                with unittest.mock.patch.object(common, "resolve_xfoil_binary",
                                                return_value=None):
                    with unittest.mock.patch.object(
                            common.MissingBinaryDialog, "exec",
                            return_value=0):  # rejected, nothing picked
                        ok = common.require_optional_binary(
                            tab, feature="XFOIL", env_var="ZBEMT_XFOIL_BIN",
                            download_hint="Install XFOIL.")
                self.assertFalse(ok)
                self.assertIsNone(
                    paths_mod.load_app_setting(common.XFOIL_SETTINGS_KEY))
                self.assertFalse(
                    Path(home, "settings.json").exists(),
                    "a cancelled dialog must not write the store")

    def test_invalid_pick_reports_inline_and_dialog_stays_open(self):
        """A pick that fails the existence check never satisfies the
        gate: inline feedback appears and Locate… keeps being offered."""
        import tempfile
        from PyQt6.QtWidgets import QDialog
        from zbemt.gui import common
        dialog = common.MissingBinaryDialog(None, feature="XFOIL",
                                            env_var="ZBEMT_XFOIL_BIN")
        with tempfile.TemporaryDirectory() as tmp:
            real_pick = self._fake_executable(tmp)
            ghost = str(Path(tmp, "ghost", "xfoil.exe"))
            with unittest.mock.patch.object(
                    common.QFileDialog, "getOpenFileName",
                    return_value=(ghost, "")):
                dialog._on_locate()
            self.assertTrue(dialog._feedback.isVisibleTo(dialog))
            self.assertIn("does not exist", dialog._feedback.text())
            self.assertIsNone(dialog.chosen_path)
            self.assertNotEqual(dialog.result(), QDialog.DialogCode.Accepted)
            # A valid pick on the second try goes through.
            with unittest.mock.patch.object(
                    common.QFileDialog, "getOpenFileName",
                    return_value=(real_pick, "")):
                dialog._on_locate()
            self.assertEqual(dialog.chosen_path, real_pick)
            self.assertEqual(dialog.result(), QDialog.DialogCode.Accepted)

    def test_dialog_lists_the_four_places_and_both_options(self):
        import os
        from unittest import mock
        from zbemt.gui import common
        # Hermetic: a machine with ZBEMT_XFOIL_BIN set globally (this
        # dev machine) would show a resolved path instead of "(not set)".
        with mock.patch.dict(os.environ, {"ZBEMT_XFOIL_BIN": ""}):
            dialog = common.MissingBinaryDialog(None, feature="XFOIL",
                                                env_var="ZBEMT_XFOIL_BIN")
        text = dialog.message_label.text()
        for expected in ("ZBEMT_XFOIL_BIN", "(not set)",
                         "Remembered 'Locate…' choice",
                         "PATH", "Standard install folders",
                         "1. Already installed?",
                         "2. Not installed?",
                         "https://web.mit.edu/drela/Public/web/xfoil/",
                         "The choice is remembered"):
            self.assertIn(expected, text)

    def test_run_button_stays_clickable_without_the_optional_package(self):
        """Before the button was DISABLED when `neuralfoil` was missing, and the
        reason lived only in a tooltip -- anyone who didn't hover the mouse
        exactly there saw a dead button without explanation. Now it stays clickable
        and `_run_external` opens a dialog with the installation command
        (`common.require_optional_package`)."""
        state = self.gui.AppState()
        tab = self.gui.AirfoilTab(state)
        self.assertTrue(tab.btn_run_external.isEnabled())

    def test_pacote_opcional_ausente_abre_dialogo_com_comando_de_instalacao(self):
        from zbemt.gui import common
        state = self.gui.AppState()
        tab = self.gui.AirfoilTab(state)
        with unittest.mock.patch.dict(
                common.OPTIONAL_PACKAGES,
                {"inexistente": ("modulo_que_nao_existe_zbemt", "pip install foo", "a thing")}):
            with helpers.patch_message_box_everywhere("QMessageBox") as mb:
                ok = common.require_optional_package(tab, "inexistente")
        self.assertFalse(ok)
        mb.information.assert_called_once()
        texto = mb.information.call_args[0][2]
        self.assertIn("pip install foo", texto)

    def test_pacote_opcional_presente_nao_abre_dialogo(self):
        from zbemt.gui import common
        state = self.gui.AppState()
        tab = self.gui.AirfoilTab(state)
        with unittest.mock.patch.dict(
                common.OPTIONAL_PACKAGES,
                {"presente": ("json", "pip install json", "a thing")}):
            with helpers.patch_message_box_everywhere("QMessageBox") as mb:
                ok = common.require_optional_package(tab, "presente")
        self.assertTrue(ok)
        mb.information.assert_not_called()

    def test_export_button_disabled_until_run_succeeds(self):
        state = self.gui.AppState()
        tab = self.gui.AirfoilTab(state)
        self.assertFalse(tab.btn_export_external.isEnabled())

    def test_run_neuralfoil_populates_reynolds_navigator(self):
        """C4 (production-plan.md): before it ran NeuralFoil for real,
        synchronously, in the GUI thread -- >7min on a modest sweep and
        cause of the entire suite hanging. Now ``_run_external``
        dispatches an ``ExternalPolarWorker`` in a QThread (same pattern as
        ``BatchRunnerWorker``); this test only validates the WIRING (the
        Reynolds navigator is populated after the worker ends),
        mocking the external engine instead of running NeuralFoil for real."""
        from zbemt import airfoils
        from zbemt.models import PolarSlice
        state = self.gui.AppState()
        tab = self.gui.AirfoilTab(state)
        tab._profile = airfoils.generate_naca4("0012")
        tab.re_list_edit.setText("1e5, 1e6")
        tab.mach_list_edit.setText("0.1")
        tab.ext_alpha_min.setValue(-6)
        tab.ext_alpha_max.setValue(6)
        tab.ext_alpha_step.setValue(2.0)
        tab.btn_run_external.setEnabled(True)   # engine may be unavailable in this environment

        alphas = [-6.0, -4.0, -2.0, 0.0, 2.0, 4.0, 6.0]

        def fake_run_polar(engine, geometry, reynolds_list, mach_list,
                            alpha_min_deg, alpha_max_deg, alpha_step_deg,
                            **_kwargs):   # diagnostics etc.
            return [
                PolarSlice(alpha_deg=list(alphas), cl=[0.1 * a for a in alphas],
                           cd=[0.01] * len(alphas), reynolds=re, mach=ma)
                for re in reynolds_list for ma in mach_list
            ]

        # QMessageBox.information (success dialog) is modal -- under
        # offscreen/headless, exec() blocks waiting for a click that
        # never comes, hanging the test indefinitely; mocked as in
        # other tests in this file (see test_..._warning above).
        with unittest.mock.patch("zbemt.external_solvers.run_polar", side_effect=fake_run_polar), \
             helpers.patch_message_box_everywhere("QMessageBox"):
            tab._run_external()
            self.assertIsNotNone(tab._ext_worker, "worker deveria ter sido despachado")

            loop = QEventLoop()
            done = {"v": False}

            def _stop(*_args):
                done["v"] = True
                loop.quit()

            tab._ext_worker.finished.connect(_stop)
            tab._ext_worker.failed.connect(_stop)
            QTimer.singleShot(10000, loop.quit)
            loop.exec()
            self.assertTrue(done["v"], "NeuralFoil worker did not finish within the timeout")

        self.assertTrue(tab.btn_export_external.isEnabled())
        a = tab._collect_airfoil_def()
        axes = airfoils.axis_values(a)
        self.assertEqual(len(axes["reynolds"]), 2)


if __name__ == "__main__":
    unittest.main()


@unittest.skipUnless(_HAS_QT, "PyQt6 not installed in this environment")
class TestToolsButton(unittest.TestCase):
    """The QMenuBar hid itself against the dark theme strip (dark-gray
    text on black), so the entry point of the dedicated design windows
    was invisible. The Tools BUTTON next to Help -- same pill, same
    size -- is the entry point now, and the menu bar is gone."""

    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def _window(self):
        from zbemt.gui import app as gui
        win = gui.MainWindow()
        win.resize(1500, 900)
        win.show()
        for _ in range(6):
            self.app.processEvents()
        self.addCleanup(win.hide)
        self.addCleanup(win.deleteLater)
        return win

    def test_menu_bar_is_gone_and_tools_sits_beside_help(self):
        win = self._window()
        self.assertEqual(len(win.menuBar().actions()), 0,
                         "the invisible menu bar must not come back")
        bar = win.flow_bar
        self.assertTrue(bar.btn_tools.isVisible())
        self.assertLessEqual(
            abs(bar.btn_tools.width() - bar.btn_help.width()), 2,
            "Tools and Help must share the same pill size")

    def test_tools_click_opens_the_geometry_designer(self):
        win = self._window()
        self.assertFalse(win.geometry_designer.isVisible())
        # The Tools pill hangs a menu off it: the click opens the menu,
        # and the MENU ACTION carries the request (tools_requested with
        # the window's key). Triggering the action is what a user's pick
        # does, so that is what the test drives.
        actions = {a.text(): a for a in win.flow_bar.btn_tools.menu().actions()}
        self.assertIn("Geometry Designer", actions)
        actions["Geometry Designer"].trigger()
        for _ in range(6):
            self.app.processEvents()
        self.assertTrue(win.geometry_designer.isVisible())
        win.geometry_designer.close()
