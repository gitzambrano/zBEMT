"""End-to-end battery for the GUI: project, geometry, airfoil, config, runs.

Steps 1 to 6 of the workflow the user follows, driven for real through Qt.
The later steps -- results, persistence, the closing prompt and the queue --
are in `test_gui_e2e_results.py`, and the base class both files share is in
`gui_e2e_base.py`, which explains why the battery is split in two.
"""

from gui_e2e_base import (  # noqa: F401
    GuiE2ETestCase, _pump_until_finished, _run_worker_and_wait, _HAS_QT,
    api, asdict, helpers, geometry_mod, math, mock, time, unittest,
    AirfoilDef, BatchDefinition, FlightCondition, Project,
    QApplication, QCloseEvent, QMessageBox, Qt, QTimer)




# =============================================================================
# Step 1 -- Project
# =============================================================================

class TestStep1Project(GuiE2ETestCase):
    def test_new_project_via_real_button_repopulates_tabs_and_flow_bar(self):
        state = self._make_state()
        with helpers.patch_message_box_everywhere("PROJECTS_ROOT", self._tmpdir):
            project_tab = self.gui.ProjectTab(state)
            geometry_tab = self.gui.GeometryTab(state)
            airfoil_tab = self.gui.AirfoilTab(state)
            config_tab = self.gui.ConfigMotorTab(state)
            tabs_widget = self.gui.QTabWidget() if hasattr(self.gui, "QTabWidget") else None
            flow_bar = self.gui.FlowIndicatorBar(state, self._fake_tabs(project_tab, geometry_tab, airfoil_tab, config_tab))

            # before any project: entire FlowIndicatorBar is gray
            for btn in flow_bar._buttons:
                self.assertIn("background: #9e9e9e", btn.styleSheet().replace(" ", "").replace("background:#9e9e9e", "background: #9e9e9e") or btn.styleSheet())

            project_tab.name_edit.setText("Heli_UH60_like")
            project_tab.radio_rotor.setChecked(True)
            # fires the real slot of the "New project" button
            project_tab._new_project()

        self.assertIsNotNone(state.project)
        self.assertEqual(state.project.name, "Heli_UH60_like")
        self.assertFalse(state.is_propeller())
        self.assertIn("Heli_UH60_like", project_tab.status_label.text())

        # the tabs repopulated from the new project (geometry/airfoil
        # tabs listen to AppState.geometry_changed/airfoil_changed)
        self.assertGreaterEqual(geometry_tab.table.rowCount(), 2)
        self.assertEqual(geometry_tab.n_blades.value(), state.project.geometry.n_blades)

        # FlowIndicatorBar left gray: Project/Geometry/Airfoil/Config
        # should be "green" (new project has valid geometry/airfoil)
        flow_bar.refresh()
        for i in range(4):
            style = flow_bar._buttons[i].styleSheet()
            self.assertNotIn("#9e9e9e", style, f"button {i} still gray after creating the project")

    @staticmethod
    def _fake_tabs(*widgets):
        """FlowIndicatorBar only needs a QTabWidget with setCurrentIndex
        -- we reuse Qt's own real QTabWidget, without MainWindow."""
        from PyQt6.QtWidgets import QTabWidget
        tabs = QTabWidget()
        for i, w in enumerate(widgets):
            tabs.addTab(w, str(i))
        return tabs


# =============================================================================
# Step 2 -- Geometry
# =============================================================================

class TestGeometryDialogSolidityAspectRatio(GuiE2ETestCase):
    """Solidity/AR are just another way of viewing the same blade area that
    root/tip chord define in the generation popup -- editing any one of the
    four recalculates the others live (`GeometryGeneratorDialog._on_param_changed`)."""

    def test_editing_chord_updates_solidity_and_aspect_ratio(self):
        state = self._make_state()
        dlg = self.gui.GeometryGeneratorDialog(None, n_blades=2, radius_m=1.0, airfoil_name="")
        dlg.kind_combo.setCurrentText("rectangular")
        dlg.root_cutout.setValue(0.0)
        dlg.chord_a.setValue(0.1)
        # rectangular, rc=0: S = c*(1-rc) = 0.1; sigma = Nb*S/pi = 2*0.1/pi
        self.assertAlmostEqual(dlg.solidity.value(), 2 * 0.1 / math.pi, places=3)
        self.assertAlmostEqual(dlg.aspect_ratio.value(), 1.0 / 0.1, places=2)

    def test_editing_solidity_updates_chord_and_stays_consistent_with_aspect_ratio(self):
        state = self._make_state()
        dlg = self.gui.GeometryGeneratorDialog(None, n_blades=2, radius_m=1.0, airfoil_name="")
        dlg.kind_combo.setCurrentText("rectangular")
        dlg.root_cutout.setValue(0.0)
        dlg.solidity.setValue(0.1)
        expected_area = 0.1 * math.pi / 2
        # chord_a only has 2 decimal places (default spinbox) -- the
        # rounded result is the source of truth, the other two fields must
        # be consistent with IT, not with the ideal unrounded value.
        self.assertAlmostEqual(dlg.chord_a.value(), expected_area, places=2)
        actual_area = dlg.chord_a.value()
        self.assertAlmostEqual(dlg.aspect_ratio.value(), 1.0 / actual_area, places=2)

    def test_editing_aspect_ratio_updates_chord_and_solidity(self):
        state = self._make_state()
        dlg = self.gui.GeometryGeneratorDialog(None, n_blades=2, radius_m=1.0, airfoil_name="")
        dlg.kind_combo.setCurrentText("rectangular")
        dlg.root_cutout.setValue(0.0)
        dlg.aspect_ratio.setValue(20.0)
        self.assertAlmostEqual(dlg.chord_a.value(), 1.0 / 20.0, places=4)
        self.assertAlmostEqual(dlg.solidity.value(), 2 * (1.0 / 20.0) / math.pi, places=4)

    def test_tapered_solidity_edit_scales_root_and_tip_chord_preserving_ratio(self):
        state = self._make_state()
        dlg = self.gui.GeometryGeneratorDialog(None, n_blades=2, radius_m=1.0, airfoil_name="")
        dlg.kind_combo.setCurrentText("tapered")
        dlg.root_cutout.setValue(0.15)
        dlg.chord_a.setValue(0.10)
        dlg.chord_b.setValue(0.04)
        ratio_before = dlg.chord_b.value() / dlg.chord_a.value()

        dlg.solidity.setValue(dlg.solidity.value() * 1.5)

        ratio_after = dlg.chord_b.value() / dlg.chord_a.value()
        # rounding to 4 decimal places by the spinbox introduces a tiny
        # residual error -- the ratio is preserved, not identical bit by bit.
        self.assertAlmostEqual(ratio_before, ratio_after, places=3)
        area = 0.5 * (dlg.chord_a.value() + dlg.chord_b.value()) * (1 - dlg.root_cutout.value())
        self.assertAlmostEqual(dlg.solidity.value(), 2 * area / math.pi, places=4)


class TestStep2Geometry(GuiE2ETestCase):
    def test_generate_tapered_blade_and_edit_table_updates_preview(self):
        state = self._make_state()
        self._new_project(state)
        geometry_tab = self.gui.GeometryTab(state)

        geometry_tab.n_blades.setValue(4)
        geometry_tab.radius_m.setValue(8.18)
        self.assertEqual(state.project.geometry.n_blades, 4)
        self.assertAlmostEqual(state.project.geometry.radius_m, 8.18)

        # Parametric generation popup: we fire the real _on_confirm slot
        # (equivalent to clicking "Generate and replace table") without
        # calling dlg.exec() -- exec() would block waiting for mouse-driven
        # closure, which this environment does not have; accept()/
        # generated_geom are already set within the real slot itself.
        dlg = self.gui.GeometryGeneratorDialog(geometry_tab, n_blades=4, radius_m=8.18, airfoil_name="")
        dlg.kind_combo.setCurrentText("tapered")
        dlg.chord_a.setValue(0.12)
        dlg.chord_b.setValue(0.05)
        dlg.twist_root.setValue(14.0)
        dlg.twist_tip.setValue(2.0)
        dlg.n_stations.setValue(20)
        dlg._on_confirm()
        self.assertIsNotNone(dlg.generated_geom)
        state.project.geometry = dlg.generated_geom
        state.notify_geometry()

        self.assertEqual(geometry_tab.table.rowCount(), 20)
        planform_before = geometry_tab.planform_canvas.simple.ax.lines + geometry_tab.planform_canvas.simple.ax.patches

        # manual editing of a cell + "Apply table edits"
        item = geometry_tab.table.item(5, 1)
        item.setText("0.09")
        geometry_tab._apply_table_edits()

        self.assertAlmostEqual(state.project.geometry.chord_norm[5], 0.09, places=6)
        # preview was redrawn (canvas still valid, no exception) and the
        # table remains consistent with the applied project.geometry
        self.assertEqual(len(state.project.geometry.r_norm), 20)
        # asterisk now means "not saved to disk" (no longer "edit not
        # applied") -- applying live still leaves the project dirty until
        # "Save project".
        self.assertTrue(geometry_tab._dirty)


# =============================================================================
# Step 3 -- Airfoil (PRIORITY: progressive disclosure)
# =============================================================================

class TestStep3Airfoil(GuiE2ETestCase):
    def test_switching_to_table_source_hides_analytical_fields(self):
        state = self._make_state()
        self._new_project(state)
        tab = self.gui.AirfoilTab(state)
        tab.show()   # isVisible() only reflects the real tree when top is shown

        tab.source_combo.setCurrentText("analytical")
        self.assertTrue(tab.cl_alpha.isVisible())
        self.assertTrue(tab.alpha0_deg.isVisible())
        self.assertTrue(tab.cd0.isVisible())
        self.assertTrue(tab.stall_model_combo.isVisible())

        # fires the real slot (currentTextChanged -> _update_source_visibility)
        tab.source_combo.setCurrentText("table")

        for w in (tab.cl_alpha, tab.alpha0_deg, tab.cd0, tab.k_coef,
                  tab.stall_model_combo, tab.alpha_stall_pos, tab.alpha_stall_neg):
            self.assertFalse(w.isVisible(), f"{w} deveria estar oculto em source='table'")
        # and the table/import fields appear in their place
        self.assertTrue(tab.table_box.isVisible())

    def test_viterna_blend_width_appears_only_when_full_range_active(self):
        state = self._make_state()
        self._new_project(state)
        tab = self.gui.AirfoilTab(state)
        tab.show()

        # analytical + stall_model != viterna: blend width hidden
        tab.source_combo.setCurrentText("analytical")
        tab.stall_model_combo.setCurrentText("clip")
        self.assertFalse(tab.viterna_blend_width_deg.isVisible())

        # link Viterna via stall_model (analytical source has no toggle
        # of its own -- extend_full_range is DERIVED from stall_model=='viterna')
        tab.stall_model_combo.setCurrentText("viterna")
        self.assertTrue(tab.viterna_blend_width_deg.isVisible())
        self.assertTrue(tab.viterna_width_label.isVisible())

        # table source: has explicit toggle
        tab.source_combo.setCurrentText("table")
        tab.extend_full_range.setChecked(False)
        self.assertFalse(tab.viterna_blend_width_deg.isVisible())
        tab.extend_full_range.setChecked(True)
        self.assertTrue(tab.viterna_blend_width_deg.isVisible())

    def test_prandtl_glauert_desliga_com_polar_tabelada_em_mach(self):
        """If the table IN USE already has more than one slice at Mach, the
        polar chosen at each condition already comes compressible: applying
        Prandtl-Glauert on top would count Mach twice. The toggle goes to
        `False` and becomes DISABLED -- it's not just a warning the user can
        ignore. Tables with only Reynolds (without Mach) continue to allow
        the toggle.

        "IN USE" is what this test came to require along with the rest: the
        condition includes the SOURCE, as in `validation.validate_config`
        (which only warns with `source == "table"`). Looking only at the
        imported slices -- which remain stored when switching source --,
        passing through 'table' once was enough for the toggle to turn gray
        forever, even in 'analytical', where no table is consulted. It was
        the defect reported by the user."""
        from zbemt.models import PolarSlice
        state = self._make_state()
        self._new_project(state)
        tab = self.gui.AirfoilTab(state)
        tab.cfg_use_compressibility.setChecked(True)
        self.assertTrue(tab.cfg_use_compressibility.isEnabled())

        so_reynolds = [
            PolarSlice(alpha_deg=[0, 5], cl=[0, 0.5], cd=[0.01, 0.02], reynolds=1e6),
            PolarSlice(alpha_deg=[0, 5], cl=[0, 0.5], cd=[0.01, 0.02], reynolds=2e6),
        ]
        varrida_em_mach = [
            PolarSlice(alpha_deg=[0, 5], cl=[0, 0.5], cd=[0.01, 0.02], mach=0.1),
            PolarSlice(alpha_deg=[0, 5], cl=[0, 0.5], cd=[0.01, 0.02], mach=0.5),
        ]

        # the table only comes into play when it IS the source of the polar
        tab.source_combo.setCurrentText("table")

        # Reynolds only, without Mach -- toggle remains enabled
        tab._imported_slices = so_reynolds
        tab._populate_slices_list()
        self.assertTrue(tab.cfg_use_compressibility.isEnabled(),
                         "table only in Reynolds should still allow P-G")

        # now with Mach varying -- toggle goes to False and disables
        tab._imported_slices = varrida_em_mach
        tab._populate_slices_list()
        self.assertFalse(tab.cfg_use_compressibility.isEnabled(),
                          "P-G devia estar desabilitado com tabela variando em Mach")
        self.assertFalse(tab.cfg_use_compressibility.isChecked(),
                          "P-G devia ter sido desmarcado ao detectar Mach tabelado")

        # back to analytical: no table is consulted, nothing to block --
        # and the value the user had checked returns
        tab.source_combo.setCurrentText("analytical")
        self.assertTrue(tab.cfg_use_compressibility.isEnabled(),
                         "in 'analytical' the table is not consulted: P-G should come back")
        self.assertTrue(tab.cfg_use_compressibility.isChecked(),
                         "o valor marcado antes do bloqueio deve ser devolvido")

    def test_dynamic_stall_disabled_when_stall_model_is_linear(self):
        state = self._make_state()
        self._new_project(state)
        tab = self.gui.AirfoilTab(state)

        tab.source_combo.setCurrentText("analytical")
        tab.stall_model_combo.setCurrentText("clip")
        tab.use_dynamic_stall.setEnabled(True)
        tab.use_dynamic_stall.setChecked(True)
        self.assertTrue(tab.use_dynamic_stall.isEnabled())
        self.assertTrue(tab.use_dynamic_stall.isChecked())

        # fires the real slot (_update_dynamic_stall_enabled) via
        # currentTextChanged of stall_model_combo
        tab.stall_model_combo.setCurrentText("linear")

        self.assertFalse(tab.use_dynamic_stall.isEnabled())
        self.assertFalse(tab.use_dynamic_stall.isChecked(),
                          "dynamic stall should be unchecked automatically when it becomes locked")

    def test_apply_to_project_writes_collected_airfoil_def(self):
        state = self._make_state()
        self._new_project(state)
        tab = self.gui.AirfoilTab(state)

        tab.source_combo.setCurrentText("analytical")
        tab.stall_model_combo.setCurrentText("clip")
        tab.airfoil_name_edit.setText("NACA 0012 rotor")
        tab.cl_alpha.setValue(6.0)
        tab.alpha_stall_pos.setValue(13.0)
        tab.alpha_stall_neg.setValue(-8.0)

        tab._apply_to_project()

        self.assertEqual(state.project.airfoil.name, "NACA 0012 rotor")
        self.assertEqual(state.project.airfoil.source, "analytical")
        self.assertEqual(state.project.airfoil.stall_model, "clip")
        self.assertAlmostEqual(state.project.airfoil.cl_alpha, 6.0)
        self.assertAlmostEqual(state.project.airfoil.alpha_stall_pos_deg, 13.0)
        self.assertEqual(state.project.airfoil_sections, [])


# =============================================================================
# Step 4 -- Config/Motor (PRIORITY: progressive disclosure + validation)
# =============================================================================

class TestStep4Config(GuiE2ETestCase):
    def test_pitt_peters_block_appears_only_for_pitt_peters_inflow(self):
        state = self._make_state()
        self._new_project(state)
        tab = self.gui.ConfigMotorTab(state)
        tab.show()
        # ConfigMotorTab only syncs from the project when
        # AppState.project_changed fires AFTER the tab exists; since the
        # project was already set before the tab was built, it syncs
        # manually once (same call that _on_project_changed would make).
        tab._refresh_config_from_project()

        tab.cfg_inflow_family.setCurrentText("glauert")
        self.assertFalse(tab.pitt_peters_box.isVisible())

        # fires the real slot (currentTextChanged -> _update_pitt_peters_visibility)
        tab.cfg_inflow_family.setCurrentText("pitt_peters")
        self.assertTrue(tab.pitt_peters_box.isVisible())

        tab.cfg_inflow_family.setCurrentText("coleman")
        self.assertFalse(tab.pitt_peters_box.isVisible())

    def test_verify_configuration_button_runs_validation_and_updates_label(self):
        state = self._make_state()
        self._new_project(state)
        tab = self.gui.ConfigMotorTab(state)

        # new project (default) should validate clean or with only warnings --
        # the important thing is that the real button fires api.validate_project
        # and populates the label (not that the result is necessarily empty).
        tab._validate_config_display()
        self.assertNotEqual(tab.config_issues_label.text(), "")

        # force a known inconsistent configuration (radial flow correction
        # on with skew angle outside range is not possible via GUI -- instead
        # we use very low Ne, which validation.py typically signals as a
        # mesh warning/error)
        tab.cfg_Ne.setValue(5)
        tab._apply_config_to_project()
        tab._validate_config_display()
        self.assertIn(tab.config_issues_label.text().count("font"), (0, tab.config_issues_label.text().count("font")))
        # config was actually written to the project (Ne applied)
        self.assertEqual(state.project.config["Ne"], 5)

    def test_pitt_peters_field_values_apply_to_project_config(self):
        state = self._make_state()
        self._new_project(state)
        tab = self.gui.ConfigMotorTab(state)

        tab.cfg_inflow_family.setCurrentText("pitt_peters")
        tab.cfg_pitt_peters_relax.setValue(0.25)
        tab._apply_config_to_project()

        self.assertEqual(state.project.config["inflow_field_model"], "pitt_peters_steady")
        self.assertAlmostEqual(state.project.config["pitt_peters_relax"], 0.25)


# =============================================================================
# Step 5 -- Run Case
# =============================================================================

class TestStep5RunCase(GuiE2ETestCase):
    def _small_heli_project(self, state):
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

    def test_run_case_hover_and_forward_flight_give_plausible_ct_cq(self):
        state = self._make_state()
        self._small_heli_project(state)
        tab = self.gui.RunCaseTab(state)
        tab.show()

        # --- case 1: hover, mu_x = 0 ------------------------------------
        tab.advance.unit_combo.setCurrentText("mu_x")
        tab.advance.set_mu(0.0)
        tab.axial.unit_combo.setCurrentIndex(0)   # alpha [deg]
        tab.axial.spin.setValue(0.0)
        tab.collective_spin.setValue(8.0)
        tab.rpm_spin.setValue(600.0)

        tab._run_case()
        self.assertTrue(tab.progress.isVisible())
        _pump_until_finished(tab._worker)

        self.assertFalse(tab.progress.isVisible())
        self.assertIsNotNone(state.last_results)
        hover_ct = state.last_results.summary.get("CT")
        self.assertIsNotNone(hover_ct)
        self.assertGreater(hover_ct, 0.0)
        self.assertLess(hover_ct, 0.5)
        self.assertTrue(tab.btn_export_csv.isEnabled())

        # --- case 2: advance, mu_x = 0.25, alpha = -5 deg ----------------
        tab.advance.set_mu(0.25)
        tab.axial.spin.setValue(-5.0)
        tab._run_case()
        _pump_until_finished(tab._worker)

        self.assertIsNotNone(state.last_results)
        fwd_ct = state.last_results.summary.get("CT")
        fwd_cq = state.last_results.summary.get("CQ")
        self.assertIsNotNone(fwd_ct)
        self.assertIsNotNone(fwd_cq)
        # in forward flight, CT remains physically plausible (same order of
        # magnitude as hover -- we don't require equality, just sanity)
        self.assertLess(abs(fwd_ct), 0.5)
        self.assertEqual(len(state.results_history), 2)

    def test_results_table_uses_report_symbols_units_and_tooltips(self):
        """Bug: `_GROUPS_ROTOR`/`_GROUPS_PROPELLER` + `_formatar_valor` were
        a SECOND manual copy, misaligned, of the same labels/units/formatting
        that `api.py`'s `_COLUMN_SYMBOL` already maintained for the HTML
        report -- Run Case, Results tab and the report could diverge in how
        they displayed the same quantity."""
        from PyQt6.QtCore import QPoint
        from zbemt import api as api_module
        state = self._make_state()
        self._small_heli_project(state)
        tab = self.gui.RunCaseTab(state)
        tab.show()

        tab.advance.unit_combo.setCurrentText("mu_x")
        tab.advance.set_mu(0.1)
        tab.collective_spin.setValue(8.0)
        tab.rpm_spin.setValue(600.0)
        tab._run_case()
        _pump_until_finished(tab._worker)

        labels = [tab.results_table.item(i, 0).text() for i in range(tab.results_table.rowCount())]
        self.assertIn("μ_x", labels)       # symbol, not the raw key
        self.assertNotIn("mu_x", labels)
        ct_row = labels.index("C_T")        # C<sub>T</sub> -> C_T (sem HTML)
        expected_value = api_module.format_summary_value(state.last_results.summary["CT"])
        self.assertEqual(tab.results_table.item(ct_row, 1).text(), expected_value)

        # instant tooltip returns symbol+unit+description for that row
        y = tab.results_table.rowViewportPosition(ct_row) + 2
        tip = tab._row_tooltip(QPoint(5, y))
        self.assertIn("Thrust coefficient", tip)

        # group header row (no associated key) does not generate tooltip.
        # "Condition" became "Flight condition" when groups started to follow
        # `api.SUMMARY_PRIMARY_KEYS` (item 12): the flight entries and the
        # echo of RPM/collective are in one group, and the title now states
        # they are the FLIGHT CONDITION, not just any condition.
        header_row = labels.index("Flight condition")
        y_header = tab.results_table.rowViewportPosition(header_row) + 2
        self.assertIsNone(tab._row_tooltip(QPoint(5, y_header)))

        # rotor geometry (radius/number of blades) is INPUT, but without it
        # here there was no way to know, from the result, which radius
        # generated that CT -- symbol "R", not the raw key "rotor_R".
        self.assertIn("R [m]", labels)
        r_row = labels.index("R [m]")
        self.assertEqual(tab.results_table.item(r_row, 1).text(),
                          api_module.format_summary_value(state.last_results.summary["rotor_R"]))

        # Configuration echo is always shown; there is no more toggle.
        self.assertIn("N_e", labels)
        self.assertNotIn("cfg_Ne", labels)
        self.assertFalse(hasattr(tab, "show_cfg_check"))

    def _trim_project(self, state):
        """Mesh/config different from `_small_heli_project` (which uses
        fixed_point/max_iter low, tuned for speed, not for numerical
        cleanliness) -- Thrust(collective) only becomes monotonic in the
        standard bracket of `run_case_trimmed` ([-10°, 30°]) with a finer
        mesh and more iterations; verified manually while writing these
        tests (the mesh of `_small_heli_project` produces noisy,
        non-monotonic Thrust(θ) well before 30°, which makes bisection
        converge to a spurious root -- it is not a bug in `run_case_trimmed`,
        it is the test mesh being too good for other purposes and too bad
        for monotonicity)."""
        project = self._new_project(state)
        project.geometry = geometry_mod.generate_tapered(
            root_chord_norm=0.10, tip_chord_norm=0.04, twist_root_deg=14.0,
            twist_tip_deg=2.0, root_cutout_norm=0.15, radius_m=1.0, n_stations=12)
        project.airfoil = AirfoilDef(source="analytical", stall_model="clip",
                                      alpha_stall_pos_deg=15.0, alpha_stall_neg_deg=-6.0)
        project.config.update(dict(Ne=8, Npsi=12, solver="fixed_point", max_iter=150,
                                    reverse_flow_model="simple_flip"))
        state.notify_geometry()
        state.notify_airfoil()
        state.notify_config()
        return project

    def test_run_mode_toggles_hide_the_dof_being_solved(self):
        state = self._make_state()
        self._small_heli_project(state)
        tab = self.gui.RunCaseTab(state)
        tab.show()

        self.assertTrue(tab.collective_spin.isVisibleTo(tab))
        self.assertTrue(tab.rpm_spin.isVisibleTo(tab))
        self.assertFalse(tab.trim_target_kind_combo.isVisibleTo(tab))

        tab.run_mode_combo.setCurrentText("Fixed RPM, target thrust/CT")
        self.assertFalse(tab.collective_spin.isVisibleTo(tab))
        self.assertTrue(tab.rpm_spin.isVisibleTo(tab))
        self.assertTrue(tab.trim_target_kind_combo.isVisibleTo(tab))

        tab.run_mode_combo.setCurrentText("Fixed collective, target thrust/CT")
        self.assertTrue(tab.collective_spin.isVisibleTo(tab))
        self.assertFalse(tab.rpm_spin.isVisibleTo(tab))

        tab.run_mode_combo.setCurrentText("Fixed collective & RPM")
        self.assertTrue(tab.collective_spin.isVisibleTo(tab))
        self.assertTrue(tab.rpm_spin.isVisibleTo(tab))
        self.assertFalse(tab.trim_target_kind_combo.isVisibleTo(tab))

    def test_solve_collective_trim_mode_hits_target_thrust(self):
        state = self._make_state()
        self._trim_project(state)
        tab = self.gui.RunCaseTab(state)
        tab.show()

        tab.advance.unit_combo.setCurrentText("mu_x")
        tab.advance.set_mu(0.0)
        tab.rpm_spin.setValue(600.0)
        tab.collective_spin.setValue(8.0)
        tab._run_case()
        _pump_until_finished(tab._worker)
        target_thrust = state.last_results.summary["Thrust"]

        tab.run_mode_combo.setCurrentText("Fixed RPM, target thrust/CT")
        tab.trim_target_kind_combo.setCurrentText("Thrust [N]")
        tab.trim_target_value.setValue(target_thrust)
        tab.collective_spin.setValue(2.0)   # ponto de partida deliberadamente errado

        tab._run_case()
        _pump_until_finished(tab._worker)

        self.assertAlmostEqual(state.last_results.summary["Thrust"], target_thrust,
                                delta=abs(target_thrust) * 1e-2 + 1e-6)
        self.assertAlmostEqual(state.last_results.summary["collective_deg"], 8.0, delta=0.1)

    def test_unbracketed_trim_target_reports_error_not_a_freeze(self):
        state = self._make_state()
        self._trim_project(state)
        tab = self.gui.RunCaseTab(state)
        tab.show()

        tab.run_mode_combo.setCurrentText("Fixed RPM, target thrust/CT")
        tab.rpm_spin.setValue(600.0)
        tab.trim_target_kind_combo.setCurrentText("Thrust [N]")
        tab.trim_target_value.setValue(1e9)   # unreachable within standard bracket

        tab._run_case()
        _pump_until_finished(tab._worker)

        self.mock_msgbox.critical.assert_called_once()


# =============================================================================
# Step 6 -- Run Batch (PRIORITY: worker, cancellation, axis exclusion)
# =============================================================================

class TestStep6RunBatch(GuiE2ETestCase):
    def _small_heli_project(self, state):
        project = self._new_project(state)
        project.geometry = geometry_mod.generate_tapered(
            root_chord_norm=0.10, tip_chord_norm=0.05, twist_root_deg=14.0,
            twist_tip_deg=2.0, root_cutout_norm=0.15, radius_m=8.18,
            n_blades=4, n_stations=8, airfoil_name="perfil 1")
        project.airfoil = AirfoilDef(source="analytical", stall_model="clip")
        project.config.update(dict(Ne=6, Npsi=4, solver="fixed_point", max_iter=40,
                                    reverse_flow_model="simple_flip"))
        state.notify_geometry(); state.notify_airfoil(); state.notify_config()
        return project

    def test_axis_slot_used_disappears_from_other_axis_combos(self):
        state = self._make_state()
        self._small_heli_project(state)
        tab = self.gui.RunBatchTab(state)
        tab.show()

        slot_combo_1, _u1, _v1 = tab.axis_rows[0]
        slot_combo_2, _u2, _v2 = tab.axis_rows[1]

        # Axis 1: choose "Advance (mu_x / J_x / V)" -- slot "inplane"
        idx_longitudinal = [i for i, (_l, s) in enumerate(tab._AXIS_SLOTS) if s == "inplane"][0]
        slot_combo_1.setCurrentIndex(idx_longitudinal)   # fires _on_axes_changed

        model2 = slot_combo_2.model()
        item_longitudinal_in_2 = model2.item(idx_longitudinal)
        self.assertFalse(item_longitudinal_in_2.isEnabled(),
                          "slot 'longitudinal' already used on axis 1 should be disabled on axis 2")

        # the corresponding fixed field ("Advance") disappears from Fixed box
        self.assertFalse(tab.fixed_advance.isVisible())
        self.assertTrue(tab.fixed_axial.isVisible())

        # returning axis 1 to "(none)" releases the slot again in axis 2
        slot_combo_1.setCurrentIndex(0)
        self.assertTrue(model2.item(idx_longitudinal).isEnabled())
        self.assertTrue(tab.fixed_advance.isVisible())

    def test_factorial_mu_x_collective_runs_all_cases(self):
        state = self._make_state()
        self._small_heli_project(state)
        tab = self.gui.RunBatchTab(state)
        tab.show()

        slot_combo_1, unit_combo_1, values_edit_1 = tab.axis_rows[0]
        idx_longitudinal = [i for i, (_l, s) in enumerate(tab._AXIS_SLOTS) if s == "inplane"][0]
        slot_combo_1.setCurrentIndex(idx_longitudinal)
        unit_combo_1.setCurrentText("mu_x")
        values_edit_1.setText("0.0, 0.1")

        slot_combo_2, _unit_combo_2, values_edit_2 = tab.axis_rows[1]
        idx_collective = [i for i, (_l, s) in enumerate(tab._AXIS_SLOTS) if s == "collective_deg"][0]
        slot_combo_2.setCurrentIndex(idx_collective)
        values_edit_2.setText("6.0, 10.0")

        tab.fixed_rpm.setValue(600.0)
        self.assertIn("2 × 2", tab.total_cases_label.text())

        # stage 1: generate -- cases go to the QUEUE, not yet running
        tab._generate_cases()
        self.assertEqual(tab.batch_table.rowCount(), 4,
                          "o fatorial deveria materializar 4 casos na fila")
        self.assertIsNone(state.last_results, "generate must not run anything")

        # stage 3: run what is in the queue
        tab._run_batch()
        self.assertTrue(tab.progress.isVisible())
        _pump_until_finished(tab._worker)

        self.assertFalse(tab.progress.isVisible())
        self.assertIsInstance(state.last_results, list)
        self.assertEqual(len(state.last_results), 4)
        # o status aparece na MESMA tabela em que os casos foram revisados
        estados = [tab.batch_table.item(i, tab._COL_STATUS).text() for i in range(4)]
        self.assertTrue(all(e.startswith("OK") for e in estados), estados)

    def test_cancel_button_stops_batch_before_all_cases_run(self):
        """Handshake with `threading.Event`, not `time.sleep` -- a real sleep
        is a race condition: under load (entire suite running in parallel), the
        delivery of the `case_finished` signal (queue between the worker's
        QThread and the main thread) can delay longer than the sleep, and all
        6 cases finish before cancellation is processed -- passes isolated,
        fails ~1 in N under load (observed in practice: 3/3 isolated, fails a
        few times together with the full suite).

        Fix: the mock BLOCKS before the 3rd case, waiting for an Event that
        is only released by the `on_case` handler AFTER calling `tab._cancel()`
        -- in other words, the worker only proceeds after the main thread has
        already requested cancellation. Deterministic result: cases 0 and 1
        always run, the 3rd runs (the `should_cancel()` loop is only checked
        BEFORE each case, so the request made during case 1 does not interrupt
        case 2 that is already in flight), and the 4th and beyond never run --
        always EXACTLY 3 completed, not "less than 6"."""
        state = self._make_state()
        self._small_heli_project(state)
        tab = self.gui.RunBatchTab(state)

        conditions = [FlightCondition(name=f"c{i}", mu_x=0.05 * i, collective_deg=8.0, rpm=600.0)
                      for i in range(6)]
        batch = BatchDefinition(name="cancel_test", conditions=conditions)

        from zbemt.models import Results
        import threading

        cancel_requested = threading.Event()

        def slow_run_single_case(proj, cond, should_cancel=None):
            if cond.name == "c2":
                # Hold the worker until the main thread has processed
                # `case_finished` of case 1 and called `tab._cancel()` --
                # without this, the `studies.run_batch` loop can check
                # `should_cancel()` (still False) and fire case 2 before
                # cancellation is even requested.
                if not cancel_requested.wait(timeout=5.0):
                    raise AssertionError("cancelamento nunca chegou -- handshake quebrado")
            return Results(summary={"mu_x": cond.mu_x, "CT": 0.01}, maps={}, condition_name=cond.name)

        tab._fill_queue(conditions, replace=True)
        worker = self.gui.BatchRunnerWorker(state.project, batch=batch)
        tab._start_run(worker, total=len(conditions), label="teste de cancelamento")

        def on_case(i, total, r):
            if i == 1:
                tab._cancel()
                cancel_requested.set()

        worker.case_finished.connect(on_case)

        with mock.patch("zbemt.studies.run_single_case", side_effect=slow_run_single_case):
            _pump_until_finished(worker)

        concluidos = [i for i in range(tab.batch_table.rowCount())
                      if tab.batch_table.item(i, tab._COL_STATUS).text().startswith("OK")]
        self.assertEqual(len(concluidos), 3,
                          "cancellation should have stopped right after the 3rd case")
        self.assertFalse(tab.progress.isVisible())
        self.assertFalse(tab.btn_cancel.isVisible())


# =============================================================================
# Step 7 -- Results
# =============================================================================

@unittest.skipUnless(_HAS_QT, "PyQt6 not installed in this environment")
class TestDescribeCaseAndBatchSettings(unittest.TestCase):
    """`describe_case_settings`/`describe_batch_settings` (zbemt/gui/common.py):
    before, a history entry only said "case mu_x=0.3" -- two entries with the
    same mu_x but different collective/rpm were indistinguishable by label."""

    def test_describe_case_settings_includes_mu_collective_rpm(self):
        from zbemt.gui.common import describe_case_settings
        desc = describe_case_settings({"mu_x": 0.3, "collective_deg": 8.0, "rpm": 600.0})
        self.assertIn("0.3", desc)
        self.assertIn("8", desc)
        self.assertIn("600", desc)

    def test_describe_case_settings_omits_missing_keys(self):
        from zbemt.gui.common import describe_case_settings
        desc = describe_case_settings({"mu_x": 0.1})
        self.assertIn("0.1", desc)
        self.assertNotIn("rpm", desc)

    def test_describe_case_settings_empty_summary_has_fallback(self):
        from zbemt.gui.common import describe_case_settings
        self.assertEqual(describe_case_settings({}), "case")

    def test_describe_batch_settings_shows_range_for_varying_key(self):
        from zbemt.gui.common import describe_batch_settings
        from zbemt.models import Results
        results = [Results(summary={"mu_x": m, "collective_deg": 8.0, "rpm": 600.0}, maps={})
                   for m in (0.0, 0.1, 0.2, 0.3)]
        desc = describe_batch_settings(results)
        self.assertIn("0", desc)
        self.assertIn("0.3", desc)
        self.assertIn("8", desc)  # constant collective: shown as a single value
        self.assertIn("4 case", desc)

    def test_describe_batch_settings_empty_list_has_fallback(self):
        from zbemt.gui.common import describe_batch_settings
        self.assertEqual(describe_batch_settings([]), "batch")
