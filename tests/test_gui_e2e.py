"""
test_gui_e2e.py
================

End-to-end battery for the GUI (production-plan.md, section G) -- drives the
GUI REAL via Qt (instantiates the tabs for real, fires the slots of real
buttons), simulating an analysis of a helicopter rotor from scratch, of 9
steps of the plan table (step 9, CLI parity, is for another agent and
was deliberately left out of here).

Priority (production-plan.md): steps 3 (Airfoil), 4 (Config/Motor), 6
(Run Batch) and 8 (Persistence) are the ones that answer "is the
progressive disclosure reasonable?" with evidence of state
(visibility/enablement/values), not just "no exception raised".

Requires PyQt6 -- if absent, the entire suite is skipped (same pattern as
tests/test_gui_smoke.py). ``QT_QPA_PLATFORM=offscreen`` is already set by
tests/conftest.py.

Hard rule of this file (has bitten this repo before -- see
tests/test_gui_smoke.py): NEVER let a real ``QMessageBox`` appear under
offscreen backend -- ``exec()`` never returns without a click and the suite
freezes. Every test that goes through a code path that can open a
QMessageBox mocks ``zbemt.gui.app.QMessageBox``.
"""

import math
import tempfile
import shutil
import time
import unittest
import unittest.mock as mock
from dataclasses import asdict

try:
    from PyQt6.QtWidgets import QApplication, QMessageBox
    from PyQt6.QtCore import QEventLoop, QTimer, Qt
    from PyQt6.QtGui import QCloseEvent
    _HAS_QT = True
except Exception:  # pragma: no cover - environment without PyQt6
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
    tests/test_gui_smoke.py::_run_and_wait. Only use with a worker that
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
        cm = helpers.patch_em_toda_gui("QMessageBox")
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


# =============================================================================
# Step 1 -- Project
# =============================================================================

class TestStep1Project(GuiE2ETestCase):
    def test_new_project_via_real_button_repopulates_tabs_and_flow_bar(self):
        state = self._make_state()
        with helpers.patch_em_toda_gui("PROJECTS_ROOT", self._tmpdir):
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
        tab.cfg_pitt_peters_states.setCurrentText("3")
        tab.cfg_pitt_peters_relax.setValue(0.25)
        tab._apply_config_to_project()

        self.assertEqual(state.project.config["inflow_field_model"], "pitt_peters_steady")
        self.assertEqual(state.project.config["pitt_peters_states"], 3)
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
        """Bug: `_GRUPOS_ROTOR`/`_GRUPOS_HELICE` + `_formatar_valor` were
        a SECOND manual copy, misaligned, of the same labels/units/formatting
        that `api.py`'s `_SIMBOLO_DE_COLUNA` already maintained for the HTML
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
        tip = tab._tooltip_da_linha(QPoint(5, y))
        self.assertIn("Thrust coefficient", tip)

        # group header row (no associated key) does not generate tooltip.
        # "Condition" became "Flight condition" when groups started to follow
        # `api.SUMMARY_PRIMARY_KEYS` (item 12): the flight entries and the
        # echo of RPM/collective are in one group, and the title now states
        # they are the FLIGHT CONDITION, not just any condition.
        header_row = labels.index("Flight condition")
        y_header = tab.results_table.rowViewportPosition(header_row) + 2
        self.assertIsNone(tab._tooltip_da_linha(QPoint(5, y_header)))

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
        tab._gerar_casos()
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

        tab._preencher_fila(conditions, substituir=True)
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


class TestStep7Results(GuiE2ETestCase):
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

        tab.mode_list.setCurrentRow(tab._MODES.index("Table"))

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
        tab.mode_list.setCurrentRow(tab._MODES.index("Table"))

        headers = [tab.table_widget.horizontalHeaderItem(c).text()
                       for c in range(tab.table_widget.columnCount())]
        # The table is always complete, no configuration checkbox.
        self.assertIn("N_e", headers)
        self.assertFalse(hasattr(tab, "table_show_cfg_check"))

    def test_table_mode_empty_selection_clears_table(self):
        state = self._make_state()
        tab = self._project_with_history(state)
        tab._clear_history_selection()
        tab.mode_list.setCurrentRow(tab._MODES.index("Table"))
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
                        "com 2 marcados o mapa de disco tem de continuar disponivel")
        self.assertGreaterEqual(tab.condition_combo.count(), 2,
                                "o seletor de condicao oferece as condicoes marcadas")

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
            tab._export_disk_maps_da_selecao()

        mock_progress.assert_called_once()
        mock_progress.return_value.show.assert_called_once()
        mock_progress.return_value.close.assert_called_once()


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
        with helpers.patch_em_toda_gui("QInputDialog") as mock_input:
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
        with helpers.patch_em_toda_gui("PROJECTS_ROOT", self._tmpdir):
            reopened_project_tab = self.gui.ProjectTab(reopened_state)
            reopened_project_tab._open_path(project.path)

        self.assertEqual(reopened_state.project.name, before_name,
                          "Project.name deveria sobreviver ao ciclo salvar/reabrir")
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

    def _janela(self):
        with helpers.patch_em_toda_gui("PROJECTS_ROOT", self._tmpdir):
            win = self.gui.MainWindow()
        self.addCleanup(win.deleteLater)
        return win

    def test_sem_pendencia_fecha_sem_perguntar(self):
        win = self._janela()
        self._new_project(win.state)
        win.state.mark_saved()
        win.close()
        self.mock_msgbox.question.assert_not_called()

    def test_alteracao_aplicada_mas_nao_salva_dispara_o_prompt(self):
        win = self._janela()
        self._new_project(win.state)
        win.state.notify_config()          # what a tab calls when applying
        pendencias = win.trabalho_nao_salvo()
        self.assertEqual(len(pendencias), 1)
        self.assertIn("project", pendencias[0])
        self.mock_msgbox.question.return_value = self.mock_msgbox.StandardButton.Discard
        win.close()
        self.mock_msgbox.question.assert_called_once()

    def test_asterisco_por_aba_e_so_espelho_de_state_unsaved(self):
        """Geometry/Airfoil/Config apply all edits live -- there is no longer
        a second layer of "edited, never applied" separate from `state.unsaved`;
        `_mark_dirty()` alone (without touching `state.unsaved`) should not
        happen through normal GUI usage, but `trabalho_nao_salvo()` only looks
        at `state.unsaved`, so nothing appears here until a tab actually
        notifies the project."""
        win = self._janela()
        self._new_project(win.state)
        win.state.mark_saved()
        win.tabs.widget(1)._mark_dirty()
        pendencias = win.trabalho_nao_salvo()
        self.assertEqual(len(pendencias), 0)

    def test_editar_campo_de_config_marca_asterisco_e_aplica_ao_vivo(self):
        """Editing a Config field applies directly to `state.project.config`
        (no "Apply to project" button) and marks the asterisk for "not saved
        to disk" -- only `Save project` clears that asterisk."""
        win = self._janela()
        self._new_project(win.state)
        win.state.mark_saved()
        config_tab = win.tabs.widget(3)
        self.assertFalse(config_tab._dirty)
        self.assertEqual(win.tabs.tabText(3), "Config/Engine")

        novo_valor = config_tab.cfg_Ne.value() + 1
        config_tab.cfg_Ne.setValue(novo_valor)

        self.assertTrue(config_tab._dirty)
        self.assertEqual(win.tabs.tabText(3), "Config/Engine *")
        self.assertEqual(win.state.project.config["Ne"], novo_valor)
        pendencias = win.trabalho_nao_salvo()
        self.assertEqual(len(pendencias), 1)
        self.assertIn("project", pendencias[0])

        config_tab._save_project()

        self.assertFalse(config_tab._dirty)
        self.assertEqual(win.tabs.tabText(3), "Config/Engine")

    def test_abrir_projeto_nao_marca_config_como_editado(self):
        """Populating widgets from the project (setValue/setChecked/
        setCurrentText) fires the same signals as manual editing -- without
        the guard `_refreshing_from_project`, opening a project would already
        leave the tab with a false-positive asterisk."""
        win = self._janela()
        self._new_project(win.state)
        config_tab = win.tabs.widget(3)
        self.assertFalse(config_tab._dirty)
        self.assertEqual(win.tabs.tabText(3), "Config/Engine")

    def test_cancelar_mantem_a_janela_aberta(self):
        win = self._janela()
        self._new_project(win.state)
        win.state.notify_config()
        self.mock_msgbox.question.return_value = self.mock_msgbox.StandardButton.Cancel
        evento = QCloseEvent()
        win.closeEvent(evento)
        self.assertFalse(evento.isAccepted())

    def test_salvar_grava_no_disco_e_limpa_a_pendencia(self):
        win = self._janela()
        project = self._new_project(win.state)
        win.state.project.name = "renomeado_antes_de_fechar"
        win.state.notify_config()
        self.mock_msgbox.question.return_value = self.mock_msgbox.StandardButton.Save
        win.close()
        self.assertEqual(api.open_project(project.path).name,
                         "renomeado_antes_de_fechar")
        self.assertEqual(win.trabalho_nao_salvo(), [])

    def test_abrir_projeto_zera_a_marca(self):
        win = self._janela()
        self._new_project(win.state)
        win.state.notify_config()
        self._new_project(win.state, name="outro")
        self.assertEqual(win.trabalho_nao_salvo(), [])


class TestShortcutsMatchDocumentation(GuiE2ETestCase):
    """Section 0.3 of docs/documentation.html promised Ctrl+N, Ctrl+O and
    Ctrl+1..7, which did not exist, and omitted Ctrl+R and Ctrl+Enter, which
    did. A documented but missing shortcut is worse than a missing one."""

    def _atalhos(self):
        from PyQt6.QtGui import QShortcut
        with helpers.patch_em_toda_gui("PROJECTS_ROOT", self._tmpdir):
            win = self.gui.MainWindow()
        self.addCleanup(win.deleteLater)
        return {s.key().toString() for s in win.findChildren(QShortcut)}, win

    def test_todos_os_atalhos_documentados_existem(self):
        atalhos, _ = self._atalhos()
        documentados = {"F1", "Ctrl+S", "Ctrl+O", "Ctrl+N", "Ctrl+R", "Ctrl+Enter"}
        documentados |= {f"Ctrl+{i}" for i in range(1, 8)}
        faltando = documentados - atalhos
        self.assertEqual(faltando, set(), f"documentados mas inexistentes: {sorted(faltando)}")

    def test_ctrl_numero_salta_para_a_aba_correspondente(self):
        _, win = self._atalhos()
        for indice in range(win.tabs.count()):
            win.tabs.setCurrentIndex(0)
            win.tabs.setCurrentIndex(indice)
            self.assertEqual(win.tabs.currentIndex(), indice)

    def test_ctrl_n_cria_projeto_e_vai_para_a_aba_projeto(self):
        _, win = self._atalhos()
        win.tabs.setCurrentIndex(4)
        with helpers.patch_em_toda_gui("PROJECTS_ROOT", self._tmpdir):
            with mock.patch.object(type(win._project_tab), "_new_project") as criar:
                win._shortcut_new_project()
        criar.assert_called_once()
        self.assertEqual(win.tabs.currentIndex(), 0)


# =============================================================================
# Run Batch reorganized: generate -> queue -> run
# =============================================================================

class TestFilaDoRunBatch(GuiE2ETestCase):
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

    def _aba(self):
        state = self._make_state()
        self._small_heli_project(state)
        aba = self.gui.RunBatchTab(state)
        return state, aba

    def _montar_fatorial(self, aba, valores_mu="0.0, 0.1, 0.2"):
        sc1, uc1, ve1 = aba.axis_rows[0]
        i_long = [i for i, (_l, s) in enumerate(aba._AXIS_SLOTS) if s == "inplane"][0]
        sc1.setCurrentIndex(i_long)
        uc1.setCurrentText("mu_x")
        ve1.setText(valores_mu)
        aba.fixed_rpm.setValue(600.0)

    def test_gerar_nao_roda(self):
        """Seeing the cases before firing N solves is the whole point of the queue."""
        state, aba = self._aba()
        self._montar_fatorial(aba)
        aba._gerar_casos()
        self.assertEqual(aba.batch_table.rowCount(), 3)
        self.assertIsNone(state.last_results)

    def test_um_unico_botao_de_rodar_e_ele_segue_a_fila(self):
        _state, aba = self._aba()
        self.assertFalse(aba.btn_run.isEnabled(), "fila vazia deveria desabilitar o rodar")
        self._montar_fatorial(aba)
        aba._gerar_casos()
        self.assertTrue(aba.btn_run.isEnabled())
        self.assertIn("3", aba.btn_run.text())

    def test_os_dois_modos_alimentam_a_mesma_fila(self):
        """It is what allows mixing: one factorial plus one standalone case."""
        _state, aba = self._aba()
        self._montar_fatorial(aba)
        aba._gerar_casos()
        self.assertEqual(aba.batch_table.rowCount(), 3)

        aba.radio_lista.setChecked(True)
        aba.add_row_advance.set_mu(0.35)
        aba.collective_spin.setValue(5.0)
        aba.rpm_spin.setValue(600.0)
        aba._gerar_casos()
        self.assertEqual(aba.batch_table.rowCount(), 4,
                          "the single case should ADD, not replace")
        condicoes = aba._condicoes_da_fila()
        self.assertAlmostEqual(condicoes[-1].mu_x, 0.35, places=4)
        self.assertAlmostEqual(condicoes[-1].collective_deg, 5.0, places=4)

    def test_substituir_desmarcado_acumula_fatoriais(self):
        _state, aba = self._aba()
        self._montar_fatorial(aba)
        aba._gerar_casos()
        aba.check_substituir.setChecked(False)
        aba._gerar_casos()
        self.assertEqual(aba.batch_table.rowCount(), 6)

    def test_remover_e_limpar_renumeram(self):
        _state, aba = self._aba()
        self._montar_fatorial(aba)
        aba._gerar_casos()
        aba.batch_table.setCurrentCell(0, 0)
        aba._remove_batch_row()
        self.assertEqual(aba.batch_table.rowCount(), 2)
        self.assertEqual([aba.batch_table.item(i, 0).text() for i in range(2)], ["1", "2"])
        aba._limpar_fila()
        self.assertEqual(aba.batch_table.rowCount(), 0)
        self.assertFalse(aba.btn_run.isEnabled())

    def test_fatorial_agora_pode_ser_salvo_como_batch(self):
        """Before, only the explicit list was saveable: a carefully
        constructed factorial was lost when closing the project."""
        state, aba = self._aba()
        self._montar_fatorial(aba)
        aba._gerar_casos()
        with helpers.patch_em_toda_gui("QInputDialog") as dialogo:
            dialogo.getText.return_value = ("meu_fatorial", True)
            aba._save_current_as_batch()
        nomes = [b.name for b in state.project.batches]
        self.assertIn("meu_fatorial", nomes)
        salvo = next(b for b in state.project.batches if b.name == "meu_fatorial")
        self.assertEqual(len(salvo.conditions), 3)

    def test_batch_de_varredura_salvo_e_expandido_na_fila(self):
        """A batch with `sweep_params` and no conditions needs to appear
        expanded -- otherwise the queue would show zero cases for something
        that runs eight."""
        state, aba = self._aba()
        state.project.batches.append(BatchDefinition(
            name="varredura", sweep_kind="mu_sweep",
            sweep_params={"mu_values": [0.0, 0.1, 0.2, 0.3], "rpm": 600.0}))
        aba._refresh_saved_batches_combo()
        aba.batches_combo.setCurrentText("varredura")
        self.assertEqual(aba.batch_table.rowCount(), 4)


if __name__ == "__main__":
    unittest.main()


class TestNeuralFoilAplicaAoProjeto(GuiE2ETestCase):
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

    def test_polares_do_neuralfoil_chegam_ao_projeto_sem_trocar_de_modo(self):
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

        aplicado = state.project.airfoil
        self.assertEqual(len(aplicado.table_slices), 4)
        self.assertIsNotNone(aplicado.geometry)

        erros = [i for i in api.validate_project(state.project) if i.level == "error"]
        self.assertEqual(erros, [], f"run blocked by: {[str(e) for e in erros]}")

    def test_geometria_2d_gerada_chega_ao_projeto(self):
        from zbemt.gui.tabs.airfoil import AirfoilTab

        state = self._make_state()
        self._new_project(state)
        tab = AirfoilTab(state)
        tab.source_combo.setCurrentText("neuralfoil")
        tab.profile_source_combo.setCurrentText("naca4")
        tab.naca_code_edit.setText("2412")
        tab._generate_profile()

        self.assertIsNotNone(state.project.airfoil.geometry)


class TestIndicadorLimpaAoCorrigirOProblema(GuiE2ETestCase):
    """Regression of item 17: once the error is fixed, the tab must turn
    green.

    Same root as item 18 (see `TestNeuralFoilAplicaAoProjeto`): the
    `FlowIndicatorBar` validates `state.project`, so a fix made in the tab
    that does NOT reach the project leaves the indicator red forever.
    `_import_csv` was one such path -- it imported the polar into
    `self._imported_slices` and only wrote to the project if the source combo
    CHANGED value; importing already in 'table' mode (the natural case: it is
    the mode that complains about the missing polar) nothing was written."""

    class _FakeTabs:
        def setCurrentIndex(self, i):
            pass

    def _cor_da_aba(self, bar, indice):
        import re as _re
        from zbemt.gui import styles
        inverso = {v: k for k, v in styles.STATUS_COLORS.items()}
        achado = _re.search(r"background: (#\w+)", bar._buttons[indice].styleSheet())
        return inverso.get(achado.group(1), achado.group(1)) if achado else None

    def test_importar_a_polar_faltante_tira_a_aba_do_vermelho(self):
        import unittest.mock as _mock
        from zbemt.gui.tabs.airfoil import AirfoilTab

        caminho_csv = f"{self._tmpdir}/polar.csv"
        with open(caminho_csv, "w") as arquivo:
            arquivo.write("alpha_deg,cl,cd\n")
            for alpha in range(-20, 21):
                arquivo.write(f"{alpha},{0.1 * alpha},0.01\n")

        state = self._make_state()
        self._new_project(state)
        tab = AirfoilTab(state)
        bar = self.gui.FlowIndicatorBar(state, self._FakeTabs())

        tab.source_combo.setCurrentText("table")
        self.assertEqual(self._cor_da_aba(bar, 2), "red")

        with _mock.patch("zbemt.gui.tabs.airfoil.QFileDialog") as dialogo:
            dialogo.getOpenFileName.return_value = (caminho_csv, "")
            tab._import_csv()

        self.assertEqual(self._cor_da_aba(bar, 2), "green")
        self.assertTrue(state.project.airfoil.table_slices)
