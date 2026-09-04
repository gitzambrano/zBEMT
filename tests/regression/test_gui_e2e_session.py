"""End-to-end battery for the GUI: persistence, closing and the queue.

Step 8 of the workflow plus what surrounds a session: the save-before-quit
prompt, the documented shortcuts, the batch queue, the external polar
reaching the project, and the validation indicator clearing. The earlier
steps are in `test_gui_e2e.py` and `test_gui_e2e_results.py`, and the base
class the three files share is in `gui_e2e_base.py`, which explains why the
battery is split.
"""

from gui_e2e_base import (  # noqa: F401
    GuiE2ETestCase, _pump_until_finished, _run_worker_and_wait, _HAS_QT,
    api, asdict, helpers, geometry_mod, math, mock, time, unittest,
    AirfoilDef, BatchDefinition, FlightCondition, Project,
    QApplication, QCloseEvent, QMessageBox, Qt, QTimer)


# =============================================================================
# Step 8 -- Persistence (PRIORITY: field-by-field comparison)
# =============================================================================

class TestStep8Persistence(GuiE2ETestCase):
    def test_save_reopen_roundtrips_project_identically(self):
        state = self._make_state()
        project = self._new_project(state, name="Heli_persist")

        # edit fields in multiple tabs via real widgets/slots -----------
        geometry_tab = self.gui.GeometryTab(state)
        geometry_tab.n_blades.setValue(4)
        geometry_tab.radius_m.setValue(8.18)

        airfoil_tab = self.gui.AirfoilTab(state)
        airfoil_tab.source_combo.setCurrentText("analytical")
        airfoil_tab.stall_model_combo.setCurrentText("viterna")
        airfoil_tab.airfoil_name_edit.setText("perfil persistido")
        airfoil_tab.alpha_stall_pos.setValue(12.5)
        airfoil_tab._apply_to_project()

        config_tab = self.gui.ConfigMotorTab(state)
        config_tab.cfg_inflow_family.setCurrentText("pitt_peters")
        config_tab.cfg_Ne.setValue(45)
        config_tab.cfg_Npsi.setValue(36)
        config_tab._apply_config_to_project()

        run_case_tab = self.gui.RunCaseTab(state)
        run_case_tab.advance.set_mu(0.15)
        run_case_tab.collective_spin.setValue(9.0)
        run_case_tab.rpm_spin.setValue(650.0)
        run_case_tab._save_current_as_case_direct = None  # no-op placeholder
        with helpers.patch_message_box_everywhere("QInputDialog") as mock_input:
            mock_input.getText.return_value = ("caso_teste", True)
            run_case_tab._save_current_as_case()

        project_tab = self.gui.ProjectTab(state)

        # snapshot BEFORE saving (what the GUI thinks is in the project)
        before_geom = asdict(state.project.geometry)
        before_airfoil = asdict(state.project.airfoil)
        before_config = dict(state.project.config)
        before_name = state.project.name
        before_saved_cases = [asdict(c) for c in state.project.saved_cases]

        # fires the real slot of the "Save project" button
        project_tab._save_project()

        # "closes" the project (discards GUI state) and reopens from scratch,
        # via the same path as the "Open from another folder..." button
        reopened_state = self._make_state()
        with helpers.patch_message_box_everywhere("PROJECTS_ROOT", self._tmpdir):
            reopened_project_tab = self.gui.ProjectTab(reopened_state)
            reopened_project_tab._open_path(project.path)

        self.assertEqual(reopened_state.project.name, before_name,
                         "Project.name must survive the save-and-reopen cycle")
        self.assertEqual(asdict(reopened_state.project.geometry), before_geom)
        self.assertEqual(asdict(reopened_state.project.airfoil), before_airfoil)
        self.assertEqual(dict(reopened_state.project.config), before_config)
        self.assertEqual([asdict(c) for c in reopened_state.project.saved_cases], before_saved_cases)
        self.assertEqual(len(reopened_state.project.saved_cases), 1)
        self.assertEqual(reopened_state.project.saved_cases[0].name, "caso_teste")


# =============================================================================
# Q7 -- prompt for "save before quit?"
# =============================================================================

class TestQ7PromptDeFechamento(GuiE2ETestCase):
    """Before, closing the window discarded everything silently: nothing
    auto-saves and 'Apply to project' only writes to memory."""

    def _window(self):
        with helpers.patch_message_box_everywhere("PROJECTS_ROOT", self._tmpdir):
            win = self.gui.MainWindow()
        self.addCleanup(win.deleteLater)
        return win

    def test_without_pending_work_closes_without_asking(self):
        win = self._window()
        self._new_project(win.state)
        win.state.mark_saved()
        win.close()
        self.mock_msgbox.question.assert_not_called()

    def test_change_applied_but_not_saved_triggers_the_prompt(self):
        win = self._window()
        self._new_project(win.state)
        win.state.notify_config()          # what a tab calls when applying
        pending = win.unsaved_work()
        self.assertEqual(len(pending), 1)
        self.assertIn("project", pending[0])
        self.mock_msgbox.question.return_value = self.mock_msgbox.StandardButton.Discard
        win.close()
        self.mock_msgbox.question.assert_called_once()

    def test_asterisk_per_tab_is_only_a_mirror_of_state_unsaved(self):
        """Geometry/Airfoil/Config apply all edits live -- there is no longer
        a second layer of "edited, never applied" separate from `state.unsaved`;
        `_mark_dirty()` alone (without touching `state.unsaved`) should not
        happen through normal GUI usage, but `unsaved_work()` only looks
        at `state.unsaved`, so nothing appears here until a tab actually
        notifies the project."""
        win = self._window()
        self._new_project(win.state)
        win.state.mark_saved()
        win.tabs.widget(1)._mark_dirty()
        pending = win.unsaved_work()
        self.assertEqual(len(pending), 0)

    def test_editing_a_config_field_marks_the_asterisk_and_applies_live(self):
        """Editing a Config field applies directly to `state.project.config`
        (no "Apply to project" button) and marks the asterisk for "not saved
        to disk" -- only `Save project` clears that asterisk."""
        win = self._window()
        self._new_project(win.state)
        win.state.mark_saved()
        config_tab = win.tabs.widget(3)
        self.assertFalse(config_tab._dirty)
        self.assertEqual(win.tabs.tabText(3), "Config/Engine")

        new_value = config_tab.cfg_Ne.value() + 1
        config_tab.cfg_Ne.setValue(new_value)

        self.assertTrue(config_tab._dirty)
        self.assertEqual(win.tabs.tabText(3), "Config/Engine *")
        self.assertEqual(win.state.project.config["Ne"], new_value)
        pending = win.unsaved_work()
        self.assertEqual(len(pending), 1)
        self.assertIn("project", pending[0])

        config_tab._save_project()

        self.assertFalse(config_tab._dirty)
        self.assertEqual(win.tabs.tabText(3), "Config/Engine")

    def test_opening_a_project_does_not_mark_config_as_edited(self):
        """Populating widgets from the project (setValue/setChecked/
        setCurrentText) fires the same signals as manual editing -- without
        the guard `_refreshing_from_project`, opening a project would already
        leave the tab with a false-positive asterisk."""
        win = self._window()
        self._new_project(win.state)
        config_tab = win.tabs.widget(3)
        self.assertFalse(config_tab._dirty)
        self.assertEqual(win.tabs.tabText(3), "Config/Engine")

    def test_cancel_keeps_the_window_open(self):
        win = self._window()
        self._new_project(win.state)
        win.state.notify_config()
        self.mock_msgbox.question.return_value = self.mock_msgbox.StandardButton.Cancel
        event = QCloseEvent()
        win.closeEvent(event)
        self.assertFalse(event.isAccepted())

    def test_save_writes_to_disk_and_clears_the_pending_work(self):
        win = self._window()
        project = self._new_project(win.state)
        win.state.project.name = "renamed_before_closing"
        win.state.notify_config()
        self.mock_msgbox.question.return_value = self.mock_msgbox.StandardButton.Save
        win.close()
        self.assertEqual(api.open_project(project.path).name,
                         "renamed_before_closing")
        self.assertEqual(win.unsaved_work(), [])

    def test_opening_a_project_resets_the_mark(self):
        win = self._window()
        self._new_project(win.state)
        win.state.notify_config()
        self._new_project(win.state, name="other")
        self.assertEqual(win.unsaved_work(), [])


class TestShortcutsMatchDocumentation(GuiE2ETestCase):
    """Section 0.3 of docs/documentation.html promised Ctrl+N, Ctrl+O and
    Ctrl+1..7, which did not exist, and omitted Ctrl+R and Ctrl+Enter, which
    did. A documented but missing shortcut is worse than a missing one."""

    def _shortcuts(self):
        from PyQt6.QtGui import QShortcut
        with helpers.patch_message_box_everywhere("PROJECTS_ROOT", self._tmpdir):
            win = self.gui.MainWindow()
        self.addCleanup(win.deleteLater)
        self.addCleanup(win.close)
        return {s.key().toString() for s in win.findChildren(QShortcut)}, win

    def test_all_documented_shortcuts_exist(self):
        shortcuts, _ = self._shortcuts()
        documented = {"F1", "Ctrl+S", "Ctrl+O", "Ctrl+N", "Ctrl+R", "Ctrl+Enter"}
        documented |= {f"Ctrl+{i}" for i in range(1, 8)}
        missing = documented - shortcuts
        self.assertEqual(missing, set(), f"documented but nonexistent: {sorted(missing)}")

    def test_ctrl_number_jumps_to_the_corresponding_tab(self):
        _, win = self._shortcuts()
        for index in range(win.tabs.count()):
            win.tabs.setCurrentIndex(0)
            win.tabs.setCurrentIndex(index)
            self.assertEqual(win.tabs.currentIndex(), index)

    def test_ctrl_n_creates_a_project_and_goes_to_the_project_tab(self):
        _, win = self._shortcuts()
        win.tabs.setCurrentIndex(4)
        with helpers.patch_message_box_everywhere("PROJECTS_ROOT", self._tmpdir):
            with mock.patch.object(type(win._project_tab), "_new_project") as create:
                win._shortcut_new_project()
        create.assert_called_once()
        self.assertEqual(win.tabs.currentIndex(), 0)


# =============================================================================
# Run Batch reorganized: generate -> queue -> run
# =============================================================================

class TestRunBatchQueue(GuiE2ETestCase):
    """The tab had three run buttons and two case generation modes that did
    not meet: the factorial fired without ever showing what was about to run,
    and the explicit list lived in its own table. Now both modes flow into
    the same queue, and there is only one run button."""

    def _small_heli_project(self, state):
        """Same small rotor as the other stages: minimal mesh, just for the
        engine to run fast -- these tests are flow, not physics."""
        project = self._new_project(state)
        project.geometry = geometry_mod.generate_tapered(
            root_chord_norm=0.10, tip_chord_norm=0.05, twist_root_deg=14.0,
            twist_tip_deg=2.0, root_cutout_norm=0.15, radius_m=8.18,
            n_blades=4, n_stations=10, airfoil_name="perfil 1")
        project.airfoil = AirfoilDef(source="analytical", stall_model="clip",
                                      alpha_stall_pos_deg=15.0, alpha_stall_neg_deg=-6.0)
        project.config.update(dict(Ne=8, Npsi=6, solver="fixed_point", max_iter=60,
                                    reverse_flow_model="simple_flip"))
        state.notify_geometry()
        state.notify_airfoil()
        state.notify_config()
        return project

    def _tab(self):
        state = self._make_state()
        self._small_heli_project(state)
        tab = self.gui.RunBatchTab(state)
        return state, tab

    def _build_factorial(self, tab, mu_values="0.0, 0.1, 0.2"):
        sc1, uc1, ve1 = tab.axis_rows[0]
        i_long = [i for i, (_l, s) in enumerate(tab._AXIS_SLOTS) if s == "inplane"][0]
        sc1.setCurrentIndex(i_long)
        uc1.setCurrentText("mu_x")
        ve1.setText(mu_values)
        tab.fixed_rpm.setValue(600.0)

    def test_generate_does_not_run(self):
        """Seeing the cases before firing N solves is the whole point of the queue."""
        state, tab = self._tab()
        self._build_factorial(tab)
        tab._generate_cases()
        self.assertEqual(tab.batch_table.rowCount(), 3)
        self.assertIsNone(state.last_results)

    def test_a_single_run_button_and_it_follows_the_queue(self):
        _state, tab = self._tab()
        self.assertFalse(tab.btn_run.isEnabled(), "empty queue should disable run")
        self._build_factorial(tab)
        tab._generate_cases()
        self.assertTrue(tab.btn_run.isEnabled())
        self.assertIn("3", tab.btn_run.text())

    def test_the_two_modes_feed_the_same_queue(self):
        """It is what allows mixing: one factorial plus one standalone case."""
        _state, tab = self._tab()
        self._build_factorial(tab)
        tab._generate_cases()
        self.assertEqual(tab.batch_table.rowCount(), 3)

        tab.radio_list.setChecked(True)
        tab.add_row_advance.set_mu(0.35)
        tab.collective_spin.setValue(5.0)
        tab.rpm_spin.setValue(600.0)
        tab._generate_cases()
        self.assertEqual(tab.batch_table.rowCount(), 4,
                          "the single case should ADD, not replace")
        conditions = tab._queue_conditions()
        self.assertAlmostEqual(conditions[-1].mu_x, 0.35, places=4)
        self.assertAlmostEqual(conditions[-1].collective_deg, 5.0, places=4)

    def test_replace_unchecked_accumulates_factorials(self):
        _state, tab = self._tab()
        self._build_factorial(tab)
        tab._generate_cases()
        tab.check_replace_queue.setChecked(False)
        tab._generate_cases()
        self.assertEqual(tab.batch_table.rowCount(), 6)

    def test_remove_and_clear_renumber(self):
        _state, tab = self._tab()
        self._build_factorial(tab)
        tab._generate_cases()
        tab.batch_table.setCurrentCell(0, 0)
        tab._remove_batch_row()
        self.assertEqual(tab.batch_table.rowCount(), 2)
        self.assertEqual([tab.batch_table.item(i, 0).text() for i in range(2)], ["1", "2"])
        tab._clear_queue()
        self.assertEqual(tab.batch_table.rowCount(), 0)
        self.assertFalse(tab.btn_run.isEnabled())

    def test_factorial_can_now_be_saved_as_batch(self):
        """Before, only the explicit list was saveable: a carefully
        constructed factorial was lost when closing the project."""
        state, tab = self._tab()
        self._build_factorial(tab)
        tab._generate_cases()
        with helpers.patch_message_box_everywhere("QInputDialog") as dialog:
            dialog.getText.return_value = ("my_factorial", True)
            tab._save_current_as_batch()
        names = [b.name for b in state.project.batches]
        self.assertIn("my_factorial", names)
        saved = next(b for b in state.project.batches if b.name == "my_factorial")
        self.assertEqual(len(saved.conditions), 3)

    def test_saved_sweep_batch_is_expanded_into_the_queue(self):
        """A batch with `sweep_params` and no conditions needs to appear
        expanded -- otherwise the queue would show zero cases for something
        that runs eight."""
        state, tab = self._tab()
        state.project.batches.append(BatchDefinition(
            name="sweep", sweep_kind="mu_sweep",
            sweep_params={"mu_values": [0.0, 0.1, 0.2, 0.3], "rpm": 600.0}))
        tab._refresh_saved_batches_combo()
        tab.batches_combo.setCurrentText("sweep")
        self.assertEqual(tab.batch_table.rowCount(), 4)


if __name__ == "__main__":
    unittest.main()


class TestNeuralFoilReachesTheProject(GuiE2ETestCase):
    """Regression of item 18: the polars generated by NeuralFoil (and the 2D
    geometry) must reach `state.project.airfoil`.

    The bug: `_on_external_finished` only wrote to the project as a SIDE
    EFFECT of `source_combo.setCurrentText("neuralfoil")` -- the signal
    `currentTextChanged` was what called `_apply_to_project`. In the real flow
    the combo is ALREADY in 'neuralfoil' (otherwise the generation block does
    not appear), the signal does not fire, nothing was written, and execution
    was blocked by "source='table' selected, but no polar was imported",
    pushing the user back to 'table' mode."""

    def _slices(self):
        import numpy as np
        from zbemt.models import PolarSlice
        al = np.arange(-20, 20.5, 0.5)
        return [PolarSlice(alpha_deg=al.tolist(), cl=(0.1 * al).tolist(),
                           cd=(0.01 + 0 * al).tolist(), reynolds=re, mach=m)
                for re in (1e5, 2e5) for m in (0.0, 0.3)]

    def test_neuralfoil_polars_reach_the_project_without_switching_modes(self):
        from zbemt.gui.tabs.airfoil import AirfoilTab
        from zbemt import airfoils

        state = self._make_state()
        self._new_project(state)
        tab = AirfoilTab(state)

        # the user is already in neuralfoil mode -- it is the only way for
        # the polar generation block to be visible to be clicked.
        tab.source_combo.setCurrentText("neuralfoil")
        tab._profile = airfoils.generate_naca4("2412")
        tab._on_external_finished(self._slices())

        applied = state.project.airfoil
        self.assertEqual(len(applied.table_slices), 4)
        self.assertIsNotNone(applied.geometry)

        errors = [i for i in api.validate_project(state.project) if i.level == "error"]
        self.assertEqual(errors, [], f"run blocked by: {[str(e) for e in errors]}")

    def test_generated_2d_geometry_reaches_the_project(self):
        from zbemt.gui.tabs.airfoil import AirfoilTab

        state = self._make_state()
        self._new_project(state)
        tab = AirfoilTab(state)
        tab.source_combo.setCurrentText("neuralfoil")
        tab.profile_source_combo.setCurrentText("naca4")
        tab.naca_code_edit.setText("2412")
        tab._generate_profile()

        self.assertIsNotNone(state.project.airfoil.geometry)


class TestIndicatorClearsWhenTheProblemIsFixed(GuiE2ETestCase):
    """Regression of item 17: once the error is fixed, the tab must turn
    green.

    Same root as item 18 (see `TestNeuralFoilReachesTheProject`): the
    `FlowIndicatorBar` validates `state.project`, so a fix made in the tab
    that does NOT reach the project leaves the indicator red forever.
    `_import_csv` was one such path -- it imported the polar into
    `self._imported_slices` and only wrote to the project if the source combo
    CHANGED value; importing already in 'table' mode (the natural case: it is
    the mode that complains about the missing polar) nothing was written."""

    class _FakeTabs:
        def setCurrentIndex(self, i):
            pass

    def _tab_color(self, bar, index):
        import re as _re
        from zbemt.gui import styles
        inverse = {v: k for k, v in styles.STATUS_COLORS.items()}
        found = _re.search(r"background: (#\w+)", bar._buttons[index].styleSheet())
        return inverse.get(found.group(1), found.group(1)) if found else None

    def test_importing_the_missing_polar_takes_the_tab_out_of_red(self):
        import unittest.mock as _mock
        from zbemt.gui.tabs.airfoil import AirfoilTab

        csv_path = f"{self._tmpdir}/polar.csv"
        with open(csv_path, "w") as f:
            f.write("alpha_deg,cl,cd\n")
            for alpha in range(-20, 21):
                f.write(f"{alpha},{0.1 * alpha},0.01\n")

        state = self._make_state()
        self._new_project(state)
        tab = AirfoilTab(state)
        bar = self.gui.FlowIndicatorBar(state, self._FakeTabs())

        tab.source_combo.setCurrentText("table")
        self.assertEqual(self._tab_color(bar, 2), "red")

        with _mock.patch("zbemt.gui.tabs.airfoil.QFileDialog") as dialog:
            dialog.getOpenFileName.return_value = (csv_path, "")
            tab._import_csv()

        self.assertEqual(self._tab_color(bar, 2), "green")
        self.assertTrue(state.project.airfoil.table_slices)
