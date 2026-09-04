"""End-to-end battery for the GUI: the Results tab.

Step 7 of the workflow, driven for real through Qt: the history, the disk
maps, the table mode and the exports. The earlier steps are in
`test_gui_e2e.py` and the closing steps in `test_gui_e2e_session.py`. The
base class the three files share is in `gui_e2e_base.py`, which explains
why the battery is split.
"""

from gui_e2e_base import (  # noqa: F401
    GuiE2ETestCase, _pump_until_finished, _run_worker_and_wait, _HAS_QT,
    api, asdict, helpers, geometry_mod, math, mock, time, unittest,
    AirfoilDef, BatchDefinition, FlightCondition, Project,
    QApplication, QCloseEvent, QMessageBox, Qt, QTimer)


class TestStep7Results(GuiE2ETestCase):
    def _show_mode(self, tab, mode: str):
        """Selects a plot/table mode AND lets the deferred redraw run.

        The Results tab coalesces redraws on a 150 ms single-shot timer
        so that a burst of clicks costs one refresh instead of one per
        click (`PR-11`). The table used to be the exception, refreshed
        inside the click; it was in fact the most expensive of the seven
        modes, so it now takes the same deferred path. A test that reads
        the table straight after selecting the mode is reading it before
        the redraw has run -- as the user would, for 150 ms.
        """
        tab.mode_list.setCurrentRow(tab._MODES.index(mode))
        if tab._selection_timer.isActive():
            tab._selection_timer.stop()
            tab._on_selection_changed()

    def _project_with_history(self, state):
        from zbemt.models import Results
        self._new_project(state)
        geometry_tab = self.gui.GeometryTab(state)
        airfoil_tab = self.gui.AirfoilTab(state)
        tab = self.gui.ResultsTab(state, geometry_tab, airfoil_tab)

        r_case = Results(summary={"mu_x": 0.0, "CT": 0.01, "CQ": 0.001},
                          maps={"Fn": [[0.0, 1.0], [1.0, 2.0]]}, condition_name="c1")
        r_batch = [Results(summary={"mu_x": 0.1, "CT": 0.02}, maps={}, condition_name="b1"),
                   Results(summary={"mu_x": 0.2, "CT": 0.03}, maps={}, condition_name="b2")]
        state.add_history_entry(kind="case", label="caso pairado", results=r_case)
        state.add_history_entry(kind="batch", label="batch mu_x-sweep", results=r_batch)
        return tab

    def test_marcar_caso_no_historico_adia_o_redesenho_em_vez_de_travar(self):
        """Responsiveness bug: checking/unchecking a history box called
        `_refresh_current()` (a complete matplotlib redraw, ~30ms) SYNCHRONOUSLY,
        one per click -- checking five cases froze the window five times in a
        row. Now the signal only restarts a timer (150ms, single-shot), so a
        burst of clicks coalesces into a single redraw."""
        state = self._make_state()
        tab = self._project_with_history(state)
        # new entries arrive already checked; unchecking first ensures that
        # the setCheckState below REALLY emits itemChanged (checking what
        # is already checked emits nothing)
        tab._clear_history_selection()
        redesenhos = {"n": 0}
        tab._refresh_current = lambda: redesenhos.__setitem__("n", redesenhos["n"] + 1)

        for i in range(tab.history_list.count()):
            tab.history_list.item(i).setCheckState(Qt.CheckState.Checked)

        # no redraws yet: the timer is single-shot and has not fired yet
        self.assertEqual(redesenhos["n"], 0)
        self.assertTrue(tab._selection_timer.isActive())
        self.assertTrue(tab._selection_timer.isSingleShot())
        # but the CHEAP state already followed the selection immediately --
        # the list of modes cannot lie about what is available to plot
        self.assertEqual(len(tab._selected_entries()), tab.history_list.count())

        # explicit buttons remain synchronous (it is what tests and users
        # expect from "Select all"/"Clear")
        tab._select_all_history()
        self.assertEqual(redesenhos["n"], 1)

    def test_trocar_modo_agenda_um_unico_redesenho(self):
        """Rapid switches between plots should not build a figure
        synchronously on each click, as that freezes the Results tab when
        multiple cases are selected."""
        state = self._make_state()
        tab = self._project_with_history(state)
        redesenhos = {"n": 0}
        tab._refresh_current = lambda: redesenhos.__setitem__("n", redesenhos["n"] + 1)

        tab.mode_list.setCurrentRow(tab._MODES.index("Coefficients vs axis"))
        tab.mode_list.setCurrentRow(tab._MODES.index("Convergence"))
        self.assertEqual(redesenhos["n"], 0)
        self.assertTrue(tab._selection_timer.isActive())
        self.assertTrue(tab._selection_timer.isSingleShot())

    def test_table_mode_shows_one_row_per_case_with_symbol_headers(self):
        """Bug: there was no tabular view of all saved parameters -- only
        plots (which require 1 or 2 results, never a complete matrix) and
        "Copy table" (TSV to the clipboard, not visible on the tab itself)."""
        state = self._make_state()
        tab = self._project_with_history(state)
        tab._select_all_history()

        self._show_mode(tab, "Table")

        # r_case (1 result) + r_batch (2 results) = 3 rows
        self.assertEqual(tab.table_widget.rowCount(), 3)
        headers = [tab.table_widget.horizontalHeaderItem(c).text()
                   for c in range(tab.table_widget.columnCount())]
        self.assertIn("μ_x", headers)   # api.SUMMARY_SYMBOLS -- not raw "mu_x"
        self.assertIn("C_T", headers)  # HTML subscript converted to suffix
        self.assertNotIn("mu_x", headers)

    def test_table_mode_hides_cfg_columns_by_default(self):
        from zbemt.models import Results
        state = self._make_state()
        self._new_project(state)
        tab = self.gui.ResultsTab(state, self.gui.GeometryTab(state), self.gui.AirfoilTab(state))
        state.add_history_entry(kind="case", label="c",
                                 results=Results(summary={"mu_x": 0.1, "CT": 0.01, "cfg_Ne": 120},
                                                  maps={}, condition_name="c1"))
        tab._select_all_history()
        self._show_mode(tab, "Table")

        headers = [tab.table_widget.horizontalHeaderItem(c).text()
                       for c in range(tab.table_widget.columnCount())]
        # The table is always complete, no configuration checkbox.
        self.assertIn("N_e", headers)
        self.assertFalse(hasattr(tab, "table_show_cfg_check"))

    def test_table_mode_empty_selection_clears_table(self):
        state = self._make_state()
        tab = self._project_with_history(state)
        tab._clear_history_selection()
        self._show_mode(tab, "Table")
        self.assertEqual(tab.table_widget.rowCount(), 0)

    def test_disk_map_continua_disponivel_com_varios_selecionados(self):
        """SUPERSEDE "requires exactly 1 selection".

        The "Disk map" mode would become DISABLED as soon as more than one
        result was checked, and a user who checked six Run Case cases simply
        could not plot anything -- it was the owner's complaint (item 13.1).
        The ambiguity of "which condition to draw" is now resolved by a
        condition selector, not by disabling selection: the mode remains
        enabled and draws the condition chosen in the dropdown.
        """
        state = self._make_state()
        tab = self._project_with_history(state)

        disk_item = [tab.mode_list.item(i) for i in range(tab.mode_list.count())
                     if tab.mode_list.item(i).text() == "Disk map"][0]
        self.assertTrue(bool(disk_item.flags() & Qt.ItemFlag.ItemIsEnabled),
                        "with 2 checked the disk map must remain available")
        self.assertGreaterEqual(tab.condition_combo.count(), 2,
                                "the condition selector offers the checked conditions")

        tab._clear_history_selection()
        tab.history_list.item(0).setCheckState(Qt.CheckState.Checked)
        self.assertTrue(bool(disk_item.flags() & Qt.ItemFlag.ItemIsEnabled))

    def test_overlay_of_two_results_enables_coefficients_vs_axis(self):
        state = self._make_state()
        tab = self._project_with_history(state)
        tab._select_all_history()

        coef_item = [tab.mode_list.item(i) for i in range(tab.mode_list.count())
                     if tab.mode_list.item(i).text() == "Coefficients vs axis"][0]
        self.assertTrue(bool(coef_item.flags() & Qt.ItemFlag.ItemIsEnabled))
        self.assertEqual(len(tab._selected_entries()), 2)

    def test_delete_selected_history_entry_removes_from_state(self):
        """Bug: results_history only grew (append-only by design, Part 4.1)
        -- there was no way to remove an entry without closing the entire
        project."""
        state = self._make_state()
        tab = self._project_with_history(state)
        self.assertEqual(len(state.results_history), 2)

        tab.history_list.setCurrentRow(0)
        tab._delete_selected_history_entries()

        self.assertEqual(len(state.results_history), 1)
        self.assertEqual(state.results_history[0].label, "batch mu_x-sweep")
        self.assertEqual(tab.history_list.count(), 1)

    def test_delete_with_nothing_highlighted_is_a_noop(self):
        state = self._make_state()
        tab = self._project_with_history(state)
        tab.history_list.setCurrentRow(-1)
        tab._delete_selected_history_entries()
        self.assertEqual(len(state.results_history), 2)

    def test_export_csv_via_run_batch_tab_writes_file(self):
        import os
        state = self._make_state()
        self._new_project(state)
        state.last_results = None
        from zbemt.models import Results
        state.last_results = Results(summary={"mu_x": 0.0, "CT": 0.01}, maps={}, condition_name="c1")

        run_batch_tab = self.gui.RunBatchTab(state)
        run_batch_tab.outdir_edit.setText(f"{self._tmpdir}/csv_export")
        run_batch_tab.save_csv_check.setChecked(True)
        for cb in run_batch_tab.plot_checks.values():
            cb.setChecked(False)

        run_batch_tab._export()

        self.assertTrue(os.path.isdir(f"{self._tmpdir}/csv_export"))
        exported = os.listdir(f"{self._tmpdir}/csv_export")
        self.assertTrue(any(f.endswith(".csv") for f in exported), exported)

    def test_export_via_run_batch_tab_shows_progress_dialog(self):
        """Bug: same freeze risk as ResultsTab._export_batch_disk_maps --
        this export also runs synchronously on the GUI thread (plots for a
        whole batch can take a while) with no progress feedback."""
        state = self._make_state()
        self._new_project(state)
        from zbemt.models import Results
        state.last_results = Results(summary={"mu_x": 0.0, "CT": 0.01}, maps={}, condition_name="c1")

        run_batch_tab = self.gui.RunBatchTab(state)
        run_batch_tab.outdir_edit.setText(f"{self._tmpdir}/csv_export2")
        run_batch_tab.save_csv_check.setChecked(True)
        for cb in run_batch_tab.plot_checks.values():
            cb.setChecked(False)

        with mock.patch("zbemt.gui.tabs.run_batch.QProgressDialog") as mock_progress:
            run_batch_tab._export()

        mock_progress.assert_called_once()
        mock_progress.return_value.show.assert_called_once()
        mock_progress.return_value.close.assert_called_once()

    def test_generate_report_defaults_to_project_outputs_dir(self):
        """Bug: "Generate report..." defaulted to `paths.outputs_dir()` (the
        REPO-ROOT/user-data outputs/ folder) instead of the per-project
        `<project.path>/outputs` convention every other export (CSV/TSV, batch
        export, CLI --report) already follows -- reports landed in a different
        place than everything else."""
        from pathlib import Path
        state = self._make_state()
        project = self._new_project(state, name="Heli_report_path")
        geometry_tab = self.gui.GeometryTab(state)
        airfoil_tab = self.gui.AirfoilTab(state)
        tab = self.gui.ResultsTab(state, geometry_tab, airfoil_tab)

        from zbemt.models import Results
        state.add_history_entry(kind="case", label="c1",
                                 results=Results(summary={"mu_x": 0.0, "CT": 0.01},
                                                  maps={}, condition_name="c1"))
        tab._select_all_history()

        with mock.patch("zbemt.gui.tabs.results.QFileDialog") as mock_dialog:
            mock_dialog.getSaveFileName.return_value = ("", "")
            tab._generate_report()
            default_path = mock_dialog.getSaveFileName.call_args[0][2]

        self.assertEqual(default_path, str(Path(project.path) / "outputs" / "report.html"))

    def test_export_batch_disk_maps_shows_progress_dialog(self):
        """Bug: "Export disk maps in batch" ran the whole export loop (now
        heavier -- the disk grid went from 12 to 16 fields) synchronously on
        the GUI thread with NO progress feedback at all, unlike its sibling
        "Generate report..." which already got this treatment for the exact
        same reason ("without this the button just freezes")."""
        state = self._make_state()
        project = self._new_project(state, name="Heli_batch_export")
        project.geometry = geometry_mod.generate_tapered(
            root_chord_norm=0.10, tip_chord_norm=0.05, twist_root_deg=14.0,
            twist_tip_deg=2.0, root_cutout_norm=0.15, radius_m=8.18,
            n_blades=4, n_stations=8, airfoil_name="perfil 1")
        project.airfoil = AirfoilDef(source="analytical", stall_model="clip")
        project.config.update(dict(Ne=6, Npsi=4, solver="fixed_point", max_iter=40))
        state.notify_geometry(); state.notify_airfoil(); state.notify_config()

        conditions = [FlightCondition(name=f"c{i}", mu_x=0.05 * i, collective_deg=8.0, rpm=600.0)
                      for i in range(2)]
        batch_results = [api.run_case(project, c) for c in conditions]
        state.add_history_entry(kind="batch", label="b1", results=batch_results)

        geometry_tab = self.gui.GeometryTab(state)
        airfoil_tab = self.gui.AirfoilTab(state)
        tab = self.gui.ResultsTab(state, geometry_tab, airfoil_tab)
        tab._select_all_history()

        from PyQt6.QtWidgets import QDialog
        with mock.patch("zbemt.gui.tabs.results.QDialog.exec",
                         return_value=QDialog.DialogCode.Accepted), \
             mock.patch("zbemt.gui.tabs.results.QProgressDialog") as mock_progress:
            # Renamed in `results.py`: the button exports maps of EVERY marked
            # condition, whether from a batch or standalone cases (item 27),
            # so the name no longer talks only about 'batch'.
            tab._export_selected_disk_maps()

        mock_progress.assert_called_once()
        mock_progress.return_value.show.assert_called_once()
        mock_progress.return_value.close.assert_called_once()
